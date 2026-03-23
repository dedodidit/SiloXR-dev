<script setup lang="ts">
import { findWorkspaceSection } from "../../constants/workspaceSections"
import { useDecisionStore } from "../../stores/decisions"
import { useInventoryStore } from "../../stores/inventory"
import { useDashboard } from "../../composables/useDashboard"
import { useBusinessHealth } from "../../composables/useBusinessHealth"
import { useDecisions } from "../../composables/useDecisions"
import { useInventory } from "../../composables/useInventory"
import { useOfflineQueue } from "../../composables/useOfflineQueue"

const route = useRoute()
const slug = computed(() => String(route.params.slug ?? ""))
const legacyWorkspaceRedirects: Record<string, string> = {
  "decision-orientation": "command-center",
  "portfolio-money-view": "command-center",
  "primary-decision": "decision-workbench",
  "decision-stack": "decision-workbench",
  "next-actions": "decision-workbench",
  "demand-trend": "demand-intelligence",
  "top-opportunities": "demand-intelligence",
  "business-trend": "product-operations",
  "forecast-strip": "product-operations",
  "all-products": "product-operations",
}
const resolvedSlug = computed(() => legacyWorkspaceRedirects[slug.value] ?? slug.value)
const section = computed(() => findWorkspaceSection(resolvedSlug.value))

if (!section.value) {
  throw createError({ statusCode: 404, statusMessage: "Workspace not found" })
}

const { summary, loading: summaryLoading, refresh } = useDashboard()
const { fetchBusinessHealthReport } = useBusinessHealth()
const dashboardRefreshTick = useState<number>("dashboard-refresh-tick", () => 0)
const decisionStore = useDecisionStore()
const inventoryStore = useInventoryStore()
const { fetchForecastStrip, fetchPortfolioSummary } = useDecisions()
const { updateProduct, deleteProduct } = useInventory()
const offlineQueue = useOfflineQueue()

const selectedProduct = ref<any>(null)
const forecastStrip = ref<any[]>([])
const portfolioSummary = ref<any>(null)
const businessHealthReport = ref<any>(null)

const isLoading = computed(() => summaryLoading.value || inventoryStore.loading)
const demandDeficits = computed(() => (summary.value?.demand_deficits ?? []).slice(0, 3))
const totalWeeklyDeficitRisk = computed(() =>
  demandDeficits.value.reduce((sum, item) => sum + Number(item?.revenue_risk_weekly ?? 0), 0)
)
const topPriorityList = computed(() =>
  portfolioSummary.value?.top_decisions?.length
    ? portfolioSummary.value.top_decisions
    : summary.value?.top_priorities?.length
    ? summary.value.top_priorities
    : decisionStore.topPriorities
)
const topDecisions = computed(() =>
  [...decisionStore.decisions]
    .sort((a, b) => {
      const order: Record<string, number> = { critical: 0, warning: 1, info: 2, ok: 3 }
      return (order[a.severity] ?? 3) - (order[b.severity] ?? 3)
    })
    .slice(0, 5)
)
const heroDecision = computed(() =>
  topPriorityList.value[0] ?? topDecisions.value[0] ?? summary.value?.active_decisions?.[0] ?? null
)
const heroItems = computed(() => {
  const seen = new Set<string>()
  return [...topPriorityList.value, ...topDecisions.value]
    .filter((item) => {
      if (seen.has(item.id)) return false
      seen.add(item.id)
      return true
    })
    .slice(0, 3)
})
const portfolioConfidence = computed(() => portfolioSummary.value?.confidence_score ?? summary.value?.avg_confidence ?? 0)
const topSellingProducts = computed(() => {
  return [...inventoryStore.products]
    .map((product) => {
      const daysRemaining = Number(product.days_remaining ?? 0)
      const estimatedQuantity = Number(product.estimated_quantity ?? 0)
      const estimatedDailyUnits =
        daysRemaining > 0 && estimatedQuantity > 0
          ? estimatedQuantity / Math.max(daysRemaining, 0.5)
          : 0
      return {
        name: product.name,
        value: estimatedDailyUnits,
        subtitle: product.demand_direction ? `${product.demand_direction} demand` : "current demand pattern",
      }
    })
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 7)
})
const primaryDemandDeficit = computed(() => demandDeficits.value[0] ?? null)
const showSpecificDeficitLabels = computed(() =>
  !summary.value?.baseline_in_use || Number(summary.value?.total_products ?? 0) >= 5
)
const revenueAtRisk = computed(() => {
  if (demandDeficits.value.length && totalWeeklyDeficitRisk.value > 0) return Math.round(totalWeeklyDeficitRisk.value)
  return Math.round(portfolioSummary.value?.total_revenue_at_risk ?? summary.value?.revenue_at_risk_total ?? 0)
})
const productsAtRisk = computed(() => {
  if (demandDeficits.value.length) return demandDeficits.value.length
  return portfolioSummary.value?.products_needing_action ?? summary.value?.products_needing_action ?? 0
})
const avgDailyRisk = computed(() => {
  const value = portfolioSummary.value?.total_revenue_at_risk ?? summary.value?.revenue_at_risk_total ?? 0
  return value > 0 ? Math.round(value / 7) : null
})
const portfolioMode = computed<"portfolio" | "baseline" | "building">(() => {
  if (summary.value?.baseline_in_use && !demandDeficits.value.length) return "building"
  if (demandDeficits.value.length) return "baseline"
  return "portfolio"
})
const portfolioEyebrow = computed(() => {
  if (portfolioMode.value === "baseline") return "Cost of inaction"
  if (portfolioMode.value === "building") return "Learning mode"
  return "Portfolio at risk"
})
const portfolioSubtitle = computed(() => {
  if (portfolioMode.value === "baseline") return "estimated from similar businesses in your category and size range"
  if (portfolioMode.value === "building") return "baseline expectations are active while we learn your business pattern"
  return "potential revenue loss this week"
})
const portfolioCtaLabel = computed(() => {
  if (portfolioMode.value === "baseline") return "Review demand gaps"
  if (portfolioMode.value === "building") return "Record more activity"
  return "Review decisions"
})

