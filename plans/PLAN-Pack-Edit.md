# PLAN: Pack Edit & Modularization

**Version:** v2.3.0
**Status:** ✅ PHASE 6 COMPLETE (2026-02-01)
**Created:** 2026-01-30
**Updated:** 2026-02-01
**Branch:** `pack-edit`

---

## Executive Summary

Toto je **MEGA komponenta** celé aplikace Synapse. PackDetailPage je srdcem správy AI modelů a musí být:
- **Krásná** - pro náročné designéry, s animacemi a premium UX
- **Modulární** - snadno rozšiřitelná o nové komponenty
- **Editovatelná** - plná správa všech částí packu
- **Připravená na budoucnost** - i18n, nové typy packů, pluginy

---

## 🏗️ PRINCIP: FUNKČNĚ ZACHOVAT, VIZUÁLNĚ VYLEPŠIT

### Základní filosofie

Toto je **kreativní projekt** pro premium UI. Nejsme omezeni na "pixel-perfect kopii".

**DVĚ ROVINY:**

1. **FUNKČNÍ ROVINA** 🔒 (zachovat)
   - Algoritmy pro video přehrávání, paralelizaci, polling
   - Download progress tracking, ETA výpočty, speed metriky
   - Civitai import flow, URL transformace
   - Všechny zobrazované informace (nepřijít o žádná data)
   - Business logika, state management, mutations

2. **VIZUÁLNÍ ROVINA** 🎨 (vylepšovat!)
   - UI může být krásnější, modernější
   - Animace mohou být bohatší, premium feel
   - Layout může být lepší, přehlednější
   - UX může být intuitivnější
   - Připravit strukturu pro edit mode

### 🎯 Cíl: Premium UI + Zero Regrese

```
FUNKČNĚ: Žádná feature nesmí zmizet nebo přestat fungovat
VIZUÁLNĚ: Můžeme udělat UI geniální, animační a vizuální skvost
```

### 🔑 Co MUSÍME zachovat (funkčně):

#### 1. Civitai Import Flow
- Domain entity a datové struktury - **neměnit typy**
- Transformace dat - zachovat logiku
- Import wizard - zachovat flow

#### 2. Dependencies - VŠECHNY informace
Zobrazujeme mnoho dat - **žádné nesmí zmizet**:
- type, name, version, size, status, provider
- Download progress + speed + ETA
- Source info (model_id, creator, repo_id)
- SHA256, local_path, URL
- Restore from backup functionality

#### 3. Preview/Video algoritmy
MediaPreview má komplexní logiku:
- Video autoplay, hover prioritization
- Thumbnail/video URL transformace pro Civitai
- NSFW blur, aspect ratio handling
- **Tyto algoritmy zachovat** - volat se správnými props

#### 4. Backup/Restore
- PackStorageStatus, Pull/Push dialogy
- Blob-level restore functionality

### ✅ CO MŮŽEME DĚLAT:

1. **Vylepšit design** - krásnější karty, lepší spacing, modernější vzhled
2. **Přidat animace** - enter/exit transitions, hover effects, micro-interactions
3. **Reorganizovat layout** - lepší uspořádání, collapsible sekce
4. **Přidat edit overlay** - v edit módu přidat akce nad existující zobrazení
5. **Zlepšit UX** - lepší empty states, loading states, error handling
6. **Připravit pro i18n** - t() wrapper pro budoucí překlady

### ❌ CO NESMÍME:

1. **Ztratit informace** - každý údaj co se zobrazuje teď musí jít zobrazit i potom
2. **Rozbít algoritmy** - download tracking, video playback, polling
3. **Změnit API kontrakty** - typy musí zůstat kompatibilní
4. **Odstranit features** - restore from backup, re-download, symlink management

### 🔧 POSTUP PŘI PRÁCI:

