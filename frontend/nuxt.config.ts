import { resolve } from "path"

export default defineNuxtConfig({
  compatibilityDate: "2024-11-01",
  future: {
    compatibilityVersion: 4,
  },
  devtools: { enabled: true },
  modules: [
    "@vueuse/nuxt",
    "@vercel/analytics",
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
      siteUrl:
        process.env.NUXT_PUBLIC_SITE_URL ??
        "https://siloxr.com",
      apiBase:
        process.env.NUXT_PUBLIC_API_BASE ??
        (process.env.NODE_ENV === "development"
          ? "http://127.0.0.1:8000/api/v1"
          : "https://siloxr-dev.onrender.com/api/v1"),
    },
  },
  app: {
    head: {
      htmlAttrs: {
        lang: "en",
      },
      title: "SiloXR",
      titleTemplate: "%s",
      charset: "utf-8",
      meta: [
        { name: "viewport",    content: "width=device-width, initial-scale=1" },
        { name: "description", content: "SiloXR helps small businesses prevent stockouts, protect cash flow, and make better inventory decisions before revenue is lost." },
        { name: "format-detection", content: "telephone=no" },
        { name: "theme-color", content: "#534AB7" },
        { property: "og:site_name", content: "SiloXR" },
      ],
      link: [
        { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
        { rel: "alternate icon", href: "/favicon.ico" },
        { rel: "manifest", href: "/site.webmanifest" },
      ],
    },
  },
  nitro: {
    prerender: {
      routes: [
        "/",
        "/robots.txt",
        "/sitemap.xml",
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
  ssr: true,
})
