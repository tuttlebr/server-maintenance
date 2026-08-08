<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <div class="login-mark" aria-hidden="true"><i class="fas fa-layer-group"></i></div>
        <h1>Fleet Manager</h1>
        <p class="login-subtitle">One place for compute, edge, and robotics operations</p>
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
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
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
    radial-gradient(circle at 20% 10%, rgba(0, 116, 223, 0.2) 0%, transparent 45%),
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

.login-mark { width: 46px; height: 46px; margin: 0 auto 12px; border-radius: 12px; display: grid; place-items: center; background: var(--color-accent); color: #fff; font-size: 20px; }
.login-logo h1 { margin: 0; font-size: 24px; }

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
