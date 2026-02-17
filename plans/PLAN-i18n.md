# PLAN: Internationalization (i18n)

**Version:** v1.0.0
**Status:** ✅ DOKONČENO (2026-02-17)
**Created:** 2026-02-03
**Author:** raven2cz + Claude Opus 4.5
**Branch:** TBD

---

## Executive Summary

Synapse již má základní i18n infrastrukturu pomocí `react-i18next`. Existuje konfigurace, dva jazyky (EN/CS) a ~250 přeložených stringů. Tento plán dokončí implementaci:

- ✅ **Existuje:** i18n konfigurace, EN/CS překlady, changeLanguage API
- ✅ **Phase 1 HOTOVO:** Settings UI pro výběr jazyka
- ✅ **Phase 2 HOTOVO:** Kompletní pokrytí všech komponent (1325 EN klíčů, 1329 CS klíčů, 50+ komponent)
- ✅ **ProfilesPage:** Plně přeložena (hlavní stránka + dropdown)
- ~~❌ **Chybí:** TypeScript typování klíčů (Phase 3), dokumentace (Phase 4)~~ → ODLOŽENO (LOW priority, volitelné)

---

## Current State Analysis

### ✅ Co již máme

#### 1. i18n Konfigurace (`apps/web/src/i18n/index.ts`)

```typescript
// Plně funkční setup
- react-i18next integrace
- localStorage persistence ('synapse-language')
- Browser language detection (fallback to 'en')
- AVAILABLE_LANGUAGES constant
- changeLanguage() API
- getCurrentLanguage() API
```

#### 2. Překladové soubory

| Soubor | Klíčů | Pokrytí |
|--------|-------|---------|
| `locales/en.json` | 1325 | Kompletní pokrytí: pack detail, modals, plugins, shared, inventory, browse, settings, AI services, search, media, viewer, downloads, import, profiles, toasts |
| `locales/cs.json` | 1329 | Kompletní česká verze včetně pluralizace (+4 české _few formy) |

#### 3. Pluralizace

```json
// Czech pluralization (count_one, count_few, count_other)
"count_one": "{{count}} závislost",
"count_few": "{{count}} závislosti",
"count_other": "{{count}} závislostí"
```

### ❌ Co chybí

| Oblast | Stav | Priorita |
|--------|------|----------|
| Settings UI pro výběr jazyka | ✅ HOTOVO | HIGH |
| Pokrytí BrowsePage | ✅ HOTOVO | HIGH |
| Pokrytí InventoryPage | ✅ HOTOVO | HIGH |
| Pokrytí PackDetailPage + modals | ✅ HOTOVO (2026-02-17) | HIGH |
| Pokrytí Pack plugins + shared | ✅ HOTOVO (2026-02-17) | HIGH |
| Pokrytí Settings stránky | ✅ HOTOVO | MEDIUM |
| Pokrytí AI Services Settings | ✅ HOTOVO (2026-02-17) | MEDIUM |
| Pokrytí Header/Sidebar | ✅ HOTOVO | MEDIUM |
| Pokrytí Media/Viewer/Search | ✅ HOTOVO (2026-02-17) | MEDIUM |
| Pokrytí Downloads/Import | ✅ HOTOVO (2026-02-17) | MEDIUM |
| Pokrytí ProfilesPage | ✅ HOTOVO (stránka + dropdown plně přeloženy) | MEDIUM |
| PARAM_LABELS + CATEGORY_META | ✅ HOTOVO (2026-02-17) | MEDIUM |
| Toast notifikace | ✅ HOTOVO (2026-02-17) | MEDIUM |
| TypeScript typování klíčů | ❌ CHYBÍ | LOW |
| Dokumentace pro překlady | ❌ CHYBÍ | LOW |

---

## Architecture

### i18n Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Synapse i18n Architecture                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User Action                                                        │
│       │                                                              │
│       ▼                                                              │
│   ┌─────────────────┐     ┌─────────────────┐                       │
│   │ Settings Page   │────▶│ changeLanguage()│                       │
│   │ Language Select │     │ (i18n/index.ts) │                       │
│   └─────────────────┘     └────────┬────────┘                       │
│                                    │                                 │
│                    ┌───────────────┼───────────────┐                │
│                    ▼               ▼               ▼                │
│             ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│             │localStorage│   │ i18next  │    │ React    │           │
│             │  persist  │   │ instance │    │ re-render│           │
│             └──────────┘    └──────────┘    └──────────┘           │
│                                                                      │
│   On App Load:                                                       │
│   1. Check localStorage('synapse-language')                          │
│   2. If empty → detect browser language                              │
│   3. If not supported → fallback to 'en'                            │
│   4. Initialize i18next with detected language                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### File Structure

