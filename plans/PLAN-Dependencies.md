# PLAN: Dependencies - Complete Rework

**Version:** v0.1.0 (Draft)
**Status:** PLANNING
**Created:** 2026-02-03
**Author:** raven2cz + Claude Opus 4.5
**Branch:** TBD

---

## Executive Summary

Dependencies v Synapse potřebují kompletní přepracování. Aktuálně existují dva typy závislostí:

1. **Asset Dependencies** - Závislosti na modelech/souborech (existující `PackDependency`)
2. **Pack Dependencies** - Závislosti mezi packy (existující `PackDependencyRef`, UI CHYBÍ)

Tento plán pokrývá:
- Vylepšení UI pro asset dependencies
- Implementaci UI pro pack-to-pack dependencies
- Tree view pro vizualizaci závislostí
- Automatická detekce a doporučování závislostí

---

## Current State

### Asset Dependencies (PackDependency) ✅ EXISTUJE

```python
class PackDependency(BaseModel):
    type: AssetKind           # lora, checkpoint, vae, etc.
    name: str                 # Dependency name
    version: Optional[str]    # Version constraint
    required: bool = True     # Is required?
    selector: Optional[DependencySelector]  # How to resolve
    local_path: Optional[str] # Local file path
    status: DependencyStatus  # installed, missing, etc.
    # ... další pole
```

**UI:** `PackDependenciesSection.tsx` - tabulka závislostí s download/restore akcemi

### Pack Dependencies (PackDependencyRef) ⚠️ UI CHYBÍ

```python
class PackDependencyRef(BaseModel):
    pack_name: str                   # Jméno závislého packu
    required: bool = True            # Povinná závislost?
    version_constraint: Optional[str] # e.g., ">=1.0.0", "latest"
```

**UI:** CHYBÍ - pouze backend model existuje

---

## Architecture

### Dva typy závislostí

```
Pack
├── dependencies: List[PackDependency]      # Asset dependencies (modely)
│   ├── LORA_1.safetensors
│   ├── VAE_1.safetensors
│   └── ControlNet_1.safetensors
│
└── pack_dependencies: List[PackDependencyRef]  # Pack dependencies
    ├── Base_Checkpoint_Pack (required)
    └── Style_LoRA_Pack (optional)
```

### Backend API Extensions

```python
# Nové API endpointy

GET /api/packs/{name}/pack-dependencies/status
# Resolve status všech pack dependencies
# Returns: List[PackDependencyStatus]

POST /api/packs/{name}/pack-dependencies
# Přidat pack dependency
# Body: { pack_name: str, required: bool, version_constraint?: str }

DELETE /api/packs/{name}/pack-dependencies/{dep_pack_name}
# Odebrat pack dependency

GET /api/packs/{name}/dependency-tree
# Kompletní strom všech závislostí (asset + pack)
# Returns: DependencyTree

POST /api/packs/{name}/dependencies/auto-detect
# Automatická detekce závislostí z description/metadata
# Returns: List[SuggestedDependency]
```

### New Models

```python
class PackDependencyStatus(BaseModel):
    """Resolved status of a pack dependency."""
    pack_name: str
    required: bool
    version_constraint: Optional[str]
    # Resolved status
    installed: bool
    current_version: Optional[str]
    version_match: bool
    error: Optional[str]

class DependencyTreeNode(BaseModel):
    """Node in dependency tree."""
    type: Literal["asset", "pack"]
    name: str
    status: str  # installed, missing, version_mismatch
    children: List["DependencyTreeNode"] = []

class SuggestedDependency(BaseModel):
    """AI-detected dependency suggestion."""
    type: Literal["asset", "pack"]
    name: str
    reason: str  # Why it was suggested
    confidence: float  # 0.0 - 1.0
    source: str  # "description", "trigger_words", "base_model"
```

---

## Frontend Components

### Directory Structure

```
apps/web/src/components/modules/pack-detail/
├── sections/
│   ├── PackDependenciesSection.tsx     # EXISTING - asset deps
│   └── PackDependenciesTreeSection.tsx # NEW - tree view
│
└── modals/
    ├── EditDependenciesModal.tsx       # EXISTING - basic
    ├── AddPackDependencyModal.tsx      # NEW - add pack dep
    └── DependencyTreeModal.tsx         # NEW - full tree view
```

### PackDependenciesTreeSection

```
┌─────────────────────────────────────────────────────────────────┐
│ 🌳 Dependency Tree                              [Expand All] [≡] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MyLoRA Pack                                                    │
│  ├── 📦 Pack Dependencies                                       │
│  │   ├── [✅] Base_Checkpoint_Pack (required)                   │
│  │   │   └── [✅] Official_VAE_Pack (optional)                  │
│  │   ├── [❌] ControlNet_Pack (required) - MISSING              │
│  │   └── [⚠️] Style_LoRA_Pack (optional) - version mismatch    │
│  │                                                              │
│  └── 📁 Asset Dependencies                                      │
│      ├── [✅] LORA_1.safetensors (installed)                   │
│      ├── [✅] VAE_1.safetensors (installed)                    │
│      └── [⏳] ControlNet_1.safetensors (downloading 45%)       │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  Summary: 5/7 installed • 1 missing • 1 version mismatch        │
│                                                                 │
│           [Install Missing]  [Update Mismatched]  [Add Pack →] │
└─────────────────────────────────────────────────────────────────┘
```

