<template>
  <div class="toast-container" role="region" aria-live="polite" aria-label="Notifications">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      :class="['toast', `toast-${toast.type}`]"
      role="status"
    >
      <div class="toast-row">
        <span class="toast-message">
          <i v-if="toast.icon" :class="['fas', toast.icon]" aria-hidden="true" style="margin-right: 6px"></i>
          {{ toast.message }}
        </span>
        <button class="toast-close" :aria-label="`Dismiss ${toast.type} notification`" @click="remove(toast.id)">
          &times;
        </button>
      </div>
      <button
        v-if="toast.details && !toast.showDetails"
        class="toast-details-toggle"
        type="button"
        @click="toggleDetails(toast.id)"
      >
        Show details
      </button>
      <button
        v-else-if="toast.details && toast.showDetails"
        class="toast-details-toggle"
        type="button"
        @click="toggleDetails(toast.id)"
      >
        Hide details
      </button>
      <pre v-if="toast.details && toast.showDetails" class="toast-details">{{ toast.details }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const toasts = ref([]);
let nextId = 0;

function add(message, type = "info", { duration = 5000, details = "", icon = "" } = {}) {
  const id = nextId++;
  const defaultIcons = { success: "fa-check-circle", error: "fa-exclamation-circle", info: "fa-info-circle" };
  toasts.value.push({
    id,
    message,
    type,
    details,
    showDetails: false,
    icon: icon || defaultIcons[type] || "",
  });
  // Errors stick around longer (and forever if details are present)
  const effectiveDuration = type === "error" && details ? 0 : duration;
  if (effectiveDuration > 0) {
    setTimeout(() => remove(id), effectiveDuration);
  }
}

function remove(id) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

function toggleDetails(id) {
  const t = toasts.value.find((x) => x.id === id);
  if (t) t.showDetails = !t.showDetails;
}

// Friendly error helper — accepts either a string, an Error/ApiError, or {message, details}.
function errorFromValue(value, fallbackMessage = "Something went wrong") {
  if (!value) return { message: fallbackMessage, details: "" };
  if (typeof value === "string") return { message: value, details: "" };
  if (value && typeof value === "object") {
    return {
      message: value.message || fallbackMessage,
      details: value.detail || value.stack || "",
    };
  }
  return { message: String(value), details: "" };
}

// Public API. Callers can pass:
//   $toast.error("Couldn't reboot host", e)               // err object → details
//   $toast.error("Couldn't reboot host", { details: "…" }) // explicit opts
window.$toast = {
  success: (msg, opts) => add(msg, "success", typeof opts === "object" ? opts : {}),
  info: (msg, opts) => add(msg, "info", typeof opts === "object" ? opts : {}),
  error: (msg, errOrOpts) => {
    if (errOrOpts && (errOrOpts instanceof Error || typeof errOrOpts.message === "string")) {
      const e = errorFromValue(errOrOpts);
      add(msg, "error", { details: e.details, duration: 0 });
    } else if (errOrOpts && typeof errOrOpts === "object") {
      add(msg, "error", errOrOpts);
    } else {
      add(msg, "error", {});
    }
  },
};
</script>
