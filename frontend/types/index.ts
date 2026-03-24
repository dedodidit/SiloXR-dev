// frontend/types/index.ts

export interface Product {
  id:                     string
  name:                   string
  sku:                    string
  unit:                   string
  category:               string
  selling_price?:         number | null
  supplier_name?:         string | null
  last_verified_quantity: number
  last_verified_at:       string | null
  estimated_quantity:     number
  confidence_score:       number
  confidence_label:       "high" | "moderate" | "low" | "very_low"
  reorder_point:          number
  reorder_quantity:       number
  needs_verification:     boolean
  quantity_gap:           number
  active_decision:        ActiveDecisionSummary | null
  days_remaining:         number | null
  demand_direction?:      "increasing" | "decreasing" | "steady" | null
  maturity_tier?:         string | null
  data_maturity_score?:   number | null
  is_active:              boolean
  updated_at:             string
  burn_rate?:             BurnRateSummary | null
  forecast_strip?:        ForecastStrip[]
  recent_events?:         InventoryEventSummary[]
}

export interface ActiveDecisionSummary {
  id:               string
  action:           DecisionAction
  severity:         Severity
  confidence_score: number
  reasoning:        string
  created_at:       string
}

export interface Decision {
  id:                              string
  product_id:                      string
  product_sku:                     string
  product_name:                    string
  action:                          DecisionAction
  severity:                        Severity
  reasoning:                       string
  gated_reasoning?:                string
  confidence_score:                number
  confidence_label:                string
  estimated_quantity_at_decision:  number
  days_remaining_at_decision:      number | null
  burn_rate_at_decision:           number | null
  estimated_lost_sales:            number
  estimated_revenue_loss:          number
  impact?:                         number
  impact_summary?: {
    visible: boolean
    lost_sales_units?: number
    revenue_loss?: number
    has_revenue_estimate?: boolean
  }
  risk_score:                      number
  priority_score:                  number
  confidence_level?:               string
  confidence_phrase?:              string
  data_stale?:                     boolean
  assumption_message?:             string
  status:                          "suggested" | "viewed" | "acted" | "ignored"
  viewed_at:                       string | null
  acted_at:                        string | null
  outcome_label:                   string | null
  is_acknowledged:                 boolean
  acknowledged_at:                 string | null
  is_active:                       boolean
  is_expired:                      boolean
  expires_at:                      string
  created_at:                      string
}

export interface UserContextSummary {
  name:          string
  business_name: string
  business_type: string
  country?:      string
  currency?:     string
  tier:          "free" | "pro"
  is_pro:        boolean
}

export interface ForecastStrip {
  forecast_date:      string
  predicted_quantity: number
  lower_bound:        number
  upper_bound:        number
  confidence_score:   number
  days_from_today:    number
}

export interface BurnRateSummary {
  rate_per_day: number
  std_dev: number
  confidence: number
  sample_days: number
  computed_at: string
}

export interface InventoryEventSummary {
  id: string
  event_type: string
  quantity: number
  signed_quantity: number
  verified_quantity?: number | null
  notes?: string
  occurred_at: string
  created_at: string
}

export interface DashboardSummary {
  total_products:           number
  products_needing_action:  number
  products_low_confidence:  number
  critical_alerts:          number
  avg_confidence:           number
  tier:                     "free" | "pro"
  is_pro:                   boolean
  active_decisions:         Decision[] | null
  top_priorities:           Decision[]
  urgent_products:          Product[]
  contextual_insights:      string[]
  user_context:             UserContextSummary
  journey_hint:             string
  last_learning_at:         string | null
  stockouts_within_7d:      number
  revenue_at_risk_total:    number
  stale_products_count:     number
  actioned_decisions_14d:   number
  ignored_decisions_14d:    number
  managerial_brief: {
    headline: string
    subtext: string
  }
  managerial_signals: ManagerialSignal[]
  usage_policy: {
    tier: "free" | "pro"
    unlimited: boolean
    refresh_interval_seconds: number
    policy_summary: string
  }
  operating_assumption: string
  baseline_in_use?: boolean
  demand_deficits?: DemandDeficit[]
}

export interface DemandDeficit {
  product_name: string
  category?: string
  generic_category?: string
  cv_estimate?: number
  expected_daily_demand: number
  observed_daily_demand: number
  demand_gap: number
  revenue_risk_daily: number
  revenue_risk_weekly: number
  customers_lost_daily: number
  confidence: number
  likely_causes: string[]
  explanation: string
}

export interface PortfolioSummary {
  total_revenue_at_risk: number
  products_needing_action: number
  top_decisions: Decision[]
  forecast_accuracy: number
  confidence_score: number
  overstock_capital: number
}

export interface BusinessHealthSummary {
  estimated_monthly_revenue: number
  estimated_weekly_revenue: number
  potential_revenue_gap_weekly: number
  confidence_score: number
}

export interface BusinessHealthTopProduct {
  name: string
  estimated_weekly_revenue: number
}

export interface BusinessHealthDemandGap {
  name: string
  expected_weekly_demand: number
  observed_weekly_demand: number
  gap_units: number
  gap_revenue: number
  confidence: number
}

export interface BusinessHealthReport {
  summary: BusinessHealthSummary
  top_products: BusinessHealthTopProduct[]
  demand_gaps: BusinessHealthDemandGap[]
  insights: string[]
  investor_summary: string
}

export interface ReorderRecord {
  id: string
  product: string
  product_name: string
  product_sku: string
  decision_id?: string | null
  suggested_quantity: number
  suggested_date: string | null
  status: "pending" | "placed" | "received"
  notes: string
  created_at: string
  updated_at: string
}

export interface DecisionSimulationScenario {
  label: string
  delay_days: number
  projected_stock: number
  projected_stockout_date: string | null
  estimated_revenue_loss: number
  confidence: number
}

export interface DecisionSimulationResponse {
  available: boolean
  recommended: DecisionSimulationScenario | null
  alternatives: DecisionSimulationScenario[]
  reason?: string
}

export interface ManagerialSignal {
  key:            string
  title:          string
  value:          string
  summary:        string
  recommendation: string
  tone:           "critical" | "warning" | "safe"
  target:         "decisions" | "stockouts" | "products" | "decisions_queue"
}

export interface InventoryEventCreate {
  event_type:        string
  quantity:          number
  verified_quantity?: number
  notes?:            string
  occurred_at?:      string
  client_event_id?:  string
  is_offline_event?: boolean
}

export type DecisionAction =
  | "REORDER" | "CHECK_STOCK" | "HOLD"
  | "ALERT_LOW" | "ALERT_CRITICAL" | "MONITOR"

export type Severity = "critical" | "warning" | "info" | "ok"
