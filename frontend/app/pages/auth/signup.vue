<script setup lang="ts">
definePageMeta({ auth: false })

import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../../constants/site"

const config = useRuntimeConfig()
const router = useRouter()
const currentUser = useState<any | null>("current-user", () => null)

const form = reactive({
  email: "",
  password: "",
  business_name: "",
})

const loading = ref(false)
const error = ref("")
const showPassword = ref(false)
const fieldErrors = reactive<Record<string, string>>({})

const reassurancePoints = [
  "Free to start",
  "No credit card required",
  "Takes less than 30 seconds",
]

const termsVersion = "placeholder-v1"

const clearErrors = () => {
  error.value = ""
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
}

const buildUsername = (email: string) => {
  const local = String(email || "").split("@")[0] || "siloxr"
  const normalized = local.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "siloxr"
  const suffix = Date.now().toString(36).slice(-6)
  return `${normalized}-${suffix}`
}

const signUp = async () => {
  clearErrors()
  loading.value = true

  try {
    const username = buildUsername(form.email)

    await $fetch(`${config.public.apiBase}/auth/register/`, {
      method: "POST",
      body: {
        username,
        email: form.email,
        password: form.password,
        business_name: form.business_name,
        business_type: "",
        phone_number: "",
        country: "",
        email_notifications_enabled: true,
        telegram_enabled: false,
        preferred_channel: "email",
        terms_accepted: true,
        terms_version: termsVersion,
      },
    })

    const tokens = await $fetch<{ access: string; refresh: string }>(
      `${config.public.apiBase}/auth/login/`,
      {
        method: "POST",
        body: { identifier: form.email, password: form.password },
      }
    )

    useCookie("siloxr_token", { maxAge: 60 * 60 * 8 }).value = tokens.access
    useCookie("siloxr_refresh", { maxAge: 60 * 60 * 24 * 30 }).value = tokens.refresh

    try {
      currentUser.value = await $fetch(`${config.public.apiBase}/auth/me/`, {
        headers: { Authorization: `Bearer ${tokens.access}` },
      })
    } catch {
      currentUser.value = {
        email: form.email,
        business_name: form.business_name,
      }
    }

    await router.push("/onboarding?welcome=1")
  } catch (e: any) {
    const data = e?.data ?? {}
    const firstDetail = data.detail || data.email?.[0] || data.password?.[0] || "We couldn't create your account."

    error.value = firstDetail
    if (Array.isArray(data.email)) fieldErrors.email = data.email[0]
    if (Array.isArray(data.password)) fieldErrors.password = data.password[0]
  } finally {
    loading.value = false
  }
}

useHead({ title: "Create free account - SiloXR" })
</script>

