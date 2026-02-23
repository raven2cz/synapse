/**
 * i18n Configuration
 *
 * Internationalization setup using react-i18next.
 * Supports English and Czech languages.
 *
 * Usage in components:
 * ```tsx
 * import { useTranslation } from 'react-i18next'
 *
 * function MyComponent() {
 *   const { t } = useTranslation()
 *   return <h1>{t('pack.header.title')}</h1>
 * }
 * ```
 */

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { initAvatarI18n } from '@avatar-engine/core'

import en from './locales/en.json'
import cs from './locales/cs.json'

// Initialize avatar-engine's own i18n (standalone, has en+cs built-in)
initAvatarI18n()

// Get saved language from localStorage or use browser default
const getSavedLanguage = (): string => {
  const saved = localStorage.getItem('synapse-language')
  if (saved && ['en', 'cs'].includes(saved)) {
    return saved
  }
  // Try to detect browser language
  const browserLang = navigator.language.split('-')[0]
  return browserLang === 'cs' ? 'cs' : 'en'
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    cs: { translation: cs },
  },
  lng: getSavedLanguage(),
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false, // React already escapes
  },
  // Disable suspense mode for simpler integration
  react: {
    useSuspense: false,
  },
})

/**
 * Change the current language and save to localStorage
 */
export const changeLanguage = (lang: 'en' | 'cs') => {
  localStorage.setItem('synapse-language', lang)
  i18n.changeLanguage(lang)
}

/**
 * Get the current language
 */
export const getCurrentLanguage = (): string => {
  return i18n.language
}

/**
 * Available languages
 */
export const AVAILABLE_LANGUAGES = [
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'cs', name: 'Czech', nativeName: 'Čeština' },
] as const

export default i18n
