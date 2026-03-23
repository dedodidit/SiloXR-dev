import { resolve } from "path"

export default defineNuxtConfig({
  compatibilityDate: "2024-11-01",
  future: {
    compatibilityVersion: 4,
  },
  devtools: { enabled: true },
  modules: [
    "@vueuse/nuxt",
  ],
  components: [
    { path: "~/components", pathPrefix: false },
  ],
  imports: {
    dirs: [
      "app/stores",
      "app/composables",
    ],
  },
  runtimeConfig: {
    public: {
      apiBase:
        process.env.NUXT_PUBLIC_API_BASE ??
        (process.env.NODE_ENV === "development"
          ? "http://127.0.0.1:8000/api/v1"
          : "https://siloxr-dev.onrender.com/api/v1"),
    },
  },
  app: {
    head: {
      title: "SiloXR",
      meta: [
        { name: "viewport",    content: "width=device-width, initial-scale=1" },
        { name: "description", content: "Business decision engine" },
      ],
    },
  },
  css: [resolve(__dirname, "assets/css/main.css")],
  vite: {
    optimizeDeps: {
      include: [
        "pinia",
        "@vue/devtools-core",
        "@vue/devtools-kit",
      ],
    },
  },
  ssr: false,
})