<template>
  <AuthShell
    eyebrow="Start free"
    title="Create your free SiloXR account"
    subtitle="Get into the product quickly, then let SiloXR guide your first setup in a few short steps."
    panel-title="Inventory decisions, faster"
    panel-copy="Create your account in seconds, add one product, and see your first operating insight immediately."
  >
    <form class="signup-flow" @submit.prevent="signUp">
      <div class="signup-proof">
        <span v-for="point in reassurancePoints" :key="point" class="signup-proof__pill">{{ point }}</span>
      </div>

      <div class="field">
        <label class="field__label">Email</label>
        <input
          v-model="form.email"
          class="field__input"
          type="email"
          autocomplete="email"
          placeholder="you@company.com"
          required
        />
        <span v-if="fieldErrors.email" class="field__error">{{ fieldErrors.email }}</span>
      </div>

      <div class="field">
        <label class="field__label">Password</label>
        <div class="field__input-wrap">
          <input
            v-model="form.password"
            class="field__input"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            placeholder="Create a secure password"
            required
          />
          <button type="button" class="field__toggle" @click="showPassword = !showPassword">
            {{ showPassword ? "Hide" : "Show" }}
          </button>
        </div>
        <span v-if="fieldErrors.password" class="field__error">{{ fieldErrors.password }}</span>
      </div>

      <div class="field">
        <label class="field__label">Business name <span class="field__optional">(optional)</span></label>
        <input
          v-model="form.business_name"
          class="field__input"
          type="text"
          placeholder="Your business name"
        />
      </div>

      <div class="signup-note">
        <p class="signup-note__title">What happens next</p>
        <p class="signup-note__copy">You’ll answer 3 quick onboarding steps, add one product, and get an immediate first insight.</p>
      </div>

      <p v-if="error" class="auth-error">{{ error }}</p>

      <button type="submit" class="auth-btn" :disabled="loading">
        {{ loading ? "Creating account..." : "Create free account" }}
      </button>

      <p class="signup-legal">
        By continuing, you agree to the SiloXR terms. We keep setup intentionally light so you can get to value faster.
      </p>
    </form>

    <div class="auth-links">
      <p class="auth-switch">
        Already have an account?
        <NuxtLink to="/auth/login" class="auth-link">Sign in</NuxtLink>
      </p>
      <p class="auth-contact">
        Need help? <a :href="SITE_CONTACT_MAILTO" class="auth-link">{{ SITE_CONTACT_EMAIL }}</a>
      </p>
    </div>
  </AuthShell>
</template>

<style scoped>
.signup-flow {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.signup-proof {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.signup-proof__pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: color-mix(in srgb, #185FA5 10%, var(--bg-card));
  border: 1px solid color-mix(in srgb, #185FA5 16%, var(--border-subtle));
  color: #185FA5;
  font-size: 12px;
  font-weight: 700;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field__label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-2);
}
.field__optional {
  color: var(--text-3);
  font-weight: 600;
}
.field__input-wrap {
  position: relative;
}
.field__input {
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle);
  background: color-mix(in srgb, var(--bg-card) 96%, transparent);
  color: var(--text);
  font-size: 15px;
  transition: border-color .18s ease, box-shadow .18s ease;
}
.field__input-wrap .field__input {
  padding-right: 72px;
}
.field__input:focus {
  outline: none;
  border-color: color-mix(in srgb, #185FA5 46%, var(--border-subtle));
  box-shadow: 0 0 0 4px color-mix(in srgb, #185FA5 12%, transparent);
}
.field__toggle {
  position: absolute;
  top: 50%;
  right: 10px;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: #185FA5;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.field__error,
.auth-error {
  font-size: 12px;
  color: var(--danger, #A32D2D);
}
.signup-note {
  display: grid;
  gap: 4px;
  padding: 16px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, #4AA3FF 12%, transparent), transparent 40%),
    linear-gradient(145deg, color-mix(in srgb, #185FA5 10%, var(--bg-card)), color-mix(in srgb, var(--bg-card) 95%, transparent));
  border: 1px solid color-mix(in srgb, #185FA5 14%, var(--border-subtle));
}
.signup-note__title {
  margin: 0;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #185FA5;
}
.signup-note__copy,
.signup-legal {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-2);
}
.auth-btn {
  min-height: 52px;
  border: none;
  border-radius: 18px;
  background: linear-gradient(135deg, #185FA5, #4AA3FF);
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 18px 32px color-mix(in srgb, #185FA5 18%, transparent);
}
.auth-btn:disabled {
  opacity: .7;
  cursor: wait;
}
.auth-links {
  display: grid;
  gap: 8px;
  margin-top: 18px;
}
.auth-switch,
.auth-contact {
  margin: 0;
  font-size: 13px;
  color: var(--text-2);
}
.auth-link {
  color: #185FA5;
  font-weight: 700;
  text-decoration: none;
}
.auth-link:hover {
  text-decoration: underline;
}
@media (max-width: 640px) {
  .signup-flow {
    gap: 14px;
  }
  .field__input {
    min-height: 50px;
  }
}
</style>
