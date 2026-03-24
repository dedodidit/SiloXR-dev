export const countryOptions = [
  { value: "", label: "Select country" },
  { value: "nigeria", label: "Nigeria" },
  { value: "ghana", label: "Ghana" },
  { value: "kenya", label: "Kenya" },
  { value: "south africa", label: "South Africa" },
  { value: "united kingdom", label: "United Kingdom" },
  { value: "united states", label: "United States" },
  { value: "canada", label: "Canada" },
  { value: "india", label: "India" },
  { value: "uae", label: "United Arab Emirates" },
  { value: "other", label: "Other" },
]

export const currencyOptions = [
  { value: "USD", label: "USD ($)" },
  { value: "NGN", label: "NGN (₦)" },
  { value: "GHS", label: "GHS (GH₵)" },
  { value: "KES", label: "KES (KSh)" },
  { value: "ZAR", label: "ZAR (R)" },
  { value: "GBP", label: "GBP (£)" },
  { value: "EUR", label: "EUR (€)" },
  { value: "CAD", label: "CAD (C$)" },
  { value: "INR", label: "INR (₹)" },
  { value: "AED", label: "AED" },
]

export const formatMoney = (value: number, currency = "USD") => {
  const amount = Number(value || 0)
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: String(currency || "USD").toUpperCase(),
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return `${String(currency || "USD").toUpperCase()} ${Math.round(amount).toLocaleString()}`
  }
}
