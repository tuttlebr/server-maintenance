<template>
  <div id="fleet-app">
    <a v-if="showNav" href="#main-content" class="skip-link" @click.prevent="skipToMain">Skip to main content</a>
    <NavBar v-if="showNav" />
    <main ref="mainContent" id="main-content" :class="{ 'page-content': showNav, container: showNav }" tabindex="-1">
      <router-view />
    </main>
    <ToastNotification />
    <HelpChat v-if="showNav" />
  </div>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import NavBar from "./components/NavBar.vue";
import ToastNotification from "./components/ToastNotification.vue";
import HelpChat from "./components/HelpChat.vue";
import { isAuthenticated } from "./api.js";
import { useDevicesStore } from "./stores/devices.js";

const route = useRoute();
const showNav = computed(() => route.path !== "/login");
const mainContent = ref(null);
function skipToMain() { mainContent.value?.focus(); }
const store = useDevicesStore();
watch(showNav, visible => visible && isAuthenticated() ? store.start() : store.stop(), { immediate: true });
onUnmounted(() => store.stop());
</script>
