import type { BusinessHealthReport } from "~/types"

export const useBusinessHealth = () => {
  const { $api } = useNuxtApp()

  const fetchBusinessHealthReport = () =>
    $api<BusinessHealthReport>("/business-health/summary/")

  return {
    fetchBusinessHealthReport,
  }
}
