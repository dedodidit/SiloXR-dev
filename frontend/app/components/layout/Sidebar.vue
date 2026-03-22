<!-- frontend/app/components/layout/Sidebar.vue -->
<script setup lang="ts">
const router = useRouter()
const route = useRoute()
const currentUser = useState<any | null>("current-user", () => null)

const props = defineProps<{
  currentSection?: string
}>()

const items = [
  {
    id: "home",
    label: "Home",
    icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
    tip: "Dashboard home",
    href: "/dashboard",
  },
  {
    id: "command-center",
    label: "Command center",
    icon: "M12 3l8 4v10l-8 4-8-4V7l8-4zm0 0v18m8-14H4",
    tip: "Orientation and money posture",
    href: "/workspace/command-center",
  },
  {
    id: "decision-workbench",
    label: "Decision workbench",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6m6 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0h6m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14",
    tip: "Queue and execution flow",
    href: "/workspace/decision-workbench",
  },
  {
    id: "demand-intelligence",
    label: "Demand intelligence",
    icon: "M3 17l5-5 4 4 8-8",
    tip: "Demand gaps and opportunities",
    href: "/workspace/demand-intelligence",
  },
  {
    id: "product-operations",
    label: "Product operations",
    icon: "M3 3v18h18M7 13l3-3 3 2 4-5",
    tip: "Product trend and stock actions",
    href: "/workspace/product-operations",
  },
  {
    id: "settings",
    label: "Settings",
    icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
    tip: "Profile and settings",
    href: "/profile",
  },
]

const visibleItems = computed(() => {
  const base = [...items]
  if (currentUser.value && !currentUser.value?.is_pro) {
    base.splice(base.length - 1, 0, {
      id: "billing",
      label: "Billing",
      icon: "M3 6.75A2.75 2.75 0 015.75 4h12.5A2.75 2.75 0 0121 6.75v10.5A2.75 2.75 0 0118.25 20H5.75A2.75 2.75 0 013 17.25V6.75zm3 2.25a.75.75 0 000 1.5h9a.75.75 0 000-1.5H6zm0 4a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5H6z",
      tip: "Upgrade subscription",
      href: "/billing/upgrade",
    })
  }
  return base
})

const active = ref(props.currentSection ?? "home")
const mobileOpen = ref(false)
const expanded = ref(true)

const navigate = async (item: typeof items[number]) => {
  active.value = item.id
  mobileOpen.value = false
  if (item.href) {
    await navigateTo(item.href)
  }
}

const logout = () => {
  useCookie("siloxr_token").value = null
  useCookie("siloxr_refresh").value = null
  router.push("/auth/login")
}

watchEffect(() => {
  const match = visibleItems.value.find((item) => item.href && route.path === item.href)
  active.value = match?.id ?? "home"
})
</script>

<template>
  <button class="sb-hamburger" aria-label="Menu" @click="mobileOpen = !mobileOpen">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path v-if="!mobileOpen" d="M4 6h16M4 12h16M4 18h16" />
      <path v-else d="M6 18L18 6M6 6l12 12" />
    </svg>
  </button>

  <div v-if="mobileOpen" class="sb-backdrop" @click="mobileOpen = false" />

  <nav
    class="sb"
    :class="{
      'sb--expanded': expanded,
      'sb--mobile-open': mobileOpen,
    }"
    aria-label="Main navigation"
  >
    <button
      class="sb__toggle"
      :title="expanded ? 'Collapse menu' : 'Expand menu'"
      @click="expanded = !expanded"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path :d="expanded ? 'M15 19l-7-7 7-7' : 'M9 5l7 7-7 7'" />
      </svg>
    </button>

    <ul class="sb__list" role="list">
      <li
        v-for="item in visibleItems"
        :key="item.id"
        class="sb__item"
        :class="{ 'sb__item--active': active === item.id }"
        :title="!expanded ? item.tip : undefined"
      >
        <button
          class="sb__btn"
          :aria-current="active === item.id ? 'page' : undefined"
          @click="navigate(item)"
        >
          <span class="sb__icon-wrap" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path :d="item.icon" />
            </svg>
          </span>
          <Transition name="sb-label">
            <span v-show="expanded" class="sb__label">{{ item.label }}</span>
          </Transition>
        </button>
      </li>
    </ul>

    <div class="sb__footer">
      <button class="sb__btn sb__signout" @click="logout">
        <span class="sb__icon-wrap" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
            <path d="M16 17l5-5-5-5" />
            <path d="M21 12H9" />
          </svg>
        </span>
        <Transition name="sb-label">
          <span v-show="expanded" class="sb__label">Sign out</span>
        </Transition>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.sb-hamburger {
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 70;
  display: none;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text);
  box-shadow: var(--shadow-sm);
}
.sb-backdrop {
  position: fixed;
  inset: 0;
  z-index: 58;
  background: rgba(0, 0, 0, 0.24);
}
.sb {
  position: sticky;
  top: 72px;
  width: 88px;
  height: calc(100vh - 92px);
  margin: 10px 0 10px 10px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 86%, transparent);
  backdrop-filter: blur(18px);
  border-radius: 20px;
  overflow: hidden;
  transition: width .22s ease, transform .22s ease;
}
.sb--expanded {
  width: 248px;
}
.sb__toggle {
  align-self: flex-end;
  margin: 10px 10px 0 0;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
}
.sb__list {
  list-style: none;
  padding: 10px 8px 8px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sb__footer {
  margin-top: auto;
  padding: 10px 8px 12px;
  border-top: 1px solid var(--border-subtle);
}
.sb__item {
  position: relative;
}
.sb__btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 0;
  border-radius: 14px;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  transition: background .18s ease, color .18s ease, transform .18s ease;
}
.sb__btn:hover {
  background: color-mix(in srgb, var(--bg-raised) 74%, transparent);
  color: var(--text);
}
.sb__item--active .sb__btn {
  background: color-mix(in srgb, var(--purple) 12%, transparent);
  color: var(--text);
}
.sb__item--active .sb__icon-wrap {
  color: var(--icon-accent);
}
.sb__icon-wrap {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg-sunken) 78%, transparent);
  color: var(--icon-accent);
  flex-shrink: 0;
}
.sb__label {
  font-size: 13px;
  font-weight: 600;
  color: inherit;
  text-align: left;
}
.sb__signout:hover {
  background: rgba(180, 35, 24, 0.08);
  color: #B42318;
}
.sb-label-enter-active,
.sb-label-leave-active {
  transition: opacity .16s ease, transform .16s ease;
}
.sb-label-enter-from,
.sb-label-leave-to {
  opacity: 0;
  transform: translateX(-4px);
}

:root[data-theme="dark"] .sb {
  background: color-mix(in srgb, var(--bg-raised) 88%, transparent);
  border-right-color: var(--border);
}
:root[data-theme="dark"] .sb__btn:hover {
  background: color-mix(in srgb, var(--bg-raised) 84%, white 16%);
}
:root[data-theme="dark"] .sb__footer {
  border-top-color: var(--border);
}
:root[data-theme="dark"] .sb__signout:hover {
  background: rgba(226, 181, 68, 0.12);
  color: var(--icon-accent);
}

@media (max-width: 980px) {
  .sb-hamburger {
    display: inline-flex;
  }
  .sb {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 60;
    height: 100vh;
    margin: 0;
    transform: translateX(-110%);
    border-radius: 0 20px 20px 0;
  }
  .sb--mobile-open {
    transform: translateX(0);
  }
}
</style>
