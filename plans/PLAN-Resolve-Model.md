# PLAN: Resolve Model Redesign

**Version:** v0.11.0 — Phase 0+1+2+2.5+3+4 COMPLETE
**Status:** Phase 4 DOKONCENA — cleanup + validace hotovo
**Priority:** HIGH
**Created:** 2026-03-07
**Author:** raven2cz + Claude Opus 4.6
**Branch:** feat/resolve-model-redesign
**Reviews:** Gemini 3.1 (2x), Codex 5.4 (3x) — vsechny zapracovany + implementation map

---

## 1. Cil

Kompletni redesign systemu pro resolvovani model dependencies v packach.
Resolver slouzi pro VSECHNY typy dependencies (checkpoint, LoRA, VAE, controlnet,
embedding, upscaler) — ne jen base model.

Modely mohou byt na **Civitai, HuggingFace, nebo lokalne**. System prohledava
vsechny relevantni zdroje a preferuje konkretni signaly nad obecnymi.

---

## 2. Architekturni principy

### 2a. Suggest / Apply — jadro celeho systemu

Kazda resolve cesta (AI, manualni, lokalni, import) prochazi dvema kroky:

```
suggest_resolution(pack, dep_id, context)
    -> List[ResolutionCandidate]

apply_resolution(pack, dep_id, candidate_id)
    -> Jediny write path pres pack_service
```

**Pravidla:**
- AI NIKDY primo mutuje `pack.json` / `pack.lock.json`
- Kazdy kandidat ma stabilni `candidate_id` (UUID) — NE index
- Apply prijima `candidate_id`, ne pozici v seznamu (suggestions se mohou zmenit)
- Manualni resolve (Civitai/HF/Local tab) taky produkuje ResolutionCandidate
  a prochazi apply — zadna specialni cesta
- Import: auto-apply pokud JEDEN dominantni kandidat s confidence v TIER-1/TIER-2
  a zadny dalsi kandidat v rozmezi 0.15 confidence
- Import: vice kandidatu s podobnou confidence → mark "unresolved" pro UI

### 2b. Evidence Ladder — hierarchie dle KONKRETNOSTI

Klicovy princip: **cim konkretnejsi signal, tim vyssi priorita.**

Evidence je organizovana do **neprekryvajicich se confidence tier:**

```
TIER-1 (0.90 - 1.00) — Jednoznacna identifikace
  E1: Hash match         SHA256 nalezen na Civitai nebo HuggingFace

TIER-2 (0.75 - 0.89) — Presna identifikace z pouziti
  E2: Preview embedded   ComfyUI workflow / A1111 params z PNG chunks
  E3: Preview API meta   meta.Model / meta.resources z Civitai API

TIER-3 (0.50 - 0.74) — Stredni jistota
  E5: File metadata      Filename patterns, architecture detection
  E6: Configured aliases store.yaml mapping → Civitai nebo HF cil

TIER-4 (0.30 - 0.49) — Vodítko, ne resolve
  E4: Source metadata    Civitai baseModel ("SDXL", "SD 1.5") — kategorie, ne model
  (POZN: E4/E5 cislovani z historickych duvodu — E5 je konkretnejsi nez E4)

TIER-AI (0.50 - 0.89) — AI doplnuje, NIKDY neprebije TIER-1
  E7: AI analysis        Cross-reference, Civitai+HF search, reasoning
                         Confidence OMEZENA na max(TIER-2) = 0.89
                         AI NEMUZE prekrocit TIER-1 (hash match)
```

**Scoring pravidla:**
- Kazdy evidence item produkuje confidence STRIKTNE v ramci sveho tieru
- AI je omezena ceiling na 0.89 — nemuze prekrocit hash match
- Kombinovani vice signalu: **provenance grouping** (viz 2g)
- Konflikty (E2 rika jiny model nez E3) → snizit confidence obou, nabidnout oba kandidaty
- Auto-apply: kandidat musi byt v TIER-1 nebo TIER-2 a zadny jiny kandidat
  nesmi byt v rozmezi 0.15 confidence

### 2c. Provider Eligibility per AssetKind

NE "vzdy oba providery", ale **dle relevance** pro dany typ:

| AssetKind | Civitai search | HF search | HF hash lookup | Poznamka |
|-----------|---------------|-----------|----------------|----------|
| checkpoint | Yes | Yes | Yes (LFS pointer) | Zakladni modely casto na HF |
| lora | Yes | No | No | HF LoRA ekosystem je minimalni |
| vae | Yes | Yes | Limited | Nektere VAE na HF (kl-f8, mse) |
| controlnet | Yes | Yes | Limited | ControlNet repos na HF |
| embedding | Yes | No | No | Prevazne Civitai |
| upscaler | Yes | Limited | No | Nektere upscalery na HF |

**Pravidla:**
- `suggest_resolution()` prohledava JEN eligible providery pro dany AssetKind
- Zabranuje zbytecne latenci a sumu u nepodporovanych kombinaci
- Konfigurovatelne v `resolve_config.py` — rozsiritelne

### 2d. HuggingFace Discovery — realisticky design

HF discovery je fundamentalne OBTIZNEJSI nez Civitai:
- HF NEMA hash lookup API (jako Civitai `find_model_by_hash`)
- HF search API (`/api/models`) filtruje dle tags, ale NE dle SHA256
- Mnoho modelu je v single-file repos (ne diffusers), ktere `filter: "diffusers"` mine
- SHA256 je dostupna jen z LFS pointeru (nutno fetchnout pointer, ne cely soubor)

**Strategie pro HF resolve:**

1. **Filename-based search** (bez AI)
   - Z preview metadata: `ckpt_name: "illustriousXL_v060.safetensors"`
   - Vyhledat na HF API: `/api/models?search=illustriousXL`
   - Profiltrovat vysledky dle file extension a AssetKind
   - Nizsi confidence (TIER-3) — filename neni jednoznacny

2. **Known repos mapping** (bez AI)
   - Staticka mapa znamych modelu: `"SD 1.5" → runwayml/stable-diffusion-v1-5`
   - Soucasti `base_model_aliases` v store.yaml
   - Confidence dle presnosti shody

3. **AI-assisted discovery** (s avatarem)
   - AI je pro HF discovery NEJEFEKTIVNEJSI nastroj
   - Umi interpretovat: model cards, repo README, file strukturu
   - MCP tool `search_huggingface` (novy) + existujici znalosti
   - Pokud vice AI provideru dostupnych: zkusit vice (fallback chain)
   - AI muze cross-referencovat nalezeny HF repo s Civitai daty

4. **LFS pointer SHA256 verification** (post-discovery)
   - Po nalezeni kandidata: fetch LFS pointer (male HTTP request, ne cely model)
   - Extrahovat SHA256 z pointer souboru
   - Porovnat s hash z evidence → potvrdi/vyvrati kandidata
   - Zvysi confidence na TIER-1 pokud hash sedi

**Realita:** Pro nove/neznáme modely na HF je AI prakticky JEDINA cesta.
Deterministicke metody (search, aliases) pokryvaji jen známe modely.

### 2e. Preview Image Metadata — pravidla extrakce

Preview obrazky obsahuji nejpresnejsi data o skutecne pouzitem modelu.
Ale ne vsechna data jsou primo pouzitelna.

**Zdroj 1: Civitai API metadata (uz mame v sidecar .json!)**
- `meta.Model` / `meta.model_name` → checkpoint name
- `meta.resources[]` → seznam pouzitych modelu (checkpoint, LoRA, VAE...)
  s `name`, `type`, `weight`, nekdy `hash`

**Zdroj 2: PNG embedded metadata (vyzaduje parser)**
- A1111: `tEXt[parameters]` → "Model: dreamshaper_8, ..."
- ComfyUI: `tEXt[prompt]` → JSON workflow → `CheckpointLoaderSimple.ckpt_name`
- **POZOR:** Civitai CDN muze stripovat PNG chunks (nutne overit v Phase 0)

**Normalizace a filtrovani (C3, C6):**

```python
class PreviewModelHint:
    filename: str              # "illustriousXL_v060.safetensors"
    kind: Optional[AssetKind]  # checkpoint, lora, vae... (z ComfyUI node type)
    source_image: str          # Ktery preview image
    source_type: Literal["api_meta", "png_embedded"]
    raw_value: str             # Surova hodnota pro debug
    resolvable: bool           # False pokud privatni/neznamy format
```

**Pravidla:**
- **Kind-aware filtrovani:** Pokud resolvujeme checkpoint, pouzit JEN checkpoint hints
- **Provenance grouping:** E2 a E3 z TEHOZ obrazku = JEDEN evidence group.
  Pokud oba rikaji "illustriousXL_v060" → confidence se nepocita 2x,
  pouzije se VYSSI z nich (E2 > E3 v hierarchii)
- **Unresolvable stav:** Pokud filename nenalezen na zadnem provideru
  a nevyhovuje zadnemu aliasu → oznacit hint jako `resolvable: false`,
  nezapocitavat do confidence
- **Private/custom modely:** Filename jako "my_custom_merge_v3" pravdepodobne
  neexistuje remote → nizka confidence, neauto-applyovat

### 2f. Genericka resolve architektura

```
POST /api/packs/{name}/dependencies/{dep_id}/suggest
  Body: { include_ai?: bool, analyze_previews?: bool }
  -> { candidates: List[ResolutionCandidate], request_id: str }

POST /api/packs/{name}/dependencies/{dep_id}/apply
  Body: { candidate_id: str }   # UUID z suggest response
  -> Aktualizuje pack.json + pack.lock PRES pack_service

Pro manualni resolve (uzivatel vybral z Civitai/HF/Local tabu):
POST /api/packs/{name}/dependencies/{dep_id}/apply
  Body: { manual: { strategy, selector_data, canonical_source? } }
  -> Validace pres validation matrix → apply pres pack_service
  -> Manualni data TAKY prochazi validaci (min fields, kompatibilita)
```

**candidate_id vs candidate_index (C4):**
- Suggest vraci kandidaty s UUID `candidate_id`
- Backend si drzi candidates v krat. cache (TTL 5min, keyed by request_id)
- Apply pouziva `candidate_id` — stabilni i kdyz se suggestions mezi tim zmenily
- Pokud candidate_id expired → 409 Conflict, frontend znovu zavola suggest

### 2g. Provenance Grouping a Scoring

**Problem (C6):** E2 (PNG embedded) a E3 (API meta) z tehoz preview obrazku
popisuji STEJNOU skutecnost. Bez groupingu se stejna informace pocita 2x.

**Reseni:**

```python
class EvidenceGroup:
    """Evidence items z tehoz zdroje (napr. jeden preview image)."""
    provenance: str        # "preview:preview_001.png"
    items: List[EvidenceItem]
    combined_confidence: float  # max(item.confidence) v ramci skupiny

# Scoring:
# 1. Seskupit evidence dle provenance
# 2. Kazda skupina prispiva svym combined_confidence (max, ne soucet)
# 3. Nezavisle skupiny se kombinuji Noisy-OR:
#    P(correct) = 1 - product(1 - group.confidence for group in groups)
# 4. Final confidence JE OMEZENA tier stropem nejlepsiho evidence
#    (hash match → max 1.0, preview → max 0.89, alias → max 0.74)
```

**Priklad:**
- Preview image 1: E2=0.85 (ComfyUI workflow), E3=0.82 (API meta) → group confidence = 0.85
- Preview image 2: E3=0.78 (API meta jiny obrazek) → group confidence = 0.78
- Combined: 1 - (1-0.85)*(1-0.78) = 0.967 → ale ceiling = 0.89 (TIER-2) → final = 0.89
- Pokud pridame E1 hash match: ceiling = 1.0 → final = 0.967

### 2h. Cross-Kind Compatibility Validation (G2)

`apply_resolution()` validuje kompatibilitu resolvovane dependency s packem:

```python
COMPATIBILITY_RULES = {
    # base_model_category → compatible_categories
    "SD 1.5": {"SD 1.5"},
    "SDXL": {"SDXL", "Pony"},   # Pony je SDXL-based
    "Illustrious": {"SDXL", "Illustrious"},
    "Flux": {"Flux"},
    "SD 3.5": {"SD 3.5"},
}
```

**Pravidla:**
- Pokud pack.base_model = "SDXL" a resolvovana LoRA je pro "SD 1.5" → WARNING
- Warning neblokuje apply (uzivatel muze overridnout) ale zobrazi se v UI
- Pro checkpoint/base model resolve: zadna kompatibilita (je to sam base model)
- Mapping je konfigurovatelny v store.yaml

### 2i. Dual-source model pro local binding

```python
class DependencySelector(BaseModel):
    strategy: SelectorStrategy
    civitai: Optional[CivitaiSelector] = None
    huggingface: Optional[HuggingFaceSelector] = None
    base_model: Optional[str] = None
    url: Optional[str] = None
    local_path: Optional[str] = None
    constraints: Optional[SelectorConstraints] = None

    # NOVY: Kanonicky zdroj pro update system
    canonical_source: Optional[CanonicalSource] = None

class CanonicalSource(BaseModel):
    """Remote identity pro update tracking — nezavisle na install strategy."""
    provider: Literal["civitai", "huggingface"]
    model_id: Optional[int] = None      # Civitai
    version_id: Optional[int] = None    # Civitai
    file_id: Optional[int] = None       # Civitai
    repo_id: Optional[str] = None       # HuggingFace
    filename: Optional[str] = None
    subfolder: Optional[str] = None     # HF repos s vice subfolders (C9)
    revision: Optional[str] = None      # HF commit/tag
    sha256: Optional[str] = None
```

### 2j. ResolutionCandidate model

```python
class ResolutionCandidate(BaseModel):
    candidate_id: str                          # UUID — stabilni identifikator
    rank: int
    confidence: float                          # 0.0 - 1.0, v ramci tier stropu
    tier: int                                  # 1-4 (dle nejlepsi evidence)
    strategy: SelectorStrategy
    selector_data: Dict[str, Any]
    canonical_source: Optional[CanonicalSource] = None

    evidence_groups: List[EvidenceGroup]        # Provenance-grouped evidence
    display_name: str                          # "Illustrious XL v0.6"
    display_description: Optional[str] = None
    provider: Optional[Literal["civitai", "huggingface", "local"]] = None
    compatibility_warnings: List[str] = []     # Cross-kind warnings

class EvidenceGroup(BaseModel):
    provenance: str                            # "preview:001.png" / "hash" / "alias:SDXL"
    items: List[EvidenceItem]
    combined_confidence: float

class EvidenceItem(BaseModel):
    source: Literal["hash_match", "preview_embedded", "preview_api_meta",
                     "source_metadata", "file_metadata", "alias_config",
                     "ai_analysis"]
    description: str
    confidence: float
    raw_value: Optional[str] = None
```

---

## 3. Aktualni problemy (overene auditem)

