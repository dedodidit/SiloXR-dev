<script setup lang="ts">
import { SITE_CONTACT_EMAIL, SITE_CONTACT_MAILTO } from "../constants/site"
import { countryOptions, currencyForCountry, currencyLabel } from "../constants/markets"

const { $api } = useNuxtApp()

const user = ref<any>(null)
const currentUser = useState<any | null>("current-user", () => null)
const saving = ref(false)
const savingPwd = ref(false)
const msg = ref("")
const pwdMsg = ref("")
const otpSending = ref(false)
const otpSent = ref(false)
const otpCode = ref("")
const verifying = ref(false)
const phoneInput = ref("")
const telegramLinking = ref(false)
const telegramLink = ref<any>(null)
const showOldPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

const form = reactive({
  business_name: "",
  business_type: "",
  phone_number: "",
  country: "",
  email_notifications_enabled: true,
  telegram_enabled: false,
  preferred_channel: "email",
  whatsapp_critical_only: false,
})

const pwdForm = reactive({ old_password: "", new_password: "", confirm: "" })
const derivedCurrency = computed(() => currencyForCountry(form.country || user.value?.country || ""))
const derivedCurrencyLabel = computed(() => currencyLabel(derivedCurrency.value))

const hydrateProfile = async () => {
  user.value = await $api("/profile/").catch(() => null)
  if (!user.value) return
  currentUser.value = user.value
  Object.assign(form, {
    business_name: user.value.business_name,
    business_type: user.value.business_type,
    phone_number: user.value.phone_number,
    country: user.value.country || "",
    email_notifications_enabled: user.value.email_notifications_enabled,
    telegram_enabled: !!user.value.telegram_enabled,
    preferred_channel: user.value.preferred_channel || "email",
    whatsapp_critical_only: !!user.value.whatsapp_critical_only,
  })
  phoneInput.value = user.value.phone_number || ""
  telegramLink.value = user.value.telegram_link
    ? {
        link: user.value.telegram_link,
        token: user.value.telegram_link.split("start=").pop() || "",
        bot_user: user.value.telegram_bot_user || "",
      }
    : null
  if (!user.value.telegram_link && user.value.telegram_link_error) {
    msg.value = user.value.telegram_link_error
  }
}

onMounted(hydrateProfile)

const saveProfile = async () => {
  saving.value = true
  msg.value = ""
  try {
    await $api("/profile/", { method: "PATCH", body: form })
    msg.value = "Profile saved."
    await hydrateProfile()
  } catch (e: any) {
    msg.value = e?.data?.detail ?? "Could not save."
  } finally {
    saving.value = false
  }
}

const changePassword = async () => {
  pwdMsg.value = ""
  if (pwdForm.new_password !== pwdForm.confirm) {
    pwdMsg.value = "Passwords do not match."
    return
  }
  savingPwd.value = true
  try {
    await $api("/profile/password/", {
      method: "POST",
      body: { old_password: pwdForm.old_password, new_password: pwdForm.new_password },
    })
    pwdMsg.value = "Password changed successfully."
    Object.assign(pwdForm, { old_password: "", new_password: "", confirm: "" })
  } catch (e: any) {
    pwdMsg.value = e?.data?.detail ?? e?.data?.password?.[0] ?? "Could not change password."
  } finally {
    savingPwd.value = false
  }
}

const sendOTP = async () => {
  otpSending.value = true
  msg.value = ""
  try {
    await $api("/profile/phone/send-otp/", {
      method: "POST",
      body: { phone_number: phoneInput.value },
    })
    otpSent.value = true
    form.phone_number = phoneInput.value
  } catch (e: any) {
    msg.value = e?.data?.detail ?? "Could not send verification code."
  } finally {
    otpSending.value = false
  }
}

const verifyOTP = async () => {
  verifying.value = true
  msg.value = ""
  try {
    await $api("/profile/phone/verify/", {
      method: "POST",
      body: { code: otpCode.value },
    })
    msg.value = "WhatsApp number verified."
    otpSent.value = false
    otpCode.value = ""
    await hydrateProfile()
  } catch (e: any) {
    msg.value = e?.data?.detail ?? "Invalid code."
  } finally {
    verifying.value = false
  }
}

const getTelegramLink = async () => {
  telegramLinking.value = true
  msg.value = ""
  try {
    telegramLink.value = await $api("/telegram/link/")
    if (process.client && telegramLink.value?.link) {
      window.open(telegramLink.value.link, "_blank", "noopener,noreferrer")
      msg.value = "Telegram opened. Send the start message there, then return here and save once the account is linked."
    }
  } catch (e: any) {
    const fallbackLink = user.value?.telegram_link
    if (fallbackLink) {
      telegramLink.value = {
        link: fallbackLink,
        token: fallbackLink.split("start=").pop() || "",
        bot_user: user.value?.telegram_bot_user || "",
      }
      if (process.client && telegramLink.value?.link) {
        window.open(telegramLink.value.link, "_blank", "noopener,noreferrer")
        msg.value = "Telegram opened. Send the start message there, then return here and save once the account is linked."
        return
      }
    }
    msg.value = e?.data?.detail ?? user.value?.telegram_link_error ?? "Could not generate Telegram link."
  } finally {
    telegramLinking.value = false
  }
}