const normalizedName = (value: string) =>
  (value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()

const genericCategoryLabel = (deficit: any) => {
  const key = String(deficit?.generic_category ?? deficit?.category ?? "").toLowerCase()
  const labels: Record<string, string> = {
    bread: "fast-moving staples",
    carbonated_soft_drink: "popular beverages",
    bottled_water: "bottled water",
    cooking_oil: "cooking oil staples",
    rice: "rice staples",
    otc: "over-the-counter demand",
    prescription: "prescription lines",
  }
  return labels[key] ?? "high-demand items"
}

const displayDeficitName = (deficit: any) =>
  showSpecificDeficitLabels.value ? deficit?.product_name : genericCategoryLabel(deficit)

const commandCenterSummary = computed(() => {
  if (demandDeficits.value.length && totalWeeklyDeficitRisk.value > 0) {
    return `Up to ₦${Math.round(totalWeeklyDeficitRisk.value).toLocaleString()}/week may still be exposed across ${demandDeficits.value.length} high-demand signal${demandDeficits.value.length === 1 ? "" : "s"}.`
  }
  return "We are analyzing your business and preparing a stronger operating picture from live activity."
})
const nextActionCopy = computed(() => {
  if (heroItems.value.length) {
    return `Start with ${heroItems.value[0]?.action ?? "the top action"}, then move through the remaining high-urgency items.`
  }
  return "Record one product or stock event to unlock stronger recommendations."
})
const riskReviewSentence = computed(() => {
  if (topDecisions.value.length) {
    return `${topDecisions.value.length} active decision${topDecisions.value.length === 1 ? "" : "s"} are currently shaping the highest-priority queue.`
  }
  return "No active decision queue yet. SiloXR will populate this workbench as signals mature."
})
const opportunitySentence = computed(() => {
  if (topSellingProducts.value.length) {
    return `The strongest current opportunity is ${topSellingProducts.value[0]?.name}, based on the latest demand pattern.`
  }
  return "Opportunity ranking will become more useful as product demand patterns form."
})
const productOpsSentence = computed(() => {
  if (selectedProduct.value?.name) {
    return `${selectedProduct.value.name} is currently in focus, with forecast, quick actions, and product controls aligned in one place.`
  }
  return "Choose a product to bring its forecast, stock controls, and product actions into one flow."
})
const sparseDecisionSentence = computed(() => {
  if (selectedProduct.value?.name) {
    return `Start with ${selectedProduct.value.name}. One verified stock count or sale event will let SiloXR begin ranking live decisions here.`
  }
  return "Add one product and record a stock event to unlock the first live decision."
})
const sparseCommandCopy = computed(() => {
  if (selectedProduct.value?.name) {
    return `Use ${selectedProduct.value.name} as the starting point. Verifying stock first gives the next decision cycle a stronger base.`
  }
  return "Start with one product and one stock event. That gives SiloXR enough signal to begin shaping live recommendations."
})

const recordStarterSale = async () => {
  if (!selectedProduct.value?.id) return
  await handleQuickSale(selectedProduct.value)
}

const verifyStarterStock = async () => {
  if (!selectedProduct.value?.id) return
  await handleSyncShelf(selectedProduct.value)
}

const onSelectProduct = async (product: any) => {
  if (!product?.id) return
  selectedProduct.value = product
  await inventoryStore.select(product.id)
  forecastStrip.value = await fetchForecastStrip(product.id, 7).catch(() => [])
}

const focusProductById = async (productId: string) => {
  const product = inventoryStore.products.find((item) => item.id === productId)
  if (!product) return
  await onSelectProduct(product)
}

const openRecordEvent = async (product: any) => {
  if (!product?.id) return
  await navigateTo(`/products/${product.id}`)
}

const handleQuickSale = async (product: any) => {
  if (!product?.id) return
  await offlineQueue.recordEvent(product.id, {
    event_type: "SALE",
    quantity: 1,
    occurred_at: new Date().toISOString(),
  })
  await reloadWorkspaceData()
}

const handleQuickRestock = async (product: any) => {
  if (!product?.id) return
  await offlineQueue.recordEvent(product.id, {
    event_type: "RESTOCK",
    quantity: 1,
    occurred_at: new Date().toISOString(),
    notes: "Quick restock",
  })
  await reloadWorkspaceData()
}

const handleSyncShelf = async (product: any) => {
  if (!product?.id) return
  await offlineQueue.recordEvent(product.id, {
    event_type: "STOCK_COUNT",
    quantity: 0,
    verified_quantity: Math.max(0, Math.round(product.estimated_quantity ?? 0)),
    occurred_at: new Date().toISOString(),
    notes: "Shelf sync",
  })
  await reloadWorkspaceData()
}

const handleRepeatLastCount = async (product: any) => {
  if (!product?.id || product.last_verified_quantity == null) return
  await offlineQueue.recordEvent(product.id, {
    event_type: "STOCK_COUNT",
    quantity: 0,
    verified_quantity: Math.max(0, Number(product.last_verified_quantity)),
    occurred_at: new Date().toISOString(),
    notes: "Repeated last count",
  })
  await reloadWorkspaceData()
}

const handleInventoryEntry = async ({
  product,
  event,
}: {
  product: any
  event: {
    event_type: string
    quantity: number
    verified_quantity?: number
    occurred_at?: string
    notes?: string
  }
}) => {
  if (!product?.id) return
  await offlineQueue.recordEvent(product.id, event)
  await reloadWorkspaceData()
}

const handleInlineUpdate = async ({ id, data }: { id: string; data: Record<string, unknown> }) => {
  try {
    const updated = await updateProduct(id, data)
    inventoryStore.upsert(updated)
    if (selectedProduct.value?.id === id) selectedProduct.value = updated
    await syncSelectedContext()
  } catch {}
}

const handleDeleteProduct = async (product: any) => {
  if (!product?.id) return
  try {
    await deleteProduct(product.id)
    if (selectedProduct.value?.id === product.id) selectedProduct.value = null
    await reloadWorkspaceData()
  } catch {}
}

const workspaceTitle = computed(() => section.value?.title ?? "Workspace")
const workspaceHint = computed(() => section.value?.helper ?? "")
const productVelocityRows = computed(() =>
  inventoryStore.products.map((product) => {
    const daysRemaining = Number(product.days_remaining ?? 0)
    const estimatedQuantity = Number(product.estimated_quantity ?? 0)
    const burnRate = Number(product.burn_rate?.rate_per_day ?? 0)
    const estimatedDailyUnits =
      burnRate > 0
        ? burnRate
        : daysRemaining > 0 && estimatedQuantity > 0
        ? estimatedQuantity / Math.max(daysRemaining, 0.5)
        : 0
    const weeklyRevenue = Number(product.selling_price ?? 0) * estimatedDailyUnits * 7

    return {
      name: product.name,
      category: product.category,
      estimatedDailyUnits,
      weeklyRevenue,
      confidence: Number(product.confidence_score ?? 0),
      daysRemaining,
      quantityGap: Number(product.quantity_gap ?? 0),
    }
  })
)
const fallbackBusinessHealthTopProducts = computed(() =>
  productVelocityRows.value
    .filter((item) => item.weeklyRevenue > 0)
    .sort((a, b) => b.weeklyRevenue - a.weeklyRevenue)
    .slice(0, 5)
    .map((item) => ({
      name: item.name,
      estimated_weekly_revenue: Math.round(item.weeklyRevenue),
    }))
)
const fallbackBusinessHealthDemandGaps = computed(() =>
  demandDeficits.value.map((gap: any) => ({
    name: gap.product_name,
    expected_weekly_demand: Number(gap.expected_daily_demand ?? 0) * 7,
    observed_weekly_demand: Number(gap.observed_daily_demand ?? 0) * 7,
    gap_units: Number(gap.demand_gap ?? 0) * 7,
    gap_revenue: Number(gap.revenue_risk_weekly ?? 0),
    confidence: Number(gap.confidence ?? summary.value?.avg_confidence ?? 0),
  }))
)
const businessHealthSummary = computed(() => businessHealthReport.value?.summary ?? null)
const businessHealthTopProducts = computed(() =>
  businessHealthReport.value?.top_products?.length
    ? businessHealthReport.value.top_products
    : fallbackBusinessHealthTopProducts.value
)
const businessHealthDemandGaps = computed(() =>
  businessHealthReport.value?.demand_gaps?.length
    ? businessHealthReport.value.demand_gaps
    : fallbackBusinessHealthDemandGaps.value
)
const analyticsWeeklyRevenue = computed(() => {
  const reportValue = Number(businessHealthSummary.value?.estimated_weekly_revenue ?? 0)
  if (reportValue > 0) return reportValue
  return productVelocityRows.value.reduce((sum, item) => sum + item.weeklyRevenue, 0)
})
const analyticsMonthlyRevenue = computed(() => analyticsWeeklyRevenue.value * 4)
const analyticsGapWeekly = computed(() => {
  const reportValue = Number(businessHealthSummary.value?.potential_revenue_gap_weekly ?? 0)
  if (reportValue > 0) return reportValue
  return businessHealthDemandGaps.value.reduce((sum, item) => sum + Number(item.gap_revenue ?? 0), 0)
})
const analyticsConfidence = computed(() => {
  const reportValue = Number(businessHealthSummary.value?.confidence_score ?? 0)
  if (reportValue > 0) return reportValue
  return Number(portfolioSummary.value?.confidence_score ?? summary.value?.avg_confidence ?? 0)
})
const businessHealthInsights = computed(() => {
  if (businessHealthReport.value?.insights?.length) return businessHealthReport.value.insights

  const insights: string[] = []
  if (analyticsGapWeekly.value > 0 && businessHealthDemandGaps.value.length) {
    insights.push(
      `${businessHealthDemandGaps.value.length} benchmark gap${businessHealthDemandGaps.value.length === 1 ? "" : "s"} currently account for about ${formatCurrency(analyticsGapWeekly.value)} per week in revenue shortfall.`
    )
  }
  if (businessHealthTopProducts.value.length) {
    const names = businessHealthTopProducts.value.slice(0, 3).map((item: any) => item.name).join(", ")
    insights.push(`Current revenue concentration sits in ${names}.`)
  }
  if (Number(summary.value?.stale_products_count ?? 0) > 0) {
    insights.push(
      `${summary.value?.stale_products_count} product${Number(summary.value?.stale_products_count ?? 0) === 1 ? "" : "s"} need fresh verification, which is weakening the confidence of this view.`
    )
  }
  if (Number(summary.value?.products_needing_action ?? 0) > 0) {
    insights.push(
      `${summary.value?.products_needing_action} tracked product${Number(summary.value?.products_needing_action ?? 0) === 1 ? "" : "s"} currently need action to protect commercial performance.`
    )
  }
  if (!insights.length) {
    insights.push("SiloXR is using your live product, stock, and demand signals to build a stronger business intelligence layer here.")
  }
  return insights.slice(0, 5)
})
const investorSummary = computed(() => {
  if (businessHealthReport.value?.investor_summary) return businessHealthReport.value.investor_summary

  const driverNames = businessHealthTopProducts.value.slice(0, 3).map((item: any) => item.name).join(", ") || "current tracked products"
  if (analyticsWeeklyRevenue.value <= 0) {
    return "This business health view is ready, but it needs more live inventory and sales activity before it can describe revenue performance with confidence."
  }
  const gapClause = analyticsGapWeekly.value > 0
    ? `Current benchmark comparison shows about ${formatCurrency(analyticsGapWeekly.value)} per week in revenue shortfall between observed sales and benchmark demand levels.`
    : "Current benchmark comparison does not show a material weekly revenue shortfall between observed sales and benchmark demand levels."
  return `This business is currently processing about ${formatCurrency(analyticsMonthlyRevenue.value)} per month, with key revenue drivers in ${driverNames}. ${gapClause} The confidence level on this operating view is ${Math.round(analyticsConfidence.value * 100)}%.`
})
const healthPillars = computed(() => [
  {
    title: "Coverage health",
    value: Number(summary.value?.total_products ?? inventoryStore.products.length ?? 0),
    label: "tracked products represented in this view",
    tone: Number(summary.value?.total_products ?? inventoryStore.products.length ?? 0) > 0 ? "safe" : "warning",
  },
  {
    title: "Verification debt",
    value: Number(summary.value?.stale_products_count ?? 0),
    label: "products need a fresh stock count",
    tone: Number(summary.value?.stale_products_count ?? 0) > 0 ? "warning" : "safe",
  },
  {
    title: "Observed gaps",
    value: businessHealthDemandGaps.value.length,
    label: "benchmark gaps visible across tracked products",
    tone: businessHealthDemandGaps.value.length > 0 ? "warning" : "safe",
  },
])
const businessHealthPrimaryTitle = computed(() => {
  const monthlyRevenue = analyticsMonthlyRevenue.value
  if (monthlyRevenue <= 0) return "More live operating data will sharpen the current business picture"
  return `Current monthly revenue pace is ${formatCurrency(monthlyRevenue)}`
})
const businessHealthHeroCopy = computed(() => {
  if (investorSummary.value) return investorSummary.value
  return "This workspace turns live inventory and demand signals into a descriptive commercial summary you can review, export, and share."
})
const businessHealthGapCoverage = computed(() => {
  const weeklyRevenue = analyticsWeeklyRevenue.value
  const weeklyGap = analyticsGapWeekly.value
  if (weeklyRevenue <= 0 || weeklyGap <= 0) return null
  return Math.round((weeklyGap / weeklyRevenue) * 100)
})

const formatCurrency = (value: number) => `NGN ${Math.round(Number(value || 0)).toLocaleString()}`

function formatNaira(value: number) {
  return `₦${Math.round(Number(value || 0)).toLocaleString()}`
}

const loadPortfolioSummarySafe = async () => {
  try {
    portfolioSummary.value = await fetchPortfolioSummary()
  } catch {
    portfolioSummary.value = null
  }
}

const loadBusinessHealthSafe = async () => {
  try {
    businessHealthReport.value = await fetchBusinessHealthReport()
  } catch {
    businessHealthReport.value = null
  }
}

const syncSelectedContext = async () => {
  const selectedId = selectedProduct.value?.id
  const nextProduct =
    (selectedId ? inventoryStore.products.find((item) => item.id === selectedId) : null)
    ?? inventoryStore.byUrgency?.[0]
    ?? inventoryStore.products[0]

  if (!nextProduct?.id) {
    selectedProduct.value = null
    forecastStrip.value = []
    return
  }

  selectedProduct.value = nextProduct
  await inventoryStore.select(nextProduct.id).catch(() => null)
  forecastStrip.value = await fetchForecastStrip(nextProduct.id, 7).catch(() => [])
}

const reloadWorkspaceData = async () => {
  await Promise.all([
    inventoryStore.load(),
    refresh(),
    decisionStore.load(),
    loadPortfolioSummarySafe(),
    loadBusinessHealthSafe(),
  ])
  await syncSelectedContext()
}

onMounted(async () => {
  await reloadWorkspaceData()
})

watchEffect(() => {
  const canonical = legacyWorkspaceRedirects[slug.value]
  if (canonical && canonical !== slug.value) {
    navigateTo(`/workspace/${canonical}`, { replace: true })
  }
})

watch(
  () => route.params.slug,
  async () => {
    await syncSelectedContext()
  },
)

watch(dashboardRefreshTick, async () => {
  await reloadWorkspaceData()
})
</script>

<template>
  <div class="workspace page-pad">
    <div class="workspace__header">
      <div>
        <p class="workspace__eyebrow">Focused workspace</p>
        <h1 class="workspace__title">{{ workspaceTitle }}</h1>
        <p class="workspace__sub">{{ section?.description }} {{ workspaceHint }}</p>
      </div>
      <NuxtLink to="/dashboard" class="btn btn-secondary btn-sm">Back to dashboard</NuxtLink>
    </div>

    <section class="workspace__section">
      <template v-if="resolvedSlug === 'command-center'">
        <div class="workspace__hero surface">
          <p class="workspace__hero-eyebrow">Current position</p>
          <h2 class="workspace__hero-amount">
            {{ demandDeficits.length ? `Up to ₦${Math.round(totalWeeklyDeficitRisk).toLocaleString()}/week potential demand gap` : 'We are analyzing your business' }}
          </h2>
          <p class="workspace__hero-copy">{{ commandCenterSummary }}</p>
        </div>

        <div class="workspace__grid workspace__grid--command">
          <PortfolioSummary
            :revenue-at-risk="revenueAtRisk"
            :products-at-risk="productsAtRisk"
            :avg-daily-risk="avgDailyRisk"
            :total-products="summary?.total_products"
            :confidence-score="portfolioConfidence"
            :eyebrow="portfolioEyebrow"
            :subtitle="portfolioSubtitle"
            :cta-label="portfolioCtaLabel"
            :mode="portfolioMode"
            @review="navigateTo('/workspace/decision-workbench')"
          />

          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Recommended next step</p>
            <h3 class="workspace__panel-title">Move from signal to action quickly.</h3>
            <p class="workspace__panel-copy">{{ heroItems.length ? nextActionCopy : sparseCommandCopy }}</p>
            <NextActionsList
              v-if="heroItems.length"
              :items="heroItems"
              @select="id => focusProductById(heroItems.find(item => item.id === id)?.product_id)"
            />
            <div v-else class="workspace__starter-list">
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="verifyStarterStock">
                <span class="workspace__starter-tag">Verify stock</span>
                <strong>{{ selectedProduct.name }}</strong>
                <span>Record a trusted shelf count to strengthen the next decision cycle.</span>
              </button>
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="recordStarterSale">
                <span class="workspace__starter-tag">Record sale</span>
                <strong>{{ selectedProduct.name }}</strong>
                <span>Capture one live sale so expected demand can start blending with your own pattern.</span>
              </button>
              <NuxtLink to="/onboarding" class="workspace__starter">
                <span class="workspace__starter-tag">Add product</span>
                <strong>Expand coverage</strong>
                <span>Add another product so SiloXR can compare demand and start ranking commercial pressure.</span>
              </NuxtLink>
            </div>
          </div>
        </div>

        <DecisionHero
          :decision="heroDecision"
          :items="heroItems"
          :context-product="selectedProduct"
          @focus-decision="id => focusProductById(heroItems.find(item => item.id === id)?.product_id)"
          @focus-product="focusProductById"
        />
      </template>

      <template v-else-if="resolvedSlug === 'decision-workbench'">
        <div class="workspace__hero surface">
          <p class="workspace__hero-eyebrow">Decision queue</p>
          <h2 class="workspace__hero-amount">
            {{ heroDecision ? `${topDecisions.length} active decision${topDecisions.length === 1 ? '' : 's'} in play` : 'Decision queue is still forming' }}
          </h2>
          <p class="workspace__hero-copy">{{ topDecisions.length ? riskReviewSentence : sparseDecisionSentence }}</p>
        </div>

        <DecisionHero
          :decision="heroDecision"
          :items="heroItems"
          :context-product="selectedProduct"
          @focus-decision="id => focusProductById(heroItems.find(item => item.id === id)?.product_id)"
          @focus-product="focusProductById"
        />

        <div class="workspace__grid workspace__grid--decisions">
          <div v-if="topDecisions.length" class="workspace__stack">
            <DecisionCard
              v-for="(decision, index) in topDecisions"
              :key="decision.id"
              :decision="decision"
              :index="index"
              @acted="reloadWorkspaceData"
              @ignored="reloadWorkspaceData"
            />
          </div>
          <div v-else class="empty-state surface">
            <div class="empty-state__icon">≈</div>
            <p class="empty-state__title">No active decisions yet.</p>
            <p class="empty-state__sub">{{ sparseDecisionSentence }}</p>
            <div class="workspace__empty-actions">
              <button v-if="selectedProduct" type="button" class="btn btn-primary btn-sm" @click="verifyStarterStock">
                Verify stock
              </button>
              <button v-if="selectedProduct" type="button" class="btn btn-secondary btn-sm" @click="recordStarterSale">
                Record sale
              </button>
              <NuxtLink to="/onboarding" class="btn btn-secondary btn-sm">Add product</NuxtLink>
            </div>
          </div>

          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Execution flow</p>
            <h3 class="workspace__panel-title">Handle the queue in order of value and urgency.</h3>
            <p class="workspace__panel-copy">
              {{ heroItems.length ? 'Review the top recommendation first, then clear the remaining decisions in priority order.' : 'Start with one trusted stock or sales event, then return here to review the first live decision queue.' }}
            </p>
            <NextActionsList
              v-if="heroItems.length"
              :items="heroItems"
              @select="id => focusProductById(heroItems.find(item => item.id === id)?.product_id)"
            />
            <div v-else class="workspace__starter-list">
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="verifyStarterStock">
                <span class="workspace__starter-tag">First move</span>
                <strong>Verify opening stock</strong>
                <span>That gives the engine a reliable inventory anchor before it ranks consequence.</span>
              </button>
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="recordStarterSale">
                <span class="workspace__starter-tag">Then</span>
                <strong>Record one sale</strong>
                <span>With one sale event, SiloXR can begin separating expected demand from observed demand.</span>
              </button>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="resolvedSlug === 'demand-intelligence'">
        <div class="workspace__hero surface">
          <p class="workspace__hero-eyebrow">Demand picture</p>
          <h2 class="workspace__hero-amount">
            {{ demandDeficits.length ? `${demandDeficits.length} demand gap${demandDeficits.length === 1 ? '' : 's'} are shaping the current opportunity` : 'Demand intelligence is still forming' }}
          </h2>
          <p class="workspace__hero-copy">{{ opportunitySentence }}</p>
        </div>

        <DemandTrendChart
          v-if="primaryDemandDeficit"
          :title="displayDeficitName(primaryDemandDeficit)"
          :expected-daily="primaryDemandDeficit.expected_daily_demand"
          :observed-daily="primaryDemandDeficit.observed_daily_demand"
          :cv-estimate="primaryDemandDeficit.cv_estimate"
          :show-baseline-label="Boolean(summary?.baseline_in_use)"
          :drift-mode="Boolean(summary?.stale_products_count)"
        />
        <div v-else class="empty-state surface">
          <div class="empty-state__icon">~</div>
          <p class="empty-state__title">Demand trend will appear here.</p>
          <p class="empty-state__sub">We need a baseline-supported demand gap before this view becomes useful.</p>
        </div>

        <div class="workspace__grid workspace__grid--demand">
          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Top demand gaps</p>
            <h3 class="workspace__panel-title">Where expected demand is outrunning what we currently observe.</h3>
            <div v-if="demandDeficits.length" class="workspace__demand-list">
              <div v-for="deficit in demandDeficits" :key="normalizedName(deficit.product_name)" class="workspace__demand-item">
                <div>
                  <p class="workspace__demand-name">{{ displayDeficitName(deficit) }}</p>
                  <p class="workspace__demand-sub">Expected {{ Math.round(Number(deficit.expected_daily_demand ?? 0) * 7) }}/week · observed {{ Math.round(Number(deficit.observed_daily_demand ?? 0) * 7) }}/week</p>
                </div>
                <p class="workspace__demand-risk">₦{{ Math.round(Number(deficit.revenue_risk_weekly ?? 0)).toLocaleString() }}/week</p>
              </div>
            </div>
            <p v-else class="workspace__panel-copy">Once demand gaps appear, SiloXR will rank them here by weekly impact.</p>
          </div>

          <div>
            <TopProductsChart v-if="topSellingProducts.length" :items="topSellingProducts" />
            <div v-else class="empty-state surface">
              <div class="empty-state__icon">+</div>
              <p class="empty-state__title">Top opportunities need more live demand signal.</p>
              <p class="empty-state__sub">As product patterns form, the strongest opportunities will rank here.</p>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="resolvedSlug === 'business-health'">
        <div class="workspace__hero surface workspace__hero--health">
          <p class="workspace__hero-eyebrow">Business intelligence layer</p>
          <h2 class="workspace__hero-amount">{{ businessHealthPrimaryTitle }}</h2>
          <p class="workspace__hero-copy">{{ businessHealthHeroCopy }}</p>
        </div>

        <div class="workspace__grid workspace__grid--health-metrics">
          <div class="workspace__metric-card surface">
            <p class="workspace__panel-eyebrow">Weekly revenue</p>
            <h3 class="workspace__metric-value">{{ formatCurrency(analyticsWeeklyRevenue) }}</h3>
            <p class="workspace__panel-copy">Observed weekly revenue generated from your live product movement and inferred demand.</p>
          </div>

          <div class="workspace__metric-card surface">
            <p class="workspace__panel-eyebrow">Revenue gap</p>
            <h3 class="workspace__metric-value workspace__metric-value--danger">{{ formatCurrency(analyticsGapWeekly) }}</h3>
            <p class="workspace__panel-copy">
              {{
                businessHealthGapCoverage != null
                  ? `Visible benchmark gaps equal about ${businessHealthGapCoverage}% of current weekly revenue.`
                  : "No material weekly revenue shortfall is currently visible against benchmark demand."
              }}
            </p>
          </div>

          <div class="workspace__metric-card surface">
            <p class="workspace__panel-eyebrow">Confidence</p>
            <h3 class="workspace__metric-value">{{ Math.round(analyticsConfidence * 100) }}%</h3>
            <p class="workspace__panel-copy">Weighted by commercial importance so higher-value lines influence the report proportionally.</p>
          </div>
        </div>

        <div class="workspace__grid workspace__grid--health">
          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Health pillars</p>
            <h3 class="workspace__panel-title">Three operating signals shaping overall business health right now.</h3>
            <div class="workspace__pillar-list">
              <div
                v-for="pillar in healthPillars"
                :key="pillar.title"
                class="workspace__pillar"
                :class="{
                  'workspace__pillar--danger': pillar.tone === 'danger',
                  'workspace__pillar--warning': pillar.tone === 'warning',
                  'workspace__pillar--safe': pillar.tone === 'safe',
                }"
              >
                <span class="workspace__pillar-title">{{ pillar.title }}</span>
                <strong class="workspace__pillar-value">{{ pillar.value }}</strong>
                <span class="workspace__pillar-copy">{{ pillar.label }}</span>
              </div>
            </div>
          </div>

          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Top revenue drivers</p>
            <h3 class="workspace__panel-title">Products currently carrying the largest weekly revenue contribution.</h3>
            <div v-if="businessHealthTopProducts.length" class="workspace__rank-list">
              <div
                v-for="(product, index) in businessHealthTopProducts"
                :key="`${product.name}-${index}`"
                class="workspace__rank-item"
              >
                <div class="workspace__rank-copy">
                  <span class="workspace__rank-badge">{{ index + 1 }}</span>
                  <div>
                    <p class="workspace__rank-title">{{ product.name }}</p>
                    <p class="workspace__rank-sub">Current weekly revenue contribution</p>
                  </div>
                </div>
                <strong class="workspace__rank-value">{{ formatCurrency(Number(product.estimated_weekly_revenue ?? 0)) }}</strong>
              </div>
            </div>
            <div v-else class="workspace__starter-list">
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="recordStarterSale">
                <span class="workspace__starter-tag">Capture revenue</span>
                <strong>Record a live sale</strong>
                <span>That immediately gives this dashboard a commercial signal to rank.</span>
              </button>
              <NuxtLink to="/onboarding" class="workspace__starter">
                <span class="workspace__starter-tag">Expand coverage</span>
                <strong>Add more tracked products</strong>
                <span>Business health gets stronger as more revenue lines are represented.</span>
              </NuxtLink>
            </div>
          </div>
        </div>

        <div class="workspace__grid workspace__grid--health">
          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Demand gap breakdown</p>
            <h3 class="workspace__panel-title">Where benchmark weekly demand is currently ahead of observed weekly sales.</h3>
            <div v-if="businessHealthDemandGaps.length" class="workspace__health-gap-list">
              <div
                v-for="gap in businessHealthDemandGaps"
                :key="gap.name"
                class="workspace__health-gap-item"
              >
                <div>
                  <p class="workspace__demand-name">{{ gap.name }}</p>
                  <p class="workspace__demand-sub">
                    Benchmark {{ Math.round(Number(gap.expected_weekly_demand ?? 0)) }}/week
                    - observed {{ Math.round(Number(gap.observed_weekly_demand ?? 0)) }}/week
                    - confidence {{ Math.round(Number(gap.confidence ?? 0) * 100) }}%
                  </p>
                </div>
                <div class="workspace__health-gap-metrics">
                  <strong>{{ formatCurrency(Number(gap.gap_revenue ?? 0)) }}/week</strong>
                  <span>{{ Math.round(Number(gap.gap_units ?? 0)) }} units below benchmark</span>
                </div>
              </div>
            </div>
            <div v-else class="workspace__starter-list">
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="verifyStarterStock">
                <span class="workspace__starter-tag">Strengthen signal</span>
                <strong>Verify stock for {{ selectedProduct.name }}</strong>
                <span>A fresh count makes the business health layer more reliable immediately.</span>
              </button>
              <button v-if="selectedProduct" type="button" class="workspace__starter" @click="recordStarterSale">
                <span class="workspace__starter-tag">Capture demand</span>
                <strong>Record a live sale</strong>
                <span>That gives the analytics layer a stronger observed demand base to compare against.</span>
              </button>
            </div>
          </div>

          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Report insights</p>
            <h3 class="workspace__panel-title">Descriptive operating takeaways translated into business language.</h3>
            <div class="workspace__insight-list">
              <div
                v-for="(insight, index) in businessHealthInsights"
                :key="`${index}-${insight}`"
                class="workspace__insight-item"
              >
                <span class="workspace__insight-index">{{ index + 1 }}</span>
                <p>{{ insight }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="workspace__grid workspace__grid--health">
          <div class="workspace__support surface workspace__support--investor">
            <p class="workspace__panel-eyebrow">Executive summary</p>
            <h3 class="workspace__panel-title">A descriptive narrative for monthly reports and partner views.</h3>
            <p class="workspace__investor-summary">{{ investorSummary }}</p>
            <div class="workspace__investor-tags">
              <span class="workspace__tag">Dashboard-ready</span>
              <span class="workspace__tag">PDF-ready</span>
              <span class="workspace__tag">Partner-ready</span>
            </div>
          </div>

          <div>
            <TopProductsChart
              v-if="productVelocityRows.filter(item => item.estimatedDailyUnits > 0).length"
              :items="productVelocityRows.filter(item => item.estimatedDailyUnits > 0).slice(0, 7).map(item => ({
                name: item.name,
                value: item.estimatedDailyUnits,
                subtitle: item.category || 'tracked line',
              }))"
            />
            <div v-else class="workspace__support surface">
              <p class="workspace__panel-eyebrow">Readiness</p>
              <h3 class="workspace__panel-title">The analytics layer is ready for more live operating input.</h3>
              <p class="workspace__panel-copy">Add products, verify stock, and record sales to unlock richer rankings, stronger investor narratives, and monthly report quality.</p>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="resolvedSlug === 'business-health' && false">
        <div class="workspace__hero surface workspace__hero--health">
          <p class="workspace__hero-eyebrow">Investor-ready report</p>
          <h2 class="workspace__hero-amount">{{ businessHealthPrimaryTitle }}</h2>
          <p class="workspace__hero-copy">{{ businessHealthHeroCopy }}</p>
        </div>

        <div class="workspace__grid workspace__grid--health-metrics">
          <div class="workspace__metric-card surface">
            <p class="workspace__panel-eyebrow">Weekly revenue</p>
            <h3 class="workspace__metric-value">{{ formatNaira(Number(businessHealthSummary?.estimated_weekly_revenue ?? 0)) }}</h3>
            <p class="workspace__panel-copy">Observed weekly revenue generated from current recorded demand.</p>
          </div>

          <div class="workspace__metric-card surface">
            <p class="workspace__panel-eyebrow">Revenue gap</p>
            <h3 class="workspace__metric-value workspace__metric-value--danger">{{ formatNaira(Number(businessHealthSummary?.potential_revenue_gap_weekly ?? 0)) }}</h3>
            <p class="workspace__panel-copy">
              {{
                businessHealthGapCoverage != null
                  ? `Closing visible gaps could add about ${businessHealthGapCoverage}% on top of current weekly revenue.`
                  : 'No material weekly revenue leakage is currently visible from unmet demand.'
              }}
            </p>
          </div>

          <div class="workspace__metric-card surface">
            <p class="workspace__panel-eyebrow">Confidence</p>
            <h3 class="workspace__metric-value">{{ Math.round(Number(businessHealthSummary?.confidence_score ?? 0) * 100) }}%</h3>
            <p class="workspace__panel-copy">Weighted by commercial importance so higher-value lines influence the report proportionally.</p>
          </div>
        </div>

        <div class="workspace__grid workspace__grid--health">
          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Top revenue drivers</p>
            <h3 class="workspace__panel-title">Products currently carrying the largest weekly revenue contribution.</h3>
            <div v-if="businessHealthTopProducts.length" class="workspace__rank-list">
              <div
                v-for="(product, index) in businessHealthTopProducts"
                :key="`${product.name}-${index}`"
                class="workspace__rank-item"
              >
                <div class="workspace__rank-copy">
                  <span class="workspace__rank-badge">{{ index + 1 }}</span>
                  <div>
                    <p class="workspace__rank-title">{{ product.name }}</p>
                    <p class="workspace__rank-sub">Estimated weekly revenue contribution</p>
                  </div>
                </div>
                <strong class="workspace__rank-value">{{ formatNaira(Number(product.estimated_weekly_revenue ?? 0)) }}</strong>
              </div>
            </div>
            <p v-else class="workspace__panel-copy">Top product ranking will appear here once live demand data is available.</p>
          </div>

          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Report insights</p>
            <h3 class="workspace__panel-title">Operational takeaways translated into business language.</h3>
            <div v-if="businessHealthInsights.length" class="workspace__insight-list">
              <div
                v-for="(insight, index) in businessHealthInsights"
                :key="`${index}-${insight}`"
                class="workspace__insight-item"
              >
                <span class="workspace__insight-index">{{ index + 1 }}</span>
                <p>{{ insight }}</p>
              </div>
            </div>
            <p v-else class="workspace__panel-copy">Insights will populate here as soon as the report has enough operating context.</p>
          </div>
        </div>

        <div class="workspace__grid workspace__grid--health">
          <div class="workspace__support surface">
            <p class="workspace__panel-eyebrow">Demand gap breakdown</p>
            <h3 class="workspace__panel-title">Where expected weekly demand is still ahead of observed demand.</h3>
            <div v-if="businessHealthDemandGaps.length" class="workspace__health-gap-list">
              <div
                v-for="gap in businessHealthDemandGaps"
                :key="gap.name"
                class="workspace__health-gap-item"
              >
                <div>
                  <p class="workspace__demand-name">{{ gap.name }}</p>
                  <p class="workspace__demand-sub">
                    Expected {{ Math.round(Number(gap.expected_weekly_demand ?? 0)) }}/week
                    · observed {{ Math.round(Number(gap.observed_weekly_demand ?? 0)) }}/week
                    · confidence {{ Math.round(Number(gap.confidence ?? 0) * 100) }}%
                  </p>
                </div>
                <div class="workspace__health-gap-metrics">
                  <strong>{{ formatNaira(Number(gap.gap_revenue ?? 0)) }}/week</strong>
                  <span>{{ Math.round(Number(gap.gap_units ?? 0)) }} units gap</span>
                </div>
              </div>
            </div>
            <p v-else class="workspace__panel-copy">No material demand gap is visible right now.</p>
          </div>

          <div class="workspace__support surface workspace__support--investor">
            <p class="workspace__panel-eyebrow">Investor summary</p>
            <h3 class="workspace__panel-title">A clean narrative that can feed monthly reports and partner views.</h3>
            <p class="workspace__investor-summary">{{ investorSummary || 'The business health narrative will appear here once operating data is sufficient.' }}</p>
            <div class="workspace__investor-tags">
              <span class="workspace__tag">Dashboard-ready</span>
              <span class="workspace__tag">PDF-ready</span>
              <span class="workspace__tag">Partner-ready</span>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="resolvedSlug === 'product-operations'">
        <div class="workspace__hero surface">
          <p class="workspace__hero-eyebrow">Product execution</p>
          <h2 class="workspace__hero-amount">
            {{ selectedProduct ? selectedProduct.name : 'Choose a product to begin' }}
          </h2>
          <p class="workspace__hero-copy">{{ productOpsSentence }}</p>
        </div>

        <div class="workspace__picker">
          <label class="workspace__picker-label">Product in focus</label>
          <select
            class="workspace__select"
            :value="selectedProduct?.id"
            @change="e => onSelectProduct(inventoryStore.products.find(p => p.id === (e.target as HTMLSelectElement).value))"
          >
            <option v-for="product in inventoryStore.byUrgency" :key="product.id" :value="product.id">
              {{ product.name }}
            </option>
          </select>
        </div>

        <div class="workspace__forecast-grid">
          <SalesForecastChart :burn-rate="inventoryStore.selected?.burn_rate" :recent-events="inventoryStore.selected?.recent_events" />

          <ForecastStrip
            v-if="forecastStrip.length"
            :strips="forecastStrip"
            :max-quantity="inventoryStore.selected?.estimated_quantity ?? 100"
            :current-quantity="inventoryStore.selected?.estimated_quantity"
            :recent-events="inventoryStore.selected?.recent_events"
          />
        <div v-else class="empty-state surface">
          <div class="empty-state__icon">→</div>
          <p class="empty-state__title">{{ selectedProduct ? 'Stock projection is waiting for one more inventory signal.' : 'We need one product in focus.' }}</p>
          <p class="empty-state__sub">
            {{
              selectedProduct
                ? `Record a stock count or restock for ${selectedProduct.name} and SiloXR will begin projecting stock levels here.`
                : 'Select a product above to unlock the stock projection and execution flow.'
            }}
          </p>
          <div v-if="selectedProduct" class="workspace__empty-actions">
            <button type="button" class="btn btn-primary btn-sm" @click="verifyStarterStock">Verify stock</button>
            <button type="button" class="btn btn-secondary btn-sm" @click="handleQuickRestock(selectedProduct)">Quick restock</button>
          </div>
        </div>
        </div>

        <ProductTable
          :products="inventoryStore.byUrgency"
          :loading="isLoading"
          @select="onSelectProduct"
          @record-event="openRecordEvent"
          @quick-sale="handleQuickSale"
          @quick-restock="handleQuickRestock"
          @sync-shelf="handleSyncShelf"
          @repeat-last-count="handleRepeatLastCount"
          @inline-update="handleInlineUpdate"
          @delete-product="handleDeleteProduct"
          @submit-inventory-entry="handleInventoryEntry"
        />
      </template>
    </section>
  </div>