| Problem | Zavaznost | Overeno | Popis |
|---------|-----------|---------|-------|
| MCP not passed to AvatarEngine | CRITICAL | task_service.py:319 | Engine BEZ `mcp_servers`. |
| Preview metadata nepouzita pro resolve | CRITICAL | — | `meta.Model`, `meta.resources[]` v sidecar JSON ignorovany. |
| Resolve je Civitai-centric | CRITICAL | — | Base modely casto na HF. HF search jen `diffusers` filter. |
| Zadny PNG metadata parser | HIGH | — | A1111/ComfyUI data v PNG se nectou. |
| AI nedostava strukturovana metadata | HIGH | pack_service.py:545 | Jen description text. |
| `model_tagging` se nevola pri importu | HIGH | pack_service.py:536-561 | |
| `pack.base_model` prepsano filename stemem | HIGH | api.py:2323 | Korupce dat. |
| Regex parsovani provider IDs z URL | HIGH | api.py:2400-2430 | Tichy fallback 0/"". |
| Mutace obchazeji pack_service | HIGH | api.py (15+ mist) | Prima layout.save_pack(). |
| Design checkpoint-centric | HIGH | BaseModelResolverModal | Vse hardcoded na checkpoint. |
| Chybi CanonicalSource | HIGH | models.py | Zadne remote identity pole. |
| SHA256 lokalnich modelu blokuje | HIGH | — | 2-6GB+ main thread. |
| Chybi cross-kind validace | MED | — | LoRA pro SD1.5 na SDXL pack = tichy problem. |
| TS union chybi 'incompatible' | MED | lib/avatar/api.ts:19 | |
| AI gate `enabled` misto `available` | MED | Layout.tsx:52 | |
| `model_tagging` validace odmitne hint-only | MED | model_tagging.py | |
| Jen CIVITAI_MODEL_LATEST updatable | MED | update_service.py:45-49 | |

---

## 4. Compatibility Matrix

| AssetKind | Local Folders | Civitai Filter | HF Eligible | Extensions | Updatable |
|-----------|--------------|----------------|-------------|------------|-----------|
| checkpoint | models/checkpoints | type=Checkpoint | Yes | .safetensors, .ckpt | Yes |
| lora | models/loras | type=LORA | No | .safetensors | Yes |
| vae | models/vae | type=VAE | Yes | .safetensors, .pt | Yes |
| controlnet | models/controlnet | type=Controlnet | Yes | .safetensors, .pth | Yes |
| embedding | models/embeddings | type=TextualInversion | No | .safetensors, .pt, .bin | Yes |
| upscaler | models/upscale_models | type=Upscaler | Limited | .pth, .safetensors | Yes |

---

## 5. Per-Strategy Validation Matrix

| Strategy | Min Selector Fields | Min Lock Fields | Installable | Updatable | Canonical Req |
|----------|-------------------|-----------------|-------------|-----------|---------------|
| CIVITAI_FILE | model_id, version_id, file_id | sha256, filename, size | Yes | No (pinned) | Auto-filled |
| CIVITAI_MODEL_LATEST | model_id | version_id, file_id, sha256 | Yes | Yes | Auto-filled |
| HUGGINGFACE_FILE | repo_id, filename | sha256, revision | Yes | No (pinned) | Auto-filled |
| LOCAL_FILE | local_path | sha256, mtime, size | N/A | Via canonical | Optional |
| URL_DOWNLOAD | url | sha256, filename | Yes | No | Optional |
| BASE_MODEL_HINT | base_model (alias) | — | Via alias | No | — |

**Pravidla:**
- `suggest_resolution()` vraci jen kandidaty splnujici Min Selector Fields
- `apply_resolution()` ODMITNE nesplnujici minimum + cross-kind check (2h)
- Zadne ticne fallbacky — kompletni data nebo error
- Alias cil muze byt Civitai NEBO HuggingFace repo

---

## 6. Import pipeline — cilovy stav

```
pack_service.py: import_civitai()
    |
    |-- 1. Fetch Civitai metadata
    |       -> model_id, version_id, files[], baseModel, tags, trainedWords
    |
    |-- 2. extract_parameters(description, metadata_context)
    |       -> gen params (sampler, steps, cfg...)
    |       -> metadata_context = { base_model, tags, trigger_words }
    |
    |-- 3. Analyze preview metadata (NOVY KROK)
    |       Pro kazdy preview image:
    |       a) Civitai API meta (sidecar .json): meta.Model, meta.resources[]
    |       b) PNG embedded meta (pokud CDN nezstripoval): A1111/ComfyUI
    |       c) Kind-aware filtrovani: jen relevant hints pro dany dep typ
    |       d) Provenance grouping: hints ze stejneho obrazku = 1 grupa
    |       -> List[PreviewModelHint]
    |
    |-- 4. suggest_resolution(pack, dep) pro kazdou dependency
    |       Evidence ladder (tier system):
    |
    |       TIER-1: E1 hash match (SHA256 z Civitai file → lookup Civitai + HF dle eligibility)
    |       TIER-2: E2/E3 preview metadata (s provenance grouping)
    |       TIER-3: E5 file metadata, E6 aliases (vcetne HF cilu)
    |       TIER-4: E4 source metadata (baseModel jako filtr)
    |       TIER-AI: E7 pokud available AND zadny TIER-1/2 kandidat:
    |           - model_tagging() pro hints
    |           - MCP: search_civitai, search_huggingface (dle eligibility)
    |           - Cross-reference, AI ceiling = 0.89
    |           - Pokud vice AI provideru: fallback chain
    |
    |       -> List[ResolutionCandidate] s evidence groups a confidence
    |
    |-- 5. Auto-apply / mark unresolved
    |       -> 1 kandidat v TIER-1/2 s >= 0.15 margin nad dalsim → auto-apply
    |       -> Vice kandidatu s podobnou confidence → "unresolved" pro UI
    |       -> Zadny kandidat → nechej dependency pro manual resolve
    |       -> Auto-apply VZDY pres pack_service write path
```

---

## 7. UI: DependencyResolverModal

```
DependencyResolverModal(dep_id, kind: AssetKind)
    |
    |-- Candidates list (vysledky suggest_resolution)
    |   |-- Serazene dle tier + confidence
    |   |-- USER-FRIENDLY confidence prezentace (NE raw cisla):
    |   |     ✅ "Exact match"       (TIER-1, 0.90+)
    |   |     🔵 "High confidence"   (TIER-2, 0.75+)
    |   |     ⚠️  "Possible match"   (TIER-3, 0.50+)
    |   |     ❓ "Hint — verify"     (TIER-4, 0.30+)
    |   |-- Evidence summary (human-readable): "Hash match on HF", "Found in preview metadata"
    |   |-- Provider icon (Civitai / HF / Local)
    |   |-- Compatibility warnings (zluty badge pokud cross-kind issue)
    |   |-- Akce u kazdeho kandidata:
    |   |     "Apply"              — resolve dependency (metadata only)
    |   |     "Apply & Download"   — resolve + spusti download v jednom kroku
    |   |     (obe akce vzdy dostupne — Apply pro planovani, Apply & Download pro okamzite pouziti)
    |
    |-- SMART TAB ORDERING:
    |   |-- Default aktivni tab = tab s nejlepsim kandidatem (ne vzdy AI)
    |   |-- Pokud candidates list uz ma TIER-1/2 → default = Candidates (zadny tab aktivni)
    |   |-- Pokud prazdne candidates → default = Preview Analysis (nejintuitivnejsi)
    |   |-- Taby serazeny dle relevance, ne fixne
    |
    |-- Tab: Preview Analysis
    |   |-- Grid cover/preview obrazku packu
    |   |-- Klik na obrazek → extrakce metadata:
    |   |     - Civitai API meta (sidecar .json)
    |   |     - PNG embedded meta (A1111/ComfyUI) pokud dostupne
    |   |-- Zobrazeni: model name, sampler, LoRAs, s kind oznacenim
    |   |-- "Use this model" → create candidate + apply (pres validaci)
    |   |-- Unresolvable hints sedi but oznaceny (nelze najit remote)
    |
    |-- Tab: AI Resolve (pokud avatar available)
    |   |-- "Analyze" pro AI hledani na Civitai + HF (dle eligibility)
    |   |-- Evidence chain zobrazeni
    |   |-- Vysledky se pridaji do candidates list s TIER-AI
    |   |-- Pokud vice AI provideru: "Try another provider" option
    |
    |-- Tab: Local Models
    |   |-- Scan dle AssetKind (compatibility matrix)
    |   |-- Background SHA256 s progress (hash cache ready z Phase 0)
    |   |-- AI dohledava canonical_source pokud available
    |
    |-- Tab: Civitai Search
    |   |-- Typed payloady (model_id, version_id, file_id)
    |   |-- Filtr dle kind z compatibility matrix
    |
    |-- Tab: HuggingFace Search (pokud HF eligible pro dany kind)
    |   |-- Typed payloady (repo_id, filename, subfolder, revision, sha256)
    |   |-- LFS pointer verification pro hash confirm

AI GATE:
  - useAvatarAvailable() hook: gate na `available === true`
  - AI tab NEZOBRAZENY pokud !available
  - HF tab NEZOBRAZENY pokud kind neni HF eligible

RESOLUTION != DOWNLOAD (obe cesty dostupne):
  - "Apply" = resolve only — produkuje metadata (DependencySelector + CanonicalSource)
    Uzivatel planuje download pozdeji (batch download, disk space management)
  - "Apply & Download" = resolve + okamzity download v jednom kroku
    Napojeni na existujici POST /api/packs/{pack}/download-asset
  - Download je VZDY dostupny i samostatne v deps sekci (pro jiz resolvovane deps)

INLINE RESOLVE (progressive disclosure):
  - V PackDependenciesSection: pokud suggest vrati TIER-1/2 kandidata,
    zobrazit INLINE: "Found: Illustrious XL v0.6 ✅ [Apply] [Apply & Download]"
  - Uzivatel NEMUSI otvirat modal pro jednoduche pripady
  - "More options..." link otvira plny DependencyResolverModal
  - Pokud zadny kandidat nebo nizka confidence → rovnou "Resolve..." tlacitko (modal)
```

---

## 8. Existujici implementace

### Frontend

| Soubor | Popis | Osud |
|--------|-------|------|
| `BaseModelResolverModal.tsx` (766 r.) | 3 taby, checkpoint-only | NAHRADIT |
| `PackDetailPage.tsx:160-224` | Query hooks pro resolve | REFAKTOR |
| `PackDependenciesSection.tsx` | Deps display + "Resolve" button | UPRAVIT |
| `GenerationDataPanel.tsx` | Zobrazuje meta | INSPIRACE pro Preview Analysis |

### Backend

| Soubor | Popis | Osud |
|--------|-------|------|
| `src/store/api.py:2255-2472` | /resolve-base-model, prima mutace | NAHRADIT |
| `src/store/dependency_resolver.py` | Protocol + 6 resolveru | ZACHOVAT, ROZSIRIT |
| `src/store/pack_service.py:536-561` | Import: jen extract_parameters | ROZSIRIT |
| `src/core/pack_builder.py:315-638` | Preview download, sidecar .json | ZACHOVAT |
| `src/store/update_service.py:45-49` | UPDATABLE_STRATEGIES | ROZSIRIT pozdeji |
| `apps/api/src/routers/browse.py:906-952` | HF search (jen diffusers filter) | ROZSIRIT |
| `apps/api/src/routers/browse.py:1203+` | Civitai search | ZACHOVAT |

### Avatar/AI

| Soubor | Popis | Osud |
|--------|-------|------|
| `src/avatar/tasks/model_tagging.py` | Skill generation-params | UPRAVIT validaci |
| `src/avatar/task_service.py:319` | Engine BEZ mcp_servers | OPRAVIT |
| `src/avatar/mcp/store_server.py` | 21 MCP tools (Civitai only hash lookup) | ROZSIRIT o HF |
| `src/avatar/routes.py:71-107` | /api/avatar/status (6 stavu) | ZACHOVAT |

### Data

| Soubor | Popis | Osud |
|--------|-------|------|
| `src/store/models.py:374-382` | DependencySelector | ROZSIRIT (canonical_source) |
| `src/store/models.py:267-307` | base_model_aliases (Civitai cile) | ROZSIRIT o HF |
| `lib/avatar/api.ts:19-28` | AvatarStatus chybi 'incompatible' | OPRAVIT |
| Preview sidecar .json | meta.Model, meta.resources | POUZIT pro resolve |

---

## 9. Bugy k oprave

### BUG 1: extractBaseModelHint() — regex na HTML description
**Soubor:** BaseModelResolverModal.tsx:123-140
**Fix:** Smazat. Pouzit pack.base_model + preview metadata.

### BUG 2: model_tagging se nevola pri importu
**Soubor:** pack_service.py:536-561
**Fix:** Pridat do import pipeline (evidence E7). Relaxovat validaci.

### BUG 3: pack.base_model prepsano filename stemem
**Soubor:** api.py:2286,2323
**Fix:** apply_resolution() NIKDY neprepise filename stemem.

### BUG 4: Regex parsovani provider IDs z URL
**Soubor:** api.py:2400-2430
**Fix:** Typed API, zadne parsovani z URL.

### BUG 5: TS union chybi 'incompatible'
**Soubor:** lib/avatar/api.ts:19
**Fix:** Pridat stav + engine_min_version.

### BUG 6: AI gate enabled misto available
**Soubor:** Layout.tsx:52
**Fix:** Gate na available === true.

---

## 10. Faze implementace

### Phase 0: Resolve infrastruktura + data model + calibration

**Cil:** Polozit vsechny zaklady. Overit predpoklady (CDN, confidence).

**Deliverables:**

**Data model:** ✅ IMPL
1. ✅ CanonicalSource model — models.py (s subfolder polem)
2. ✅ ResolutionCandidate + EvidenceGroup + EvidenceItem modely — `resolve_models.py`
3. ✅ PreviewModelHint model — `resolve_models.py`
4. ✅ Cross-kind compatibility rules config — `resolve_config.py`

**Konfigurace:** ✅ IMPL
5. ✅ Compatibility matrix — `src/store/resolve_config.py` (AssetKindConfig, TIER_CONFIGS, COMPATIBILITY_RULES)
6. ✅ Validation matrix — `src/store/resolve_validation.py` (STRATEGY_REQUIREMENTS, validate_candidate, validate_before_apply)
7. ⚠️ base_model_aliases — AliasEvidenceProvider cteni z store.yaml IMPL, config yaml vzor zatim ne

**Scoring:** ✅ IMPL
- ✅ `src/store/resolve_scoring.py` — Noisy-OR, provenance grouping, tier ceiling

**Evidence Providers:** ✅ IMPL
- ✅ `src/store/evidence_providers.py` — 6 provideru (Hash, Preview, File, Alias, Source, AI)
- ✅ EvidenceProvider Protocol s @runtime_checkable

**ResolveService:** ✅ IMPL
- ✅ `src/store/resolve_service.py` — suggest/apply orchestrace, candidate cache, lazy providers

**Hash cache:** ✅ IMPL
- ✅ `src/store/hash_cache.py` — persistent cache, mtime+size invalidace, compute_sha256

**Preview metadata extractor:** ✅ IMPL
8. ✅ `src/utils/preview_meta_extractor.py`
   - ✅ Cteni sidecar .json → meta.Model, meta.resources[] (s kind-aware filtrovanim)
   - ✅ PNG tEXt chunk parser (PIL) → A1111 params, ComfyUI workflow JSON
   - ✅ Target specificky ComfyUI nody: CheckpointLoaderSimple, LoraLoader, VAELoader
   - ✅ Vraci List[PreviewModelHint] s provenance tagy

**Calibration (C5):** ✅ PROVEDENO
9. ✅ **CDN metadata test** — `tests/calibration/test_cdn_png_metadata.py`
   - ✅ VYSLEDEK: CDN servíruje JPEG/WebP, NE originální PNG
   - ✅ E2 (PNG embedded) degradováno na "best effort"
   - ✅ E3 (API meta ze sidecar .json) je PRIMARY zdroj preview evidence
10. ⚠️ **Confidence calibration** — odlozeno na Phase 1 (vyzaduje import flow s realnymi daty)