```
apps/web/src/
├── i18n/
│   ├── index.ts              # ✅ Main config (EXISTS)
│   ├── types.ts              # 🆕 TypeScript types for keys
│   └── locales/
│       ├── en.json           # ✅ English (EXISTS)
│       ├── cs.json           # ✅ Czech (EXISTS)
│       ├── de.json           # 🔮 Future: German
│       └── ...               # 🔮 Future: More languages
│
├── components/
│   └── settings/
│       └── LanguageSettings.tsx  # 🆕 Language selector UI
```

---

## Design Principles

### 1. Developer Experience

```typescript
// ✅ GOOD - Simple, clean API
const { t } = useTranslation()
return <h1>{t('pack.header.title', { name: pack.name })}</h1>

// ❌ BAD - Hardcoded strings
return <h1>{pack.name}</h1>

// ✅ GOOD - Structured keys with namespaces
t('pack.dependencies.status.installed')
t('common.save')
t('errors.networkError')

// ❌ BAD - Flat, unclear keys
t('installed')
t('save_btn')
```

### 2. Translation File Structure

```json
{
  "namespace": {
    "section": {
      "key": "value",
      "nested": {
        "deepKey": "value"
      }
    }
  }
}
```

**Namespaces:**
- `pack` - Pack detail page
- `packs` - Packs list page
- `browse` - Browse Civitai page
- `inventory` - Model Inventory page
- `profiles` - Profiles page
- `settings` - Settings page
- `common` - Shared strings (Save, Cancel, etc.)
- `nav` - Navigation (Sidebar, Header)
- `errors` - Error messages
- `toasts` - Toast notifications

### 3. Interpolation & Pluralization

```json
// Interpolation
"greeting": "Hello, {{name}}!"

// English pluralization
"count": "{{count}} items",
"count_one": "{{count}} item",
"count_other": "{{count}} items"

// Czech pluralization (more complex)
"count_one": "{{count}} položka",     // 1
"count_few": "{{count}} položky",     // 2-4
"count_other": "{{count}} položek"    // 5+
```

### 4. Dynamic Switching (No Restart)

```typescript
// Language změna je OKAMŽITÁ - žádný restart
changeLanguage('cs')  // Všechny komponenty se překreslí

// React automaticky re-renderuje díky i18next bindingu
```

---

## Implementation Phases

### Phase 1: Settings UI for Language Selection ✅ HOTOVO

**Files:**
- `apps/web/src/components/modules/settings/LanguageSettings.tsx` ✅
- `apps/web/src/components/modules/SettingsPage.tsx` (integrated) ✅

**UI Design:**

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚙️ Settings                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🌐 Language / Jazyk                                            │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 🇬🇧 English                                          [✓] │ │
│  │    Interface will be displayed in English                 │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 🇨🇿 Čeština                                           [ ] │ │
│  │    Rozhraní bude zobrazeno v češtině                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ℹ️ Changes take effect immediately without restart.           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Tasks:**
- [x] Create `LanguageSettings.tsx` component
- [x] Integrate into SettingsPage Display section
- [x] Add flag icons (emoji flags)
- [x] Add settings translations (en.json, cs.json)
- [x] Test build passes

### Phase 2: Complete Translation Coverage ✅ HOTOVO (2026-02-17)

**Rozsah:** 1325 EN klíčů, 1329 CS klíčů, 50+ komponent přeloženo

1. **HIGH - User-facing pages** ✅ HOTOVO
   - [x] BrowsePage.tsx + components (~45 klíčů)
   - [x] InventoryPage.tsx + InventoryStats.tsx + InventoryFilters.tsx (~90 klíčů)
   - [x] ImportWizardModal.tsx (~35 klíčů)
   - [x] PackDetailPage.tsx + všechny sekce (header, info, parameters, workflows, storage, gallery, dependencies)
   - [x] Pack modals (7 souborů: DescriptionEditor, EditDependencies, EditPack, EditParameters, EditPreviews, UploadWorkflow, BaseModelResolver, CreatePack)
   - [x] Pack plugins (CivitaiPlugin, CustomPlugin, InstallPlugin)
   - [x] Pack shared (EditableTags, EditableText, ErrorBoundary, UnsavedChangesDialog, EmptyState)
   - [x] DownloadsPage.tsx, GenerationDataPanel.tsx, FullscreenMediaViewer.tsx
   - [x] SearchFilters.tsx (filter labels, sort/period defaults)
   - [x] MediaPreview.tsx, ImagePreview.tsx, VideoPlayer.tsx, ModelCard.tsx

