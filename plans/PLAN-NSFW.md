# PLAN: Globalni NSFW Filtr

**Stav:** Faze 1 HOTOVA, Faze 1B-6 CEKAJI
**Vytvoreno:** 2026-03-04
**Verze:** 4.0.0
**Posledni aktualizace:** 2026-03-05

---

## Prehled

Viceurobnovy NSFW filtracni system, ktery nahradi jednoduchy boolean `nsfwBlurEnabled`.

**Komponenty:**
- `NsfwFilterMode`: `show` | `blur` | `hide`
- `NsfwMaxLevel`: `pg` | `pg13` | `r` | `x` | `all` (mapuje se na Civitai browsing level bitmasku)

**Civitai nsfwLevel bitmaska:**
```
PG=1, PG-13=2, R=4, X=8, Blocked=16
Kumulativni kombinace: pg=1, pg13=3, r=7, x=15, all=31
```

---

## Audit: Soucasny stav

### Co existuje (Faze 1)
- `nsfwStore.ts` — Zustand store s `filterMode`, `maxLevel`, `shouldBlur()`, `shouldHide()`, `getBrowsingLevel()`
- `settingsStore.ts` — deleguje na nsfwStore, synchronizacni subscribe
- Persistence + auto-migrace z legacy `nsfwBlurEnabled`

### Co chybi (mezery)
1. **Metody store prijimaji jen `boolean`** — `shouldBlur(nsfw: boolean)` nemuze vynucovat `maxLevel` per-item
2. **`nsfwLevel` se nepropaguje** — datove typy pouzivaji `nsfw: boolean`, numericka uroven se ztraci na API hranici
3. **Komponenty pouzivaji inline blur logiku** — `nsfw && nsfwBlurEnabled && !isRevealed`
4. **`shouldHide()` se nikde nepouziva** — zadna komponenta neskryva NSFW obsah
5. **`getBrowsingLevel()` se nepouziva v BrowsePage** — bridge ma hardcoded `config.nsfw ? 31 : 1`
6. **Settings UI je binarni** — jen on/off prepinac, zadny 3-rezimovy ani maxLevel
7. **Header prepinac je binarni** — jen show/blur, bez hide
8. **Zadna cross-tab synchronizace** — Zustand persist standardne nebroadcastuje
9. **`useNsfwStore` importovany ale nepouzity** v CommunityGalleryPanel (pouziva lokalni stav)

### Dotcene soubory (16)
| Soubor | Soucasna NSFW logika |
|--------|---------------------|
| `MediaPreview.tsx` | `nsfw && nsfwBlurEnabled && !isRevealed` inline, blur overlay, reveal button |
| `FullscreenMediaViewer.tsx` | Stejna inline logika, blur overlay, reveal v thumbnailech |
| `ModelCard.tsx` | `nsfw && nsfwBlurEnabled && !isRevealed` inline |
| `ImagePreview.tsx` | Stejna inline logika |
| `BrowsePage.tsx` | `includeNsfw=true` hardcoded, `nsfw` prop na MediaPreview |
| `PacksPage.tsx` | `nsfwBlurEnabled` + `is_nsfw_hidden` tag check |
| `CommunityGalleryPanel.tsx` | Lokalni `communityBrowsingLevel` stav, predava do adapteru |
| `Header.tsx` | 2-stavovy prepinac (show/blur) |
| `SettingsPage.tsx` | Jednoduchy on/off prepinac |
| `settingsStore.ts` | Legacy delegace |
| `nsfwStore.ts` | Store (metody prijimaji jen boolean) |
| `searchTypes.ts` | `nsfw: boolean` v ModelPreview a CivitaiModel |
| `trpcBridgeAdapter.ts` | Predava browsingLevel jen pro community galerii |

---

## Faze 1: Store + Zpetna kompatibilita (HOTOVO)

**Soubory:**
- `apps/web/src/stores/nsfwStore.ts` — Zustand store s persist
- `apps/web/src/stores/settingsStore.ts` — deleguje na nsfwStore

**Implementace:**
- `useNsfwStore` s `filterMode`, `maxLevel`, `getBrowsingLevel()`, `shouldBlur()`, `shouldHide()`
- Persistence klic: `synapse-nsfw-settings`
- Auto-migrace z legacy `synapse-settings.nsfwBlurEnabled`
- `settingsStore.nsfwBlurEnabled` getter/setter deleguje na `nsfwStore`
- Subscribe sync: zmeny v nsfwStore se propaguji do settingsStore

**Stav:** IMPL+INTEG

---

## Faze 1B: Upgrade Store — Granularita urovni + Cross-Tab Sync (CEKA)

### Cil
Upgradovat metody store aby prijimaly numericke `nsfwLevel` (ne jen boolean). Pridat cross-tab synchronizaci.

