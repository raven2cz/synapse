# Synapse - Claude Code Project Memory

## 🎯 Základní pravidla

### Komunikace
- **S uživatelem:** Česky
- **Kód, komentáře, JSDoc, commit messages:** Anglicky
- **Dokumentace:** Anglicky (pokud uživatel neurčí jinak)

### Jediný zdroj pravdy
**`plans/PLAN-Model-Inventory.md`** je JEDINÝ soubor, který určuje:
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
│   ├── PLAN-Internal-Search-trpc.md # ✅ DOKONČENO - Interní vyhledávání
│   ├── PLAN-Phase-6-Store-UI.md     # ✅ DOKONČENO - Store UI zmapování
│   ├── PLAN-Model-Inventory.md      # 🚧 AKTIVNÍ - Model Inventory & Backup
│   └── PLAN-Blob-Manifest.md        # 🚧 AKTIVNÍ - Blob Manifest (orphan metadata)
├── tests/            # Python tests (pytest) - viz sekce Testování
│   ├── conftest.py   # Globální fixtures a markery
│   ├── unit/         # Rychlé, izolované testy (zrcadlí src/)
│   │   ├── core/     # src/core/ testy
│   │   ├── clients/  # src/clients/ testy
│   │   └── utils/    # src/utils/ testy
│   ├── store/        # Store/API testy
│   ├── integration/  # Multi-component testy
│   ├── lint/         # Architecture enforcement
│   └── helpers/      # Sdílené test fixtures
├── scripts/          # Utility skripty
│   └── verify.sh     # ⭐ HLAVNÍ verifikační skript
└── config/           # Configuration files
```

---

## 🔧 Důležité příkazy

### ⭐ Verifikace projektu (VŽDY před commitem!)
```bash
./scripts/verify.sh            # Kompletní verifikace
./scripts/verify.sh --quick    # Rychlá verifikace
./scripts/verify.sh --help     # Zobrazit všechny možnosti
```

### Backend (Python)
```bash
# Testy přes verify.sh (doporučeno)
./scripts/verify.sh --backend

# Přímé spuštění pytest
uv run pytest tests/ -v
uv run pytest tests/unit/core/test_pack_builder_video.py -v

# Spustit backend server
uv run uvicorn src.store.api:app --reload --port 8000
```

### Frontend (Web)
```bash
cd apps/web

pnpm install          # Instalace závislostí
pnpm dev              # Dev server
pnpm test --run       # Testy (single run)
pnpm build            # Production build
```

---

## 🏗️ Architektura - Klíčové komponenty

### Backend
| Soubor | Účel |
|--------|------|
| `src/core/pack_builder.py` | Import packů z Civitai, stahování preview |
| `src/store/pack_service.py` | CRUD operace nad packy |
| `src/store/api.py` | FastAPI routery pro packy a inventory (v2) |
| `src/store/inventory_service.py` | Blob inventory, cleanup, impacts, verification |
| `src/store/backup_service.py` | Backup storage: backup/restore/sync operace |
| `src/store/cli.py` | **🆕** Typer CLI: inventory, backup, profiles, packs |
| `src/utils/media_detection.py` | Detekce typu média (image/video), URL transformace |
| `src/clients/civitai_client.py` | Civitai API client |

### Frontend
| Soubor | Účel |
|--------|------|
| `MediaPreview.tsx` | **HLAVNÍ** komponenta pro zobrazení obrázků/videí s autoPlay |
| `FullscreenMediaViewer.tsx` | Fullscreen galerie s navigací, quality selector |
| `GenerationDataPanel.tsx` | Panel s metadata (prompt, seed, model, atd.) |
| `BrowsePage.tsx` | Browse Civitai - hotovo |
| `PacksPage.tsx` | Seznam packů - hotovo |
| `PackDetailPage.tsx` | Detail packu - hotovo |
| `ImportWizardModal.tsx` | Wizard pro import s výběrem verzí |
| **🆕 `InventoryPage.tsx`** | **Model Inventory** - správa blob storage a backupů |
| **🆕 `BlobsTable.tsx`** | Tabulka blobů s sorting, filtering, bulk actions |
| **🆕 `InventoryStats.tsx`** | Dashboard karty: Local Disk, Backup, Status, Quick Actions |

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

## 🧪 Testování a Verifikace

### ⭐ Hlavní příkaz: verify.sh

**VŽDY použij `./scripts/verify.sh` před commitem!**

```bash
# Kompletní verifikace (doporučeno před commitem)
./scripts/verify.sh

