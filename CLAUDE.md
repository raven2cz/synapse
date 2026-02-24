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
│   └── PLAN-Blob-Manifest.md        # ✅ DOKONČENO - Blob Manifest (orphan metadata)
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
| `src/avatar/__init__.py` | Avatar-engine feature flag, version check |
| `src/avatar/config.py` | AvatarConfig dataclass, YAML loading, path resolution |
| `src/avatar/routes.py` | FastAPI router (6 endpoints), avatar-engine mount |
| `src/avatar/skills.py` | Skill loading, system prompt building |
| `src/avatar/ai_service.py` | AvatarAIService — drop-in AI parameter extraction |
| `src/avatar/mcp/store_server.py` | 21 MCP tools (Store, Civitai, Workflow, Dependencies) |

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
- **Thumbnail:** `anim=false,transcode=true,width=450` (statický snímek)
- **Video:** `anim=true,transcode=true,width=450` + `.mp4` (MUSÍ mít `anim=true`!)
- Civitai vrací videa s `.jpeg` příponou - nutná transformace!
- **Detaily viz:** `docs/CIVITAI-CDN-VIDEO.md`

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
├── unit/                # Rychlé, izolované testy (vše mockované)
│   ├── core/            # test_pack_builder_video.py, test_parameters.py
│   ├── clients/         # test_civarchive.py
│   ├── store/           # test_download_service.py (63 testů)
│   └── utils/           # test_media_detection.py
├── store/               # Store/API testy
├── integration/         # Multi-component + Smoke testy
│   ├── test_import_e2e.py              # Import flow E2E (15 testů)
│   ├── test_download_integration.py    # BlobStore/PackService/Store wiring (27 testů)
│   └── test_download_smoke.py          # Full lifecycle smoke (7 testů)
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
5. **Každá feature MUSÍ mít všechny tři typy testů** (viz níže)

### Typy testů (povinné pro každou feature)

#### Unit testy (`tests/unit/`)
- **Účel:** Testují jednu třídu/funkci izolovaně, všechny závislosti mockované
- **Umístění:** `tests/unit/<module>/test_<name>.py` (zrcadlí `src/`)
- **Jak psát:**
  - Mockovat vše mimo testovanou jednotku (`unittest.mock.patch`, `MagicMock`)
  - Testovat happy path, edge cases, error handling
  - Pokrýt všechny veřejné metody
  - Regresní testy pro opravené bugy
- **Příklad:** `tests/unit/store/test_download_service.py` — testuje DownloadService s mockovaným `requests.Session`

```python
# Unit test pattern
class TestDownloadToFile:
    def test_basic_download(self, tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"data"]
        # ... mock HTTP, test only DownloadService logic
```

#### Integrační testy (`tests/integration/`)
- **Účel:** Testují interakci mezi 2+ komponentami, HTTP stále mockované
- **Umístění:** `tests/integration/test_<feature>.py`
- **Jak psát:**
  - Používat reálné třídy (BlobStore, PackService, Store), mockovat jen HTTP/external
  - Testovat správné propojení (wiring) — předávání závislostí, delegaci volání
  - Testovat error propagaci mezi vrstvami
  - Testovat lifecycle operace (cache clear before/after)
- **Příklad:** `tests/integration/test_download_integration.py` — testuje BlobStore→DownloadService delegaci, Store wiring

```python
# Integration test pattern
class TestBlobStoreDownloadDelegation:
    def test_download_http_delegates_to_service(self, tmp_path):
        mock_ds = MagicMock(spec=DownloadService)
        blob_store = BlobStore(layout, download_service=mock_ds)
        blob_store._download_http(url, expected_sha256=sha256)
        mock_ds.download_to_file.assert_called_once()
```

#### Smoke / E2E testy (`tests/integration/test_*_smoke.py`)
- **Účel:** Testují celý flow od začátku do konce, mockované jen HTTP volání
- **Umístění:** `tests/integration/test_<feature>_smoke.py`
- **Jak psát:**
  - Používat reálný Store (s `tmp_path` jako root)
  - Fake Civitai client s realistickými daty
  - Mockovat `requests.Session` / `requests.get` (ne interní třídy)
  - Testovat celý lifecycle: import → list → check updates → verify files
  - Testovat souběžnost a thread safety
- **Příklad:** `tests/integration/test_download_smoke.py` — testuje import flow, auth injection, cache deduplication

```python
# Smoke test pattern
class TestImportFlowSmoke:
    def test_import_creates_pack_with_download_service(self, smoke_store):
        store, fake_civitai = smoke_store
        with patch("src.store.download_service.requests.Session", ...):
            pack = store.import_civitai(url="https://civitai.com/models/1001")
        assert pack is not None
        assert (store.layout.packs_path / pack.name / "pack.json").exists()
```

### Test Pyramid

