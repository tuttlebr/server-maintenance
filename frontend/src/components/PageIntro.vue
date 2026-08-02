<template>
  <p class="page-intro"><slot /></p>
</template>

<style scoped>
.page-intro {
  margin: calc(-1 * var(--space-sm)) 0 var(--space-md);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  max-width: 720px;
}
</style>