2. **MEDIUM - Settings & Profiles** ✅ HOTOVO
   - [x] SettingsPage.tsx (settings.* namespace)
   - [x] AIServicesSettings.tsx + AdvancedAISettings.tsx + ProviderCard.tsx + TaskPriorityConfig.tsx
   - [x] ProfileDropdown.tsx
   - [x] PullConfirmDialog.tsx, PushConfirmDialog.tsx
   - [x] ProfilesPage.tsx hlavní stránka (profiles.* namespace - title, subtitle, activeProfiles, stack, shadowed, toast, table, error)

3. **LOW - Navigation & Layout** ✅ HOTOVO
   - [x] Header.tsx (header.* namespace)
   - [x] Sidebar.tsx (sidebar.*, nav.* namespace)

4. **TECHNICAL - Parameter labels & Categories** ✅ HOTOVO (2026-02-17)
   - [x] 56 parameter labels (`pack.parameters.labels.*`)
   - [x] 7 edit-specific labels (`pack.parameters.editLabels.*`)
   - [x] 13 category labels (`pack.parameters.categories.*`)
   - [x] PackParametersSection.tsx - PARAM_LABELS → t() s dynamickým lookup
   - [x] EditParametersModal.tsx - PARAM_DEFINITIONS → labelKey pattern + getParamLabel()
   - [x] CATEGORY_META v obou souborech → labelKey pattern

5. **EDGE CASES** ✅ HOTOVO (2026-02-17)
   - [x] Toast notifikace v AIServicesSettings (8 zpráv)
   - [x] title atributy (Mute/Unmute, Edit pack name, Refresh preview)
   - [x] EmptyState preset configs (titleKey/descriptionKey/actionKey pattern)
   - [x] FILTER_TYPE_CONFIGS v SearchFilters (labelKey pattern)
   - [x] PACK_TYPES v CreatePackModal → inventory.assetKind
   - [x] Quality badge v FullscreenMediaViewer → viewer.quality* keys

**Verify:** TypeScript kompilace čistá, Vite build prošel, klíče 100% synchronizované

### Phase 3: TypeScript Type Safety (Optional)

```typescript
// apps/web/src/i18n/types.ts

// Auto-generate from en.json structure
type TranslationKeys =
  | 'pack.header.title'
  | 'pack.header.version'
  | 'pack.actions.edit'
  // ... etc

// Typed useTranslation hook
declare module 'react-i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: {
      translation: typeof import('./locales/en.json')
    }
  }
}
```

**Benefits:**
- Autocomplete for translation keys
- Compile-time error for missing keys
- Refactoring support

### Phase 4: Documentation & Guidelines

Create `docs/i18n-guide.md`:

- How to add new translations
- Naming conventions
- Pluralization rules
- Testing translations
- Adding new languages

---

## Adding New Language (Future)

### Steps to add German (de):

1. **Create translation file:**
   ```bash
   cp apps/web/src/i18n/locales/en.json apps/web/src/i18n/locales/de.json
   ```

2. **Translate strings** (or use automated tools)

3. **Register in config:**
   ```typescript
   // i18n/index.ts
   import de from './locales/de.json'

   resources: {
     en: { translation: en },
     cs: { translation: cs },
     de: { translation: de },  // Add
   }

   // Update AVAILABLE_LANGUAGES
   export const AVAILABLE_LANGUAGES = [
     { code: 'en', name: 'English', nativeName: 'English' },
     { code: 'cs', name: 'Czech', nativeName: 'Čeština' },
     { code: 'de', name: 'German', nativeName: 'Deutsch' },  // Add
   ] as const
   ```

4. **Update language detection:**
   ```typescript
   const getSavedLanguage = (): string => {
     // ...
     return ['en', 'cs', 'de'].includes(browserLang) ? browserLang : 'en'
   }
   ```

5. **Test thoroughly**

---

## Best Practices for Developers

### DO ✅

```typescript
// Use translation hook
const { t } = useTranslation()

// Use structured keys
t('pack.actions.save')

// Pass interpolation values
t('pack.header.version', { version: '1.0.0' })

// Use pluralization
t('pack.dependencies.count', { count: 5 })

// Fallback for dynamic content (user-generated)
const title = pack.customTitle || t('pack.header.defaultTitle')
```

### DON'T ❌

```typescript
// Don't hardcode UI strings
<button>Save</button>  // ❌

// Don't use string concatenation
t('hello') + ' ' + t('world')  // ❌

// Don't forget pluralization for countable items
`${count} items`  // ❌

// Don't translate user-generated content
t(pack.description)  // ❌ - description is from user, not UI
```

### When NOT to translate

- User-generated content (descriptions, names)
- Technical terms that shouldn't be localized (API, JSON, etc.)
- Brand names (Civitai, ComfyUI, etc.)
- File paths and URLs

---

## Testing Checklist

### Manual Testing

- [ ] Switch language in Settings → all visible UI updates immediately
- [ ] Refresh page → language persists
- [ ] Clear localStorage → browser detection works
- [ ] All pages render without missing translation warnings
- [ ] Pluralization works correctly (1 item, 2 items, 5 items)
- [ ] Interpolation works ({name}, {count}, etc.)

