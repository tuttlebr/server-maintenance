<template>
  <div id="fleet-app">
    <a v-if="showNav" href="#main-content" class="skip-link">Skip to main content</a>
    <NavBar v-if="showNav" />
    <main id="main-content" :class="{ 'page-content': showNav, container: showNav }" tabindex="-1">
      <router-view />
    </main>
    <ToastNotification />
    <HelpChat v-if="showNav" />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import NavBar from "./components/NavBar.vue";
import ToastNotification from "./components/ToastNotification.vue";
import HelpChat from "./components/HelpChat.vue";

const route = useRoute();
const showNav = computed(() => route.path !== "/login");
</script>
