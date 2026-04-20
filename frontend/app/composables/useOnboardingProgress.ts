type OnboardingDraft = {
  step: 1 | 2 | 3
  businessType: string
  productName: string
  estimatedStock: string
  productId: string
  completed: boolean
}

const DEFAULT_DRAFT: OnboardingDraft = {
  step: 1,
  businessType: "",
  productName: "",
  estimatedStock: "",
  productId: "",
  completed: false,
}

export function useOnboardingProgress(userKey: MaybeRefOrGetter<string>) {
  const state = useState<OnboardingDraft>("onboarding-progress", () => ({ ...DEFAULT_DRAFT }))

  const storageKey = computed(() => {
    const resolved = String(toValue(userKey) || "guest").trim() || "guest"
    return `siloxr-onboarding:${resolved}`
  })

  const load = () => {
    if (!process.client) return
    try {
      const raw = window.localStorage.getItem(storageKey.value)
      if (!raw) {
        state.value = { ...DEFAULT_DRAFT }
        return
      }
      const parsed = JSON.parse(raw)
      state.value = {
        ...DEFAULT_DRAFT,
        ...parsed,
      }
    } catch {
      state.value = { ...DEFAULT_DRAFT }
    }
  }

  const save = (patch: Partial<OnboardingDraft>) => {
    state.value = {
      ...state.value,
      ...patch,
    }
    if (!process.client) return
    window.localStorage.setItem(storageKey.value, JSON.stringify(state.value))
  }

  const reset = () => {
    state.value = { ...DEFAULT_DRAFT }
    if (!process.client) return
    window.localStorage.removeItem(storageKey.value)
  }

  return {
    progress: state,
    load,
    save,
    reset,
  }
}