**Hash cache zaklady (G1):** ✅ IMPL
11. ✅ Hash cache modul — `src/store/hash_cache.py`
    - ✅ Cache structure: `{ path: { sha256, mtime, size, computed_at } }`
    - ✅ Persistence: `data/registry/local_model_hashes.json`
    - ✅ Invalidace: mtime+size change → rehash
    - ⚠️ Async hash computation — zatim sync, async az Phase 3

**API:** ✅ IMPL+INTEG (Phase 1)
12. ✅ Suggest/Apply endpointy — 3 API endpointy v `api.py`: suggest-resolution, apply-resolution, apply-manual-resolution
13. ✅ Apply pres pack_service write path — `PackService.apply_dependency_resolution()` implementovano
    - ✅ `/resolve-base-model` oznaceno jako deprecated (OpenAPI `deprecated=True`)

**Phase 1 BUG fixy:** ✅ IMPL+INTEG
- ✅ BUG 1: `extractBaseModelHint()` smazano z `BaseModelResolverModal.tsx`, nahrazeno `pack.base_model` prop
- ✅ BUG 2: `model_tagging()` rule-based fallback bezi pri importu (merges tags, no MCP)
- ✅ BUG 3: `pack.base_model` NEVER overwritten with filename stem
- ✅ BUG 4: typed API IDs (model_id, version_id, repo_id) na `ResolveBaseModelRequest`

**Phase 1 Import pipeline:** ✅ IMPL+INTEG
- ✅ `SuggestOptions.preview_hints_override` — external hints z import pipeline
- ✅ `Store._post_import_resolve()` — post-import orchestrace (suggest E1-E6, auto-apply TIER-1/2 s margin 0.15)
- ✅ `Store.suggest_resolution()` / `apply_resolution()` — delegate metody na Store facade
- ✅ `Store.migrate_resolve_deps(dry_run=True/False)` — migration helper pro stare packy

**Gates:** ❌ Phase 2
14. ✅ `can_use_ai()` gate — useAvatarAvailable hook + AI tab visibility in DependencyResolverModal
15. ✅ Fix BUG 5: TS union + incompatible — AvatarStatus.state includes 'incompatible', engine_min_version added
16. ✅ Fix BUG 6: AI gate available — Layout.tsx gates on `available === true` instead of `enabled !== false`

**Testy:** ✅ 291 TESTU (+ 2 calibration external)
- ✅ Unit: modely (22), config (37), validation (26), scoring (23), hash_cache (15), evidence_providers (34), resolve_service (19), preview_extractor (27)
- ✅ Review fix testy (46): tier boundary gaps, zero-value validation, fingerprint stale warning, atomic cache write, scoring spec examples, suggest→apply round-trip, real Pydantic models
- ✅ Phase 1 Block A+B (13): BUG 3, BUG 4, PackService.apply_dependency_resolution, Store facade, API schemas
- ✅ Phase 1 Block C (16): SuggestOptions hints override, ResolveService suggest s override, post-import resolve orchestrace, Store delegate metody, auto-apply logika
- ✅ Phase 1 Block D (11): model_tagging rule-based, migration helper dry-run/apply/skip/error
- ✅ Calibration: CDN PNG metadata (2, external)
- ⚠️ Integration testy (import s evidence ladder) — az po Phase 1 review
- ⚠️ Smoke testy (kompletni import z Civitai s resolve) — az po Phase 1 review

**Phase 1 Review cyklus:** ✅ DOKONCEN
- ✅ Claude review: overeni vsech zmen, konzistence s planem
- ✅ Gemini 3.1 review: 8 issues — 1 opraven (missing request_id v migrate), 7 odlozeno/by-design
- ✅ Codex 5.4 review: 6 issues — 2 opraveny (post-import skip pinned deps, apply 4xx na failure), 4 odlozeno (SSRF=Phase 3, UI typed IDs=Phase 2, cache binding=Phase 2, HF race=pre-existing)

**Phase 1 Review fixy aplikovane:**
- Fix: `_post_import_resolve` preskakuje deps s jinou strategii nez BASE_MODEL_HINT (Codex 4)
- Fix: Apply endpointy vracejí 4xx při neúspěchu místo 200 (Codex 6)
- Fix: `migrate_resolve_deps` předává request_id do apply (Gemini 1)

**Review cyklus:** ✅ DOKONCEN
- ✅ Claude review: 7 issues nalezeno a opraveno (unused imports, import inside loop, cache abstraction leak)
- ✅ Gemini 3.1 review: 8 issues — 5 opraveno (tier gaps, FD leak, atomic write, broad except, validation), 3 odlozeno (thread safety=CLI app, search phase=Phase 1, TODO candidate_base_model=Phase 1)
- ✅ Codex 5.4 review: 6 issues — 3 opraveno (model_id=0, fingerprint stale, ensure_providers truthiness), 3 odlozeno (apply no-op=Phase 1, provider field access=Phase 1 adapter, key unification=Phase 1 search)
- ✅ Verified s realnymi Pydantic modely (Pack, PackDependency) — NE jen MagicMock

**Review fixy aplikovane:**
- Fix: tier boundary gaps — `>=` comparison misto range matching (Gemini 1.1)
- Fix: PIL Image.open() s context managerem — FD leak (Gemini 1.3)
- Fix: atomic cache write — temp file + replace() (Gemini 3.1)
- Fix: model_id=0 rejected validaci (Codex 3)
- Fix: fingerprint stale check v apply() (Codex 6)
- Fix: exc_info=True v provider error logu (Gemini 4.2)
- Fix: _ensure_providers truthiness bug — `is not None` misto `if self._providers:` (nalezeno testy)

### Phase 1: Import pipeline + bug fixy

**Cil:** Import z Civitai pouziva evidence ladder vcetne preview metadata.

**Deliverables:**

1. ✅ Fix BUG 1: `extractBaseModelHint()` smazano, nahrazeno `pack.base_model` prop
2. ✅ Fix BUG 3: apply nikdy neprepise base_model filename stemem
3. ✅ Fix BUG 4: typed API misto regex parsing (model_id, version_id, repo_id)

4. ✅ **Import pipeline integrace:**
   - ✅ Krok 3: analyze preview metadata (sidecar .json, dle calibration PNG tez)
   - ✅ Krok 4: suggest_resolution() s evidence ladder E1-E6
   - ✅ Krok 5: auto-apply dle tier pravidel (TIER-1/2, margin 0.15)
   - ⚠️ Konfigurovatelny threshold v store.yaml — az Phase 2 (hard-coded 0.15 margin)

5. ⚠️ Enriched AI context pro extract_parameters() — odlozeno (vyzaduje zmenu AvatarTaskService API)

6. ✅ Deprecate /resolve-base-model (OpenAPI deprecated=True, docstring warning)

7. ✅ Fix BUG 2: model_tagging() rule-based fallback bezi pri importu

8. ✅ **Migration helper** (C8): `Store.migrate_resolve_deps(dry_run=True/False)`
   - ✅ Projde packy s BASE_MODEL_HINT deps, spusti suggest
   - ✅ Dry-run mode → reportuje co by se zmenilo
   - ✅ Apply mode → auto-apply s tier/margin pravidly
   - ✅ Error handling, ambiguous/low_confidence detection

**Testy:** ✅ 40 NOVYCH TESTU
- ✅ Unit Block A+B (13): BUG 3, BUG 4, PackService integration, Store facade, API schemas
- ✅ Unit Block C (16): hints override, suggest s override, post-import resolve, delegates, auto-apply
- ✅ Unit Block D (11): model_tagging, migration helper
- ⚠️ Integration: import s evidence ladder — az po review
- ⚠️ Smoke: kompletni import z Civitai s resolve — az po review

### Phase 2: AI-enhanced resolution + UI

**Cil:** MCP-enabled AI dependency resolution. DependencyResolverModal s Preview Analysis tabem.

**DULEZITE:** Tato faze pridava AI vrstvu (E7) nad existujici E1-E6 evidence providers z Phase 0/1.
AI NIKDY neprebije hash match (TIER-1). AI ceiling = 0.89. Prompty MUSI byt v konfiguracnich
souborech (skills), NE hardcoded v Python kodu.

---

#### Phase 2 — Implementacni bloky

##### BLOK A: Skill soubory (konfigurace — prompty + domain knowledge)

Prompty pro AI ziji v `config/avatar/skills/*.md`. System je nacita dynamicky pres
`src/avatar/skills.py` → `load_skills(skill_names)` → predava do `AITask.build_system_prompt()`.
Uzivatel je muze editovat bez zmeny kodu. Custom override: `~/.synapse/avatar/custom-skills/`.

| # | Soubor | Stav | Popis |
|---|--------|------|-------|
| A1 | `config/avatar/skills/model-resolution.md` | ✅ HOTOVO (otestovano) | **HLAVNI prompt pro AI dependency resolution.** ~240 radku. Otestovano na 3 scenarich (Illustrious, RealVisXL, no-match). Review: 6 issues nalezeno a opraveno. |
| A2 | `config/avatar/skills/dependency-resolution.md` | ✅ Existuje (40 radku) | Obecny popis asset dependency modelu. Pouziva se jako reference knowledge. Bez zmen. |
| A3 | `config/avatar/skills/model-types.md` | ✅ Existuje (32 radku) | Base model architectures (SD1.5, SDXL, Flux, Pony). Reference knowledge. Bez zmen. |
| A4 | `config/avatar/skills/civitai-integration.md` | ✅ Existuje (70 radku) | Civitai API docs, CDN patterns. Reference knowledge. Bez zmen. |
| A5 | `config/avatar/skills/huggingface-integration.md` | ✅ HOTOVO (novy) | HF Hub API reference: search, tree, download URL, LFS hash, repo types, common repos, eligibility matrix. ~95 radku. |

**A1 — `model-resolution.md` — HOTOVO A OTESTOVANO**

Soubor (~240 radku) obsahuje:
1. **Ucel a task description** — co AI dela
2. **Available tools** — 4 MCP tools: `search_civitai`, `analyze_civitai_model`, `search_huggingface`, `find_model_by_hash`
3. **Input format** — presna struktura vstupu (PACK INFO, DEPENDENCY, EVIDENCE, PREVIEW HINTS)
4. **4-krokova search strategie** — Analyze → Civitai search → Civitai analyze (version IDs) → HF search → Evaluate
5. **Output JSON schema** — candidates[] + search_summary, field requirements per provider
6. **Confidence scoring** — base ranges + adjustments + ceiling rule `min(calc, 0.89)`
7. **Candidate deduplication** — same model on Civitai+HF = dva separate kandidaty
8. **10 pravidel** — ceiling, no hallucination, max 5 candidates, max 5 tool calls, etc.
9. **3 few-shot priklady** — strong match, no match (private), multiple candidates

**Testovano na 3 scenarich:**
- Illustrious LoRA → checkpoint: ✅ spravne nasel Illustrious XL
- RealVisXL portrait → checkpoint: ✅ V4.0 s version_id+file_id, SD1.5 mismatch omitted
- Private custom model: ✅ prazdny vysledek, zadna hallucinace

**Review nalezl 6 issues, vsechny opraveny:**
1. ✅ version_id/file_id null → pridano Step 2b (analyze_civitai_model)
2. ✅ search_summary chybi → povinne pole
3. ✅ confidence math v reasoning → explicitni aritmetika
4. ✅ ceiling po adjustments → `min(calc, 0.89)` as final step
5. ✅ architecture mismatch → omit rule
6. ✅ retry bounds → max 5 tool calls, max 2 retry variace

**A5 — `huggingface-integration.md` — NOVY SOUBOR**

Reference knowledge pro AI (~95 radku): HF Hub API (search, tree, resolve endpoints),
source identifier schema, repo types (single-file vs diffusers), file format detection,
LFS hash verification, common model repos tabulka, eligibility per AssetKind.

##### BLOK B: MCP tools (kod — nastroje, ktere AI pouziva)

AI pres MCP protokol vola nastroje registrovane v `src/avatar/mcp/store_server.py`.
Existujici MCP tools (21 kusu) jsou vsechny PLNE implementovane — zadne mocky.

| # | Tool | Stav | Popis |
|---|------|------|-------|
| B1 | `search_civitai` | ✅ Existuje | Civitai search. Overit zda output format vraci model_id, version_id, file_id (pro typed CivitaiSelector). |
| B2 | `search_huggingface` | ❌ NEEXISTUJE | **NOVY MCP tool.** HF API search, filename search, model card inspection, LFS pointer SHA256 fetch. Sirsi nez browse.py (ne jen diffusers filter). |
| B3 | `find_model_by_hash` | ✅ Existuje | Hash lookup. Overit zda podporuje HF LFS pointery vedle Civitai. |
| B4 | `suggest_asset_sources` | ✅ Existuje | Zdroje pro stazeni assetu. Muze byt uzitecne pro AI jako doplnkovy tool. |

**B2 — `search_huggingface` MUSI podporovat:**
- HF Hub API search (models endpoint) — ne jen diffusers pipeline filter
- Filename search v HF repo (tree endpoint) — pro single-file repo (safetensors, ckpt)
- Model card inspection (README.md) — base model info, tags
- LFS pointer SHA256 fetch — pro hash matching (E1 evidence na HF)
- Input: query string, optional filters (pipeline_tag, tags, library)
- Output: seznam vysledku s repo_id, filenames, sizes, hashes, tags
- Rate limiting a error handling

##### BLOK C: Avatar task system rozsireni (kod)

Existujici system: `AITask` ABC → `SKILL_NAMES` → skills loading → `build_system_prompt()` →
LLM volani → `parse_result()` → `validate_output()`. Registrace v `TaskRegistry`.
Engine vytvaren per-task v `AvatarTaskService._ensure_engine_for_task()`.

| # | Soubor | Stav | Zmena |
|---|--------|------|-------|
| C1 | `src/avatar/tasks/base.py` | ✅ HOTOVO | Pridano `needs_mcp: bool = False` a `timeout_s: int = 120` na `AITask` ABC |
| C2 | `src/avatar/task_service.py` | ✅ HOTOVO | V `_ensure_engine_for_task()` predava `mcp_servers` + `timeout=task.timeout_s` do AvatarEngine |
| C3 | `src/avatar/tasks/dependency_resolution.py` | ✅ HOTOVO | `DependencyResolutionTask` — 5 skill files, needs_mcp=True, timeout_s=180, confidence ceiling enforcement |
| C4 | `src/avatar/tasks/registry.py` | ✅ HOTOVO | `DependencyResolutionTask()` zaregistrovan v default registry |

**C3 — `DependencyResolutionTask` design:**

```python
class DependencyResolutionTask(AITask):
    task_type = "dependency_resolution"
    SKILL_NAMES = ("model-resolution", "dependency-resolution", "model-types", "civitai-integration", "huggingface-integration")
    needs_mcp = True          # AI pouziva search_civitai + analyze_civitai_model + search_huggingface + find_model_by_hash
    timeout_s = 180           # MCP volani jsou pomalejsi nez pure prompt

    def build_system_prompt(self, skills_content: str) -> str:
        # skills_content = concatenace VSECH 4 skill souboru (nactenych dynamicky)
        # Task NEPRIDAVA vlastni hardcoded prompt — VSECHEN prompt je ve skill souborech
        return skills_content

    def parse_result(self, raw_output: Dict) -> Dict:
        # Mapuje AI JSON output → strukturovany format pro AIEvidenceProvider:
        # - Extrahuje candidates[] z AI vystupu
        # - Pro kazdy: display_name, provider (civitai/hf), confidence, reasoning
        # - Pro civitai: model_id, version_id, file_id
        # - Pro hf: repo_id, filename
        # - Orizne confidence na max 0.89 (AI ceiling)
        ...

    def validate_output(self, output: Any) -> bool:
        # Overuje:
        # - output je dict s klicem "candidates" (list)
        # - Kazdy kandidat ma povinne fieldy: display_name, confidence, reasoning
        # - confidence je float v rozmezi 0.0-0.89
        # - provider je "civitai" | "huggingface" | None
        ...

    def get_fallback(self) -> None:
        return None  # Zadny fallback — E1-E6 evidence providers uz bezi nezavisle na AI
```

