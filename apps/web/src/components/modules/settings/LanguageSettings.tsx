/**
 * LanguageSettings
 *
 * Language selector for the Settings page.
 * Allows users to switch between available languages with immediate effect.
 *
 * Features:
 * - Radio-button style selection
 * - Shows native language names
 * - Immediate switching (no restart required)
 * - Persists to localStorage
 */

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Globe, Check } from 'lucide-react'
import { clsx } from 'clsx'
import { AVAILABLE_LANGUAGES, changeLanguage, getCurrentLanguage } from '@/i18n'

// Language flag/icon mapping (using emoji flags)
const LANGUAGE_FLAGS: Record<string, string> = {
  en: '🇬🇧',
  cs: '🇨🇿',
  de: '🇩🇪',
  fr: '🇫🇷',
  es: '🇪🇸',
  ja: '🇯🇵',
  zh: '🇨🇳',
  ko: '🇰🇷',
  ru: '🇷🇺',
  pl: '🇵🇱',
}

export function LanguageSettings() {
  const { t, i18n } = useTranslation()
  const [currentLang, setCurrentLang] = useState(getCurrentLanguage())

  // Sync with i18n state
  useEffect(() => {
    const handleLanguageChange = (lng: string) => {
      setCurrentLang(lng)
    }

    i18n.on('languageChanged', handleLanguageChange)
    return () => {
      i18n.off('languageChanged', handleLanguageChange)
    }
  }, [i18n])

  const handleLanguageSelect = (langCode: string) => {
    changeLanguage(langCode as 'en' | 'cs')
    setCurrentLang(langCode)
  }

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center gap-2 text-slate-400">
        <Globe className="w-4 h-4" />
        <span className="text-sm font-medium">{t('settings.language.title')} / Language</span>
      </div>

      {/* Language options */}
      <div className="space-y-2">
        {AVAILABLE_LANGUAGES.map((lang) => {
          const isSelected = currentLang === lang.code
          const flag = LANGUAGE_FLAGS[lang.code] || '🌐'

          return (
            <button
              key={lang.code}
              onClick={() => handleLanguageSelect(lang.code)}
              className={clsx(
                'w-full flex items-center justify-between p-3 rounded-lg',
                'transition-all duration-200',
                'border',
                isSelected
                  ? 'bg-indigo-500/20 border-indigo-500/50 shadow-lg shadow-indigo-500/10'
                  : 'bg-slate-800/30 border-slate-700/50 hover:bg-slate-800/50 hover:border-slate-600/50'
              )}
            >
              <div className="flex items-center gap-3">
                {/* Flag */}
                <span className="text-2xl" role="img" aria-label={lang.name}>
                  {flag}
                </span>

                {/* Language info */}
                <div className="text-left">
                  <span className={clsx(
                    'block font-medium',
                    isSelected ? 'text-indigo-300' : 'text-slate-100'
                  )}>
                    {lang.nativeName}
                  </span>
                  <span className="block text-xs text-slate-500">
                    {lang.name}
                  </span>
                </div>
              </div>

              {/* Checkmark for selected */}
              {isSelected && (
                <div className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500">
                  <Check className="w-4 h-4 text-white" />
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* Info text */}
      <p className="text-xs text-slate-500 mt-2">
        {t('settings.language.subtitle')}
      </p>
    </div>
  )
}

export default LanguageSettings
