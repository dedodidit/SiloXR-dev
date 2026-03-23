export interface WorkspaceSection {
  slug: string
  title: string
  description: string
  icon: string
  helper: string
}

export const workspaceSections: WorkspaceSection[] = [
  {
    slug: "command-center",
    title: "Command center",
    description: "Start with the money signal, the top recommendation, and the next moves.",
    helper: "Orientation, portfolio posture, primary decision, and next actions in one place.",
    icon: "M12 3l8 4v10l-8 4-8-4V7l8-4zm0 0v18m8-14H4",
  },
  {
    slug: "decision-workbench",
    title: "Decision workbench",
    description: "Work through the active decision queue with consequence and urgency together.",
    helper: "Primary decision, stack, and execution flow in one workspace.",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6m6 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0h6m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14",
  },
  {
    slug: "demand-intelligence",
    title: "Demand intelligence",
    description: "See how expected demand, observed demand, and top opportunities connect.",
    helper: "Demand gaps, trends, and opportunity ranking in one view.",
    icon: "M3 17l5-5 4 4 8-8",
  },
  {
    slug: "business-health",
    title: "Business health",
    description: "Turn operating data into a structured descriptive view of revenue, gaps, and business condition.",
    helper: "Executive summary, revenue picture, top products, and benchmark gaps in one report workspace.",
    icon: "M4 19h16M7 16l3-4 3 2 4-6 3 2",
  },
  {
    slug: "product-operations",
    title: "Product operations",
    description: "Manage product execution with forecast, stock actions, and product controls together.",
    helper: "Selected product focus, 7-day strip, and product table in one workspace.",
    icon: "M3 3v18h18M7 13l3-3 3 2 4-5",
  },
]

export const findWorkspaceSection = (slug: string) =>
  workspaceSections.find((section) => section.slug === slug) ?? null
