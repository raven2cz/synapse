# Model Inventory - Komplexni navrh

**Status:** ✅ DOKONČENO - Všechny iterace kompletní (2026-01-24)
**Vytvoreno:** 2026-01-24
**Autor:** Claude (na zaklade analyzy existujici architektury)
**Implementace zahájena:** 2026-01-24

---

## 1. Prehled a cile

### 1.1 Co je Model Inventory?

Model Inventory je **nova hlavni zalozka** v Synapse UI, ktera poskytuje:

1. **Prehled vsech modelu** (blobu) v content-addressable storage
2. **Statistiky diskoveho prostoru** s vizualizaci
3. **Detekci problemu** (orphans, missing, duplicity)
4. **Bezpecne nastroje pro uklid** s guard rails
5. **Pokrocile funkce** pro power users
6. **🆕 Backup Storage integrace** - externa zalohovaci zarizeni s plnou synchronizaci

### 1.2 Proc samostatna zalozka?

- **Dulezitost**: Sprava modelu je PRIMARNI feature store - dulezitejsi nez Profiles
- **Komplexnost**: Potrebuje vlastni prostor pro tabulky, grafy, filtry
- **Oddeleni**: Settings ma obsahovat jen konfiguraci, ne operace

### 1.3 Umisteni v navigaci

```
[Packs] [Model Inventory] [Profiles] [Browse Civitai] [Settings]
             ^^^                           ^^^
    PRIMARNI zalozka              Predposledni (budou dalsi browse zdroje)
```

**Proc toto poradi:**
- **Packs** - hlavni prace s packy (vlastni tvorba, import, management)
- **Model Inventory** - sprava fyzickych souboru/blobu
- **Profiles** - prepinani kontextu (use/back)
- **Browse Civitai** - predposledni, protoze v budoucnu budou dalsi zdroje (HuggingFace, lokalni import z obrazku s metadaty, atd.)
- **Settings** - konfigurace (vzdy posledni)

### 1.4 📚 Odkaz na dokumentaci

V UI MUSI byt odkaz na dokumentaci (HTML export z Markdown). Umisteni:
- **V headeru** nebo **v Settings** - odkaz "Documentation" / "Help"
- **V Model Inventory** - help ikona (?) vedle nazvu s tooltipem a odkazem
- **V BlobsTable** - help text vysvetlujici statusy a akce

Dokumentace bude obsahovat:
- Jak funguje blob storage (content-addressable, SHA256)
- Co znamenaji jednotlive statusy (REFERENCED, ORPHAN, MISSING, BACKUP_ONLY)
- Jak funguje backup storage a synchronizace
- CLI prikazy pro inventory a backup
- FAQ a troubleshooting

```tsx
// Priklad help linku v UI
<Button variant="ghost" size="sm" asChild>
  <a href="/docs/inventory" target="_blank">
    <HelpCircle className="w-4 h-4 mr-1" />
    Help
  </a>
</Button>
```

---

## 2. Architektura - Co uz mame

### 2.1 BlobStore (src/store/blob_store.py)

```python
# Existujici metody, ktere muzeme pouzit:
blob_store.list_blobs() -> List[str]        # Vsechny SHA256 hashe
blob_store.blob_exists(sha256) -> bool      # Existence
blob_store.blob_size(sha256) -> int         # Velikost v bytes
blob_store.remove_blob(sha256) -> bool      # Smazani
blob_store.verify(sha256) -> bool           # Overeni integrity
blob_store.verify_all() -> (valid, invalid) # Hromadne overeni
blob_store.get_total_size() -> int          # Celkova velikost
blob_store.clean_partial() -> int           # Uklid .part souboru
```

### 2.2 PackLock struktura (zdroj referenci)

```python
# state/packs/<PackName>/lock.json
PackLock:
  resolved: List[ResolvedDependency]
    - dependency_id: str
    - artifact:
        kind: AssetKind (checkpoint, lora, vae, ...)
        sha256: str           # <- REFERENCE NA BLOB
        size_bytes: int
        provider:
          name: ProviderName  # civitai, huggingface, local
          model_id: int       # Civitai model ID
          version_id: int     # Civitai version ID
          file_id: int        # Civitai file ID
          filename: str       # Original filename

# Pack dependency ma expose config:
PackDependency:
  expose:
    filename: str             # <- DISPLAY NAME pro blob
```

### 2.3 Existujici endpointy

```
GET  /api/store/status     - zakladni status
POST /api/store/doctor     - diagnostika
GET  /api/v2/packs/        - seznam packu
GET  /api/v2/packs/{name}  - detail packu s lock daty
```

---

## 2.5 🆕 Backup Storage - Klicova feature

### 2.5.1 Motivace

**Problem:**
- Modely jsou OBROVSKE (checkpoint 6-12GB, LoRA 100-500MB)
- Disky na pracovnich stanicich maji omezenou kapacitu
- Uzivatele potrebuji mazat modely, aby uvolnili misto
- ALE nechteji je ztratit - jen je "odlozit"
- Pri potrebe chteji model rychle ziskat zpet bez stahovani z internetu

**Reseni: Backup Storage**
- Externi disk (USB, NAS, sitovy disk)
- Obsahuje ZRCADLO blob storage
- Synapse vi, co je kde, a umi synchronizovat

### 2.5.2 Konfigurace (v Settings)

```json
// Pridano do config.json
{
  "backup": {
    "enabled": true,
    "path": "/mnt/external/synapse-backup",  // Linux: mount path
    // nebo: "D:\\SynapseBackup"              // Windows: drive letter
    "auto_backup_new": false,                 // Auto-zaloha novych blobu
    "warn_before_delete_last_copy": true      // Varovat pri mazani posledni kopie
  }
}
```

**Dynamicke mountovani:**
- Linux: cesta muze byt dynamicky mountovana (napr. `/media/user/ExternalDrive`)
- Synapse MUSI kontrolovat dostupnost pred kazdou operaci
- UI ukazuje stav pripojeni backup zarizeni

### 2.5.3 Struktura na backup disku

```
/mnt/external/synapse-backup/
└── .synapse/
    └── store/
        └── data/
            └── blobs/
                └── sha256/
                    ├── ab/
                    │   └── abc123...  # Zalohovany blob
                    └── cd/
                        └── cde456...
```

**STEJNA struktura jako lokalni store** - umoznuje primo kopirovat/synchronizovat.

### 2.5.4 Operace s backup storage

| Operace | Popis | Kdyz |
|---------|-------|------|
| **Backup blob** | Zkopirovat z local → backup | Uzivatel chce zalohovat |
| **Restore blob** | Zkopirovat z backup → local | Pack potrebuje blob, ktery je jen na backupu |
| **Delete local only** | Smazat z local, zachovat na backup | Uvolneni mista |
| **Delete backup only** | Smazat z backup, zachovat local | Uklid backupu |
| **Delete everywhere** | Smazat z obou mist | Uplne odstraneni (s varovanim!) |
| **Sync to backup** | Hromadne zkopirovat vsechny LOCAL_ONLY → backup | Kompletni zaloha |
| **Verify backup** | Zkontrolovat integritu backupu | Diagnostika |

### 2.5.5 Auto-restore pri pouziti packu

**Scenario:**
1. Uzivatel spusti `synapse use MyPack`
2. Pack potrebuje blob `abc123...`
3. Blob NENI lokalne (byl smazan pro uvolneni mista)
4. Blob JE na backup storage

**Flow:**
```
1. Detekce: blob BACKUP_ONLY
2. UI dialog: "Model 'xyz.safetensors' (6.8 GB) je pouze na backup storage.
              Chcete ho obnovit?"
              [Cancel] [Restore & Continue]
3. Kontrola: dostatek mista na lokalnim disku?
   - Ano: pokracovat
   - Ne: "Nedostatek mista. Uvolnete X GB nebo zruste operaci."
4. Kopirovani s progress barem
5. Pokracovani v use operaci
```

### 2.5.6 Guard rails a bezpecnost

**Varovani pri mazani:**
```
# Mazani LOCAL_ONLY blobu:
"Tento model je POUZE na lokalnim disku a NENI zalohovany.
 Smazanim ho ztratite. Chcete pokracovat?"

# Mazani posledni kopie (neni nikde jinde):
⚠️ VAROVANI: Tento model neni nikde jinde!
Smazanim ho KOMPLETNE ZTRATITE.
Budete ho muset znovu stahnout z [Civitai/HuggingFace].
[Cancel] [Delete Permanently]
```

**Kontroly pred operacemi:**
- Je backup pripojeny? (pro backup/restore operace)
- Je dostatek mista? (pro restore/backup)
- Neni soubor prave pouzivan?

### 2.5.7 UI indikace v BlobsTable

Nova vizualizace v tabulce:

| Icon | Location | Vyznam |
|------|----------|--------|
| 💾 | LOCAL_ONLY | Pouze lokalne (nezalohovano!) |
| ☁️ | BACKUP_ONLY | Pouze na backupu (lze obnovit) |
| ✅ | BOTH | Zalohovano (bezpecne) |
| ❌ | NOWHERE | Chybi vsude (MISSING) |

**Sloupec "Location" v tabulce:**
```
| Name               | Type | Size   | Status | Location | Actions |
|--------------------|------|--------|--------|----------|---------|
| juggernaut_xl_v9   | ckpt | 6.8 GB | REF    | ✅ BOTH  | [...]   |
| detail_tweaker     | lora | 145 MB | REF    | 💾 LOCAL | [Backup]|
| old_checkpoint     | ckpt | 5.2 GB | ORPH   | ☁️ BACKUP| [Restore][Del]|
| missing_model      | vae  | ?      | MISS   | ❌ NONE  | [Download]|
```

---

## 3. Nova API - Inventory Service

### 3.1 Datovy model

```python
# Novy soubor: src/store/inventory_service.py

class BlobStatus(str, Enum):
    """Status blobu v inventari."""
    REFERENCED = "referenced"   # Blob existuje lokalne a je referencovany packem
    ORPHAN = "orphan"           # Blob existuje lokalne, ale zadny pack ho nereferencuje
    MISSING = "missing"         # Pack referencuje, ale blob neexistuje NIKDE (ani backup)
    BACKUP_ONLY = "backup_only" # 🆕 Blob NENI lokalne, ale JE na backup storage

class BlobLocation(str, Enum):
    """Kde se blob fyzicky nachazi."""
    LOCAL_ONLY = "local_only"       # Pouze na lokalnim disku
    BACKUP_ONLY = "backup_only"     # Pouze na backup zarizeni
    BOTH = "both"                   # Na obou mistech (synchronizovano)
    NOWHERE = "nowhere"             # Nikde (MISSING stav)

class BlobOrigin(BaseModel):
    """Puvod blobu - odkud pochazi."""
    provider: ProviderName
    model_id: Optional[int] = None
    version_id: Optional[int] = None
    file_id: Optional[int] = None
    filename: Optional[str] = None
    repo_id: Optional[str] = None      # Pro HuggingFace

class InventoryItem(BaseModel):
    """Jedna polozka inventare."""
    sha256: str
    kind: AssetKind
    display_name: str                   # Priorita: expose.filename > origin.filename > sha256[:12]
    size_bytes: int

    # 🆕 Lokace blobu
    location: BlobLocation              # LOCAL_ONLY, BACKUP_ONLY, BOTH, NOWHERE
    on_local: bool                      # Je na lokalnim disku?
    on_backup: bool                     # Je na backup zarizeni?
    status: BlobStatus
    used_by_packs: List[str]            # Seznam nazvu packu
    ref_count: int                      # Pocet referenci (muze byt > pocet packu)
    origin: Optional[BlobOrigin] = None # Kde se vzal
    active_in_uis: List[str] = []       # Ktera UI ho prave pouzivaji
    verified: Optional[bool] = None     # True/False/None (neovereno)

class InventorySummary(BaseModel):
    """Souhrn statistiky inventare."""
    blobs_total: int
    blobs_referenced: int
    blobs_orphan: int
    blobs_missing: int
    bytes_total: int
    bytes_referenced: int
    bytes_orphan: int
    bytes_by_kind: Dict[str, int]       # checkpoint: 50GB, lora: 2GB, ...

class InventoryResponse(BaseModel):
    """Odpoved z /api/store/inventory."""
    generated_at: str
    summary: InventorySummary
    items: List[InventoryItem]

class CleanupResult(BaseModel):
    """Vysledek cleanup operace."""
    dry_run: bool
    orphans_found: int
    orphans_deleted: int
    bytes_freed: int
    deleted: List[InventoryItem]        # Co bylo smazano
    errors: List[str] = []              # Pripadne chyby

class ImpactAnalysis(BaseModel):
    """Analyza dopadu smazani blobu."""
    sha256: str
    status: BlobStatus
    size_bytes: int
    used_by_packs: List[str]
    active_in_uis: List[str]
    can_delete_safely: bool             # True jen pro orphany
    warning: Optional[str] = None
```

### 3.2 Nove API endpointy

#### GET /api/store/inventory

Hlavni endpoint pro ziskani inventare.

**Query parametry:**
- `kind` (optional): Filtr podle typu (checkpoint, lora, vae, all). Default: all
- `status` (optional): Filtr podle statusu (referenced, orphan, missing, all). Default: all
- `include_verification` (optional, bool): Zda overit hashe. Default: false (pomale!)
- `sort_by` (optional): size_desc, size_asc, name_asc, kind. Default: size_desc
- `limit` (optional, int): Max polozek. Default: 1000
- `offset` (optional, int): Pro paginaci. Default: 0

**Response:**
```json
{
  "generated_at": "2026-01-24T12:34:56Z",
  "summary": {
    "blobs_total": 45,
    "blobs_referenced": 38,
    "blobs_orphan": 5,
    "blobs_missing": 2,
    "bytes_total": 125000000000,
    "bytes_referenced": 120000000000,
    "bytes_orphan": 5000000000,
    "bytes_by_kind": {
      "checkpoint": 100000000000,
      "lora": 20000000000,
      "vae": 5000000000
    },
    // 🆕 Backup statistiky
    "backup": {
      "enabled": true,
      "connected": true,
      "path": "/mnt/external/synapse-backup",
      "blobs_local_only": 12,
      "blobs_backup_only": 8,
      "blobs_both": 23,
      "bytes_local_only": 45000000000,
      "bytes_backup_only": 30000000000,
      "bytes_synced": 80000000000
    }
  },
  "items": [
    {
      "sha256": "abc123...",
      "kind": "checkpoint",
      "display_name": "juggernaut_xl_v9.safetensors",
      "size_bytes": 6800000000,
      "status": "referenced",
      "location": "both",           // 🆕 LOCAL_ONLY, BACKUP_ONLY, BOTH, NOWHERE
      "on_local": true,             // 🆕
      "on_backup": true,            // 🆕
      "used_by_packs": ["Juggernaut_XL", "My_Custom_Pack"],
      "ref_count": 2,
      "origin": {
        "provider": "civitai",
        "model_id": 133005,
        "version_id": 456789,
        "filename": "juggernautXL_v9Rundiffusion.safetensors"
      },
      "active_in_uis": ["comfyui", "forge"],
      "verified": null
    }
  ]
}
```

#### GET /api/store/inventory/summary

Rychly endpoint jen pro statistiky (bez items).

**Response:** Pouze `InventorySummary` cast.

#### GET /api/store/inventory/{sha256}

Detail jednoho blobu.

**Response:**
```json
{
  "item": { /* InventoryItem */ },
  "impacts": {
    "can_delete_safely": false,
    "warning": "Tento blob pouziva 2 packy. Smazani zpusobi 'missing' stav.",
    "affected_packs": [
      {
        "name": "Juggernaut_XL",
        "dependency_id": "juggernaut-main",
        "is_active": true
      }
    ]
  },
  "file_info": {
    "path": "data/blobs/sha256/ab/abc123...",
    "created_at": "2026-01-20T10:00:00Z",
    "last_accessed": "2026-01-24T08:00:00Z"
  }
}
```

#### POST /api/store/inventory/cleanup-orphans

Bezpecny uklid orphan blobu.

**Request:**
```json
{
  "dry_run": true,
  "max_items": 100
}
```

**Response:** `CleanupResult`

#### DELETE /api/store/inventory/{sha256}

Smazani konkretniho blobu s guard rails.

**Request:**
```json
{
  "force": false,
  "confirm_impacts": false
}
```

**Behavior:**
- `force=false`: Smaze jen orphany. Pro referenced vraci 409 s impacts.
- `force=true, confirm_impacts=true`: Smaze i referenced (uzivatel potvrdil).

**Response 200 (uspech):**
```json
{
  "deleted": true,
  "sha256": "abc123...",
  "bytes_freed": 6800000000
}
```

**Response 409 (conflict):**
```json
{
  "deleted": false,
  "sha256": "abc123...",
  "reason": "Blob is referenced by packs",
  "impacts": { /* ImpactAnalysis */ }
}
```

#### POST /api/store/inventory/verify

Overeni integrity blobu.

**Request:**
```json
{
  "sha256": ["abc123...", "def456..."],
  "all": false
}
```

**Response:**
```json
{
  "verified": 2,
  "valid": ["abc123..."],
  "invalid": ["def456..."],
  "duration_ms": 5420
}
```

### 3.3 🆕 Backup Storage API endpointy

