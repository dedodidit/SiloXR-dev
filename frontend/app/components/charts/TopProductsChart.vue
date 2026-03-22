<script setup lang="ts">
const props = defineProps<{
  items: Array<{
    name: string
    value: number
    subtitle?: string | null
  }>
}>()

const canvas = ref<HTMLCanvasElement | null>(null)
let chart: any = null

const maxValue = computed(() =>
  props.items.length ? Math.max(...props.items.map(item => item.value)) : 0
)

const { chartReady, onCanvas, rebuild } = useChartLoader(() => buildChart(), 220)

const buildChart = () => {
  if (!canvas.value || !props.items.length) return
  const Chart = (window as any).Chart
  if (!Chart) return

  if (chart) {
    chart.destroy()
    chart = null
  }

  chart = new Chart(canvas.value, {
    type: "bar",
    data: {
      labels: props.items.map(item => item.name),
      datasets: [
        {
          label: "Estimated units/day",
          data: props.items.map(item => Number(item.value.toFixed(2))),
          backgroundColor: props.items.map((_, index) =>
            index === 0
              ? "rgba(255, 77, 79, 0.88)"
              : index < 3
              ? "rgba(83, 74, 183, 0.82)"
              : "rgba(239, 159, 39, 0.78)"
          ),
          borderRadius: 10,
          borderSkipped: false,
          maxBarThickness: 22,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 520, easing: "easeOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#FFFFFF",
          borderColor: "#E5E3DB",
          borderWidth: 1,
          titleColor: "#141412",
          bodyColor: "#4A4945",
          padding: 12,
          cornerRadius: 10,
          callbacks: {
            label: (ctx: any) => ` Estimated velocity: ${ctx.parsed.x.toFixed(2)} units/day`,
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          suggestedMax: maxValue.value > 0 ? maxValue.value * 1.15 : 10,
          grid: { color: "rgba(20,20,18,0.05)", drawBorder: false },
          ticks: {
            color: "#8E8C84",
            font: { size: 11 },
          },
          border: { display: false },
        },
        y: {
          grid: { display: false, drawBorder: false },
          ticks: {
            color: "#2A2926",
            font: { size: 12, weight: "600" },
          },
          border: { display: false },
        },
      },
    },
  })
}

watch(
  () => props.items,
  () => rebuild(),
  { deep: true }
)

onUnmounted(() => {
  if (chart) chart.destroy()
})
</script>

<template>
  <div class="tph surface">
    <div class="tph__header">
      <div>
        <p class="tph__title">Top 7 selling products</p>
        <p class="tph__sub">Estimated from the current burn pattern across tracked products</p>
      </div>
      <span class="tph__badge">Live ranking</span>
    </div>

    <div class="tph__body">
      <div v-if="!chartReady" class="skeleton skeleton--chart tph__skeleton" />
      <canvas
        v-show="chartReady"
        :ref="(el: any) => { onCanvas(el); canvas = el }"
        class="tph__canvas"
      />
    </div>

    <div class="tph__list">
      <div v-for="item in items" :key="item.name" class="tph__row">
        <div>
          <p class="tph__name">{{ item.name }}</p>
          <p v-if="item.subtitle" class="tph__meta">{{ item.subtitle }}</p>
        </div>
        <strong class="tph__value">{{ item.value.toFixed(1) }}/day</strong>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tph {
  padding: 18px 18px 14px;
  box-shadow: var(--shadow-md);
}
.tph__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.tph__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.tph__sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-4);
}
.tph__badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(83, 74, 183, 0.08);
  color: #534AB7;
  font-size: 11px;
  font-weight: 700;
}
.tph__body {
  position: relative;
  height: 260px;
}
.tph__canvas,
.tph__skeleton {
  width: 100%;
  height: 100%;
}
.tph__list {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}
.tph__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid rgba(20, 20, 18, 0.06);
}
.tph__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.tph__meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-4);
}
.tph__value {
  font-size: 13px;
  color: #141412;
}
</style>