### Automated Testing (Optional)

```typescript
// Check for missing translations
test('all EN keys exist in CS', () => {
  const enKeys = getAllKeys(enJson)
  const csKeys = getAllKeys(csJson)
  expect(csKeys).toEqual(expect.arrayContaining(enKeys))
})
```

---

## Open Questions

| Question | Status |
|----------|--------|
| Should we use flag icons or text-only selector? | Open - text+flag |
| RTL language support needed? | No - not planned |
| Professional translation service? | No - community translations |
| Automated key extraction from code? | Open - could use i18next-parser |

---

## Related Plans

- **PLAN-AI-Services.md** - AI features will need translations
- **PLAN-Dependencies.md** - New UI will need translations
- **PLAN-Install-Packs.md** - Script UI will need translations

---

*Created: 2026-02-03*
*Last Updated: 2026-02-17*
*Status: ✅ DOKONČENO*

---

## Changelog

### 2026-02-17 - PLAN CLOSED ✅
- ✅ ProfilesPage.tsx ověřena jako plně přeložená (profiles.* namespace: 28 klíčů EN, 30 klíčů CS s pluralizací)
- ✅ Všechny komponenty kompletně přeloženy, žádné hardcoded stringy
- ✅ Phase 3 (TypeScript types) a Phase 4 (docs) odloženy jako volitelné LOW priority
- ✅ **PLÁN UZAVŘEN** - i18n implementace kompletní

### 2026-02-17 - Phase 2 Final: Complete Translation Coverage
- ✅ **1325 EN klíčů, 1329 CS klíčů** (z původních ~250)
- ✅ **50+ komponent** přeloženo pomocí useTranslation/t()
- ✅ Pack detail: header, info, parameters, workflows, storage, gallery, dependencies
- ✅ Pack modals: 8 souborů (Description, Dependencies, Pack, Parameters, Previews, Workflow, BaseModel, Create)
- ✅ Pack plugins: Civitai, Custom, Install (včetně getter pattern pro plugin names)
- ✅ Pack shared: EditableTags, EditableText, ErrorBoundary (class component pattern), UnsavedChangesDialog, EmptyState
- ✅ Media: MediaPreview, ImagePreview, VideoPlayer, ModelCard, FullscreenMediaViewer (quality badges)
- ✅ Downloads, Import, Search, GenerationData
- ✅ AI Services: Settings + toast notifikace, AdvancedSettings, ProviderCard, TaskPriorityConfig
- ✅ Profiles: ProfileDropdown, PullConfirmDialog, PushConfirmDialog
- ✅ Technical: 56 parameter labels, 13 category labels, filter type configs
- ✅ Patterns použité: useTranslation hook, import i18n + getter pattern (plugins), labelKey pattern (constants), dynamic keys (t(`namespace.${variable}`))
- ✅ TypeScript čistý, Vite build prošel

### 2026-02-03 - Phase 2 Complete
- ✅ Translated SettingsPage.tsx - all sections (display, paths, store, backup, tokens, diagnostics)
- ✅ Added missing `settings.*` keys (gitHint, usedSize, freeSpace, placeholders, init messages)
- ✅ Translated Header.tsx - tagline, NSFW toggle
- ✅ Translated Sidebar.tsx - navigation labels, status messages, toggle button titles
- ✅ Added `header.*` namespace (~2 keys)
- ✅ Added `sidebar.*` namespace (~4 keys)
- ✅ Updated `nav.*` with downloads key
- ✅ All builds pass successfully

### 2026-02-03 - Phase 2 Partial Complete
- ✅ Translated BrowsePage.tsx - title, subtitle, zoom, search, loading, modal sections, stats, toasts
- ✅ Added `browse.*` namespace (~45 klíčů) to en.json and cs.json
- ✅ Translated InventoryPage.tsx - header, loading, errors, toasts
- ✅ Translated InventoryStats.tsx - local storage, blob status, quick actions, backup card, sync buttons
- ✅ Translated InventoryFilters.tsx - search, dropdowns, filter chips
- ✅ Added `inventory.*` namespace (~90 klíčů) to en.json and cs.json
- ✅ Translated ImportWizardModal.tsx - sections, options, summary, buttons
- ✅ Added `import.*` namespace (~35 klíčů) to en.json and cs.json
- ✅ All builds pass successfully

### 2026-02-03 - Phase 1 Complete
- ✅ Created `LanguageSettings.tsx` component with emoji flags
- ✅ Integrated into SettingsPage Display section
- ✅ Added `settings.*` translations to en.json and cs.json
- ✅ Component uses translations for dynamic text
- ✅ Build passes successfully