### Proc
Soucasne `shouldBlur(nsfw: boolean)` nemuze vynucovat `maxLevel`. Kdyz uzivatel nastavi maxLevel na `r`, obrazek PG-13 i obrazek X oba predaji `nsfw=true` — store je nerozezna.

### Zmeny

**Soubor:** `apps/web/src/stores/nsfwStore.ts`

1. **Upgrade signatur `shouldBlur` a `shouldHide`:**
   ```typescript
   // Prijima numericku uroven (Civitai konvence) nebo boolean fallback
   shouldBlur: (nsfwLevel: number | boolean) => boolean
   shouldHide: (nsfwLevel: number | boolean) => boolean
   ```

2. **Logika s urovnemi:**
   ```typescript
   // Sentinel pro legacy boolean nsfw=true (numericka uroven neni k dispozici)
   const UNKNOWN_NSFW_LEVEL = -1

   // Helper: zjisti jestli uroven polozky presahuje uzivateluv maxLevel
   function exceedsMaxLevel(itemLevel: number, maxBitmask: number): boolean {
     // Legacy obsah s neznamou urovni (-1) se NIKDY neskryva podle maxLevel
     // (nezname jeho uroven, takze nemuzeme rozhodovat o stropu)
     if (itemLevel === UNKNOWN_NSFW_LEVEL) return false
     // Uroven polozky je jediny bit (1, 2, 4, 8, 16)
     // maxBitmask je kumulativni (1, 3, 7, 15, 31)
     // Polozka presahuje pokud jeji bit NENI nastaveny v masce
     return (itemLevel & maxBitmask) === 0
   }

   // Helper: normalizuje boolean/number vstup
   function normalizeLevel(nsfwLevel: number | boolean): { isNsfw: boolean; level: number } {
     if (typeof nsfwLevel === 'boolean') {
       // Boolean fallback: true = neznama NSFW uroven (nepredpokladame X!)
       // false = bezpecny obsah (PG=1)
       return { isNsfw: nsfwLevel, level: nsfwLevel ? UNKNOWN_NSFW_LEVEL : 1 }
     }
     return { isNsfw: nsfwLevel > 1, level: nsfwLevel }
   }

   shouldBlur: (nsfwLevel: number | boolean) => {
     const { isNsfw } = normalizeLevel(nsfwLevel)
     const state = get()
     // Rozmazat JAKYKOLI nsfw obsah v blur rezimu.
     // (shouldHide uz resi polozky presahujici maxLevel — ty se
     //  vubec nevykresli, takze shouldBlur se pro ne nevola)
     return state.filterMode === 'blur' && isNsfw
   }

   shouldHide: (nsfwLevel: number | boolean) => {
     const { isNsfw, level } = normalizeLevel(nsfwLevel)
     const state = get()
     if (!isNsfw) return false
     if (state.filterMode === 'hide') return true
     // V show I blur rezimu: polozky presahujici maxLevel jsou skryte.
     // Show rezim = "bez rozmazani" NE "ignoruj strop".
     // Uzivatel nastavil strop — respektujeme ho bez ohledu na blur/show.
     // Legacy boolean obsah (UNKNOWN_NSFW_LEVEL) se nikdy neskryva podle stropu.
     return exceedsMaxLevel(level, LEVEL_BITMASK[state.maxLevel])
   }
   ```

   **Semantika:**
   | Rezim | NSFW v ramci maxLevel | Presahuje maxLevel | Legacy boolean (neznama uroven) |
   |-------|----------------------|--------------------|---------------------------------|
   | `show` | viditelne + badge | skryte | viditelne + badge |
   | `blur` | rozmazane | skryte | rozmazane |
   | `hide` | skryte | skryte | skryte |

3. **`getBrowsingLevel()` respektuje hide rezim:**
   ```typescript
   getBrowsingLevel: () => {
     const state = get()
     // V hide rezimu pozadovat pouze bezpecny obsah ze serveru
     if (state.filterMode === 'hide') return 1
     return LEVEL_BITMASK[state.maxLevel]
   }
   ```

4. **Cross-tab synchronizace:**
   ```typescript
   // Vychozi hodnoty pro reset
   const NSFW_DEFAULTS = { filterMode: 'blur' as const, maxLevel: 'all' as const }

   // Idempotentni listener — bezpecny pro HMR
   let _storageListenerAttached = false
   if (typeof window !== 'undefined' && !_storageListenerAttached) {
     _storageListenerAttached = true
     window.addEventListener('storage', (e) => {
       if (e.key !== 'synapse-nsfw-settings') return

       if (e.newValue === null) {
         // Storage byl vycisten (napr. uzivatel smazal data prohlizece v jinem tabu)
         // Reset na vychozi hodnoty
         useNsfwStore.setState({
           filterMode: NSFW_DEFAULTS.filterMode,
           maxLevel: NSFW_DEFAULTS.maxLevel,
           nsfwBlurEnabled: true,
         })
         return
       }

       try {
         const { state } = JSON.parse(e.newValue)
         useNsfwStore.setState({
           filterMode: state.filterMode,
           maxLevel: state.maxLevel,
           nsfwBlurEnabled: state.filterMode !== 'show',
         })
       } catch { /* ignorovat chyby parsovani */ }
     })
   }
   ```