**KRITICKE:** `build_system_prompt()` NEMA pridavat vlastni hardcoded text. VSECHEN prompt
obsah musi byt v skill souborech (`config/avatar/skills/`), aby sel editovat bez zmeny kodu.
Jedina vyjimka: formatovani input dat (pack metadata) do promptu — to je v kodu, protoze
je to strukturovana data transformace, ne prompt engineering.

##### BLOK D: AIEvidenceProvider (kod — napojeni AI do resolve pipeline)

| # | Soubor | Stav | Zmena |
|---|--------|------|-------|
| D1 | `src/store/evidence_providers.py` | ✅ HOTOVO | `AIEvidenceProvider` prepsany: `_build_ai_input()` formatuje strukturovany text, `_ai_candidate_to_hit()` mapuje civitai+hf kandidaty na EvidenceHit, spravne pouziva `TaskResult` (ne raw dict) |
| D2 | `can_use_ai()` gate funkce | ⚠️ ODLOZENO na Phase 2 UI | Zatim `supports()` kontroluje jen `avatar is not None`. Full gate s config flagy az pri UI integraci (Block F). |

**D1 — AIEvidenceProvider opravy (vs. puvodni stub):**
- `execute_task()` prijima string, ne dict → `_build_ai_input(ctx)` formatuje PACK INFO + DEPENDENCY + PREVIEW HINTS
- Vysledek je `TaskResult` dataclass, ne dict → `task_result.success`, `task_result.output`
- Podpora Civitai i HuggingFace kandidatu → `_ai_candidate_to_hit()` routi dle `provider`
- CIVITAI_FILE strategie pokud mame `version_id` + `file_id`, jinak CIVITAI_MODEL_LATEST
- Dedup key: `civitai:{model_id}:{version_id}` nebo `hf:{repo_id}:{filename}`
- 18 unit testu v `tests/unit/store/test_evidence_providers.py`

##### BLOK E: ResolveService rozsireni (kod — AI merge do suggest pipeline)

| # | Soubor | Stav | Zmena |
|---|--------|------|-------|
| E1 | `src/store/resolve_service.py` | ✅ Existuje | **ROZSIRIT suggest():** Pokud `include_ai=True` a zadny TIER-1/2 kandidat z E1-E6, pustit AIEvidenceProvider. Merge + re-rank vysledky. |
| E2 | Auto-apply threshold | Hard-coded 0.15 | **PRESUNOUT** do `store.yaml` jako `resolve.auto_apply_margin: 0.15` |
| E3 | AI confidence ceiling | Hard-coded 0.89 | **DEFINOVAT** v `resolve_config.py` jako `AI_CONFIDENCE_CEILING = 0.89` |
| E4 | DRY auto-apply helper | Duplicitni logika | **KONSOLIDOVAT** `_post_import_resolve()` a `migrate_resolve_deps()` do sdilene helper funkce |
| E5 | Cache binding | Chybi | **PRIDAT** apply kontroluje `pack_name+dep_id` v cached candidates (Codex P1 #3) |

##### BLOK F: UI — DependencyResolverModal + inline resolve (frontend)

| # | Soubor | Stav | Zmena |
|---|--------|------|-------|
| F1 | `DependencyResolverModal.tsx` | ✅ IMPL+INTEG | **NOVY modal** — 5 tabu (Candidates, Preview, AI Resolve, Civitai, HF). CandidateCard, EvidenceGroups, confidence tiers. Integrovan v PackDetailPage. |
| F2 | `usePackData.ts` | ✅ IMPL+INTEG | **ROZSIRENO:** suggestResolution, applyResolution, applyAndDownload mutace. isSuggesting/isApplying/isApplyingAndDownloading states. |
| F3 | `PackDependenciesSection.tsx` | ✅ IMPL+INTEG | **ROZSIRENO:** onOpenDependencyResolver prop, per-asset resolve button opens modal (fallback to onResolvePack). |
| F4 | `PackDetailPage.tsx` | ✅ IMPL+INTEG | **ROZSIRENO:** Resolver state, handlers (open/suggest/apply/applyAndDownload), eager suggest, DependencyResolverModal JSX, useAvatarAvailable. |
| F5 | `useAvatarAvailable()` hook | ✅ IMPL+INTEG | **NOVY hook** — kontroluje avatarStatus.available via TanStack Query. Exportovan z hooks/index.ts. |
| F6 | TS typy pro resolve | ✅ IMPL+INTEG | **PRIDANO:** ResolutionCandidate, SuggestResult, ApplyResult, EvidenceItemInfo, EvidenceGroupInfo, ConfidenceLevel, HF_ELIGIBLE_KINDS do types.ts. |
| F7 | BUG 5: TS union + incompatible | ✅ OPRAVENO | AvatarStatus.state union rozsiren o 'incompatible', pridano engine_min_version field (lib/avatar/api.ts). |
| F8 | BUG 6: AI gate v UI | ✅ OPRAVENO | Layout.tsx: zmeneno z `enabled !== false` na `available === true`. Koment upraven. |
| F9 | HF tab | ✅ IMPL | DependencyResolverModal: HF tab ma `visible: HF_ELIGIBLE_KINDS.has(kind)` — skryty pro lora/embedding/upscaler. |

##### BLOK G: HF search backend rozsireni

| # | Soubor | Stav | Zmena |
|---|--------|------|-------|
| G1 | `src/clients/huggingface.py` nebo `browse.py` | ✅ Existuje (browse.py) | **ROZSIRIT:** Ne jen diffusers filter. Single-file repo support. |
| G2 | HF LFS pointer SHA256 | ❌ Chybi | Fetch SHA256 z HF LFS pointeru pro hash matching (E1 evidence na HF) |

##### BLOK H: Konfigurace a konstanty

| # | Co | Kde | Popis |
|---|-----|-----|-------|
| H1 | Provider eligibility matrix | `src/store/resolve_config.py` | Ktera AssetKind muze hledat na HF — tabulka z sekce 2c. Musi byt editovatelna (config, ne hardcoded). |
| H2 | AI confidence ceiling | `src/store/resolve_config.py` | `AI_CONFIDENCE_CEILING = 0.89` |
| H3 | Auto-apply margin | `store.yaml` | `resolve.auto_apply_margin: 0.15` |
| H4 | AI timeout | `src/avatar/tasks/dependency_resolution.py` | `timeout_s = 180` (konfigurovatelne v budoucnu pres avatar.yaml) |

---

#### Phase 2 — Poradi implementace (doporucene)

```
1. ✅ BLOK A: Skill soubory (model-resolution.md, huggingface-integration.md)
2. ✅ BLOK C: AITask rozsireni (base.py, task_service.py, dependency_resolution.py, registry.py)
3. ✅ BLOK B: search_huggingface MCP tool + fix analyze_civitai_model
4. ✅ BLOK D: AIEvidenceProvider rewrite (_build_ai_input, _ai_candidate_to_hit, HF support)
5. ✅ BLOK E: ResolveService — E1 uz fungovalo (include_ai flag + provider registration). E2-E5 refinementy odlozeny.
6. ✅ BLOK H: Konfigurace a konstanty — AI_CONFIDENCE_CEILING, HF_ELIGIBLE_KINDS, AUTO_APPLY_MARGIN v resolve_config.py
7. ✅ BLOK G: HF backend rozsireni — search_huggingface MCP tool hotov, _hf_hash_lookup() v evidence_providers.py
8. ✅ BLOK F: UI — DependencyResolverModal + inline resolve (5-tab modal, 3 mutace, eager suggest)
```

**STAV:** PHASE 2 KOMPLETNI. Všechny bloky A-H hotovy. Celý chain funguje:
`ResolveService.suggest(include_ai=True)` → `AIEvidenceProvider._build_ai_input()` →
`AvatarTaskService.execute_task("dependency_resolution", ...)` → skills loaded →
AvatarEngine + MCP tools → `DependencyResolutionTask.parse_result()` → confidence ceiling →
`_ai_candidate_to_hit()` (civitai/hf) → `_merge_and_score()` → `SuggestResult`.

---

#### Phase 2 — Testy (aktualni stav)

| Typ | Pocet | Soubor |
|-----|-------|--------|
| Unit: DependencyResolutionTask | 45 | `tests/unit/avatar/test_dependency_resolution_task.py` |
| Unit: AIEvidenceProvider | 18 | `tests/unit/store/test_evidence_providers.py` (AI section) |
| Unit: TaskRegistry | 59 total (3 new) | `tests/unit/avatar/test_task_registry.py` |
| Integration: AI resolve chain | 23 | `tests/integration/test_ai_resolve_integration.py` |
| Smoke: ResolveService+AI | 7 | `tests/integration/test_ai_resolve_smoke.py` |

**Celkem Phase 2 unit/integ:** 93 testu pro AI resolution + 17 novych (config, evidence, MCP fallback).
**E2E real provider testy:** 15 testu (5 scenaru × 3 providery), 100% PASS.
Viz detailni test plan v sekci 11o

#### Phase 2 — Review & Final Integration (2026-03-08)

**Backend (Blocks G, H):**
- ✅ `HF_ELIGIBLE_KINDS` frozenset, `AUTO_APPLY_MARGIN = 0.15` in resolve_config.py
- ✅ AI_CONFIDENCE_CEILING deduplicated (dependency_resolution.py re-exports from resolve_config.py)
- ✅ `_hf_hash_lookup()` in evidence_providers.py — verifies HF LFS SHA256 against known hash
- ✅ 15 new config+evidence tests (8 HF eligibility, 3 auto-apply margin, 4 HF hash lookup)

**Frontend (Block F):**
- ✅ DependencyResolverModal.tsx — 5-tab modal (Candidates, Preview, AI Resolve, Civitai, HF)
- ✅ usePackData.ts — 3 mutations (suggest/apply/applyAndDownload) + error toasts
- ✅ useAvatarAvailable.ts hook — gates AI tab on `available === true`
- ✅ PackDependenciesSection.tsx — per-asset resolve button → opens DependencyResolverModal
- ✅ PackDetailPage.tsx — orchestrator state, handlers, eager suggest with stale-response guard
- ✅ BUG 5 (TS union + incompatible), BUG 6 (AI gate available vs enabled)
- ✅ HF tab visibility gated on HF_ELIGIBLE_KINDS
- ✅ pack-data-invalidation.test.ts updated (2 new mutations categorized)

**3-Review Cycle:**
- **Claude:** Fixed hook ordering bug (openModal/closeModal before resolver handlers)
- **Gemini:** Found race condition in eager suggest, missing catch handlers, nested buttons — all fixed
- **Codex:** Found nested interactive controls in CandidateCard, unhandled AI resolve rejection — all fixed
- **Testy:** 2096 backend passed (8 pre-existing failures), 1141 frontend passed, 0 new failures

**Meilisearch Integration (2026-03-08):**
- ✅ `CivitaiClient.search_meilisearch()` — fulltext search pres Civitai Meilisearch index
  - Civitai REST API (`/api/v1/models?query=...`) nevraci mnoho modelu (Illustrious-XL, Detail Tweaker)
  - Meilisearch (`search-new.civitai.com/multi-search`) je stejny index jako Civitai web UI — najde vse
  - Token konfigurovatelny pres `CIVITAI_MEILISEARCH_TOKEN` env var (public token, ne secret)
- ✅ MCP `search_civitai` tool: Meilisearch-first, REST API fallback
- ✅ Defensive types handling v `search_models()` (string + list input)
- ✅ 2 nove unit testy: meilisearch_success_skips_rest, meilisearch_failure_falls_back_to_rest

**Claude Permission Fix (2026-03-08):**
- ✅ `task_service.py` predava `permission_mode`/`allowed_tools` z avatar.yaml do AvatarEngine kwargs
  - Root cause: AvatarEngine bez config objektu pouziva kwargs, task_service je nepredaval
  - Claude defaultoval na `acceptEdits` → odmital MCP tools bez interaktivniho potvrzeni
- ✅ `avatar.yaml.example` aktualizovan: `permission_mode: bypassPermissions` + `allowed_tools` s MCP wildcard
- ✅ `~/.synapse/store/state/avatar.yaml` aktualizovan

**E2E Testy s realnymi AI providery (2026-03-08):**
- ✅ `tests/e2e_resolve_real.py` — 5 scenaru × 2 providery (gemini, codex) = 10 testu
- ✅ `tests/e2e_resolve_claude.py` — 5 scenaru × claude (standalone, nelze v Claude Code)
- Scenare: SDXL Base, Illustrious XL, Flux.1 Dev, Detail Tweaker LoRA, Pony V6 XL

**Finalni E2E vysledky — 15/15 PASS (100%):**

| Scenario | Gemini 3 Pro | Codex 5.3 | Claude Opus 4.6 |
|---|---|---|---|
| SDXL Base Checkpoint | PASS 89% (Civitai+HF) | PASS 89% (Civitai+HF) | PASS 89% (Civitai+HF) |
| Illustrious XL | PASS 80% (Civitai) | PASS 79% (Civitai) | PASS 75% (Civitai) |
| Flux.1 Dev | PASS 89% (Civitai+HF) | PASS 87% (HF) | PASS 89% (HF) |
| Detail Tweaker LoRA | PASS 89% (Civitai) | PASS 87% (Civitai) | PASS 89% (Civitai) |
| Pony V6 XL | PASS 88% (Civitai+HF) | PASS 89% (Civitai+HF) | PASS 89% (Civitai+HF) |

**Code Review (post-Meilisearch):**
- 0 Critical, 3 Medium, 8 Low issues nalezeny
- Medium: token → env var (opraveno), nsfwLevel parsing (opraveno), limit bounds (opraveno)
- Low: security warning v example config (opraveno), fallback komentare (opraveno), 2 nove testy (opraveno)
- 1988 backend tests passed, 0 failed

**Phase 2 STAV: ✅ KOMPLETNI** — commit `4958309`, branch `feat/resolve-model-redesign`

---

#### Phase 2.5: Preview Enrichment + Bug Fixes (2026-03-09)

**Cil:** Odstranit `model_id=0` placeholder gap — preview/file hinty ted resolvuji skutecne Civitai IDs.

**Problem:**
- `PreviewMetaEvidenceProvider` a `FileMetaEvidenceProvider` vytvarily kandidaty s `model_id=0`
- `resolve_validation.py` odmitalo `model_id=0` jako "invalid zero value"
- `_post_import_resolve()` nekontrolovala `ApplyResult.success` — false "Auto-applied" log
- Celkove: preview hinty nikdy nevedly k realnym downloadable kandidatum bez AI provideru

**Reseni: Enrichment v PreviewMetaEvidenceProvider** (stejny pattern jako HashEvidenceProvider):
1. ✅ Provider prijima `pack_service_getter` → pristup k Civitai klientu
2. ✅ Hash lookup: `civitai.get_model_by_hash(hint.hash)` → realne `model_id/version_id/file_id`
3. ✅ Name search fallback: `search_meilisearch(stem)` → name+kind matching → `get_model()` pro latest
4. ✅ Hash cache pro deduplikaci API callu v ramci jednoho `suggest()`
5. ✅ Confidence boost +0.05 pro enriched kandidaty
6. ✅ Backward compatible: bez `pack_service_getter` funguje v placeholder modu

**Bug fixy:**
- ✅ `_post_import_resolve()` ted kontroluje `apply_result.success` + predava `request_id`
- ✅ Apply failure se loguje jako warning, ne false success

**Zmeny:**
| Soubor | Zmena |
|--------|-------|
| `src/store/evidence_providers.py` | PreviewMetaEvidenceProvider enrichment (hash+name), helpers |
| `src/store/resolve_service.py:160` | Wiring: `PreviewMetaEvidenceProvider(ps_getter)` |
| `src/store/__init__.py:635` | Bug fix: check `apply_result.success` |
| `tests/unit/store/test_evidence_providers.py` | +10 testu (TestPreviewMetaEnrichment) |
| `tests/unit/store/test_phase1_import_pipeline.py` | +1 test, 1 fix |

**Testy:** 1827 backend + 1153 frontend = 2980 passed, 0 failed

**Identifikace problemu:** Analyze Claude + Explore agent + Codex 5.4 (3 nezavisle analyzy)

---

### Phase 3: Local Resolve — import lokalnich souboru ✅ KOMPLETNI

**Cil:** Uzivatel muze resolvovat dependenci z lokalniho souboru misto stahovani.
Soubor se hashuje, zkopiruje do blob store, a enrichuje se metadata z Civitai/HF.

**Stav:** ✅ KOMPLETNI — commit `6f8b485` (2026-03-10), branch `feat/resolve-model-redesign`

**Tri scenare:**

**A) Dep uz ma remote zdroj (Civitai/HF):** ✅ IMPL+INTEG
- Dep je resolved na civitai_file(model_id=123, sha256=abc...) ale soubor neni stazeny
- Uzivatel otevre Local tab, zvoli slozku
- System porovna SHA256/filename → doporuci konkretni soubor ("tohle vypada jako ten spravny")
- Uzivatel potvrdi → copy do blob store, dep resolvovana
- **Implementace:** `LocalFileService.recommend()` s confidence scoring:
  sha256_exact (1.0) > filename_exact (0.85) > filename_stem (0.6) > none (0.0)

