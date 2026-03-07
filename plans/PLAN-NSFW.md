# PLAN: Globalni NSFW Filtr

**Stav:** IMPLEMENTOVANO ✅ (v6.1.0 — opravy z review)
**Vytvoreno:** 2026-03-04
**Verze:** 6.1.0
**Posledni aktualizace:** 2026-03-06

---

## Prehled

Viceurobnovy NSFW filtracni system s tremi rezimy a maxLevel stropem.

**Komponenty:**
- `NsfwFilterMode`: `show` | `blur` | `hide`
- `NsfwMaxLevel`: `pg` | `pg13` | `r` | `x` | `all` (mapuje se na Civitai browsing level bitmasku)

**Civitai nsfwLevel bitmaska:**
```
PG=1, PG-13=2, R=4, X=8, Blocked=16
Kumulativni kombinace: pg=1, pg13=3, r=7, x=15, all=31
```

---

## Klicova design pravidla

1. **Hide je KONFIGURACNI rezim** — nastavuje se POUZE v Settings, NIKDY dynamicky
2. **Zadne `return null` v komponentach** — filtrace NSFW obsahu se deje na DATOVE urovni (parent useMemo filtr), ne v jednotlivych komponentach
3. **Zadne zmeny API dotazu** — `getBrowsingLevel()` se nemeni podle filterMode, API vzdy vraci data podle maxLevel
4. **Header toggle je show ↔ blur** — v hide modu tlacitko zmizi, zadny 3-stavovy cyklus
5. **maxLevel je hard cutoff** — obsah NAD touto uroven je zcela skryty (ne rozmazany)

---

## Architektura filtrace

```
Settings UI (filterMode + maxLevel)
    ↓
nsfwStore (Zustand + persist + cross-tab sync)
    ↓
┌─────────────────────────────────────────────────┐
│ DATOVA UROVEN (parent komponenty)               │
│                                                 │
│ Pouziva shouldHide() — resi VSECHNY pripady:    │
│   filterMode=hide + isNsfw → skryto             │
│   filterMode=show/blur + exceedsMaxLevel → skryto│
│                                                 │
│ BrowsePage:                                     │
│   visibleModels = allModels.filter(!shouldHide) │
│   detail previews = previews.filter(!shouldHide)│
│   fullscreen = filtrovane previews/community    │
│                                                 │
│ CommunityGalleryPanel:                          │
│   visibleImages = images.filter(!shouldHide)    │
│   onImagesChange(visibleImages) ← filtrovane    │
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ KOMPONENTOVA UROVEN (beze zmen oproti main)     │
│                                                 │
│ MediaPreview, ModelCard, ImagePreview:           │
│   pouzivaji useSettingsStore.nsfwBlurEnabled     │
│   nsfwBlurEnabled = filterMode !== 'show'       │
│   → v hide modu: nsfwBlurEnabled=true → blur    │
│   → v blur modu: nsfwBlurEnabled=true → blur    │
│   → v show modu: nsfwBlurEnabled=false → nic    │
│   (fallback blur pokud NSFW model projde filtrem)│
│                                                 │
│ FullscreenMediaViewer:                          │
│   beze zmen oproti main, pouziva nsfwBlurEnabled│
└─────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────┐
│ HEADER                                          │
│                                                 │
│ filterMode=hide → tlacitko NEVIDITELNE          │
│ filterMode=show/blur → puvodni ON/OFF toggle    │
│   (show ↔ blur, slider styl z main)             │
└─────────────────────────────────────────────────┘
```

---

## Faze 1: Store + Zpetna kompatibilita (HOTOVO ✅)

**Soubory:**
- `apps/web/src/stores/nsfwStore.ts` — Zustand store s persist
- `apps/web/src/stores/settingsStore.ts` — deleguje na nsfwStore

**Implementace:**
- `useNsfwStore` s `filterMode`, `maxLevel`, `getBrowsingLevel()`, `shouldBlur()`, `shouldHide()`
- Persistence klic: `synapse-nsfw-settings`
- Auto-migrace z legacy `synapse-settings.nsfwBlurEnabled`
- `settingsStore.nsfwBlurEnabled` getter/setter deleguje na `nsfwStore`
- Subscribe sync: zmeny v nsfwStore se propaguji do settingsStore

---

## Faze 2: Upgrade Store — Granularita urovni + Cross-Tab Sync (HOTOVO ✅)

**Soubor:** `apps/web/src/stores/nsfwStore.ts`

