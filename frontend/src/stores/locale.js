// Locale store — language selection, persisted in localStorage
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { STORAGE_KEY } from '../plugins/i18n.js'

export const SUPPORTED_LOCALES = [
  { code: 'en-US', label: 'English' },
  { code: 'de-DE', label: 'Deutsch' },
]

export const useLocaleStore = defineStore('locale', () => {
  const stored = localStorage.getItem(STORAGE_KEY)
  const locale = ref(stored || 'en-US')

  function setLocale(code, i18n) {
    locale.value = code
    localStorage.setItem(STORAGE_KEY, code)
    if (i18n) {
      i18n.global.locale.value = code
    }
  }

  return { locale, setLocale, SUPPORTED_LOCALES }
})