**B) Dep nema remote zdroj, enrichment pres hash:** ✅ IMPL+INTEG
- Custom pack, dep ma jen nazev (napr. `juggernaut_xl.safetensors`)
- Uzivatel vybere soubor → system hashuje (SHA256)
- Hash → Civitai by-hash API → najde model_id, version_id, canonical_source
- ~~Hash → HuggingFace lookup (pokud Civitai nevi)~~ (HF enrichment az Phase 4)
- Dep je plne enrichovana + soubor v blob store
- **Overeno na realnych datech:** 4 soubory (add-detail-xl, ponyDiffusionV6XL, frostbitev2, pixel_art_style) — vsechny uspesne enrichovany z Civitai

**C) Hash nic nenajde, enrichment pres jmeno:** ✅ IMPL+INTEG
- Hash nenajde nic na Civitai ani HF
- Filename stem (napr. `juggernaut_xl_v9` → "juggernaut xl v9") → name search na Civitai (Meilisearch)
- Pokud najde → doplni canonical_source, metadata
- Pokud nenajde → ulozi jako LOCAL_FILE strategie s display_name z filename
- Vzdy se ulozi aspon: sha256, file size, display_name z filename
- **Overeno na realnych datech:** ltx-2-19b-lora-camera-control-dolly-left.safetensors → filename_only fallback

**Deliverables:**

1. ✅ **Backend: Directory browsing** — `GET /api/store/browse-local`
   - Parametry: `path` (adresar), `kind` (AssetKind pro filtraci pripon)
   - Vraci seznam souboru: name, size, mtime, extension, cached_hash
   - Security: path traversal prevence, allowlisted extensions (.safetensors, .ckpt, .pt, .bin, .pth, .onnx, .sft, .gguf)
   - Regular file check (no symlinks, no devices)
   - **Implementace:** `store_router.get("/browse-local")` → `LocalFileService.browse()`

2. ✅ **Backend: Import local file** — `POST /api/packs/{pack_name}/import-local`
   - Parametry: pack_name, dep_id, file_path, skip_enrichment
   - Flow: validate path → SHA256 hash (s cache) → atomic copy do blob store → enrich → apply resolution
   - Enrichment pipeline: `enrich_file()` → hash lookup (Civitai) → name search (Meilisearch) → filename_only fallback
   - Background import: `ThreadPoolExecutor(max_workers=2)`, `_cleanup_old_imports(MAX_IMPORT_HISTORY=50)`
   - Progress polling: `GET /api/store/imports/{import_id}` (1000ms interval)
   - **Implementace:** `v2_packs_router.post("/{pack_name}/import-local")` → `_active_imports` dict + polling

3. ✅ **Backend: Smart file recommendation** — `GET /api/packs/{pack_name}/recommend-local`
   - Parametry: pack_name, dep_id, directory
   - Pokud dep ma known SHA256 nebo filename → scan adresar a doporucit match
   - Poradi: exact SHA256 match (1.0) > filename exact (0.85) > filename stem (0.6) > none (0.0)
   - **Implementace:** `v2_packs_router.get("/{pack_name}/recommend-local")` → `LocalFileService.recommend()`

4. ✅ **Frontend: Local File tab v DependencyResolverModal**
   - 4 stavy: browse → importing → success → error
   - Browse: directory input, recent paths (localStorage), file listing s recommendations
   - Importing: progress bar s gradient, stage indicators (hashing → copying → enriching → applying)
   - Success: checkmark, file details, enrichment info (civitai_hash / civitai_name / filename_only)
   - Error: error message s retry
   - **Implementace:** `LocalResolveTab.tsx` (~530 radku), integrovano v `DependencyResolverModal.tsx`

5. ✅ **Security hardening:**
   - Path validace: absolute path required, no `..` traversal, resolved path check
   - Extension allowlist: `.safetensors`, `.ckpt`, `.pt`, `.bin`, `.pth`, `.onnx`, `.sft`, `.gguf`
   - Regular file check (stat.S_ISREG) — no symlinks, directories, devices
   - TOCTOU prevence: fstat na otevreny handle
   - Atomic blob copy: UUID-based `.tmp` → `os.replace()` (race condition safe)
   - Copy strategies: reflink (zero-copy, Btrfs/XFS) → hardlink (same FS) → shutil.copy2 (fallback)

6. ✅ **Shared enrichment module** — `src/store/enrichment.py` (267 radku)
   - `enrich_by_hash()` — SHA256 lookup na Civitai (get_model_by_hash)
   - `enrich_by_name()` — Filename stem search na Civitai (Meilisearch-first, REST fallback)
   - `enrich_file()` — Pipeline: hash → name → filename_only fallback (vzdy vraci vysledek)
   - `extract_stem()` — Clean model name z filename
   - Helpers: `_normalize_name()`, `_kind_matches_civitai_type()`, `_extract_file_id_from_version()`, `_get_latest_version()`
   - Sdileno s `PreviewMetaEvidenceProvider` (Phase 2.5) a `LocalFileService` (Phase 3)

**Store integrace:** ✅
- `LocalFileService` jako 10. sluzba v `Store.__init__()` (DI pattern)
- Pristup k `HashCache`, `BlobStore`, `PackService` pres gettery (lazy, no circular deps)
- `_apply_resolution()` buduje `ManualResolveData` dle enrichment strategie (CIVITAI_FILE / HUGGINGFACE_FILE / LOCAL_FILE)
- Deleguje na `resolve_service.apply_manual()` nebo `pack_service.apply_dependency_resolution()` (fallback)

**Testy:** ✅ 57 NOVYCH TESTU
- Unit enrichment (26): `tests/unit/store/test_enrichment.py`
  - TestExtractStem (7), TestNormalizeName (3), TestKindMatchesCivitaiType (6)
  - TestEnrichByHash (4), TestEnrichByName (3), TestEnrichFile (3)
- Unit local_file_service (31): `tests/unit/store/test_local_file_service.py`
  - TestValidatePath (9), TestValidateDirectory (5), TestBrowse (7)
  - TestRecommend (5), TestImportFile (4), TestEnrichment (1)

**Real-world testovani (2026-03-10):** ✅ OVERENO
- Legacy repo: `/home/box/.synapse/repo-legacy/` (492 GB, 94 souboru)
- Browse checkpoints: 7 souboru, Browse loras: 19 souboru
- Import `tifa_lockhart_offset.safetensors` (302 MB) — skip_enrichment=True → OK
- Import `add-detail-xl.safetensors` (218 MB) — civitai_hash match → model 122359 "Detail Tweaker XL"
- Import `ponyDiffusionV6XL.safetensors` (6.4 GB) — civitai_hash match → model 257749 "Pony Diffusion V6 XL" (6.7s)
- Import `frostbitev2_Illu_dwnsty.safetensors` (109 MB) — civitai_hash match → model 947081
- Import `ltx-2-19b-lora-camera-control-dolly-left.safetensors` (312 MB) — filename_only fallback (ne na Civitai)
- API flow: browse-local (200 OK), recommend-local (200 OK), import-local + polling (completed)
- `pixel_art_style_z_image_turbo.safetensors` — API import+polling: civitai_hash → model 1770073

**Bug nalezeny a opraveny behem implementace:**
- `v2_store_router` neexistoval v `api.py` → opraveno na `store_router` (3 vyskyty)
- `CanonicalSource(type="civitai")` → `provider="civitai"` (Pydantic field je `provider`, ne `type`)
- Test `test_rejects_directory` — directory fails on extension check first, not regular file check

**Review:** ✅ 2 kola
- **Round 1:** Memory leak (MAX_IMPORT_HISTORY), unbounded threads (ThreadPoolExecutor), race condition (atomic write), polling too fast (500→1000ms)
- **Round 2:** Deterministic tmp collision (UUID-based), polling double-click guard, model_dump() false positive

**Zmeny v souborech:**
| Soubor | Zmena |
|--------|-------|
| `src/store/enrichment.py` | **NOVY** — shared enrichment module (267 radku) |
| `src/store/local_file_service.py` | **NOVY** — LocalFileService: browse, recommend, import_file (~450 radku) |
| `src/store/__init__.py` | +HashCache init, +LocalFileService jako 10. sluzba |
| `src/store/api.py` | +5 endpointu (browse-local, recommend-local, import-local, imports, imports/{id}), ThreadPoolExecutor |
| `apps/web/.../modals/LocalResolveTab.tsx` | **NOVY** — Local File tab s 4 stavy (~530 radku) |
| `apps/web/.../modals/DependencyResolverModal.tsx` | +Local File tab integrace, +HardDrive icon |
| `apps/web/.../types.ts` | +LocalFileInfo, FileRecommendation, BrowseLocalResult, LocalImportStatus |
| `apps/web/.../constants.ts` | +localBrowse, localRecommend, localImport query keys |
| `plans/SPEC-Local-Resolve.md` | **NOVY** — full specifikace (architektura, security, API, UX, testy) |
| `tests/unit/store/test_enrichment.py` | **NOVY** — 26 testu |
| `tests/unit/store/test_local_file_service.py` | **NOVY** — 31 testu |

**Celkem testy po Phase 3:** 2131 backend + frontend passed, 0 failed

### Phase 4: Provider polish + download + cleanup

**Cil:** Typed payloady, cleanup, download napojeni.
**Status:** ✅ DOKONCENO (2026-03-10) — 2 commity: `8b0b910`, `6cf7db1`

**Deliverables:**

1. ✅ Typed provider payloady end-to-end — odmitat nekompletni
   - `apply-manual-resolution` endpoint rejects incomplete payloads per strategy (422)
   - Civitai: requires `civitai_model_id` + `civitai_version_id`
   - HuggingFace: requires `hf_repo_id` + `hf_filename`
   - Local: requires `local_path`
   - URL: requires `url`
2. ✅ Audit resolve endpointu — validace vstupu
   - `suggest-resolution`: validates dep_id exists in pack (404), max_candidates capped at 50
   - `apply-resolution`: validates pack exists (404)
   - `apply_manual()`: loads pack for cross-kind validation (was missing)
3. ~~Resolution → Download napojeni~~ — DEFERRED (download system uz funguje pres existing `download-asset` endpoint, neni treba nove napojeni)
4. ✅ Cleanup: smazat stary endpoint /resolve-base-model, BaseModelResolverModal, ~~extractBaseModelHint~~ (uz smazano)
   - Smazano 1289 radku deprecated kodu
   - `BaseModelResolverModal.tsx` (749 radku) — DELETED
   - `/resolve-base-model` endpoint + `ResolveBaseModelRequest` — REMOVED from api.py
   - `resolveBaseModelMutation` — REMOVED from usePackData.ts
   - `baseModelResolver` — REMOVED from ModalState, DEFAULT_MODAL_STATE, types.ts, constants.ts
   - PackDependenciesSection redirected to DependencyResolverModal
   - PackDetailPage cleaned (removed useQuery, QUERY_KEYS unused imports)
   - i18n keys removed from en.json, cs.json
   - Tests updated: test_api_v2_critical.py, test_phase1_bug_fixes.py, test_api_critical.py, test_architecture.py
   - Frontend tests updated: pack-data-invalidation.test.ts, pack-detail-hooks.test.ts

**Testy:** 2203 backend + frontend all passed, 7 new validation tests added

**Zmenene soubory (Phase 4):**
- `src/store/api.py` — removed endpoint, added validation
- `src/store/resolve_service.py` — apply_manual cross-kind validation
- `apps/web/src/components/modules/PackDetailPage.tsx` — cleanup
- `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts` — removed mutation
- `apps/web/src/components/modules/pack-detail/modals/BaseModelResolverModal.tsx` — DELETED
- `apps/web/src/components/modules/pack-detail/modals/index.ts` — removed export
- `apps/web/src/components/modules/pack-detail/sections/PackDependenciesSection.tsx` — redirect
- `apps/web/src/components/modules/pack-detail/types.ts` — removed baseModelResolver
- `apps/web/src/components/modules/pack-detail/constants.ts` — removed default
- `apps/web/src/i18n/locales/{en,cs}.json` — removed keys
- `tests/unit/store/test_resolve_validation.py` — 7 new tests
- `tests/store/test_api_v2_critical.py` — removed deprecated tests
- `tests/unit/store/test_phase1_bug_fixes.py` — removed BUG4 tests
- `tests/store/test_api_critical.py` — updated assertions
- `tests/lint/test_architecture.py` — removed endpoint requirement

---

## 11. Implementation Design — presna mapa napojeni (v2)

Revidovano po Gemini+Codex review implementacniho designu v0.7.0.
Opraveny: cyklicka zavislost, avatar injection timing, EvidenceProvider kontrakt,
chybejici DTO, candidate cache, test plan.

### 11a. Existujici architekturni vzory (DODRZOVAT)

Synapse pouziva konzistentni vzory, do kterych se MUSIME napojit:

| Vzor | Kde pouzivan | Jak rozsirime |
|------|-------------|--------------|
| **Store = Facade** | `__init__.py` drzi 8 sluzeb, constructor DI | Pridat `resolve_service` jako 9. sluzbu, `local_file_service` jako 10. |
| **Protocol-based registry** | `DependencyResolver` protocol, `_ensure_resolvers()` lazy init | `EvidenceProvider` protocol, `_ensure_providers()` lazy init |
| **AITask ABC + TaskRegistry** | `tasks/base.py`, `tasks/registry.py`, auto-discovered | Pridat `DependencyResolutionTask` do registry |
| **Shared services** | DownloadService, BlobStore sdilene pres Store | ResolveService dostane sdilene sluzby |
| **Lazy-loaded clients** | `@property` v PackService pro civitai/hf | ResolveService pouzije tytez |
| **FastAPI Depends()** | `store=Depends(require_initialized)` | Nove endpointy stejna injection |
| **TanStack Query mutations** | `usePackData` hook centralizuje mutace | Pridat suggest/apply mutace |
| **Props-based modaly** | BaseModelResolverModal, data up via callbacks | DependencyResolverModal stejny vzor |