**Zmeny:**
- `shouldBlur(nsfwLevel: number | boolean)` — upgrade z boolean na number | boolean
- `shouldHide(nsfwLevel: number | boolean)` — upgrade z boolean na number | boolean
- `normalizeLevel()` helper — boolean→{isNsfw, level}, fail-closed pro malformed
- `exceedsMaxLevel()` helper — bitmask check `(itemLevel & ~safeBitmask) !== 0`
- `UNKNOWN_NSFW_LEVEL = -1` sentinel pro legacy boolean=true
- ~~`getBrowsingLevel()` vraci 1 v hide rezimu~~ → **OPRAVENO v6.0**: vraci vzdy `LEVEL_BITMASK[maxLevel]` bez ohledu na filterMode (API se nemeni)
- Cross-tab sync pres `storage` event listener
- Validace filterMode/maxLevel v cross-tab sync + Zustand merge guard

**Testy:** `nsfw-store.test.ts` — 54 testu

---

## Faze 3: Settings UI (HOTOVO ✅)

**Soubor:** `apps/web/src/components/modules/SettingsPage.tsx`

**Zmeny:**
- 3-rezimovy SegmentedControl pro `filterMode` (show/blur/hide)
- maxLevel dropdown (PG/PG-13/R/X/All) — skryty v hide rezimu
- Popis maxLevel: "Content above this level is completely hidden" (hard cutoff, ne blur)
- Nativni `<select>` nahrazeny za `<ThemedSelect>` (sdilena UI komponenta)
- i18n klice: `settings.display.nsfwMode.*`, `settings.display.nsfwLevel.*`

**Testy:** `nsfw-settings-ui.test.ts` — 25 testu

---

## ~~Faze 4: Komponenty — useNsfwFilter Hook v komponentach~~ → ZRUSENO

**Puvodni plan:** useNsfwFilter hook + `isHidden→return null` v MediaPreview/ModelCard/ImagePreview + visibleItems v FullscreenMediaViewer

**Duvod zruseni:** Komponenty NESMI filtrovat obsah — filtrace patri na datovou uroven (parent useMemo). Komponenty zustavaji na main verzi s `useSettingsStore.nsfwBlurEnabled`. Hook `useNsfwFilter` existuje v `src/hooks/useNsfwFilter.ts` ale komponenty ho NEPOUZIVAJI.

**Co zustalo z puvodni faze 4:**
- `useNsfwFilter.ts` hook — existuje, ale neni pouzivany v komponentach (k dispozici pro budouci pouziti)

**Co bylo REVERTOVANO na main:**
- `MediaPreview.tsx` — zadne zmeny oproti main
- `ModelCard.tsx` — zadne zmeny oproti main
- `ImagePreview.tsx` — zadne zmeny oproti main
- `FullscreenMediaViewer.tsx` — zadne zmeny oproti main

---

## ~~Faze 5: BrowsePage + Bridge browsingLevel~~ → ZRUSENO (API zmeny)

**Puvodni plan:** browsingLevel v API dotazech, nsfwLevel propagace v transformerech, bridge filtr

**Duvod zruseni:** Zmena API dotazu rozbilda nacitani modelu. NSFW filtrace se dela client-side, ne API-side.

**Co bylo REVERTOVANO na main:**
- `BrowsePage.tsx` — browsingLevel v queryKey/search params ODEBRAN
- `trpcBridgeAdapter.ts` — browsingLevel passthrough ODEBRAN
- `civitaiTransformers.ts` — zadne zmeny oproti main
- `synapse-civitai-bridge.user.js` — zadne zmeny oproti main

**Co zustalo:**
- `searchTypes.ts` — `nsfwLevel?: number` v ModelPreview a CivitaiModel (typ plumbing, beze zmeny chovani)

---

## Faze 5 (NOVA): Client-side filtrace (HOTOVO ✅ — v6.1 upgrade na shouldHide)

**Soubory:**
- `apps/web/src/components/modules/BrowsePage.tsx` — client-side useMemo filtr
- `apps/web/src/components/ui/CommunityGalleryPanel.tsx` — client-side useMemo filtr

**~~Puvodni zmeny (v6.0):~~**
- ~~`filterMode === 'hide' ? filter : passthrough`~~ — NAHRAZENO v6.1

**Aktualni zmeny (v6.1 — shouldHide):**
- **BrowsePage:**
  - `visibleModels = allModels.filter(m => !shouldHide(m.nsfw) && !shouldHide(m.previews[0]?.nsfw ?? false))`
  - Detail panel: `modelDetail.previews.filter(p => !shouldHide(p.nsfw))`
  - Fullscreen viewer: `visiblePreviews` misto `modelDetail.previews`
  - Grid renderuje `visibleModels` misto `allModels`
  - Paginace/load more zustava na `allModels` (data loading se nemeni)
  - API dotazy BEZE ZMEN (includeNsfw=true jako na main)
- **CommunityGalleryPanel:**
  - `visibleImages = images.filter(img => !shouldHide(img.nsfw))`
  - `onImagesChange(visibleImages)` — predava uz filtrovane do parent
  - Grid renderuje `visibleImages` s indexem v filtrovanem seznamu