### Zmeny datovych typu

**Soubor:** `apps/web/src/lib/api/searchTypes.ts`

Pridat `nsfwLevel` vedle stavajiciho `nsfw` boolean (zpetna kompatibilita):

```typescript
interface ModelPreview {
  // ... stavajici
  nsfw: boolean
  nsfwLevel?: number  // NOVE: Civitai numericka uroven (1=PG, 2=PG-13, 4=R, 8=X)
}

interface CivitaiModel {
  // ... stavajici
  nsfw: boolean
  nsfwLevel?: number  // NOVE
}
```

**Soubor:** `apps/web/src/components/ui/FullscreenMediaViewer.tsx` (MediaItem typ)

```typescript
export interface MediaItem {
  // ... stavajici
  nsfw?: boolean
  nsfwLevel?: number  // NOVE: numericka uroven pro granularni filtrovani
}
```

### Zpetna kompatibilita
- Vsechna stavajici volani `shouldBlur(true/false)` fungují dale
- `boolean true` = neznama NSFW uroven (-1) — rozmazane v blur rezimu, nikdy skryte podle maxLevel stropu
- `boolean false` = bezpecny obsah (PG=1) — nikdy rozmazane ani skryte
- Komponenty mohou postupne adoptovat `nsfwLevel` jakmile budou numericka data k dispozici

### Testy
- Unit: `shouldBlur(true)` vraci true v blur rezimu (zpetna kompatibilita)
- Unit: `shouldBlur(false)` vraci false v jakemkoli rezimu
- Unit: `shouldBlur(2)` (PG-13) vraci true v blur rezimu s maxLevel=`r` (v ramci limitu = rozmazane)
- Unit: `shouldBlur(8)` (X) vraci true v blur rezimu s maxLevel=`r` (ale shouldHide ho skryje driv)
- Unit: `shouldHide(true)` vraci false v blur rezimu (legacy = neznama uroven, nikdy skryte podle stropu)
- Unit: `shouldHide(true)` vraci false v show rezimu (legacy = neznama uroven, nikdy skryte podle stropu)
- Unit: `shouldHide(true)` vraci true v hide rezimu (hide rezim skryva VSECHNO nsfw)
- Unit: `shouldHide(8)` (X) vraci true v show rezimu s maxLevel=`r` (presahuje strop i v show rezimu!)
- Unit: `shouldHide(8)` (X) vraci true v blur rezimu s maxLevel=`r` (presahuje strop)
- Unit: `shouldHide(2)` (PG-13) vraci false v blur rezimu s maxLevel=`r` (v ramci stropu)
- Unit: `shouldHide(4)` (R) vraci true v blur rezimu s maxLevel=`pg13` (presahuje strop)
- Unit: `shouldHide(8)` vraci true v hide rezimu bez ohledu na maxLevel
- Unit: `getBrowsingLevel()` vraci 1 kdyz filterMode=hide
- Unit: `getBrowsingLevel()` vraci 7 kdyz filterMode=blur, maxLevel=r
- Unit: Cross-tab sync aktualizuje stav ze storage eventu
- Unit: `normalizeLevel(true)` vraci `{ isNsfw: true, level: -1 }` (UNKNOWN)
- Unit: `normalizeLevel(false)` vraci `{ isNsfw: false, level: 1 }`
- Unit: `normalizeLevel(4)` vraci `{ isNsfw: true, level: 4 }`
- Unit: `exceedsMaxLevel(-1, 7)` vraci false (neznama uroven nikdy nepresahuje)

---

## Faze 2: Settings UI (CEKA)

### Cil
Nahradit binarni prepinac v SettingsPage 3-rezimovym prepinacam + maxLevel dropdown.

### Soucasny stav
`SettingsPage.tsx:237-257` — jednoduchy on/off switch (`setNsfwBlur(!nsfwBlurEnabled)`).

### Zmeny

**Soubor:** `apps/web/src/components/modules/SettingsPage.tsx`

1. **Importovat `useNsfwStore`** misto `useSettingsStore` pro NSFW sekci
2. **3-rezimovy SegmentedControl** pro `filterMode`:
   ```
   +----------+----------+----------+
   | Zobrazit | Rozmazat |  Skryt   |
   +----------+----------+----------+
   ```
   - `show` — NSFW viditelne s badge (v ramci maxLevel stropu; presahujici = skryte)
   - `blur` — rozmazane s kliknutim pro odkryti (soucasne chovani)
   - `hide` — NSFW obsah se vubec nevykresluje
   - Pouzit stavajici button group vzor z UI

