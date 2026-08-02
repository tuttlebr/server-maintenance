<template>
  <BaseModal
    :visible="visible"
    :title="title"
    :danger="dangerMode"
    :danger-label="dangerLabel"
    :dismissible="false"
    size="sm"
    @cancel="cancel"
  >
    <p v-if="message" class="confirm-message">{{ message }}</p>
    <slot />

    <div v-if="requireText" class="confirm-typed">
      <label class="form-label" :for="typedInputId">
        Type <code>{{ requireText }}</code> to confirm
      </label>
      <input
        :id="typedInputId"
        ref="typedInput"
        v-model="typed"
        class="form-input"
        autocomplete="off"
        spellcheck="false"
        @keydown.enter.prevent="onTypedEnter"
      />
    </div>

    <template #actions>
      <button class="btn btn-ghost" type="button" data-cancel @click="cancel">Cancel</button>
      <button
        :class="['btn', dangerMode ? 'btn-danger' : 'btn-primary']"
        type="button"
        :disabled="!canConfirm"
        @click="confirm"
      >
        {{ confirmText }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import BaseModal from "./BaseModal.vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: "Confirm" },
  message: { type: String, default: "" },
  confirmText: { type: String, default: "Confirm" },
  dangerMode: { type: Boolean, default: false },
  dangerLabel: { type: String, default: "Destructive action" },
  // When set, user must type this string before the confirm button enables.
  requireText: { type: String, default: "" },
});

const emit = defineEmits(["confirm", "cancel"]);

const typed = ref("");
const typedInput = ref(null);
const typedInputId = `confirm-typed-${Math.random().toString(36).slice(2, 9)}`;

const canConfirm = computed(() => {
  if (!props.requireText) return true;
  return typed.value.trim() === props.requireText;
});

function confirm() {
  if (!canConfirm.value) return;
  emit("confirm");
}
function cancel() {
  emit("cancel");
}
function onTypedEnter() {
  if (canConfirm.value) confirm();
}

watch(
  () => props.visible,
  async (open) => {
    if (open) {
      typed.value = "";
      if (props.requireText) {
        await nextTick();
        typedInput.value?.focus();
      }
    }
  }
);
</script>

<style scoped>
.confirm-message {
  margin: 0 0 var(--space-sm) 0;
}

.confirm-typed {
  margin-top: var(--space-sm);
}

.confirm-typed code {
  font-family: var(--font-mono, "JetBrains Mono", "Courier New", monospace);
  background: var(--surface-lighter);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-danger, var(--nv-red));
}
</style>