### 11b. Klicove designove rozhodnuti (z review)

**R1: Zadna cyklicka zavislost**
- ResolveService → PackService (pro apply write path) = OK
- PackService NEZNA ResolveService (zadna zpetna reference)
- Post-import resolve orchestrovano z `Store.import_civitai()` (facade)
- Stejna jednosmernost jako zbytek Store architektury

**R2: Klienty pres PackService, ne duplicitne**
- ResolveService NEDRZI vlastni civitai/hf klienty
- Pristupuje pres `pack_service.civitai` / `pack_service.huggingface` (lazy-loaded properties)
- Jediny vlastnik klientu = PackService

**R3: Avatar pres getter, ne primo**
- `avatar_getter: Callable[[], AvatarTaskService | None]`
- Provider zavola getter at runtime → bezpecne i pokud avatar pripojen pozdeji
- Zadny timing problem s _ensure_providers()

**R4: Provider vraci kandidata + evidenci dohromady**
- NE holou evidenci (kde by kandidat mel byt sestaven nekde jinde)
- `ProviderResult` obsahuje `List[EvidenceHit]` kde kazdy hit ma `CandidateSeed` + `EvidenceItem`
- ResolveService jen mergi a rankuje — neinterpretuje evidence

**R5: Import-time AI default OFF**
- `include_ai=False` pro import (deterministicke urovne E1-E6 staci pro vetsinu)
- AI jen pri explicitnim suggest v UI nebo pro unresolved deps
- Duvod: AvatarTaskService serializes engine za jednim lockem → multi-dep AI = pomale

### 11c. DTO definice (vsechny na jednom miste)

```python
# src/store/resolve_models.py — vsechny DTO pro resolve system

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

# --- Evidence kontrakty ---

class CandidateSeed(BaseModel):
    """Identifikace kandidata — co provider nasel."""
    key: str                                   # Deduplikacni klic (hash+provider)
    selector: DependencySelector               # Kompletni selector data
    canonical_source: Optional[CanonicalSource] = None
    display_name: str                          # "Illustrious XL v0.6"
    display_description: Optional[str] = None
    provider_name: Optional[Literal["civitai", "huggingface", "local"]] = None

class EvidenceHit(BaseModel):
    """Jeden nalez = kandidat + dukaz proc."""
    candidate: CandidateSeed
    provenance: str                            # "preview:001.png", "hash:sha256", "alias:SDXL"
    item: EvidenceItem                         # Konkretni dukaz

class EvidenceItem(BaseModel):
    source: Literal["hash_match", "preview_embedded", "preview_api_meta",
                     "source_metadata", "file_metadata", "alias_config",
                     "ai_analysis"]
    description: str
    confidence: float
    raw_value: Optional[str] = None

class ProviderResult(BaseModel):
    """Vystup jednoho evidence provideru."""
    hits: List[EvidenceHit] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None

# --- Request/Response kontrakty ---

class SuggestOptions(BaseModel):
    """Volby pro suggest_resolution."""
    include_ai: bool = False                   # Default OFF (R5)
    analyze_previews: bool = True
    max_candidates: int = 10

class SuggestResult(BaseModel):
    """Vysledek suggest — seznam kandidatu + metadata."""
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    candidates: List[ResolutionCandidate] = Field(default_factory=list)
    pack_fingerprint: str = ""                 # SHA hash pack.json pro stale detection
    warnings: List[str] = Field(default_factory=list)

class ApplyResult(BaseModel):
    """Vysledek apply — uspech/neuspech."""
    success: bool
    message: str = ""
    compatibility_warnings: List[str] = Field(default_factory=list)

class ManualResolveData(BaseModel):
    """Data z manualniho resolve (Civitai/HF/Local tab)."""
    strategy: SelectorStrategy
    civitai: Optional[CivitaiSelector] = None
    huggingface: Optional[HuggingFaceSelector] = None
    local_path: Optional[str] = None
    url: Optional[str] = None
    canonical_source: Optional[CanonicalSource] = None
    display_name: Optional[str] = None

# --- Resolve context (predavano providerum) ---

class ResolveContext(BaseModel):
    """Kontext predavany evidence providerum."""
    pack: Any                                  # Pack objekt (ne Pydantic)
    dependency: Any                            # PackDependency
    dep_id: str
    kind: AssetKind
    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
    layout: Any = None                         # StoreLayout (pro file-system access)

    class Config:
        arbitrary_types_allowed = True
```

### 11d. EvidenceProvider Protocol

```python
# src/store/evidence_providers.py

@runtime_checkable
class EvidenceProvider(Protocol):
    """
    Protocol pro evidence providery.
    Stejny vzor jako DependencyResolver — duck typing, @runtime_checkable.

    Kazdy provider:
    1. Zkontroluje supports() — je relevantni pro dany AssetKind?
    2. gather() — sbira evidence, vraci ProviderResult s EvidenceHit items
    3. Kazdy EvidenceHit obsahuje CandidateSeed (CO nasel) + EvidenceItem (PROC)
    """

    @property
    def tier(self) -> int:
        """Confidence tier tohoto provideru (1-4)."""
        ...

    def supports(self, context: ResolveContext) -> bool:
        """Zda je provider relevantni pro dany context (kind, dostupnost sluzby)."""
        ...

    def gather(self, context: ResolveContext) -> ProviderResult:
        """Sbira evidence. Vraci hits s kandidaty + dukazy."""
        ...
```

**Implementace (6 provideru):**

```python
class HashEvidenceProvider:
    """E1: SHA256 lookup na Civitai + HF. Tier 1."""
    tier = 1

    def __init__(self, pack_service_getter):
        self._ps = pack_service_getter  # Callable → PackService

    def supports(self, ctx):
        return True  # Vzdy, pokud mame hash

    def gather(self, ctx):
        # Lookup hash z existujiciho lock nebo z Civitai file metadata
        # → civitai: pack_service.civitai.get_model_by_hash()
        # → hf: LFS pointer check (pokud eligible)
        ...

class PreviewMetaEvidenceProvider:
    """E2+E3: Preview metadata (PNG + API sidecar). Tier 2."""
    tier = 2
    def supports(self, ctx): return bool(ctx.preview_hints)
    def gather(self, ctx): ...  # Kind-aware filtrovani, provenance grouping

class FileMetaEvidenceProvider:
    """E5: Filename patterns, architecture. Tier 3."""
    tier = 3
    def supports(self, ctx): return True
    def gather(self, ctx): ...

class AliasEvidenceProvider:
    """E6: Configured aliases (Civitai + HF cile). Tier 3."""
    tier = 3
    def __init__(self, layout_getter):
        self._layout = layout_getter  # Callable → StoreLayout
    def supports(self, ctx): return True
    def gather(self, ctx): ...  # Cteni base_model_aliases z config

class SourceMetaEvidenceProvider:
    """E4: Civitai baseModel field (jen voditko). Tier 4."""
    tier = 4
    def supports(self, ctx): return True
    def gather(self, ctx): ...

class AIEvidenceProvider:
    """E7: AI analysis (MCP-backed). Ceiling 0.89."""
    tier = 2  # AI muze byt az Tier 2

    def __init__(self, avatar_getter):
        self._get_avatar = avatar_getter  # Callable → Optional[AvatarTaskService]

    def supports(self, ctx):
        avatar = self._get_avatar()
        return avatar is not None and can_use_ai()

    def gather(self, ctx):
        avatar = self._get_avatar()
        if avatar is None:
            return ProviderResult(error="Avatar not available")
        result = avatar.execute_task("dependency_resolution", ...)
        ...  # Parse do EvidenceHit items
```

### 11e. ResolveService — jadro (opraveny design)

```python
# src/store/resolve_service.py

class ResolveService:
    """
    Orchestrace dependency resolution.
    9. sluzba v Store facade.

    NEDRZI vlastni klienty — pristupuje pres pack_service (R2).
    NEZNA PackService zpetne — jednosmerny tok (R1).
    Avatar pres getter callable (R3).
    """
    def __init__(
        self,
        layout: StoreLayout,
        pack_service: PackService,
        avatar_getter: Callable[[], Optional[AvatarTaskService]] = lambda: None,
        providers: Optional[Dict[str, EvidenceProvider]] = None,
        candidate_cache: Optional[CandidateCacheStore] = None,
    ):
        self._layout = layout
        self._pack_service = pack_service
        self._avatar_getter = avatar_getter
        self._providers = providers
        self._cache = candidate_cache or InMemoryCandidateCache()

    def _ensure_providers(self) -> None:
        """Lazy init. Providers pouzivaji gettery, ne prime reference."""
        if self._providers:
            return
        from .evidence_providers import (
            HashEvidenceProvider, PreviewMetaEvidenceProvider,
            FileMetaEvidenceProvider, AliasEvidenceProvider,
            SourceMetaEvidenceProvider, AIEvidenceProvider,
        )
        ps_getter = lambda: self._pack_service
        layout_getter = lambda: self._layout
        self._providers = {
            "hash_match": HashEvidenceProvider(ps_getter),
            "preview_meta": PreviewMetaEvidenceProvider(),
            "file_meta": FileMetaEvidenceProvider(),
            "alias": AliasEvidenceProvider(layout_getter),
            "source_meta": SourceMetaEvidenceProvider(),
            "ai": AIEvidenceProvider(self._avatar_getter),
        }

    def suggest(self, pack: Pack, dep_id: str, options: SuggestOptions) -> SuggestResult:
        """
        1. Sestavi ResolveContext
        2. Projde providers (dle tier poradi, jen supports()==True)
        3. Merge EvidenceHit po candidate.key
        4. Score (Noisy-OR s provenance grouping + tier ceiling)
        5. Sort, assign UUID candidate_id, cache
        6. Vrati SuggestResult
        """
        ...

    def apply(self, pack_name: str, dep_id: str, candidate_id: str) -> ApplyResult:
        """
        1. Najde kandidata v cache (dle request_id + candidate_id)
        2. Overi pack fingerprint (stale detection)
        3. Validace: min fields (validation matrix) + cross-kind check
        4. Deleguje na pack_service.apply_dependency_resolution()
        5. Vrati ApplyResult
        """
        ...

    def apply_manual(self, pack_name: str, dep_id: str, manual: ManualResolveData) -> ApplyResult:
        """
        Stejna validace jako apply, ale data z manualniho UI.
        Taky deleguje na pack_service.apply_dependency_resolution().
        """
        ...
```

### 11f. Candidate cache

```python
# Soucasti resolve_service.py nebo samostatny modul

class CandidateCacheStore(Protocol):
    """Abstrakce pro candidate cache — injectable, testable."""
    def store(self, request_id: str, fingerprint: str,
              candidates: List[ResolutionCandidate]) -> None: ...
    def get(self, request_id: str, candidate_id: str) -> Optional[ResolutionCandidate]: ...
    def check_fingerprint(self, request_id: str, fingerprint: str) -> bool: ...
    def cleanup_expired(self) -> None: ...

class InMemoryCandidateCache:
    """Default in-process cache. TTL 5min. S fingerprint kontrolou."""
    # POZN: Synapse bezi jako single-worker uvicorn (ne multi-worker)
    # Pro multi-worker: nahradit za file-based nebo Redis cache
    ...
```

### 11g. PackService rozsireni — apply write path (R1)

```python
# V pack_service.py — nova metoda:

def apply_dependency_resolution(
    self,
    pack_name: str,
    dep_id: str,
    selector: DependencySelector,
    canonical_source: Optional[CanonicalSource],
    lock_entry: Optional[Dict[str, Any]],
    display_name: Optional[str] = None,
) -> None:
    """
    Jediny write path pro dependency resolve.
    Aktualizuje pack.json + pack.lock.json ATOMICKY.

    NIKDY neprepise pack.base_model filename stemem (BUG 3 fix).
    """
    pack = self.layout.load_pack(pack_name)
    lock = self.layout.load_pack_lock(pack_name) or PackLock(pack_name=pack_name)

    # Najdi dependency
    dep = next((d for d in pack.dependencies if d.id == dep_id), None)
    if dep is None:
        raise ValueError(f"Dependency {dep_id} not found")

    # Update selector + canonical_source
    dep.selector = selector
    if canonical_source:
        dep.selector.canonical_source = canonical_source

    # Update lock entry
    if lock_entry:
        lock.artifacts[dep_id] = ResolvedArtifact(**lock_entry)

    # Atomicky zapis
    self.layout.save_pack(pack)
    self.layout.save_pack_lock(lock)
```

### 11h. Store facade — orchestrace (R1)

```python
# V src/store/__init__.py:

# === V __init__() za inventory_service: ===

self.resolve_service = ResolveService(
    layout=self.layout,
    pack_service=self.pack_service,
    avatar_getter=lambda: self._avatar_task_service,  # R3: getter
)

# === Delegovane metody: ===

def suggest_resolution(self, pack_name, dep_id, options=None):
    pack = self.get_pack(pack_name)
    return self.resolve_service.suggest(pack, dep_id, options or SuggestOptions())

def apply_resolution(self, pack_name, dep_id, candidate_id):
    return self.resolve_service.apply(pack_name, dep_id, candidate_id)

# === V import_civitai() — post-import orchestrace: ===

def import_civitai(self, url, ...):
    # 1-2. Existujici import logika v pack_service
    pack = self.pack_service.import_from_civitai(url, ...)

    # 3. Post-import resolve (orchestrovano z Store, NE z PackService)
    if pack and pack.dependencies:
        from .utils.preview_meta_extractor import extract_preview_hints
        hints = extract_preview_hints(pack, self.layout)
        for dep in pack.dependencies:
            result = self.resolve_service.suggest(pack, dep.id, SuggestOptions(
                include_ai=False,  # R5: default OFF pri importu
                preview_hints_override=hints,
            ))
            # Auto-apply pokud TIER-1/2 s dostatecnym marginem
            if result.candidates and result.candidates[0].tier <= 2:
                top = result.candidates[0]
                margin = (top.confidence - result.candidates[1].confidence
                         if len(result.candidates) > 1 else 1.0)
                if margin >= 0.15:
                    self.resolve_service.apply(pack.name, dep.id, top.candidate_id)

    return pack

# === Avatar injection (post-init): ===

def set_avatar_service(self, avatar_task_service):
    """Volano z api.py po inicializaci avatar."""
    self._avatar_task_service = avatar_task_service
    # Getter v resolve_service uz automaticky vidi novou hodnotu (R3)
```

### 11i. Avatar task rozsireni