# Rychlá verifikace (bez build, bez slow testů)
./scripts/verify.sh --quick

# Pouze backend testy
./scripts/verify.sh --backend

# Pouze frontend testy
./scripts/verify.sh --frontend

# Specifické test kategorie
./scripts/verify.sh --backend --unit        # Pouze unit testy
./scripts/verify.sh --backend --integration # Pouze integrační
./scripts/verify.sh --backend --store       # Pouze store testy
./scripts/verify.sh --lint                  # Architektura check

# Verbose výstup
./scripts/verify.sh --verbose

# Nápověda
./scripts/verify.sh --help
```

### Struktura testů (Backend)

```
tests/
├── conftest.py          # Globální fixtures + pytest markery
├── helpers/
│   └── fixtures.py      # FakeCivitaiClient, TestStoreContext, assertions
├── unit/                # Rychlé, izolované testy
│   ├── core/            # test_pack_builder_video.py, test_parameters.py
│   ├── clients/         # test_civarchive.py
│   └── utils/           # test_media_detection.py
├── store/               # Store/API testy
├── integration/         # Multi-component testy
└── lint/                # Architecture enforcement (test_architecture.py)
```

### Pytest Markery

```python
@pytest.mark.slow         # Dlouhotrvající testy
@pytest.mark.integration  # Vyžadují více komponent
@pytest.mark.civitai      # Civitai API testy
@pytest.mark.e2e          # End-to-end testy
```

Použití:
```bash
uv run pytest -m "not slow"           # Bez pomalých testů
uv run pytest -m "integration"        # Pouze integrační
uv run pytest -m "not integration"    # Bez integračních
```

### Jak psát testy

#### 1. Umístění testů
- `tests/unit/core/` → pro `src/core/`
- `tests/unit/utils/` → pro `src/utils/`
- `tests/unit/clients/` → pro `src/clients/`
- `tests/integration/` → pro testy více komponent

#### 2. Pojmenování
```python
# Soubor: test_<module_name>.py
# Třída: Test<FeatureName>
# Metoda: test_<what_it_tests>

class TestMediaDetection:
    def test_detect_video_by_extension(self):
        ...
```

#### 3. Použití fixtures (z conftest.py)
```python
def test_with_fixtures(
    fake_civitai_client,     # FakeCivitaiClient instance
    test_store_context,      # Izolovaný test store
    civitai_video_url,       # Sample Civitai video URL
    temp_dir,                # Temporary directory
):
    ...
```

#### 4. Parametrizované testy
```python
@pytest.mark.parametrize("url,expected", [
    ("https://example.com/video.mp4", MediaType.VIDEO),
    ("https://example.com/image.jpg", MediaType.IMAGE),
])
def test_detect_media_type(url, expected):
    assert detect_media_type(url).type == expected
