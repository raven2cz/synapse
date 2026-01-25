# Phase 6: Store UI & Infrastructure

**Status:** 🚧 AKTIVNÍ
**Vytvořeno:** 2026-01-24
**Poslední aktualizace:** 2026-01-24 (Phase 6.A kompletní + CLI refactor)

---

## Přehled

Phase 6 má dvě části:
- **Část A:** Zmapování a konsolidace Store infrastruktury
- **Část B:** Nový UI tab Inventory/Store (později)

---

# ČÁST A: Store Infrastructure Mapping

## A.1 Architektura Store

### A.1.1 Adresářová struktura

```
~/.synapse/store/
├── state/                          # Git-verzované (lze sdílet)
│   ├── config.json                 # Store konfigurace
│   ├── ui_sets.json                # UI set definice (local, all, comfyui, ...)
│   ├── packs/<PackName>/
│   │   ├── pack.json               # Pack definice (dependencies, previews, metadata)
│   │   ├── lock.json               # Resolved artifacts s SHA256
│   │   └── resources/previews/     # Stažené preview obrázky/videa
│   └── profiles/<ProfileName>/
│       └── profile.json            # Seznam packů v profilu
│
└── data/                           # Lokální runtime (nikdy do gitu)
    ├── blobs/sha256/<ab>/<sha256>  # Content-addressable storage
    ├── views/<ui>/
    │   ├── profiles/<profile>/     # Symlink stromy per profil
    │   │   └── models/<kind>/      # Symlinky do blobů
    │   └── active -> profiles/<x>  # Aktivní profil symlink
    ├── runtime.json                # Stack profilů per UI
    ├── cache/                      # Cache
    ├── tmp/                        # Temp soubory
    └── .synapse.lock               # File lock
```

### A.1.2 Klíčové komponenty (src/store/)

| Soubor | Účel | Status |
|--------|------|--------|
| `layout.py` | Cesty, atomic JSON I/O, file locking | ✅ IMPL+INTEG |
| `blob_store.py` | SHA256 content-addressable storage | ✅ IMPL+INTEG |
| `view_builder.py` | Symlink stromy, last-wins konflikty | ✅ IMPL+INTEG |
| `profile_service.py` | Use/back workflow, profile management | ✅ IMPL+INTEG |
| `ui_attach.py` | Napojení UIs (symlink/YAML) | ✅ IMPL+INTEG |
| `pack_service.py` | Pack CRUD, import, resolve | ✅ IMPL+INTEG |
| `update_service.py` | Check/apply updates | ✅ IMPL+INTEG |
| `api.py` | FastAPI routers | ✅ IMPL+INTEG |
| `cli.py` | Typer CLI | ✅ IMPL+INTEG |
| `models.py` | Pydantic modely | ✅ IMPL+INTEG |

---

## A.2 Profile System - Detailní popis

### A.2.1 Co je profil?

Profil = seznam packů v určeném pořadí s "last wins" strategií pro konflikty.

**Typy profilů:**
- `global` - Výchozí profil se všemi packy. Nelze smazat.
- `work__<PackName>` - Pracovní profil pro fokusovanou práci s packem

### A.2.2 Runtime Stack

Každé UI má vlastní stack profilů v `runtime.json`:

```json
{
  "schema": "synapse.runtime.v1",
  "ui": {
    "comfyui": { "stack": ["global"] },
    "forge": { "stack": ["global", "work__Juggernaut_XL"] }
  }
}
```

**Stack pravidla:**
- Stack vždy obsahuje minimálně `["global"]`
- Aktivní profil = vrchol stacku (`stack[-1]`)
- `push_profile()` přidá na vrchol
- `pop_profile()` odebere z vrcholu (ale nikdy `global`)

### A.2.3 Use/Back Workflow

**USE příkaz:**
```
synapse use <pack> [--ui-set local] [--sync]
```

1. Ověří, že pack existuje
2. Vytvoří/aktualizuje `work__<pack>` profil:
   - Kopie global, ale `<pack>` přesunut na konec (last wins)
3. Pushne `work__<pack>` na stack všech UI v ui_set
4. Pokud `--sync`: Build views + activate

**BACK příkaz:**
```
synapse back [--ui-set local] [--sync]
```