</template>

<style scoped>
.workspace {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.workspace__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.workspace__eyebrow,
.workspace__panel-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.workspace__title {
  margin-top: 4px;
  font-size: clamp(28px, 3vw, 40px);
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: var(--text);
}
.workspace__sub {
  margin-top: 8px;
  max-width: 760px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-3);
}
.workspace__section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.workspace__hero {
  padding: 22px;
  border: 1px solid rgba(83, 74, 183, 0.12);
  background: linear-gradient(180deg, color-mix(in srgb, var(--purple) 7%, var(--bg-card)), color-mix(in srgb, var(--bg-card) 98%, transparent));
}
.workspace__hero--health {
  background:
    radial-gradient(circle at top right, rgba(24, 95, 165, 0.1), transparent 32%),
    linear-gradient(180deg, color-mix(in srgb, var(--purple) 8%, var(--bg-card)), color-mix(in srgb, var(--bg-card) 98%, transparent));
}
.workspace__hero-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.workspace__hero-amount {
  margin-top: 6px;
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1.12;
  letter-spacing: -0.03em;
  color: var(--text);
}
.workspace__hero-copy {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-2);
}
.workspace__grid {
  display: grid;
  gap: 16px;
}
.workspace__forecast-grid {
  display: grid;
  gap: 16px;
}
.workspace__grid--command,
.workspace__grid--decisions,
.workspace__grid--demand,
.workspace__grid--health {
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.95fr);
}
.workspace__grid--health-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.workspace__support {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.workspace__support--investor {
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-card) 96%, transparent), color-mix(in srgb, var(--bg-card) 90%, transparent)),
    radial-gradient(circle at top right, rgba(83, 74, 183, 0.08), transparent 42%);
}
.workspace__metric-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.workspace__metric-value {
  margin: 0;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.04em;
  color: var(--text);
}
.workspace__metric-value--danger {
  color: var(--danger, #b42318);
}
.workspace__pillar-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.workspace__pillar {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-raised) 88%, transparent);
}
.workspace__pillar--danger {
  border-color: color-mix(in srgb, var(--danger, #b42318) 24%, var(--border-subtle));
  background: color-mix(in srgb, var(--danger, #b42318) 8%, var(--bg-card));
}
.workspace__pillar--warning {
  border-color: color-mix(in srgb, #d98a00 24%, var(--border-subtle));
  background: color-mix(in srgb, #d98a00 8%, var(--bg-card));
}
.workspace__pillar--safe {
  border-color: color-mix(in srgb, var(--success, #1f8f6a) 22%, var(--border-subtle));
  background: color-mix(in srgb, var(--success, #1f8f6a) 8%, var(--bg-card));
}
.workspace__pillar-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.workspace__pillar-value {
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--text);
}
.workspace__pillar-copy {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-3);
}
.workspace__panel-title {
  font-size: 18px;
  line-height: 1.25;
  color: var(--text);
}
.workspace__panel-copy {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-3);
}
.workspace__stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.workspace__picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.workspace__picker-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-3);
}
.workspace__select {
  min-width: 240px;
  max-width: 360px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text);
}
.workspace__demand-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.workspace__demand-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--border-subtle);
}
.workspace__demand-item:first-child {
  padding-top: 0;
  border-top: 0;
}
.workspace__demand-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.workspace__demand-sub {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-3);
}
.workspace__demand-risk {
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
  color: var(--danger, #b42318);
}
.workspace__rank-list,
.workspace__insight-list,
.workspace__health-gap-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.workspace__rank-item,
.workspace__health-gap-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 0;
  border-top: 1px solid var(--border-subtle);
}
.workspace__rank-item:first-child,
.workspace__health-gap-item:first-child {
  padding-top: 0;
  border-top: 0;
}
.workspace__rank-copy {
  display: flex;
  align-items: center;
  gap: 12px;
}
.workspace__rank-badge,
.workspace__insight-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--purple) 14%, transparent);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
}
.workspace__rank-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.workspace__rank-sub {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-3);
}
.workspace__rank-value {
  white-space: nowrap;
  font-size: 16px;
  letter-spacing: -0.02em;
  color: var(--text);
}
.workspace__insight-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-raised) 86%, transparent);
}
.workspace__insight-item p {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-2);
}
.workspace__health-gap-metrics {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  text-align: right;
}
.workspace__health-gap-metrics strong {
  white-space: nowrap;
  font-size: 14px;
  color: var(--danger, #b42318);
}
.workspace__health-gap-metrics span {
  font-size: 12px;
  color: var(--text-3);
}
.workspace__investor-summary {
  margin: 2px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-2);
}
.workspace__investor-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}
.workspace__tag {
  display: inline-flex;
  align-items: center;
  padding: 7px 11px;
  border-radius: 999px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-soft) 92%, transparent);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}
.workspace__starter-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.workspace__starter {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--bg-raised);
  color: var(--text);
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.workspace__starter:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
  border-color: color-mix(in srgb, var(--purple) 18%, var(--border));
}
.workspace__starter-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.workspace__starter strong {
  font-size: 14px;
  color: var(--text);
}
.workspace__starter span:last-child {
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-3);
}
.workspace__empty-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 14px;
}
@media (max-width: 980px) {
  .workspace__grid--command,
  .workspace__grid--decisions,
  .workspace__grid--demand,
  .workspace__grid--health,
  .workspace__grid--health-metrics {
    grid-template-columns: 1fr;
  }
  .workspace__pillar-list {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .workspace__header {
    flex-direction: column;
    align-items: stretch;
  }
  .workspace__hero,
  .workspace__support {
    padding: 18px;
  }
  .workspace__demand-item {
    flex-direction: column;
  }
  .workspace__select {
    max-width: none;
    width: 100%;
  }
}
</style>
