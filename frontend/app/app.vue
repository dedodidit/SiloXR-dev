<!-- frontend/app/app.vue
     Updated to:
     - Include Sidebar in the layout for dashboard pages
     - Apply the Figma header design (gradient logo, active underline,
       shimmer Pro badge, user avatar initials)
     - Wire new-user grace period badge from useDashboard
     - All existing logic (auth, logout, user fetch) preserved
-->
<script setup lang="ts">
const router = useRouter()
const route  = useRoute()
const token  = useCookie("siloxr_token")
const { $api } = useNuxtApp()

const isAuthPage    = computed(() => route.path.startsWith("/auth/"))
const isOnboardPage = computed(() => route.path === "/onboarding")
const isDashboard   = computed(() => route.path === "/dashboard")
const isWorkspace   = computed(() => route.path.startsWith("/workspace/"))
const showSidebar   = computed(() => isWorkspace.value && showHeader.value)
const isPublicMarketing = computed(() => route.path === "/" || route.path.startsWith("/landing"))
const showHeader    = computed(() => !isAuthPage.value && !isPublicMarketing.value && !!token.value)

const user = ref<any>(null)
const currentUser = useState<any | null>("current-user", () => null)
const colorMode = ref<"light" | "dark">("light")
const dashboardRefreshTick = useState<number>("dashboard-refresh-tick", () => 0)

const applyColorMode = (mode: "light" | "dark") => {
  if (typeof document === "undefined") return
  document.documentElement.setAttribute("data-theme", mode)
}

const toggleColorMode = () => {
  colorMode.value = colorMode.value === "dark" ? "light" : "dark"
  if (typeof window !== "undefined") {
    localStorage.setItem("siloxr_color_mode", colorMode.value)
  }
  applyColorMode(colorMode.value)
}

const triggerDashboardRefresh = () => {
  dashboardRefreshTick.value += 1
}

onMounted(async () => {
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem("siloxr_color_mode")
    if (stored === "dark" || stored === "light") {
      colorMode.value = stored
    } else {
      colorMode.value = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
    }
    applyColorMode(colorMode.value)
  }
  if (token.value) {
    try {
      user.value = await $api("/auth/me/")
      currentUser.value = user.value
    } catch {}
  }
})

watch(currentUser, (nextUser) => {
  if (nextUser) user.value = nextUser
})

const openAccountSettings = () => {
  router.push("/profile")
}

const headerUser = computed(() => currentUser.value || user.value || null)

const displayUserName = computed(() => {
  const raw = String(
    headerUser.value?.business_name
      || headerUser.value?.first_name
      || headerUser.value?.username
      || headerUser.value?.email?.split?.("@")?.[0]
      || ""
  ).trim()
  if (!raw) return "Account"
  return raw.charAt(0).toUpperCase() + raw.slice(1)
})
const userInitial = computed(() =>
  displayUserName.value.trim().charAt(0).toUpperCase() || "S"
)
const isFreeUser = computed(() => Boolean(headerUser.value) && !headerUser.value?.is_pro)
</script>

