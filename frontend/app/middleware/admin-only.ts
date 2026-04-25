export default defineNuxtRouteMiddleware(async () => {
  const token = useCookie("siloxr_token")
  if (!token.value) return navigateTo("/auth/login")

  const currentUser = useState<any | null>("current-user", () => null)
  const { $api } = useNuxtApp()

  if (!currentUser.value) {
    try {
      currentUser.value = await $api("/auth/me/")
    } catch {
      return navigateTo("/auth/login")
    }
  }

  if (!currentUser.value?.is_staff) {
    return navigateTo("/dashboard")
  }
})