```python
# src/avatar/tasks/base.py — pridat do AITask:
class AITask(ABC):
    task_type: str = ""
    SKILL_NAMES: Tuple[str, ...] = ()
    needs_mcp: bool = False     # NOVY: flag pro MCP-enabled execution
    timeout_s: int = 120        # NOVY: konfigurovatelny timeout

# src/avatar/task_service.py — _ensure_engine_for_task():
engine = AvatarEngine(
    provider=self._provider,
    model=self._model or None,
    system_prompt=system_prompt,
    timeout=task.timeout_s,                                           # NOVY
    safety_instructions="unrestricted",
    mcp_servers=self.config.mcp_servers if task.needs_mcp else None,  # NOVY
)

# src/avatar/tasks/dependency_resolution.py — novy task:
class DependencyResolutionTask(AITask):
    task_type = "dependency_resolution"
    SKILL_NAMES = ("model-resolution", "dependency-resolution", "model-types", "civitai-integration", "huggingface-integration")
    needs_mcp = True
    timeout_s = 180  # MCP volani jsou pomalejsi

    def build_system_prompt(self, skills_content): ...
    def parse_result(self, raw_output): ...
    def validate_output(self, output): ...
    def get_fallback(self): return None  # E1-E6 uz pokryto resolve_service

# src/avatar/tasks/registry.py — registrace:
from .dependency_resolution import DependencyResolutionTask
_default_registry.register(DependencyResolutionTask())
```

### 11j. API endpointy

```python
# src/store/api.py — v2_packs_router:

class SuggestRequest(BaseModel):
    include_ai: bool = False          # Default OFF (R5)
    analyze_previews: bool = True

class ApplyRequest(BaseModel):
    candidate_id: Optional[str] = None
    manual: Optional[ManualResolveData] = None

@v2_packs_router.post("/{pack_name}/dependencies/{dep_id}/suggest")
def suggest_dependency_resolution(
    pack_name: str, dep_id: str,
    request: SuggestRequest,
    store=Depends(require_initialized),
):
    options = SuggestOptions(
        include_ai=request.include_ai,
        analyze_previews=request.analyze_previews,
    )
    return store.suggest_resolution(pack_name, dep_id, options)

@v2_packs_router.post("/{pack_name}/dependencies/{dep_id}/apply")
def apply_dependency_resolution(
    pack_name: str, dep_id: str,
    request: ApplyRequest,
    store=Depends(require_initialized),
):
    if request.candidate_id:
        return store.apply_resolution(pack_name, dep_id, request.candidate_id)
    elif request.manual:
        return store.resolve_service.apply_manual(pack_name, dep_id, request.manual)
    raise HTTPException(400, "candidate_id or manual required")
```

### 11k. Frontend — usePackData + DependencyResolverModal

```typescript
// usePackData.ts — nove mutace:

const suggestResolutionMutation = useMutation({
  mutationFn: async ({ depId, options }: SuggestParams) => {
    const res = await fetch(
      `/api/packs/${enc(packName)}/dependencies/${depId}/suggest`,
      { method: 'POST', headers: CT_JSON, body: JSON.stringify(options ?? {}) }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json() as Promise<SuggestResult>
  },
})

const applyResolutionMutation = useMutation({
  mutationFn: async ({ depId, candidateId, manual }: ApplyParams) => {
    const res = await fetch(
      `/api/packs/${enc(packName)}/dependencies/${depId}/apply`,
      { method: 'POST', headers: CT_JSON, body: JSON.stringify(
        candidateId ? { candidate_id: candidateId } : { manual }
      )}
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
    toast.success(t('pack.resolve.applied'))
  },
})

// DependencyResolverModal.tsx — props:
interface DependencyResolverModalProps {
  isOpen: boolean
  onClose: () => void
  packName: string
  depId: string
  kind: AssetKind
  candidates: ResolutionCandidate[]
  isSuggesting: boolean
  onSuggest: (options?: SuggestOptions) => Promise<SuggestResult>
  onApply: (candidateId: string) => void
  onApplyAndDownload: (candidateId: string) => void  // Apply + trigger download
  onApplyManual: (data: ManualResolveData) => void
  isApplying: boolean
  previews: PreviewImage[]
  avatarAvailable: boolean
}

// --- Confidence prezentace (helper) ---

type ConfidenceLevel = 'exact' | 'high' | 'possible' | 'hint'

function getConfidenceLevel(candidate: ResolutionCandidate): ConfidenceLevel {
  if (candidate.tier === 1) return 'exact'
  if (candidate.tier === 2) return 'high'
  if (candidate.tier === 3) return 'possible'
  return 'hint'
}

const CONFIDENCE_DISPLAY: Record<ConfidenceLevel, { icon: string; label: string; color: string }> = {
  exact:    { icon: '✅', label: 'Exact match',    color: 'text-green-400'  },
  high:     { icon: '🔵', label: 'High confidence', color: 'text-blue-400'   },
  possible: { icon: '⚠️', label: 'Possible match',  color: 'text-amber-400'  },
  hint:     { icon: '❓', label: 'Hint — verify',   color: 'text-text-muted' },
}
// Raw confidence cisla dostupna v expandable "Details" — ne jako primarni zobrazeni

// --- Smart tab ordering ---
// Default tab logika:
//   1. Pokud candidates list ma TIER-1/2 → zadny tab aktivni (candidates list staci)
//   2. Pokud candidates prazdne → Preview Analysis (nejintuitivnejsi)
//   3. Jinak → tab s nejrelevatnejsim obsahem pro dany kind
```

### 11l. UX: Inline resolve + Apply & Download — implementacni design

**Napojeni na existujici download system:**

"Apply & Download" NENI novy download endpoint — je to sekvence dvou existujicich operaci:
1. `POST /{pack}/dependencies/{dep_id}/apply` → resolve (produkuje selector + lock entry)
2. `POST /{pack}/download-asset` → stahne asset (existujici endpoint v `usePackDownloads`)

Frontend to orchestruje v jednom kliknuti:

```typescript
// usePackData.ts — Apply & Download compound action:

const applyAndDownloadMutation = useMutation({
  mutationFn: async ({ depId, candidateId }: { depId: string; candidateId: string }) => {
    // Step 1: Apply resolve (metadata)
    const applyRes = await fetch(
      `/api/packs/${enc(packName)}/dependencies/${depId}/apply`,
      { method: 'POST', headers: CT_JSON, body: JSON.stringify({ candidate_id: candidateId }) }
    )
    if (!applyRes.ok) throw new Error(await applyRes.text())
    const result = await applyRes.json() as ApplyResult

    // Step 2: Refetch pack data to get updated asset info (url, filename, sha256)
    await queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })

    return { result, depId }
  },
  onSuccess: ({ depId }) => {
    // Step 3: Trigger download via existing usePackDownloads hook
    // Parent component calls downloads.downloadAsset(asset) po refetch
    onApplyAndDownloadComplete?.(depId)
    toast.success(t('pack.resolve.appliedAndDownloading'))
  },
})

// Return:
return {
  ...existing,
  applyAndDownload: (depId, candidateId) =>
    applyAndDownloadMutation.mutateAsync({ depId, candidateId }),
  isApplyingAndDownloading: applyAndDownloadMutation.isPending,
}
```

**Orchestrace v PackDetailPage.tsx:**

```typescript
// PackDetailPage drzi oba hooks:
const packData = usePackData(packName)
const downloads = usePackDownloads(packName)

// Po apply+refetch → spusti download pro danou dependency:
const handleApplyAndDownloadComplete = useCallback(async (depId: string) => {
  // Refetch done v mutaci → najdi updatovany asset
  const updatedPack = queryClient.getQueryData<Pack>(QUERY_KEYS.pack(packName))
  const asset = updatedPack?.assets?.find(a => a.dep_id === depId)
  if (asset && asset.url) {
    downloads.downloadAsset(asset)  // Existujici download system
  }
}, [packName, downloads, queryClient])
```

**Inline resolve v PackDependenciesSection:**

```typescript
// Progressive disclosure — jednoduche pripady bez modalu:
//
// V deps listu, pokud suggest vrati TIER-1/2 kandidata:
// ┌─────────────────────────────────────────────────────────┐
// │ 🔷 Checkpoint: illustriousXL_v060.safetensors           │
// │   Found: Illustrious XL v0.6 ✅                         │
// │   [Apply]  [Apply & Download]  [More options...]        │
// └─────────────────────────────────────────────────────────┘
//
// Pokud zadny kandidat nebo nizka confidence:
// ┌─────────────────────────────────────────────────────────┐
// │ 🔷 Checkpoint: unknown_model.safetensors                │
// │   ❓ No match found                                     │
// │   [Resolve...]  (otvira DependencyResolverModal)        │
// └─────────────────────────────────────────────────────────┘

// PackDependenciesSection.tsx — rozsireni props:
interface PackDependenciesSectionProps {
  // ... existujici props (assets, downloadingAssets, onDownloadAsset, ...)

  // NOVE — inline resolve:
  inlineResolveSuggestions?: Map<string, ResolutionCandidate>  // dep_id → top candidate
  onApplyResolve?: (depId: string, candidateId: string) => void
  onApplyAndDownloadResolve?: (depId: string, candidateId: string) => void
  onOpenResolveModal?: (depId: string, kind: AssetKind) => void
  isApplyingResolve?: boolean
}

// Zobrazeni v renderAsset():
//   if (needsResolve && inlineSuggestion) {
//     // Show inline candidate with Apply / Apply & Download / More options
//   } else if (needsResolve) {
//     // Existing "Resolve..." button → opens modal
//   }
```

**Smart tab ordering v DependencyResolverModal:**

```typescript
// Logika pro vyber default tabu:

function getDefaultTab(
  candidates: ResolutionCandidate[],
  avatarAvailable: boolean,
  kind: AssetKind,
): string | null {
  // 1. Pokud mame TIER-1/2 kandidata → candidates list staci, zadny tab
  if (candidates.some(c => c.tier <= 2)) return null

  // 2. Pokud prazdne candidates → Preview Analysis (nejintuitivnejsi)
  if (candidates.length === 0) return 'preview-analysis'

  // 3. Pokud mame jen low-confidence → AI tab pokud available
  if (avatarAvailable) return 'ai-resolve'

  // 4. Fallback → Civitai search
  return 'civitai-search'
}

// Poradi tabu (dynamicke dle kontextu):
function getTabOrder(kind: AssetKind, avatarAvailable: boolean): TabDef[] {
  const tabs: TabDef[] = [
    { id: 'preview-analysis', label: 'Preview Analysis', always: true },
    { id: 'ai-resolve', label: 'AI Resolve', visible: avatarAvailable },
    { id: 'local', label: 'Local Models', always: true },
    { id: 'civitai', label: 'Civitai', always: true },
    { id: 'huggingface', label: 'HuggingFace', visible: HF_ELIGIBLE_KINDS.has(kind) },
  ]
  return tabs.filter(t => t.always || t.visible)
}
// Preview Analysis jako prvni tab (nejintuitivnejsi), ne AI
// AI az druhy — vyzaduje explicitni akci "Analyze"
```

**Kdy se volá suggest (eager loading):**

```typescript
// V PackDetailPage — eager suggest pro unresolved deps:
// Pri nacteni packu → pro kazdou unresolved dep zavolat suggest (bez AI)
// Vysledky ulozit do stanu → pouzit pro inline resolve i modal

useEffect(() => {
  if (!pack?.dependencies) return
  const unresolvedDeps = pack.dependencies.filter(d => !d.selector?.strategy)
  for (const dep of unresolvedDeps) {
    packData.suggestResolution(dep.id, { include_ai: false })
      .then(result => {
        if (result.candidates.length > 0) {
          setInlineSuggestions(prev => new Map(prev).set(dep.id, result.candidates[0]))
        }
      })
      .catch(() => {}) // Tichy fail — inline resolve je best-effort
  }
}, [pack?.dependencies])
// POZN: Debounce/dedup zajisti react-query (stejny key = zadny duplikat)
```

### 11m. Soubory — kompletni seznam

```
NOVE SOUBORY (Phase 0-2):
src/store/resolve_service.py           — ResolveService (suggest/apply orchestrace)
src/store/resolve_models.py            — Vsechny DTO (CandidateSeed, EvidenceHit, ProviderResult, ...)
src/store/evidence_providers.py        — 6 evidence provideru (Strategy pattern)
src/store/resolve_config.py            — AssetKind eligibility, compatibility matrix, aliases
src/store/resolve_validation.py        — Per-strategy min fields, cross-kind check
src/store/resolve_scoring.py           — Noisy-OR, provenance grouping, tier ceiling
src/store/hash_cache.py                — Persistent hash cache s async computation
src/utils/preview_meta_extractor.py    — PNG tEXt parser + sidecar .json reader
src/avatar/tasks/dependency_resolution.py  — AI task pro MCP-backed resolve
config/avatar/skills/model-resolution.md   — Hlavni AI prompt pro resolve (~240 radku, otestovano)
config/avatar/skills/huggingface-integration.md — HF Hub API reference knowledge (~95 radku)

NOVE SOUBORY (Phase 3):
src/store/enrichment.py                — Shared enrichment: hash/name lookup, enrich_file() pipeline (267 radku)
src/store/local_file_service.py        — LocalFileService: browse, recommend, import_file (~450 radku)
apps/web/.../modals/LocalResolveTab.tsx — Local File tab: 4-state UI (browse/importing/success/error, ~530 radku)
plans/SPEC-Local-Resolve.md            — Full specifikace (architektura, security, API, UX, testy)
tests/unit/store/test_enrichment.py    — 26 testu (extract_stem, normalize, kind_match, enrich)
tests/unit/store/test_local_file_service.py — 31 testu (validate, browse, recommend, import)

UPRAVENE SOUBORY (Phase 0-2):
src/store/__init__.py                  — +ResolveService, +set_avatar_service, import orchestrace
src/store/pack_service.py              — +apply_dependency_resolution() write metoda
src/store/models.py                    — +CanonicalSource (s subfolder), rozsireni DependencySelector
src/store/api.py                       — +suggest/apply endpointy, deprecate /resolve-base-model
src/avatar/tasks/base.py               — +needs_mcp, +timeout_s na AITask
src/avatar/task_service.py             — mcp_servers do engine, dynamicky timeout
src/avatar/tasks/registry.py           — +DependencyResolutionTask registrace
apps/web/.../hooks/usePackData.ts      — +suggest/apply/applyAndDownload mutace
apps/web/.../modals/DependencyResolverModal.tsx  — NOVY (nahrazuje BaseModelResolverModal)
apps/web/.../sections/PackDependenciesSection.tsx — +inline resolve UI, +Apply & Download
apps/web/.../PackDetailPage.tsx        — orchestrace apply+download, eager suggest
apps/web/src/lib/avatar/api.ts         — +incompatible stav v TS union

UPRAVENE SOUBORY (Phase 3):
src/store/__init__.py                  — +HashCache init, +LocalFileService jako 10. sluzba
src/store/api.py                       — +5 local resolve endpointu, ThreadPoolExecutor, import polling
apps/web/.../modals/DependencyResolverModal.tsx — +Local File tab integrace, +HardDrive icon
apps/web/.../types.ts                  — +LocalFileInfo, FileRecommendation, BrowseLocalResult, LocalImportStatus
apps/web/.../constants.ts              — +localBrowse, localRecommend, localImport query keys
```

### 11n. Dependency graf — cilovy stav