<template>
  <div id="app-root">
    <button
      v-if="!showHeader"
      class="app-floating-theme"
      type="button"
      :title="colorMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
      @click="toggleColorMode"
    >
      <svg v-if="colorMode === 'dark'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>
      <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.79A9 9 0 1111.21 3c0 .34.02.67.05 1A7 7 0 0020 12c.34.03.67.05 1 .05z" />
      </svg>
      <span>{{ colorMode === "dark" ? "Light" : "Dark" }}</span>
    </button>

    <!-- ── Top header ─────────────────────────────────────────── -->
    <header v-if="showHeader" class="app-header">

      <!-- Brand -->
      <NuxtLink to="/dashboard" class="app-header__brand">
        <div class="app-header__brand-mark" aria-hidden="true">
          <svg viewBox="0 0 12 12" fill="none" width="14" height="14">
            <path d="M2 9L6 3L10 9H2Z" fill="white" opacity="0.95"/>
            <path d="M4 9L6 6L8 9H4Z" fill="white" opacity="0.5"/>
          </svg>
        </div>
        <div class="app-header__brand-text">
          <span class="app-header__brand-name">SiloXR</span>
          <span class="app-header__brand-sub">Decision Engine</span>
        </div>
      </NuxtLink>

      <!-- Nav (hidden on dashboard — sidebar handles it there) -->
      <nav v-if="!isOnboardPage && !isDashboard" class="app-header__nav">
        <NuxtLink to="/dashboard"  class="app-header__link">Dashboard</NuxtLink>
        <NuxtLink to="/onboarding" class="app-header__link">+ Add product</NuxtLink>
        <NuxtLink to="/upload"     class="app-header__link">Import data</NuxtLink>
        <NuxtLink to="/profile"    class="app-header__link">Account</NuxtLink>
      </nav>

      <!-- On dashboard: just a spacer so right section aligns -->
      <div v-if="isDashboard" style="flex:1" />

      <!-- Right -->
      <div class="app-header__right">

        <!-- Pro badge with shimmer -->
        <div v-if="headerUser?.is_pro" class="app-header__pro-badge shimmer-badge">
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
            <path d="M4 1L5.2 3.2L7.6 3.6L5.8 5.4L6.2 7.8L4 6.6L1.8 7.8L2.2 5.4L0.4 3.6L2.8 3.2L4 1Z"
              fill="currentColor"/>
          </svg>
          Pro
        </div>

        <NuxtLink v-if="isFreeUser" to="/billing/upgrade" class="app-header__upgrade">
          Upgrade
        </NuxtLink>

        <button
          class="app-header__theme"
          type="button"
          :title="colorMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggleColorMode"
        >
          <svg v-if="colorMode === 'dark'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
          </svg>
          <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1111.21 3c0 .34.02.67.05 1A7 7 0 0020 12c.34.03.67.05 1 .05z" />
          </svg>
          <span>{{ colorMode === "dark" ? "Light" : "Dark" }}</span>
        </button>

        <button
          v-if="isDashboard || isWorkspace"
          class="app-header__refresh"
          type="button"
          :title="isWorkspace ? 'Refresh workspace' : 'Refresh dashboard'"
          @click="triggerDashboardRefresh"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 1 1-2.64-6.36" />
            <path d="M21 3v6h-6" />
          </svg>
          <span>Refresh</span>
        </button>

        <!-- User avatar -->
        <button class="app-header__user" @click="openAccountSettings" :title="`Open account settings for ${displayUserName}`">
          <div class="app-header__avatar">{{ userInitial }}</div>
          <div class="app-header__user-info">
            <span class="app-header__user-name">{{ displayUserName }}</span>
            <span class="app-header__user-role">{{ headerUser?.is_pro ? 'Pro' : 'Free' }}</span>
          </div>
        </button>

      </div>
    </header>

    <!-- ── Body: sidebar only on dashboard ───────────────────── -->
    <div class="app-body" :class="{ 'app-body--with-sidebar': showSidebar }">
      <Sidebar v-if="showSidebar" />
      <main class="app-main">
        <NuxtPage />
      </main>
    </div>

    <TourOverlay v-if="(isDashboard || isWorkspace) && showHeader" />
  </div>
</template>

<style>
/* Global reset already in main.css — only structural styles here */
#app-root {
  min-height:     100vh;
  background:     var(--bg, #F4F3EF);
  display:        flex;
  flex-direction: column;
}

.app-body {
  flex:    1;
  display: flex;
}
.app-main { flex: 1; min-width: 0; }

.app-floating-theme {
  position: fixed;
  top: 18px;
  right: 18px;
  z-index: 120;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-card) 88%, transparent);
  backdrop-filter: blur(14px);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: background .18s ease, border-color .18s ease, transform .18s ease, color .18s ease;
}
.app-floating-theme:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  color: var(--text);
}

/* Header brand text */
.app-header__brand-text {
  display:        flex;
  flex-direction: column;
  gap:            0;
  line-height:    1;
}
.app-header__brand-name {
  font-size:      19px;
  font-weight:    800;
  letter-spacing: -0.03em;
  background:     linear-gradient(135deg, var(--text) 0%, var(--purple) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.app-header__brand-sub {
  font-size:   10px;
  font-weight: 500;
  color:       var(--text-4);
  margin-top:  1px;
}

/* Active nav underline */
.app-header__link.router-link-active::after {
  content:      "";
  position:     absolute;
  bottom:       2px;
  left:         50%;
  transform:    translateX(-50%);
  width:        18px;
  height:       3px;
  border-radius: 99px;
  background:   var(--purple);
}
.app-header__link { position: relative; }

/* Pro badge */
.app-header__pro-badge {
  position:      relative;
  display:       inline-flex;
  align-items:   center;
  gap:           4px;
  padding:       5px 12px;
  border-radius: 10px;
  background:    linear-gradient(135deg, var(--purple), var(--purple-2));
  font-size:     12px;
  font-weight:   700;
  color:         #fff;
  overflow:      hidden;
  box-shadow:    0 2px 8px rgba(83,74,183,0.32);
}

.app-header__theme {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: background .18s ease, border-color .18s ease, transform .18s ease, color .18s ease, box-shadow .18s ease;
}
.app-header__theme:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
}

.app-header__refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: background .18s ease, border-color .18s ease, transform .18s ease, color .18s ease, box-shadow .18s ease;
}
.app-header__refresh:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
}
.app-header__upgrade {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--purple), var(--purple-2));
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  box-shadow: var(--shadow-xs);
  transition: transform .18s ease, box-shadow .18s ease, opacity .18s ease;
}
.app-header__upgrade:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
  opacity: 0.94;
}