3. **maxLevel dropdown** pod segmented control:
   ```
   NSFW uroven: [PG v]
   ```
   Moznosti: PG (nejbezpecnejsi) -> PG-13 -> R -> X -> Vse
   - Label: "Maximalni uroven NSFW obsahu k zobrazeni"
   - Zobrazit POUZE kdyz `filterMode !== 'hide'` (hide rezim = nic se neukazuje, uroven je irelevantni)

4. **Popisy** pro kazdy rezim:
   - Show: "Obsah do nastavene urovne viditelny se stitky NSFW"
   - Blur: "NSFW obsah je rozmazany, kliknutim se odkryje"
   - Hide: "NSFW obsah je zcela skryty"

### i18n klice (nove)

**en.json:**
```json
"settings.display.nsfwMode": "NSFW Filter Mode",
"settings.display.nsfwModeDesc": "How to handle NSFW content",
"settings.display.nsfwMode.show": "Show",
"settings.display.nsfwMode.blur": "Blur",
"settings.display.nsfwMode.hide": "Hide",
"settings.display.nsfwMode.showDesc": "Content within max level visible with NSFW badges",
"settings.display.nsfwMode.blurDesc": "NSFW content is blurred until clicked",
"settings.display.nsfwMode.hideDesc": "NSFW content is completely hidden",
"settings.display.nsfwMaxLevel": "Maximum NSFW Level",
"settings.display.nsfwMaxLevelDesc": "Maximum content rating to display",
"settings.display.nsfwLevel.pg": "PG (Safe)",
"settings.display.nsfwLevel.pg13": "PG-13",
"settings.display.nsfwLevel.r": "R (Mature)",
"settings.display.nsfwLevel.x": "X (Explicit)",
"settings.display.nsfwLevel.all": "All"
```

**cs.json:**
```json
"settings.display.nsfwMode": "Rezim NSFW filtru",
"settings.display.nsfwModeDesc": "Jak zachazet s NSFW obsahem",
"settings.display.nsfwMode.show": "Zobrazit",
"settings.display.nsfwMode.blur": "Rozmazat",
"settings.display.nsfwMode.hide": "Skryt",
"settings.display.nsfwMode.showDesc": "Obsah do nastavene urovne viditelny se stitky NSFW",
"settings.display.nsfwMode.blurDesc": "NSFW obsah je rozmazany, kliknutim se odkryje",
"settings.display.nsfwMode.hideDesc": "NSFW obsah je zcela skryty",
"settings.display.nsfwMaxLevel": "Maximalni uroven NSFW",
"settings.display.nsfwMaxLevelDesc": "Maximalni hodnoceni obsahu k zobrazeni",
"settings.display.nsfwLevel.pg": "PG (Bezpecne)",
"settings.display.nsfwLevel.pg13": "PG-13",
"settings.display.nsfwLevel.r": "R (Pro dospele)",
"settings.display.nsfwLevel.x": "X (Explicitni)",
"settings.display.nsfwLevel.all": "Vse"
```

### Testy
- Unit: SettingsPage vykresluje 3 segmenty rezimu, maxLevel dropdown
- Unit: maxLevel dropdown je skryty kdyz mode=hide
- Unit: kliknuti na segment meni `filterMode` v nsfwStore
- Unit: vyber maxLevel meni `maxLevel` v nsfwStore

---

## Faze 3: Komponenty — useNsfwFilter Hook + Filtrovani podle urovni (CEKA)

### Cil
Nahradit vsechny inline `nsfw && nsfwBlurEnabled && !isRevealed` vzory centralizovanym hookem.
Pridat `shouldHide()` logiku. Propagovat numericke `nsfwLevel` kde je k dispozici.

### Strategie

Zavest **helper hook** pro eliminaci boilerplate:

```typescript
// apps/web/src/hooks/useNsfwFilter.ts
export function useNsfwFilter(nsfwLevel: number | boolean) {
  // Pouzit individualni selektory pro spravnou reaktivitu
  const shouldBlur = useNsfwStore((s) => s.shouldBlur)
  const shouldHide = useNsfwStore((s) => s.shouldHide)
  const filterMode = useNsfwStore((s) => s.filterMode)
  // Subscribe na maxLevel aby se odvozone hodnoty prepocitaly pri zmene stropu
  const _maxLevel = useNsfwStore((s) => s.maxLevel) // spousti re-render
  const [isRevealed, setIsRevealed] = useState(false)

  // Reset reveal stavu pri zmene rezimu
  useEffect(() => {
    setIsRevealed(false)
  }, [filterMode])

  const isHidden = shouldHide(nsfwLevel)
  // Vzajemne se vylucujici: skryte polozky se nikdy nerozmazavaji
  const isBlurred = !isHidden && shouldBlur(nsfwLevel) && !isRevealed
  const isNsfw = typeof nsfwLevel === 'boolean' ? nsfwLevel : nsfwLevel > 1

  return {
    isBlurred,
    isHidden,
    isRevealed,
    reveal: () => setIsRevealed(true),
    hide: () => setIsRevealed(false),
    toggle: () => setIsRevealed(prev => !prev),
    // Badge viditelny v show rezimu NEBO po manualnim odkryti
    showBadge: isNsfw && (filterMode === 'show' || isRevealed),
  }
}
```

