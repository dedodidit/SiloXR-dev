<script setup lang="ts">
definePageMeta({ auth: false })

const config = useRuntimeConfig()
const step = ref<"email" | "code" | "done">("email")
const email = ref("")
const code = ref("")
const newPwd = ref("")
const confirm = ref("")
const loading = ref(false)
const error = ref("")
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

const sendCode = async () => {
  error.value = ""
  loading.value = true
  try {
    await $fetch(`${config.public.apiBase}/auth/forgot-password/`, {
      method: "POST",
      body: { email: email.value },
    })
    step.value = "code"
  } catch {
    step.value = "code"
  } finally {
    loading.value = false
  }
}

const resetPwd = async () => {
  error.value = ""
  if (newPwd.value !== confirm.value) {
    error.value = "Passwords do not match."
    return
  }
  loading.value = true
  try {
    await $fetch(`${config.public.apiBase}/auth/reset-password/`, {
      method: "POST",
      body: { email: email.value, code: code.value, new_password: newPwd.value },
    })
    step.value = "done"
  } catch (e: any) {
    error.value = e?.data?.detail ?? e?.data?.password?.[0] ?? "Invalid or expired code."
  } finally {
    loading.value = false
  }
}

useHead({ title: "Reset password - SiloXR" })
</script>

<template>
  <AuthShell
    eyebrow="Secure account recovery"
    :title="step === 'email' ? 'Reset your password' : step === 'code' ? 'Enter your reset code' : 'Password updated'"
    :subtitle="step === 'email'
      ? 'We will send a verification code to your email.'
      : step === 'code'
      ? 'Use the code from your inbox to choose a new password.'
      : 'Your account is ready to sign in again.'"
    panel-title="Recovery flow"
    panel-copy="Get back into SiloXR without losing your account history, preferences, or business context."
  >
      <form v-if="step === 'email'" class="auth-form" @submit.prevent="sendCode">
        <div class="field">
          <label class="field__label">Email address</label>
          <input v-model="email" class="field__input" type="email" required placeholder="you@company.com" />
        </div>
        <p v-if="error" class="auth-error">{{ error }}</p>
        <button type="submit" class="auth-btn" :disabled="loading">
          {{ loading ? "Sending…" : "Send reset code" }}
        </button>
      </form>

      <form v-else-if="step === 'code'" class="auth-form" @submit.prevent="resetPwd">
        <div class="field">
          <label class="field__label">Reset code</label>
          <input v-model="code" class="field__input" type="text" maxlength="6" required placeholder="6-digit code" />
          <span class="field__hint">Check your email for the code.</span>
        </div>
        <div class="field">
          <label class="field__label">New password</label>
          <div class="field__input-wrap">
            <input
              v-model="newPwd"
              class="field__input"
              :type="showNewPassword ? 'text' : 'password'"
              autocomplete="new-password"
              required
            />
            <button type="button" class="field__toggle" @click="showNewPassword = !showNewPassword">
              {{ showNewPassword ? "Hide" : "Show" }}
            </button>
          </div>
        </div>
        <div class="field">
          <label class="field__label">Confirm new password</label>
          <div class="field__input-wrap">
            <input
              v-model="confirm"
              class="field__input"
              :type="showConfirmPassword ? 'text' : 'password'"
              autocomplete="new-password"
              required
            />
            <button type="button" class="field__toggle" @click="showConfirmPassword = !showConfirmPassword">
              {{ showConfirmPassword ? "Hide" : "Show" }}
            </button>
          </div>
        </div>
        <p v-if="error" class="auth-error">{{ error }}</p>
        <button type="submit" class="auth-btn" :disabled="loading">
          {{ loading ? "Resetting…" : "Reset password" }}
        </button>
      </form>

      <div v-else class="auth-form auth-form--done">
        <div class="auth-done">✓</div>
        <p class="auth-card__sub">Your password has been reset successfully.</p>
        <NuxtLink to="/auth/login" class="auth-btn auth-btn--link">Sign in now</NuxtLink>
      </div>

      <div class="auth-links">
        <NuxtLink to="/auth/login" class="auth-link">Back to sign in</NuxtLink>
      </div>
  </AuthShell>
</template>

<style scoped>
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.auth-form--done {
  text-align: center;
  align-items: center;
}
.auth-done {
  font-size: 38px;
  color: var(--teal);
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
.field__input:focus {
  outline: none;
  border-color: var(--purple);
  box-shadow: 0 0 0 3px rgba(83,74,183,0.1);
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
.auth-error {
  font-size: 13px;
  color: var(--red);
  padding: 9px 12px;
  background: var(--red-bg);
  border-radius: 10px;
  border: 1px solid rgba(255,77,79,0.15);
}
.auth-btn {
  padding: 12px;
  background: linear-gradient(135deg, var(--purple), var(--purple-2));
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: transform .15s, box-shadow .15s, opacity .15s;
  box-shadow: 0 4px 14px rgba(83,74,183,0.28);
  text-align: center;
  text-decoration: none;
}
.auth-btn:hover:not(:disabled) {
  transform: scale(1.015);
  box-shadow: 0 6px 20px rgba(83,74,183,0.38);
}
.auth-btn:disabled {
  opacity: .55;
  cursor: not-allowed;
}
.auth-btn--link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.auth-links {
  display: flex;
  justify-content: center;
}
.auth-link {
  color: var(--purple);
  font-weight: 600;
  text-decoration: none;
}
.auth-link:hover {
  text-decoration: underline;
}
</style>