1. **Pochopit** - přečíst existující kód, pochopit PROČ a CO dělá
2. **Extrahovat** - přesunout do modulární komponenty
3. **Vylepšit** - udělat UI krásnější, přidat animace
4. **Ověřit** - všechny features fungují, všechna data viditelná

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Pack Types](#pack-types)
3. [Architecture Overview](#architecture-overview)
4. [Directory Structure](#directory-structure)
5. [Component Specifications](#component-specifications)
6. [Hooks Architecture](#hooks-architecture)
7. [Plugin System](#plugin-system)
8. [Internationalization (i18n)](#internationalization-i18n)
9. [Design System](#design-system)
10. [Implementation Phases](#implementation-phases)
11. [Testing Strategy](#testing-strategy)
12. [Risk Mitigation](#risk-mitigation)
13. [Entity Analysis](#entity-analysis) ✅ NEW

---

## Entity Analysis ✅ VERIFIED (2026-01-31)

### Backend Pack Model (src/store/models.py)

```python
class PackCategory(str, Enum):
    """Category determines pack's origin and editability"""
    EXTERNAL = "external"   # Imported from Civitai, HuggingFace, etc.
    CUSTOM = "custom"       # Created locally from scratch
    INSTALL = "install"     # Installation pack (ComfyUI, Forge, etc.)

class Pack(BaseModel):
    schema_: str = "synapse.pack.v2"
    name: str
    pack_type: AssetKind           # checkpoint, lora, vae, etc.
    pack_category: PackCategory    # 🆕 EXTERNAL, CUSTOM, INSTALL
    source: PackSource             # REQUIRED - provider, model_id, version_id, url
    dependencies: List[PackDependency]
    pack_dependencies: List[PackDependencyRef]  # 🆕 Dependencies on OTHER PACKS
    resources: PackResources
    previews: List[PreviewInfo]
    cover_url: Optional[str]
    version: Optional[str]
    description: Optional[str]
    base_model: Optional[str]
    author: Optional[str]
    tags: List[str]
    user_tags: List[str]
    trigger_words: List[str]
    created_at: Optional[datetime]
    parameters: Optional[GenerationParameters]
    model_info: Optional[ModelInfo]
    workflows: List[WorkflowInfo]

class PackDependencyRef(BaseModel):
    """Reference to another pack this pack depends on"""
    pack_name: str                   # Name of the dependent pack
    required: bool = True            # Is this dependency required?
    version_constraint: Optional[str] # e.g., ">=1.0.0", "latest"
```

### PackSource Structure

```python
class PackSource(BaseModel):
    provider: ProviderName  # civitai, huggingface, local, url
    model_id: Optional[int]
    version_id: Optional[int]
    url: Optional[str]
```

### API Response (GET /api/v2/packs/{name})

```json
{
  "name": "...",
  "version": "...",
  "description": "...",
  "author": "...",
  "tags": [],
  "user_tags": [],
  "source_url": "https://...",   // Just URL string, not full source!
  "created_at": "...",
  "installed": true,
  "has_unresolved": false,
  "all_installed": true,
  "can_generate": true,
  "assets": [...],
  "previews": [...],
  "workflows": [...],
  "parameters": {...},
  "model_info": {...},
  "pack": {...},                  // FULL Pack.model_dump() here!
  "lock": {...}
}
```

### Frontend types.ts Alignment ✅ FIXED

- ❌ ~~`pack_subtype`~~ - REMOVED (never existed in backend)
- ✅ `pack.source: PackSourceInfo` - available via `pack` field
- ✅ `pack.pack_type: PackType` - available via `pack` field

### Civitai Import Flow ✅ VERIFIED

Import správně ukládá:
- `pack.source.provider = "civitai"`
- `pack.source.model_id` - Civitai model ID
- `pack.source.version_id` - Civitai version ID
- `pack.source.url` - Original Civitai URL
- `dependencies[].selector.civitai` - Per-dependency Civitai selectors

### PackCategory - Pack Classification 🆕

**Proč pack_category?**
- `pack_type` = typ assetu (checkpoint, lora, vae...)
- `pack_category` = ODKUD pack pochází a JAK byl vytvořen

**Hodnoty:**
| Category | Description | Editability |
|----------|-------------|-------------|
| `EXTERNAL` | Importováno z Civitai, HuggingFace, URL | Omezená (metadata read-only) |
| `CUSTOM` | Vytvořeno lokálně od nuly | Plná editovatelnost |
| `INSTALL` | Instalační pack (ComfyUI, Forge) | Script-based management |

**Migrace:**
- Existující Civitai packs → `pack_category = EXTERNAL`
- Nové packy → podle způsobu vytvoření

### Pack Dependencies (Dependency Tree) 🆕

Packs mohou záviset nejen na modelech (dependencies), ale i na JINÝCH PACKECH.

**Use cases:**
- LoRA pack závisí na Checkpoint packu (base model)
- Workflow pack závisí na všech potřebných LoRA/VAE packech
- Install pack může záviset na jiném install packu

**Struktura:**
```python
class PackDependencyRef(BaseModel):
    pack_name: str                   # Jméno závislého packu
    required: bool = True            # Povinná závislost?
    version_constraint: Optional[str] # Verze constraint
```

**UI zobrazení:**
- Sekce "Pack Dependencies" (vedle existující "Dependencies")
- Tree view - zobrazí celý strom závislostí
- Status: installed / missing / version mismatch
- Quick actions: Install missing, Navigate to pack

### Existing Packs - MIGRATION NEEDED

Všech 10 existujících packů:
- ✅ Mají `source` field s provider/model_id/version_id/url
- ✅ Mají `pack_type` (ne pack_subtype)
- ⚠️ CHYBÍ `pack_category` → nastavit na `EXTERNAL` (všechny jsou z Civitai)
- ⚠️ CHYBÍ `pack_dependencies` → nastavit na `[]` (prázdný list)

---

## Problem Statement

### Current State
- `PackDetailPage.tsx` má **3267 řádků** - neudržitelné
- Všechna logika inline (queries, mutations, state, render)
- Packs lze vytvářet pouze importem z Civitai
- Omezené editační možnosti
- Žádná podpora pro různé typy packů

### Target State
- Modulární architektura s komponenty < 300 řádků
- Plná editovatelnost všech částí packu
- 3+ typy packů (Custom, Civitai, Install)
- Plugin systém pro type-specific chování
- Připravenost na i18n
- Premium UX s animacemi

---

## Pack Types

### 1. Custom Pack 🎨
**Source:** `provider = LOCAL`

Plně uživatelsky tvořený pack - od prázdného nebo ze šablony.

**Charakteristiky:**
- Všechna pole editovatelná
- Žádné external source tracking
- Uživatel přidává dependencies ručně
- Markdown description

**Use cases:**
- Osobní kolekce modelů
- Experimentální sestavy
- Kombinace z různých zdrojů

### 2. Civitai Pack 🌐
**Source:** `provider = CIVITAI`, `model_id`, `version_id`

Importovaný z Civitai s tracking původu.

**Charakteristiky:**
- Base model resolver (existující)
- Update checking via UpdateService
- HTML description (read-only nebo raw edit)
- Civitai metadata synchronizace

**Use cases:**
- Import LoRA/Checkpoint z Civitai
- Sledování nových verzí
- Automatické updates

### 3. Install Pack 🔧 (FUTURE)
**Source:** `provider = LOCAL`, `user_tags = ["install-pack"]`

> ⚠️ NOTE: Install packs are a FUTURE feature. Currently not implemented.
> Will use `user_tags` for identification since `pack_subtype` doesn't exist.

Instalační pack pro UI prostředí.

**Charakteristiky:**
- Script-based (bash/python)
- Commands: install, start, stop, verify, update
- Console output viewer
- Environment status monitoring
- Méně focus na previews

**Use cases:**
- ComfyUI instalace a správa
- Forge Neo setup
- Custom UI environments

---

## Architecture Overview

### Guiding Principles

1. **Single Responsibility** - každá komponenta má jeden účel
2. **Composition over Inheritance** - skládání komponent
3. **Colocation** - související kód pohromadě
4. **Explicit over Implicit** - jasné rozhraní komponent
5. **Prepare for Change** - snadné přidávání nových features

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PackDetailPage                              │
│  (Orchestrator - ~300 lines, routing, layout, plugin loading)   │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   usePackData   │  │  usePackEdit    │  │ usePackPlugin   │
│   (data layer)  │  │  (edit state)   │  │ (type-specific) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Section Components                          │
│  PackHeader │ PackGallery │ PackDependencies │ PackWorkflows    │
│  PackInfo   │ PackParams  │ PackStorage      │ PackScripts      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Modal System                             │
│  EditInfoModal │ EditPreviewsModal │ EditDependenciesModal      │
│  CreatePackModal │ MarkdownEditorModal │ ScriptConsoleModal     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
apps/web/src/components/modules/
├── PackDetailPage.tsx              # Orchestrator (~300 lines)
├── PacksPage.tsx                   # List + Create button
│
└── pack-detail/
    ├── index.ts                    # Public exports
    ├── types.ts                    # Shared TypeScript types
    ├── constants.ts                # Animation configs, defaults
    │
    ├── sections/                   # Main content sections
    │   ├── index.ts
    │   ├── PackHeader.tsx          # Title, badges, main actions
    │   ├── PackGallery.tsx         # Preview grid + fullscreen
    │   ├── PackInfoSection.tsx     # Description, metadata
    │   ├── PackDependenciesSection.tsx  # Dependencies list
    │   ├── PackWorkflowsSection.tsx     # Workflows management
    │   ├── PackParametersSection.tsx    # Generation parameters
    │   ├── PackStorageSection.tsx       # Backup/restore (existing)
    │   └── PackScriptsSection.tsx       # Install pack scripts
    │
    ├── modals/                     # All modal dialogs
    │   ├── index.ts
    │   ├── CreatePackModal.tsx     # Pack creation wizard
    │   ├── EditInfoModal.tsx       # Title, description, metadata
    │   ├── EditPreviewsModal.tsx   # Add/remove/reorder previews
    │   ├── EditDependenciesModal.tsx    # Dependency management
    │   ├── EditParametersModal.tsx      # Generation parameters
    │   ├── EditWorkflowsModal.tsx       # Workflow management
    │   ├── BaseModelResolverModal.tsx   # Civitai base model (existing)
    │   ├── MarkdownEditorModal.tsx      # Full markdown editor
    │   ├── ScriptConsoleModal.tsx       # Install pack console
    │   └── ConfirmDeleteModal.tsx       # Confirmation dialogs
    │
    ├── hooks/                      # Custom React hooks
    │   ├── index.ts
    │   ├── usePackData.ts          # Pack query + mutations
    │   ├── usePackEdit.ts          # Edit mode state management
    │   ├── usePackDownloads.ts     # Download progress tracking
    │   ├── usePackPlugin.ts        # Plugin system hook
    │   └── useMarkdownEditor.ts    # Markdown edit/preview state
    │
    ├── plugins/                    # Pack type plugins
    │   ├── index.ts
    │   ├── types.ts                # Plugin interface definitions
    │   ├── CivitaiPlugin.tsx       # Civitai-specific features
    │   ├── InstallPlugin.tsx       # Install pack features
    │   └── CustomPlugin.tsx        # Custom pack features
    │
    ├── shared/                     # Shared UI components
    │   ├── index.ts
    │   ├── SectionHeader.tsx       # Reusable section header with edit button
    │   ├── EditableText.tsx        # Click-to-edit text component
    │   ├── AnimatedSection.tsx     # Section with enter/exit animations
    │   ├── EmptyState.tsx          # Empty state placeholders
    │   └── LoadingSection.tsx      # Section loading skeleton
    │
    └── utils/                      # Helper functions
        ├── index.ts
        ├── packValidation.ts       # Validation helpers
        ├── packTransforms.ts       # Data transformations
        └── animations.ts           # Animation configurations
```

---

## Component Specifications

### PackDetailPage (Orchestrator)

**Responsibility:** Layout, routing, plugin loading, composition

```tsx
// Pseudo-code structure
function PackDetailPage() {
  const { packName } = useParams()
  const { pack, isLoading, mutations } = usePackData(packName)
  const { isEditing, editState } = usePackEdit()
  const plugin = usePackPlugin(pack?.source.provider)

  if (isLoading) return <PackSkeleton />
  if (!pack) return <PackNotFound />

  return (
    <div className="space-y-6">
      <PackHeader pack={pack} plugin={plugin} />
      <PackGallery pack={pack} editable={isEditing} />
      <PackInfoSection pack={pack} editable={isEditing} />
      <PackDependenciesSection pack={pack} editable={isEditing} />
      {plugin.renderExtraSections()}
      <PackWorkflowsSection pack={pack} editable={isEditing} />
      <PackParametersSection pack={pack} editable={isEditing} />
      <PackStorageSection pack={pack} />

      {/* Modals rendered via portal */}
      <ModalProvider />
    </div>
  )
}
```

### PackHeader

**Responsibility:** Pack identity, primary actions

**Features:**
- Pack name (editable inline)
- Version badge
- Type badge (LoRA, Checkpoint, Install...)
- Source badge (Civitai, Local, HuggingFace)
- NSFW indicator
- Primary actions: Use Pack, Edit, Delete
- Plugin actions (e.g., "Check Updates" for Civitai)

**Animations:**
- Hover effects on badges
- Button press feedback
- Action success/error feedback

### PackGallery

**Responsibility:** Preview media display and management

**Features:**
- Responsive grid with zoom controls
- Video autoplay on hover
- Click to fullscreen (existing FullscreenMediaViewer)
- Edit mode:
  - Add preview (upload, URL, drag & drop)
  - Remove preview (with confirmation)
  - Reorder (drag & drop or arrow buttons)
  - Set as cover image
- Empty state with upload prompt

**Animations:**
- Grid item enter/exit
- Hover scale effect
- Drag preview ghost
- Upload progress indicator

### PackInfoSection

**Responsibility:** Pack metadata display and editing

**Features:**
- Description display (HTML or Markdown rendered)
- Edit mode:
  - If HTML source: raw HTML editor or read-only
  - If Markdown/new: full Markdown editor with live preview
- Model info (base model, author, downloads, rating)
- Tags display and editing
- Trigger words (copyable chips)

**Markdown Editor:**
- Toolbar: bold, italic, headers, lists, links, code
- Split view: edit | preview
- Full-screen editing option
- Syntax highlighting

### PackDependenciesSection

**Responsibility:** Dependency management

**Features:**
- List of all dependencies with:
  - Type icon (LoRA, VAE, Checkpoint, ControlNet...)
  - Name and version
  - Size
  - Status (installed, pending, error)
  - Download progress
- Edit mode:
  - Add dependency (search Civitai/HuggingFace/Local)
  - Remove dependency
  - Edit dependency (change version, constraints)
  - Reorder dependencies
- Bulk actions: Download All, Update All

**Complexity Note:**
Pack může mít 8+ dependencies! UI musí zvládat:
- Přehledné zobrazení mnoha položek
- Grouping by type
- Collapse/expand
- Search/filter within dependencies

### PackWorkflowsSection

**Responsibility:** ComfyUI workflow management

**Features:**
- List of workflows with:
  - Name and description
  - Default workflow indicator
  - Symlink status
- Edit mode:
  - Upload workflow (.json)
  - Remove workflow
  - Set as default
  - Edit name/description
- Open in ComfyUI button

### PackParametersSection

**Responsibility:** Generation parameters

**Features:**
- Grid display of parameters (sampler, steps, CFG, etc.)
- Recommended strength for LoRAs
- Edit mode:
  - Quick-add common parameters
  - Custom parameter key-value pairs
  - Remove parameters

### PackScriptsSection (Install Pack Only)

**Responsibility:** Script management for Install packs

**Features:**
- Script list (install.sh, start.sh, stop.sh, etc.)
- Run buttons with status
- Console output viewer (modal)
- Environment status indicators
- Edit mode:
  - Add/edit scripts
  - Script editor with syntax highlighting

---

## Hooks Architecture

### usePackData

**Purpose:** Centralizovaná správa dat a mutací

```tsx
interface UsePackDataReturn {
  // Queries
  pack: Pack | undefined
  packLock: PackLock | undefined
  backupStatus: BackupStatus | undefined
  isLoading: boolean
  error: Error | null

  // Mutations
  updatePack: (data: Partial<Pack>) => Promise<void>
  deletePack: () => Promise<void>
  downloadAsset: (asset: Asset) => Promise<void>
  downloadAll: () => Promise<void>
  addPreview: (file: File | string) => Promise<void>
  removePreview: (index: number) => Promise<void>
  reorderPreviews: (from: number, to: number) => Promise<void>
  addDependency: (dep: Dependency) => Promise<void>
  removeDependency: (id: string) => Promise<void>
  updateDependency: (id: string, data: Partial<Dependency>) => Promise<void>

  // Refetch
  refetch: () => void
}

function usePackData(packName: string): UsePackDataReturn {
  // All useQuery and useMutation calls here
  // Returns clean interface for components
}
```

### usePackEdit

**Purpose:** Edit mode state management

```tsx
interface UsePackEditReturn {
  // State
  isEditing: boolean
  hasUnsavedChanges: boolean
  editingSection: string | null

  // Actions
  startEditing: (section?: string) => void
  stopEditing: () => void
  saveChanges: () => Promise<void>
  discardChanges: () => void

  // Field-level
  setFieldValue: (path: string, value: any) => void
  getFieldValue: (path: string) => any
  getFieldError: (path: string) => string | null
}
```

### usePackDownloads

**Purpose:** Download progress tracking

```tsx
interface UsePackDownloadsReturn {
  activeDownloads: DownloadProgress[]
  getDownloadProgress: (assetName: string) => DownloadProgress | undefined
  isDownloading: (assetName: string) => boolean
  totalProgress: number // 0-100
}
```

### usePackPlugin

**Purpose:** Load type-specific plugin

```tsx
interface UsePackPluginReturn {
  plugin: PackPlugin
  extraActions: Action[]
  extraSections: React.ReactNode[]
  validateEdit: (changes: Partial<Pack>) => ValidationResult
}
```

---

## Plugin System ✅ IMPLEMENTOVÁNO

Plugin systém umožňuje type-specific chování pro různé typy packů. Každý plugin může přidávat vlastní UI sekce, akce v headeru a validaci změn.

### Architektura

```
┌─────────────────────────────────────────────────────────────────┐
│                      usePackPlugin Hook                          │
│   (Loads correct plugin based on pack type & priority)           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ InstallPlugin│  │CivitaiPlugin │  │ CustomPlugin │
    │ Priority:100 │  │ Priority:50  │  │ Priority:0   │
    │ (user_tags)  │  │ (source)     │  │ (fallback)   │
    └──────────────┘  └──────────────┘  └──────────────┘
```

### Priority Matching

Plugin matching používá **priority-based system**:

1. **InstallPlugin (100)** - nejvyšší priorita, matchuje `user_tags.includes('install-pack')`
2. **CivitaiPlugin (50)** - matchuje `pack.source.provider === 'civitai'`
3. **CustomPlugin (0)** - fallback pro všechny ostatní packy

```typescript
const PLUGIN_REGISTRY: PackPlugin[] = [
  InstallPlugin,  // Priority: 100
  CivitaiPlugin,  // Priority: 50
  CustomPlugin,   // Priority: 0 - Fallback
].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))
```

### Plugin Interface (Kompletní)

```typescript
interface PackPlugin {
  // ==== Identity ====
  id: string                              // Unique plugin ID
  name: string                            // Human-readable name
  priority?: number                       // Higher = checked first (default: 0)
  appliesTo: (pack: PackDetail) => boolean // Matching function

  // ==== UI Extensions ====
  renderHeaderActions?: (context: PluginContext) => ReactNode
  renderExtraSections?: (context: PluginContext) => ReactNode
  renderModals?: (context: PluginContext) => ReactNode
  getBadge?: (pack: PackDetail) => PluginBadge | null

  // ==== Behavior Hooks ====
  onPackLoad?: (pack: PackDetail) => void
  onBeforeSave?: (pack: PackDetail, changes: Partial<PackDetail>) => {
    changes: Partial<PackDetail>
    errors?: Record<string, string>
  }
  validateChanges?: (pack: PackDetail, changes: Partial<PackDetail>) => ValidationResult

  // ==== Feature Flags ====
  features?: PluginFeatures
}

interface PluginFeatures {
  canEditMetadata?: boolean        // Edit name, description, etc.
  canEditPreviews?: boolean        // Add/remove/reorder previews
  canEditDependencies?: boolean    // Manage asset dependencies
  canEditWorkflows?: boolean       // Workflow management
  canEditParameters?: boolean      // Generation parameters
  canCheckUpdates?: boolean        // Civitai update checking
  canManagePackDependencies?: boolean  // Pack-to-pack dependencies
  canRunScripts?: boolean          // Install pack scripts
  canDelete?: boolean              // Pack deletion
}
```

### PluginContext

Každý plugin dostává context s daty a akcemi:

```typescript
interface PluginContext {
  pack: PackDetail                 // Current pack data
  isEditing: boolean               // Edit mode active?
  hasUnsavedChanges: boolean       // Unsaved changes?
  modals: Record<string, boolean>  // Modal state
  openModal: (key: string) => void
  closeModal: (key: string) => void
  refetch: () => void              // Refetch pack data
  toast: {
    success: (message: string) => void
    error: (message: string) => void
    info: (message: string) => void
  }
}
```

### CivitaiPlugin (360 řádků)

Plugin pro packy importované z Civitai:

**Features:**
- ✅ Check Updates button → volá `GET /api/updates/check/{pack_name}`
- ✅ Apply Updates → volá `POST /api/updates/apply` s `{ pack: name, sync: true }`
- ✅ View on Civitai button
- ✅ CivitaiInfoSection (model_id, version_id, source URL)
- ✅ UpdateCheckSection s detaily změn

**Feature Flags:**
```typescript
features: {
  canEditMetadata: false,    // Read-only from Civitai
  canEditPreviews: false,    // Read-only from Civitai
  canEditDependencies: false,
  canEditWorkflows: true,
  canEditParameters: true,
  canCheckUpdates: true,     // ← Hlavní feature
  canDelete: true,
}
```

**API Endpoints:**
- `GET /api/updates/check/{pack_name}` → UpdateCheckResponse
- `POST /api/updates/apply` → UpdateResult (pack v body!)

### CustomPlugin (490 řádků)

Plugin pro lokálně vytvořené packy:

**Features:**
- ✅ Full editability všech polí
- ✅ Pack dependencies section (závislosti na jiných packách)
- ✅ Support pro 7+ dependencies se search/filter
- ✅ EditCapabilitiesInfo panel v edit mode
- ✅ Tree view pro pack dependencies

**Feature Flags:**
```typescript
features: {
  canEditMetadata: true,
  canEditPreviews: true,
  canEditDependencies: true,
  canEditWorkflows: true,
  canEditParameters: true,
  canCheckUpdates: false,
  canManagePackDependencies: true,  // ← Hlavní feature
  canDelete: true,
}
```

**Pack Dependencies:**
```typescript
interface PackDependencyRef {
  pack_name: string           // Dependent pack name
  required?: boolean          // Is required?
  version_constraint?: string // e.g., ">=1.0.0"
}

interface PackDependencyStatus extends PackDependencyRef {
  installed: boolean
  current_version?: string
  version_match: boolean
  error?: string
}
```

### InstallPlugin (326 řádků) - PROTOTYPE

Plugin pro instalační packy (ComfyUI, Forge):

**Features (PROTOTYPE):**
- ✅ PrototypeNotice banner
- ✅ ScriptsSection (mock scripts)
- ✅ EnvironmentStatus component
- ⏳ Script execution (future)
- ⏳ Console output (future)

**Feature Flags:**
```typescript
features: {
  canEditMetadata: true,
  canEditPreviews: false,
  canRunScripts: true,  // ← Hlavní feature (future)
  canDelete: true,
}
```

### Použití v PackDetailPage

```tsx
import { usePackPlugin } from './pack-detail'

function PackDetailPage() {
  const { pack } = usePackData(packName)

  // Load plugin based on pack type
  const { plugin, context } = usePackPlugin({
    pack,
    isEditing,
    hasUnsavedChanges,
    modals,
    openModal,
    closeModal,
    refetch,
  })

  return (
    <>
      <PackHeader
        pack={pack}
        // Plugin header actions (Check Updates, View on Civitai, etc.)
        pluginActions={context && plugin?.renderHeaderActions?.(context)}
      />

      {/* Standard sections */}
      <PackGallery />
      <PackInfoSection />
      <PackDependenciesSection />

      {/* Plugin extra sections (Update section, Pack dependencies, etc.) */}
      {context && plugin?.renderExtraSections?.(context)}

      {/* Plugin modals */}
      {context && plugin?.renderModals?.(context)}
    </>
  )
}
```

### Jak přidat nový plugin

1. **Vytvořit soubor** `plugins/MyPlugin.tsx`
2. **Implementovat PackPlugin interface:**

```typescript
import type { PackPlugin, PluginContext, PluginBadge } from './types'

export const MyPlugin: PackPlugin = {
  id: 'my-plugin',
  name: 'My Custom Plugin',
  priority: 75,  // Between Civitai (50) and Install (100)

  appliesTo: (pack) => {
    // Return true if this plugin should handle the pack
    return pack.pack?.source?.provider === 'my-source'
  },

  getBadge: (): PluginBadge => ({
    label: 'My Plugin',
    variant: 'info',
    icon: 'Star',
    tooltip: 'Custom plugin',
  }),

  features: {
    canEditMetadata: true,
    // ... other features
  },

  renderHeaderActions: (context) => (
    <Button onClick={() => context.toast.info('Hello!')}>
      My Action
    </Button>
  ),

  renderExtraSections: (context) => (
    <MyCustomSection pack={context.pack} />
  ),

  validateChanges: (pack, changes) => {
    const errors: Record<string, string> = {}
    // Validation logic
    return { valid: Object.keys(errors).length === 0, errors }
  },
}
```

3. **Registrovat v PLUGIN_REGISTRY** (`usePackPlugin.ts`):

```typescript
const PLUGIN_REGISTRY: PackPlugin[] = [
  InstallPlugin,
  MyPlugin,        // ← Add here
  CivitaiPlugin,
  CustomPlugin,
].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))
```

4. **Exportovat** z `plugins/index.ts`:

```typescript
export { MyPlugin } from './MyPlugin'
```

### Testy

Plugin systém má **79 testů** v `__tests__/pack-plugins.test.ts`:

- Plugin matching logic (15 tests)
- Priority ordering (5 tests)
- Feature flags (12 tests)
- Validation (9 tests)
- Context creation (6 tests)
- Pack dependencies (8 tests)
- Update types (6 tests)
- Badge tests (9 tests)
- API URL tests (7 tests)
- Integration tests (2 tests)

---

## Internationalization (i18n) 🆕 REAL IMPLEMENTATION

### Framework: react-i18next

**Instalace:**
```bash
cd apps/web
pnpm add react-i18next i18next
```

### Directory Structure

```
apps/web/src/
├── i18n/
│   ├── index.ts           # i18n configuration
│   ├── locales/
│   │   ├── en.json        # English translations
│   │   └── cs.json        # Czech translations
│   └── types.ts           # TypeScript types for translations
```

### Configuration (i18n/index.ts)

```tsx
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import cs from './locales/cs.json'

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    cs: { translation: cs },
  },
  lng: 'en',              // Default language
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,   // React already escapes
  },
})

export default i18n
```

### Usage in Components

```tsx
import { useTranslation } from 'react-i18next'

function PackHeader({ pack }) {
  const { t } = useTranslation()

  return (
    <h1>{t('pack.header.title', { name: pack.name })}</h1>
    <Button>{t('pack.actions.edit')}</Button>
    <span>{t('pack.dependencies.count', { count: deps.length })}</span>
  )
}
```

### Translation Files Structure

**en.json:**
```json
{
  "pack": {
    "header": {
      "title": "{{name}}",
      "version": "Version {{version}}"
    },
    "actions": {
      "edit": "Edit",
      "delete": "Delete",
      "use": "Use Pack",
      "download": "Download",
      "cancel": "Cancel",
      "save": "Save"
    },
    "gallery": {
      "title": "Gallery",
      "empty": "No previews yet",
      "addPreview": "Add Preview"
    },
    "dependencies": {
      "title": "Dependencies",
      "empty": "No dependencies",
      "count": "{{count}} dependencies",
      "packDependencies": "Pack Dependencies"
    },
    "info": {
      "title": "Information",
      "description": "Description",
      "triggerWords": "Trigger Words",
      "baseModel": "Base Model"
    },
    "parameters": {
      "title": "Parameters",
      "empty": "No parameters defined"
    },
    "workflows": {
      "title": "Workflows",
      "empty": "No workflows"
    },
    "storage": {
      "title": "Storage",
      "backup": "Backup",
      "restore": "Restore"
    }
  },
  "common": {
    "loading": "Loading...",
    "error": "An error occurred",
    "success": "Success",
    "confirm": "Confirm",
    "cancel": "Cancel"
  }
}
```

**cs.json:**
```json
{
  "pack": {
    "header": {
      "title": "{{name}}",
      "version": "Verze {{version}}"
    },
    "actions": {
      "edit": "Upravit",
      "delete": "Smazat",
      "use": "Použít Pack",
      "download": "Stáhnout",
      "cancel": "Zrušit",
      "save": "Uložit"
    },
    "gallery": {
      "title": "Galerie",
      "empty": "Zatím žádné náhledy",
      "addPreview": "Přidat náhled"
    },
    "dependencies": {
      "title": "Závislosti",
      "empty": "Žádné závislosti",
      "count": "{{count}} závislostí",
      "packDependencies": "Závislosti na packách"
    },
    "info": {
      "title": "Informace",
      "description": "Popis",
      "triggerWords": "Spouštěcí slova",
      "baseModel": "Základní model"
    },
    "parameters": {
      "title": "Parametry",
      "empty": "Žádné parametry"
    },
    "workflows": {
      "title": "Workflow",
      "empty": "Žádné workflow"
    },
    "storage": {
      "title": "Úložiště",
      "backup": "Záloha",
      "restore": "Obnovit"
    }
  },
  "common": {
    "loading": "Načítání...",
    "error": "Došlo k chybě",
    "success": "Úspěch",
    "confirm": "Potvrdit",
    "cancel": "Zrušit"
  }
}
```

### Integration Note

- **Zatím bez UI přepínače** - jazyk se nastavuje programově
- **Budoucí UI:** Language selector v Settings nebo Header
- **Persistence:** localStorage pro uložení preference

---

## Design System

### Animation Standards

```tsx
// constants.ts
export const ANIMATIONS = {
  // Durations
  fast: 150,      // Hover, press feedback
  normal: 300,    // Section transitions
  slow: 500,      // Page transitions, modals

  // Easings
  easeOut: 'cubic-bezier(0.0, 0.0, 0.2, 1)',
  easeIn: 'cubic-bezier(0.4, 0.0, 1, 1)',
  easeInOut: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',

  // Presets
  fadeIn: 'animate-in fade-in duration-300',
  slideUp: 'animate-in slide-in-from-bottom-4 duration-300',
  slideRight: 'animate-in slide-in-from-right-4 duration-300',
  scale: 'animate-in zoom-in-95 duration-200',
}
```

### Section Component Pattern

```tsx
// Každá sekce má stejnou strukturu
function PackSection({
  title,
  icon,
  editable,
  onEdit,
  children
}: SectionProps) {
  return (
    <Card className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <SectionHeader
        title={title}
        icon={icon}
        editable={editable}
        onEdit={onEdit}
      />
      <div className="p-4">
        {children}
      </div>
    </Card>
  )
}
```

### Edit Mode Visual Indicators

```tsx
// Editable state styling
const editableClasses = {
  idle: 'cursor-pointer hover:bg-white/5 transition-colors',
  hover: 'ring-1 ring-synapse/30',
  editing: 'ring-2 ring-synapse bg-synapse/5',
  error: 'ring-2 ring-red-500 bg-red-500/5',
}
```

### Premium UX Details

- **Micro-interactions:** Button press ripples, icon animations
- **Loading states:** Skeleton screens matching final layout
- **Empty states:** Helpful illustrations + clear CTAs
- **Error states:** Friendly messages + recovery actions
- **Success feedback:** Toast notifications + subtle animations
- **Hover reveals:** Edit buttons appear on section hover

---

## Implementation Phases

### Phase 1: Foundation & Core Extraction ✅ COMPLETE
**Duration:** 2-3 sessions
**Goal:** Modulární základ bez změny funkcionality

#### Iteration 1.1: Directory Setup & Types ✅ DONE
- [x] Vytvořit `pack-detail/` directory structure
- [x] Definovat TypeScript types (`types.ts`) - 300+ řádků, všechny pack types
- [x] Vytvořit constants (`constants.ts`) - animations, grid config, i18n prep
- [x] Vytvořit shared components:
  - [x] `SectionHeader.tsx` - hover-reveal edit button, collapsible
  - [x] `EmptyState.tsx` - presets pro gallery/deps/workflows/params
  - [x] `LoadingSection.tsx` - skeleton variants pro všechny sekce
  - [x] `AnimatedSection.tsx` - wrapper s animacemi
- [x] CSS animace: shimmer, slide-in, zoom-in/out (index.css)

#### Iteration 1.2: Extract Hooks ✅ DONE
- [x] `usePackData.ts` - všechny queries a mutations (~420 řádků)
  - Queries: pack, backupStatus
  - Mutations: delete, use, update, parameters, workflows, symlinks, backup
- [x] `usePackDownloads.ts` - download progress (~240 řádků)
  - Active downloads polling
  - Progress tracking
  - Completed/failed download toasts
- [ ] ~~Aktualizovat PackDetailPage pro použití hooks~~ → přesunuto do 1.3 (s extrakcí sekcí)
- [x] Hooks exportovány v `hooks/index.ts` a `pack-detail/index.ts`

#### Iteration 1.3: Extract Sections - FUNKČNĚ ZACHOVAT, VIZUÁLNĚ VYLEPŠIT 🎨

**FILOSOFIE:**
- **Funkčně:** Zachovat všechny features, algoritmy, zobrazovaná data
- **Vizuálně:** Můžeme vylepšit UI, přidat animace, udělat krásnější design
- **Struktura:** Připravit pro edit mode

**Postup pro každou sekci:**
1. Přečíst a pochopit původní kód - CO dělá a PROČ
2. Extrahovat do modulární komponenty
3. Zachovat všechny FUNKCE a ALGORITMY (download tracking, video playback, etc.)
4. Vylepšit UI kde má smysl (lepší layout, animace, premium feel)
5. Ověřit: všechny features fungují, všechna data zobrazena

**Sekce k extrakci:**

- [x] `PackHeader.tsx` ✅ DONE
  - FUNKCE: Use Pack, Source link, Delete ✓
  - VYLEPŠENO: Animace, premium badge styling, hover effects

- [x] `PackGallery.tsx` ✅ DONE
  - FUNKCE ZACHOVÁNY:
    - MediaPreview algoritmy (autoPlay, playFullOnHover, thumbnailSrc) ✓
    - FullscreenMediaViewer integrace (via onPreviewClick) ✓
    - Zoom controls ✓
  - VYLEPŠENO: Staggered animace, premium hover effects, lepší video badge

- [x] `PackInfoSection.tsx` ✅ DONE
  - FUNKCE ZACHOVÁNY:
    - HTML rendering (dangerouslySetInnerHTML) ✓
    - Copy trigger words to clipboard ✓
    - Všechny model_info badges ✓
  - VYLEPŠENO: Premium card design, animované copy feedback

- [x] `PackDependenciesSection.tsx` ✅ DONE ⚠️ KRITICKÉ - ALL DATA PRESERVED
  - FUNKCE ZACHOVÁNY (VŠECHNO!):
    - Status icons (downloading, installed, backup-only, unresolved, pending) ✓
    - Asset info: type, name, version, size, status, provider ✓
    - Source info: model_id, model_name, creator, repo_id ✓
    - Download progress + speed + ETA + bytes ✓
    - SHA256, local_path, URL zobrazení ✓
    - Restore from backup button ✓
    - Re-download, Delete buttons ✓
    - Base model resolver trigger ✓
  - VYLEPŠENO: Hover effects, transitions

- [x] `PackWorkflowsSection.tsx` ✅ DONE
  - FUNKCE ZACHOVÁNY:
    - Symlink status (In ComfyUI / Broken link) ✓
    - Link/Unlink buttons ✓
    - Download JSON, Delete workflow ✓
    - Generate Default workflow ✓
  - VYLEPŠENO: Premium card design, status badges

- [x] `PackParametersSection.tsx` ✅ DONE
  - FUNKCE ZACHOVÁNY: Všechny parameter typy, Edit button ✓
  - VYLEPŠENO: Hover effects, premium cards

- [x] `PackStorageSection.tsx` ✅ DONE - backup status & actions
  - FUNKCE ZACHOVÁNY: Pull/Push/Push&Free buttons, PackBlobsTable ✓
  - Integruje existující `PackStorageStatus`, `PackStorageActions`, `PackBlobsTable`

- [x] `PackUserTagsSection.tsx` ✅ DONE - user tags
  - FUNKCE ZACHOVÁNY: Tag display, Edit button trigger ✓
  - VYLEPŠENO: Premium tag chips, nsfw-pack special styling, hover effects

#### Iteration 1.4: Extract Modals ✅ DONE

- [x] `EditPackModal.tsx` ✅ DONE (~240 řádků)
  - User tags editor with suggested tags
  - Custom tag input with Enter key
  - Special nsfw-pack styling
  - Save/Cancel with loading state

- [x] `EditParametersModal.tsx` ✅ DONE (~280 řádků)
  - Quick-add buttons for common params
  - Editable parameter rows
  - Custom parameter input
  - Type conversion (numbers vs strings)

- [x] `UploadWorkflowModal.tsx` ✅ DONE (~180 řádků)
  - File input (.json only)
  - Auto-populate name from filename
  - Optional description
  - Upload with loading state

- [x] `BaseModelResolverModal.tsx` ✅ DONE (~730 řádků)
  - Three tabs: Local, Civitai, HuggingFace
  - Smart base model hint extraction
  - Local model filtering
  - Remote search with method info
  - HuggingFace file selection
  - Model selection and resolution

- [x] `modals/index.ts` ✅ DONE - all modals exported

#### Iteration 1.5: Entity Extensions & i18n ✅ DONE (2026-01-31)

**A) Backend - PackCategory & PackDependencies ✅**
- [x] Přidat `PackCategory` enum do `src/store/models.py`
- [x] Přidat `pack_category` field do `Pack` modelu (default: EXTERNAL)
- [x] Přidat `PackDependencyRef` model
- [x] Přidat `pack_dependencies` field do `Pack` modelu (default: [])
- [x] Aktualizovat Civitai import - nastavit `pack_category = EXTERNAL`
- [x] ~~Migrační skript~~ - Pydantic defaults handle existing packs automatically

**B) Frontend - TypeScript Types ✅**
- [x] Přidat `PackCategory` type do `types.ts`
- [x] Přidat `PackDependencyRef` interface do `types.ts`
- [x] Aktualizovat `PackDetail` interface

**C) Frontend - i18n Framework ✅**
- [x] `npm install react-i18next i18next`
- [x] Vytvořit `apps/web/src/i18n/` directory
- [x] Vytvořit `i18n/index.ts` - konfigurace s localStorage persistence
- [x] Vytvořit `i18n/locales/en.json` - English translations (~170 keys)
- [x] Vytvořit `i18n/locales/cs.json` - Czech translations (~170 keys)
- [x] Integrovat do `main.tsx`
- [x] ⚠️ ZATÍM bez UI přepínače jazyka (API: `changeLanguage('cs')`)

**D) Frontend - Pack Dependencies Section**
- [ ] `sections/PackDependenciesTreeSection.tsx` - zobrazení pack dependencies (FUTURE)
- [ ] Integrace do PackDetailPage (FUTURE)

#### Iteration 1.6: CRITICAL INTEGRATION ✅ COMPLETE (2026-01-31)

**Stav před integrací:**
- PackDetailPage.tsx měla 3,267 řádků - monolitická
- pack-detail/ obsahuje 10,000+ řádků modulárního kódu
- ~~93% kódu bylo NEINTEGROVÁNO~~ → NYNÍ INTEGROVÁNO

**Výsledek:**
- PackDetailPage.tsx nyní má ~480 řádků (orchestrátor)
- Používá všechny modulární komponenty
- 507 testů prochází
- TypeScript kompilace OK
- Frontend build OK

**ÚKOLY:**

**A) Přepis PackDetailPage.tsx** ✅
- [x] Kompletní přepis PackDetailPage na orchestrátor (~480 řádků místo 3,267)
- [x] Starý kód smazán, máme backup v git hlavy

**B) Integrovat hooks** ✅
- [x] Nahradit inline useQuery/useMutation za `usePackData`
- [x] Nahradit inline polling za `usePackDownloads`
- [x] Přidat `usePackEdit` pro edit mode

**C) Integrovat section komponenty** ✅
- [x] Import a použití `PackHeader`
- [x] Import a použití `PackGallery`
- [x] Import a použití `PackInfoSection`
- [x] Import a použití `PackDependenciesSection`
- [x] Import a použití `PackWorkflowsSection`
- [x] Import a použití `PackParametersSection`
- [x] Import a použití `PackStorageSection`
- [ ] ~~PackUserTagsSection~~ (není potřeba - user tags jsou v EditPackModal)

**D) Integrovat modals** ✅
- [x] Import a použití `EditPackModal`
- [x] Import a použití `EditParametersModal`
- [x] Import a použití `UploadWorkflowModal`
- [x] Import a použití `BaseModelResolverModal`
- [ ] ~~EditPreviewsModal~~ (Phase 4 - není vyžadován nyní)
- [ ] ~~EditDependenciesModal~~ (Phase 4 - není vyžadován nyní)
- [ ] ~~DescriptionEditorModal~~ (Phase 4 - není vyžadován nyní)

**E) Verifikace** ✅
- [x] API contract testy prochází (507 passed, 7 skipped)
- [x] Frontend testy prochází
- [x] TypeScript kompilace OK
- [x] Frontend build OK
- [ ] Manuální UI test (vyžaduje uživatele)

**F) Aktualizace testů** ✅
- [x] `tests/store/test_inventory_stabilization.py` - přidána helper funkce `get_pack_detail_module_content()` pro kontrolu modulárních souborů
- [x] `tests/store/test_api_critical.py` - aktualizován test pro modulární architekturu

### Phase 2: Edit Capabilities ✅ COMPLETE
**Duration:** 2-3 sessions
**Goal:** Plná editovatelnost

#### Iteration 2.1: Edit Mode Infrastructure ✅ DONE (2026-01-31)
- [x] `usePackEdit.ts` hook (~320 řádků)
  - Edit mode toggle (global and per-section)
  - Unsaved changes tracking
  - Field-level state management (setFieldValue, getFieldValue)
  - Change history tracking
  - Validation support
  - Auto-save option (disabled by default)
- [x] Edit mode toggle v header (PackHeader updated)
  - Edit button to enter edit mode
  - "Editing" badge indicator
  - Conditional button display
- [x] "Unsaved changes" warning
  - `UnsavedChangesDialog` component
  - `useBeforeUnload` hook for tab close protection
  - Save/Discard/Cancel options
- [x] Save/Discard buttons in edit mode
  - Integrated into PackHeader
  - Disabled state when no changes
  - Loading state during save

#### Iteration 2.2: Inline Editing ✅ DONE (2026-01-31)
- [x] `EditableText.tsx` component (~280 řádků)
  - Click-to-edit with Enter/Escape shortcuts
  - Single-line (input) and multi-line (textarea) modes
  - Validation support (required, maxLength, custom)
  - Premium styling with edit indicator
- [x] `EditableTags.tsx` component (~200 řádků)
  - Click tag to remove (in edit mode)
  - Add new tags via input
  - Suggested tags dropdown
  - Special styling for nsfw-pack, style:, subject: tags

#### Iteration 2.3: EditPreviewsModal ✅ DONE (2026-01-31)
- [x] `EditPreviewsModal.tsx` (~450 řádků)
  - Preview grid with drag & drop reordering
  - Add preview (upload file or URL)
  - Remove preview
  - Set as cover image (star icon)
  - Video/image type detection
  - Index badges and cover badge

#### Iteration 2.4: EditDependenciesModal ✅ DONE (2026-01-31)
- [x] `EditDependenciesModal.tsx` (~450 řádků)
  - Expandable dependency list with details
  - Mark for removal (with restore option)
  - Add dependency panel (search placeholder)
  - Type filter dropdown
  - Search/filter dependencies
  - Support for 8+ dependencies with scroll

#### Iteration 2.5: Description Editor ✅ DONE (2026-01-31)
- [x] `DescriptionEditorModal.tsx` (~450 řádků)
  - Auto-detect content format (HTML vs Markdown)
  - Format toggle (Markdown/HTML)
  - Markdown toolbar (bold, italic, headers, lists, links, code, quote, image)
  - Keyboard shortcuts (Ctrl+B, Ctrl+I, Ctrl+K)
  - Split view: edit | preview
  - Full-screen editing option
  - Live preview with basic Markdown rendering
  - HTML raw editor for Civitai imports

### Phase 3: Pack Creation ✅ COMPLETE
**Duration:** 1-2 sessions
**Goal:** Vytváření nových packů

#### Iteration 3.1: Backend API ✅ DONE (2026-01-31)
- [x] `POST /api/packs/create` endpoint
  - `CreatePackRequest` Pydantic model with all fields
  - Creates pack with `pack_category = PackCategory.CUSTOM`
  - Creates pack directories (resources/previews, resources/workflows)
  - Validates unique pack name
  - Returns success with pack name for navigation
- [x] Validation (unique name, required fields)

#### Iteration 3.2: CreatePackModal ✅ DONE (2026-01-31)
- [x] `modals/CreatePackModal.tsx` (~400 řádků)
  - Pack type selection (6 types: lora, checkpoint, vae, controlnet, textual_inversion, embedding)
  - Name input (required, unique)
  - Description input (Markdown supported)
  - Base model selector (SD 1.5, SDXL 1.0, Pony, etc.)
  - Version input (default: 1.0.0)
  - Author input
  - Tags input (TagInput component with Add/Remove)
  - Trigger words input (TagInput component)
  - Full i18n support (en.json + cs.json)
  - Form validation, error handling, loading states

#### Iteration 3.3: PacksPage Integration ✅ DONE (2026-01-31)
- [x] "Create Pack" button in header
- [x] Empty state with create CTA
- [x] Full i18n support for PacksPage
  - All hardcoded strings replaced with t() calls
  - New translation keys in en.json/cs.json
- [x] useMutation for pack creation
- [x] Auto-navigate to new pack after creation
- [x] Query invalidation after create

### Phase 4: Plugin System ✅ COMPLETE
**Duration:** 1 session
**Goal:** Type-specific behavior

#### Iteration 4.1: Plugin Infrastructure ✅ DONE (2026-01-31)
- [x] `plugins/types.ts` (409 řádků) - Plugin interfaces, PluginContext, PluginFeatures
- [x] `plugins/usePackPlugin.ts` (157 řádků) - Plugin hook s PLUGIN_REGISTRY
- [x] Plugin loading v PackDetailPage
- [x] Priority-based plugin matching (Install: 100, Civitai: 50, Custom: 0)

#### Iteration 4.2: CivitaiPlugin ✅ DONE (2026-01-31)
- [x] `plugins/CivitaiPlugin.tsx` (360 řádků)
- [x] Check Updates button with `/api/updates/check/{pack_name}` integration
- [x] Apply updates via `/api/updates/apply/{pack_name}`
- [x] CivitaiInfoSection showing source metadata
- [x] View on Civitai link
- [x] Features: canCheckUpdates, canEditParameters, canDelete

#### Iteration 4.3: CustomPlugin ✅ DONE (2026-01-31)
- [x] `plugins/CustomPlugin.tsx` (490 řádků)
- [x] Pack dependencies section (pack-to-pack dependencies)
- [x] Tree view for 7+ dependencies
- [x] EditCapabilitiesInfo showing full edit mode
- [x] Features: full editability, canManagePackDependencies

#### Iteration 4.4: InstallPlugin ✅ DONE (2026-01-31)
- [x] `plugins/InstallPlugin.tsx` (326 řádků) - PROTOTYPE
- [x] PrototypeNotice banner
- [x] ScriptsSection with mock scripts (install.sh, start.sh, stop.sh, update.sh)
- [x] EnvironmentStatus component (installed/running/stopped)
- [x] Features: canRunScripts, limited editability
- [x] NOTE: Full implementation deferred to future plan

#### Plugin Tests ✅ DONE (2026-01-31)
- [x] `__tests__/pack-plugins.test.ts` (72 tests)
- [x] Plugin matching logic tests
- [x] Plugin features tests
- [x] Validation tests
- [x] Context creation tests
- [x] Pack dependencies tests
- [x] usePackPlugin hook logic tests

### Phase 5: Polish & Testing ✅ COMPLETE (REVIEWED 2026-01-31)
**Duration:** 1 session
**Goal:** Production ready

#### Iteration 5.1: Animations & Transitions ✅ DONE
- [x] Section enter/exit animations - all sections use `ANIMATION_PRESETS.fadeIn` with staggered delays
- [x] Modal transitions - `fadeIn` backdrop + `scaleIn` content
- [x] Gallery grid staggered animations (30ms per item)
- [x] Loading skeletons in `LoadingSection.tsx`

#### Iteration 5.2: Error Handling ✅ DONE + REVIEWED
- [x] `ErrorBoundary.tsx` (270 řádků) - class component error boundary
- [x] `SectionErrorBoundary` - class component s proper retry support
- [x] Friendly error messages s development mode stack traces
- [x] Recovery actions (Retry, Go Home buttons)
- [x] Integrated into PackDetailPage:
  - Page-level ErrorBoundary wraps entire content
  - Section-level SectionErrorBoundary for each section (Gallery, Info, Dependencies, Workflows, Parameters, Storage)
  - Plugin sections wrapped in SectionErrorBoundary
  - Plugin modals wrapped in ErrorBoundary

**REVIEW FIXES (2026-01-31):**
- [x] Fixed: SectionErrorBoundary retry now properly resets error state
- [x] Fixed: Plugin sections now wrapped in error boundaries
- [x] Fixed: retryCount tracking for multiple retry attempts
- [x] Fixed: Development mode error message display in section fallback

#### Iteration 5.3: Testing ✅ DONE + REVIEWED
- [x] `pack-detail-hooks.test.ts` (41 tests) - unit tests pro hook logic
- [x] `error-boundary.test.ts` (30 tests) - ErrorBoundary component tests
  - State management tests
  - Props validation tests
  - Retry mechanism tests
  - Development mode detection
  - Integration tests
  - Error type tests
- [x] `pack-plugins.test.ts` (79 tests) - plugin system tests
- [x] **Total: 539 frontend tests passing**

---

## Error Boundary Architecture

### Overview

Error boundaries provide graceful error handling at multiple levels:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PackDetailPage                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    ErrorBoundary                              │ │
│  │  (Page-level - catches all unhandled errors)                 │ │
│  │  ┌─────────────────────────────────────────────────────────┐ │ │
│  │  │                PackDetailPageContent                     │ │ │
│  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐  │ │ │
│  │  │  │SectionError   │ │SectionError   │ │SectionError   │  │ │ │
│  │  │  │Boundary       │ │Boundary       │ │Boundary       │  │ │ │
│  │  │  │ (Gallery)     │ │ (Info)        │ │ (Deps)        │  │ │ │
│  │  │  └───────────────┘ └───────────────┘ └───────────────┘  │ │ │
│  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐  │ │ │
│  │  │  │SectionError   │ │SectionError   │ │SectionError   │  │ │ │
│  │  │  │Boundary       │ │Boundary       │ │Boundary       │  │ │ │
│  │  │  │ (Workflows)   │ │ (Params)      │ │ (Storage)     │  │ │ │
│  │  │  └───────────────┘ └───────────────┘ └───────────────┘  │ │ │
│  │  │  ┌─────────────────────────────────────────────────────┐│ │ │
│  │  │  │        SectionErrorBoundary (Plugin Sections)       ││ │ │
│  │  │  └─────────────────────────────────────────────────────┘│ │ │
│  │  │  ┌─────────────────────────────────────────────────────┐│ │ │
│  │  │  │           ErrorBoundary (Plugin Modals)             ││ │ │
│  │  │  └─────────────────────────────────────────────────────┘│ │ │
│  │  └─────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### ErrorBoundary (Class Component)

Main error boundary with full UI:

```typescript
interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode              // Optional custom fallback
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  showDetails?: boolean             // Show stack in dev mode (auto-detected)
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  showStack: boolean
}
```

**Features:**
- Full error UI with icon, message, and action buttons
- "Try Again" button resets error state
- "Go Home" button navigates to home
- Development mode shows expandable stack trace
- `onError` callback for logging/analytics

### SectionErrorBoundary (Class Component)

Compact error boundary for sections with retry support:

```typescript
interface SectionErrorBoundaryProps {
  children: ReactNode
  sectionName?: string    // Display name for error message
  onRetry?: () => void    // Called AFTER state reset
}

interface SectionErrorBoundaryState {
  hasError: boolean
  error: Error | null
  retryCount: number      // Tracks retry attempts
}
```

**Key Behavior:**
1. On error: Shows compact fallback with section name
2. On retry click:
   - First: Resets `hasError` to `false`
   - Then: Calls `onRetry()` to refresh data
3. `retryCount` increments each retry for debugging

### Usage in PackDetailPage

```tsx
// Page-level boundary
export function PackDetailPage() {
  return (
    <ErrorBoundary onError={(error) => console.error(error)}>
      <PackDetailPageContent />
    </ErrorBoundary>
  )
}

// Section-level boundaries
<SectionErrorBoundary sectionName="Gallery" onRetry={packData.refetch}>
  <PackGallery ... />
</SectionErrorBoundary>

// Plugin section boundary
<SectionErrorBoundary sectionName="Plugin Sections" onRetry={packData.refetch}>
  {plugin.renderExtraSections(context)}
</SectionErrorBoundary>

// Plugin modal boundary (no retry needed for modals)
<ErrorBoundary onError={(error) => console.error(error)}>
  {plugin.renderModals(context)}
</ErrorBoundary>
```

### Error Isolation

Each section is isolated - if Gallery crashes, other sections continue working:

| Component | Boundary | On Error |
|-----------|----------|----------|
| PackHeader | None | Escalates to page |
| PackGallery | SectionErrorBoundary | Shows section error |
| PackInfoSection | SectionErrorBoundary | Shows section error |
| PackDependenciesSection | SectionErrorBoundary | Shows section error |
| PackWorkflowsSection | SectionErrorBoundary | Shows section error |
| PackParametersSection | SectionErrorBoundary | Shows section error |
| PackStorageSection | SectionErrorBoundary | Shows section error |
| Plugin Sections | SectionErrorBoundary | Shows section error |
| Plugin Modals | ErrorBoundary | Shows modal error |

---

## Testing Strategy

### Unit Tests
```
tests/
├── hooks/
│   ├── usePackData.test.ts
│   ├── usePackEdit.test.ts
│   └── usePackDownloads.test.ts
├── utils/
│   ├── packValidation.test.ts
│   └── packTransforms.test.ts
└── plugins/
    └── CivitaiPlugin.test.ts
```

### Component Tests
- Každá section komponenta má basic render test
- Modal tests: open, close, submit
- Edit mode toggle tests

### E2E Tests
- Create custom pack from scratch
- Edit existing pack (all sections)
- Import from Civitai (existing)
- Delete pack with confirmation

---

## Risk Mitigation

### 1. Breaking Existing Functionality
**Mitigation:**
- Extrakce po malých krocích
- Test po každé extrakci
- Starý kód zakomentován dokud není ověřeno
- Git commit po každém stabilním stavu

### 2. Large File Refactoring
**Mitigation:**
- Jasný plán co extrahovat kdy
- Jedna sekce = jeden commit
- TypeScript kontrola po každé změně
- `verify.sh` před každým commitem

### 3. Complex State Management
**Mitigation:**
- Hooks isolují state logiku
- Jasné rozhraní mezi komponenty
- Edit state v jednom místě (usePackEdit)

### 4. Plugin System Complexity
**Mitigation:**
- Začít jednoduchým interface
- Přidat features postupně
- Fallback na default chování

### 5. Performance (8+ dependencies)
**Mitigation:**
- Virtualized list pro dlouhé seznamy
- Memoization kde potřeba
- Lazy loading modals

### 6. 🚨 Civitai Import Regression
**Mitigation:**
- **NIKDY** neměnit datové typy bez konzultace
- Zachovat transformační logiku
- Testovat import flow po každé změně
- Při pochybnostech STOP a ptát se

### 7. 🚨 Preview/Video FUNKČNÍ Regression
**Mitigation:**
- MediaPreview volat se SPRÁVNÝMI PROPS (autoPlay, playFullOnHover, thumbnailSrc)
- Civitai URL transformace zachovat (algoritmy)
- Test: hover → video hraje, click → fullscreen
- UI může být vylepšeno (hover effects, animace), ale funkce musí fungovat

### 8. 🚨 Dependencies FUNKČNÍ Regression
**Mitigation:**
- Všechna data musí být ZOBRAZITELNÁ (nemusí vypadat stejně, ale musí být vidět)
- Download progress, speed, ETA - algoritmy zachovat
- Restore from backup - funkce zachovat
- UI může být krásnější, ale žádná informace nesmí zmizet
- Všechny sloupce/informace musí zůstat
- Download progress bar musí fungovat identicky

---

## Implementation Registry 📋

### SOUHRN VŠECH IMPLEMENTOVANÝCH SOUBORŮ

**Celkem vytvořeno/změněno: 35+ souborů, ~10,000 řádků nového kódu**

---

### 📁 pack-detail/ Directory Structure

```
apps/web/src/components/modules/pack-detail/
├── index.ts                    # 15 lines - public exports
├── types.ts                    # 445 lines - TypeScript interfaces
├── constants.ts                # 336 lines - animations, grid config
│
├── hooks/                      # 1,294 lines total
│   ├── index.ts                # 28 lines
│   ├── usePackData.ts          # 586 lines
│   ├── usePackDownloads.ts     # 296 lines
│   └── usePackEdit.ts          # 384 lines
│
├── shared/                     # 1,681 lines total
│   ├── index.ts                # export barrel
│   ├── SectionHeader.tsx       # 193 lines
│   ├── EmptyState.tsx          # 218 lines
│   ├── LoadingSection.tsx      # 271 lines
│   ├── AnimatedSection.tsx     # 184 lines
│   ├── EditableText.tsx        # 361 lines
│   ├── EditableTags.tsx        # 258 lines
│   └── UnsavedChangesDialog.tsx # 196 lines
│
├── sections/                   # 2,270 lines total
│   ├── index.ts                # export barrel
│   ├── PackHeader.tsx          # 324 lines
│   ├── PackGallery.tsx         # 220 lines
│   ├── PackInfoSection.tsx     # 285 lines
│   ├── PackDependenciesSection.tsx # 571 lines
│   ├── PackWorkflowsSection.tsx    # 356 lines
│   ├── PackParametersSection.tsx   # 212 lines
│   ├── PackStorageSection.tsx      # 169 lines
│   └── PackUserTagsSection.tsx     # 133 lines
│
├── modals/                     # 3,863 lines total
│   ├── index.ts                # export barrel
│   ├── EditPackModal.tsx           # 293 lines
│   ├── EditParametersModal.tsx     # 358 lines
│   ├── UploadWorkflowModal.tsx     # 228 lines
│   ├── BaseModelResolverModal.tsx  # 758 lines
│   ├── EditPreviewsModal.tsx       # 579 lines
│   ├── EditDependenciesModal.tsx   # 608 lines
│   ├── DescriptionEditorModal.tsx  # 546 lines
│   └── CreatePackModal.tsx         # 493 lines
│
├── plugins/                    # 1,585 lines total
│   ├── index.ts                # 22 lines - exports
│   ├── types.ts                # 409 lines - interfaces
│   ├── usePackPlugin.ts        # 157 lines - hook
│   ├── CivitaiPlugin.tsx       # 360 lines
│   ├── CustomPlugin.tsx        # 490 lines
│   └── InstallPlugin.tsx       # 326 lines (prototype)
│
└── utils/
    └── index.ts                # placeholder
```

---

### 🔧 HOOKS - Detailní dokumentace

#### `usePackData.ts` (586 řádků)
**Účel:** Centralizovaná správa všech pack dat a mutací

**Queries:**
- `packQuery` - GET /api/v2/packs/{name}
- `backupStatusQuery` - GET /api/store/packs/{name}/backup-status

**Mutations (15+):**
- `deletePackMutation` - DELETE /api/v2/packs/{name}
- `usePackMutation` - POST /api/v2/packs/{name}/use
- `updatePackMutation` - PATCH /api/v2/packs/{name}
- `updateParametersMutation` - PATCH /api/v2/packs/{name}/parameters
- `resolveBaseMutation` - POST /api/v2/packs/{name}/resolve-base
- `uploadWorkflowMutation` - POST /api/v2/packs/{name}/workflows
- `deleteWorkflowMutation` - DELETE /api/v2/packs/{name}/workflows/{workflow}
- `generateDefaultWorkflowMutation` - POST /api/v2/packs/{name}/workflows/generate-default
- `linkWorkflowMutation` - POST /api/v2/packs/{name}/workflows/{workflow}/link
- `unlinkWorkflowMutation` - DELETE /api/v2/packs/{name}/workflows/{workflow}/link
- `backupPullMutation` - POST /api/store/backup/restore/{name}
- `backupPushMutation` - POST /api/store/backup/blob
- `backupPushFreeMutation` - POST /api/store/backup/blob (s delete_local)
- `downloadAssetMutation` - POST /api/v2/packs/{name}/download/{asset}
- `deleteAssetMutation` - DELETE /api/v2/packs/{name}/dependencies/{asset}
- `restoreBlobMutation` - POST /api/store/backup/restore-blob

**Return type:**
```typescript
interface UsePackDataReturn {
  pack: PackDetail | undefined
  packLock: PackLock | undefined
  backupStatus: BackupStatus | undefined
  isLoading: boolean
  error: Error | null
  refetch: () => void
  // ... všechny mutations
}
```

#### `usePackDownloads.ts` (296 řádků)
**Účel:** Polling aktivních downloadů s progress tracking

**Features:**
- Auto-polling GET /api/downloads (každé 2s když aktivní)
- Progress calculation (downloaded/total bytes)
- Speed calculation (bytes/s)
- ETA calculation
- Toast notifications pro completed/failed
- `isDownloading(assetName)` helper

**Return type:**
```typescript
interface UsePackDownloadsReturn {
  activeDownloads: DownloadProgress[]
  getDownloadProgress: (name: string) => DownloadProgress | undefined
  isDownloading: (name: string) => boolean
  hasActiveDownloads: boolean
}
```

#### `usePackEdit.ts` (384 řádků)
**Účel:** Edit mode state management

**Features:**
- Global edit mode toggle
- Per-section editing state
- Field-level value tracking (setFieldValue/getFieldValue)
- Change detection (hasUnsavedChanges)
- Dirty fields tracking
- Validation support
- useBeforeUnload hook pro browser warning

**Return type:**
```typescript
interface UsePackEditReturn {
  isEditing: boolean
  editingSection: string | null
  hasUnsavedChanges: boolean
  dirtyFields: Set<string>
  startEditing: (section?: string) => void
  stopEditing: () => void
  setFieldValue: (path: string, value: any) => void
  getFieldValue: (path: string) => any
  markClean: () => void
  discardChanges: () => void
}
```

---

### 🎨 SHARED COMPONENTS - Detailní dokumentace

#### `SectionHeader.tsx` (193 řádků)
**Props:**
- `title: string` - section title
- `icon?: LucideIcon` - optional icon
- `editable?: boolean` - show edit button on hover
- `onEdit?: () => void` - edit button callback
- `collapsible?: boolean` - can collapse/expand
- `defaultCollapsed?: boolean`
- `badge?: string` - optional badge text
- `actions?: ReactNode` - additional action buttons

#### `EmptyState.tsx` (218 řádků)
**Presets:**
- `gallery` - no previews
- `dependencies` - no dependencies
- `workflows` - no workflows
- `parameters` - no parameters
- `custom` - customizable

**Props:**
- `preset?: EmptyStatePreset`
- `icon?: LucideIcon`
- `title?: string`
- `description?: string`
- `action?: { label: string, onClick: () => void }`

#### `LoadingSection.tsx` (271 řádků)
**Variants:**
- `header` - pack header skeleton
- `gallery` - preview grid skeleton
- `info` - info section skeleton
- `dependencies` - dependency list skeleton
- `workflows` - workflow list skeleton
- `parameters` - params grid skeleton

#### `AnimatedSection.tsx` (184 řádků)
**Props:**
- `children: ReactNode`
- `delay?: number` - staggered animation delay
- `className?: string`

**Animace:** fade-in + slide-up s configurable delay

#### `EditableText.tsx` (361 řádků)
**Features:**
- Click-to-edit
- Single-line (input) nebo multi-line (textarea)
- Enter = save, Escape = cancel
- Validation (required, maxLength, custom validator)
- Error state display
- Edit indicator icon

**Props:**
- `value: string`
- `onChange: (value: string) => void`
- `editable?: boolean`
- `multiline?: boolean`
- `placeholder?: string`
- `validate?: (value: string) => string | null`
- `required?: boolean`
- `maxLength?: number`

#### `EditableTags.tsx` (258 řádků)
**Features:**
- Tag display chips
- Click tag to remove (in edit mode)
- Add new tag input
- Suggested tags dropdown
- Special styling for: `nsfw-pack`, `style:*`, `subject:*`

**Props:**
- `tags: string[]`
- `onChange: (tags: string[]) => void`
- `editable?: boolean`
- `suggestions?: string[]`
- `placeholder?: string`

#### `UnsavedChangesDialog.tsx` (196 řádků)
**Features:**
- Modal dialog for unsaved changes warning
- Three actions: Save, Discard, Cancel
- Loading state during save

**Props:**
- `isOpen: boolean`
- `onSave: () => Promise<void>`
- `onDiscard: () => void`
- `onCancel: () => void`
- `isSaving?: boolean`

---

### 📦 SECTION COMPONENTS - Detailní dokumentace

#### `PackHeader.tsx` (324 řádků)
**Zobrazuje:**
- Pack name (velký titulek)
- Version badge
- Type badge (LoRA, Checkpoint, VAE...)
- Source badge (Civitai link, Local)
- NSFW indicator
- "Needs Setup" warning badge
- Base model badge

**Akce:**
- Use Pack button
- Edit mode toggle
- Save/Discard (v edit mode)
- Delete button
- Open on Civitai link

**Edit mode:**
- "Editing" badge indicator
- Save/Discard buttons
- Conditional action display

#### `PackGallery.tsx` (220 řádků)
**Features:**
- Responsive preview grid
- Zoom controls (sm/md/lg)
- Video autoPlay on hover
- Click to open fullscreen

**MediaPreview props zachovány:**
- `autoPlay={true}`
- `playFullOnHover={true}`
- `thumbnailSrc` pro video thumbnails

**Props:**
- `previews: PreviewInfo[]`
- `onPreviewClick: (index: number) => void`
- `editable?: boolean`
- `onEditClick?: () => void`

#### `PackInfoSection.tsx` (285 řádků)
**Zobrazuje:**
- Description (HTML rendering via dangerouslySetInnerHTML)
- Trigger words (copyable chips)
- Model info badges:
  - Base model
  - Author
  - Downloads count
  - Rating
  - Trained words

**Akce:**
- Copy trigger word to clipboard
- Edit description button

#### `PackDependenciesSection.tsx` (571 řádků) ⚠️ KRITICKÁ KOMPONENTA
**Zobrazuje VŠECHNA data:**
- Type icon (Checkpoint, LoRA, VAE, ControlNet, Embedding, TextualInversion)
- Name + version
- Size (formatted)
- Status icon (installed ✓, downloading ↓, backup-only ☁, unresolved ⚠, pending ○)
- Provider badge

**Expandable detail:**
- SHA256 hash
- Local path
- Source URL
- Model ID, Model Name, Creator (Civitai)
- Repo ID (HuggingFace)

**Download progress:**
- Progress bar
- Downloaded/Total bytes
- Speed (MB/s)
- ETA

**Akce:**
- Download button
- Re-download button
- Delete button
- Restore from backup button
- Resolve base model button

#### `PackWorkflowsSection.tsx` (356 řádků)
**Zobrazuje:**
- Workflow name + description
- Default workflow badge
- Symlink status (In ComfyUI ✓ / Broken link ⚠ / Not linked)

**Akce:**
- Link to ComfyUI
- Unlink from ComfyUI
- Download JSON
- Delete workflow
- Generate Default workflow

#### `PackParametersSection.tsx` (212 řádků)
**Zobrazuje:**
- Parameter grid (2 columns)
- Parameter name + value
- Special handling for: sampler, scheduler, steps, cfg, strength, clip_skip

**Akce:**
- Edit parameters button → opens EditParametersModal

#### `PackStorageSection.tsx` (169 řádků)
**Integruje existující komponenty:**
- `PackStorageStatus` - disk usage, backup status
- `PackStorageActions` - Pull/Push/Push&Free buttons
- `PackBlobsTable` - blob-level management

#### `PackUserTagsSection.tsx` (133 řádků)
**Zobrazuje:**
- User tags as chips
- Special styling for `nsfw-pack`, `nsfw-pack-hide`, `favorites`, `to-review`

**Akce:**
- Edit tags button → opens EditPackModal

---

### 🪟 MODAL COMPONENTS - Detailní dokumentace

#### `EditPackModal.tsx` (293 řádků)
**Features:**
- User tags editor
- Suggested tags: nsfw-pack, nsfw-pack-hide, favorites, to-review, wip, archived
- Custom tag input (Enter to add)
- Click tag to remove
- Special nsfw-pack styling (červená)

#### `EditParametersModal.tsx` (358 řádků)
**Features:**
- Quick-add buttons: sampler, scheduler, steps, cfg_scale, clip_skip, strength
- Editable parameter rows (key + value)
- Custom parameter input
- Type conversion (numbers vs strings)
- Delete parameter button

#### `UploadWorkflowModal.tsx` (228 řádků)
**Features:**
- File input (.json only)
- Auto-populate name from filename
- Optional description input
- Upload with loading state

#### `BaseModelResolverModal.tsx` (758 řádků)
**Features:**
- Three tabs: Local, Civitai, HuggingFace
- Smart base model hint extraction from pack
- Local model filtering by type
- Civitai search with method info display
- HuggingFace repo browser + file selection
- Model selection and resolution

#### `EditPreviewsModal.tsx` (579 řádků) - Phase 2
**Features:**
- Preview grid display
- Drag & drop reordering
- Add preview: file upload OR URL input
- Remove preview (X button)
- Set as cover (star icon)
- Video/image type detection
- Index badges
- Cover badge

#### `EditDependenciesModal.tsx` (608 řádků) - Phase 2
**Features:**
- Expandable dependency list
- Full dependency details
- Mark for removal (with restore option)
- Add dependency panel (search placeholder - not fully implemented)
- Type filter dropdown
- Search/filter dependencies
- Scroll support for 8+ dependencies

#### `DescriptionEditorModal.tsx` (546 řádků) - Phase 2
**Features:**
- Auto-detect content format (HTML vs Markdown)
- Format toggle (Markdown/HTML)
- Markdown toolbar:
  - Bold, Italic, Strikethrough
  - Headers (H1-H3)
  - Lists (bullet, numbered)
  - Links, Images
  - Code (inline, block)
  - Quote
- Keyboard shortcuts: Ctrl+B, Ctrl+I, Ctrl+K
- Split view: edit | preview
- Full-screen editing option
- Live Markdown preview
- HTML raw editor mode

#### `CreatePackModal.tsx` (493 řádků) - Phase 3
**Features:**
- Pack name input (required, unique)
- Pack type selector: lora, checkpoint, vae, controlnet, textual_inversion, embedding
- Description input (Markdown supported)
- Base model dropdown: SD 1.5, SD 2.1, SDXL 1.0, SDXL Turbo, Pony, Flux.1, Other
- Version input (default: 1.0.0)
- Author input
- Tags input (TagInput component)
- Trigger words input (TagInput component)
- Form validation
- Error handling
- Loading states
- Full i18n support

---

### 📝 TYPES.TS - Klíčové interfaces (445 řádků)

```typescript
// Pack types
type PackType = 'checkpoint' | 'lora' | 'vae' | 'controlnet' | 'embedding' | 'textual_inversion' | 'hypernetwork' | 'other'
type PackCategory = 'external' | 'custom' | 'install'

// Source info
interface PackSourceInfo {
  provider: 'civitai' | 'huggingface' | 'local' | 'url'
  model_id?: number
  version_id?: number
  url?: string
}

// Pack dependency ref (pack-to-pack)
interface PackDependencyRef {
  pack_name: string
  required: boolean
  version_constraint?: string
}

// Preview info
interface PreviewInfo {
  url: string
  type: 'image' | 'video'
  nsfw?: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
}

// Asset/Dependency
interface PackAsset {
  name: string
  type: PackType
  version?: string
  size?: number
  status: 'installed' | 'pending' | 'downloading' | 'backup-only' | 'unresolved'
  provider?: string
  sha256?: string
  local_path?: string
  url?: string
  selector?: {
    civitai?: { model_id: number, version_id?: number, file_id?: number }
    huggingface?: { repo_id: string, filename: string }
  }
}

// Download progress
interface DownloadProgress {
  asset_name: string
  pack_name: string
  downloaded: number
  total: number
  speed: number
  eta?: number
  status: 'downloading' | 'completed' | 'failed'
}

// Full pack detail response
interface PackDetail {
  name: string
  version?: string
  description?: string
  author?: string
  tags: string[]
  user_tags: string[]
  source_url?: string
  created_at?: string
  installed: boolean
  has_unresolved: boolean
  all_installed: boolean
  can_generate: boolean
  assets: PackAsset[]
  previews: PreviewInfo[]
  workflows: WorkflowInfo[]
  parameters?: GenerationParameters
  model_info?: ModelInfo
  pack: {
    source: PackSourceInfo
    pack_type: PackType
    pack_category: PackCategory
    pack_dependencies: PackDependencyRef[]
    // ... další fieldy
  }
  lock?: PackLock
}
```

---

### 🌐 i18n FILES - Internationalization

#### `apps/web/src/i18n/index.ts` (74 řádků)
**Features:**
- react-i18next configuration
- Language detection (localStorage → browser)
- Supported languages: en, cs
- `changeLanguage(lang)` export
- `getCurrentLanguage()` export
- `AVAILABLE_LANGUAGES` constant

#### `apps/web/src/i18n/locales/en.json` (247 řádků)
**Translation keys:**
- `pack.*` - pack detail page (~80 keys)
- `pack.modals.*` - all modals (~50 keys)
- `pack.modals.create.*` - create pack modal (20 keys)
- `packs.*` - packs list page (15 keys)
- `common.*` - shared strings (15 keys)
- `errors.*` - error messages (5 keys)

#### `apps/web/src/i18n/locales/cs.json` (250 řádků)
**Stejná struktura jako en.json, české překlady**

---

### 🔌 BACKEND CHANGES

#### `src/store/models.py`

**PackCategory enum (řádek 78):**
```python
class PackCategory(str, Enum):
    EXTERNAL = "external"  # Imported from Civitai, HuggingFace
    CUSTOM = "custom"      # Created locally
    INSTALL = "install"    # Installation pack
```

**PackDependencyRef model (řádek 438):**
```python
class PackDependencyRef(BaseModel):
    pack_name: str
    required: bool = True
    version_constraint: Optional[str] = None
```

**Pack model updates:**
- Added `pack_category: PackCategory = PackCategory.EXTERNAL`
- Added `pack_dependencies: List[PackDependencyRef] = []`

#### `src/store/api.py`

**CreatePackRequest model (řádek 2614):**
```python
class CreatePackRequest(BaseModel):
    name: str
    pack_type: str = "lora"
    description: Optional[str] = None
    base_model: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: Optional[List[str]] = []
    user_tags: Optional[List[str]] = []
    trigger_words: Optional[List[str]] = []
```

**POST /api/packs/create endpoint (řádek 2627):**
- Creates pack with `pack_category = PackCategory.CUSTOM`
- Creates directories: `resources/previews`, `resources/workflows`
- Validates unique pack name
- Returns: `{ "success": true, "name": "...", "message": "..." }`

---

### 📄 PACKS PAGE UPDATE

#### `apps/web/src/components/modules/PacksPage.tsx` (415 řádků)

**Nové features:**
- Full i18n support - všechny stringy přes `t()`
- Create Pack button v headeru
- `useMutation` pro vytvoření packu
- Auto-navigate na nový pack po vytvoření
- Query invalidation po create
- Empty state s create CTA

**Translation keys používané:**
- `packs.title`, `packs.subtitle`
- `packs.search`, `packs.create`
- `packs.filter.allTags`, `packs.filter.activeFilters`
- `packs.empty.noPacks`, `packs.empty.noMatch`
- `packs.card.assets`, `packs.card.needsSetup`
- `packs.zoom.in`, `packs.zoom.out`
- `common.loading`, `errors.loadFailed`

---

## Current Status

### PHASE 1: Foundation & Core Extraction ✅ COMPLETE

**Iteration 1.1** ✅ (2026-01-30)
- Directory structure vytvořena
- `types.ts` (445 řádků) - všechny TypeScript interfaces
- `constants.ts` (336 řádků) - animace, grid config

**Iteration 1.2** ✅ (2026-01-30)
- `usePackData.ts` (586 řádků) - queries + 15 mutations
- `usePackDownloads.ts` (296 řádků) - download progress polling

**Iteration 1.3** ✅ (2026-01-31)
- 8 section komponent extrahováno (2,270 řádků celkem)
- Všechny funkce zachovány
- UI vylepšeno (animace, hover effects)

**Iteration 1.4** ✅ (2026-01-31)
- 4 modal komponenty (1,637 řádků)
- EditPackModal, EditParametersModal, UploadWorkflowModal, BaseModelResolverModal

**Iteration 1.5** ✅ (2026-01-31)
- Backend: PackCategory, PackDependencyRef
- Frontend: i18n framework (571 řádků)
- Types: PackCategory, PackDependencyRef interfaces

### PHASE 2: Edit Capabilities ✅ COMPLETE

**Iteration 2.1** ✅ (2026-01-31)
- `usePackEdit.ts` (384 řádků) - edit mode state
- `UnsavedChangesDialog.tsx` (196 řádků)
- PackHeader updated s edit mode toggle

**Iteration 2.2** ✅ (2026-01-31)
- `EditableText.tsx` (361 řádků)
- `EditableTags.tsx` (258 řádků)

**Iteration 2.3** ✅ (2026-01-31)
- `EditPreviewsModal.tsx` (579 řádků)

**Iteration 2.4** ✅ (2026-01-31)
- `EditDependenciesModal.tsx` (608 řádků)

**Iteration 2.5** ✅ (2026-01-31)
- `DescriptionEditorModal.tsx` (546 řádků)

### PHASE 3: Pack Creation ✅ COMPLETE

**Iteration 3.1** ✅ (2026-01-31)
- Backend: CreatePackRequest, POST /api/packs/create

**Iteration 3.2** ✅ (2026-01-31)
- `CreatePackModal.tsx` (493 řádků)

**Iteration 3.3** ✅ (2026-01-31)
- PacksPage.tsx updated (415 řádků)
- Full i18n support
- Create Pack button + mutation

### STATISTICS

| Category | Files | Lines |
|----------|-------|-------|
| Hooks | 4 | 1,423 |
| Shared components | 8 | 2,166 |
| Section components | 8 | 2,270 |
| Modal components | 8 | 3,863 |
| Plugins | 4 | 1,585 |
| Types/Constants | 2 | 781 |
| i18n | 3 | 571 |
| Tests | 3 | 1,550 |
| **TOTAL** | **40** | **14,209** |

**Phase 5 Files:**
- `ErrorBoundary.tsx` (270 řádků) - class components
- `pack-detail-hooks.test.ts` (400 řádků, 41 tests)
- `error-boundary.test.ts` (350 řádků, 30 tests)

### PHASE 4: Plugin System ✅ COMPLETE

**Iteration 4.1-4.4** ✅ (2026-01-31)
- Plugin infrastructure (types.ts, usePackPlugin.ts)
- CivitaiPlugin (360 řádků) - Update checking, Civitai metadata
- CustomPlugin (490 řádků) - Pack dependencies, full editability
- InstallPlugin (326 řádků) - Prototype for install packs
- Tests (79 tests v pack-plugins.test.ts + 7 API URL tests)

### PHASE 5: Polish & Testing ✅ COMPLETE + REVIEWED

**Iteration 5.1-5.3** ✅ (2026-01-31)
- ErrorBoundary.tsx (270 řádků) - page-level + section-level error boundaries
- SectionErrorBoundary - class component with proper retry mechanism
- pack-detail-hooks.test.ts (41 tests) - unit tests for hook logic
- error-boundary.test.ts (30 tests) - ErrorBoundary component tests
- Section staggered animations, modal transitions
- Plugin sections wrapped in error boundaries
- **Total: 539 frontend tests passing**

**Review Fixes:**
- ✅ SectionErrorBoundary retry properly resets error state
- ✅ Plugin sections wrapped in error boundaries
- ✅ Plugin modals wrapped in error boundaries
- ✅ Added 30 new tests for ErrorBoundary

### Phase 6: Backend API & Parameters Unification 🚧 IN PROGRESS

**Goal:** Sjednocení ukládání všech editovatelných částí packu + oprava "ghost parameters"

#### Zjištěné problémy

**1. "Ghost" `hires_fix: false`**
- V `GenerationParameters` modelu je `hires_fix: bool = False` (ne Optional[None])
- Při uložení jakéhokoliv parametru se vytvoří celý objekt s defaulty
- `hires_fix: false` se serializuje do JSON i když uživatel ho nikdy nenastavil

**2. Duplicitní modely**
- `GenerationParameters` existuje ve DVOU souborech:
  - `src/core/models.py:352` - dataclass (legacy)
  - `src/store/models.py:460` - Pydantic model (používá se)
- Možný zdroj konfuzí a bugů

**3. UI nezobrazuje všechny parametry**
- `PackParametersSection` má hardcoded seznam: clip_skip, cfg_scale, steps, sampler, scheduler, width/height, denoise
- `hires_*` parametry NEJSOU zobrazeny
- Custom parametry NEJSOU zobrazeny

**4. Nekonzistentní save API**
| Část | Endpoint | Status |
|------|----------|--------|
| Parameters | `PATCH /api/packs/{name}/parameters` | ✅ Funguje, ale s bugy |
| Workflows | `POST /api/packs/{name}/workflows/upload` | ⚠️ Starší API |
| Dependencies | Různé endpointy | ⚠️ Fragmentované |
| Description | CHYBÍ | ❌ |
| Previews | CHYBÍ | ❌ |
| Metadata (name, tags) | `PATCH /api/packs/{name}` | ✅ Funguje |

---

#### Iteration 6.1: Fix GenerationParameters Model ✅ COMPLETE (2026-02-01)

**Cíl:** Opravit model, aby defaulty neprosakovaly do JSON

**DONE:**
- ✅ `hires_fix: bool = False` → `hires_fix: Optional[bool] = None` v obou modelech
- ✅ `model_serializer` v Pydantic modelu pro automatické exclude None
- ✅ Aktualizace dataclass verze v `core/models.py`
- ✅ 15 nových testů v `tests/unit/store/test_generation_parameters.py`
- ✅ 6 nových testů v `TestHiresFixSerialization` ve stávajícím test souboru

**Změny v `src/store/models.py`:**
```python
class GenerationParameters(BaseModel):
    """Default generation parameters extracted from Civitai or user-defined."""
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    clip_skip: Optional[int] = None
    denoise: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None

    # HiRes - ALL Optional[None] now!
    hires_fix: Optional[bool] = None        # ← FIX: was bool = False
    hires_upscaler: Optional[str] = None
    hires_steps: Optional[int] = None
    hires_denoise: Optional[float] = None

    # Custom parameters - for ANY user-defined parameter
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Allow additional fields
```

**Migrace existujících packů:**
- Script: `scripts/migrate_parameters.py`
- Nahradí `hires_fix: false` → odstranit (je-li default)
- Zachová `hires_fix: true` (explicitně nastaveno)

**Testy:**
- `tests/unit/store/test_generation_parameters.py`
- Test: default values nezasahují do JSON
- Test: custom parameters v `extra` dict
- Test: migrace existujících packů

---

#### Iteration 6.2: Enhance EditParametersModal UI ✅ COMPLETE (2026-02-01)

**Cíl:** Zobrazit VŠECHNY parametry včetně custom

**DONE:**
- ✅ Kategorizace do 4 sekcí: Generation, Resolution, HiRes, Custom
- ✅ Collapsible HiRes sekce
- ✅ BooleanSwitch pro `hires_fix` místo text input
- ✅ Number inputs pro numerické parametry
- ✅ Quick-add rozšířen o všechny hires_* parametry
- ✅ Human-readable labels pro všechny parametry

**Změny v `EditParametersModal.tsx`:**

1. **Kategorizace parametrů:**
```tsx
const PARAM_CATEGORIES = {
  generation: ['sampler', 'scheduler', 'steps', 'cfg_scale', 'clip_skip', 'denoise', 'seed'],
  resolution: ['width', 'height'],
  hires: ['hires_fix', 'hires_upscaler', 'hires_steps', 'hires_denoise'],
}
```

2. **Collapsible sekce:**
- "Generation Settings" (základní)
- "Resolution" (width/height)
- "HiRes Fix" (collapsible, expanded only if hires_fix=true)
- "Custom Parameters" (všechno ostatní)

3. **Type-aware inputs:**
```tsx
// Boolean parameters → switch
{type === 'boolean' && <Switch checked={value} onChange={...} />}

// Number parameters → number input
{type === 'number' && <input type="number" value={value} .../>}

// String parameters → text/select
{type === 'string' && <input type="text" value={value} .../>}
```

4. **Quick-add rozšířit:**
```tsx
const QUICK_ADD_PARAMS = [
  // Existing
  'clipSkip', 'cfgScale', 'steps', 'sampler', 'scheduler', 'width', 'height', 'denoise',
  // New: HiRes
  'hiresFix', 'hiresUpscaler', 'hiresSteps', 'hiresDenoise',
]
```

**Testy:**
- `apps/web/src/__tests__/EditParametersModal.test.tsx`
- Test: zobrazí všechny parametry včetně custom
- Test: boolean input pro hires_fix
- Test: collapsible HiRes sekce

---

#### Iteration 6.3: Enhance PackParametersSection UI ✅ COMPLETE (2026-02-01)

**Cíl:** Zobrazit VŠECHNY parametry ve čtecím módu

**DONE:**
- ✅ Dynamické zobrazení VŠECH parametrů z `parameters` objektu
- ✅ Kategorizace do 4 skupin: Generation, Resolution, HiRes, Custom
- ✅ Collapsible HiRes sekce (pokud existují hires_* params)
- ✅ Boolean hodnoty zobrazeny jako "Enabled"/"Disabled"
- ✅ Kombinovaná resolution jako "512×768"
- ✅ Human-readable labels pro všechny parametry

**Změny v `PackParametersSection.tsx`:**

1. **Dynamické parametry:**
```tsx
// Místo hardcoded podmínek
const displayParams = useMemo(() => {
  if (!parameters) return []

  return Object.entries(parameters)
    .filter(([key, value]) => value != null && value !== '')
    .map(([key, value]) => ({
      key,
      label: formatParamLabel(key),
      value: formatParamValue(key, value),
      category: getParamCategory(key),
      highlight: ['clip_skip', 'strength_recommended'].includes(key),
    }))
}, [parameters])
```

2. **Grouped display:**
```tsx
// Group by category
{Object.entries(groupBy(displayParams, 'category')).map(([category, params]) => (
  <div key={category}>
    <h4>{category}</h4>
    {params.map(p => <ParameterCard {...p} />)}
  </div>
))}
```

3. **HiRes section** (collapsed by default):
```tsx
{hasHiresParams && (
  <Collapsible title="HiRes Fix Settings">
    {hiresParams.map(...)}
  </Collapsible>
)}
```

---

#### Iteration 6.4: Backend API - PATCH /api/packs/{name} Unified ✅ COMPLETE (2026-02-01)

**Cíl:** Jeden endpoint pro všechny editovatelné části packu

**Nový unified PATCH endpoint:**

```python
@v2_packs_router.patch("/{pack_name}", response_model=PackDetail)
def update_pack(
    pack_name: str,
    update: PackUpdateRequest = Body(...),
    store=Depends(require_initialized),
):
    """
    Unified pack update endpoint.

    Supports partial updates - only provided fields are updated.
    """
    pack = store.get_pack(pack_name)

    # Update each provided field
    if update.description is not None:
        pack.description = update.description

    if update.parameters is not None:
        pack.parameters = merge_parameters(pack.parameters, update.parameters)

    if update.user_tags is not None:
        pack.user_tags = update.user_tags

    # ... more fields

    store.layout.save_pack(pack)
    return pack
```

**Request model:**
```python
class PackUpdateRequest(BaseModel):
    """Partial pack update request."""
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    user_tags: Optional[List[str]] = None
    cover_url: Optional[str] = None
    # Note: previews handled separately via upload endpoint

    class Config:
        extra = "forbid"  # Reject unknown fields
```

**Merge logic pro parameters:**
```python
def merge_parameters(
    existing: Optional[GenerationParameters],
    updates: Dict[str, Any]
) -> GenerationParameters:
    """
    Merge parameter updates into existing.

    - None value in updates = remove parameter
    - Missing key = keep existing
    - Value = update
    """
    base = existing.model_dump(exclude_none=True) if existing else {}

    for key, value in updates.items():
        if value is None:
            base.pop(key, None)  # Remove
        else:
            base[key] = value   # Update

    return GenerationParameters(**base)
```

---

#### Iteration 6.5: Backend API - Previews Management ✅ COMPLETE (2026-02-01)

**Cíl:** CRUD operace pro preview obrázky/videa

**Endpoints:**

```python
# List previews
@v2_packs_router.get("/{pack_name}/previews")
def list_previews(pack_name: str) -> List[PreviewInfo]:
    ...

# Upload new preview
@v2_packs_router.post("/{pack_name}/previews")
def upload_preview(
    pack_name: str,
    file: UploadFile,
    position: int = Query(default=-1),  # -1 = append
) -> PreviewInfo:
    ...

# Reorder previews
@v2_packs_router.patch("/{pack_name}/previews/order")
def reorder_previews(
    pack_name: str,
    order: List[str] = Body(...),  # List of filenames in new order
) -> List[PreviewInfo]:
    ...

# Set cover image
@v2_packs_router.patch("/{pack_name}/previews/{filename}/cover")
def set_cover_preview(pack_name: str, filename: str) -> PackDetail:
    ...

# Delete preview
@v2_packs_router.delete("/{pack_name}/previews/{filename}")
def delete_preview(pack_name: str, filename: str) -> dict:
    ...
```

**PreviewInfo model:**
```python
class PreviewInfo(BaseModel):
    filename: str
    media_type: Literal["image", "video", "unknown"]
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: Optional[int] = None
    is_cover: bool = False
    url: str  # Relative URL for frontend
```

---

#### Iteration 6.6: Frontend Integration ✅ COMPLETE (2026-02-01)

**Cíl:** Napojit UI modaly na nové API

**Changes:**

1. **usePackData.ts** - nové mutations:
```tsx
const updateDescriptionMutation = useMutation({
  mutationFn: (description: string) =>
    fetch(`/api/packs/${packName}`, {
      method: 'PATCH',
      body: JSON.stringify({ description }),
    }),
  onSuccess: () => queryClient.invalidateQueries(['pack', packName]),
})

const updatePreviewOrderMutation = useMutation({...})
const uploadPreviewMutation = useMutation({...})
const deletePreviewMutation = useMutation({...})
```

2. **DescriptionEditorModal** - real save:
```tsx
onSave={async (html) => {
  await updateDescription(html)
  closeModal('editDescription')
}}
```

3. **EditPreviewsModal** - real operations:
```tsx
onReorder={async (newOrder) => await updatePreviewOrder(newOrder)}
onUpload={async (files) => await uploadPreviews(files)}
onDelete={async (filename) => await deletePreview(filename)}
onSetCover={async (filename) => await setCoverPreview(filename)}
```

---

#### Iteration 6.7: Code Review & Tests ✅ COMPLETE (2026-02-01)

**Cíl:** ~~Odstranit duplicity~~ a přidat testy

**Architecture Note:**
Dvě verze `GenerationParameters` jsou ZÁMĚRNĚ oddělené:
- `src/core/models.py` - dataclass pro workflow generování
- `src/store/models.py` - Pydantic pro API/storage

Obě verze byly opraveny na `hires_fix: Optional[bool] = None`.
~~1. Odstranit `GenerationParameters` z `src/core/models.py` (ponechat jen v store/models.py)~~
~~2. Sjednotit importy v celém projektu~~

**Nové testy:**

Backend:
- `tests/unit/store/test_generation_parameters.py` (10 tests)
- `tests/unit/store/test_pack_update_api.py` (15 tests)
- `tests/unit/store/test_previews_api.py` (12 tests)

Frontend:
- `EditParametersModal.test.tsx` (8 tests)
- `PackParametersSection.test.tsx` (6 tests)
- `usePackData.test.tsx` - extend existing (10 tests)

---

#### Success Criteria Phase 6 ✅ ALL COMPLETE

- [x] `hires_fix: false` se neobjevuje v JSON pokud není explicitně nastaveno
- [x] EditParametersModal zobrazuje VŠECHNY parametry včetně custom
- [x] PackParametersSection zobrazuje VŠECHNY parametry dynamicky
- [x] Unified PATCH endpoint funguje pro description, parameters, tags
- [x] Preview CRUD API funguje kompletně (upload, delete, reorder, set cover)
- [x] Frontend modaly reálně ukládají data (usePackData mutations)
- [x] 528 testů projde (15 nových v test_generation_parameters.py)
- [x] Migrace existujících packů proběhne bez ztráty dat

---

### PHASES 1-6 COMPLETE ✅

Pack Edit & Modularization UI is now production ready:
- 40+ files, ~14,500 lines of new code
- Full modularity (sections, modals, hooks, plugins)
- Plugin system for extensibility
- Error boundaries at page and section level
- i18n support (en, cs)
- Comprehensive test coverage (528 tests)
- **Phase 6:** Ghost parameters fix, unified PATCH API, preview CRUD, frontend mutations

---

## Dependencies & Libraries

### Existující (už v projektu)
- `@tanstack/react-query` - data fetching
- `clsx` - className utility
- `lucide-react` - icons

### K přidání (pouze pokud potřeba)
- `react-markdown` - Markdown rendering
- `@dnd-kit/core` - drag & drop (pokud nestačí native)
- `monaco-editor` nebo `codemirror` - pro script editor (Install pack)

---

## Notes

- **UpdateService** už existuje - integrovat, nepřepisovat
- **Existující packs/ komponenty** (PackStorageStatus, etc.) - zachovat a integrovat
- **FullscreenMediaViewer** - nedotýkat se, použít as-is
- **Design** - premium feel, pro náročné designéry
- **Budoucnost** - připraveno na i18n, nové pack typy, pluginy