### Zmeny podle souboru

#### 3.1 MediaPreview.tsx
- Importovat `useNsfwFilter` misto `useSettingsStore`
- Prijmout `nsfwLevel?: number` prop vedle stavajiciho `nsfw` propu
- `const nsfwInput = nsfwLevel ?? nsfw ?? false` (preferovat numericke, fallback na boolean)
- `const { isBlurred, isHidden, isRevealed, toggle, showBadge } = useNsfwFilter(nsfwInput)`
- `if (isHidden) return null` — vubec nevykreslovat
- Nahradit `shouldBlur` -> `isBlurred`
- Nahradit NSFW badge logiku -> `showBadge`
- Odebrat interni `isRevealed` stav (presunut do hooku)
- Ponechat `nsfwBlurEnabled` prop pro zpetnou kompatibilitu (override store)

#### 3.2 FullscreenMediaViewer.tsx
- Importovat `useNsfwStore`
- **Filtrovat polozky PRED navigaci** (zadne placeholdery):
  ```typescript
  const shouldHide = useNsfwStore((s) => s.shouldHide)
  const filterMode = useNsfwStore((s) => s.filterMode)
  const maxLevel = useNsfwStore((s) => s.maxLevel)
  const visibleItems = useMemo(
    () => items.filter(item => !shouldHide(item.nsfwLevel ?? item.nsfw ?? false)),
    // shouldHide je stabilni ref ale interene cte stav pres get() —
    // musi obsahovat filterMode + maxLevel aby se spustil prepocet
    [items, shouldHide, filterMode, maxLevel]
  )
  ```
- **Mapovani indexu** (prevence padu):
  ```typescript
  // Mapovat puvodní initialIndex na visibleItems index pres identitu polozky
  const mappedInitialIndex = useMemo(() => {
    if (visibleItems.length === 0) return -1
    const targetItem = items[initialIndex]
    if (!targetItem) return 0
    // Referencni rovnost — visibleItems jsou stejne objekty z items pole
    const idx = visibleItems.indexOf(targetItem)
    return idx >= 0 ? idx : 0  // Fallback na prvni viditelnou pokud originalni byla skryta
  }, [items, visibleItems, initialIndex])
  ```
- **Osetreni prazdneho stavu** (useEffect, ne v tele renderovani):
  ```typescript
  // Zavrit viewer kdyz vsechny polozky budou skryte (napr. uzivatel zmeni maxLevel)
  // Musi byt v useEffect — volani onClose v renderu je React anti-pattern
  useEffect(() => {
    if (visibleItems.length === 0) onClose?.()
  }, [visibleItems.length, onClose])

  // Guard render
  if (visibleItems.length === 0) return null
  ```
- Pouzit `visibleItems` pro vsechnu navigaci, mapovani indexu, thumbnail strip
- Per-item blur: pouzit `useNsfwFilter` pro aktualni viditelnou polozku
- Blur overlay: nahradit inline logiku za `isBlurred`

#### 3.3 ModelCard.tsx
- Importovat `useNsfwFilter`
- Prijmout `nsfwLevel?: number` prop
- `const { isBlurred, isHidden, toggle, showBadge } = useNsfwFilter(nsfwLevel ?? nsfw)`
- `if (isHidden) return null`
- Nahradit inline blur vzor

#### 3.4 ImagePreview.tsx
- Importovat `useNsfwFilter`
- Stejny vzor jako ModelCard
- `if (isHidden) return null`

#### 3.5 CommunityGalleryPanel.tsx
- Uz pouziva `nsfwStore.getBrowsingLevel()` pro API volani (dobre!)
- **Vynucovat globalni strop na lokalnim browsingLevel selektoru**:
  ```typescript
  const globalMaxLevel = useNsfwStore((s) => s.getBrowsingLevel())

  // Efektivni uroven = prunik lokalni volby a globalniho stropu
  // Uzivatel muze zuzit (vybrat PG kdyz globalni je R) ale nikdy rozsirit (vybrat Vse kdyz globalni je PG)
  const effectiveBrowsingLevel = communityBrowsingLevel === 'auto'
    ? globalMaxLevel
    : Math.min(communityBrowsingLevel, globalMaxLevel)
  ```
  Poznamka: `Math.min` zde funguje protoze bitmasky jsou kumulativni (1 < 3 < 7 < 15 < 31).
