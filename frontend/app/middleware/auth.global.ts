// frontend/app/middleware/auth.global.ts

export default defineNuxtRouteMiddleware((to) => {
  const token = useCookie("siloxr_token")
  const isPublic =
    to.path === "/"
    || to.path.startsWith("/landing")
    || to.path.startsWith("/legal/")
    || to.path.startsWith("/auth/")

  if (to.path === "/" && token.value) {
    return navigateTo("/dashboard")
  }

  if (isPublic) return
  if (!token.value) return navigateTo("/auth/login")
})
