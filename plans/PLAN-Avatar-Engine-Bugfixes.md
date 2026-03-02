# Avatar Engine v1.1 — integrace bugfixů do Synapse

> Branch v avatar-engine: `fix/synapse-integration-bugs`
> Datum: 2026-02-24

## Přehled oprav

| # | Oprava | Problém v Synapse |
|---|--------|-------------------|
| 1 | **i18n koexistence** | Avatar překlady zmizí, protože Synapse volá `i18n.init()` po `initAvatarI18n()` a přepíše resources |
| 2 | **initialMode prop** | Po refreshi zůstane fullscreen uložený v localStorage — widget se otevře rovnou na celou obrazovku místo FAB |
| 3 | **Fullscreen pozadí** | Průhlednost fullscreen overlaye — prosvítá obsah pod ním |
| 4 | **createProviders()** | Testy běží s drahými modely (gemini-pro, claude-opus) — chybí snadný způsob přepnout na levnější |

---

## Krok 1: npm link

V avatar-engine (už hotovo):
```bash
cd ~/git/github/avatar-engine
npm run build
cd packages/core && npm link
cd ../react && npm link
```

V Synapse:
```bash
cd ~/git/github/synapse/apps/web
npm link @avatar-engine/core @avatar-engine/react
```

> **Ověření:** `ls -la node_modules/@avatar-engine/core` → symlink na avatar-engine repo

---

## Krok 2: Opravit i18n inicializaci

**Soubor:** `apps/web/src/i18n/index.ts`

Aktuální kód volá `initAvatarI18n()` **před** `i18n.init()`, takže Synapse init přepíše
avatar resources. Nová verze `initAvatarI18n` tohle řeší automaticky (re-inject po init),
ale je čistší volat ho **po** Synapse initu a předat plugin:

```typescript
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { initAvatarI18n } from '@avatar-engine/react'

import en from './locales/en.json'
import cs from './locales/cs.json'

const getSavedLanguage = (): string => {
  const saved = localStorage.getItem('synapse-language')
  if (saved && ['en', 'cs'].includes(saved)) return saved
  const browserLang = navigator.language.split('-')[0]
  return browserLang === 'cs' ? 'cs' : 'en'
}

// 1. Synapse init (hlavní resources)
i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    cs: { translation: cs },
  },
  lng: getSavedLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
})

// 2. Avatar i18n — injektne avatar překlady do existující instance
//    (safe i když se Synapse reinicializuje později)
initAvatarI18n([initReactI18next])
```

**Klíčová změna:** `initAvatarI18n()` se volá **po** `i18n.init()`, ne před ním.

---

## Krok 3: Přidat initialMode na AvatarWidget

**Soubor:** `apps/web/src/components/layout/Layout.tsx`

Přidat `initialMode="fab"` na `<AvatarWidget>`, aby se po refreshi vždy otevřel jako FAB
(ne fullscreen, i když byl naposledy fullscreen):

```diff
 <AvatarWidget
+  initialMode="fab"
   messages={chat.messages}
   sendMessage={sendWithContext}
   ...
```

> Tím se vyřeší bug kdy uživatel refreshne stránku ve fullscreenu
> a widget se otevře rovnou fullscreen bez možnosti vidět Synapse UI.

---

## Krok 4: Test providers (volitelné, pro integrační testy)

**Soubor:** `apps/web/src/components/avatar/AvatarProvider.tsx` (nebo testovací setup)

```typescript
import { createProviders } from '@avatar-engine/react'

// Pro testy — levnější modely
const testProviders = createProviders({
  gemini: { defaultModel: 'gemini-2.5-flash' },
  claude: { defaultModel: 'claude-haiku-4-5' },
})

// V AvatarWidget:
<AvatarWidget customProviders={testProviders} ... />
```

Pro produkci není potřeba — default PROVIDERS se použijí automaticky.

---

## Krok 5: Ověření

```bash
# 1. Dev server
cd ~/git/github/synapse/apps/web
npm run dev

# 2. Otevřít v prohlížeči — zkontrolovat:
#    - [ ] Widget se otevře jako FAB (ne fullscreen)
#    - [ ] Kliknout na FAB → compact → fullscreen — pozadí je černé, ne průhledné
#    - [ ] Přepnout jazyk cs/en — avatar texty se přeloží správně
#    - [ ] Otevřít DevTools console — žádné i18n warningy

# 3. Build check
npm run build
```

---

## Krok 6: Odpojit npm link, publish, update

Až bude vše otestované:

```bash
# 1. V avatar-engine — merge + tag
cd ~/git/github/avatar-engine
git checkout main && git merge fix/synapse-integration-bugs
git tag v1.1.0 && git push origin main --tags
# → CI publishne na npm

# 2. V Synapse — odpojit link, update z npm
cd ~/git/github/synapse/apps/web
npm unlink @avatar-engine/core @avatar-engine/react
npm install @avatar-engine/core@^1.1.0 @avatar-engine/react@^1.1.0
```
