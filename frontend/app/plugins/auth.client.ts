// frontend/app/plugins/auth.client.ts

/**
 * Silent JWT refresh plugin.
 * Automatically refreshes the access token before it expires.
 * Runs on app mount and on window focus.
 * If refresh fails, clears tokens and redirects to login.
 */

export default defineNuxtPlugin(async () => {
  const refreshToken = useCookie("siloxr_refresh")
  const accessToken  = useCookie("siloxr_token")
  const config       = useRuntimeConfig()
  let refreshInterval: ReturnType<typeof setInterval> | null = null

  const clearSession = async () => {
    accessToken.value  = null
    refreshToken.value = null
    await navigateTo("/auth/login")
  }

  const tryRefresh = async (): Promise<boolean> => {
    if (!refreshToken.value) return false
    try {
      const data = await $fetch<{ access: string }>(
        `${config.public.apiBase.replace("/v1", "")}/token/refresh/`,
        { method: "POST", body: { refresh: refreshToken.value } }
      )
      accessToken.value = data.access
      // Sync to IDB for service worker
      if ((window as any).__siloxr_idb_set) {
        await (window as any).__siloxr_idb_set("access_token", data.access)
      }
      return true
    } catch {
      await clearSession()
      return false
    }
  }

  // Refresh on focus (user returns to tab)
  window.addEventListener("focus", () => {
    if (refreshToken.value) void tryRefresh()
  })

  // Schedule refresh every 14 minutes (access token = 15min in prod)
  const schedule = () => {
    if (refreshInterval) clearInterval(refreshInterval)
    refreshInterval = setInterval(async () => {
      if (refreshToken.value) await tryRefresh()
    }, 14 * 60 * 1000)
  }

  if (refreshToken.value && !accessToken.value) {
    await tryRefresh()
  }

  schedule()
})
