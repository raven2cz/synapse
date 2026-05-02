# PLAN: Workflow Creation Wizard

**Version:** v0.1.0 (Draft)
**Status:** PLANNING
**Created:** 2026-02-03
**Author:** raven2cz + Claude Opus 4.5
**Branch:** TBD

---

## Executive Summary

Synapse potřebuje způsob, jak generovat workflows a konfigurační soubory pro různá UI (ComfyUI, Forge, A1111, SDnext, Fooocus, atd.) z pack parametrů. Tato feature musí:

1. **Zachovat pack.parameters** - AI-extracted parametry jsou cenné a nesmí být přepsány
2. **Umožnit výběr zdroje vizuálně** - uživatel vidí obrázky, ne dropdown s čísly
3. **Podporovat všechna UI** - modulární systém šablon pro různé formáty
4. **Ukládat výsledky do packu** - workflows se ukládají, ne jen exportují

---

## Motivation

### Proč NE "Apply to Pack Parameters"

Původně existovala feature pro aplikaci parametrů z preview obrázků do pack.parameters. Tato feature byla **ODSTRANĚNA** protože:

1. **Přepisuje AI-extracted parametry** - práce AI extrakce se ztratí
2. **Přepisuje AI Insights** - cenné informace jako usage_tips, compatibility zmizí
3. **Dropdown se 100 obrázky je nepoužitelný** - uživatel nevidí, který obrázek vybírá
4. **Merge logika je složitá a error-prone** - konflikty, ztráta dat

### Správný přístup: Workflow Wizard

Místo modifikace pack.parameters vytváříme **dedikovaný wizard**, který:

- **ČTEME** pack.parameters (nikdy nemodifikujeme)
- **Vizuálně zobrazuje** preview obrázky s jejich parametry
- **Generuje** workflow/config soubory podle šablon
- **Ukládá** výsledky do pack složky

---

## Use Cases

### Primary Use Case: Create Workflow for Specific Look

```
User: "Chci vytvořit ComfyUI workflow, který replikuje vzhled obrázku #3"

1. User otevře pack detail
2. Klikne "Create Workflow"
3. Wizard se otevře:
   - Vybere cílové UI (ComfyUI)
   - Vidí galerii preview obrázků
   - Klikne na obrázek #3
   - Vidí jeho parametry (cfg:8.5, steps:35, ...)
   - Může upravit parametry (upscaler, model, ...)
4. Klikne "Create"
5. Workflow je uložen do packu
```

### Secondary Use Case: Create Workflow from Default Parameters

```
User: "Chci workflow s doporučenými parametry od autora"

1. User otevře wizard
2. Vybere "Default (AI Recommended)" jako zdroj
3. Používají se pack.parameters (AI-extracted)
4. Workflow je vygenerován
```

---

## UI Design