useHead({ title: "Account settings - SiloXR" })
const isFreeUser = computed(() => Boolean(user.value) && !user.value?.is_pro)
</script>

<template>
  <div class="page-pad profile-page">
    <div class="profile-page__header">
      <h1 class="t-heading">Account settings</h1>
      <p class="t-small" style="margin-top:3px">Manage your profile, password, and notification channels.</p>
      <p class="t-small" style="margin-top:8px">
        Need help? <a :href="SITE_CONTACT_MAILTO" class="profile-link">{{ SITE_CONTACT_EMAIL }}</a>
      </p>
    </div>

    <div class="profile-grid">
      <section v-if="isFreeUser" class="profile-section surface">
        <h2 class="profile-section__title">Upgrade to Pro</h2>
        <p class="t-body" style="margin-bottom:14px">
          Unlock stronger notifications, more advanced decision support, and the full SiloXR operating experience.
        </p>
        <NuxtLink to="/billing/upgrade" class="btn btn-primary" style="width:fit-content">
          View upgrade options
        </NuxtLink>
      </section>

      <section class="profile-section surface">
        <h2 class="profile-section__title">Business info</h2>
        <div class="profile-fields">
          <div class="field">
            <label class="field__label">Business name</label>
            <input v-model="form.business_name" class="field__input" type="text" placeholder="Your business name" />
          </div>
          <div class="field">
            <label class="field__label">Business type</label>
            <select v-model="form.business_type" class="field__input">
              <option value="">Select type…</option>
              <option value="retail">Retail</option>
              <option value="wholesale">Wholesale / distribution</option>
              <option value="pharmacy">Pharmacy</option>
              <option value="food">Food & beverage</option>
              <option value="hardware">Hardware & building</option>
              <option value="supermarket">Supermarket</option>
              <option value="other">Other</option>
            </select>
          </div>
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
            <input class="field__input" type="text" :value="derivedCurrencyLabel" disabled />
            <span class="field__hint">Currency follows your selected country automatically.</span>
          </div>
          <div class="field">
            <label style="display:flex;align-items:center;gap:10px;font-size:13px;cursor:pointer">
              <input type="checkbox" v-model="form.email_notifications_enabled" />
              Receive decision alerts by email
            </label>
          </div>
        </div>
        <p v-if="msg" class="profile-msg" :class="msg.includes('saved') || msg.includes('verified') ? 'profile-msg--ok' : 'profile-msg--err'">
          {{ msg }}
        </p>
        <button class="btn btn-primary" :disabled="saving" @click="saveProfile" style="margin-top:16px;width:fit-content">
          {{ saving ? "Saving…" : "Save changes" }}
        </button>
      </section>

      <section class="profile-section surface">
        <h2 class="profile-section__title">WhatsApp notifications</h2>
        <p class="t-body" style="margin-bottom:14px">
          Verify your phone number before enabling WhatsApp delivery.
        </p>
        <div class="field">
          <label class="field__label">WhatsApp number</label>
          <input v-model="phoneInput" class="field__input" type="tel" placeholder="+2348012345678" />
          <span class="field__hint">Include country code, for example +234 for Nigeria.</span>
        </div>
        <div class="profile-actions">
          <button class="btn btn-secondary" :disabled="otpSending" @click="sendOTP">
            {{ otpSending ? "Sending…" : "Send verification code" }}
          </button>
        </div>
        <div v-if="otpSent" class="profile-otp">
          <div class="field">
            <label class="field__label">Verification code</label>
            <input v-model="otpCode" class="field__input" type="text" maxlength="6" placeholder="6-digit code" />
          </div>
          <button class="btn btn-primary" :disabled="verifying" @click="verifyOTP">
            {{ verifying ? "Verifying…" : "Verify number" }}
          </button>
        </div>
      </section>

      <section class="profile-section surface">
        <h2 class="profile-section__title">Telegram notifications</h2>
        <p class="t-body" style="margin-bottom:14px">
          Telegram must be linked to your SiloXR account before it can be used for real-time notifications. You can still change channel preference and delivery settings here any time.
        </p>

        <div v-if="user?.telegram_linked" class="profile-msg profile-msg--ok">
          Telegram connected. You can enable Telegram delivery below.
        </div>
        <div v-else class="profile-telegram">
          <a :href="user?.telegram_download_url || 'https://telegram.org/dl'" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">
            Download Telegram
          </a>
          <button class="btn btn-primary" :disabled="telegramLinking" @click="getTelegramLink">
            {{ telegramLinking ? "Generating…" : "Connect Telegram" }}
          </button>
          <div v-if="telegramLink" class="profile-otp">
            <p class="t-small">Open the bot link and send the start code to verify your Telegram account.</p>
            <a :href="telegramLink.link" target="_blank" rel="noopener noreferrer" class="btn btn-primary" style="width:fit-content">
              Open SiloXR bot
            </a>
            <p class="field__hint" style="margin-top:8px">Link expires in 30 minutes. Code: {{ telegramLink.token }}</p>
          </div>
          <p v-else-if="user?.telegram_link_error" class="profile-msg profile-msg--err" style="margin-top:12px">
            {{ user.telegram_link_error }}
          </p>
        </div>

        <div class="field" style="margin-top:16px">
          <label style="display:flex;align-items:center;gap:10px;font-size:13px;cursor:pointer">
            <input type="checkbox" v-model="form.telegram_enabled" :disabled="!user?.telegram_linked" />
            Enable Telegram notifications
          </label>
        </div>

        <div class="field" style="margin-top:16px">
          <label class="field__label">Preferred notification channel</label>
          <select v-model="form.preferred_channel" class="field__input">
            <option value="email">Email</option>
            <option value="telegram">Telegram</option>
          </select>
        </div>
      </section>

      <section v-if="user?.is_pro" class="profile-section surface">
        <h2 class="profile-section__title">WhatsApp controls</h2>
        <div class="field">
          <label style="display:flex;align-items:center;gap:10px;font-size:13px;cursor:pointer">
            <input type="checkbox" v-model="form.whatsapp_critical_only" />
            Critical alerts only
          </label>
          <span class="field__hint">Only the highest-confidence urgent alerts will be sent via WhatsApp.</span>
        </div>
      </section>

      <section class="profile-section surface">
        <h2 class="profile-section__title">Password</h2>
        <div class="profile-fields">
          <div class="field">
            <label class="field__label">Current password</label>
            <div class="field__input-wrap">
              <input v-model="pwdForm.old_password" class="field__input" :type="showOldPassword ? 'text' : 'password'" autocomplete="current-password" />
              <button type="button" class="field__toggle" @click="showOldPassword = !showOldPassword">
                {{ showOldPassword ? "Hide" : "Show" }}
              </button>
            </div>
          </div>
          <div class="field">
            <label class="field__label">New password</label>
            <div class="field__input-wrap">
              <input v-model="pwdForm.new_password" class="field__input" :type="showNewPassword ? 'text' : 'password'" autocomplete="new-password" />
              <button type="button" class="field__toggle" @click="showNewPassword = !showNewPassword">
                {{ showNewPassword ? "Hide" : "Show" }}
              </button>
            </div>
          </div>
          <div class="field">
            <label class="field__label">Confirm new password</label>
            <div class="field__input-wrap">
              <input v-model="pwdForm.confirm" class="field__input" :type="showConfirmPassword ? 'text' : 'password'" autocomplete="new-password" />
              <button type="button" class="field__toggle" @click="showConfirmPassword = !showConfirmPassword">
                {{ showConfirmPassword ? "Hide" : "Show" }}
              </button>
            </div>
          </div>
        </div>
        <p v-if="pwdMsg" class="profile-msg" :class="pwdMsg.includes('successfully') ? 'profile-msg--ok' : 'profile-msg--err'">
          {{ pwdMsg }}
        </p>
        <button class="btn btn-primary" :disabled="savingPwd" @click="changePassword" style="margin-top:16px;width:fit-content">
          {{ savingPwd ? "Updating…" : "Change password" }}
        </button>
      </section>
    </div>
  </div>
</template>

<style scoped>
.profile-page__header { margin-bottom: 28px; }
.profile-link {
  color: var(--purple);
  font-weight: 600;
  text-decoration: none;
}
.profile-link:hover {
  text-decoration: underline;
}
.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  align-items: start;
}
.profile-section {
  padding: 24px;
  display: flex;
  flex-direction: column;
}
.profile-section__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 16px;
}
.profile-fields {
  display: flex;
  flex-direction: column;
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
  color: var(--text-3);
}
.field__hint {
  font-size: 12px;
  color: var(--text-4);
}
.field__input {
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg-card);
  color: var(--text);
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
.profile-msg {
  font-size: 12px;
  padding: 8px 12px;
  border-radius: var(--r-sm);
  margin-top: 8px;
}
.profile-msg--ok { background: var(--teal-bg); color: var(--teal); }
.profile-msg--err { background: var(--red-bg); color: var(--red); }
.profile-actions,
.profile-telegram {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.profile-otp {
  margin-top: 14px;
  padding: 14px;
  background: var(--bg-sunken);
  border-radius: var(--r-md);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