---

## Faze 6: Header prepinac (HOTOVO ✅ — REDESIGN v6.0)

**Soubor:** `apps/web/src/components/layout/Header.tsx`

**~~Puvodni implementace (v5.0):~~**
- ~~3-stavovy cyklus: show → blur → hide → show~~
- ~~NEXT_MODE, MODE_STYLES, MODE_ICONS, MODE_LABELS const mapy~~
- ~~Ban ikona pro hide rezim~~

**Aktualni implementace (v6.0):**
- `useNsfwStore` misto `useSettingsStore`
- `filterMode !== 'hide'` → tlacitko je NEVIDITELNE v hide modu
- `show ↔ blur` toggle — puvodni ON/OFF slider styl z main (indigo/red barvy, EyeOff/Eye ikony)
- Zadny 3-stavovy cyklus, zadna Ban ikona
- i18n: pouze `header.nsfw` klic (smazany nsfwShow/Blur/Hide/Aria/Announce klice)

**Testy:** `nsfw-header-cycle.test.ts` — 8 testu (toggle show↔blur, hide mode behavior, edge cases)

---

## ~~Faze PacksPage~~ — VYRAZENO

Packy pouzivaji user-driven system (flagy `is_nsfw`, `nsfw-pack-hide` tag).
Uzivatel sam rozhoduje co je NSFW a co skryt — globalni filtr nedava smysl.

**PacksPage (seznam):** Filtrace dle user-driven flags, globalni NSFW filtr se neaplikuje.
**PackDetail (galerie):** NSFW previews se pouze BLURRUJI (nsfwBlurEnabled), NIKDY se neschovavaji.
Duvod: Uzivatel si pack sam stahnul vedome — hide jeho vlastniho obsahu by bylo matouci.
Pokud NSFW preview nechce, muze ho smazat pres Edit v PackGallery.

---

## Poradi implementace

```
Faze 1 (Store zaklad)            ✅
    |
Faze 2 (Upgrade Store)           ✅ granularita urovni, cross-tab sync
    |
Faze 3 (Settings UI)             ✅ 3-rezimovy prepinac, maxLevel, ThemedSelect
    |
~~Faze 4 (Komponenty)~~          ❌ ZRUSENO — komponenty zustavaji na main
    |
~~Faze 5 (API browsingLevel)~~   ❌ ZRUSENO — API se nemeni
    |
Faze 5 NOVA (Client-side filtr)  ✅ useMemo v BrowsePage + CommunityGalleryPanel
    |
Faze 6 (Header toggle)           ✅ show↔blur toggle, skryty v hide modu
    |
Faze 7 (Review opravy)           ✅ shouldHide() ve filtrech, detail panel, onImagesChange
```

---

## Soubory zmenene (souhrn — oproti main)

| Soubor | Zmeny |
|--------|-------|
| `nsfwStore.ts` | shouldBlur/shouldHide(number\|boolean), normalizeLevel, exceedsMaxLevel, cross-tab sync, merge guard |
| `settingsStore.ts` | Beze zmen (delegace na nsfwStore funguje) |
| `SettingsPage.tsx` | 3-rezimovy prepinac, maxLevel ThemedSelect dropdown |
| `ThemedSelect.tsx` | NOVY — sdilena UI komponenta (extrakce z CommunityGalleryPanel) |
| `Header.tsx` | useNsfwStore, show↔blur toggle, skryty v hide modu |
| `BrowsePage.tsx` | +useNsfwStore.shouldHide, visibleModels filtr, detail previews filtr, fullscreen visiblePreviews |
| `CommunityGalleryPanel.tsx` | ThemedSelect import, shouldHide filtr, onImagesChange(visibleImages) |
| `searchTypes.ts` | +nsfwLevel v ModelPreview/CivitaiModel (typ plumbing) |
| `useNsfwFilter.ts` | Existuje, ale NENI pouzivan v komponentach |
| `en.json` | +settings.display.nsfwMode/Level klice, -header 3-state klice |
| `cs.json` | +settings.display.nsfwMode/Level klice, -header 3-state klice |

**Soubory BEZE ZMEN oproti main:**
- `MediaPreview.tsx`, `ModelCard.tsx`, `ImagePreview.tsx`, `FullscreenMediaViewer.tsx`
- `trpcBridgeAdapter.ts`, `civitaiTransformers.ts`, `synapse-civitai-bridge.user.js`

---

## Testy

