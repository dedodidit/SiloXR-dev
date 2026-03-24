<script setup lang="ts">
definePageMeta({ auth: false })

import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../../constants/site"
import { countryOptions, currencyOptions } from "../../constants/markets"

const config = useRuntimeConfig()
const router = useRouter()

const form = reactive({
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
  business_name: "",
  business_type: "",
  phone_number: "",
  country: "",
  currency: "USD",
  email_notifications_enabled: true,
  preferred_channel: "email",
  terms_accepted: false,
})

const loading = ref(false)
const error = ref("")
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const fieldErrors = reactive<Record<string, string>>({})

const termsVersion = "placeholder-v1"

const clearErrors = () => {
  error.value = ""
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
}

const signUp = async () => {
  clearErrors()

  if (form.password !== form.confirmPassword) {
    fieldErrors.confirmPassword = "Passwords do not match."
    return
  }

  if (!form.terms_accepted) {
    fieldErrors.terms_accepted = "You must accept the terms and conditions to continue."
    return
  }

  loading.value = true

  try {
    const registration = await $fetch<{
      telegram_link?: string
      telegram_bot_user?: string
    }>(`${config.public.apiBase}/auth/register/`, {
      method: "POST",
      body: {
        username: form.username,
        email: form.email,
        password: form.password,
        business_name: form.business_name,
        business_type: form.business_type,
        phone_number: form.phone_number,
        country: form.country,
        currency: form.currency,
        email_notifications_enabled: form.email_notifications_enabled,
        telegram_enabled: form.preferred_channel === "telegram",
        preferred_channel: form.preferred_channel,
        terms_accepted: form.terms_accepted,
        terms_version: termsVersion,
      },
    })

    const tokens = await $fetch<{ access: string; refresh: string }>(
      `${config.public.apiBase}/auth/login/`,
      {
        method: "POST",
        body: { identifier: form.username || form.email, password: form.password },
      }
    )

    useCookie("siloxr_token", { maxAge: 60 * 60 * 8 }).value = tokens.access
    useCookie("siloxr_refresh", { maxAge: 60 * 60 * 24 * 30 }).value = tokens.refresh

    if (process.client && form.preferred_channel === "telegram" && registration?.telegram_link) {
      sessionStorage.setItem("siloxr-telegram-link", JSON.stringify({
        link: registration.telegram_link,
        bot_user: registration.telegram_bot_user || "",
      }))
      await router.push("/auth/telegram-link")
      return
    }

    await router.push("/dashboard")
  } catch (e: any) {
    const data = e?.data ?? {}
    const firstDetail = data.detail
      || data.username?.[0]
      || data.email?.[0]
      || data.password?.[0]
      || data.terms_accepted?.[0]
      || "We couldn't complete your signup."

    error.value = firstDetail

    if (Array.isArray(data.username)) fieldErrors.username = data.username[0]
    if (Array.isArray(data.email)) fieldErrors.email = data.email[0]
    if (Array.isArray(data.password)) fieldErrors.password = data.password[0]
    if (Array.isArray(data.terms_accepted)) fieldErrors.terms_accepted = data.terms_accepted[0]
  } finally {
    loading.value = false
  }
}

useHead({ title: "Create account - SiloXR" })
</script>