```
Store (Facade) — 10 sluzeb, JEDNOSMERNY tok
│
├── [1-8] existujici sluzby beze zmeny
│
├── [9] ResolveService (NOVY)
│   ├── StoreLayout (shared)
│   ├── PackService (shared — jen pro apply write path, JEDNOSMERNY)
│   ├── avatar_getter: Callable → Optional[AvatarTaskService]
│   ├── EvidenceProvider registry (lazy-initialized, gettery)
│   │   ├── HashEvidenceProvider (T1) → ps_getter → pack_service.civitai/hf
│   │   ├── PreviewMetaEvidenceProvider (T2) → preview_meta_extractor
│   │   ├── FileMetaEvidenceProvider (T3)
│   │   ├── AliasEvidenceProvider (T3) → layout_getter → config
│   │   ├── SourceMetaEvidenceProvider (T4)
│   │   └── AIEvidenceProvider (T-AI) → avatar_getter → task_service
│   ├── ResolveScoring → Noisy-OR, tier ceiling
│   ├── ResolveValidation → per-strategy min fields, cross-kind
│   └── CandidateCacheStore → InMemoryCandidateCache (injectable)
│
├── [10] LocalFileService (NOVY — Phase 3)
│   ├── HashCache (shared — persistent SHA256 cache)
│   ├── BlobStore (shared — blob storage)
│   ├── pack_service_getter: Callable → PackService (lazy, no circular deps)
│   ├── enrichment.py (shared modul):
│   │   ├── enrich_by_hash() → Civitai hash lookup
│   │   ├── enrich_by_name() → Meilisearch name search
│   │   └── enrich_file() → pipeline: hash → name → filename_only
│   ├── browse(directory, kind?) → BrowseResult
│   ├── recommend(directory, dep, kind?) → List[FileRecommendation]
│   └── import_file(path, pack, dep, skip_enrichment?) → LocalImportResult
│       ├── validate_path() → security checks
│       ├── SHA256 hash (with HashCache)
│       ├── Atomic blob copy (reflink → hardlink → shutil.copy2)
│       ├── enrich_file() → EnrichmentResult
│       └── _apply_resolution() → ManualResolveData → resolve_service.apply_manual()
│
├── Store.import_civitai() orchestruje:
│   1. pack_service.import_from_civitai() → Pack
│   2. resolve_service.suggest(pack, dep, include_ai=False) → SuggestResult
│   3. resolve_service.apply() pokud auto-apply pravidla splnena
│
└── Store.set_avatar_service() → self._avatar_task_service
    (avatar_getter v ResolveService automaticky vidi)
```

### 11o. Test plan — kompletni struktura

**Soubory:**
```
tests/unit/store/test_resolve_service.py
tests/unit/store/test_evidence_providers.py
tests/unit/store/test_resolve_scoring.py
tests/unit/store/test_resolve_validation.py
tests/unit/store/test_resolve_models.py
tests/unit/store/test_hash_cache.py
tests/unit/store/test_enrichment.py                  — Phase 3: shared enrichment module (26 testu)
tests/unit/store/test_local_file_service.py           — Phase 3: browse, recommend, import (31 testu)
tests/unit/utils/test_preview_meta_extractor.py
tests/unit/avatar/test_dependency_resolution_task.py
tests/store/test_resolve_api.py
tests/integration/test_resolve_integration.py
tests/integration/test_resolve_import_flow.py
tests/smoke/test_06_resolve_roundtrip.py
```

**Fixtures (tests/helpers/resolve_fixtures.py):**
```python
# Fake clients
fake_civitai_client          # Mock s predefined model responses
fake_huggingface_client      # Mock s HF repo/file data
fake_avatar_task_service     # Mock vracejici predefined TaskResult

# Pack fixtures
pack_with_unresolved_dep     # Pack s 1+ unresolved dependency
pack_with_resolved_dep       # Pack s resolved dep (pro regression)
pack_with_multiple_deps      # Pack s checkpoint + LoRA + VAE deps

# Preview fixtures
preview_sidecar_with_model   # Sidecar .json s meta.Model
preview_png_with_comfyui     # PNG s ComfyUI workflow v tEXt chunk
preview_png_stripped          # PNG bez metadata (CDN stripped)

# Registry
provider_registry_stub       # Predefined providers s known outputs
frozen_candidate_cache       # Cache s pre-filled candidates

# Store
store_with_resolve_service   # Plny Store s ResolveService injected
```

**Konkretni test cases:**

**Unit: test_resolve_service.py**
```python
class TestSuggest:
    def test_skips_providers_that_dont_support_context(self): ...
    def test_merges_hits_by_candidate_key(self): ...
    def test_assigns_uuid_candidate_id(self): ...
    def test_caches_result_with_fingerprint(self): ...
    def test_returns_empty_when_no_providers_match(self): ...
    def test_orders_by_tier_then_confidence(self): ...

class TestApply:
    def test_delegates_to_pack_service_apply(self): ...
    def test_rejects_unknown_candidate_id(self): ...
    def test_rejects_stale_fingerprint(self): ...
    def test_validates_min_fields_per_strategy(self): ...
    def test_warns_cross_kind_incompatibility(self): ...

class TestApplyManual:
    def test_validates_same_as_cached_candidate(self): ...
    def test_creates_canonical_source_for_civitai(self): ...
```

**Unit: test_evidence_providers.py**
```python
class TestHashProvider:
    def test_returns_tier1_hit_on_civitai_hash_match(self): ...
    def test_returns_tier1_hit_on_hf_hash_match(self): ...
    def test_returns_empty_when_no_hash_available(self): ...
    def test_skips_hf_when_kind_not_eligible(self): ...

class TestPreviewMetaProvider:
    def test_extracts_model_from_sidecar_json(self): ...
    def test_groups_by_provenance_per_image(self): ...
    def test_marks_unresolvable_for_private_models(self): ...
    def test_filters_by_kind(self): ...

class TestAIProvider:
    def test_supports_returns_false_when_avatar_none(self): ...
    def test_supports_returns_true_after_set_avatar(self): ...
    def test_gather_calls_dependency_resolution_task(self): ...
    def test_caps_confidence_at_089(self): ...
```

**Unit: test_resolve_scoring.py**
```python
class TestNoisyOR:
    def test_single_group(self): ...
    def test_independent_groups_combine(self): ...
    def test_tier_ceiling_applied(self): ...
    def test_conflicting_evidence_lowers_both(self): ...

class TestProvenanceGrouping:
    def test_same_image_groups_into_one(self): ...
    def test_different_images_stay_separate(self): ...
    def test_group_confidence_is_max_of_items(self): ...
```

**Integration: test_resolve_integration.py**
```python
class TestSuggestApplyFlow:
    def test_suggest_then_apply_updates_pack_json(self, store_with_resolve): ...
    def test_suggest_then_apply_updates_lock_json(self, store_with_resolve): ...
    def test_manual_apply_same_validation(self, store_with_resolve): ...
    def test_apply_never_overwrites_base_model_with_stem(self, store_with_resolve): ...

class TestImportWithResolve:
    def test_import_auto_resolves_tier1_hash(self, store_with_resolve, fake_civitai): ...
    def test_import_leaves_unresolved_when_low_confidence(self, store_with_resolve): ...
    def test_import_skips_ai_by_default(self, store_with_resolve): ...
    def test_import_respects_margin_threshold(self, store_with_resolve): ...
```

**Integration: test_resolve_api.py**
```python
class TestSuggestEndpoint:
    def test_returns_candidates_with_evidence(self, client): ...
    def test_respects_include_ai_flag(self, client): ...
    def test_returns_409_on_stale_apply(self, client): ...

class TestApplyEndpoint:
    def test_apply_candidate_updates_pack(self, client): ...
    def test_apply_manual_validates_fields(self, client): ...
    def test_apply_returns_compatibility_warnings(self, client): ...
```

**Smoke: test_06_resolve_roundtrip.py**
```python
class TestResolveRoundtrip:
    def test_import_resolve_download_lifecycle(self, smoke_store): ...
    def test_manual_civitai_resolve_flow(self, smoke_store): ...
    def test_manual_local_bind_flow(self, smoke_store): ...
```

---

## 12. Review historie

### v0.1.0 — Initial draft
### v0.2.0 — Gemini 3.1 + Codex 5.4 (1. kolo, 14 nalezu)
### v0.3.0 — Zapracovani 1. kola
### v0.4.0 — Codex 5.4 (2. kolo, 9 nalezu) — suggest/apply, evidence ladder, matrices
### v0.5.0 — Uzivatelske review (3 kriticke body) — dual-provider, preview metadata, HF design

### v0.6.0 (2026-03-07) — Gemini + Codex final review
### v0.7.0 (2026-03-07) — Implementation Design Map — FINAL

**Gemini 3.1 — final review (5 nalezu):**
1. HIGH: Hash cache presunout do Phase 0 (G1)
2. HIGH: Cross-kind compatibility validace chybi (G2)
3. MED: Scoring bez formalni combining function (G3)
4. MED: CDN stripping fallback (G4)
5. LOW: Alias/CanonicalSource sync (G5)

**Codex 5.4 — final review (10 nalezu):**
1. HIGH: Confidence ranges se prekryvaji — need neprekryvajici se tiery (C1)
2. HIGH: HF discovery underspecified, diffusers-only filter (C2)
3. HIGH: Preview metadata overstated — unresolvable/private modely (C3)
4. HIGH: candidate_index nestabilni — pouzit candidate_id UUID (C4)
5. MED: Neoverene predpoklady pred Phase 1 — calibration subphase (C5)
6. MED: Korelovana evidence — provenance grouping (C6)
7. MED: "Vzdy dual provider" vs eligibility per kind (C7)
8. MED: Migrace starych packu nepromyslena (C8)
9. LOW: CanonicalSource chybi subfolder (C9)
10. LOW: E4/E5 poradi — file metadata konkretnejsi nez baseModel (C10)

**Zapracovani v0.6.0 (kompletni redesign, ne appendy):**
- **Tier system** (2b): neprekryvajici se confidence bands, AI ceiling 0.89 (C1)
- **Provider eligibility** (2c): per-AssetKind tabulka misto "vzdy oba" (C7)
- **HF discovery design** (2d): 4 strategie (filename, known repos, AI, LFS verify) (C2)
- **Preview normalizace** (2e): kind-aware, provenance grouping, unresolvable stav (C3, C6)
- **Stable candidate_id** (2f): UUID misto indexu, request cache s TTL (C4)
- **Provenance grouping a Noisy-OR** (2g): formalni scoring s tier ceiling (G3, C6)
- **Cross-kind compatibility** (2h): warning pri nekompatibilnich kombinacich (G2)
- **Hash cache v Phase 0** (10): zaklady pred local resolve (G1)
- **Calibration subphase** (Phase 0): CDN test + confidence mapping na realnych datech (C5, G4)
- **Migration helper** (Phase 1): enrichment starych packu (C8)
- **subfolder v CanonicalSource** (2i): HF repo disambiguation (C9)
- **E4/E5 prohozeni** (2b): file metadata (TIER-3) pred source metadata (TIER-4) (C10)

**v0.7.0 — Implementation Design Map:**
- Kompletni architekturni pruzkum existujiciho codebase
- Zmapovane vzory: Store facade, Protocol registries, AITask ABC, FastAPI DI, TanStack Query
- Sekce 11: presna mapa napojeni — kam co patri, jaky vzor pouzit
- ResolveService jako 9. sluzba v Store (constructor DI, lazy providers)
- EvidenceProvider Protocol (jako DependencyResolver — duck typing, extensible)
- DependencyResolutionTask (AITask ABC, v registry, needs_mcp flag)
- Frontend: usePackData rozsireni, DependencyResolverModal props pattern
- 10 novych souboru, presny dependency graf, zero parallel architectures

**v0.7.1 — UX refinement + cleanup:**
- Odstraneny duplicitni subsekce 11c-11k (stara verze, 382 radku)
- Opraveno cislovani sekci (12 Review historie, 13 Open Questions)
- Poznamka u E4/E5 cislovani (historicke duvody)
- User-friendly confidence prezentace (Exact match / High / Possible / Hint misto raw cisel)
- "Apply & Download" akce — resolve + okamzity download v jednom kroku (vedle Apply only)
- Smart tab ordering — default tab dle nejlepsiho kandidata, ne fixni poradi
- Inline resolve v PackDependenciesSection — TIER-1/2 kandidati bez nutnosti otvirat modal
- Preview Analysis jako default tab pri prazdnych candidates (nejintuitivnejsi)

---

## 13. Open Questions

| Otazka | Status |
|--------|--------|
| ~~AI gate mechanismus~~ | UZAVRENO — available === true |
| ~~Resolution vs download~~ | UZAVRENO — explicitne oddelene |
| ~~ComfyUI endpoint 500~~ | UZAVRENO — vraci [] gracefully |
| ~~Confidence ranges~~ | UZAVRENO — neprekryvajici se tiery |
| ~~Dual provider vzdy?~~ | UZAVRENO — provider eligibility per AssetKind |
| ~~Preview metadata overcounting~~ | UZAVRENO — provenance grouping |
| ~~candidate_index stabilita~~ | UZAVRENO — UUID candidate_id |
| ~~Civitai CDN stripuje PNG metadata?~~ | UZAVRENO — CDN servíruje JPEG/WebP, NE originální PNG. E2 (png_embedded) je best-effort only. E3 (api_meta ze sidecar .json) je PRIMARY zdroj. Kalibrace 2026-03-07. |
| Confidence thresholds (0.85 auto-apply?) | OPEN → Phase 1 calibration na realnych datech (import flow) |
| Timeout pro MCP-enabled tasky | OPEN — merit pri implementaci |
| HUGGINGFACE_LATEST strategie? | OPEN — zatim neni v update_service |

---

---

#### Preview Analysis Tab — Full Implementation (2026-03-08)

**Block F placeholder → full implementation.**

**Backend:**
- ✅ BUG 7 fix: Sidecar format — `_parse_sidecar_meta()` now supports both flat and wrapped formats
- ✅ BUG 8 fix: Sidecar path — `extract_preview_hints()` now uses `pack_previews_path()` not `pack_path()`
- ✅ Enhanced sidecar parsing: `hash`, `weight` fields on `PreviewModelHint`; LoRA tags from prompt text
- ✅ `PreviewAnalysisResult` model: filename, url, media_type, hints, generation_params
- ✅ `analyze_pack_previews()` — full preview analysis function
- ✅ ComfyUI node registry: `ComfyUINodeDef` dataclass + `COMFYUI_NODE_REGISTRY` dict (20 node types)
  - Multi-model node support (DualCLIPLoader → 2 hints)
  - New nodes: UNETLoader, DiffControlNetLoader, IPAdapterModelLoader, StyleModelLoader, etc.
- ✅ `GET /api/packs/{pack}/preview-analysis` endpoint
- ✅ `SuggestResult.preview_hints` extension

**Frontend:**
- ✅ `PreviewAnalysisTab.tsx` — ~350 line component with:
  - Responsive thumbnail grid (5-8 columns)
  - Click-to-select with metadata panel
  - Model hints with kind badges, hash, weight display
  - "Use" button → cross-references existing candidates, switches to Candidates tab
  - Generation params display (sampler, steps, CFG, seed, prompt, negative)
  - Copy-to-clipboard for prompts
  - Loading, error, empty states
- ✅ `usePreviewAnalysis` hook (React Query, 5min staleTime)
- ✅ `PreviewModelHintInfo`, `PreviewAnalysisItem`, `PreviewAnalysisResponse` types
- ✅ Integrated into DependencyResolverModal (replaced placeholder)

**Tests:**
- 65 unit tests: `tests/unit/utils/test_preview_meta_extractor.py`
  - BUG 7 format tests (6), enhanced parsing (10), real data (5), ComfyUI registry (14)
  - analyze_pack_previews (5), generation params (4), existing tests preserved (21)
- 5 API tests: `tests/store/test_api_preview_analysis.py`
- 12 frontend tests: `apps/web/src/__tests__/preview-analysis.test.ts`

**Review:** Claude review completed — 4 MEDIUM issues found and fixed (bounds check, clipboard error handling, misleading docstring, unused prop). Pre-existing Layout.tsx TS errors not related to changes.

*Created: 2026-03-07*
*Last Updated: 2026-03-08*