#### GET /api/store/backup/status

Stav pripojeni backup zarizeni.

**Response:**
```json
{
  "enabled": true,
  "connected": true,
  "path": "/mnt/external/synapse-backup",
  "total_blobs": 31,
  "total_bytes": 110000000000,
  "free_space": 450000000000,
  "last_sync": "2026-01-23T18:00:00Z"
}
```

**Response (nepripojeno):**
```json
{
  "enabled": true,
  "connected": false,
  "path": "/mnt/external/synapse-backup",
  "error": "Mount point not accessible"
}
```

#### POST /api/store/backup/blob/{sha256}

Zalohovat konkretni blob na backup storage.

**Request:**
```json
{
  "verify_after": true
}
```

**Response:**
```json
{
  "success": true,
  "sha256": "abc123...",
  "bytes_copied": 6800000000,
  "duration_ms": 45000
}
```

**Errors:**
- 400: Backup not enabled
- 503: Backup not connected
- 409: Blob already on backup
- 507: Insufficient space on backup

#### POST /api/store/backup/restore/{sha256}

Obnovit blob z backup storage na lokalni disk.

**Request:**
```json
{
  "verify_after": true
}
```

**Response:**
```json
{
  "success": true,
  "sha256": "abc123...",
  "bytes_copied": 6800000000,
  "duration_ms": 45000
}
```

**Errors:**
- 400: Backup not enabled
- 503: Backup not connected
- 404: Blob not found on backup
- 507: Insufficient space locally

#### DELETE /api/store/backup/blob/{sha256}

Smazat blob z backup storage (ponechat lokalne).

**Request:**
```json
{
  "confirm": true
}
```

**Response:**
```json
{
  "success": true,
  "sha256": "abc123...",
  "bytes_freed": 6800000000,
  "still_on_local": true
}
```

#### POST /api/store/backup/sync

Hromadna synchronizace na backup.

**Request:**
```json
{
  "direction": "to_backup",    // "to_backup" | "from_backup"
  "only_missing": true,        // Jen bloby co nejsou na cilove strane
  "dry_run": true
}
```

**Response:**
```json
{
  "dry_run": true,
  "direction": "to_backup",
  "blobs_to_sync": 12,
  "bytes_to_sync": 45000000000,
  "blobs_synced": 0,
  "bytes_synced": 0,
  "items": [
    { "sha256": "abc...", "size_bytes": 6800000000 }
  ]
}
```

#### DELETE /api/store/inventory/{sha256}?target=local|backup|both

Rozsireni delete endpointu o cilove umisteni.

**Query params:**
- `target`: `local` (default), `backup`, `both`
- `force`: `true/false`

**Guard rails:**
- `target=both` + `force=false` → 409 pokud je posledni kopie
- `target=local` → OK pokud je na backupu
- `target=backup` → OK pokud je lokalne

> ⚠️ **BUG OPRAVEN 2026-01-25:** Původní implementace NEIMPLEMENTOVALA `target=backup`!
> Viz sekce 17 "KRITICKÁ CHYBA: Delete from Backup NEFUNGOVALO"

**Response:**
```json
{
  "deleted_from": ["local"],    // nebo ["backup"] nebo ["local", "backup"]
  "sha256": "abc123...",
  "bytes_freed": 6800000000,
  "remaining_on": "backup",     // nebo "local" nebo "nowhere"
  "warning": null               // nebo "This was the last copy!"
}
```

---

## 4. Backend implementace

### 4.1 Novy soubor: src/store/inventory_service.py

```python
"""
Synapse Store v2 - Inventory Service

Provides comprehensive blob inventory with:
- Reference tracking (which packs use which blobs)
- Orphan detection
- Missing blob detection
- Safe cleanup operations
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from .blob_store import BlobStore
from .layout import StoreLayout
from .models import (
    AssetKind,
    ProviderName,
    PackLock,
    # + nove modely definovane vyse
)


class InventoryService:
    """Service for blob inventory management."""

    def __init__(self, layout: StoreLayout, blob_store: BlobStore):
        self.layout = layout
        self.blob_store = blob_store

    def build_inventory(
        self,
        kind_filter: Optional[AssetKind] = None,
        status_filter: Optional[BlobStatus] = None,
        include_verification: bool = False,
    ) -> InventoryResponse:
        """
        Build complete inventory by cross-referencing blobs and pack locks.

        Algorithm:
        1. List all physical blobs
        2. Scan all pack locks for references
        3. Cross-reference to determine status
        4. Optionally verify hashes
        """
        # Step 1: Get all physical blobs
        physical_blobs = set(self.blob_store.list_blobs())

        # Step 2: Build reference map from all pack locks
        ref_map = self._build_reference_map()

        # Step 3: Determine referenced blobs
        referenced_blobs = set(ref_map.keys())

        # Step 4: Calculate sets
        orphan_blobs = physical_blobs - referenced_blobs
        missing_blobs = referenced_blobs - physical_blobs

        # Step 5: Build items
        items = []

        # Referenced blobs (exist and are referenced)
        for sha256 in physical_blobs & referenced_blobs:
            items.append(self._build_item(
                sha256, BlobStatus.REFERENCED, ref_map[sha256],
                include_verification
            ))

        # Orphan blobs (exist but not referenced)
        for sha256 in orphan_blobs:
            items.append(self._build_item(
                sha256, BlobStatus.ORPHAN, [],
                include_verification
            ))

        # Missing blobs (referenced but don't exist)
        for sha256 in missing_blobs:
            items.append(self._build_item(
                sha256, BlobStatus.MISSING, ref_map[sha256],
                include_verification
            ))

        # Step 6: Apply filters
        if kind_filter:
            items = [i for i in items if i.kind == kind_filter]
        if status_filter:
            items = [i for i in items if i.status == status_filter]

        # Step 7: Build summary
        summary = self._build_summary(items)

        return InventoryResponse(
            generated_at=datetime.now().isoformat(),
            summary=summary,
            items=items,
        )

    def _build_reference_map(self) -> Dict[str, List[PackReference]]:
        """
        Scan all pack locks and build sha256 -> [references] map.
        """
        ref_map: Dict[str, List[PackReference]] = {}

        for pack_name in self.layout.list_packs():
            try:
                lock = self.layout.load_pack_lock(pack_name)
                pack = self.layout.load_pack(pack_name)

                for resolved in lock.resolved:
                    sha256 = resolved.artifact.sha256
                    if not sha256:
                        continue

                    if sha256 not in ref_map:
                        ref_map[sha256] = []

                    # Get expose filename from pack dependency
                    expose_filename = None
                    for dep in pack.dependencies:
                        if dep.id == resolved.dependency_id:
                            expose_filename = dep.expose.filename
                            break

                    ref_map[sha256].append(PackReference(
                        pack_name=pack_name,
                        dependency_id=resolved.dependency_id,
                        kind=resolved.artifact.kind,
                        origin=BlobOrigin(
                            provider=resolved.artifact.provider.name,
                            model_id=resolved.artifact.provider.model_id,
                            version_id=resolved.artifact.provider.version_id,
                            file_id=resolved.artifact.provider.file_id,
                            filename=resolved.artifact.provider.filename,
                        ),
                        expose_filename=expose_filename,
                        size_bytes=resolved.artifact.size_bytes,
                    ))
            except Exception:
                continue  # Skip packs with missing/invalid locks

        return ref_map

    def cleanup_orphans(self, dry_run: bool = True) -> CleanupResult:
        """
        Remove orphan blobs safely.

        NEVER removes referenced blobs.
        """
        inventory = self.build_inventory(status_filter=BlobStatus.ORPHAN)

        result = CleanupResult(
            dry_run=dry_run,
            orphans_found=len(inventory.items),
            orphans_deleted=0,
            bytes_freed=0,
            deleted=[],
        )

        if dry_run:
            result.deleted = inventory.items
            result.bytes_freed = sum(i.size_bytes for i in inventory.items)
            return result

        # Actually delete
        for item in inventory.items:
            try:
                if self.blob_store.remove_blob(item.sha256):
                    result.orphans_deleted += 1
                    result.bytes_freed += item.size_bytes
                    result.deleted.append(item)
            except Exception as e:
                result.errors.append(f"{item.sha256}: {str(e)}")

        return result

    def get_impacts(self, sha256: str) -> ImpactAnalysis:
        """
        Analyze what would break if a blob is deleted.
        """
        inventory = self.build_inventory()

        item = next((i for i in inventory.items if i.sha256 == sha256), None)

        if not item:
            return ImpactAnalysis(
                sha256=sha256,
                status=BlobStatus.MISSING,
                size_bytes=0,
                used_by_packs=[],
                active_in_uis=[],
                can_delete_safely=True,
                warning="Blob neexistuje",
            )

        can_delete = item.status == BlobStatus.ORPHAN
        warning = None

        if item.status == BlobStatus.REFERENCED:
            warning = f"Tento blob pouziva {len(item.used_by_packs)} pack(u). Smazani zpusobi MISSING stav."

        return ImpactAnalysis(
            sha256=sha256,
            status=item.status,
            size_bytes=item.size_bytes,
            used_by_packs=item.used_by_packs,
            active_in_uis=item.active_in_uis,
            can_delete_safely=can_delete,
            warning=warning,
        )
```

### 4.2 Integrace do Store tridy (src/store/__init__.py)

```python
# Pridat do __init__.py:

from .inventory_service import InventoryService

class Store:
    def __init__(self, ...):
        ...
        self.inventory_service = InventoryService(self.layout, self.blob_store)

    # Delegovane metody
    def get_inventory(self, **kwargs) -> InventoryResponse:
        return self.inventory_service.build_inventory(**kwargs)

    def get_inventory_summary(self) -> InventorySummary:
        return self.inventory_service.build_inventory().summary

    def cleanup_orphans(self, dry_run: bool = True) -> CleanupResult:
        return self.inventory_service.cleanup_orphans(dry_run)

    def get_blob_impacts(self, sha256: str) -> ImpactAnalysis:
        return self.inventory_service.get_impacts(sha256)

    def delete_blob(self, sha256: str, force: bool = False) -> dict:
        impacts = self.get_blob_impacts(sha256)

        if not impacts.can_delete_safely and not force:
            return {
                "deleted": False,
                "reason": "Blob is referenced",
                "impacts": impacts,
            }

        removed = self.blob_store.remove_blob(sha256)
        return {
            "deleted": removed,
            "sha256": sha256,
            "bytes_freed": impacts.size_bytes if removed else 0,
        }
```

### 4.3 API Router (src/store/api.py)

```python
# Pridat nove endpointy do /api/store/

@router.get("/inventory")
async def get_inventory(
    kind: Optional[str] = None,
    status: Optional[str] = None,
    include_verification: bool = False,
    sort_by: str = "size_desc",
    limit: int = 1000,
    offset: int = 0,
):
    """Get blob inventory with filtering and pagination."""
    store = get_store()

    kind_filter = AssetKind(kind) if kind and kind != "all" else None
    status_filter = BlobStatus(status) if status and status != "all" else None

    inventory = store.get_inventory(
        kind_filter=kind_filter,
        status_filter=status_filter,
        include_verification=include_verification,
    )

    # Sort
    if sort_by == "size_desc":
        inventory.items.sort(key=lambda x: x.size_bytes, reverse=True)
    elif sort_by == "size_asc":
        inventory.items.sort(key=lambda x: x.size_bytes)
    elif sort_by == "name_asc":
        inventory.items.sort(key=lambda x: x.display_name.lower())

    # Paginate
    inventory.items = inventory.items[offset:offset + limit]

    return inventory


@router.get("/inventory/summary")
async def get_inventory_summary():
    """Get quick inventory summary (no items)."""
    store = get_store()
    return store.get_inventory_summary()


@router.get("/inventory/{sha256}")
async def get_blob_detail(sha256: str):
    """Get detailed info about a specific blob."""
    store = get_store()
    inventory = store.get_inventory()

    item = next((i for i in inventory.items if i.sha256 == sha256), None)
    if not item:
        raise HTTPException(404, "Blob not found")

    impacts = store.get_blob_impacts(sha256)

    return {
        "item": item,
        "impacts": impacts,
    }


@router.post("/inventory/cleanup-orphans")
async def cleanup_orphans(dry_run: bool = True):
    """Remove orphan blobs safely."""
    store = get_store()
    return store.cleanup_orphans(dry_run=dry_run)


@router.delete("/inventory/{sha256}")
async def delete_blob(sha256: str, force: bool = False):
    """Delete a specific blob with safety checks."""
    store = get_store()
    result = store.delete_blob(sha256, force=force)

    if not result["deleted"] and "impacts" in result:
        raise HTTPException(409, detail=result)

    return result


@router.post("/inventory/verify")
async def verify_blobs(sha256: Optional[List[str]] = None, all: bool = False):
    """Verify blob integrity."""
    store = get_store()

    if all:
        valid, invalid = store.blob_store.verify_all()
    else:
        valid = []
        invalid = []
        for h in (sha256 or []):
            if store.blob_store.verify(h):
                valid.append(h)
            else:
                invalid.append(h)

    return {
        "verified": len(valid) + len(invalid),
        "valid": valid,
        "invalid": invalid,
    }
```

---

## 5. UI Design

### 5.1 Struktura stranky

```
+------------------------------------------------------------------+
|  [Tab: Model Inventory]                                          |
+------------------------------------------------------------------+
|                                                                  |
|  +------------------+ +------------------+ +--------------------+|
|  | 💾 LOCAL DISK    | | ☁️ BACKUP        | | ⚡ QUICK ACTIONS   ||
|  | [====    ] 125GB | | [==      ] 110GB | | [Cleanup Orphans]  ||
|  | Free: 375GB      | | 🟢 Connected     | | [Sync to Backup]   ||
|  | 12 local-only    | | 8 backup-only    | | [Verify All]       ||
|  +------------------+ +------------------+ +--------------------+|
|                                                                  |
|  +--------------------------------------------------------------+|
|  | STATUS OVERVIEW          [Pie Chart: REF/ORPH/MISS/BACKUP]   ||
|  | 38 referenced | 5 orphan | 2 missing | 8 backup-only         ||
|  +--------------------------------------------------------------+|
|                                                                  |
|  [Filters] Kind: [All v] Status: [All v] Location: [All v]      |
|            Search: [________________________] [🔍]               |
|                                                                  |
|  ================================================================|
|  🔥 BLOBS TABLE - HLAVNI KOMPONENTA (viz 5.3)                   |
|  ================================================================|
|  | Icon | Name               | Type | Size   | Status | Loc | + ||
|  |------|-------------------|------|--------|--------|-----|---||
|  | [C]  | juggernaut_xl_v9  | ckpt | 6.8 GB | [REF]  | ✅  |...||
|  | [L]  | detail_tweaker    | lora | 145 MB | [REF]  | 💾  |[B]||
|  | [V]  | old_vae           | vae  | 335 MB | [ORPH] | ☁️  |[R]||
|  | [?]  | missing_model     | ckpt |   -    | [MISS] | ❌  |[D]||
|  +--------------------------------------------------------------+|
|                                                                  |
|  Showing 1-50 of 45 items                    [< Prev] [Next >]  |
|  Selected: 3 items (7.3 GB)      [Backup Selected] [Delete Sel] |
+------------------------------------------------------------------+

Legenda Location:
  ✅ BOTH      - na obou mistech (bezpecne)
  💾 LOCAL     - pouze lokalne (NEZALOHOVANO!)
  ☁️ BACKUP    - pouze na backupu (lze obnovit)
  ❌ NOWHERE   - chybi vsude (MISSING)

Akce [B]=Backup, [R]=Restore, [D]=Download from source
```

> **🔥 DULEZITE: BlobsTable je NEJDULEZITEJSI komponenta cele zalozky!**
> Musi byt dokonale zpracovana - viz detailni specifikace v sekci 5.3.

### 5.2 Komponenty

#### 5.2.1 InventoryPage (hlavni komponenta)

```tsx
// apps/web/src/components/modules/InventoryPage.tsx

export function InventoryPage() {
  const [filters, setFilters] = useState({
    kind: 'all',
    status: 'all',
    search: '',
  });

  const { data: inventory, isLoading } = useQuery({
    queryKey: ['inventory', filters],
    queryFn: () => api.getInventory(filters),
  });

  return (
    <div className="space-y-6">
      {/* Header s statistikami */}
      <InventoryStats summary={inventory?.summary} />

      {/* Filtry */}
      <InventoryFilters filters={filters} onChange={setFilters} />

      {/* Tabulka */}
      <InventoryTable
        items={inventory?.items || []}
        onDelete={handleDelete}
        onShowImpacts={handleShowImpacts}
      />

      {/* Cleanup dialog */}
      <CleanupWizard
        open={showCleanup}
        onClose={() => setShowCleanup(false)}
      />
    </div>
  );
}
```

#### 5.2.2 InventoryStats (dashboard nahore)

