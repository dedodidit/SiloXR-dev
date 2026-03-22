// frontend/app/composables/useInactivityNudge.ts

/**
 * Detects user inactivity and surfaces a soft nudge
 * encouraging them to update their stock data.
 */
export const useInactivityNudge = (thresholdMs = 3 * 60 * 1000) => {
  const nudgeVisible  = ref(false)
  const nudgeMessage  = ref("")
  let   timer: any    = null

  const MESSAGES = [
    "Update your stock counts to improve forecast accuracy.",
    "Recording a sale takes 5 seconds — it keeps your insights fresh.",
    "Your confidence scores improve with each stock count you record.",
  ]

  let msgIdx = 0

  const reset = () => {
    clearTimeout(timer)
    nudgeVisible.value = false
    timer = setTimeout(() => {
      nudgeMessage.value = MESSAGES[msgIdx % MESSAGES.length]
      msgIdx++
      nudgeVisible.value = true
    }, thresholdMs)
  }

  onMounted(() => {
    window.addEventListener("mousemove", reset)
    window.addEventListener("keydown",   reset)
    window.addEventListener("click",     reset)
    window.addEventListener("touchstart",reset)
    reset()
  })

  onUnmounted(() => {
    clearTimeout(timer)
    window.removeEventListener("mousemove", reset)
    window.removeEventListener("keydown",   reset)
    window.removeEventListener("click",     reset)
    window.removeEventListener("touchstart",reset)
  })

  const dismiss = () => { nudgeVisible.value = false; reset() }

  return { nudgeVisible, nudgeMessage, dismiss }
}