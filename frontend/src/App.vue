<template>
  <v-app :theme="themeStore.theme">
    <!-- Global snackbar for error messages -->
    <v-snackbar
      v-model="showError"
      color="error"
      location="top"
      :timeout="4000"
    >
      {{ errorMessage }}
      <template #actions>
        <v-btn variant="text" @click="showError = false">{{ $t('common.dismiss') }}</v-btn>
      </template>
    </v-snackbar>

    <router-view v-slot="{ Component, route }">
      <transition name="fade" mode="out-in">
        <component :is="Component" :key="route.name" />
      </transition>
    </router-view>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useThemeStore } from './stores/theme.js'
import { useTheme } from 'vuetify'

const themeStore = useThemeStore()
const vuetifyTheme = useTheme()

const showError = ref(false)
const errorMessage = ref('')

onMounted(() => {
  // Apply persisted theme
  themeStore.applyToVuetify(vuetifyTheme)

  // Global error event listener for API errors surfaced from child components
  window.addEventListener('evenly:error', (e) => {
    errorMessage.value = e.detail
    showError.value = true
  })
})
</script>

<style>
/* Mobile-first: max content width on desktop */
.hk-container {
  max-width: 480px;
  margin: 0 auto;
  width: 100%;
}

/* Route transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Global overrides — no raw hex values, using Vuetify tokens */
body {
  overscroll-behavior: none;
}

/* Ensure bottom nav doesn't overlap content */
.hk-page {
  padding-bottom: 80px;
}
</style>