1. Pop ze stacku všech UI v ui_set
2. Aktivuje předchozí profil
3. Pokud `--sync`: Rebuild views

**RESET příkaz:**
```
POST /api/profiles/reset
```

1. Nastaví stack na `["global"]` pro všechna UI
2. Rebuild views

### A.2.4 View System

Views jsou symlink stromy:

```
data/views/comfyui/
├── profiles/
│   ├── global/
│   │   └── models/
│   │       ├── checkpoints/model.safetensors -> ../../blobs/sha256/ab/abc...
│   │       └── loras/lora.safetensors -> ../../blobs/sha256/cd/cde...
│   └── work__Juggernaut_XL/
│       └── models/...
└── active -> profiles/work__Juggernaut_XL
```

**Build proces:**
1. `compute_plan()` - Iteruje packs v pořadí, aplikuje last-wins
2. `build()` - Vytvoří symlinky ve staging, pak atomic replace
3. `activate()` - Update `active` symlinku

---

## A.3 UI Attachment System

### A.3.1 Dva způsoby napojení

**1. ComfyUI - extra_model_paths.yaml (preferovaný)**
```yaml
synapse:
  checkpoints: /path/to/store/data/views/comfyui/active/models/checkpoints
  loras: /path/to/store/data/views/comfyui/active/models/loras
  ...
```
- Modely na root úrovni (ne v subfolderu)
- Kritické pro Civitai generation data kompatibilitu
- Automatický backup při prvním attach

**2. Forge/A1111/SDNext - Symlinky**
```
Forge/models/Lora/synapse -> /path/to/views/forge/active/models/Lora
```
- Modely v `synapse/` subfolderu

### A.3.2 UI Kind Mapping

`config.json` obsahuje mapování asset kindů na cesty per UI:

```json
{
  "ui": {
    "kind_map": {
      "comfyui": {
        "checkpoint": "models/checkpoints",
        "lora": "models/loras",
        ...
      },
      "forge": {
        "checkpoint": "models/Stable-diffusion",
        "lora": "models/Lora",
        ...
      }
    }
  }
}
```

---

## A.4 API Endpoints

### A.4.1 Store Router (`/api/store/`)

| Method | Endpoint | Popis |
|--------|----------|-------|
| POST | `/init` | Inicializace store |
| GET | `/config` | Získat konfiguraci |
| GET | `/status` | Aktuální status |
| POST | `/doctor` | Diagnostika a opravy |
| POST | `/clean` | Vyčištění tmp/cache |
| POST | `/attach` | Připojit UIs k views |
| POST | `/detach` | Odpojit UIs |
| GET | `/attach-status` | Status připojení |

### A.4.2 Profiles Router (`/api/profiles/`)

| Method | Endpoint | Popis |
|--------|----------|-------|
| GET | `/` | Seznam profilů |
| GET | `/status` | Kompletní status (stack per UI, shadowed) |
| POST | `/use` | Aktivovat work profil |
| POST | `/back` | Návrat na předchozí profil |
| POST | `/sync` | Sync profilu (install + build views) |
| POST | `/reset` | Reset na global |
| GET | `/{name}` | Detail profilu |

### A.4.3 Packs Router (`/api/v2/packs/`)

| Method | Endpoint | Popis |
|--------|----------|-------|
| GET | `/` | Seznam packů |
| GET | `/{name}` | Detail packu |
| POST | `/import` | Import z Civitai |
| POST | `/{name}/install` | Install blobů |
| POST | `/{name}/resolve` | Resolve dependencies |
| DELETE | `/{name}` | Smazat pack |

---

## A.5 CLI Příkazy

**✅ REFAKTOROVÁNO 2026-01-24: Rich library pro profesionální výstup**

CLI nyní používá:
- **Rich library** pro formátování (tabulky, panely, barvy)
- **Konzistentní ikony**: ✓ (success), ✗ (error), ⚠ (warning), ℹ (info)
- **Všechny příkazy mají `--json` flag** pro strojové zpracování

### A.5.1 Store Management

```bash
synapse store init [--force]     # Inicializace
synapse store config [--json]    # Zobrazit konfiguraci (Rich tabulka)
```

### A.5.2 Pack Operations

