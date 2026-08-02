<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="visible"
        class="modal-overlay"
        :class="{ 'modal-overlay-danger': danger }"
        role="presentation"
        @click.self="onBackdrop"
      >
        <div
          ref="modalEl"
          class="modal"
          :class="[sizeClass, { 'modal-danger': danger }]"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
          @keydown.esc.stop="onEsc"
        >
          <div v-if="danger" class="modal-danger-strip" aria-hidden="true">
            <i class="fas fa-exclamation-triangle"></i>
            <span>{{ dangerLabel }}</span>
          </div>
          <div class="modal-body-inner">
            <header v-if="title || $slots.header" class="modal-header">
              <slot name="header">
                <h3 :id="titleId" class="modal-title">{{ title }}</h3>
              </slot>
              <button
                v-if="dismissible"
                class="modal-close"
                type="button"
                aria-label="Close dialog"
                @click="emit('cancel')"
              >
                <i class="fas fa-times" aria-hidden="true"></i>
              </button>
            </header>
            <div class="modal-content"><slot /></div>
            <footer v-if="$slots.actions" class="modal-actions"><slot name="actions" /></footer>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: "" },
  size: { type: String, default: "md" }, // sm | md | lg
  danger: { type: Boolean, default: false },
  dangerLabel: { type: String, default: "Destructive action" },
  dismissible: { type: Boolean, default: true },
  closeOnBackdrop: { type: Boolean, default: true },
  closeOnEsc: { type: Boolean, default: true },
});

const emit = defineEmits(["cancel"]);

const modalEl = ref(null);
const titleId = `modal-title-${Math.random().toString(36).slice(2, 9)}`;
const sizeClass = computed(() => `modal-${props.size}`);

let lastFocused = null;
let cleanupTrap = null;

function focusFirst() {
  if (!modalEl.value) return;
  const focusables = modalEl.value.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  // Prefer the cancel button if present; otherwise first focusable; otherwise modal itself.
  const cancelBtn = modalEl.value.querySelector("[data-cancel]");
  (cancelBtn || focusables[0] || modalEl.value).focus();
}

function trapTab(e) {
  if (e.key !== "Tab" || !modalEl.value) return;
  const focusables = Array.from(
    modalEl.value.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  );
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

function onBackdrop() {
  if (props.closeOnBackdrop) emit("cancel");
}
function onEsc() {
  if (props.closeOnEsc) emit("cancel");
}

watch(
  () => props.visible,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement;
      document.body.style.overflow = "hidden";
      await nextTick();
      focusFirst();
      modalEl.value?.addEventListener("keydown", trapTab);
      cleanupTrap = () => modalEl.value?.removeEventListener("keydown", trapTab);
    } else {
      document.body.style.overflow = "";
      cleanupTrap?.();
      cleanupTrap = null;
      if (lastFocused && typeof lastFocused.focus === "function") {
        lastFocused.focus();
      }
      lastFocused = null;
    }
  }
);
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-sm);
}

.modal {
  background-color: var(--surface-white);
  border-radius: 6px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
  width: 100%;
  max-width: 500px;
  outline: none;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 2 * var(--space-sm));
}

.modal-sm { max-width: 380px; }
.modal-md { max-width: 540px; }
.modal-lg { max-width: 760px; }

.modal-danger-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--color-danger, var(--nv-red));
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.modal-body-inner {
  padding: var(--space-md);
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.modal-title { margin: 0; }

.modal-close {
  appearance: none;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}
.modal-close:hover { background: rgba(0, 0, 0, 0.06); color: var(--text-on-light); }
.modal-close:focus-visible { outline: 2px solid var(--nv-green); outline-offset: 1px; }

.modal-content { font-size: 14px; line-height: 1.55; }

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-xs);
  margin-top: var(--space-md);
  flex-wrap: wrap;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.modal-fade-enter-active .modal,
.modal-fade-leave-active .modal {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to { opacity: 0; }
.modal-fade-enter-from .modal,
.modal-fade-leave-to .modal {
  transform: translateY(6px) scale(0.985);
  opacity: 0;
}
</style>
