<template>
  <span class="info-tip" :class="[`info-tip-${placement}`, `info-tip-${size}`]">
    <button
      type="button"
      class="info-tip-trigger"
      :aria-label="ariaLabel"
      :aria-describedby="tipId"
      @click.stop="onClick"
      @keydown.escape="open = false"
      @blur="open = false"
    >
      <i class="fas fa-circle-info" aria-hidden="true"></i>
    </button>
    <span
      :id="tipId"
      class="info-tip-bubble"
      role="tooltip"
      :class="{ 'info-tip-open': open }"
    ><slot>{{ text }}</slot></span>
  </span>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  text: { type: String, default: "" },
  placement: { type: String, default: "top" },
  size: { type: String, default: "sm" },
  label: { type: String, default: "More information" },
});

const open = ref(false);
const uid = Math.random().toString(36).slice(2, 9);
const tipId = computed(() => `tip-${uid}`);
const ariaLabel = computed(() => props.label);

function onClick() {
  open.value = !open.value;
}
</script>

<style scoped>
.info-tip {
  position: relative;
  display: inline-flex;
  align-items: center;
  vertical-align: baseline;
  margin-left: 4px;
}

.info-tip-trigger {
  appearance: none;
  background: transparent;
  border: none;
  padding: 0;
  margin: 0;
  cursor: help;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  border-radius: 50%;
  transition: color var(--transition-standard);
}
.info-tip-sm .info-tip-trigger { font-size: 12px; width: 14px; height: 14px; }
.info-tip-md .info-tip-trigger { font-size: 14px; width: 16px; height: 16px; }

.info-tip-trigger:hover,
.info-tip-trigger:focus-visible {
  color: var(--color-info);
  outline: none;
}
.info-tip-trigger:focus-visible {
  box-shadow: var(--shadow-focus);
}

.info-tip-bubble {
  position: absolute;
  z-index: 300;
  width: max-content;
  max-width: 260px;
  padding: 8px 10px;
  background: var(--surface-dark);
  color: var(--text-on-dark);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.45;
  letter-spacing: 0;
  text-transform: none;
  text-align: left;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-dropdown);
  pointer-events: none;
  opacity: 0;
  transform: translateY(2px);
  transition: opacity 0.12s ease-out, transform 0.12s ease-out;
  white-space: normal;
}

.info-tip:hover .info-tip-bubble,
.info-tip-trigger:focus-visible + .info-tip-bubble,
.info-tip-bubble.info-tip-open {
  opacity: 1;
  transform: translateY(0);
}

/* Placement variants */
.info-tip-top .info-tip-bubble {
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translate(-50%, 2px);
}
.info-tip-top:hover .info-tip-bubble,
.info-tip-top .info-tip-trigger:focus-visible + .info-tip-bubble,
.info-tip-top .info-tip-bubble.info-tip-open {
  transform: translate(-50%, 0);
}

.info-tip-bottom .info-tip-bubble {
  top: calc(100% + 6px);
  left: 50%;
  transform: translate(-50%, -2px);
}
.info-tip-bottom:hover .info-tip-bubble,
.info-tip-bottom .info-tip-trigger:focus-visible + .info-tip-bubble,
.info-tip-bottom .info-tip-bubble.info-tip-open {
  transform: translate(-50%, 0);
}

.info-tip-right .info-tip-bubble {
  left: calc(100% + 6px);
  top: 50%;
  transform: translate(2px, -50%);
}
.info-tip-right:hover .info-tip-bubble,
.info-tip-right .info-tip-trigger:focus-visible + .info-tip-bubble,
.info-tip-right .info-tip-bubble.info-tip-open {
  transform: translate(0, -50%);
}

/* Mobile: bubbles can be wide and may overflow; constrain and anchor */
@media (max-width: 600px) {
  .info-tip-bubble { max-width: min(240px, calc(100vw - 32px)); }
}
</style>