```bash
synapse list [--json]                    # Seznam packů (Rich tabulka)
synapse show <pack> [--json]             # ✅ NOVÉ: Detail packu (panel + tabulka)
synapse import <url> [--no-previews]     # Import z Civitai
synapse install <pack>                   # Stáhnout bloby
synapse resolve <pack>                   # Resolve dependencies
synapse delete <pack> [--force] [--json] # Smazat pack (vrací DeleteResult)
```

### A.5.3 Profile/Use Operations

```bash
synapse use <pack> [--ui-set local] [--sync]   # Aktivovat work profil
synapse back [--ui-set local] [--sync]         # Návrat
synapse reset [--ui-set local] [--sync] [--json] # ✅ NOVÉ CLI: Reset na global
synapse sync [profile] [--ui-set local]        # Sync profilu
synapse status [--ui-set local] [--json]       # Aktuální stav (Rich tabulka)
synapse profiles list [--json]                 # ✅ NOVÉ: Seznam profilů
synapse profiles show <name> [--json]          # ✅ NOVÉ: Detail profilu
```

### A.5.4 UI Attachment ✅ NOVÉ

```bash
synapse attach [--ui-set local] [--json]         # Připojit UIs k views
synapse detach [--ui-set local] [--json]         # Odpojit UIs
synapse attach-status [--ui-set local] [--json]  # Status připojení (Rich tabulka)
```

### A.5.5 Maintenance

```bash
synapse doctor [--rebuild-views] [--verify-blobs] [--json]  # Diagnostika
synapse clean [--tmp] [--cache] [--partial]                 # Vyčištění
synapse check-updates <pack> [--json]                       # Kontrola aktualizací jednoho packu
synapse check-all-updates [--json]                          # ✅ NOVÉ: Kontrola všech packů
synapse update <pack> [--dry-run] [--json]                  # Aktualizace
synapse search <query> [--json]                             # Vyhledávání
```

### A.5.6 Backup Operations ✅ NOVÉ (2026-01-24)

Tři úrovně granularity backup operací:

```
BLOB:   synapse backup blob/restore <sha256>    (single file)
PACK:   synapse backup pull/push <pack>         (all pack blobs)
ALL:    synapse backup sync                     (entire store)
```

**Pack-level příkazy:**
```bash
synapse backup pull <pack> [--execute] [--json]   # Restore pack blobs z backupu
synapse backup push <pack> [--execute] [--json]   # Backup pack blobs
synapse backup push <pack> --execute --cleanup    # Backup + smazat lokální kopie
```

**Use case:** Zůstat na global profilu, ale mít modely dostupné lokálně:
```bash
# Uvolnit místo - zálohovat a smazat lokální
synapse backup push MyPack --execute --cleanup

# Později: obnovit modely BEZ aktivace work profilu
synapse backup pull MyPack --execute

# Modely jsou dostupné, zůstáváš na global
synapse status  # → profile: global
```

**Testy:** `tests/store/test_backup.py`
- `TestBackupPullPack` (4 testy)
- `TestBackupPushPack` (4 testy)
- `TestPullPushRoundTrip` (1 test)

### A.5.6 CLI vs API parita

| API Endpoint | CLI Příkaz | Status |
|--------------|------------|--------|
| `POST /store/init` | `synapse store init` | ✅ |
| `GET /store/config` | `synapse store config` | ✅ |
| `GET /store/status` | `synapse status` | ✅ |
| `POST /store/attach` | `synapse attach` | ✅ NOVÉ |
| `POST /store/detach` | `synapse detach` | ✅ NOVÉ |
| `GET /store/attach-status` | `synapse attach-status` | ✅ NOVÉ |
| `POST /store/doctor` | `synapse doctor` | ✅ |
| `GET /profiles/` | `synapse profiles list` | ✅ NOVÉ |
| `GET /profiles/{name}` | `synapse profiles show` | ✅ NOVÉ |
| `POST /profiles/reset` | `synapse reset` | ✅ NOVÉ |
| `GET /packs/` | `synapse list` | ✅ |
| `GET /packs/{name}` | `synapse show` | ✅ NOVÉ |
| `POST /packs/{name}/check-updates` | `synapse check-updates` | ✅ |
| N/A | `synapse check-all-updates` | ✅ NOVÉ (CLI only)

