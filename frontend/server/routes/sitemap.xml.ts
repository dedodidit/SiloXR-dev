export default defineEventHandler((event) => {
  const { public: { siteUrl = "https://siloxr.com" } } = useRuntimeConfig(event)
  const base = String(siteUrl).replace(/\/+$/, "")
  const today = new Date().toISOString()

  const urls = [
    {
      loc: `${base}/`,
      lastmod: today,
      changefreq: "weekly",
      priority: "1.0",
    },
  ]

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((url) => `  <url>
    <loc>${url.loc}</loc>
    <lastmod>${url.lastmod}</lastmod>
    <changefreq>${url.changefreq}</changefreq>
    <priority>${url.priority}</priority>
  </url>`).join("\n")}
</urlset>`

  setHeader(event, "content-type", "application/xml; charset=UTF-8")
  return xml
})
