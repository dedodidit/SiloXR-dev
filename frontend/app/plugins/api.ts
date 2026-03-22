// frontend/app/plugins/api.ts

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const refreshUrl = `${config.public.apiBase.replace("/v1", "")}/token/refresh/`

  const api = $fetch.create({
    baseURL:     config.public.apiBase,
    credentials: "include",

    onRequest({ options }) {
      const token = useCookie("siloxr_token")
      if (token.value) {
        options.headers = {
          ...options.headers as Record<string, string>,
          Authorization: `Bearer ${token.value}`,
        }
      }
    },

    async onResponseError(ctx) {
      const { request, options, response } = ctx

      if (response.status === 401) {
        const accessToken  = useCookie("siloxr_token")
        const refreshToken = useCookie("siloxr_refresh")
        const retried = Boolean((options as Record<string, unknown>)._retried)

        if (!retried && refreshToken.value) {
          try {
            const data = await $fetch<{ access: string }>(refreshUrl, {
              method: "POST",
              body: { refresh: refreshToken.value },
            })

            accessToken.value = data.access

            return await $fetch(request, {
              ...options,
              headers: {
                ...(options.headers as Record<string, string> | undefined),
                Authorization: `Bearer ${data.access}`,
              },
              _retried: true,
            })
          } catch {
            refreshToken.value = null
          }
        }

        accessToken.value  = null
        refreshToken.value = null
        await navigateTo("/auth/login")
      }
    },
  })

  return { provide: { api } }
})