### AddPackDependencyModal

```
┌─────────────────────────────────────────────────────────────────┐
│ Add Pack Dependency                                         [×] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Search Pack:  [________________________] 🔍                   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 📦 SD15_Base_Checkpoint                                   │  │
│  │    Checkpoint • v1.2.0 • Installed                        │  │
│  │    Base model for SD 1.5 LoRAs                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 📦 SDXL_Base_Checkpoint                                   │  │
│  │    Checkpoint • v2.0.0 • Installed                        │  │
│  │    Base model for SDXL LoRAs                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Options:                                                       │
│  [✓] Required dependency                                        │
│  [ ] Version constraint: [_____________]                        │
│                                                                 │
│                                          [Cancel]  [Add Pack]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Use Cases

### 1. LoRA závisí na Checkpoint

```
My_Anime_LoRA (pack)
└── pack_dependencies:
    └── Anime_Checkpoint_Pack (required)
        └── Obsahuje: anime_base.safetensors
```

**Benefit:** Když uživatel importuje LoRA, Synapse upozorní, že potřebuje Anime_Checkpoint_Pack.

### 2. Workflow Pack závisí na více packách

```
My_Workflow_Pack (pack)
└── pack_dependencies:
    ├── Base_Checkpoint_Pack (required)
    ├── Detail_LoRA_Pack (required)
    ├── Style_LoRA_Pack (optional)
    └── Upscaler_Pack (optional)
```

**Benefit:** Při otevření workflow se zkontrolují všechny závislosti.

### 3. Automatická detekce závislostí

Synapse analyzuje:
- Description ("works best with Dreamshaper")
- Base model hint ("SD 1.5")
- Trigger words (pokud odpovídají jinému packu)

A navrhne pack dependencies.

---

## Implementation Phases

### Phase 1: Backend - Pack Dependencies API
- [ ] `GET /api/packs/{name}/pack-dependencies/status` endpoint
- [ ] `POST /api/packs/{name}/pack-dependencies` endpoint
- [ ] `DELETE /api/packs/{name}/pack-dependencies/{name}` endpoint
- [ ] `PackDependencyStatus` model
- [ ] Tests

### Phase 2: Frontend - Pack Dependencies Section
- [ ] `PackDependenciesTreeSection.tsx` - tree view komponenta
- [ ] Integrace do PackDetailPage
- [ ] Status badges (installed, missing, mismatch)
- [ ] Quick actions (Install Missing, Update)

### Phase 3: Frontend - Add Pack Dependency Modal
- [ ] `AddPackDependencyModal.tsx`
- [ ] Pack search/filter
- [ ] Version constraint input
- [ ] Validation (circular dependencies)

### Phase 4: Dependency Tree API
- [ ] `GET /api/packs/{name}/dependency-tree` endpoint
- [ ] Recursive resolution
- [ ] Circular dependency detection
- [ ] `DependencyTreeModal.tsx` - fullscreen tree view

### Phase 5: Auto-Detection (AI)
- [ ] `POST /api/packs/{name}/dependencies/auto-detect` endpoint
- [ ] Description parsing
- [ ] Base model matching
- [ ] Trigger word correlation
- [ ] Confidence scoring

---

## UI Integration

### Kde zobrazit

1. **PackDetailPage** - PackDependenciesTreeSection pod existující PackDependenciesSection
2. **CustomPlugin** - extra sekce pro pack dependencies management
3. **Import Wizard** - upozornění na chybějící pack dependencies

### Navigation

```
Pack Detail
├── Gallery
├── Info
├── Dependencies (existující asset deps)
├── 🆕 Pack Dependencies (nová sekce)
│   └── Tree view s pack-to-pack závislostmi
├── Workflows
├── Parameters
└── Storage
```

---

## Related Plans

- **PLAN-Pack-Edit.md** - Původní CustomPlugin s pack dependencies stub
- **PLAN-Workflow-Wizard.md** - Workflows mohou záviset na packách
- **🔗 PLAN-Updates.md** - **Úzce provázáno!** Update packu může ovlivnit pack dependencies ostatních packů. Při updatu verze modelu je potřeba:
  - Zkontrolovat, zda jiné packy nemají `version_constraint` na starší verzi
  - Upozornit uživatele, pokud update rozbije závislost jiného packu
  - Nabídnout kaskádový update (updatovat i závislé packy)
  - Řešit společně s PLAN-Updates Phase 1-3

---

## Open Questions

| Question | Status |
|----------|--------|
| Jak řešit circular dependencies? | Open - detect and warn |
| Verze constraint syntax (semver vs custom)? | Open |
| Automatické instalace závislostí? | Open |
| Dependency locking (lock file)? | Open |
| Co když update packu rozbije dependency jiného packu? | Open - řešit s PLAN-Updates |
| Kaskádový update závislých packů? | Open - řešit s PLAN-Updates |

---

*Created: 2026-02-03*
*Last Updated: 2026-02-17 - Přidáno prolinkování s PLAN-Updates (společné řešení update + dependency impact)*