```
        /\
       /  \        Smoke/E2E (7+)   — celé flows, reálný Store
      /    \       ← pomalější, méně testů
     /------\
    /        \     Integrační (27+)  — 2+ komponenty, mockovaný HTTP
   /          \    ← střední rychlost
  /------------\
 /              \  Unit (63+)       — 1 třída, vše mockované
/________________\ ← nejrychlejší, nejvíc testů
```

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
| Phase 6 | `plans/PLAN-Phase-6-Store-UI.md` | ✅ DOKONČENO (Část B → PLAN-Model-Inventory) |
| **Model Inventory** | `plans/PLAN-Model-Inventory.md` | ✅ DOKONČENO |
| **Blob Manifest** | `plans/PLAN-Blob-Manifest.md` | ✅ DOKONČENO (v2.2.0) |
| **i18n** | `plans/PLAN-i18n.md` | ✅ DOKONČENO (v1.0.0) |
| **CDN Video Fix** | `plans/PLAN-CDN-Video-Fix.md` | ✅ DOKONČENO (anim=true, smoke testy) |

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
2. Napsat/aktualizovat testy (unit + integration + smoke/E2E)
3. ./scripts/verify.sh --quick    # Rychlá kontrola
4. Opravit případné chyby
5. ./scripts/verify.sh            # Plná verifikace
6. Commit pouze pokud projde
```

### ⭐ POVINNÉ: Review po každé iteraci/fázi

Po dokončení každé iterace (nejen před commitem) provést **3 nezávislé review**:

#### 1. Claude review (automatický)
Přečíst KAŽDÝ nový/změněný soubor, zkontrolovat:
- Error handling (žádné tiché `except: pass`)
- Thread safety, validace vstupů, import guardy
- Cachování (žádné zbytečné I/O na každém requestu)

#### 2. Gemini review (přímé CLI ze synapse adresáře)
```bash
# Z kořene synapse projektu:
gemini -p "You are a senior code reviewer. Review the following files for bugs, security issues, missing error handling, and code quality: <seznam souborů>. Provide numbered issues with severity." --yolo
```

#### 3. Codex review (přímé CLI ze synapse adresáře)
```bash
# Z kořene synapse projektu — VŽDY specifikovat scope (commit/soubory):
codex review --commit <SHA>                  # Review konkrétního commitu
codex exec "Review these files for bugs, security, error handling: <seznam souborů>"  # Explicitní seznam
```
**POZOR:** `codex review --uncommitted` reviewuje CELÉ repo diff, ne jen konkrétní fázi! Proto vždy specifikovat buď commit SHA nebo explicitní seznam souborů.

#### Alternativně: přes avatar-engine
```bash
cd ~/git/github/avatar-engine && uv run avatar -w /home/box/git/github/synapse \
  chat -p gemini --yolo --no-stream "<review prompt>"
```
**Pozor:** `-w` flag musí být PŘED subcommandem `chat`. Přímé CLI je spolehlivější pro cross-repo review.

#### Avatar-engine info
- **Umístění:** `~/git/github/avatar-engine`
- **Spuštění (avatar CLI):** `cd ~/git/github/avatar-engine && uv run avatar chat -p <provider> ...`
- **Přímé CLI:** `gemini -p "..."` / `codex review` / `codex exec "..."`
- **Providery:** `gemini`, `claude`, `codex`
- **Dokumentace:** `~/git/github/avatar-engine/README.md`

#### Po review
1. **Zvalidovat** nálezy ze všech 3 review
2. **Implementovat** opravy pro validní nálezy
3. **Test pyramid** — ověřit, že existují VŠECHNY tři typy testů:
   - Unit testy (30-60): error paths, edge cases, all branches
   - Integration testy (8-15): reálné komponenty, mockovaný HTTP
   - Smoke/E2E testy (3-7): celý lifecycle, reálný Store
4. **Zaznamenat do PLANu** — stav, počet testů, nalezené issues, kdo co našel

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

## 🤖 Avatar Engine Documentation

Avatar-related docs live in `docs/avatar/`. See `docs/avatar/README.md` for navigation.

| Doc | Purpose |
|-----|---------|
| `docs/avatar/getting-started.md` | Setup & first chat |
| `docs/avatar/configuration.md` | avatar.yaml reference |
| `docs/avatar/mcp-tools-reference.md` | All 21 MCP tools |
| `docs/avatar/skills-and-avatars.md` | Custom skills & avatars |
| `docs/avatar/theming.md` | CSS theming |
| `docs/avatar/architecture.md` | Developer reference |
| `docs/avatar/troubleshooting.md` | Common issues |

### Pravidla pro Avatar dokumentaci
- Změna v `src/avatar/` → aktualizovat relevantní docs v `docs/avatar/`
- Nové MCP tools → přidat do `docs/avatar/mcp-tools-reference.md`
- Nové skills → přidat do `docs/avatar/skills-and-avatars.md`
- Config změny → aktualizovat `docs/avatar/configuration.md` + `config/avatar.yaml.example`
- Nové frontend avatar komponenty → aktualizovat `docs/avatar/architecture.md`

---

## 🐛 Known Issues & Lessons Learned

### Civitai CDN & Video playback (2026-02-22)
`<video>` v MediaPreview MUSÍ mít `autoPlay` atribut a `src=` (NIKDY `<source>` children).
Videa NESMÍ být omezována (žádný MAX_CONCURRENT). Viz `docs/CIVITAI-CDN-VIDEO.md`.

### CSS overflow u collapsible sekcí (2026-02-17)
**Problém:** Pack detail sekce s `transition-[max-height]` a `max-h-[Npx]` BEZ `overflow-hidden`
způsobí, že obsah přesahující max-height přeteče vizuálně přes další sekce. Card má poloprůhledné
pozadí (`bg-slate-deep/50`), takže přetečený obsah (obrázky z Civitai HTML description) prosvítá.

**Pravidlo:** Každý collapsible wrapper MUSÍ mít:
- `overflow-hidden` jako base class (vždy, nejen v collapsed stavu)
- Dostatečně velký `max-h` pro expanded stav (`max-h-[10000px]`)
- `overflow-y-auto` pouze v collapsed stavu pro scrollování

**Dotčené soubory:**
- `PackInfoSection.tsx` (DescriptionCard) - opraveno
- `PackGallery.tsx` - bylo OK (`overflow-hidden` bylo)
- `PackParametersSection.tsx` - bylo OK (`overflow-hidden` bylo)

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

*Poslední aktualizace: 2026-02-24*
*Aktivní fáze: Avatar Engine - Iterace 9 (Dokumentace)*