<template>
  <AuthShell
    eyebrow="Start free"
    title="Create your SiloXR account"
    subtitle="Start with industry baselines, then let SiloXR personalize around your real business activity."
    panel-title="Decision system setup"
    panel-copy="Set up your account once, then move from uncertainty to clearer stock, demand, and revenue decisions."
  >
    <form class="auth-form" @submit.prevent="signUp">
      <div class="auth-grid">
        <div class="field">
          <label class="field__label">Username</label>
          <input
            v-model="form.username"
            class="field__input"
            type="text"
            autocomplete="username"
            placeholder="your username"
            required
          />
          <span v-if="fieldErrors.username" class="field__error">{{ fieldErrors.username }}</span>
        </div>

        <div class="field">
          <label class="field__label">Business name</label>
          <input
            v-model="form.business_name"
            class="field__input"
            type="text"
            placeholder="Your business name"
          />
        </div>
      </div>

      <div class="auth-grid">
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
          <label class="field__label">Phone number</label>
          <input
            v-model="form.phone_number"
            class="field__input"
            type="tel"
            autocomplete="tel"
            placeholder="+2348012345678"
          />
        </div>
      </div>

      <div class="auth-grid">
        <div class="field">
          <label class="field__label">Country</label>
          <select v-model="form.country" class="field__input">
            <option v-for="option in countryOptions" :key="option.value || 'blank-country'" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>

        <div class="field">
          <label class="field__label">Currency</label>
          <select v-model="form.currency" class="field__input">
            <option v-for="option in currencyOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
      </div>

      <div class="field">
        <label class="field__label">Business type</label>
        <select v-model="form.business_type" class="field__input">
          <option value="">Select business type</option>
          <option value="retail">Retail</option>
          <option value="wholesale">Wholesale / distribution</option>
          <option value="pharmacy">Pharmacy</option>
          <option value="food">Food & beverage</option>
          <option value="hardware">Hardware & building</option>
          <option value="supermarket">Supermarket</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div class="auth-grid">
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
          <label class="field__label">Confirm password</label>
          <div class="field__input-wrap">
            <input
              v-model="form.confirmPassword"
              class="field__input"
              :type="showConfirmPassword ? 'text' : 'password'"
              autocomplete="new-password"
              placeholder="Repeat your password"
              required
            />
            <button type="button" class="field__toggle" @click="showConfirmPassword = !showConfirmPassword">
              {{ showConfirmPassword ? "Hide" : "Show" }}
            </button>
          </div>
          <span v-if="fieldErrors.confirmPassword" class="field__error">{{ fieldErrors.confirmPassword }}</span>
        </div>
      </div>

      <div class="terms-box">
        <p class="terms-box__title">Notification setup</p>
        <p class="terms-box__copy">
          Choose how SiloXR should reach you first. You can change this later in your profile.
        </p>
        <div class="notify-choice">
          <label class="notify-option">
            <input v-model="form.preferred_channel" type="radio" value="email" />
            <span>Email first</span>
          </label>
          <label class="notify-option">
            <input v-model="form.preferred_channel" type="radio" value="telegram" />
            <span>Telegram first</span>
          </label>
        </div>
        <label class="terms-check">
          <input v-model="form.email_notifications_enabled" type="checkbox" />
          <span>Send SiloXR updates to my email.</span>
        </label>
        <p v-if="form.preferred_channel === 'telegram'" class="terms-box__hint">
          Telegram setup will continue immediately after signup so you do not have to repeat this step later.
        </p>
      </div>

      <div class="terms-box">
        <p class="terms-box__title">Terms and conditions</p>
        <p class="terms-box__copy">
          <NuxtLink to="/legal/terms" class="terms-box__link">Placeholder legal framework</NuxtLink>.
          This will be replaced with the final SiloXR terms, privacy, notification,
          and billing conditions before launch.
        </p>
        <label class="terms-check">
          <input v-model="form.terms_accepted" type="checkbox" />
          <span>I accept the SiloXR terms and conditions.</span>
        </label>
        <span v-if="fieldErrors.terms_accepted" class="field__error">{{ fieldErrors.terms_accepted }}</span>
      </div>

      <p v-if="error" class="auth-error">{{ error }}</p>

      <button type="submit" class="auth-btn" :disabled="loading">
        {{ loading ? "Creating account..." : "Create free account" }}
      </button>
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
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.auth-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field__input-wrap {
  position: relative;
}
.field__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}
.field__input {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-raised);
  color: var(--text);
  transition: border-color .15s ease, box-shadow .15s ease, background .2s ease;
}
.field__input::placeholder {
  color: var(--text-4);
}
.field__input:focus {
  outline: none;
  border-color: var(--purple);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--purple) 18%, transparent);
}
.field__toggle {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: var(--purple);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.field__error {
  font-size: 12px;
  color: var(--red);
}
.terms-box {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--purple-bg) 72%, transparent), transparent 100%),
    var(--bg-raised);
}
.terms-box__title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}
.terms-box__copy {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-2);
}
.terms-box__link {
  color: var(--purple);
  font-weight: 700;
  text-decoration: none;
}
.terms-box__link:hover {
  text-decoration: underline;
}
.terms-box__hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-3);
}
.notify-choice {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.notify-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-2);
  cursor: pointer;
}
.terms-check {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  font-size: 13px;
  color: var(--text-2);
  cursor: pointer;
}
.terms-check input {
  margin-top: 2px;
}
.auth-error {
  font-size: 13px;
  color: var(--red);
  padding: 10px 12px;
  background: var(--red-bg);
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--red) 20%, transparent);
}
.auth-btn {
  padding: 13px 14px;
  background: linear-gradient(135deg, var(--purple), var(--purple-2));
  color: #fff;
  border: none;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: transform .15s ease, box-shadow .15s ease, opacity .15s ease;
  box-shadow: 0 8px 24px color-mix(in srgb, var(--purple) 28%, transparent);
}
.auth-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}
.auth-btn:disabled {
  opacity: .6;
  cursor: not-allowed;
}
.auth-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.auth-switch,
.auth-contact {
  font-size: 13px;
  color: var(--text-3);
}
.auth-link {
  color: var(--purple);
  font-weight: 600;
  text-decoration: none;
}
.auth-link:hover {
  text-decoration: underline;
}
@media (max-width: 720px) {
  .auth-grid {
    grid-template-columns: 1fr;
  }
}
</style>