- Pridat `shouldHide` pro filtrovani preview polozek (client-side bezpecnostni sit):
  ```typescript
  const shouldHide = useNsfwStore((s) => s.shouldHide)
  const filterMode = useNsfwStore((s) => s.filterMode)
  const maxLevel = useNsfwStore((s) => s.maxLevel)
  const visiblePreviews = useMemo(
    () => allPreviews.filter(p => !shouldHide(p.nsfwLevel ?? p.nsfw ?? false)),
    // Musi obsahovat filterMode + maxLevel — shouldHide je stabilni ref
    [allPreviews, shouldHide, filterMode, maxLevel]
  )
  ```

### Zpetna kompatibilita
- `nsfw: boolean` prop ponechan na vsech komponentach (zpetna kompatibilita)
- Novy `nsfwLevel?: number` prop pridan vedle
- Hook prijima `number | boolean` — funguje s obojim
- `nsfwBlurEnabled` prop na MediaPreview ponechan ale oznacen `@deprecated`

### i18n klice (nove)

**en.json:**
```json
"viewer.nsfwHiddenPlaceholder": "NSFW content hidden",
"viewer.nsfwItemsFiltered": "{{count}} items hidden by NSFW filter"
```

**cs.json:**
```json
"viewer.nsfwHiddenPlaceholder": "NSFW obsah skryt",
"viewer.nsfwItemsFiltered": "{{count}} polozek skryto NSFW filtrem"
```

### Testy
- Unit: `useNsfwFilter(true)` v blur rezimu -> isBlurred=true, isHidden=false
- Unit: `useNsfwFilter(true)` v hide rezimu -> isBlurred=false, isHidden=true
- Unit: `useNsfwFilter(8)` s maxLevel=r, blur rezim -> isHidden=true, isBlurred=false (vzajemne se vylucuji)
- Unit: `useNsfwFilter(2)` s maxLevel=r, blur rezim -> isBlurred=true, isHidden=false
- Unit: reveal() nastavi isRevealed=true, toggle() prepina
- Unit: showBadge=true kdyz filterMode=show A nsfw
- Unit: showBadge=true kdyz isRevealed=true A nsfw
- Unit: MediaPreview s mode=hide vraci null
- Unit: ModelCard s mode=hide vraci null
- Unit: FullscreenViewer filtruje skryte polozky z navigace
- Unit: CommunityGalleryPanel filtruje skryte nahledy
- Integracni: prepnuti rezimu -> vsechny komponenty reagují

---

## ~~Faze 4: PacksPage~~ — VYRAZENO

Packy pouzivaji user-driven system (flagy `is_nsfw`, `nsfw-pack-hide` tag).
Uzivatel sam rozhoduje co je NSFW a co skryt — globalni `shouldHide()` s `maxLevel` stropem
nedava smysl (pack nema numerickou uroven). Soucasny system zustava beze zmen.

---

## Faze 4: BrowsePage + Bridge browsingLevel (CEKA)

### Cil
Predat `browsingLevel` z nsfwStore do bridge/adapteru. Server-side filtrovani misto client-side.

### Soucasny stav
- `BrowsePage.tsx:120`: `const [includeNsfw] = useState(true)` — hardcoded true
- Bridge: `browsingLevel: config.nsfw ? 31 : 1` — bridge-level config, nezavisle na frontendu
- CommunityGalleryPanel uz predava browsingLevel spravne

### Klicove rozhodnuti — bez client-side filtrovani v hide rezimu

**ZADNE client-side filtrovani v hide rezimu.** Misto toho:
- `getBrowsingLevel()` uz vraci `1` kdyz `filterMode === 'hide'` (z Faze 1B)
- To znamena ze API/bridge vraci pouze bezpecny obsah — zadne prazdne stranky
- Velikost stranky je zachovana, nekonecny scroll funguje spravne
- Uspora bandwidthu (NSFW obsah se nikdy nestahuje)

### Zmeny

#### 4.1 Rozsireni SearchParams
**Soubor:** `apps/web/src/lib/api/searchTypes.ts`

```typescript
interface SearchParams {
  // ... stavajici
  browsingLevel?: number  // Civitai browsing level bitmaska (1-31)
}
```

#### 4.2 BrowsePage
**Soubor:** `apps/web/src/components/modules/BrowsePage.tsx`

1. Odebrat `const [includeNsfw] = useState(true)`
2. Importovat `useNsfwStore`
3. Pouzit store:
   ```typescript
   // Pouzit individualni selektory pro optimalni re-rendery
   const getBrowsingLevel = useNsfwStore((s) => s.getBrowsingLevel)
   const filterMode = useNsfwStore((s) => s.filterMode)
   const maxLevel = useNsfwStore((s) => s.maxLevel)
   const browsingLevel = getBrowsingLevel()  // Vraci 1 v hide rezimu!
   ```
4. V adapter.search():
   ```typescript
   await adapter.search({
     // ...stavajici
     browsingLevel,
     // odebrat: nsfw: includeNsfw,
   })
   ```
