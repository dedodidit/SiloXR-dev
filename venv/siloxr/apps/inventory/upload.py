# backend/apps/inventory/upload.py

"""
Data Upload Processor.

Handles CSV, Excel, and basic PDF table imports.
All events created through EventProcessor to maintain
the time-series contract.

Supported formats:
  CSV:   product_name, sku, date, quantity, event_type
  Excel: same schema, first sheet
  PDF:   basic table extraction (best-effort)

Sample dataset available at /api/v1/upload/sample/
"""

import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Expected column names (flexible mapping) ───────────────────────────────────
COLUMN_MAP = {
    "product":    ["product", "product_name", "name", "item"],
    "sku":        ["sku", "code", "product_code", "item_code"],
    "date":       ["date", "occurred_at", "transaction_date", "sale_date"],
    "quantity":   ["quantity", "qty", "units", "amount"],
    "event_type": ["event_type", "type", "transaction_type"],
}

VALID_EVENT_TYPES = {"SALE", "RESTOCK", "STOCK_COUNT", "ADJUSTMENT", "WASTE"}


class UploadProcessor:
    """
    Processes uploaded data files and imports events.
    Returns a structured result with row-level success/failure detail.
    """

    def process(
        self,
        file_content: bytes,
        file_type:    str,
        user,
        default_event_type: str = "SALE",
    ) -> dict:
        """
        Main entry point. Returns:
        {
            "created":  int,
            "skipped":  int,
            "errors":   list[str],
            "products_created": list[str],
        }
        """
        if file_type == "csv":
            rows = self._parse_csv(file_content)
        elif file_type in ("xlsx", "xls"):
            rows = self._parse_excel(file_content)
        elif file_type == "pdf":
            rows = self._parse_pdf(file_content)
        else:
            return {"error": f"Unsupported file type: {file_type}"}

        return self._import_rows(rows, user, default_event_type)

    def _parse_csv(self, content: bytes) -> list[dict]:
        import csv
        text    = content.decode("utf-8", errors="replace")
        reader  = csv.DictReader(io.StringIO(text))
        return [self._normalise_row(row) for row in reader]

    def _parse_excel(self, content: bytes) -> list[dict]:
        try:
            import openpyxl
            wb  = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws  = wb.active
            headers = [str(c.value or "").lower().strip() for c in ws[1]]
            rows    = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                raw = {headers[i]: (row[i] if i < len(row) else None)
                       for i in range(len(headers))}
                rows.append(self._normalise_row(raw))
            return rows
        except ImportError:
            raise ImportError("openpyxl is required for Excel upload. Run: pip install openpyxl")

    def _parse_pdf(self, content: bytes) -> list[dict]:
        """Best-effort PDF table extraction."""
        try:
            import pdfplumber
            rows = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        headers = [str(h or "").lower().strip() for h in table[0]]
                        for row_data in table[1:]:
                            raw = {headers[i]: row_data[i]
                                   for i in range(min(len(headers), len(row_data)))}
                            rows.append(self._normalise_row(raw))
            return rows
        except ImportError:
            raise ImportError("pdfplumber is required for PDF upload. Run: pip install pdfplumber")

    def _normalise_row(self, raw: dict) -> dict:
        """Map flexible column names to our standard schema."""
        result = {}
        raw_lower = {k.lower().strip(): v for k, v in raw.items()}
        for field, aliases in COLUMN_MAP.items():
            for alias in aliases:
                if alias in raw_lower:
                    result[field] = raw_lower[alias]
                    break
        return result

    def _import_rows(
        self, rows: list[dict], user, default_event_type: str
    ) -> dict:
        from apps.inventory.models import Product, InventoryEvent
        from apps.inventory.events import EventProcessor
        from django.utils import timezone as tz
        from django.utils.dateparse import parse_date, parse_datetime

        created          = 0
        skipped          = 0
        errors           = []
        products_created = []

        for i, row in enumerate(rows, start=2):
            try:
                product_name = str(row.get("product") or "").strip()
                sku          = str(row.get("sku") or product_name[:20]).strip().upper()
                if not product_name or not sku:
                    skipped += 1
                    continue

                raw_qty = row.get("quantity")
                try:
                    qty = float(str(raw_qty or "0").replace(",", ""))
                except ValueError:
                    errors.append(f"Row {i}: invalid quantity '{raw_qty}'")
                    skipped += 1
                    continue

                raw_date  = row.get("date")
                occurred  = tz.now()
                if raw_date:
                    occurred = self._parse_occurred_at(str(raw_date), fallback=occurred)

                raw_type   = str(row.get("event_type") or default_event_type).upper()
                event_type = raw_type if raw_type in VALID_EVENT_TYPES else default_event_type

                # Get or create product
                product, was_created = Product.objects.get_or_create(
                    sku=sku,
                    defaults={
                        "owner": user,
                        "name":  product_name,
                        "unit":  "units",
                    },
                )
                if was_created:
                    products_created.append(sku)

                # Create event via EventProcessor
                processor = EventProcessor(product)
                kwargs = {
                    "event_type":  event_type,
                    "quantity":    abs(qty),
                    "occurred_at": occurred,
                    "recorded_by": user,
                    "notes":       f"Imported from file upload",
                }
                if event_type == InventoryEvent.STOCK_COUNT:
                    kwargs["verified_quantity"] = int(abs(qty))
                    kwargs["quantity"]           = 0

                processor.record(**kwargs)
                created += 1

            except Exception as exc:
                errors.append(f"Row {i}: {exc}")
                skipped += 1
                logger.warning("Upload row %d failed: %s", i, exc)

        return {
            "created":          created,
            "skipped":          skipped,
            "errors":           errors[:20],   # cap error list
            "products_created": products_created,
        }

    def _parse_occurred_at(self, raw_date: str, fallback):
        from django.utils import timezone as tz
        from django.utils.dateparse import parse_date, parse_datetime

        value = str(raw_date or "").strip()
        if not value:
            return fallback

        parsed_dt = parse_datetime(value)
        if parsed_dt:
            if tz.is_naive(parsed_dt):
                return tz.make_aware(parsed_dt, tz.get_current_timezone())
            return parsed_dt

        parsed_date = parse_date(value)
        if parsed_date:
            naive = datetime.combine(parsed_date, datetime.min.time())
            return tz.make_aware(naive, tz.get_current_timezone())

        for pattern in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
            try:
                parsed = datetime.strptime(value, pattern)
                if "H:%M" in pattern:
                    return tz.make_aware(parsed, tz.get_current_timezone())
                return tz.make_aware(datetime.combine(parsed.date(), datetime.min.time()), tz.get_current_timezone())
            except ValueError:
                continue

        return fallback


