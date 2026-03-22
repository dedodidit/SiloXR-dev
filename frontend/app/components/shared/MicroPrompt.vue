<!-- frontend/app/components/shared/MicroPrompt.vue -->

<script setup lang="ts">
const props = defineProps<{
  product: any
  visible: boolean
}>()

const emit = defineEmits<{
  confirm: [action: string]
  dismiss: []
}>()

const { recordEvent } = useOfflineQueue()

const promptType = computed(() => {
  if (props.product?.needs_verification)                return 'verify'
  if (props.product?.demand_direction === 'increasing') return 'demand_up'
  if (props.product?.demand_direction === 'decreasing') return 'demand_down'
  return 'general'
})

const prompts = computed(() => ({
  verify: {
    question: `Have you counted ${props.product?.name} recently?`,
    yes:  'Yes, enter count',
    no:   'Not yet',
    icon: '?',
  },
  demand_up: {
    question: `Sales of ${props.product?.name} seem to be picking up. Did you notice this?`,
    yes:  'Yes, ordering more',
    no:   'Not sure',
    icon: '↑',
  },
  demand_down: {
    question: `${props.product?.name} seems slower than usual. Is this expected?`,
    yes:  'Yes, seasonal',
    no:   'Unexpected',
    icon: '↓',
  },
  general: {
    question: `Any recent sales of ${props.product?.name} to record?`,
    yes:  'Record a sale',
    no:   'No change',
    icon: '·',
  },
}[promptType.value]))

const showCountInput = ref(false)
const countValue     = ref(0)
const saving         = ref(false)

const handleYes = async () => {
  if (promptType.value === 'verify') { showCountInput.value = true; return }
  emit('confirm', promptType.value === 'general' ? 'record_sale' : promptType.value)
}

const submitCount = async () => {
  if (countValue.value <= 0) return
  saving.value = true
  try {
    await recordEvent(props.product.id, {
      event_type:        'STOCK_COUNT',
      quantity:          0,
      verified_quantity: countValue.value,
      occurred_at:       new Date().toISOString(),
      notes:             'Quick count via micro-prompt',
    })
    emit('confirm', 'stock_counted')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Transition name="micro">
    <div v-if="visible" class="micro-prompt">
      <div class="micro-prompt__icon">{{ prompts?.icon }}</div>

      <div class="micro-prompt__body">
        <p class="micro-prompt__question">{{ prompts?.question }}</p>

        <div v-if="showCountInput" class="micro-prompt__count">
          <input
            v-model.number="countValue"
            type="number"
            min="0"
            class="micro-prompt__input"
            placeholder="Enter count"
            autofocus
          />
          <button
            class="micro-prompt__btn micro-prompt__btn--yes"
            :disabled="saving || countValue <= 0"
            @click="submitCount"
          >
            {{ saving ? 'Saving…' : 'Confirm' }}
          </button>
        </div>

        <div v-else class="micro-prompt__actions">
          <button class="micro-prompt__btn micro-prompt__btn--yes" @click="handleYes">
            {{ prompts?.yes }}
          </button>
          <button class="micro-prompt__btn micro-prompt__btn--no" @click="emit('dismiss')">
            {{ prompts?.no }}
          </button>
        </div>
      </div>

      <button class="micro-prompt__close" @click="emit('dismiss')">×</button>
    </div>
  </Transition>
</template>

<style scoped>
.micro-prompt {
  display:       flex;
  align-items:   flex-start;
  gap:           12px;
  padding:       14px 16px;
  background:    var(--surface, #fff);
  border:        1px solid var(--border, #e0e0e0);
  border-left:   3px solid var(--purple, #534AB7);
  border-radius: var(--r-md, 10px);
  box-shadow:    var(--shadow-md, 0 4px 16px rgba(0,0,0,.08));
  position:      relative;
  max-width:     420px;
}
.micro-prompt__icon {
  width:           28px;
  height:          28px;
  border-radius:   50%;
  background:      var(--purple-bg, #EEEDFE);
  color:           var(--purple, #534AB7);
  display:         flex;
  align-items:     center;
  justify-content: center;
  font-weight:     700;
  font-size:       14px;
  flex-shrink:     0;
}
.micro-prompt__body     { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.micro-prompt__question { font-size: 13px; font-weight: 500; color: var(--text, #141412); line-height: 1.5; }
.micro-prompt__actions  { display: flex; gap: 8px; }
.micro-prompt__count    { display: flex; gap: 8px; align-items: center; }
.micro-prompt__input {
  padding:       7px 10px;
  border:        1px solid var(--border, #e0e0e0);
  border-radius: var(--r-sm, 6px);
  font-size:     13px;
  width:         100px;
  background:    var(--surface, #fff);
  color:         var(--text, #141412);
}
.micro-prompt__btn {
  padding:       6px 14px;
  border-radius: var(--r-sm, 6px);
  font-size:     12px;
  font-weight:   600;
  cursor:        pointer;
  border:        1px solid var(--border, #e0e0e0);
  transition:    all .15s;
}
.micro-prompt__btn--yes {
  background:   var(--purple, #534AB7);
  color:        #fff;
  border-color: var(--purple, #534AB7);
}
.micro-prompt__btn--yes:hover:not(:disabled) { opacity: .88; }
.micro-prompt__btn--yes:disabled { opacity: .5; cursor: not-allowed; }
.micro-prompt__btn--no  { background: transparent; color: var(--text-3, #7A7870); }
.micro-prompt__btn--no:hover { border-color: var(--border-strong, #aaa); }
.micro-prompt__close {
  position:    absolute;
  top:         8px;
  right:       10px;
  background:  none;
  border:      none;
  cursor:      pointer;
  font-size:   16px;
  color:       var(--text-4, #A8A69E);
  line-height: 1;
}
.micro-enter-active, .micro-leave-active { transition: all .2s ease; }
.micro-enter-from, .micro-leave-to       { opacity: 0; transform: translateY(-6px); }
</style>