5. QueryKey: pridat `browsingLevel` misto statickeho `includeNsfw`
6. **ZADNE client-side filtrovani** — server to resi pres browsingLevel

#### 4.3 trpcBridgeAdapter
**Soubor:** `apps/web/src/lib/api/adapters/trpcBridgeAdapter.ts`

1. Predat `browsingLevel` do bridge searche:
   ```typescript
   bridge.search({
     // ...stavajici
     browsingLevel: params.browsingLevel,
   })
   ```
2. Aktualizovat bridge interface — pridat `browsingLevel?: number` do search requestu

#### 4.4 Bridge skript
**Soubor:** `scripts/tampermonkey/synapse-civitai-bridge.user.js`

1. `buildSearchUrl` — pouzit `params.browsingLevel` pokud je k dispozici, jinak fallback na config:
   ```javascript
   browsingLevel: params.browsingLevel ?? (config.nsfw ? 31 : 1),
   ```
2. `buildMeilisearchRequest` — pridat nsfwLevel filtr z browsingLevel:
   ```javascript
   // Prelozit browsingLevel bitmasku na nsfwLevel filtr
   const allowedLevels = []
   if (browsingLevel & 1) allowedLevels.push(1)   // PG
   if (browsingLevel & 2) allowedLevels.push(2)   // PG-13
   if (browsingLevel & 4) allowedLevels.push(4)   // R
   if (browsingLevel & 8) allowedLevels.push(8)   // X
   if (browsingLevel & 16) allowedLevels.push(16) // Blocked
   nsfwFilter = `(${allowedLevels.map(l => `nsfwLevel=${l}`).join(' OR ')})`
   ```
3. Vsechny image endpointy (`buildModelImagesUrl`, `buildModelImagesAsPostsUrl`) — prijmout a predat `browsingLevel`

#### 4.5 Propagace nsfwLevel z API odpovedi
**Soubor:** Bridge skript + `trpcBridgeAdapter.ts`

Zajistit ze `nsfwLevel` numericka hodnota z Civitai API se propaguje do frontendovych datovych typu:
```javascript
// V bridge response mappingu:
previews: images.map(img => ({
  url: img.url,
  nsfw: img.nsfwLevel > 1,           // boolean pro zpetnou kompatibilitu
  nsfwLevel: img.nsfwLevel,           // NOVE: numericka uroven
  // ...
}))
```

### Testy
- Unit: `getBrowsingLevel()` vraci spravnou bitmasku pro kazdy maxLevel
- Unit: `getBrowsingLevel()` vraci 1 kdyz filterMode=hide
- Unit: BrowsePage predava browsingLevel do adapteru
- Unit: QueryKey se meni kdyz se zmeni browsingLevel (spousti refetch)
- Integracni: adapter -> bridge — browsingLevel se propaguje
- Unit: Meilisearch filter builder generuje spravny nsfwLevel filtr
- Unit: Bridge mapuje nsfwLevel numericke hodnoty do preview dat

---

## Faze 6: Upgrade Header prepinace (CEKA)

### Cil
Upgradovat header tlacitko z 2-stavoveho na 3-stavovy cyklus.

### Soucasny stav
`Header.tsx:46-65` — prepinani mezi show/blur s Eye/EyeOff ikonami.

### Zmeny

**Soubor:** `apps/web/src/components/layout/Header.tsx`

1. Importovat `useNsfwStore` misto `useSettingsStore`
2. 3-stavovy cyklus: `show -> blur -> hide -> show`
3. Vizualni stavy:
   ```
   Show:  zeleny okraj,  Eye ikona,    "NSFW: Zobrazit"
   Blur:  indigo okraj,  EyeOff ikona, "NSFW: Rozmazat"
   Hide:  cerveny okraj, Ban ikona,    "NSFW: Skryt"
   ```
4. Click handler:
   ```typescript
   const cycleMode = () => {
     const next = { show: 'blur', blur: 'hide', hide: 'show' } as const
     setFilterMode(next[filterMode])
   }
   ```
5. Tooltip: aktualni rezim + "Kliknutim prepnete"
6. **Pristupnost:**
   ```typescript
   <button
     onClick={cycleMode}
     aria-label={t(`header.nsfwAria.${filterMode}`)}
     // Bez role="switch" — 3-stavovy cyklus NENI binarni prepinac
     // Vychozi button role + dynamicky aria-label je spravny vzor
   >
     {/* ikona + label */}
   </button>
   {/* Live region pro oznameni cteckam obrazovky */}
   <span className="sr-only" aria-live="polite" aria-atomic="true">
     {t(`header.nsfwAnnounce.${filterMode}`)}
   </span>
   ```

### i18n klice (nove)