```

### Frontend testy (Vitest)

```bash
cd apps/web
pnpm test              # Watch mode
pnpm test --run        # Single run (CI)
pnpm test -- --ui      # UI mode
```

Umístění: `apps/web/src/__tests__/`

### Požadavky na testy

1. **Každá feature MUSÍ mít testy**
2. **Testy musí projít před commitem** → `./scripts/verify.sh`
3. **Nové soubory v src/ = nové testy v tests/**
4. **Při bugfixu přidat test na regrese**

---

## 📋 Aktuální práce: Model Inventory

**Viz:** `plans/PLAN-Model-Inventory.md`

### Hlavní cíle:

Model Inventory je **PRIMÁRNÍ feature** store - nová hlavní záložka pro správu blobů a backup storage.

**Iterace 1: Backend - Inventory Service** ✅ DOKONČENO
- ✅ `inventory_service.py` - kompletní služba (300+ řádků)
- ✅ Modely v `models.py` (BlobStatus, BlobLocation, InventoryItem, atd.)
- ✅ Integrace do `Store` třídy
- ✅ API endpointy (`/api/store/inventory/*`)
- ✅ Backend testy (21 testů v `test_inventory.py`)

**Iterace 2: Backend - Backup Storage** ✅ DOKONČENO
- ✅ `backup_service.py` (~450 řádků)
- ✅ backup/restore/sync operace
- ✅ Backup API endpointy (7 endpointů)
- ✅ Guard rails (is_last_copy, delete warning)
- ✅ Location detection v inventory
- ✅ Backend testy (29 testů v `test_backup.py`)

**Iterace 3: CLI** ✅ DOKONČENO
- ✅ `synapse inventory` subcommand (list, orphans, missing, cleanup, impacts, verify)
- ✅ `synapse backup` subcommand (status, sync, blob, restore, delete, config)
- ✅ Rich formatting, progress spinners
- ✅ CLI testy (34 testů v `test_cli.py`)

**Iterace 4: UI Dashboard & BlobsTable** ✅ DOKONČENO
- ✅ `InventoryPage.tsx` - hlavní stránka s React Query
- ✅ `InventoryStats.tsx` - dashboard karty (Local Disk, Backup, Status, Quick Actions)
- ✅ `BlobsTable.tsx` - 🔥 HLAVNÍ KOMPONENTA (~450 řádků)
  - Všechny sloupce (Checkbox, Icon, Name, Type, Size, Status, Location, Used By, Actions)
  - Sortable headers, bulk selection, context menu
  - Quick actions (Backup/Restore/Delete)
- ✅ Helper komponenty: `LocationIcon`, `StatusBadge`, `AssetKindIcon`
- ✅ `InventoryFilters.tsx` - search + kind/status/location dropdowns
- ✅ Navigace v `Sidebar.tsx` ("Model Inventory" mezi Packs a Profiles)
- ✅ Route `/inventory` v `App.tsx`
- ✅ TypeScript typy v `types.ts`, utility v `utils.ts`

**Iterace 5-6: UI Wizards & Integrace** ❌ ČEKÁ
- ❌ CleanupWizard, BackupSyncWizard, DeleteConfirmationDialog
- ❌ ImpactsDialog, VerifyProgress
- ❌ Frontend testy, E2E testy

**STATUS:** 🚧 ITERACE 5 - UI WIZARDS & DIALOGS

---

## 📚 Archiv fází

| Fáze | Soubor | Stav |
|------|--------|------|
| Phase 4 | `plans/PLAN-Phase-4.md` | ✅ DOKONČENO |
| Phase 5 | `plans/PLAN-Internal-Search-trpc.md` | ✅ DOKONČENO |
| Phase 6 | `plans/PLAN-Phase-6-Store-UI.md` | ✅ DOKONČENO |
| **Model Inventory** | `plans/PLAN-Model-Inventory.md` | 🚧 AKTIVNÍ |
| **Blob Manifest** | `plans/PLAN-Blob-Manifest.md` | 🚧 AKTIVNÍ (v2.2.0) |

---

## 🔄 Workflow při nové session

1. **Přečíst CLAUDE.md** (automaticky)
2. **Přečíst aktivní PLAN soubor** - zjistit aktuální stav
3. **Pokračovat od prvního ❌ nebo ⚠️ bodu**
4. **Po dokončení tasku:**
   - Aktualizovat PLAN (aditivně!)
   - Označit stav integrace
   - **Spustit `./scripts/verify.sh`** ← KRITICKÉ!

### Workflow při vývoji feature

```
1. Implementovat feature
2. Napsat/aktualizovat testy
3. ./scripts/verify.sh --quick    # Rychlá kontrola
4. Opravit případné chyby
5. ./scripts/verify.sh            # Plná verifikace
6. Commit pouze pokud projde
```

---

## 🚨 Co NEDĚLAT

- ❌ Nemazat text z PLAN souboru
- ❌ Neimplementovat bez plánu
- ❌ Nevytvářet nové komponenty, když existují (MediaPreview, GenerationDataPanel)
- ❌ Nepřeskakovat integraci - implementace bez integrace = nefunkční
- ❌ Nezapomínat na testy
- ❌ Neměnit existující API kontrakty bez migrace
- ❌ NEPRACOVAT na Phase 4, 5, 6 - ty jsou DOKONČENY!
- ❌ NEPŘESKAKOVAT iterace Model Inventory - musí jít po sobě!

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

*Poslední aktualizace: 2026-01-24*
*Aktivní fáze: Model Inventory - Iterace 3 (CLI příkazy)*
