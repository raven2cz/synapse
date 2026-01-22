# Synapse - Claude Code Project Memory

## 🎯 Základní pravidla

### Komunikace
- **S uživatelem:** Česky
- **Kód, komentáře, JSDoc, commit messages:** Anglicky
- **Dokumentace:** Anglicky (pokud uživatel neurčí jinak)

### Jediný zdroj pravdy
**`plans/PLAN-Internal-Search-trpc.md`** je JEDINÝ soubor, který určuje:
- Co je implementováno
- Co je INTEGROVÁNO (kritické! implementace ≠ integrace)
- Co ještě chybí
- Jak jsou věci implementovány

### Pravidla pro PLAN soubor
- **NIKDY nemazat text** - pouze škrtat (~~text~~) nebo přidávat
- Vždy označit stav: `✅ IMPL+INTEG` | `⚠️ IMPL (chybí integrace)` | `❌ CHYBÍ`
- Při implementaci přidat poznámku JAK bylo implementováno
- Při integraci přidat poznámku KDE bylo integrováno
- Každá feature musí mít testy!

---

## 📁 Struktura projektu

```
synapse/
├── apps/
│   ├── api/          # FastAPI backend (legacy, deprecated)
│   └── web/          # React frontend (Vite + TanStack Query)
│       └── src/
│           ├── components/
│           │   ├── modules/   # Page components (BrowsePage, PacksPage, PackDetailPage)
│           │   └── ui/        # Reusable UI (MediaPreview, FullscreenMediaViewer)
│           ├── lib/           # Utilities, hooks
│           └── __tests__/     # Frontend tests (Vitest)
├── src/              # Python backend
│   ├── api/          # FastAPI routers (v2)
│   ├── core/         # Core logic (pack_builder.py, models.py)
│   ├── store/        # Pack storage (pack_service.py, api.py)
│   ├── utils/        # Utilities (media_detection.py)
│   └── clients/      # External API clients (civitai.py)
├── plans/            # PLAN soubory pro jednotlivé fáze
│   ├── PLAN-Phase-4.md              # ✅ DOKONČENO - Packs Video & Import
│   └── PLAN-Internal-Search-trpc.md # 🚧 AKTIVNÍ - Interní vyhledávání
├── tests/            # Python tests (pytest)
│   ├── unit/
│   └── integration/
└── config/           # Configuration files
```

---

## 🔧 Důležité příkazy

### Backend (Python)
```bash
# Spustit testy
pytest tests/ -v

# Spustit konkrétní test
pytest tests/unit/test_pack_builder_video.py -v

# Spustit backend server
python -m uvicorn src.api.main:app --reload --port 8000
```

### Frontend (Web)
```bash
# Přejít do web složky
cd apps/web

# Instalace závislostí
pnpm install

# Spustit dev server
pnpm dev

# Spustit testy
pnpm test

# Build
pnpm build
```

---

## 🏗️ Architektura - Klíčové komponenty

### Backend
| Soubor | Účel |
|--------|------|
| `src/core/pack_builder.py` | Import packů z Civitai, stahování preview |
| `src/store/pack_service.py` | CRUD operace nad packy |
| `src/store/api.py` | FastAPI routery pro packy (v2) |
| `src/utils/media_detection.py` | Detekce typu média (image/video), URL transformace |
| `src/clients/civitai_client.py` | Civitai API client |

### Frontend
| Soubor | Účel |
|--------|------|
| `MediaPreview.tsx` | **HLAVNÍ** komponenta pro zobrazení obrázků/videí s autoPlay |
| `FullscreenMediaViewer.tsx` | Fullscreen galerie s navigací, quality selector |
| `GenerationDataPanel.tsx` | Panel s metadata (prompt, seed, model, atd.) |
| `BrowsePage.tsx` | Browse Civitai - **CÍL PHASE 5** |
| `PacksPage.tsx` | Seznam packů - hotovo |
| `PackDetailPage.tsx` | Detail packu - hotovo |
| `ImportWizardModal.tsx` | Wizard pro import s výběrem verzí |

