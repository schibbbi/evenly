// Theme store — light/dark mode, persisted in localStorage
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'evenly-theme'

function detectSystemTheme() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useThemeStore = defineStore('theme', () => {
  // On first visit: no stored value → detect system preference
  const stored = localStorage.getItem(STORAGE_KEY)
  const initial = stored || detectSystemTheme()
  const theme = ref(initial)

  function setTheme(name, vuetifyTheme) {
    theme.value = name
    localStorage.setItem(STORAGE_KEY, name)
    if (vuetifyTheme) {
      vuetifyTheme.global.name.value = name
    }
  }

  function toggle(vuetifyTheme) {
    setTheme(theme.value === 'light' ? 'dark' : 'light', vuetifyTheme)
  }

  function applyToVuetify(vuetifyTheme) {
    vuetifyTheme.global.name.value = theme.value
  }

  return { theme, setTheme, toggle, applyToVuetify }
})
