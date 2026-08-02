<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <svg viewBox="0 0 120 44" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="NVIDIA">
          <text x="10" y="32" fill="#76B900" font-family="NVIDIA Sans, sans-serif" font-weight="700" font-size="28">NVIDIA</text>
        </svg>
        <p class="login-subtitle">Fleet Manager</p>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label class="form-label" for="login-username">Username</label>
          <input
            id="login-username"
            v-model="username"
            type="text"
            class="form-input"
            placeholder="admin"
            autocomplete="username"
            autofocus
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="login-password">Password</label>
          <input
            id="login-password"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="Enter password"
            autocomplete="current-password"
          />
        </div>
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button type="submit" class="btn btn-green login-btn" :disabled="loading">
          {{ loading ? "Signing in…" : "Sign In" }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { login, setToken } from "../api.js";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function handleLogin() {
  error.value = "";
  loading.value = true;
  try {
    const data = await login(username.value, password.value);
    setToken(data.access_token);
    router.push("/");
  } catch (e) {
    error.value = e?.status === 401 ? "Invalid username or password" : (e?.message || "Couldn't sign in");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 20% 10%, rgba(118, 185, 0, 0.18) 0%, transparent 45%),
    radial-gradient(circle at 80% 90%, rgba(0, 116, 223, 0.12) 0%, transparent 50%),
    var(--surface-dark);
}

.login-card {
  background-color: var(--surface-white);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
  padding: var(--space-lg);
  width: 380px;
  max-width: 90vw;
}

.login-logo {
  text-align: center;
  margin-bottom: var(--space-md);
}

.login-logo svg {
  height: 36px;
  margin: 0 auto;
  display: block;
}

.login-subtitle {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 8px;
  letter-spacing: 0.4px;
}

.login-btn {
  width: 100%;
  margin-top: var(--space-xs);
}

.login-error {
  color: var(--color-danger);
  font-size: 13px;
  margin-bottom: var(--space-xs);
  font-weight: 500;
}
</style>
