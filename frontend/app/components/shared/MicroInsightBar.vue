<script setup lang="ts">
const { $api } = useNuxtApp()

type InsightItem = {
  id: string
  text: string
  productId?: string
  productName?: string
  yesLabel?: string
  noLabel?: string
}

const messages = ref<InsightItem[]>([])
const current = ref(0)
const visible = ref(true)
const acted = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const fallbacks: InsightItem[] = [
  {
    id: "fallback-weekend",
    text: "We are learning your business. Based on similar stores, demand often lifts into the weekend.",
  },
  {
    id: "fallback-verification",
    text: "Confidence grows faster when you verify one shelf count instead of scanning every product.",
  },
  {
    id: "fallback-rhythm",
    text: "A quick stock update today makes tomorrow's decision stack more reliable.",
  },
]

const rotate = () => {
  if (messages.value.length < 2) return
  visible.value = false
  acted.value = false
  setTimeout(() => {
    current.value = (current.value + 1) % messages.value.length
    visible.value = true
  }, 260)
}

const active = computed(() => messages.value[current.value] ?? null)

const handlePrimary = async () => {
  if (!active.value) return
  acted.value = true
  if (active.value.productId) {
    await navigateTo(`/products/${active.value.productId}`)
    return
  }
  await navigateTo("/onboarding")
}

const handleDismiss = () => {
  acted.value = true
  rotate()
}

onMounted(async () => {
  try {
    const nudges = await $api<any[]>("/nudge/")
    const text = nudges
      .filter((item: any) => item?.question)
      .slice(0, 5)
      .map((item: any, index: number) => ({
        id: item.product_id ?? `nudge-${index}`,
        text: item.question,
        productId: item.product_id,
        productName: item.product_name,
        yesLabel: item.yes_label || "Review now",
        noLabel: item.no_label || "Later",
      }))
    messages.value = text.length ? text : fallbacks
  } catch {
    messages.value = fallbacks
  }

  if (messages.value.length > 1) {
    timer = setInterval(rotate, 9000)
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div v-if="active" class="mib surface">
    <div class="mib__header">
      <span class="mib__label">Micro insight</span>
      <button class="mib__skip" type="button" @click="handleDismiss">Next</button>
    </div>

    <Transition name="mib-copy" mode="out-in">
      <div :key="active.id" class="mib__body">
        <p class="mib__text">{{ active.text }}</p>
        <div class="mib__actions">
          <button class="mib__btn mib__btn--primary" type="button" @click="handlePrimary">
            {{ active.yesLabel || "Review now" }}
          </button>
          <button class="mib__btn" type="button" @click="handleDismiss">
            {{ active.noLabel || "Later" }}
          </button>
        </div>
        <p v-if="acted" class="mib__meta">The decision stack will keep adjusting as new data comes in.</p>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.mib {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--border-subtle);
  box-shadow: var(--shadow-xs);
}
.mib__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.mib__label {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-4);
}
.mib__skip {
  border: none;
  background: transparent;
  color: var(--purple);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.mib__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.mib__text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-2);
}
.mib__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.mib__btn {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-3);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
}
.mib__btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
.mib__btn--primary {
  background: var(--purple);
  color: #fff;
  border-color: var(--purple);
}
.mib__meta {
  font-size: 12px;
  color: var(--text-4);
}
.mib-copy-enter-active,
.mib-copy-leave-active { transition: opacity .25s ease, transform .25s ease; }
.mib-copy-enter-from,
.mib-copy-leave-to { opacity: 0; transform: translateY(4px); }
</style>
