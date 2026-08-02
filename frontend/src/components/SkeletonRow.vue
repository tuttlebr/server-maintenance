<template>
  <div class="skeleton-row" :style="{ gap: gap + 'px' }" aria-hidden="true">
    <span
      v-for="(w, i) in widths"
      :key="i"
      class="skel"
      :style="{ width: w, height: height + 'px' }"
    />
  </div>
</template>

<script setup>
defineProps({
  widths: { type: Array, default: () => ["120px", "60px", "180px", "60px"] },
  height: { type: Number, default: 14 },
  gap: { type: Number, default: 12 },
});
</script>

<style scoped>
.skeleton-row {
  display: flex;
  align-items: center;
  padding: 12px 15px;
}
</style>
