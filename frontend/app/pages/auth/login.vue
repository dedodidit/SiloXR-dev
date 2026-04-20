<script setup lang="ts">
definePageMeta({ auth: false })

const config = useRuntimeConfig()
const router = useRouter()

const identifier = ref("")
const password = ref("")
const error = ref("")
const loading = ref(false)
const showPassword = ref(false)

const login = async () => {
  error.value = ""
  loading.value = true

  try {
    const data = await $fetch<{ access: string; refresh: string }>(
      `${config.public.apiBase}/auth/login/`,
      {
        method: "POST",
        body: { identifier: identifier.value, password: password.value },
      }
    )

    useCookie("siloxr_token", { maxAge: 60 * 60 * 8 }).value = data.access
    useCookie("siloxr_refresh", { maxAge: 60 * 60 * 24 * 30 }).value = data.refresh
    await router.push("/dashboard")
  } catch {
    error.value = "Invalid username, email, or password."
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell
    eyebrow="Secure access"
    title="Welcome back to SiloXR"
    subtitle="Sign in to continue into your command center and active workspaces."
    panel-title="Decision operating system"
    panel-copy="The fastest path back into your current money posture, active decisions, and product execution flow."
  >
    <form class="auth-form" @submit.prevent="login">
      <div class="field">
        <label class="field__label">Username or email</label>
        <input
          v-model="identifier"
          class="field__input"
          type="text"
          placeholder="your username or email"
          autocomplete="username"
          required
        />
      </div>

      <div class="field">
        <label class="field__label">Password</label>
        <div class="field__input-wrap">
          <input
            v-model="password"
            class="field__input"
            :type="showPassword ? 'text' : 'password'"
            placeholder="Enter your password"
            autocomplete="current-password"
            required
          />
          <button type="button" class="field__toggle" @click="showPassword = !showPassword">
            {{ showPassword ? "Hide" : "Show" }}
          </button>
        </div>
      </div>

      <p v-if="error" class="auth-error">{{ error }}</p>

      <button type="submit" class="auth-btn" :disabled="loading">
        {{ loading ? "Signing in..." : "Sign in" }}
      </button>
    </form>

    <div class="auth-links">
      <NuxtLink to="/auth/forgot-password" class="auth-link">Forgot password?</NuxtLink>
      <p class="auth-switch">
        No account?
        <NuxtLink to="/auth/signup" class="auth-link">Create one free</NuxtLink>
      </p>
    </div>
  </AuthShell>
</template>

<style scoped>
.auth-form {
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
.field__input {
  width: 100%;
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
}
.auth-btn:hover:not(:disabled) {
  transform: scale(1.015);
  box-shadow: 0 6px 20px rgba(83,74,183,0.38);
}
.auth-btn:disabled {
  opacity: .55;
  cursor: not-allowed;
}
.auth-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.auth-switch {
  font-size: 13px;
  color: var(--text-4);
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
