// i18n plugin — vue-i18n v9 (Composition API mode)
// Locale is persisted in localStorage via the locale store.
// To add a new language: add a JSON file in src/locales/ and import it here.

import { createI18n } from 'vue-i18n'
import en from '../locales/en-US.json'
import de from '../locales/de-DE.json'

const STORAGE_KEY = 'evenly-locale'

function detectLocale() {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && ['en-US', 'de-DE'].includes(stored)) return stored
  // Browser language detection
  const lang = navigator.language || 'en-US'
  if (lang.startsWith('de')) return 'de-DE'
  return 'en-US'
}

const i18n = createI18n({
  legacy: false,           // Composition API mode
  locale: detectLocale(),
  fallbackLocale: 'en-US',
  messages: {
    'en-US': en,
    'de-DE': de,
  },
})

export default i18n
export { STORAGE_KEY }