```tsx
// Dashboard s 4 kartami: Local Disk, Backup Storage, Status, Quick Actions

interface InventoryStatsProps {
  summary?: InventorySummary;
  backupStatus?: BackupStatus;
  onCleanup: () => void;
  onVerify: () => void;
  onSyncToBackup: () => void;
}

export function InventoryStats({
  summary,
  backupStatus,
  onCleanup,
  onVerify,
  onSyncToBackup,
}: InventoryStatsProps) {
  return (
    <div className="grid grid-cols-4 gap-4">
      {/* LOCAL DISK Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <HardDrive className="w-4 h-4" />
            Local Disk
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {formatBytes(summary?.bytes_total || 0)}
          </div>
          <Progress
            value={(summary?.bytes_total || 0) / (summary?.disk_total || 1) * 100}
            className="mt-2"
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>Free: {formatBytes(summary?.disk_free || 0)}</span>
            <span>{summary?.backup?.blobs_local_only || 0} local-only</span>
          </div>

          {/* Warning for local-only blobs */}
          {(summary?.backup?.blobs_local_only || 0) > 0 && (
            <div className="mt-2 flex items-center gap-1 text-xs text-amber-600">
              <AlertTriangle className="w-3 h-3" />
              {summary?.backup?.blobs_local_only} not backed up
            </div>
          )}
        </CardContent>
      </Card>

      {/* BACKUP STORAGE Card */}
      <Card className={cn(
        !backupStatus?.connected && backupStatus?.enabled && 'border-amber-500/50'
      )}>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Cloud className="w-4 h-4" />
            Backup Storage
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!backupStatus?.enabled ? (
            <div className="text-muted-foreground text-sm">
              <div>Not configured</div>
              <Button variant="link" size="sm" className="p-0 h-auto mt-1">
                Configure in Settings →
              </Button>
            </div>
          ) : !backupStatus?.connected ? (
            <div className="text-amber-600">
              <div className="flex items-center gap-1">
                <AlertCircle className="w-4 h-4" />
                Disconnected
              </div>
              <div className="text-xs mt-1 text-muted-foreground">
                {backupStatus.path}
              </div>
            </div>
          ) : (
            <>
              <div className="text-2xl font-bold">
                {formatBytes(summary?.backup?.bytes_synced || 0)}
              </div>
              <Progress
                value={
                  ((summary?.backup?.total_bytes || 0) /
                   (backupStatus.total_space || 1)) * 100
                }
                className="mt-2"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-green-500" />
                  Connected
                </span>
                <span>{summary?.backup?.blobs_backup_only || 0} backup-only</span>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* STATUS Overview Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Status Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-sm">Referenced</span>
              </div>
              <span className="font-mono text-sm">{summary?.blobs_referenced || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-gray-500" />
                <span className="text-sm">Orphan</span>
              </div>
              <span className="font-mono text-sm">{summary?.blobs_orphan || 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-sm">Backup-only</span>
              </div>
              <span className="font-mono text-sm">{summary?.backup?.blobs_backup_only || 0}</span>
            </div>
            {(summary?.blobs_missing || 0) > 0 && (
              <div className="flex items-center justify-between text-red-600">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-red-500" />
                  <span className="text-sm">Missing</span>
                </div>
                <span className="font-mono text-sm">{summary?.blobs_missing}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* QUICK ACTIONS Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Quick Actions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(summary?.blobs_orphan || 0) > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start"
              onClick={onCleanup}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Cleanup {summary?.blobs_orphan} Orphans
            </Button>
          )}

          {backupStatus?.connected && (summary?.backup?.blobs_local_only || 0) > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start"
              onClick={onSyncToBackup}
            >
              <Upload className="w-4 h-4 mr-2" />
              Backup {summary?.backup?.blobs_local_only} Local-only
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            onClick={onVerify}
          >
            <Shield className="w-4 h-4 mr-2" />
            Verify Integrity
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

### 5.3 🔥 BlobsTable - HLAVNI KOMPONENTA

> **TOTO JE NEJDULEZITEJSI KOMPONENTA CELE ZALOZKY!**
> Musi byt dokonale zpracovana - funkcni, prehledna, s intuitivnimi akcemi.

#### 5.3.1 Sloupce tabulky

| Sloupec | Popis | Sirka | Sortable |
|---------|-------|-------|----------|
| ☐ | Checkbox pro bulk select | 40px | Ne |
| Icon | AssetKind ikona | 40px | Ne |
| Name | display_name + sha256 prefix | flex | Ano |
| Type | AssetKind badge | 80px | Ano |
| Size | Formatovana velikost | 100px | Ano (default desc) |
| Status | REFERENCED/ORPHAN/MISSING badge | 100px | Ano |
| Location | LOCAL/BACKUP/BOTH/NOWHERE ikona | 80px | Ano |
| Used By | Pack badges (max 2 + overflow) | 150px | Ne |
| Actions | Context menu + quick actions | 120px | Ne |

#### 5.3.2 Location ikony a stavy

```tsx
const LocationIcon = ({ location }: { location: BlobLocation }) => {
  const config = {
    both: {
      icon: <CheckCircle2 className="w-4 h-4" />,
      color: 'text-green-500',
      tooltip: 'Backed up (safe)',
      bgColor: 'bg-green-500/10',
    },
    local_only: {
      icon: <HardDrive className="w-4 h-4" />,
      color: 'text-amber-500',
      tooltip: 'Local only - NOT BACKED UP!',
      bgColor: 'bg-amber-500/10',
    },
    backup_only: {
      icon: <Cloud className="w-4 h-4" />,
      color: 'text-blue-500',
      tooltip: 'Backup only - can restore',
      bgColor: 'bg-blue-500/10',
    },
    nowhere: {
      icon: <AlertTriangle className="w-4 h-4" />,
      color: 'text-red-500',
      tooltip: 'Missing everywhere!',
      bgColor: 'bg-red-500/10',
    },
  };

  const c = config[location];

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <div className={cn('p-1 rounded', c.bgColor, c.color)}>
            {c.icon}
          </div>
        </TooltipTrigger>
        <TooltipContent>{c.tooltip}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
```

#### 5.3.3 Row Actions podle stavu

**Kontextove akce (dropdown menu):**

| Location | Status | Dostupne akce |
|----------|--------|---------------|
| BOTH | REF | Copy SHA, Show Impacts, Delete from Backup, Delete from Local |
| BOTH | ORPH | Copy SHA, Delete from Backup, Delete from Local, Delete Everywhere |
| LOCAL_ONLY | REF | Copy SHA, Show Impacts, **[!] Backup Now** |
| LOCAL_ONLY | ORPH | Copy SHA, **[!] Backup Now**, Delete |
| BACKUP_ONLY | REF | Copy SHA, Show Impacts, **Restore**, Delete from Backup |
| BACKUP_ONLY | ORPH | Copy SHA, Restore, Delete from Backup |
| NOWHERE | MISS | Copy SHA, Show Impacts, **Re-download** |

**Quick Actions (inline buttons):**
- `LOCAL_ONLY` → zobrazit tlacitko `[Backup]` primo v radku
- `BACKUP_ONLY` → zobrazit tlacitko `[Restore]` primo v radku
- `ORPHAN` → zobrazit tlacitko `[Delete]` primo v radku (cervene)

#### 5.3.4 Kompletni implementace

```tsx
// apps/web/src/components/modules/inventory/BlobsTable.tsx

interface BlobsTableProps {
  items: InventoryItem[];
  backupEnabled: boolean;
  backupConnected: boolean;
  onBackup: (sha256: string) => Promise<void>;
  onRestore: (sha256: string) => Promise<void>;
  onDelete: (sha256: string, target: 'local' | 'backup' | 'both') => Promise<void>;
  onShowImpacts: (item: InventoryItem) => void;
  onBulkAction: (sha256s: string[], action: BulkAction) => void;
}

type BulkAction = 'backup' | 'restore' | 'delete_local' | 'delete_backup';

export function BlobsTable({
  items,
  backupEnabled,
  backupConnected,
  onBackup,
  onRestore,
  onDelete,
  onShowImpacts,
  onBulkAction,
}: BlobsTableProps) {
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [sortConfig, setSortConfig] = useState<{
    key: keyof InventoryItem;
    direction: 'asc' | 'desc';
  }>({ key: 'size_bytes', direction: 'desc' });

  // Sorting
  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
      }

      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      const cmp = aStr.localeCompare(bStr);
      return sortConfig.direction === 'asc' ? cmp : -cmp;
    });
  }, [items, sortConfig]);

  // Selection helpers
  const allSelected = selectedItems.size === items.length && items.length > 0;
  const someSelected = selectedItems.size > 0 && !allSelected;

  const toggleAll = () => {
    if (allSelected) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(items.map(i => i.sha256)));
    }
  };

  const toggleItem = (sha256: string) => {
    const newSet = new Set(selectedItems);
    if (newSet.has(sha256)) {
      newSet.delete(sha256);
    } else {
      newSet.add(sha256);
    }
    setSelectedItems(newSet);
  };

  // Selected items summary
  const selectedSummary = useMemo(() => {
    const selected = items.filter(i => selectedItems.has(i.sha256));
    return {
      count: selected.length,
      totalBytes: selected.reduce((sum, i) => sum + i.size_bytes, 0),
      canBackup: selected.filter(i => i.location === 'local_only').length,
      canRestore: selected.filter(i => i.location === 'backup_only').length,
      canDelete: selected.filter(i => i.status === 'orphan').length,
    };
  }, [items, selectedItems]);

  return (
    <div className="space-y-4">
      {/* Bulk Actions Bar (visible when items selected) */}
      {selectedItems.size > 0 && (
        <div className="flex items-center justify-between bg-muted p-3 rounded-lg">
          <div className="flex items-center gap-4">
            <span className="font-medium">
              {selectedSummary.count} selected
            </span>
            <span className="text-muted-foreground">
              ({formatBytes(selectedSummary.totalBytes)})
            </span>
          </div>

          <div className="flex items-center gap-2">
            {backupEnabled && backupConnected && selectedSummary.canBackup > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'backup')}
              >
                <Upload className="w-4 h-4 mr-2" />
                Backup {selectedSummary.canBackup}
              </Button>
            )}

            {backupEnabled && backupConnected && selectedSummary.canRestore > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'restore')}
              >
                <Download className="w-4 h-4 mr-2" />
                Restore {selectedSummary.canRestore}
              </Button>
            )}

            {selectedSummary.canDelete > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => onBulkAction([...selectedItems], 'delete_local')}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete {selectedSummary.canDelete} Orphans
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedItems(new Set())}
            >
              Clear
            </Button>
          </div>
        </div>
      )}

      {/* Main Table */}
      <Table>
        <TableHeader>
          <TableRow>
            {/* Checkbox */}
            <TableHead className="w-[40px]">
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                onCheckedChange={toggleAll}
              />
            </TableHead>

            {/* Icon */}
            <TableHead className="w-[40px]"></TableHead>

            {/* Name - sortable */}
            <TableHead>
              <SortableHeader
                label="Name"
                sortKey="display_name"
                currentSort={sortConfig}
                onSort={setSortConfig}
              />
            </TableHead>

            {/* Type */}
            <TableHead className="w-[80px]">Type</TableHead>

            {/* Size - sortable */}
            <TableHead className="w-[100px] text-right">
              <SortableHeader
                label="Size"
                sortKey="size_bytes"
                currentSort={sortConfig}
                onSort={setSortConfig}
              />
            </TableHead>

            {/* Status - sortable */}
            <TableHead className="w-[100px]">
              <SortableHeader
                label="Status"
                sortKey="status"
                currentSort={sortConfig}
                onSort={setSortConfig}
              />
            </TableHead>

            {/* Location - sortable */}
            <TableHead className="w-[80px]">
              <SortableHeader
                label="Location"
                sortKey="location"
                currentSort={sortConfig}
                onSort={setSortConfig}
              />
            </TableHead>

            {/* Used By */}
            <TableHead className="w-[150px]">Used By</TableHead>

            {/* Actions */}
            <TableHead className="w-[120px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          {sortedItems.map((item) => (
            <BlobRow
              key={item.sha256}
              item={item}
              selected={selectedItems.has(item.sha256)}
              onToggle={() => toggleItem(item.sha256)}
              backupEnabled={backupEnabled}
              backupConnected={backupConnected}
              onBackup={onBackup}
              onRestore={onRestore}
              onDelete={onDelete}
              onShowImpacts={onShowImpacts}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// Individual row component