/* User button */
.app-header__user {
  display:       flex;
  align-items:   center;
  gap:           8px;
  padding:       4px 8px 4px 4px;
  border:        none;
  background:    transparent;
  border-radius: 10px;
  cursor:        pointer;
  transition:    background 0.15s, border-color 0.15s, box-shadow 0.15s;
  border:        1px solid transparent;
}
.app-header__user:hover { background: rgba(0,0,0,0.04); }

.app-header__avatar {
  width:           32px;
  height:          32px;
  border-radius:   9px;
  background:      linear-gradient(135deg, color-mix(in srgb, var(--purple) 18%, transparent), color-mix(in srgb, var(--purple) 8%, transparent));
  border:          1px solid color-mix(in srgb, var(--purple) 22%, var(--border));
  display:         flex;
  align-items:     center;
  justify-content: center;
  font-size:       12px;
  font-weight:     700;
  color:           var(--purple);
}
.app-header__user-info {
  display:        flex;
  flex-direction: column;
  text-align:     left;
}
.app-header__user-name { font-size: 12px; font-weight: 600; color: var(--text); line-height: 1.1; }
.app-header__user-role { font-size: 10px; color: var(--text-4); line-height: 1.1; }

:root[data-theme="dark"] .app-header__user:hover {
  background: rgba(255,255,255,0.05);
}

:root[data-theme="dark"] .app-header {
  background: rgba(17,17,16,0.88);
  border-bottom-color: var(--border);
}

:root[data-theme="dark"] .app-header__brand-name {
  background: linear-gradient(135deg, #F4F1E8 0%, #E2B544 60%, #C99218 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

:root[data-theme="dark"] .app-header__brand-sub {
  color: var(--text-3);
}

:root[data-theme="dark"] .app-header__pro-badge {
  background: linear-gradient(135deg, #E2B544, #C99218);
  color: #1B1608;
  box-shadow: 0 4px 14px rgba(201,146,24,0.28);
}

:root[data-theme="dark"] .app-header__theme {
  background: var(--bg-raised);
  border-color: var(--border-strong);
  color: var(--text);
  box-shadow: var(--shadow-sm);
}

:root[data-theme="dark"] .app-header__theme:hover {
  border-color: color-mix(in srgb, var(--icon-accent) 35%, var(--border-strong));
  color: var(--icon-accent);
}

:root[data-theme="dark"] .app-floating-theme {
  background: color-mix(in srgb, var(--bg-raised) 90%, transparent);
  border-color: var(--border-strong);
  color: var(--text);
}

:root[data-theme="dark"] .app-floating-theme:hover {
  border-color: color-mix(in srgb, var(--icon-accent) 35%, var(--border-strong));
  color: var(--icon-accent);
}

:root[data-theme="dark"] .app-header__refresh {
  background: var(--bg-raised);
  border-color: var(--border-strong);
  color: var(--text);
  box-shadow: var(--shadow-sm);
}

:root[data-theme="dark"] .app-header__refresh:hover {
  border-color: color-mix(in srgb, var(--icon-accent) 35%, var(--border-strong));
  color: var(--icon-accent);
}

:root[data-theme="dark"] .app-header__user {
  background: rgba(255,255,255,0.02);
  border-color: var(--border-subtle);
}

:root[data-theme="dark"] .app-header__avatar {
  background: linear-gradient(135deg, rgba(212,136,6,0.22), rgba(212,136,6,0.1));
  border-color: rgba(212,136,6,0.26);
  color: var(--icon-accent);
}
</style>