---

## A.6 Frontend UI komponenty

### A.6.1 ProfilesPage (`/profiles`)

**Soubor:** `apps/web/src/components/modules/ProfilesPage.tsx`

**Funkce:**
- Zobrazuje grid UI statusů (comfyui, forge, ...)
- Per-UI: aktivní profil, stack vizualizace
- Tlačítka Back a Reset
- Tabulka shadowed souborů

**API volání:**
- `GET /api/profiles/status` (polling 5s)
- `POST /api/profiles/back`
- `POST /api/profiles/reset`

### A.6.2 ProfileDropdown (v headeru)

**Soubor:** `apps/web/src/components/layout/ProfileDropdown.tsx`

**Funkce:**
- Dropdown s aktuálním profilem
- Stack vizualizace
- Quick Back/Reset akce
- Shadowed files warning badge

### A.6.3 PackDetailPage - Use Button

**Soubor:** `apps/web/src/components/modules/PackDetailPage.tsx`

**Funkce:**
- Tlačítko "Use" volá `POST /api/profiles/use`
- Po úspěchu invaliduje `profiles-status` query

---

## A.7 Test Coverage Analysis

### A.7.1 Existující testy (`tests/store/`)

| Soubor | Co testuje | Status |
|--------|------------|--------|
| `test_layout.py` | Init, pack/profile CRUD, paths, JSON I/O | ✅ OK |
| `test_blob_store.py` | SHA256, adopt, download, verify, dedup | ✅ OK |
| `test_views_profiles.py` | ViewBuilder, symlinks, use/back | ✅ OK |
| `test_api_critical.py` | UIAttacher, API smoke testy | ✅ OK |
| `test_e2e.py` | Use/back E2E workflow | ✅ OK |
| `test_pack_service_v2.py` | Pack service | ✅ OK |

### A.7.2 Chybějící testy / Mezery v pokrytí

| Oblast | Chybí | Priorita | Status |
|--------|-------|----------|--------|
| ~~Reset endpoint~~ | ~~Chybí test~~ | ~~🔴 HIGH~~ | ✅ PŘIDÁNO |
| ~~Delete pack cleanup~~ | ~~Nečistí work profily~~ | ~~🔴 HIGH~~ | ✅ PŘIDÁNO |
| ~~Kompletní workflow~~ | ~~E2E integrační test~~ | ~~🔴 HIGH~~ | ✅ PŘIDÁNO (5 testů) |
| ~~CLI (`cli.py`)~~ | ~~Žádné přímé testy CLI příkazů~~ | ~~🟢 LOW~~ | ✅ PŘIDÁNO (17 testů) |
| HTTP downloads | Pouze `file://` URL testovány | 🟢 LOW | ❌ |

### A.7.4 CLI Integrační testy (2026-01-24)

Přidáno do `test_e2e.py` - třída `TestCLIIntegration` (17 testů):

| Test | Popis |
|------|-------|
| `test_cli_init_creates_store` | Store init |
| `test_cli_list_empty` | Prázdný seznam packů |
| `test_cli_list_json` | JSON výstup |
| `test_cli_status` | Status display |
| `test_cli_status_json` | Status JSON |
| `test_cli_use_requires_pack` | Use validace |
| `test_cli_back_at_global` | Back na global |
| `test_cli_use_and_back_workflow` | Kompletní use/back workflow |
| `test_cli_doctor` | Doctor diagnostika |
| `test_cli_doctor_json` | Doctor JSON |
| `test_cli_clean` | Clean operace |
| `test_cli_config` | Config display |
| `test_cli_delete_nonexistent_pack` | Delete error handling |
| `test_cli_delete_pack` | Delete operace |
| `test_cli_reset_at_global` | Reset na global |
| `test_cli_reset_after_use` | Reset po use stacku |
| `test_cli_reset_json_output` | Reset JSON |

### A.7.3 Nové integrační testy (2026-01-24)

Přidáno do `test_e2e.py` - třída `TestCompleteUserWorkflow`:

| Test | Popis |
|------|-------|
| `test_full_workflow_init_to_cleanup` | Kompletní workflow: init → create packs → blobs → views → use/back → doctor → delete → clean |
| `test_shadowing_and_last_wins` | Test last-wins konfliktní rezoluce při stejných filenames |
| `test_blob_deduplication` | Ověření, že duplicitní content je uložen jen jednou |
| `test_multiple_ui_views` | Ověření různých cest pro ComfyUI vs Forge |
| `test_doctor_detects_issues` | Test detekce chybějících blobů |

---

## A.8 Nalezené problémy / Potenciální bugy

### A.8.1 ✅ Opravené bugy (2026-01-24)

1. **Reset endpoint** - ~~`view_builder.activate_profile("global", ui)` špatný název metody a pořadí argumentů~~
   - **BUG:** Metoda `activate_profile` neexistovala! Správně je `activate(ui, profile_name)`
   - **FIX:** Opraveno v `api.py:3020` na `activate(ui, "global")`
   - **EXTRA FIX:** Přidán try/except pro případ kdy view neexistuje
   - **TEST:** `TestResetEndpoint` (2 testy) v `test_api_critical.py`

2. **Race condition v use()/back()** - ~~Runtime modifikace bez locku~~
   - **BUG:** `use()` a `back()` v `profile_service.py` měnily `runtime.json` bez file locku
   - **FIX v profile_service.py:**
     - `use()` line 233-238: `with self.layout.lock():` kolem runtime operací
     - `back()` line 288-302: Kompletní přepsání s atomickým lockingem
   - **Vzor:**
     ```python
     with self.layout.lock():
         runtime = self.layout.load_runtime()
         # ... modifikace ...
         self.layout.save_runtime(runtime)
     ```

3. **Work profile cleanup** - ~~Když se smaže pack, work profily zůstanou orphaned~~
   - **BUG:** `delete_pack` neodstraňoval work profily ani z runtime stacku
   - **FIX:** Rozšířen `delete_pack` v `__init__.py:353-385` o:
     - Odstranění work profilu z runtime stacků všech UI
     - Smazání work profilu (`work__<pack>`)
   - **TEST:** `TestDeletePackCleanup` (4 testy) v `test_api_critical.py`

4. **Silent failures v delete_pack()** - ~~Chyby při cleanup se tiše ignorovaly~~
   - **BUG:** `delete_pack` vracel jen `True/False`, bez informací o problémech
   - **FIX:** Nový `DeleteResult` model v `models.py`:
     ```python
     class DeleteResult(BaseModel):
         pack_name: str
         deleted: bool
         cleanup_warnings: List[str]  # Zachycené problémy
         removed_from_global: bool
         removed_work_profile: bool
         removed_from_stacks: bool
     ```
   - **Změna v `__init__.py`:** `delete_pack()` nyní vrací `DeleteResult`
   - **TEST:** Aktualizován `test_delete_pack_handles_unused_pack`

5. **Doctor CLI bug** - ~~`packs_checked` a `orphaned_blobs` atributy neexistovaly~~
   - **BUG:** CLI v `doctor_command` používal atributy, které `DoctorReport` nemá
   - **FIX:** CLI opraveno v `cli.py:831-874` aby používal jen existující atributy

6. **Doctor JSON output** - ~~Progress message znečišťoval JSON~~
   - **BUG:** `console.print("[dim]Running diagnostics...[/dim]")` se tisklo před JSON
   - **FIX:** `if not json:` guard v `cli.py:822`

### A.8.2 ❓ Zbývá k prověření

7. **Shadowed warning** - UI zobrazuje shadowed pro první UI, ne per-UI? (Low priority)

### A.8.3 ✅ Ověřeno jako OK

- Profile stack logika (push/pop)
- Last-wins resolution
- Blob deduplication
- Atomic JSON writes
- File locking (layout.lock())

---

## A.9 TODO: Část A

### A.9.1 Zmapování ✅

- [x] Adresářová struktura
- [x] Store komponenty
- [x] Profile system
- [x] UI attachment
- [x] API endpointy
- [x] CLI příkazy
- [x] Frontend UI
- [x] Test coverage

### A.9.2 Verifikace a opravy ✅

