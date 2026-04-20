type TourPreference = "pending" | "guided" | "skip"

const STORAGE_KEY = "siloxr-tour-choice"

export function useTourPreference() {
  const preference = useState<TourPreference>("tour-preference", () => "pending")

  const initialize = () => {
    if (!process.client) return
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === "guided" || stored === "skip") {
      preference.value = stored
      return
    }
    preference.value = "pending"
  }

  const setPreference = (value: TourPreference) => {
    preference.value = value
    if (!process.client) return
    window.localStorage.setItem(STORAGE_KEY, value)
  }

  return {
    preference,
    initialize,
    setPreference,
  }
}