**Celkovy pocet NSFW testu:** 165
- `nsfw-store.test.ts` — 54 testu (store logika, normalizeLevel, exceedsMaxLevel, cross-tab sync)
- `nsfw-settings-ui.test.ts` — 25 testu (3-rezimovy prepinac, maxLevel dropdown)
- `nsfw-filter-hook.test.ts` — 78 testu (useNsfwFilter hook, reveal state)
- `nsfw-header-cycle.test.ts` — 8 testu (show↔blur toggle, hide mode)

**Smazane testy (z puvodni v5.0 implementace):**
- ~~`nsfw-browsing-level.test.ts`~~ — testoval browsingLevel v API (zruseno)
- ~~`nsfw-component-render.test.tsx`~~ — testoval nsfwLevel prop na revertovanych komponentach
- ~~`nsfw-integration.test.tsx`~~ — testoval isHidden v komponentach (zruseno)

---

## Review historie

**v5.0–v5.2 (puvodni implementace):** 5 kol × (Claude + Gemini + Codex)
- Implementovany API zmeny (browsingLevel), component-level hiding, 3-state header
- Problemy: rozbite nacitani modelu v BrowsePage, overengineering v komponentach

**v6.0 (redesign):** 1 kolo × (Gemini gemini-3.1 + Codex gpt-5.4)
- Gemini: "Revert BrowsePage, add client-side filter, CommunityGalleryPanel chybi v revert listu"
- Codex: "Nerevertovat BrowsePage uplne — revertovat jen API zmeny, pridat parent-level filtraci. searchTypes nsfwLevel plumbing ponechat."
- Oba: "Component-level return null zpusobuje diry v gridu. Filtrovat na datove urovni."

**v6.1 (opravy z review):** 1 kolo × (Claude + Gemini gemini-3.1 + Codex gpt-5.4)
- **Gemini HIGH:** maxLevel cutoff ignorovan v BrowsePage/CommunityGalleryPanel (pouzival `filterMode === 'hide'` misto `shouldHide()`)
- **Codex HIGH:** Hide bypassable v detail panelu a fullscreen vieweru (nefiltrovane preview pole)
- **Claude HIGH:** onImagesChange predava nefiltrovane images do parent → fullscreen viewer zobrazi vse
- **Vsechny opraveny ve Fazi 7**

---

## Faze 7: Opravy z review — maxLevel cutoff + detail panel (v6.1.0)

**Status:** ✅ HOTOVO

**Nalezy z 3 review (Claude + Gemini 3.1 + Codex 5.4):**

### HIGH — maxLevel hard cutoff ignorovan ve filtrech
- BrowsePage `visibleModels` a CommunityGalleryPanel `visibleImages` pouzivaji `filterMode === 'hide'`
- ALE maxLevel cutoff (napr. maxLevel=r a content X) se NEUPLATNUJE v blur/show modech
- **FIX:** Nahradit `filterMode === 'hide' ? filter : passthrough` za `shouldHide()` z nsfwStore
- `shouldHide()` JIZ resi oba pripady: hide mode + maxLevel cutoff v KAZDEM modu

### HIGH — Detail panel renderuje VSE bez filtru
- BrowsePage:898 `modelDetail.previews.map(...)` — zadny filtr
- Fullscreen viewer:461 `activeGalleryItems` pouziva nefiltrovane `communityImages` / `modelDetail.previews`
- **FIX:** Pridat `visiblePreviews` useMemo filtr + pouzit ve fullscreen viewer

### HIGH — onImagesChange predava nefiltrovane images
- CommunityGalleryPanel:114 `onImagesChange?.(images)` — raw data
- BrowsePage ulozi do `communityImages` → fullscreen viewer zobrazi vse
- **FIX:** `onImagesChange?.(visibleImages)` — predat uz filtrovane

### Soubory ke zmene:
| Soubor | Zmena |
|--------|-------|
| `BrowsePage.tsx` | `shouldHide()` misto `filterMode === 'hide'`, filtr na detail previews, filtr na fullscreen items |
| `CommunityGalleryPanel.tsx` | `shouldHide()` misto `filterMode === 'hide'`, `onImagesChange(visibleImages)` |

### Architektura po oprave:
```
shouldHide(nsfwLevel) rozhoduje o VSEM:
  - filterMode=hide + isNsfw → true
  - filterMode=show/blur + exceedsMaxLevel → true
  - jinak → false

BrowsePage:
  visibleModels = allModels.filter(m => !shouldHide(m.nsfw))
  visiblePreviews = modelDetail.previews.filter(p => !shouldHide(p.nsfw))
  fullscreen items = visiblePreviews / visibleCommunityImages

CommunityGalleryPanel:
  visibleImages = images.filter(img => !shouldHide(img.nsfw))
  onImagesChange(visibleImages)  ← uz filtrovane
```

---

*Posledni aktualizace: 2026-03-06 (v6.1.0 — opravy z review: shouldHide, detail panel filtr, onImagesChange filtr)*