SAMPLE_CSV = """product_name,sku,date,quantity,event_type
Palm Oil 5L,PO-5L-001,2026-02-01,50,RESTOCK
Palm Oil 5L,PO-5L-001,2026-02-03,5,SALE
Palm Oil 5L,PO-5L-001,2026-02-04,8,SALE
Palm Oil 5L,PO-5L-001,2026-02-05,6,SALE
Palm Oil 5L,PO-5L-001,2026-02-08,10,SALE
Palm Oil 5L,PO-5L-001,2026-02-10,45,STOCK_COUNT
Indomie Noodles,NDL-001,2026-02-01,200,RESTOCK
Indomie Noodles,NDL-001,2026-02-01,30,SALE
Indomie Noodles,NDL-001,2026-02-02,25,SALE
Indomie Noodles,NDL-001,2026-02-03,40,SALE
Indomie Noodles,NDL-001,2026-02-05,35,SALE
Indomie Noodles,NDL-001,2026-02-07,180,STOCK_COUNT
Sachet Water,SW-500-001,2026-02-01,500,RESTOCK
Sachet Water,SW-500-001,2026-02-01,80,SALE
Sachet Water,SW-500-001,2026-02-02,95,SALE
Sachet Water,SW-500-001,2026-02-03,110,SALE
Sachet Water,SW-500-001,2026-02-04,100,SALE
Sachet Water,SW-500-001,2026-02-05,90,SALE
"""

SAMPLE_SALES_CSV = """product_name,sku,date,quantity,event_type
Palm Oil 5L,PO-5L-001,2026-02-03 09:15,5,SALE
Palm Oil 5L,PO-5L-001,2026-02-04 10:05,8,SALE
Indomie Noodles,NDL-001,2026-02-03 14:30,40,SALE
Sachet Water,SW-500-001,2026-02-05 16:10,90,SALE
"""

SAMPLE_STOCK_CSV = """product_name,sku,date,quantity,event_type
Palm Oil 5L,PO-5L-001,2026-02-01 08:00,50,RESTOCK
Palm Oil 5L,PO-5L-001,2026-02-10 18:00,45,STOCK_COUNT
Indomie Noodles,NDL-001,2026-02-01 08:30,200,RESTOCK
Indomie Noodles,NDL-001,2026-02-07 17:45,180,STOCK_COUNT
"""