---

## ⚠️ Kritické vzory (DODRŽOVAT!)

### Video autoPlay systém (z BrowsePage)
```typescript
<MediaPreview
  src={url}
  type={media_type}                    // 'image' | 'video'
  thumbnailSrc={thumbnail_url}         // Pro videa - statický snímek
  nsfw={isNsfw}
  aspectRatio="portrait"
  autoPlay={true}                      // ← Automatické přehrávání
  playFullOnHover={true}               // ← Priorita na hover
  onClick={(e) => {
    e.preventDefault()
    e.stopPropagation()                // ← Zabrání Link navigaci!
    openFullscreen()
  }}
/>
```

### Civitai URL transformace
- **Thumbnail:** `?anim=false&transcode=true&width=450` (statický snímek)
- **Video:** `?transcode=true&width=450` + `.mp4` (pro playback)
- Civitai vrací videa s `.jpeg` příponou - nutná transformace!

### FullscreenMediaViewer items
```typescript
interface FullscreenMediaItem {
  url: string
  type?: 'image' | 'video' | 'unknown'
  thumbnailUrl?: string
  nsfw?: boolean
  width?: number
  height?: number
  meta?: Record<string, any>           // ← Pro GenerationDataPanel!
}
```

---

## 🧪 Testování

### Požadavky
- Každá feature MUSÍ mít testy
- Backend: pytest v `tests/unit/` nebo `tests/integration/`
- Frontend: Vitest v `apps/web/src/__tests__/`

### Spuštění
```bash
# Všechny Python testy
pytest tests/ -v

# Všechny frontend testy
cd apps/web && pnpm test

# Konkrétní test soubor
pytest tests/unit/test_media_detection.py -v
```

---

## 📋 Aktuální práce: Phase 5 - Internal Civitai Search (tRPC)

**Viz:** `plans/PLAN-Internal-Search-trpc.md`

### Hlavní cíle:
1. ❌ Backend search router (`/api/search/models`)
2. ❌ Search service s cachováním
3. ❌ Frontend API client
4. ❌ BrowsePage integrace
5. ❌ Local pack enrichment
6. ❌ Offline fallback

**STATUS:** 🚧 PLANNING

---

## 📚 Archiv fází

| Fáze | Soubor | Stav |
|------|--------|------|
| Phase 4 | `plans/PLAN-Phase-4.md` | ✅ DOKONČENO |
| Phase 5 | `plans/PLAN-Internal-Search-trpc.md` | 🚧 AKTIVNÍ |

---

## 🔄 Workflow při nové session

1. **Přečíst CLAUDE.md** (automaticky)
2. **Přečíst aktivní PLAN soubor** - zjistit aktuální stav
3. **Pokračovat od prvního ❌ nebo ⚠️ bodu**
4. **Po dokončení tasku:**
   - Aktualizovat PLAN (aditivně!)
   - Označit stav integrace
   - Ověřit testy

---

## 🚨 Co NEDĚLAT

- ❌ Nemazat text z PLAN souboru
- ❌ Neimplementovat bez plánu
- ❌ Nevytvářet nové komponenty, když existují (MediaPreview, GenerationDataPanel)
- ❌ Nepřeskakovat integraci - implementace bez integrace = nefunkční
- ❌ Nezapomínat na testy
- ❌ Neměnit existující API kontrakty bez migrace
- ❌ NEPRACOVAT na Phase 4 - ta je dokončena!

---

## 📝 Konvence kódu

### TypeScript/React
- Používat TypeScript strict mode
- Props interface vždy definovat
- Hooks na začátku komponenty
- Event handlery: `handleXxx` nebo `onXxx`

### Python
- Type hints všude
- Dataclasses pro modely
- Pydantic pro API modely
- Docstrings pro veřejné funkce

### Git
- Commit messages anglicky
- Format: `type: short description`
- Types: feat, fix, refactor, test, docs

---

*Poslední aktualizace: 2026-01-22*
*Aktivní fáze: Phase 5 - Internal Search (tRPC)*
