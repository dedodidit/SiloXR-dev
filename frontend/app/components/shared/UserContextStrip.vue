<!-- frontend/app/components/shared/UserContextStrip.vue -->

<script setup lang="ts">
const { $api }  = useNuxtApp()
const user      = ref<any>(null)
const coverage  = ref<any>(null)

onMounted(async () => {
  try {
    [user.value, coverage.value] = await Promise.all([
      $api("/auth/me/"),
      $api("/coverage/"),
    ])
  } catch {}
})

const businessLabel = computed(() => {
  const map: Record<string, string> = {
    retail:      "Retail",
    wholesale:   "Wholesale",
    pharmacy:    "Pharmacy",
    food:        "Food & Beverage",
    hardware:    "Hardware",
    supermarket: "Supermarket",
  }
  return map[user.value?.business_type ?? ""] ?? user.value?.business_type ?? "Business"
})

const timeOfDay = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
})

const displayName = computed(() =>
  user.value?.business_name || user.value?.first_name || user.value?.username || "Business"
)

const avatarLetter = computed(() =>
  String(displayName.value).trim().charAt(0).toUpperCase() || "S"
)

const isEnterprise = computed(() => String(user.value?.tier || "").toLowerCase() === "enterprise")
const isPaidPlan = computed(() => ["core", "pro", "enterprise"].includes(String(user.value?.tier || "").toLowerCase()))
</script>

<template>
  <div v-if="user" class="ucs surface">
    <div class="ucs__left">
      <!-- Avatar placeholder -->
      <div class="ucs__avatar" aria-hidden="true">
        {{ avatarLetter }}
      </div>
      <div class="ucs__info">
        <p class="ucs__greeting">{{ timeOfDay }}, {{ displayName }}</p>
        <p class="ucs__meta">
          {{ businessLabel }}
          <span class="ucs__sep">·</span>
          <span
            class="ucs__tier"
            :style="{
              background: isPaidPlan ? 'var(--purple-bg, #EEEDFE)' : 'var(--border-subtle, #EDECEA)',
              color:       isPaidPlan ? 'var(--purple, #534AB7)' : 'var(--text-3, #7A7870)',
            }"
          >
            {{ user.tier?.toUpperCase() ?? "FREE" }}
          </span>
        </p>
      </div>
    </div>

    <!-- Right: coverage status + upgrade CTA -->
    <div class="ucs__right">
      <span
        v-if="coverage?.is_limited"
        class="ucs__coverage t-hint"
      >
        Monitoring {{ coverage.visible }} of {{ coverage.total }} products
      </span>
      <NuxtLink
        v-if="!isEnterprise"
        to="/billing/upgrade"
        class="ucs__upgrade"
      >
        View plans
      </NuxtLink>
    </div>
  </div>
</template>

<style scoped>
.ucs {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  gap:             16px;
  padding:         14px 18px;
  flex-wrap:       wrap;
}
.ucs__left { display: flex; align-items: center; gap: 12px; }

.ucs__avatar {
  width:           36px;
  height:          36px;
  border-radius:   50%;
  background:      var(--purple-bg, #EEEDFE);
  color:           var(--purple, #534AB7);
  display:         flex;
  align-items:     center;
  justify-content: center;
  font-size:       15px;
  font-weight:     700;
  flex-shrink:     0;
}

.ucs__info     { display: flex; flex-direction: column; gap: 2px; }
.ucs__greeting { font-size: 14px; font-weight: 600; color: var(--text, #141412); }
.ucs__meta {
  font-size:   12px;
  color:       var(--text-3, #7A7870);
  display:     flex;
  align-items: center;
  gap:         6px;
}
.ucs__sep  { color: var(--text-4, #A8A69E); }
.ucs__tier {
  font-size:      10px;
  font-weight:    700;
  letter-spacing: .06em;
  padding:        2px 7px;
  border-radius:  99px;
}

.ucs__right {
  display:     flex;
  align-items: center;
  gap:         12px;
  flex-wrap:   wrap;
}
.ucs__coverage { white-space: nowrap; }
.ucs__upgrade {
  font-size:     12px;
  font-weight:   600;
  padding:       6px 14px;
  border-radius: var(--r-sm, 6px);
  background:    var(--purple, #534AB7);
  color:         #fff;
  text-decoration: none;
  transition:    opacity 0.15s;
  white-space:   nowrap;
}
.ucs__upgrade:hover { opacity: .88; }
</style>