### Wizard Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Create Workflow                                            [×] │
├─────────────────────────────────────────────────────────────────┤
│  Step 1: Select Target UI                                       │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ ComfyUI │  │  Forge  │  │  A1111  │  │ SDnext  │  ...      │
│  │   ✓     │  │         │  │         │  │         │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
│                                                                 │
│                                          [Cancel] [Next →]      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Create Workflow - ComfyUI                                  [×] │
├─────────────────────────────────────────────────────────────────┤
│  Step 2: Select Parameter Source                                │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ⭐ DEFAULT (AI Recommended)                    [Select] │   │
│  │    cfg: 7, steps: 25, sampler: DPM++ 2M Karras          │   │
│  │    Source: AI extraction from description               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Or select specific look from previews:                         │
│                                                                 │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │
│  │  [img] │  │  [img] │  │  [img] │  │  [img] │  │  [img] │   │
│  │   #1   │  │   #2   │  │ ✓ #3   │  │   #4   │  │   #5   │   │
│  │ cfg:7  │  │ cfg:8  │  │cfg:8.5 │  │ cfg:6  │  │ cfg:7  │   │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘   │
│                                                                 │
│  Selected: Image #3                                             │
│  cfg: 8.5, steps: 35, sampler: euler_a, seed: 12345            │
│                                                                 │
│                                   [← Back] [Cancel] [Next →]    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Create Workflow - ComfyUI                                  [×] │
├─────────────────────────────────────────────────────────────────┤
│  Step 3: Configure Workflow                                     │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Base Parameters (from Image #3):                               │
│  ├── CFG Scale:      [8.5    ] [-][+]                          │
│  ├── Steps:          [35     ] [-][+]                          │
│  ├── Sampler:        [euler_a        ▼]                        │
│  └── Seed:           [12345  ] [🎲 Random]                     │
│                                                                 │
│  Model Configuration:                                           │
│  ├── Checkpoint:     [Auto-detect from pack    ▼]              │
│  ├── LoRA:           [GhostMix_v2.0.safetensors]               │
│  └── LoRA Strength:  [1.0    ] [-][+]                          │
│                                                                 │
│  Upscaler (ComfyUI specific):                                   │
│  ├── Enable:         [✓]                                        │
│  ├── Model:          [4x-UltraSharp          ▼]                │
│  ├── Scale:          [2.0    ]                                  │
│  └── Denoise:        [0.4    ]                                  │
│                                                                 │
│  Workflow Name: [GhostMix_image3_style        ]                │
│                                                                 │
│                                   [← Back] [Cancel] [Create]    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### File Structure

```
pack/
├── pack.json                    # Metadata, parameters, AI insights (NEVER modified by wizard)
├── blobs/                       # Model files
├── previews/                    # Preview images
└── workflows/                   # NEW: Generated workflows
    ├── comfyui/
    │   ├── default.json         # Based on pack.parameters
    │   └── image3_style.json    # Based on image #3
    ├── forge/
    │   └── default.json
    └── a1111/
        └── default.json
```

### Template System

```
src/
└── workflow/
    ├── templates/               # Workflow templates per UI
    │   ├── comfyui/
    │   │   ├── base.json        # Base ComfyUI workflow structure
    │   │   ├── with_upscaler.json
    │   │   └── with_controlnet.json
    │   ├── forge/
    │   │   └── generation_params.json
    │   └── a1111/
    │       └── generation_params.txt
    │
    ├── generators/              # Template processors
    │   ├── base.py              # Abstract generator
    │   ├── comfyui.py           # ComfyUI workflow generator
    │   ├── forge.py             # Forge config generator
    │   └── a1111.py             # A1111 config generator
    │
    └── service.py               # Workflow generation service
```

### Generator Interface

```python
class WorkflowGenerator(ABC):
    """Abstract base for workflow generators."""

    @property
    @abstractmethod
    def ui_name(self) -> str:
        """Target UI name (e.g., 'ComfyUI')."""
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Output file extension (e.g., '.json')."""
        pass

    @abstractmethod
    def generate(
        self,
        pack: Pack,
        parameters: Dict[str, Any],
        options: GeneratorOptions,
    ) -> str:
        """Generate workflow content."""
        pass

    @abstractmethod
    def get_configurable_options(self) -> List[ConfigOption]:
        """Return list of UI-specific configurable options."""
        pass
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                       DATA FLOW                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐                                            │
│  │ pack.parameters │  ← AI-extracted (READ ONLY)                │
│  │ + AI Insights   │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │ Preview Images  │     │ Workflow Wizard │                   │
│  │ with meta       │────▶│                 │                   │
│  └─────────────────┘     │ 1. Select UI    │                   │
│                          │ 2. Select source│                   │
│                          │ 3. Configure    │                   │
│                          └────────┬────────┘                   │
│                                   │                             │
│                                   ▼                             │
│                          ┌─────────────────┐                   │
│                          │   Generator     │                   │
│                          │   (per UI)      │                   │
│                          └────────┬────────┘                   │
│                                   │                             │
│                                   ▼                             │
│                          ┌─────────────────┐                   │
│                          │ pack/workflows/ │  ← Saved output   │
│                          │ └── comfyui/    │                   │
│                          │     └── x.json  │                   │
│                          └─────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Supported UIs (Planned)

| UI | Format | Priority | Notes |
|----|--------|----------|-------|
| ComfyUI | JSON workflow | High | Node-based, complex |
| Forge | JSON/YAML config | High | Fork of A1111 |
| A1111 | TXT/JSON params | High | Most popular |
| SDnext | JSON config | Medium | Fork of A1111 |
| Fooocus | JSON preset | Medium | Simplified UI |
| InvokeAI | JSON config | Low | Different architecture |

---

## Implementation Phases

### Phase 1: Foundation
- [ ] Backend: Workflow storage in pack
- [ ] Backend: Basic generator interface
- [ ] Frontend: Wizard UI scaffold
- [ ] Frontend: UI selector step

### Phase 2: ComfyUI Generator
- [ ] ComfyUI template structure
- [ ] Parameter mapping (pack params → ComfyUI nodes)
- [ ] Basic workflow generation
- [ ] Save to pack/workflows/comfyui/

### Phase 3: Visual Source Selection
- [ ] Preview gallery in wizard
- [ ] Image parameter extraction
- [ ] Default vs Image source selection
- [ ] Parameter preview/comparison

### Phase 4: Configuration Step
- [ ] UI-specific options
- [ ] Upscaler configuration
- [ ] Model/LoRA configuration
- [ ] Workflow naming

### Phase 5: Additional UIs
- [ ] Forge generator
- [ ] A1111 generator
- [ ] SDnext generator
- [ ] Fooocus generator

### Phase 6: Advanced Features
- [ ] Workflow templates (presets)
- [ ] Workflow editing
- [ ] Workflow import
- [ ] Batch generation

---

## Domain Audit Findings (2026-05-02)

Z `plans/audits/DOMAIN-AUDIT.md` + `plans/audits/codex-domain-audit.md`. Tři klíčové
nálezy blokují Workflow Wizard implementaci.

### H6 [HIGH] — `AssetKind.CUSTOM_NODE` chybí v `UIKindMap`

**Finding:** `AssetKind.CUSTOM_NODE = "custom_node"` existuje v enumu (`models.py:42`),
ale **`UIKindMap` ho nemá jako pole** (`models.py:121-132`):

```python
class UIKindMap(BaseModel):
    checkpoint: str = "models/checkpoints"
    lora: str = "models/loras"
    vae: str = "models/vae"
    embedding: str = "models/embeddings"
    controlnet: str = "models/controlnet"
    upscaler: str = "models/upscale_models"
    clip: str = "models/clip"
    text_encoder: str = "models/text_encoders"
    diffusion_model: str = "models/diffusion_models"
    unet: str = "models/unet"
    # ❌ chybí: custom_node, workflow, unknown
```

Při `UIKindMap.get_path(AssetKind.CUSTOM_NODE)` se vrátí `None` (řádek 134-136 — `getattr`
fallback). `ViewBuilder.compute_plan()` pak má fallback na `models/{kind.value}`, takže
custom node se zapíše do `models/custom_node/<file>` místo do `custom_nodes/<repo>/`.

**Důsledek:** ComfyUI custom nodes po profile aktivaci nejsou v `custom_nodes/`, takže
ComfyUI je nenačte. Workflow používající custom node selhe s "Node not found" errorem.

**Recommendation:**

1. Přidat `custom_node: str = "custom_nodes"` (a varianty per UI) do `UIKindMap`.
2. ComfyUI custom nodes jsou ale **adresáře, ne soubory** — `UIKindMap` možná potřebuje
   layout type ("file" vs "directory") nebo separátní mapping.
3. Forge / A1111 custom_nodes neexistují (mají vlastní extension manager). Zvážit:
   `custom_node: Optional[str]` per UI nebo "not supported" hodnota.
4. Plus chybějící: `workflow`, `unknown` → triage dle Open Q #4.

**Severity:** HIGH (custom_node assety se rozbijí, jakmile je profile aktivuje)
**Refs:** `models.py:121`, `models.py:42`, `view_builder.py compute_plan()`
DOMAIN-AUDIT Section 10.

### M8 [MEDIUM] — Žádný `WORKFLOW` PackCategory

**Finding:** `PackCategory` enum má jen `EXTERNAL`, `CUSTOM`, `INSTALL`. Workflow imports
(point 4 z Release-1 roadmapy) nemají kam patřit. Volby:

**Volba A — nový `PackCategory.WORKFLOW`:**
- Vlastní lifecycle (workflow.json je první-class artifact, ne resource).
- Vlastní routing: `state/packs/<workflow-pack>/workflow.json` + assety v lock.
- Inventory rozliší workflow packy snadno.

**Volba B — `PackCategory.CUSTOM` s `imported_workflow_ref` facetem:**
- Workflow je jen "speciální custom pack" s flag-poli.
- Méně modelových změn, ale custom packs se rozdělí na "true custom" (manuálně vyrobený)
  vs "workflow-imported" (vyrobený import wizardem) — fragmentace sémantiky.

→ **Open Question #4 z auditu, čeká na vlastníka.**

**Severity:** MEDIUM (blokuje Phase 1 Workflow Wizard — neexistuje target shape)
**Refs:** `models.py PackCategory`, DOMAIN-AUDIT Section 9.

### M10 [MEDIUM] — `extra_model_paths.yaml` schema je YAML-string, ne modelovaný

**Finding:** `ui_attach.py` generuje `extra_model_paths.yaml` (ComfyUI specifický config)
manipulací string templatů. Není žádný typovaný `ExtraModelPathsConfig` model. Důsledek:

- Při změně schématu (ComfyUI 0.4.0+ změnil layout) je nutná manuální úprava generátoru.
- Žádná validace před zápisem — invalid YAML může rozbít ComfyUI.
- Žádný diff mechanismus — view rebuild přepíše uživatelské manuální změny.

**Recommendation:** Vytvořit `ExtraModelPathsConfig` Pydantic model + serializer
(`yaml.safe_dump`). Validovat před zápisem. Pro user manual sections použít
"BEGIN/END SYNAPSE" markery a zachovat content mimo ně.

**Severity:** MEDIUM (cross-cutting — nedotýká se Workflow Wizard přímo, ale view-build
flow se kterým Workflow Wizard musí integrovat)
**Refs:** `ui_attach.py`, DOMAIN-AUDIT Section 10.

### Související otázky pro vlastníka

- **Open Q #4** — Workflow imports → `PackCategory.WORKFLOW` (samostatný) nebo `CUSTOM`
  s facetem? **Musí být zodpovězeno před Phase 1.**
- **Open Q #9** — Custom nodes: store assets, install packs, nebo separate extension
  manager? Ovlivňuje H6 fix.

---

## Related Plans

- **PLAN-AI-Services.md** - AI parameter extraction (provides pack.parameters)
- **PLAN-Pack-Edit.md** - Pack editing features (Phase 7 obsoleted by this)
- **PLAN-Install-Packs.md** — související s Open Q #9 (custom nodes)
- **PLAN-Release-1-Roadmap.md** — distribuce všech audit findings
- **plans/audits/DOMAIN-AUDIT.md + codex-domain-audit.md** — full audit detail

---

## Open Questions

| Question | Status |
|----------|--------|
| How to handle LoRA/model paths per UI? | Open |
| Should workflows be editable in Synapse? | Open |
| How to handle UI version differences? | Open |
| Workflow validation before save? | Open |
| Workflow → PackCategory.WORKFLOW nebo CUSTOM s facetem? | Open (DOMAIN-AUDIT Open Q #4) |
| Custom nodes: store / install / extension manager? | Open (DOMAIN-AUDIT Open Q #9) |

---

*Created: 2026-02-03*
*Last Updated: 2026-02-03*