function BlobRow({
  item,
  selected,
  onToggle,
  backupEnabled,
  backupConnected,
  onBackup,
  onRestore,
  onDelete,
  onShowImpacts,
}: {
  item: InventoryItem;
  selected: boolean;
  onToggle: () => void;
  backupEnabled: boolean;
  backupConnected: boolean;
  onBackup: (sha256: string) => Promise<void>;
  onRestore: (sha256: string) => Promise<void>;
  onDelete: (sha256: string, target: 'local' | 'backup' | 'both') => Promise<void>;
  onShowImpacts: (item: InventoryItem) => void;
}) {
  const [isLoading, setIsLoading] = useState(false);

  const handleAction = async (action: () => Promise<void>) => {
    setIsLoading(true);
    try {
      await action();
    } finally {
      setIsLoading(false);
    }
  };

  // Determine quick action button
  const quickAction = useMemo(() => {
    if (item.location === 'local_only' && backupEnabled && backupConnected) {
      return {
        label: 'Backup',
        icon: <Upload className="w-3 h-3" />,
        variant: 'outline' as const,
        className: 'text-amber-600 border-amber-300 hover:bg-amber-50',
        action: () => onBackup(item.sha256),
      };
    }
    if (item.location === 'backup_only' && backupConnected) {
      return {
        label: 'Restore',
        icon: <Download className="w-3 h-3" />,
        variant: 'outline' as const,
        className: 'text-blue-600 border-blue-300 hover:bg-blue-50',
        action: () => onRestore(item.sha256),
      };
    }
    if (item.status === 'orphan' && item.on_local) {
      return {
        label: 'Delete',
        icon: <Trash2 className="w-3 h-3" />,
        variant: 'destructive' as const,
        className: '',
        action: () => onDelete(item.sha256, 'local'),
      };
    }
    return null;
  }, [item, backupEnabled, backupConnected]);

  return (
    <TableRow className={cn(selected && 'bg-muted/50')}>
      {/* Checkbox */}
      <TableCell>
        <Checkbox checked={selected} onCheckedChange={onToggle} />
      </TableCell>

      {/* Icon */}
      <TableCell>
        <AssetKindIcon kind={item.kind} />
      </TableCell>

      {/* Name */}
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium truncate max-w-[200px]">
            {item.display_name}
          </span>
          <span className="text-xs text-muted-foreground font-mono">
            {item.sha256.slice(0, 12)}...
          </span>
        </div>
      </TableCell>

      {/* Type */}
      <TableCell>
        <Badge variant="outline" className="text-xs">
          {item.kind}
        </Badge>
      </TableCell>

      {/* Size */}
      <TableCell className="text-right font-mono text-sm">
        {item.size_bytes > 0 ? formatBytes(item.size_bytes) : '-'}
      </TableCell>

      {/* Status */}
      <TableCell>
        <StatusBadge status={item.status} />
      </TableCell>

      {/* Location */}
      <TableCell>
        <LocationIcon location={item.location} />
      </TableCell>

      {/* Used By */}
      <TableCell>
        {item.used_by_packs.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {item.used_by_packs.slice(0, 2).map(pack => (
              <Badge key={pack} variant="secondary" className="text-xs">
                {pack}
              </Badge>
            ))}
            {item.used_by_packs.length > 2 && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <Badge variant="secondary" className="text-xs">
                      +{item.used_by_packs.length - 2}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    {item.used_by_packs.slice(2).join(', ')}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        ) : (
          <span className="text-muted-foreground text-sm">-</span>
        )}
      </TableCell>

      {/* Actions */}
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          {/* Quick Action Button */}
          {quickAction && (
            <Button
              variant={quickAction.variant}
              size="sm"
              className={cn('h-7 px-2 text-xs', quickAction.className)}
              disabled={isLoading}
              onClick={() => handleAction(quickAction.action)}
            >
              {isLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <>
                  {quickAction.icon}
                  <span className="ml-1">{quickAction.label}</span>
                </>
              )}
            </Button>
          )}

          {/* Context Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                <MoreHorizontal className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {/* Always available */}
              <DropdownMenuItem onClick={() => navigator.clipboard.writeText(item.sha256)}>
                <Copy className="w-4 h-4 mr-2" />
                Copy SHA256
              </DropdownMenuItem>

              {item.status === 'referenced' && (
                <DropdownMenuItem onClick={() => onShowImpacts(item)}>
                  <Info className="w-4 h-4 mr-2" />
                  Show Impacts
                </DropdownMenuItem>
              )}

              <DropdownMenuSeparator />

              {/* Backup actions */}
              {backupEnabled && backupConnected && (
                <>
                  {item.location === 'local_only' && (
                    <DropdownMenuItem onClick={() => handleAction(() => onBackup(item.sha256))}>
                      <Upload className="w-4 h-4 mr-2" />
                      Backup to External
                    </DropdownMenuItem>
                  )}

                  {item.location === 'backup_only' && (
                    <DropdownMenuItem onClick={() => handleAction(() => onRestore(item.sha256))}>
                      <Download className="w-4 h-4 mr-2" />
                      Restore from Backup
                    </DropdownMenuItem>
                  )}
                </>
              )}

              {/* Delete actions */}
              {item.on_local && item.status === 'orphan' && (
                <DropdownMenuItem
                  className="text-red-600"
                  onClick={() => handleAction(() => onDelete(item.sha256, 'local'))}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete from Local
                </DropdownMenuItem>
              )}

              {item.on_backup && backupConnected && (
                <DropdownMenuItem
                  className="text-red-600"
                  onClick={() => handleAction(() => onDelete(item.sha256, 'backup'))}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete from Backup
                </DropdownMenuItem>
              )}

              {item.location === 'both' && item.status === 'orphan' && (
                <DropdownMenuItem
                  className="text-red-600"
                  onClick={() => handleAction(() => onDelete(item.sha256, 'both'))}
                >
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  Delete Everywhere
                </DropdownMenuItem>
              )}

              {/* Re-download for missing */}
              {item.status === 'missing' && item.origin && (
                <DropdownMenuItem>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Re-download from {item.origin.provider}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </TableCell>
    </TableRow>
  );
}

// Sortable header helper
function SortableHeader({
  label,
  sortKey,
  currentSort,
  onSort,
}: {
  label: string;
  sortKey: keyof InventoryItem;
  currentSort: { key: keyof InventoryItem; direction: 'asc' | 'desc' };
  onSort: (config: { key: keyof InventoryItem; direction: 'asc' | 'desc' }) => void;
}) {
  const isActive = currentSort.key === sortKey;

  const handleClick = () => {
    if (isActive) {
      onSort({ key: sortKey, direction: currentSort.direction === 'asc' ? 'desc' : 'asc' });
    } else {
      onSort({ key: sortKey, direction: 'desc' });
    }
  };

  return (
    <button
      className="flex items-center gap-1 hover:text-foreground"
      onClick={handleClick}
    >
      {label}
      {isActive && (
        currentSort.direction === 'asc'
          ? <ChevronUp className="w-3 h-3" />
          : <ChevronDown className="w-3 h-3" />
      )}
    </button>
  );
}
```

#### 5.3.5 Pomocne komponenty

```tsx
// StatusBadge - viz 5.2.4

// AssetKindIcon - ikony pro typy assetu
function AssetKindIcon({ kind }: { kind: AssetKind }) {
  const icons = {
    checkpoint: <Box className="w-4 h-4 text-purple-500" />,
    lora: <Layers className="w-4 h-4 text-blue-500" />,
    vae: <Cpu className="w-4 h-4 text-green-500" />,
    embedding: <Type className="w-4 h-4 text-orange-500" />,
    controlnet: <GitBranch className="w-4 h-4 text-pink-500" />,
    upscaler: <Maximize2 className="w-4 h-4 text-cyan-500" />,
    other: <FileQuestion className="w-4 h-4 text-gray-500" />,
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>{icons[kind] || icons.other}</TooltipTrigger>
        <TooltipContent>{kind}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
```

#### 5.2.4 StatusBadge

```tsx
function StatusBadge({ status }: { status: BlobStatus }) {
  const config = {
    referenced: {
      label: 'Referenced',
      icon: <CheckCircle className="w-3 h-3" />,
      className: 'bg-green-500/10 text-green-600 border-green-500/20',
    },
    orphan: {
      label: 'Orphan',
      icon: <CircleDashed className="w-3 h-3" />,
      className: 'bg-gray-500/10 text-gray-600 border-gray-500/20',
    },
    missing: {
      label: 'Missing',
      icon: <AlertCircle className="w-3 h-3" />,
      className: 'bg-red-500/10 text-red-600 border-red-500/20',
    },
    backup_only: {
      label: 'Backup',
      icon: <Cloud className="w-3 h-3" />,
      className: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    },
  };

  const c = config[status];

  return (
    <Badge variant="outline" className={cn('gap-1', c.className)}>
      {c.icon}
      {c.label}
    </Badge>
  );
}
```

#### 5.2.5 DeleteConfirmationDialog (Guard Rails)

```tsx
// Dialog pro potvrzeni mazani s ruznymi urovnemi varovani

interface DeleteConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem | null;
  target: 'local' | 'backup' | 'both';
  onConfirm: () => void;
}

export function DeleteConfirmationDialog({
  open,
  onOpenChange,
  item,
  target,
  onConfirm,
}: DeleteConfirmationDialogProps) {
  if (!item) return null;

  // Determine warning level
  const isLastCopy =
    (target === 'both') ||
    (target === 'local' && !item.on_backup) ||
    (target === 'backup' && !item.on_local);

  const isReferenced = item.status === 'referenced';

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            {isLastCopy ? (
              <>
                <AlertTriangle className="w-5 h-5 text-red-500" />
                Delete Last Copy?
              </>
            ) : (
              <>
                <Trash2 className="w-5 h-5" />
                Delete Blob?
              </>
            )}
          </AlertDialogTitle>

          <AlertDialogDescription className="space-y-4">
            {/* Blob info */}
            <div className="bg-muted p-3 rounded-lg">
              <div className="font-medium">{item.display_name}</div>
              <div className="text-sm text-muted-foreground">
                {formatBytes(item.size_bytes)} • {item.kind}
              </div>
            </div>

            {/* Warning messages */}
            {isLastCopy && (
              <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium text-red-600">
                    This is the ONLY copy of this model!
                  </div>
                  <div className="text-sm text-red-600/80">
                    Deleting it will permanently remove it. You'll need to
                    re-download from {item.origin?.provider || 'the source'}.
                  </div>
                </div>
              </div>
            )}

            {isReferenced && (
              <div className="flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <Info className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium text-amber-600">
                    This blob is used by {item.used_by_packs.length} pack(s)
                  </div>
                  <div className="text-sm text-amber-600/80">
                    {item.used_by_packs.join(', ')}
                  </div>
                </div>
              </div>
            )}

            {!isLastCopy && (
              <div className="text-sm">
                Deleting from {target}.
                {target === 'local' && item.on_backup && (
                  <span className="text-green-600">
                    {' '}Backup copy will be preserved.
                  </span>
                )}
                {target === 'backup' && item.on_local && (
                  <span className="text-green-600">
                    {' '}Local copy will be preserved.
                  </span>
                )}
              </div>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={cn(
              isLastCopy && 'bg-red-600 hover:bg-red-700'
            )}
          >
            {isLastCopy ? 'Delete Permanently' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
```

#### 5.2.6 BackupSyncWizard (hromadna synchronizace)

```tsx
// Wizard pro hromadnou synchronizaci na backup

interface BackupSyncWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  direction: 'to_backup' | 'from_backup';
}

export function BackupSyncWizard({
  open,
  onOpenChange,
  direction,
}: BackupSyncWizardProps) {
  const [step, setStep] = useState<'preview' | 'progress' | 'complete'>('preview');

  // Dry run query
  const { data: preview, isLoading: isPreviewLoading } = useQuery({
    queryKey: ['backup-sync-preview', direction],
    queryFn: () => api.backupSync({ direction, dry_run: true }),
    enabled: open,
  });

  // Execute mutation
  const syncMutation = useMutation({
    mutationFn: () => api.backupSync({ direction, dry_run: false }),
    onSuccess: () => setStep('complete'),
  });

  const isToBackup = direction === 'to_backup';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isToBackup ? (
              <>
                <Upload className="w-5 h-5" />
                Backup to External Storage
              </>
            ) : (
              <>
                <Download className="w-5 h-5" />
                Restore from Backup
              </>
            )}
          </DialogTitle>
        </DialogHeader>

        {step === 'preview' && (
          <div className="space-y-4">
            {isPreviewLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            ) : preview?.blobs_to_sync === 0 ? (
              <div className="text-center py-8">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium">Already Synced!</h3>
                <p className="text-muted-foreground mt-2">
                  {isToBackup
                    ? 'All local blobs are already backed up.'
                    : 'All backup blobs are already restored locally.'}
                </p>
              </div>
            ) : (
              <>
                {/* Summary */}
                <div className="grid grid-cols-2 gap-4">
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-3xl font-bold">
                        {preview?.blobs_to_sync}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Blobs to {isToBackup ? 'backup' : 'restore'}
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-3xl font-bold">
                        {formatBytes(preview?.bytes_to_sync || 0)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Total size
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Item list */}
                <div className="max-h-60 overflow-y-auto border rounded-lg">
                  {preview?.items.map((item) => (
                    <div
                      key={item.sha256}
                      className="flex items-center justify-between p-3 border-b last:border-b-0"
                    >
                      <div className="flex items-center gap-3">
                        <AssetKindIcon kind={item.kind} />
                        <div>
                          <div className="font-medium">{item.display_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {item.kind}
                          </div>
                        </div>
                      </div>
                      <div className="font-mono text-sm">
                        {formatBytes(item.size_bytes)}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Space check */}
                {preview?.space_warning && (
                  <div className="flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                    <div className="text-sm text-amber-600">
                      {preview.space_warning}
                    </div>
                  </div>
                )}
              </>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  setStep('progress');
                  syncMutation.mutate();
                }}
                disabled={!preview || preview.blobs_to_sync === 0}
              >
                {isToBackup ? 'Start Backup' : 'Start Restore'}
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === 'progress' && (
          <div className="py-8 space-y-4">
            <div className="flex flex-col items-center">
              <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
              <h3 className="text-lg font-medium">
                {isToBackup ? 'Backing up...' : 'Restoring...'}
              </h3>
              <p className="text-muted-foreground">
                {syncMutation.data?.blobs_synced || 0} / {preview?.blobs_to_sync} blobs
              </p>
            </div>
            <Progress
              value={
                ((syncMutation.data?.blobs_synced || 0) /
                 (preview?.blobs_to_sync || 1)) * 100
              }
            />
          </div>
        )}

        {step === 'complete' && (
          <div className="py-8 text-center">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h3 className="text-xl font-bold mb-2">
              {isToBackup ? 'Backup Complete!' : 'Restore Complete!'}
            </h3>
            <p className="text-muted-foreground mb-4">
              {syncMutation.data?.blobs_synced} blobs ({formatBytes(syncMutation.data?.bytes_synced || 0)})
            </p>
            <Button onClick={() => onOpenChange(false)}>Close</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

#### 5.2.7 CleanupWizard (3-krokovy wizard)

```tsx
export function CleanupWizard({ open, onClose }) {
  const [step, setStep] = useState(1);
  const [dryRunResult, setDryRunResult] = useState<CleanupResult | null>(null);

  // Step 1: Dry run
  const dryRunMutation = useMutation({
    mutationFn: () => api.cleanupOrphans({ dry_run: true }),
    onSuccess: (result) => {
      setDryRunResult(result);
      setStep(2);
    },
  });

  // Step 3: Execute
  const executeMutation = useMutation({
    mutationFn: () => api.cleanupOrphans({ dry_run: false }),
    onSuccess: () => {
      setStep(3);
      queryClient.invalidateQueries(['inventory']);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Cleanup Orphan Blobs</DialogTitle>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-4 mb-6">
          <StepIndicator step={1} current={step} label="Scan" />
          <StepIndicator step={2} current={step} label="Review" />
          <StepIndicator step={3} current={step} label="Complete" />
        </div>

        {step === 1 && (
          <div className="text-center py-8">
            <p className="mb-4">
              This will scan for orphan blobs that are not referenced by any pack.
            </p>
            <Button onClick={() => dryRunMutation.mutate()}>
              {dryRunMutation.isPending ? 'Scanning...' : 'Start Scan'}
            </Button>
          </div>
        )}

        {step === 2 && dryRunResult && (
          <div>
            <div className="bg-muted p-4 rounded-lg mb-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-2xl font-bold">
                    {dryRunResult.orphans_found}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Orphan blobs found
                  </div>
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {formatBytes(dryRunResult.bytes_freed)}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Will be freed
                  </div>
                </div>
              </div>
            </div>

            {/* List of items to delete */}
            <div className="max-h-60 overflow-y-auto border rounded">
              {dryRunResult.deleted.map(item => (
                <div key={item.sha256} className="flex items-center justify-between p-2 border-b">
                  <div>
                    <div className="font-medium">{item.display_name}</div>
                    <div className="text-xs text-muted-foreground">{item.kind}</div>
                  </div>
                  <div className="text-sm font-mono">
                    {formatBytes(item.size_bytes)}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-between mt-4">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => executeMutation.mutate()}
                disabled={dryRunResult.orphans_found === 0}
              >
                Delete {dryRunResult.orphans_found} Orphans
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="text-center py-8">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h3 className="text-xl font-bold mb-2">Cleanup Complete!</h3>
            <p className="text-muted-foreground mb-4">
              Freed {formatBytes(executeMutation.data?.bytes_freed || 0)}
            </p>
            <Button onClick={onClose}>Close</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

---

## 6. CLI rozsireni

### 6.1 Inventory prikazy

```bash
# Inventory listing
synapse inventory [--kind checkpoint|lora|...] [--status referenced|orphan|missing] [--json]

# Summary only (rychle)
synapse inventory --summary

# Detail blobu
synapse inventory show <sha256> [--json]

# Cleanup orphans
synapse inventory cleanup [--dry-run] [--force]

# Verify integrity
synapse inventory verify [--all] [sha256...]
```

### 6.2 🆕 Backup prikazy

```bash
# Zobrazit stav backup storage
synapse backup status [--json]

# Zalohovat konkretni blob
synapse backup blob <sha256>

# Obnovit blob z backupu
synapse backup restore <sha256>

# Hromadna synchronizace
synapse backup sync [--dry-run] [--direction to_backup|from_backup]

# Smazat z backupu
synapse backup delete <sha256> [--force]

# Konfigurovat backup (alternativa k Settings UI)
synapse backup config --path /mnt/external/synapse-backup [--enable|--disable]
```

### 6.3 Priklad vystupu

```
$ synapse backup status

╭─────────────────────────────────────────────────────────────╮
│  Backup Storage                                             │
├─────────────────────────────────────────────────────────────┤
│  Status:    🟢 Connected                                    │
│  Path:      /mnt/external/synapse-backup                    │
│  Space:     110 GB used / 500 GB total                      │
│                                                             │
│  Blobs:                                                     │
│    ✅ Both locations:    23                                 │
│    💾 Local only:        12  (45 GB NOT BACKED UP!)         │
│    ☁️  Backup only:        8  (30 GB)                        │
│                                                             │
│  Last sync: 2026-01-23 18:00                                │
╰─────────────────────────────────────────────────────────────╯

$ synapse backup sync --dry-run

Backup Sync Preview
═══════════════════

Direction: local → backup
Blobs to sync: 12
Total size: 45.2 GB

Would backup:
  • juggernautXL_v10.safetensors (6.8 GB)
  • sdxl_vae.safetensors (335 MB)
  • detail_tweaker_xl.safetensors (145 MB)
  ... and 9 more

Run with --execute to perform sync.
```

### 6.4 Implementace inventory (cli.py)

```python
inventory_app = typer.Typer(
    name="inventory",
    help="Model inventory management",
)
app.add_typer(inventory_app, name="inventory")


@inventory_app.callback(invoke_without_command=True)
def inventory_list(
    ctx: typer.Context,
    kind: Optional[str] = typer.Option(None, "--kind", "-k", help="Filter by kind"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    summary_only: bool = typer.Option(False, "--summary", help="Show only summary"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all blobs in inventory."""
    if ctx.invoked_subcommand is not None:
        return

    store = get_store()
    require_initialized(store)

    inventory = store.get_inventory(
        kind_filter=AssetKind(kind) if kind else None,
        status_filter=BlobStatus(status) if status else None,
    )

    if json:
        if summary_only:
            output_json(inventory.summary.model_dump())
        else:
            output_json(inventory.model_dump())
        return

    # Summary
    s = inventory.summary
    output_header("Model Inventory")

    summary_table = Table(box=box.ROUNDED)
    summary_table.add_column("Metric")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total blobs", str(s.blobs_total))
    summary_table.add_row("Referenced", f"[green]{s.blobs_referenced}[/green]")
    summary_table.add_row("Orphan", f"[dim]{s.blobs_orphan}[/dim]")
    summary_table.add_row("Missing", f"[red]{s.blobs_missing}[/red]" if s.blobs_missing else "0")
    summary_table.add_row("", "")
    summary_table.add_row("Total size", format_bytes(s.bytes_total))
    summary_table.add_row("Orphan size", format_bytes(s.bytes_orphan))

    console.print(summary_table)

    if summary_only:
        return

    console.print()

    # Items table
    items_table = Table(title=f"Blobs ({len(inventory.items)})", box=box.ROUNDED)
    items_table.add_column("Type", width=6)
    items_table.add_column("Name")
    items_table.add_column("Size", justify="right")
    items_table.add_column("Status")
    items_table.add_column("Used By")

    for item in inventory.items[:50]:  # Limit display
        status_str = {
            "referenced": "[green]REF[/green]",
            "orphan": "[dim]ORPH[/dim]",
            "missing": "[red]MISS[/red]",
        }.get(item.status, item.status)

        used_by = ", ".join(item.used_by_packs[:2])
        if len(item.used_by_packs) > 2:
            used_by += f" +{len(item.used_by_packs) - 2}"

        items_table.add_row(
            item.kind[:6],
            item.display_name[:40],
            format_bytes(item.size_bytes),
            status_str,
            used_by or "[dim]-[/dim]",
        )

    console.print(items_table)

    if len(inventory.items) > 50:
        console.print(f"\n[dim]... and {len(inventory.items) - 50} more[/dim]")


@inventory_app.command("cleanup")
def inventory_cleanup(
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview only"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Remove orphan blobs."""
    store = get_store()
    require_initialized(store)

    result = store.cleanup_orphans(dry_run=dry_run)

    if json:
        output_json(result.model_dump())
        return

    if dry_run:
        output_header("Cleanup Preview (dry run)")
        console.print(f"Orphans found: [bold]{result.orphans_found}[/bold]")
        console.print(f"Would free: [bold]{format_bytes(result.bytes_freed)}[/bold]")

        if result.deleted:
            console.print("\nWould delete:")
            for item in result.deleted[:10]:
                console.print(f"  • {item.display_name} ({format_bytes(item.size_bytes)})")

        console.print("\n[dim]Run with --execute to actually delete[/dim]")
    else:
        output_success(f"Deleted {result.orphans_deleted} orphan(s)")
        console.print(f"Freed: [bold]{format_bytes(result.bytes_freed)}[/bold]")
```

### 6.5 Implementace backup (cli.py)

```python
backup_app = typer.Typer(
    name="backup",
    help="Backup storage management",
)
app.add_typer(backup_app, name="backup")


@backup_app.command("status")
def backup_status(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show backup storage status."""
    store = get_store()
    require_initialized(store)

    status = store.get_backup_status()

    if json:
        output_json(status.model_dump())
        return

    output_header("Backup Storage")

    if not status.enabled:
        console.print("[dim]Backup not configured.[/dim]")
        console.print("\nConfigure with:")
        console.print("  synapse backup config --path /path/to/backup --enable")
        return

    # Status panel
    panel_content = []

    if status.connected:
        panel_content.append(f"Status:    [green]🟢 Connected[/green]")
    else:
        panel_content.append(f"Status:    [red]🔴 Disconnected[/red]")
        if status.error:
            panel_content.append(f"Error:     [red]{status.error}[/red]")

    panel_content.append(f"Path:      {status.path}")

    if status.connected:
        panel_content.append(f"Space:     {format_bytes(status.total_bytes)} used / {format_bytes(status.total_space)} total")
        panel_content.append("")
        panel_content.append("Blobs:")
        panel_content.append(f"  [green]✅ Both locations:[/green]    {status.blobs_both}")
        panel_content.append(f"  [yellow]💾 Local only:[/yellow]        {status.blobs_local_only}  ({format_bytes(status.bytes_local_only)})")
        panel_content.append(f"  [blue]☁️  Backup only:[/blue]        {status.blobs_backup_only}  ({format_bytes(status.bytes_backup_only)})")

        if status.blobs_local_only > 0:
            panel_content.append("")
            panel_content.append(f"[yellow]⚠ {status.blobs_local_only} blobs NOT BACKED UP![/yellow]")

    console.print(Panel("\n".join(panel_content), box=box.ROUNDED))


@backup_app.command("sync")
def backup_sync(
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview only"),
    direction: str = typer.Option("to_backup", "--direction", "-d",
                                   help="Sync direction: to_backup or from_backup"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Sync blobs with backup storage."""
    store = get_store()
    require_initialized(store)

    status = store.get_backup_status()
    if not status.connected:
        output_error("Backup storage not connected")
        raise typer.Exit(1)

    result = store.backup_sync(direction=direction, dry_run=dry_run)

    if json:
        output_json(result.model_dump())
        return

    is_to_backup = direction == "to_backup"
    action = "backup" if is_to_backup else "restore"

    if dry_run:
        output_header(f"Backup Sync Preview ({action})")

        if result.blobs_to_sync == 0:
            console.print("[green]✓[/green] Already synced!")
            return

        console.print(f"Direction:     local {'→' if is_to_backup else '←'} backup")
        console.print(f"Blobs to sync: [bold]{result.blobs_to_sync}[/bold]")
        console.print(f"Total size:    [bold]{format_bytes(result.bytes_to_sync)}[/bold]")

        if result.items:
            console.print(f"\nWould {action}:")
            for item in result.items[:10]:
                console.print(f"  • {item.display_name} ({format_bytes(item.size_bytes)})")
            if len(result.items) > 10:
                console.print(f"  ... and {len(result.items) - 10} more")

        console.print(f"\n[dim]Run with --execute to perform sync.[/dim]")
    else:
        output_success(f"Synced {result.blobs_synced} blob(s)")
        console.print(f"Transferred: [bold]{format_bytes(result.bytes_synced)}[/bold]")


@backup_app.command("blob")
def backup_blob(
    sha256: str = typer.Argument(..., help="SHA256 hash of blob to backup"),
):
    """Backup a specific blob to external storage."""
    store = get_store()
    require_initialized(store)

    status = store.get_backup_status()
    if not status.connected:
        output_error("Backup storage not connected")
        raise typer.Exit(1)

    with console.status(f"Backing up {sha256[:12]}..."):
        result = store.backup_blob(sha256)

    if result.success:
        output_success(f"Backed up {sha256[:12]}...")
        console.print(f"Size: {format_bytes(result.bytes_copied)}")
    else:
        output_error(f"Failed: {result.error}")
        raise typer.Exit(1)


@backup_app.command("restore")
def backup_restore(
    sha256: str = typer.Argument(..., help="SHA256 hash of blob to restore"),
):
    """Restore a blob from backup storage."""
    store = get_store()
    require_initialized(store)

    status = store.get_backup_status()
    if not status.connected:
        output_error("Backup storage not connected")
        raise typer.Exit(1)

    with console.status(f"Restoring {sha256[:12]}..."):
        result = store.restore_blob(sha256)

    if result.success:
        output_success(f"Restored {sha256[:12]}...")
        console.print(f"Size: {format_bytes(result.bytes_copied)}")
    else:
        output_error(f"Failed: {result.error}")
        raise typer.Exit(1)


@backup_app.command("config")
def backup_config(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Backup storage path"),
    enable: bool = typer.Option(False, "--enable", help="Enable backup"),
    disable: bool = typer.Option(False, "--disable", help="Disable backup"),
):
    """Configure backup storage."""
    store = get_store()
    require_initialized(store)

    if enable and disable:
        output_error("Cannot use --enable and --disable together")
        raise typer.Exit(1)

    config = store.get_config()

    if path:
        config.backup_path = path

    if enable:
        if not config.backup_path:
            output_error("Backup path required. Use --path to set it.")
            raise typer.Exit(1)
        config.backup_enabled = True

    if disable:
        config.backup_enabled = False

    store.save_config(config)

    output_success("Backup configuration updated")
    console.print(f"  Path:    {config.backup_path or '[not set]'}")
    console.print(f"  Enabled: {'[green]Yes[/green]' if config.backup_enabled else '[dim]No[/dim]'}")
```

---

## 7. Testy

### 7.1 Backend testy (tests/store/test_inventory.py)

```python
"""Tests for inventory service."""

import pytest
from src.store import Store
from src.store.inventory_service import BlobStatus


class TestInventoryDetection:
    """Test orphan/referenced/missing detection."""

    def test_detects_referenced_blob(self, tmp_path):
        """Blob referencovany packem ma status REFERENCED."""
        store = Store(tmp_path)
        store.init()

        # Create pack with blob
        # ... setup ...

        inventory = store.get_inventory()

        assert any(
            item.status == BlobStatus.REFERENCED
            for item in inventory.items
        )

    def test_detects_orphan_blob(self, tmp_path):
        """Blob bez reference ma status ORPHAN."""
        store = Store(tmp_path)
        store.init()

        # Add blob directly without pack reference
        blob_content = b"orphan blob content"
        sha256 = store.blob_store.adopt_bytes(blob_content)

        inventory = store.get_inventory()

        orphan = next(
            (i for i in inventory.items if i.sha256 == sha256),
            None
        )
        assert orphan is not None
        assert orphan.status == BlobStatus.ORPHAN

    def test_detects_missing_blob(self, tmp_path):
        """Reference na neexistujici blob ma status MISSING."""
        store = Store(tmp_path)
        store.init()

        # Create pack with reference to non-existent blob
        # ... setup lock with fake sha256 ...

        inventory = store.get_inventory()

        assert inventory.summary.blobs_missing > 0


class TestInventoryCleanup:
    """Test cleanup operations."""

    def test_cleanup_dry_run_does_not_delete(self, tmp_path):
        """Dry run nesmaže nic."""
        store = Store(tmp_path)
        store.init()

        # Add orphan blob
        sha256 = store.blob_store.adopt_bytes(b"orphan")

        result = store.cleanup_orphans(dry_run=True)

        assert result.orphans_found == 1
        assert result.orphans_deleted == 0
        assert store.blob_store.blob_exists(sha256)  # Still exists

    def test_cleanup_execute_deletes_orphans(self, tmp_path):
        """Execute smaze orphany."""
        store = Store(tmp_path)
        store.init()

        sha256 = store.blob_store.adopt_bytes(b"orphan")

        result = store.cleanup_orphans(dry_run=False)

        assert result.orphans_deleted == 1
        assert not store.blob_store.blob_exists(sha256)

    def test_cleanup_never_deletes_referenced(self, tmp_path):
        """Cleanup NIKDY nesmaze referencovane bloby."""
        store = Store(tmp_path)
        store.init()

        # Create pack with blob
        # ... setup ...

        result = store.cleanup_orphans(dry_run=False)

        # Referenced blob should still exist
        assert store.blob_store.blob_exists(referenced_sha256)


class TestInventoryImpacts:
    """Test impact analysis."""

    def test_impacts_referenced_blob(self, tmp_path):
        """Impacts pro referencovany blob vraci packs."""
        store = Store(tmp_path)
        store.init()

        # Setup pack with blob
        # ...

        impacts = store.get_blob_impacts(sha256)

        assert not impacts.can_delete_safely
        assert len(impacts.used_by_packs) > 0

    def test_impacts_orphan_blob(self, tmp_path):
        """Impacts pro orphan vraci can_delete_safely=True."""
        store = Store(tmp_path)
        store.init()

        sha256 = store.blob_store.adopt_bytes(b"orphan")

        impacts = store.get_blob_impacts(sha256)

        assert impacts.can_delete_safely
        assert len(impacts.used_by_packs) == 0
```

### 7.2 API testy (tests/store/test_inventory_api.py)

```python
"""Tests for inventory API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestInventoryAPI:
    """Test inventory API endpoints."""

    def test_get_inventory_returns_summary(self, client):
        """GET /inventory vraci summary."""
        response = client.get("/api/store/inventory")
        assert response.status_code == 200
        data = response.json()

        assert "summary" in data
        assert "items" in data
        assert "blobs_total" in data["summary"]

    def test_get_inventory_summary_only(self, client):
        """GET /inventory/summary vraci jen statistiky."""
        response = client.get("/api/store/inventory/summary")
        assert response.status_code == 200
        data = response.json()

        assert "blobs_total" in data
        assert "items" not in data

    def test_cleanup_orphans_409_for_referenced(self, client):
        """DELETE na referencovany blob vraci 409."""
        # Setup referenced blob
        # ...

        response = client.delete(
            f"/api/store/inventory/{referenced_sha256}"
        )

        assert response.status_code == 409
        data = response.json()
        assert "impacts" in data["detail"]


class TestBackupAPI:
    """Test backup API endpoints."""

    def test_backup_status_disabled(self, client):
        """GET /backup/status when backup not configured."""
        response = client.get("/api/store/backup/status")
        assert response.status_code == 200
        data = response.json()

        assert data["enabled"] is False
        assert data["connected"] is False

    def test_backup_status_connected(self, client, mock_backup_storage):
        """GET /backup/status when backup connected."""
        response = client.get("/api/store/backup/status")
        assert response.status_code == 200
        data = response.json()

        assert data["enabled"] is True
        assert data["connected"] is True
        assert "total_blobs" in data

    def test_backup_blob_success(self, client, mock_backup_storage, test_blob):
        """POST /backup/blob/{sha256} copies blob to backup."""
        sha256 = test_blob["sha256"]

        response = client.post(f"/api/store/backup/blob/{sha256}")
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["bytes_copied"] == test_blob["size"]

    def test_backup_blob_503_not_connected(self, client):
        """POST /backup/blob fails when backup not connected."""
        response = client.post("/api/store/backup/blob/abc123")
        assert response.status_code == 503

    def test_restore_blob_success(self, client, mock_backup_storage, backup_only_blob):
        """POST /backup/restore/{sha256} restores blob from backup."""
        sha256 = backup_only_blob["sha256"]

        response = client.post(f"/api/store/backup/restore/{sha256}")
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    def test_restore_blob_404_not_on_backup(self, client, mock_backup_storage):
        """POST /backup/restore fails for blob not on backup."""
        response = client.post("/api/store/backup/restore/nonexistent")
        assert response.status_code == 404

    def test_backup_sync_dry_run(self, client, mock_backup_storage, local_only_blobs):
        """POST /backup/sync dry_run returns preview."""
        response = client.post("/api/store/backup/sync", json={
            "direction": "to_backup",
            "dry_run": True,
        })
        assert response.status_code == 200
        data = response.json()

        assert data["dry_run"] is True
        assert data["blobs_to_sync"] == len(local_only_blobs)
        assert data["blobs_synced"] == 0

    def test_delete_blob_with_target(self, client, mock_backup_storage, both_location_blob):
        """DELETE /inventory/{sha256}?target=local deletes only from local."""
        sha256 = both_location_blob["sha256"]

        response = client.delete(
            f"/api/store/inventory/{sha256}",
            params={"target": "local"}
        )
        assert response.status_code == 200
        data = response.json()

        assert "local" in data["deleted_from"]
        assert data["remaining_on"] == "backup"

    def test_delete_last_copy_requires_force(self, client, local_only_blob):
        """DELETE last copy without force returns 409."""
        sha256 = local_only_blob["sha256"]

        response = client.delete(
            f"/api/store/inventory/{sha256}",
            params={"target": "both"}
        )
        assert response.status_code == 409
        assert "last copy" in response.json()["detail"].lower()
```

### 7.3 🆕 Backup testy (tests/store/test_backup.py)

```python
"""Tests for backup storage functionality."""

import pytest
from pathlib import Path
from src.store import Store
from src.store.inventory_service import BlobLocation


class TestBackupStorage:
    """Test backup storage operations."""

    @pytest.fixture
    def backup_path(self, tmp_path):
        """Create temporary backup storage path."""
        backup = tmp_path / "backup"
        backup.mkdir()
        return backup

    @pytest.fixture
    def store_with_backup(self, tmp_path, backup_path):
        """Store with backup configured."""
        store = Store(tmp_path)
        store.init()
        store.configure_backup(path=str(backup_path), enabled=True)
        return store

    def test_backup_blob_copies_to_backup(self, store_with_backup, backup_path):
        """Backup blob copies file to backup storage."""
        # Add blob to local store
        sha256 = store_with_backup.blob_store.adopt_bytes(b"test content")

        # Backup
        result = store_with_backup.backup_blob(sha256)

        assert result.success
        # Verify file exists on backup
        backup_blob = backup_path / ".synapse/store/data/blobs/sha256" / sha256[:2] / sha256
        assert backup_blob.exists()

    def test_restore_blob_copies_to_local(self, store_with_backup, backup_path):
        """Restore blob copies file from backup to local."""
        # Setup: blob exists only on backup
        sha256 = "abc123def456..."
        backup_blob_dir = backup_path / ".synapse/store/data/blobs/sha256" / sha256[:2]
        backup_blob_dir.mkdir(parents=True)
        (backup_blob_dir / sha256).write_bytes(b"backup content")

        # Restore
        result = store_with_backup.restore_blob(sha256)

        assert result.success
        assert store_with_backup.blob_store.blob_exists(sha256)

    def test_location_detection_both(self, store_with_backup, backup_path):
        """Detects BOTH when blob is on both local and backup."""
        sha256 = store_with_backup.blob_store.adopt_bytes(b"content")
        store_with_backup.backup_blob(sha256)

        inventory = store_with_backup.get_inventory()
        item = next(i for i in inventory.items if i.sha256 == sha256)

        assert item.location == BlobLocation.BOTH
        assert item.on_local is True
        assert item.on_backup is True

    def test_location_detection_local_only(self, store_with_backup):
        """Detects LOCAL_ONLY when blob is only local."""
        sha256 = store_with_backup.blob_store.adopt_bytes(b"local only")

        inventory = store_with_backup.get_inventory()
        item = next(i for i in inventory.items if i.sha256 == sha256)

        assert item.location == BlobLocation.LOCAL_ONLY
        assert item.on_local is True
        assert item.on_backup is False

    def test_location_detection_backup_only(self, store_with_backup, backup_path):
        """Detects BACKUP_ONLY when blob is only on backup."""
        sha256 = "backup_only_blob"
        backup_blob_dir = backup_path / ".synapse/store/data/blobs/sha256" / sha256[:2]
        backup_blob_dir.mkdir(parents=True)
        (backup_blob_dir / sha256).write_bytes(b"backup only content")

        inventory = store_with_backup.get_inventory()
        item = next((i for i in inventory.items if i.sha256 == sha256), None)

        assert item is not None
        assert item.location == BlobLocation.BACKUP_ONLY
        assert item.on_local is False
        assert item.on_backup is True

    def test_delete_local_preserves_backup(self, store_with_backup):
        """Deleting from local preserves backup copy."""
        sha256 = store_with_backup.blob_store.adopt_bytes(b"content")
        store_with_backup.backup_blob(sha256)

        result = store_with_backup.delete_blob(sha256, target="local")

        assert result["deleted_from"] == ["local"]
        assert result["remaining_on"] == "backup"
        assert not store_with_backup.blob_store.blob_exists(sha256)
        # Backup still exists
        inventory = store_with_backup.get_inventory()
        item = next(i for i in inventory.items if i.sha256 == sha256)
        assert item.location == BlobLocation.BACKUP_ONLY

    def test_delete_last_copy_requires_force(self, store_with_backup):
        """Deleting last copy requires force=True."""
        sha256 = store_with_backup.blob_store.adopt_bytes(b"only copy")

        result = store_with_backup.delete_blob(sha256, target="both", force=False)

        assert result["deleted"] is False
        assert "last copy" in result["reason"].lower()
        # Blob still exists
        assert store_with_backup.blob_store.blob_exists(sha256)

    def test_backup_disconnected_detection(self, store_with_backup, backup_path):
        """Detects when backup storage is disconnected."""
        # Remove backup path to simulate disconnection
        import shutil
        shutil.rmtree(backup_path)

        status = store_with_backup.get_backup_status()

        assert status.enabled is True
        assert status.connected is False


class TestAutoRestore:
    """Test auto-restore when pack needs blob from backup."""

    def test_use_pack_triggers_restore(self, store_with_backup, backup_path):
        """Using pack with backup-only blob triggers restore."""
        # Setup: pack references blob that's only on backup
        # ... create pack and lock ...
        # ... put blob only on backup ...

        # This should trigger auto-restore
        result = store_with_backup.use_pack("TestPack")

        # Blob should now be local
        assert store_with_backup.blob_store.blob_exists(sha256)
        assert result.restored_blobs == [sha256]
```

---

## 8. Migrace Settings

### 8.1 Co presunout z Settings do Model Inventory

| Puvodni v Settings | Novy umisteni |
|-------------------|---------------|
| Doctor diagnostika | Model Inventory > Quick Actions |
| Verify blobs | Model Inventory > Quick Actions |
| Clean partial | Model Inventory > Cleanup wizard |
| Disk usage | Model Inventory > Dashboard |

### 8.2 Co zustane v Settings

- Store root path (read-only display)
- Default UI set selection
- Civitai API key input
- UI attachment configuration
- Theme/appearance (pokud existuje)
- ✅ **Backup Storage konfigurace** (implementováno 2026-01-25):
  - Enable/disable backup toggle
  - Backup path input
  - Auto-backup new models toggle
  - Warn before delete last copy toggle
  - Connection status display

---

## 9. Implementacni plan

### ✅ Iterace 1: Backend - Inventory Service (DOKONČENO 2026-01-24)
- [x] ✅ Vytvorit `inventory_service.py` → **IMPL:** `src/store/inventory_service.py` (300+ řádků)
- [x] ✅ Pridat modely do `models.py` → **IMPL:** BlobStatus, BlobLocation, BlobOrigin, PackReference, InventoryItem, InventorySummary, InventoryResponse, CleanupResult, ImpactAnalysis, BackupStats
- [x] ✅ Integrovat do `Store` tridy → **IMPL:** `src/store/__init__.py` - delegované metody
- [x] ✅ Pridat API endpointy → **IMPL:** `src/store/api.py` - 6 endpointů:
  - GET `/api/store/inventory` (filtering, sorting, pagination)
  - GET `/api/store/inventory/summary`
  - GET `/api/store/inventory/{sha256}`
  - POST `/api/store/inventory/cleanup-orphans`
  - DELETE `/api/store/inventory/{sha256}`
  - POST `/api/store/inventory/verify`
- [x] ✅ Napsat backend testy → **IMPL:** `tests/store/test_inventory.py` (21 testů)

### ✅ Iterace 2: Backend - Backup Storage (DOKONČENO 2026-01-24)
- [x] ✅ Vytvorit `backup_service.py` → **IMPL:** `src/store/backup_service.py` (~450 řádků)
  - BackupService class s metodami: get_status, backup_blob, restore_blob, delete_from_backup, sync, verify_backup_blob
  - Exceptions: BackupError, BackupNotEnabledError, BackupNotConnectedError, BlobNotFoundError, InsufficientSpaceError
- [x] ✅ Implementovat backup/restore operace → **IMPL:**
  - backup_blob() - kopíruje local → backup s verifikací
  - restore_blob() - kopíruje backup → local s verifikací
  - delete_from_backup() - smaže z backupu s confirm guard
  - sync() - hromadná synchronizace (to_backup/from_backup, dry_run support)
- [x] ✅ Location detection → **IMPL:** `inventory_service.py` aktualizován
  - Detekuje LOCAL_ONLY, BACKUP_ONLY, BOTH, NOWHERE
  - Inventory správně ukazuje backup blobs jako BACKUP_ONLY status
- [x] ✅ Pridat backup API endpointy → **IMPL:** `src/store/api.py` - 7 endpointů:
  - GET `/api/store/backup/status`
  - POST `/api/store/backup/blob/{sha256}` (backup)
  - POST `/api/store/backup/restore/{sha256}` (restore)
  - DELETE `/api/store/backup/blob/{sha256}` (delete from backup)
  - POST `/api/store/backup/sync`
  - PUT `/api/store/backup/config`
  - GET `/api/store/backup/blob/{sha256}/warning`
- [x] ✅ Guard rails → **IMPL:**
  - is_last_copy() - detekuje zda je blob pouze na jednom místě
  - get_delete_warning() - varování před mazáním poslední kopie
  - confirm flag pro delete operace
- [x] ✅ Napsat backup testy → **IMPL:** `tests/store/test_backup.py` (29 testů)
  - TestBackupStatus (5 testů)
  - TestBackupBlob (5 testů)
  - TestRestoreBlob (4 testy)
  - TestDeleteFromBackup (3 testy)
  - TestSyncBackup (3 testy)
  - TestBackupLocationDetection (3 testy)
  - TestGuardRails (4 testy)
  - TestBackupVerification (2 testy)
- [x] ✅ Modely v `models.py`:
  - BackupConfig - konfigurace backupu
  - BackupStatus - stav připojení
  - BackupOperationResult - výsledek backup/restore
  - BackupDeleteResult - výsledek mazání
  - SyncItem, SyncResult - sync operace

### ✅ Iterace 3: CLI (DOKONČENO)
- [x] Pridat `inventory` subcommand s Rich formatovanim
  - Implementováno: `synapse inventory list|orphans|missing|cleanup|impacts|verify`
  - Rich tabulky pro inventory listing s filtrováním dle kind/status
  - Progress bar pro cleanup a verify operace
- [x] Pridat `backup` subcommand (status, sync, blob, restore, config)
  - Implementováno: `synapse backup status|sync|blob|restore|delete|config`
  - Dry-run podpora pro sync operace
  - Guard rails pro nebezpečné operace (delete)
- [x] Cleanup command s progress
  - Rich Progress spinner pro dlouhotrvající operace
  - Dry-run vs --execute režimy
- [x] Napsat CLI testy
  - 34 testů v tests/store/test_cli.py
  - TestInventoryList, TestInventoryOrphans, TestInventoryMissing
  - TestInventoryCleanup, TestInventoryImpacts, TestInventoryVerify
  - TestBackupStatus, TestBackupSync, TestBackupBlob
  - TestBackupRestore, TestBackupConfig, TestStoreNotInitialized

**Implementační detaily:**
- Rozšířen `src/store/cli.py` o dva nové Typer subcommand skupiny
- Helper funkce pro formátování: `_format_size`, `_location_display`, `_status_display`
- Všech 431 testů projde (včetně 34 nových CLI testů)

### ✅ Iterace 4: UI - Dashboard & BlobsTable (DOKONČENO 2026-01-24)
- [x] ✅ Vytvorit `InventoryPage.tsx` → **IMPL:** `apps/web/src/components/modules/inventory/InventoryPage.tsx`
- [x] ✅ `InventoryStats` dashboard s backup kartou → **IMPL:** `apps/web/src/components/modules/inventory/InventoryStats.tsx`
  - 4 karty: Local Disk, Backup Storage, Status Overview, Quick Actions
  - Progress bars pro disk usage
  - Dynamické zobrazení podle backup stavu (enabled/connected/disconnected)
- [x] ✅ 🔥 `BlobsTable` - HLAVNI KOMPONENTA → **IMPL:** `apps/web/src/components/modules/inventory/BlobsTable.tsx` (~450 řádků)
  - [x] Vsechny sloupce vcetne Location (Checkbox, Icon, Name, Type, Size, Status, Location, Used By, Actions)
  - [x] Row actions (backup/restore/delete) - quick actions + context menu
  - [x] Bulk selection a akce - select all, bulk backup/restore/delete
  - [x] Sorting a filtrovani - sortable headers pro Name, Type, Size, Status, Location
- [x] ✅ `LocationIcon` a `StatusBadge` komponenty → **IMPL:**
  - `LocationIcon.tsx` - ikony pro BOTH/LOCAL_ONLY/BACKUP_ONLY/NOWHERE s barvami
  - `StatusBadge.tsx` - badges pro REFERENCED/ORPHAN/MISSING/BACKUP_ONLY
  - `AssetKindIcon.tsx` - ikony pro checkpoint/lora/vae/embedding/controlnet/upscaler
- [x] ✅ `InventoryFilters` komponenta → **IMPL:** `apps/web/src/components/modules/inventory/InventoryFilters.tsx`
  - Search input
  - Kind/Status/Location dropdown filters
- [x] ✅ Navigace a routing
  - Přidáno do `Sidebar.tsx` - "Model Inventory" mezi Packs a Profiles
  - Přidána route `/inventory` v `App.tsx`
- [x] ✅ Typy a utility
  - `types.ts` - všechny TypeScript typy (InventoryItem, BackupStatus, etc.)
  - `utils.ts` - formatBytes, formatRelativeTime, copyToClipboard
  - `index.ts` - re-exporty

**Implementační detaily:**
- 10 nových souborů v `apps/web/src/components/modules/inventory/`
- Použití existujících UI komponent (Card, Button, ProgressBar, BreathingOrb)
- React Query pro data fetching s auto-refresh
- Context menu pro row actions
- Responsivní grid pro stats dashboard
- Všech 431 testů projde + TypeScript type check OK

### ✅ Iterace 5: UI - Wizards & Dialogs (DOKONČENO 2026-01-24)
- [x] `DeleteConfirmationDialog.tsx` - Guard rails dialog s isLastCopy/isReferenced warnings
- [x] `CleanupWizard.tsx` - 3-krokovy wizard (Scan → Review → Complete)
- [x] `BackupSyncWizard.tsx` - Preview → Progress → Complete pattern
- [x] `ImpactsDialog.tsx` - Show blob dependencies (packs, UIs)
- [x] `VerifyProgressDialog.tsx` - SHA256 verification progress

**Implementace:**
- Všechny dialogy používají `createPortal` pattern (jako ImportWizardModal)
- Glass morphism design, Escape key handling
- Plná integrace v `InventoryPage.tsx` - state management, React Query mutations
- index.ts aktualizován s exporty
- Všech 431 testů projde + TypeScript type check OK

### ✅ Iterace 6: Integrace a finalizace (DOKONČENO 2026-01-24)
- [x] ✅ Navigace již v pořádku (Packs → Model Inventory → Profiles → Browse → Settings)
- [x] ✅ Doctor button přidán do Quick Actions v InventoryStats
  - Volá `/api/store/doctor` s `rebuild_views: true`
  - Invaliduje inventory query po úspěchu
- [x] ✅ Auto-restore při `use` operaci
  - `ProfileService._install_missing_blobs()` nyní nejprve zkouší restore z backupu
  - Pokud blob existuje na backupu ale ne lokálně, automaticky ho obnoví
  - Teprve pak fallback na download z URL
  - Úpravy: `profile_service.py` (backup_service integration), `__init__.py` (set_backup_service)
- [x] ✅ Frontend testy
  - Nový soubor: `apps/web/src/__tests__/inventory-utils.test.ts` (49 testů)
  - Testy: formatBytes, formatRelativeTime, filter logic, guard rails, bulk actions
- [x] ✅ Dokumentace
  - Rozšířeno `src/store/README.md` o sekce:
    - Model Inventory (statusy, lokace, CLI příkazy, API endpointy)
    - Backup Storage (konfigurace, CLI příkazy, API endpointy, guard rails, auto-restore)

**Implementační detaily:**
- ProfileService získal `backup_service` dependency pro auto-restore
- Metoda `set_backup_service()` umožňuje lazy initialization
- Dokumentace v `src/store/README.md` - kompletní reference pro CLI i API
- Všech 431 backend testů + 389 frontend testů prošlo
- TypeScript type check OK

---

## 10. Otevrene otazky

### Inventory

1. **Grouping by model identity** - Seskupit ruzne verze stejneho modelu?
   - Pro: Cleaner UI, "keep newest" akce
   - Proti: Komplexnejsi implementace

2. **Background verification** - Overovat hashe na pozadi?
   - Pro: Lepsi UX, bez blokovani
   - Proti: Komplexnejsi state management

3. **Size limits/warnings** - Varovat pri velkych packach?
   - Potreba definovat prahy

### Backup Storage

4. **Multiple backup locations** - Podporovat vice backup zarizeni?
   - Napr. "work backup" a "home backup"
   - Komplexni, mozna v budoucnosti

5. **Incremental sync** - Zaznamenavat zmeny pro rychlejsi sync?
   - Potreba tracking "last synced" timestamp
   - Nebo full scan pri kazdem sync?

6. **Backup verification** - Jak casto overovat integritu backupu?
   - Pri kazdem pripojeni?
   - Na vyzadani?
   - Periodic background check?

7. **Network storage** - Podporovat NAS/sitove disky?
   - SMB/CIFS, NFS mounts
   - Pomale operace - potreba progress indikace
   - Timeout handling

8. **Compression** - Komprimovat bloby na backupu?
   - Pro: Mensi misto
   - Proti: Pomale restore, CPU overhead
   - Safetensors uz jsou komprimovane

9. **Auto-backup policy** - Automaticka zaloha novych blobu?
   - "Backup on download" option
   - Nebo manualni sync?

---

## 11. Slovnicek pojmu

| Pojem | Vyznam |
|-------|--------|
| **Blob** | Fyzicky soubor v content-addressable storage (identifikovany SHA256) |
| **Pack** | Logicka skupina modelu s definici (pack.json) a zamkem (lock.json) |
| **Lock** | Resolved zavislosti packu s konkretnimi SHA256 referencemi |
| **Orphan** | Blob existujici v storage, ale nereferencovany zadnym packem |
| **Missing** | Reference na blob, ktery neexistuje nikde (ani local, ani backup) |
| **Backup Storage** | Externi zalozni disk s kopii blob storage |
| **Location** | Kde se blob nachazi: LOCAL_ONLY, BACKUP_ONLY, BOTH, NOWHERE |

---

*Vytvoreno: 2026-01-24*
*Aktualizovano: 2026-01-24 (pridana Backup Storage sekce, BlobsTable specifikace)*
*Aktualizovano: 2026-01-24 (Iterace 1 DOKONČENA - backend inventory service)*
*Aktualizovano: 2026-01-24 (Iterace 2 DOKONČENA - backup_service.py, API endpointy, 29 testů)*
*Aktualizovano: 2026-01-24 (Iterace 3 DOKONČENA - CLI příkazy inventory/backup, 34 testů)*
*Aktualizovano: 2026-01-24 (Iterace 4 DOKONČENA - UI komponenty: InventoryPage, InventoryStats, BlobsTable, LocationIcon, StatusBadge, AssetKindIcon, InventoryFilters)*
*Aktualizovano: 2026-01-24 (CLI backup pull/push implementováno - viz sekce 6.6)*
*Tento navrh vychazi z detailni analyzy existujici architektury Synapse Store v2.*

---

## 12. Pack-Level Backup v UI (PackDetailPage)

### 12.1 Motivace

Uživatel chce mít možnost:
1. **Zálohovat pack** bez aktivace work profilu
2. **Obnovit pack** bez aktivace work profilu
3. Zůstat na global profilu 99% času, ale mít modely dostupné

**Use case:**
```
1. Smazat lokální modely (uvolnit místo) → synapse backup push MyPack --cleanup
2. Později: obnovit modely BEZ aktivace → synapse backup pull MyPack --execute
3. Modely jsou lokálně, uživatel je stále na global profilu
```

### 12.2 CLI - již implementováno ✅

```bash
# Pack-level backup operace (2026-01-24)
synapse backup pull <pack> [--execute] [--json]   # Restore z backupu
synapse backup push <pack> [--execute] [--json]   # Zálohovat
synapse backup push <pack> --execute --cleanup    # Zálohovat + smazat lokální

# Tři úrovně granularity:
BLOB:   synapse backup blob/restore <sha256>    (single file)
PACK:   synapse backup pull/push <pack>         (all pack blobs)
ALL:    synapse backup sync                     (entire store)
```

### 12.3 UI Design - PackDetailPage

#### 12.3.1 Umístění

Na **PackDetailPage** vedle existujícího "Use" tlačítka přidat **Storage Actions**:

```
┌──────────────────────────────────────────────────────────────────┐
│  Pack: Juggernaut_XL                                             │
│  ───────────────────────────────────────────────────────────────│
│                                                                  │
│  [Preview Gallery...]                                            │
│                                                                  │
│  ═══════════════════════════════════════════════════════════════│
│  ACTIONS                                                         │
│  ───────────────────────────────────────────────────────────────│
│                                                                  │
│  Profile Actions:                                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  [  Use  ]   Aktivovat work profil work__Juggernaut_XL     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Storage Actions:              [Backup Status: ✅ 3/3 synced]   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  [↓ Pull]  [↑ Push]  [↑ Push & Free Space]                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Dependencies (3):                                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ☐ juggernautXL_v9.safetensors  │ 6.8 GB │ ✅ BOTH │ ckpt  │ │
│  │ ☐ sdxl_vae.safetensors         │ 335 MB │ 💾 LOCAL│ vae   │ │
│  │ ☐ detail_tweaker_xl.safetensors│ 145 MB │ ✅ BOTH │ lora  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Legend:
  ✅ BOTH   - synced (local + backup)
  💾 LOCAL  - only local (NOT backed up!)
  ☁️ BACKUP - only on backup (can restore)
  ❌ MISSING - nowhere (error)
```

#### 12.3.2 Stavy a akce

| Pack Blob Status | Dostupné akce | Hlavní CTA |
|------------------|---------------|------------|
| All LOCAL_ONLY | Push, Push & Free | **[↑ Push]** (amber warning) |
| All BOTH | Push & Free (no-op push) | *dimmed* |
| All BACKUP_ONLY | Pull | **[↓ Pull]** (blue) |
| Mixed | Pull, Push | Obě enabled |
| Some MISSING | Pull (partial), Warning | Warning banner |

#### 12.3.3 Komponenty

**PackStorageStatus** - mini status card:
```tsx
interface PackStorageStatusProps {
  packName: string;
  blobs: PackBlobStatus[];
  backupConnected: boolean;
}

// Zobrazí: "3/3 synced" nebo "2/3 local only" nebo "1/3 backup only"
```

**PackStorageActions** - action buttons:
```tsx
interface PackStorageActionsProps {
  packName: string;
  canPull: boolean;   // má bloby jen na backupu
  canPush: boolean;   // má bloby jen lokálně
  onPull: () => void;
  onPush: (cleanup: boolean) => void;
}
```

**PackBlobsTable** - mini verze BlobsTable:
```tsx
// Zobrazuje jen bloby daného packu
// Sloupce: Name, Size, Location, Kind
// Bez bulk actions (ty jsou na úrovni packu)
```

#### 12.3.4 Dialogy

**PullConfirmDialog:**
```
┌─────────────────────────────────────────────────────┐
│  ↓ Pull Pack from Backup                            │
│  ───────────────────────────────────────────────────│
│                                                     │
│  Restore 2 blobs from backup:                       │
│                                                     │
│  • juggernautXL_v9.safetensors (6.8 GB)            │
│  • sdxl_vae.safetensors (335 MB)                   │
│                                                     │
│  Total: 7.1 GB                                      │
│                                                     │
│  ℹ️ Profile stays on global                         │
│                                                     │
│  ──────────────────────────────────────────────────│
│  [Cancel]                        [Restore from Backup]│
└─────────────────────────────────────────────────────┘
```

**PushConfirmDialog:**
```
┌─────────────────────────────────────────────────────┐
│  ↑ Push Pack to Backup                              │
│  ───────────────────────────────────────────────────│
│                                                     │
│  Backup 2 blobs to external storage:                │
│                                                     │
│  • juggernautXL_v9.safetensors (6.8 GB)            │
│  • detail_tweaker_xl.safetensors (145 MB)          │
│                                                     │
│  Total: 7.0 GB                                      │
│                                                     │
│  ☐ Delete local copies after backup (free 7.0 GB)  │
│                                                     │
│  ──────────────────────────────────────────────────│
│  [Cancel]                              [Backup Now]  │
└─────────────────────────────────────────────────────┘
```

### 12.4 API endpointy - již implementováno ✅

```
POST /api/packs/{name}/pull   → store.pull_pack(name, dry_run)
POST /api/packs/{name}/push   → store.push_pack(name, dry_run, cleanup)
```

Alternativně použít existující backup endpointy:
```
POST /api/store/backup/pull-pack/{name}
POST /api/store/backup/push-pack/{name}
```

### 12.5 Implementační plán

#### ✅ Iterace 7: Pack Backup UI (DOKONČENO 2026-01-24)

- [x] `PackStorageStatus.tsx` - mini status indicator
- [x] `PackStorageActions.tsx` - Pull/Push/Push&Free buttons
- [x] `PackBlobsTable.tsx` - mini tabulka blobů packu
- [x] `PullConfirmDialog.tsx` - potvrzení pull operace
- [x] `PushConfirmDialog.tsx` - potvrzení push operace s cleanup checkbox
- [x] Integrace do `PackDetailPage.tsx`
- [x] API endpointy: `/api/store/backup/pull-pack/{name}`, `/api/store/backup/push-pack/{name}`, `/api/store/backup/pack-status/{name}`
- [x] TypeScript typy: `PackBackupStatusResponse`, `PackPullPushResponse` v `inventory/types.ts`
- [ ] Frontend testy (budoucí iterace)
- [ ] E2E test celého workflow (budoucí iterace)

**Implementace (2026-01-24):**
- Backend: 3 nové API endpointy v `src/store/api.py`
- Frontend: 5 nových komponent v `apps/web/src/components/modules/packs/`
- Integrace: Storage sekce v PackDetailPage s tabulkou blobů a akčními tlačítky
- Verify: Všech 448 testů prošlo

---

### 12.6 CLI Reference (implementováno 2026-01-24)

Sekce 6 (CLI rozšíření) doplněna o pack-level operace:

```bash
# Pack-level backup příkazy
synapse backup pull <pack>               # Preview (dry run)
synapse backup pull <pack> --execute     # Skutečně obnovit

synapse backup push <pack>               # Preview (dry run)
synapse backup push <pack> --execute     # Skutečně zálohovat
synapse backup push <pack> --execute --cleanup  # Zálohovat + smazat lokální
```

**Testy:** `tests/store/test_backup.py`
- `TestBackupPullPack` (4 testy)
- `TestBackupPushPack` (4 testy)
- `TestPullPushRoundTrip` (1 test)

---

## 13. CODE REVIEW - Pack Backup UI (2026-01-24)

### 13.1 Nenavazující části (díry v implementaci)

#### 🔴 P1: Duplicitní `formatBytes` funkce
**Problém:** Funkce `formatBytes` je zkopírována ve 3 souborech:
- `PullConfirmDialog.tsx:14`
- `PushConfirmDialog.tsx:16`
- `PackBlobsTable.tsx:7`

**Řešení:** Přesunout do sdíleného utility souboru `apps/web/src/lib/format.ts`

---

#### 🔴 P2: PushConfirmDialog - "Free only" use case nefunguje
**Problém:** Když jsou všechny bloby už zálohované (`local_only=0`, `both>0`), uživatel nemůže použít "Push & Free" k uvolnění místa.

**Aktuální logika:**
```tsx
disabled={isLoading || (blobsToBackup.length === 0 && !cleanup)}
```

Když `blobsToBackup.length === 0` a uživatel zaškrtne cleanup, tlačítko se aktivuje, ale dialog zobrazuje "All blobs already backed up" bez seznamu co se bude mazat.

**Řešení:** Přidat druhou sekci v dialogu pro "Blobs to free" když jsou synced.

---

#### 🟡 P3: Chybí invalidace `['pack', packName]` po pull/push
**Problém:** Po úspěšném pull se změní stav instalace blobů, ale pack detail query se neinvaliduje.

**Dopad:** UI může ukazovat staré hodnoty `installed: false` i po obnovení z backupu.

**Řešení:** V `onSuccess` callbackech mutací přidat:
```tsx
queryClient.invalidateQueries({ queryKey: ['pack', packName] })
```

---

#### 🟡 P4: `pull_pack` backend má neočekávaný fallback na download z URL
**Problém:** Kód v `src/store/__init__.py:1459-1465`:
```python
# Blob not on backup - try download from URL as fallback
if resolved.artifact.download and resolved.artifact.download.urls:
    if not dry_run:
        self.blob_store.download(resolved.artifact.download.urls[0], sha256)
```

**Dopad:** Uživatel očekává "restore z backupu", ale systém může stahovat z internetu bez upozornění.

**Řešení:** Odstranit fallback nebo explicitně to oznámit v UI/výsledku.

---

#### 🟡 P5: `SyncItem` v backendu nemá `kind` field
**Problém:** `SyncItem` model (`src/store/models.py`) obsahuje `kind`, ale `pull_pack`/`push_pack` metody ho nenastavují:
```python
items_to_restore.append(SyncItem(
    sha256=sha256,
    size_bytes=resolved.artifact.size_bytes or 0,
    display_name=display_name,
    # CHYBÍ: kind=...
))
```

**Dopad:** API vrací `kind: null` nebo default hodnotu.

**Řešení:** Přidat `kind=dep.kind` při vytváření SyncItem.

---

### 13.2 Klasické review (kvalita kódu)

#### 🟡 R1: `useState(initialCleanup)` se neaktualizuje při změně prop
**Soubor:** `PushConfirmDialog.tsx:37`

**Problém:**
```tsx
const [cleanup, setCleanup] = useState(initialCleanup)
```
Když se `initialCleanup` změní (např. uživatel klikne "Push & Free" místo "Push"), `cleanup` state zůstane na staré hodnotě.

**Řešení:** Přidat `useEffect` nebo použít `key` prop pro reset:
```tsx
useEffect(() => {
  setCleanup(initialCleanup)
}, [initialCleanup])
```

---

#### 🟡 R2: Chybí loading state pro backup status query
**Soubor:** `PackDetailPage.tsx`

**Problém:** Storage sekce se nezobrazí dokud `backupStatus` není loaded:
```tsx
{backupStatus && (
  <Card>...
```

**Řešení:** Přidat skeleton loader nebo použít `isLoading` z query.

---

#### 🟢 R3: Dialogy nemají klávesové zkratky
**Problém:**
- Escape nezavírá dialog
- Enter nepotvrzuje akci

**Řešení:** Přidat `useEffect` s keyboard event listenery.

---

#### 🟢 R4: Chybí validace `pack_name` v API
**Soubor:** `src/store/api.py`

**Problém:** Endpointy přijímají `pack_name` bez validace na path traversal (`../../../etc/passwd`).

**Řešení:** Přidat validaci nebo sanitizaci v `require_initialized` dependency.

---

#### 🟢 R5: `display_name` logika není konzistentní
**Backend:** `src/store/__init__.py:1450-1451`
```python
display_name = dep.expose.filename if dep and dep.expose else resolved.dependency_id
```

**Problém:** `dep.name` by byl lepší user-friendly název než `dependency_id` nebo `expose.filename`.

---

### 13.3 Chybějící testy

#### ❌ T1: Frontend unit testy pro komponenty
- `PackStorageStatus.test.tsx`
- `PackStorageActions.test.tsx`
- `PullConfirmDialog.test.tsx`
- `PushConfirmDialog.test.tsx`

#### ❌ T2: API integration testy
- Test pro `GET /api/store/backup/pack-status/{name}`
- Test pro error handling (pack not found, backup not enabled)

#### ❌ T3: E2E test workflow
- Import pack → Push → Free → Pull → Verify installed

---

### 13.4 Doporučené pořadí oprav

1. **P1** - formatBytes duplikace (quick win, čistý kód)
2. **P3** - invalidace pack query (bug fix)
3. **R1** - useState sync (bug fix)
4. **P5** - SyncItem kind field (data consistency)
5. **P2** - "Free only" use case (feature completion)
6. **R2** - loading skeleton (UX)
7. **P4** - pull_pack fallback (unexpected behavior)
8. **R3-R5** - nice-to-have improvements
9. **T1-T3** - testy

---

### 13.5 OPRAVY PROVEDENY (2026-01-24)

Všechny priority P1-P5, R1-R2 byly opraveny:

| # | Oprava | Soubory |
|---|--------|---------|
| **P1** | ✅ `formatBytes` extrahována do `apps/web/src/lib/utils/format.ts` | PullConfirmDialog, PushConfirmDialog, PackBlobsTable |
| **P2** | ✅ Push & Free funguje i když jsou všechny bloby synced | PushConfirmDialog.tsx |
| **P3** | ✅ Invalidace `['pack', packName]` po pull/push | PackDetailPage.tsx |
| **P4** | ✅ URL fallback odstraněn, vrací error místo tichého stahování | src/store/__init__.py |
| **P5** | ✅ `kind` field přidán do SyncItem modelu a nastavován v pull/push | models.py, __init__.py |
| **R1** | ✅ `useEffect` sync pro `initialCleanup` prop | PushConfirmDialog.tsx |
| **R2** | ✅ Loading skeleton pro backup status | PackDetailPage.tsx |

**Zůstává k řešení (nice-to-have):**
- R3: Klávesové zkratky pro dialogy
- R4: Validace pack_name na path traversal
- R5: Konzistentní display_name logika
- T1-T3: Chybějící testy

**Verify:** Všech 448 testů prošlo.

---

## 14. Settings - Backup Storage Configuration (2026-01-25)

### 14.1 Problém

V InventoryStats.tsx bylo tlačítko "Configure in Settings →" které nikam nevedlo - Backup Storage konfigurace v Settings chyběla.

### 14.2 Implementace

**Backend:**
- ✅ `BackupStatus` model rozšířen o `auto_backup_new`, `warn_before_delete_last_copy`, `total_space`
- ✅ `backup_service.py` - všechny `get_status()` returns nyní vrací config options

**Frontend:**
- ✅ `SettingsPage.tsx` - nová sekce "Backup Storage" s:
  - Enable/disable toggle
  - Backup path input
  - Connection status display (connected/disconnected + stats)
  - Auto-backup new models toggle
  - Warn before delete last copy toggle
  - Save button s API call na `PUT /api/store/backup/config`
- ✅ `InventoryStats.tsx` - tlačítko "Configure in Settings →" nyní naviguje na `/settings#backup-config`
- ✅ `types.ts` - přidán `BackupConfigRequest` interface

**Soubory:**
| Soubor | Změna |
|--------|-------|
| `src/store/models.py` | `BackupStatus` rozšířen |
| `src/store/backup_service.py` | Config options ve všech status returns |
| `apps/web/src/components/modules/SettingsPage.tsx` | Backup Storage Configuration sekce |
| `apps/web/src/components/modules/inventory/InventoryStats.tsx` | Navigace na Settings |
| `apps/web/src/components/modules/inventory/types.ts` | `BackupConfigRequest` |

**Verify:** Všech 448 testů prošlo.

---

*Implementováno: 2026-01-25*

---

## 15. Settings Cleanup & Notifications (2026-01-25)

### 15.1 Povinné pravidlo: Toast Notifications

**KRITICKÉ:** Všechny operace ukládání, odpovědi API a akce MUSÍ používat interní toast notification systém:
- ✅ Úspěch → `toast.success('Message')`
- ❌ Chyba → `toast.error('Error message')`

```typescript
// Příklad správné implementace
const handleSave = async () => {
  try {
    await saveOperation()
    toast.success('Settings saved successfully')
  } catch (error) {
    toast.error('Failed to save settings')
  }
}
```

### 15.2 Provedené změny

| Změna | Popis |
|-------|-------|
| ✅ Jeden Save Settings tlačítko | Odstraněn duplicitní "Save Backup Settings", vše ukládá jedno tlačítko |
| ✅ Backup config integrován | `handleSave()` nyní ukládá i backup konfiguraci |
| ✅ Doctor/Clean tlačítka odstraněny | Duplikáty - již existují v Model Inventory > Quick Actions |
| ✅ Init Store zachován | Zůstává pro první inicializaci store |
| ⚠️ Diagnostics - TODO | Sekce označena jako TODO - zvážit přesun do Profiles tab |

### 15.3 Diagnostics sekce

**Status:** ⚠️ K REVIZI

Diagnostics sekce v Settings je zastaralá:
- Pouze kontroluje ComfyUI path
- Nevaliduje všechny UI paths (forge, a1111, sdnext)
- Lépe by patřila do Profiles tab jako "UI Health Check"

**Doporučení:**
- Přesunout do Profiles tab
- Rozšířit o validaci všech UI paths
- Přidat kontrolu symlinků a oprávnění

**Verify:** Všech 448 testů prošlo.

### 15.4 Další opravy (2026-01-25)

| Změna | Popis |
|-------|-------|
| ✅ Init Store zvýraznění | Primary variant když store není inicializovaný, secondary když je |
| ✅ Init Store text | "Init Store" vs "Re-init Store" podle stavu |
| ✅ InventoryPage toast | Přidány toast.success/error do všech mutací (backup, restore, delete, bulk action, doctor) |
| ✅ Invalidace queries | Init Store nyní invaliduje i `backup-status` pro refresh stavu inicializace |

**Verify:** Všech 448 testů prošlo.

---

*Implementováno: 2026-01-25*

---

## 16. ✅ Záloha state/ adresáře

**Status:** ✅ IMPLEMENTOVÁNO 2026-01-25

### Implementované komponenty:

1. **Backend - Modely** (`src/store/models.py`):
   - `StateSyncStatus` enum (synced, local_only, backup_only, modified, conflict)
   - `StateSyncItem` model pro jednotlivé soubory
   - `StateSyncSummary` pro přehled
   - `StateSyncResult` pro výsledek operace

2. **Backend - Service** (`src/store/backup_service.py`):
   - `backup_state_path` property
   - `get_state_sync_status()` - vrací aktuální stav
   - `sync_state(direction, dry_run)` - synchronizace souborů
   - `backup_state_file(rel_path)` - záloha jednoho souboru
   - `restore_state_file(rel_path)` - obnova jednoho souboru

3. **API endpointy** (`src/store/api.py`):
   - `GET /api/store/state/sync-status` - stav synchronizace
   - `POST /api/store/state/sync` - provedení synchronizace

4. **CLI příkazy** (`src/store/cli.py`):
   - `synapse backup state-status` - zobrazí stav
   - `synapse backup state-sync [--direction] [--execute]` - synchronizace

5. **UI komponenty** (`apps/web/src/components/modules/inventory/`):
   - `StateSyncCard.tsx` - karta zobrazující stav a akce
   - Typy v `types.ts`
   - Integrace do `InventoryStats.tsx` jako 5. karta

---

### Původní návrh (pro referenci):

### 16.1 Motivace

Aktuální backup řešení zálohuje pouze `data/blobs/` (model soubory).
Adresář `state/` obsahuje:
- Pack metadata (pack.json, lock.json)
- **Previews** (stovky obrázků/videí - mohou být velké!)
- Workflows (.json)
- Profiles (profile.json)
- Config (config.json, ui_sets.json)

**Doporučený přístup:**
- `state/` by měl být verzován v **git** (je to navrženo jako git-versioned)
- Pro uživatele bez git by měla existovat možnost sync na externí disk

### 16.2 ⚠️ Rizika

**Git konflikt:**
Pokud je `state/` git repo a provedeme rsync/sync z externího disku, může to:
- Rozbít git status (uncommitted changes)
- Přepsat lokální změny
- Způsobit merge konflikty

**Doporučení:**
- Varování v UI pokud je `.git/` detekován ve `state/`
- Nabídnout pouze "export" místo "sync" pro git uživatele

### 16.3 Co by bylo potřeba implementovat

#### Backend - BackupService rozšíření

```python
# src/store/backup_service.py

class BackupService:
    # Nové properties
    @property
    def backup_state_path(self) -> Optional[Path]:
        """Get backup state directory path."""
        root = self.backup_root
        if not root:
            return None
        return root / ".synapse" / "store" / "state"

    # Nové metody
    def sync_state_to_backup(
        self,
        dry_run: bool = True,
        exclude_git: bool = True,
    ) -> StateSyncResult:
        """Sync state/ directory to backup storage."""
        pass

    def sync_state_from_backup(
        self,
        dry_run: bool = True,
        exclude_git: bool = True,
    ) -> StateSyncResult:
        """Restore state/ directory from backup storage."""
        pass

    def get_state_sync_status(self) -> StateSyncStatus:
        """Get status of state/ sync (local vs backup diff)."""
        pass
```

#### Nové modely

```python
# src/store/models.py

class StateSyncStatus(BaseModel):
    """Status of state/ directory sync."""
    local_packs: int
    backup_packs: int
    packs_local_only: List[str]
    packs_backup_only: List[str]
    packs_modified: List[str]  # Different content
    local_bytes: int
    backup_bytes: int
    has_git: bool  # Warning if .git exists
    last_sync: Optional[str]

class StateSyncResult(BaseModel):
    """Result of state/ sync operation."""
    dry_run: bool
    direction: Literal['to_backup', 'from_backup']
    packs_synced: int
    bytes_synced: int
    files_synced: int
    errors: List[str]
    warnings: List[str]  # e.g., "Skipped .git directory"
```

#### API endpointy

```python
# src/store/api.py

@router.get("/backup/state-status")
async def get_state_sync_status() -> StateSyncStatus:
    """Get state/ sync status."""
    pass

@router.post("/backup/sync-state")
async def sync_state(
    direction: Literal['to_backup', 'from_backup'],
    dry_run: bool = True,
    exclude_git: bool = True,
) -> StateSyncResult:
    """Sync state/ directory."""
    pass
```

#### CLI příkazy

```bash
# synapse backup state-status
# Zobrazí stav synchronizace state/ adresáře

synapse backup state-status
# Output:
# State Sync Status
# ─────────────────────────────────────
# Local packs:     15
# Backup packs:    12
# Local-only:      3 (pack-a, pack-b, pack-c)
# Backup-only:     0
# Modified:        2 (pack-x, pack-y)
# Local size:      2.5 GB
# Backup size:     2.1 GB
# ⚠ Git detected:  Yes (use --exclude-git)

# synapse backup push-state [--dry-run] [--exclude-git]
synapse backup push-state --dry-run
# Would sync 5 packs (450 MB) to backup

synapse backup push-state
# Syncing state/ to backup...
# ✓ Synced 5 packs (450 MB)

# synapse backup pull-state [--dry-run] [--exclude-git]
synapse backup pull-state --dry-run
# Would restore 2 packs (180 MB) from backup
# ⚠ Warning: This will overwrite local changes!
```

#### UI komponenty

```
InventoryStats.tsx
├── Nová karta "State Backup" vedle "Backup Storage"
│   ├── Počet packů local vs backup
│   ├── Velikost local vs backup
│   ├── Warning pokud .git detected
│   └── Quick actions: "Sync to Backup", "Restore from Backup"

InventoryPage.tsx
├── StateSyncWizard (nový dialog)
│   ├── Dry-run preview (co se změní)
│   ├── Exclude options (git, specific packs)
│   ├── Direction selector (push/pull)
│   └── Progress indicator

SettingsPage.tsx
├── Backup Storage sekce rozšířena
│   ├── Checkbox "Also sync pack metadata (state/)"
│   └── Warning text o git
```

#### Testy

```python
# tests/store/test_state_backup.py

class TestStateSyncStatus:
    def test_detects_local_only_packs(self)
    def test_detects_backup_only_packs(self)
    def test_detects_modified_packs(self)
    def test_detects_git_directory(self)
    def test_calculates_sizes(self)

class TestStateSyncToBackup:
    def test_dry_run_returns_preview(self)
    def test_syncs_new_packs(self)
    def test_syncs_modified_packs(self)
    def test_excludes_git_by_default(self)
    def test_preserves_backup_only_packs(self)

class TestStateSyncFromBackup:
    def test_dry_run_returns_preview(self)
    def test_restores_backup_only_packs(self)
    def test_warns_about_overwrites(self)
    def test_excludes_git_by_default(self)

class TestStateSyncCLI:
    def test_state_status_command(self)
    def test_push_state_dry_run(self)
    def test_push_state_execute(self)
    def test_pull_state_dry_run(self)
    def test_pull_state_execute(self)
```

### 16.4 Implementační priority

1. **Backend modely a service** - StateSyncStatus, StateSyncResult, metody v BackupService
2. **API endpointy** - GET /state-status, POST /sync-state
3. **CLI příkazy** - state-status, push-state, pull-state
4. **Backend testy** - Kompletní pokrytí
5. **UI - StateSyncWizard** - Dialog pro sync operace
6. **UI - InventoryStats rozšíření** - State Backup karta
7. **UI - Settings integrace** - Checkbox a warning
8. **Frontend testy** - Vitest pro nové komponenty

### 16.5 Poznámky

- Implementace by měla používat rsync-like algoritmus (copy only changed files)
- Hardlinky/symlinky by měly být správně ošetřeny
- Velké preview soubory by měly mít progress indikátor
- Zvážit delta sync pro efektivitu

---

*Návrh vytvořen: 2026-01-25*
*Status: NEIMPLEMENTOVÁNO - pouze dokumentace pro budoucí referenci*

---

*Review provedeno: 2026-01-24*
*Opravy provedeny: 2026-01-24*

---

## 17. 🔴 KRITICKÁ CHYBA: Delete from Backup NEFUNGOVALO (2026-01-25)

### 17.1 Popis chyby

**Symptom:** Uživatel klikl na "Delete from Backup" u modelu, který existoval pouze na záloze. Toast zobrazil "success", ale:
- Blob NEBYL smazán ze zálohy
- Tabulka se neaktualizovala

**Příčina:** V `inventory_service.py` funkce `delete_blob()` měla NEKOMPLETNÍ implementaci:

```python
# CHYBNÝ KÓD - target="backup" nikdy neprošel!
if target in ("local", "both"):
    # ... mazání z local storage

# CHYBĚLO:
# if target in ("backup", "both"):
#     # ... mazání z backup storage
```

Backend vracal `{"deleted": false, "reason": "Target 'backup' not supported yet"}`, ale:
1. API (`api.py`) nekontroloval `deleted` field správně - vracel 200 OK
2. Frontend (`InventoryPage.tsx`) nezobrazoval error message

### 17.2 Opravy

**Soubor: `src/store/inventory_service.py`**
```python
# Delete from backup if requested
if target in ("backup", "both"):
    try:
        if self.backup_service and self.backup_service.is_connected():
            backup_path = self.backup_service.backup_blob_path(sha256)
            if backup_path and backup_path.exists():
                result = self.backup_service.delete_from_backup(sha256, confirm=True)
                if result.success:
                    deleted_from.append("backup")
                else:
                    raise RuntimeError(f"Backup delete failed: {result.error}")
```

**Soubor: `src/store/api.py`**
```python
if not result.get("deleted"):
    if "impacts" in result:
        raise HTTPException(409, detail=result)
    else:
        reason = result.get("reason", "Unknown error")
        raise HTTPException(400, detail=reason)
```

**Soubor: `apps/web/src/components/modules/inventory/InventoryPage.tsx`**
```typescript
async deleteBlob(sha256: string, target: 'local' | 'backup' | 'both'): Promise<void> {
  const res = await fetch(`/api/store/inventory/${sha256}?target=${target}`, { method: 'DELETE' })
  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(errorText || 'Failed to delete blob')
  }
}
```

### 17.3 Nové testy

Přidány do `tests/store/test_inventory.py` v třídě `TestDeleteBlob`:

| Test | Popis |
|------|-------|
| `test_delete_from_backup_target` | Mazání z backupu když blob existuje v obou lokacích |
| `test_delete_from_both_targets` | Mazání z obou lokací (`target="both"`) |
| `test_delete_backup_only_blob_with_backup_target` | **KLÍČOVÝ TEST** - mazání blobu existujícího pouze na záloze |

### 17.4 Poučení

⚠️ **Specifikace v sekci 3.2 (řádky 640-662) byla korektní**, ale implementace ji plně neimplementovala!

Plán specifikoval:
```
target=backup → OK pokud je lokalne
```

Ale kód toto vůbec neřešil - `target="backup"` propadl bez akce.

**Pravidlo:** Při implementaci funkce s více větvemi (local/backup/both) VŽDY:
1. Implementovat VŠECHNY větve
2. Napsat test pro KAŽDOU větev
3. Explicitně testovat edge case (blob pouze na jednom místě)

### 17.5 Verifikace

```
./scripts/verify.sh --quick
✅ 461 passed, 7 skipped
```

---

*Opraveno: 2026-01-25*

---

## 18. 🔴 KRITICKÁ CHYBA: VerifyProgressDialog - černá obrazovka (2026-01-25)

### 18.1 Popis chyby

**Symptom:** Po dokončení verifikace dialog zmizel, ale zůstala černá obrazovka (backdrop) a uživatel nemohl nic dělat.

**Příčina:** Nesoulad mezi API odpovědí a očekávaným rozhraním:

| API vrací | UI očekává |
|-----------|------------|
| `verified` (číslo) | `total` |
| `valid` (string[]) | `verified` (počet) |
| `invalid` (string[]) | `failed` (počet) |
| - | `bytes_verified` |
| - | `errors` (Array<{sha256, error}>) |

Když `result.errors` bylo `undefined`, volání `result.errors.length` v VerifyProgressDialog.tsx:257 crashlo React komponentu, ale backdrop zůstal viditelný.

### 18.2 Oprava

**Soubor: `apps/web/src/components/modules/inventory/InventoryPage.tsx`**

Transformace API odpovědi na správný formát:

```typescript
async verifyIntegrity(): Promise<VerifyResult> {
  const res = await fetch('/api/store/inventory/verify', { ... })
  // Transform API response to match VerifyResult interface
  // API returns: { verified, valid: string[], invalid: string[], duration_ms }
  // UI expects: { total, verified, failed, bytes_verified, errors: Array<{sha256, error}> }
  const data = await res.json()
  return {
    total: data.verified || 0,
    verified: (data.valid || []).length,
    failed: (data.invalid || []).length,
    bytes_verified: 0,
    errors: (data.invalid || []).map((sha256: string) => ({
      sha256,
      error: 'Hash mismatch',
    })),
  }
}
```

### 18.3 Poučení

⚠️ **API kontrakty musí být vždy synchronizované s frontend interfaces!**

Pravidla:
1. Při změně API odpovědi VŽDY aktualizovat frontend typy
2. Při změně frontend typů VŽDY zkontrolovat API
3. Defensive programming: `(data.field || [])` místo přímého přístupu

### 18.4 Verifikace

```
./scripts/verify.sh --quick
✅ 461 passed, 7 skipped
```

---

*Opraveno: 2026-01-25*

---

## 19. 🔴 KRITICKÁ CHYBA: is_enabled() metoda neexistovala (2026-01-25)

### 19.1 Popis chyby

**Symptom:** V Pack Detail stránce sekce Storage ukazovala "Backup disabled" a "Enable backup in Settings", přestože backup byl povolen a připojen.

**Příčina:** API endpoint `/backup/pack-status/{pack_name}` volal neexistující metodu:

```python
# api.py:1003 - CHYBA!
"backup_enabled": store.backup_service.is_enabled(),  # AttributeError!
```

`BackupService` měla `is_connected()`, ale NE `is_enabled()`.

Výsledek:
1. API endpoint vyhodil `AttributeError`
2. Frontend query selhala
3. Frontend zobrazil fallback "Backup disabled"

### 19.2 Oprava

Přidána chybějící metoda do `src/store/backup_service.py`:

```python
def is_enabled(self) -> bool:
    """Quick check if backup is enabled in config."""
    return self.config.enabled
```

### 19.3 Druhá část opravy - Storage karta

Storage karta v PackDetailPage se vůbec nezobrazovala při selhání query.

Změněno z:
```tsx
{isLoading ? <Skeleton /> : backupStatus && <Card>...</Card>}
// ↑ Když backupStatus undefined, NEZOBRAZÍ SE NIC
```

Na:
```tsx
<Card>
  {isLoading ? <Skeleton /> : backupStatus ? <Buttons /> : <ErrorMessage />}
</Card>
// ↑ Karta vždy viditelná, zobrazí error message při selhání
```

### 19.4 Verifikace

```
./scripts/verify.sh --quick
✅ 465 passed, 7 skipped
```

---

*Opraveno: 2026-01-25*

---

## 20. 🔴 KRITICKÁ CHYBA: resolved.artifacts vs resolved.artifact (2026-01-25)

### 20.1 Popis chyby

**Symptom:** Pack Detail page stále zobrazovala "Backup disabled" i po opravě #19 a restartu serveru.

**Příčina:** API endpoint `/backup/pack-status/{pack_name}` používal neexistující atribut:

```python
# api.py:1029-1031 - CHYBA!
if not resolved or not resolved.artifacts:  # AttributeError!
    continue
for artifact in resolved.artifacts:  # PLURAL - neexistuje!
```

Model `ResolvedDependency` má `artifact` (SINGULAR), ne `artifacts` (PLURAL):

```python
class ResolvedDependency(BaseModel):
    dependency_id: str
    artifact: ResolvedArtifact  # ← SINGULAR!
```

Výsledek:
1. API endpoint vyhodil `'ResolvedDependency' object has no attribute 'artifacts'`
2. HTTP 500 Internal Server Error
3. Frontend query selhala
4. Frontend zobrazil fallback "Backup disabled"

### 20.2 Oprava

Změněno v `src/store/api.py`:

```python
# PŘED (ŠPATNĚ):
if not resolved or not resolved.artifacts:
    continue
for artifact in resolved.artifacts:

# PO (SPRÁVNĚ):
if not resolved or not resolved.artifact:
    continue
artifact = resolved.artifact
```

### 20.3 Regresní test

Přidán test do `tests/store/test_api_critical.py`:

```python
def test_resolved_dependency_has_artifact_not_artifacts(self, tmp_path):
    """Regression test for bug #20."""
    from src.store.models import ResolvedDependency, ResolvedArtifact

    resolved = ResolvedDependency(...)

    assert hasattr(resolved, 'artifact')       # MUST exist
    assert not hasattr(resolved, 'artifacts')  # MUST NOT exist
```

### 20.4 Verifikace

```bash
# Po restartu serveru:
curl -s "http://localhost:8000/api/store/backup/pack-status/Pack_Name" | python3 -m json.tool
# Vrátí: { "pack": "...", "backup_enabled": true, "backup_connected": true, ... }
```

---

*Opraveno: 2026-01-25*