- [x] ~~Ověřit reset endpoint bug~~ → **OPRAVENO** (api.py)
- [x] ~~Review race conditions~~ → **OPRAVENO** (profile_service.py - locking)
- [x] ~~Ověřit delete_pack cleanup~~ → **OPRAVENO** (__init__.py + DeleteResult)
- [x] Přidat testy:
  - [x] Reset endpoint testy (2 testy)
  - [x] Delete pack cleanup testy (4 testy)
  - [x] Kompletní workflow integrační testy (5 testů)
  - [x] **CLI integrační testy (17 testů)** ← NOVÉ

### A.9.3 CLI Refaktor ✅ NOVÉ

- [x] Rich library pro profesionální styling
- [x] Přidat chybějící příkazy:
  - [x] `synapse show <pack>`
  - [x] `synapse attach` / `detach` / `attach-status`
  - [x] `synapse profiles list` / `profiles show`
  - [x] `synapse check-all-updates`
  - [x] `synapse reset` (CLI pro existující API)
- [x] Opravit doctor command (neexistující atributy)
- [x] Opravit JSON output (progress message pollution)
- [x] 100% CLI vs API parita

### A.9.4 Dokumentace ✅

- [x] Aktualizovat tuto dokumentaci po verifikaci (2026-01-24)
- [x] **Aktualizovat po CLI refaktoru (2026-01-24)** ← NOVÉ

### A.9.5 Zbývající práce (nice to have)

- [ ] Update service testy (low priority)
- [ ] SQLite cache DB (není implementováno, jen placeholder)

---

# ČÁST B: Store UI (Inventory Tab)

**Status:** ⏳ ČEKÁ NA DOKONČENÍ ČÁSTI A

*Bude doplněno po dokončení Části A*

## B.1 Plánované funkce

- [ ] Nový tab "Inventory" nebo "Store"
- [ ] Přehled nainstalovaných blobů
- [ ] Disk usage statistiky
- [ ] Orphan blob cleanup
- [ ] UI attach status s vizuálním feedbackem
- [ ] Profile management UI

---

## A.10 Nové/Upravené modely (models.py)

### A.10.1 DeleteResult ✅ NOVÉ

```python
class DeleteResult(BaseModel):
    """Result of 'delete' command."""
    pack_name: str
    deleted: bool
    cleanup_warnings: List[str] = Field(default_factory=list)
    removed_from_global: bool = False
    removed_work_profile: bool = False
    removed_from_stacks: bool = False
```

### A.10.2 ResetResult ✅ NOVÉ

```python
class ResetResult(BaseModel):
    """Result of 'reset' command."""
    ui_targets: List[str]
    from_profiles: Dict[str, str]  # ui -> old profile
    to_profile: str  # always "global"
    synced: bool
    notes: List[str] = Field(default_factory=list)
```

### A.10.3 DoctorActions (existující)

```python
class DoctorActions(BaseModel):
    views_rebuilt: bool = False
    db_rebuilt: Optional[str] = None  # "auto", "force", or None (SQLite not implemented)
    blobs_verified: bool = False
```

### A.10.4 DoctorReport (existující)

```python
class DoctorReport(BaseModel):
    profile: str
    ui_targets: List[str]
    actions: DoctorActions
    active: Dict[str, str]
    missing_blobs: List[MissingBlob]
    unresolved: List[UnresolvedReport]
    shadowed: List[ShadowedEntry]
    notes: List[str]
```

---

## Poznámky

### Zdroje

- `src/store/` - Backend implementace
- `apps/web/src/components/` - Frontend komponenty
- `tests/store/` - Testy
- `.synapse/store/` - Reálná data (symlink do `~/.synapse/store`)

### Workflow při vývoji

1. Nejdřív dokončit Část A (verifikace, testy) ✅ DONE
2. Pak začít Část B (UI)
3. Vždy `./scripts/verify.sh` před commitem

### Test statistiky

```
Backend testy: 347 passed, 7 skipped
Store testy:   186 passed, 2 skipped
CLI testy:     17 passed
```

### Neimplementované placeholders

- **SQLite cache DB** - `layout.db_path` definuje cestu, ale není implementováno
- **Orphan blob cleanup** - placeholder v UI plánu

---

*Poslední aktualizace: 2026-01-24 - Část A kompletní + CLI refaktor s Rich library + race condition fixes + DeleteResult model*