**en.json:**
```json
"header.nsfwShow": "NSFW: Show",
"header.nsfwBlur": "NSFW: Blur",
"header.nsfwHide": "NSFW: Hide",
"header.nsfwCycleTooltip": "Current: {{mode}}. Click to cycle.",
"header.nsfwAria.show": "NSFW filter: showing all content. Click to blur.",
"header.nsfwAria.blur": "NSFW filter: blurring content. Click to hide.",
"header.nsfwAria.hide": "NSFW filter: hiding content. Click to show.",
"header.nsfwAnnounce.show": "NSFW filter changed to: Show all",
"header.nsfwAnnounce.blur": "NSFW filter changed to: Blur",
"header.nsfwAnnounce.hide": "NSFW filter changed to: Hide"
```

**cs.json:**
```json
"header.nsfwShow": "NSFW: Zobrazit",
"header.nsfwBlur": "NSFW: Rozmazat",
"header.nsfwHide": "NSFW: Skryt",
"header.nsfwCycleTooltip": "Aktualne: {{mode}}. Kliknutim prepnete.",
"header.nsfwAria.show": "NSFW filtr: zobrazuji veskerý obsah. Kliknutim rozmazete.",
"header.nsfwAria.blur": "NSFW filtr: rozmazany obsah. Kliknutim skryjete.",
"header.nsfwAria.hide": "NSFW filtr: skryty obsah. Kliknutim zobrazite.",
"header.nsfwAnnounce.show": "NSFW filtr zmenen na: Zobrazit vse",
"header.nsfwAnnounce.blur": "NSFW filtr zmenen na: Rozmazat",
"header.nsfwAnnounce.hide": "NSFW filtr zmenen na: Skryt"
```

### Testy
- Unit: 3 stavy vykresluji spravnou ikonu, barvu, text
- Unit: kliknuti cykluje show->blur->hide->show
- Unit: stav se synchronizuje s nsfwStore
- Unit: aria-label se aktualizuje podle stavu
- Unit: aria-live region oznamuje zmeny

---

## Poradi implementace

```
Faze 1B (Upgrade Store)        -- granularita urovni, cross-tab sync, getBrowsingLevel fix
    |
Faze 2 (Settings UI)          -- uzivatel muze konfigurovat rezim + maxLevel
    |
Faze 3 (Komponenty)           -- useNsfwFilter hook, hide rezim, badge fix
    |
Faze 4 (BrowsePage + Bridge)  -- server-side browsingLevel, propagace nsfwLevel
    |
Faze 5 (Header prepinac)      -- rychly pristup, 3-stavovy cyklus, pristupnost
```

Faze 1B musi byt prvni (zmena kontraktu store).
Faze 2 a 3 mohou bezet paralelne po 1B.
Faze 4 zavisi na 1B (chovani getBrowsingLevel).
Faze 5 je nezavisla po 1B.

---

## Soubory ke zmene (souhrn)

| Soubor | Faze | Zmeny |
|--------|------|-------|
| `nsfwStore.ts` | 1B | Level-aware shouldBlur/shouldHide, getBrowsingLevel hide fix, cross-tab sync |
| `searchTypes.ts` | 1B, 5 | +nsfwLevel do ModelPreview/CivitaiModel, +browsingLevel do SearchParams |
| `SettingsPage.tsx` | 2 | 3-rezimovy prepinac, maxLevel dropdown |
| `useNsfwFilter.ts` | 3 | NOVY — sdileny hook |
| `MediaPreview.tsx` | 3 | useNsfwFilter, isHidden->null, +nsfwLevel prop |
| `FullscreenMediaViewer.tsx` | 3 | Filtrovani skrytych polozek z navigace, useNsfwFilter |
| `ModelCard.tsx` | 3 | useNsfwFilter, isHidden->null, +nsfwLevel prop |
| `ImagePreview.tsx` | 3 | useNsfwFilter, isHidden->null |
| `CommunityGalleryPanel.tsx` | 3 | shouldHide filtr na nahledech |
| `BrowsePage.tsx` | 4 | getBrowsingLevel(), odebrat includeNsfw, bez client-side filtru |
| `trpcBridgeAdapter.ts` | 4 | Predat browsingLevel do bridge searche, propagovat nsfwLevel |
| `synapse-civitai-bridge.user.js` | 4 | browsingLevel param, Meilisearch nsfwLevel filtr |
| `Header.tsx` | 5 | 3-stavovy cyklus, aria-label, aria-live |
| `en.json` | 2, 3, 5 | Nove i18n klice |
| `cs.json` | 2, 3, 5 | Ceske preklady |

---

## Verifikace (po kazde fazi)

1. `cd apps/web && npx tsc --noEmit` — 0 chyb
2. `cd apps/web && npx vitest run` — vsechny testy prochazi
3. `./scripts/verify.sh --quick` — plna verifikace
4. Manualne: prepnout rezimy, overit vizualni chovani

---

*Posledni aktualizace: 2026-03-05 (v4.0.0 — cestina, vycisteno od review balastu)*
