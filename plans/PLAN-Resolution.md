# PLAN: Smart Resolution - Model Discovery & Download

**Version:** v0.1.0
**Status:** DRAFT / FUTURE
**Priority:** Medium
**Created:** 2026-02-19
**Author:** raven2cz + Claude Opus 4.6

---

## 1. Goal

Smart resolution for unresolved pack dependencies: automatically discover, match, and download missing model files.

This plan was extracted from Dependencies Phase 5 (PLAN-Dependencies.md) to give it dedicated scope.

---

## 2. Planned Features

### 2a: Local Model Scanning & Matching
- Scan ComfyUI/Forge/A1111 model directories
- Match local files against unresolved dependencies by filename, hash, or metadata
- Auto-resolve deps that already exist on disk but aren't registered

### 2b: Avatar-Engine AI Recommendations
- Integration with avatar-engine AI agents
- AI suggests correct models for a pack based on description, style, workflow
- Confidence scoring for recommendations

### 2c: Auto-detect Dependencies from Descriptions
- Parse pack/model descriptions for dependency hints
- Extract model references from Civitai descriptions (HTML parsing)
- Suggest dependencies based on workflow analysis

### 2d: Download Orchestration
- Queue-based download system for unresolved deps
- Progress tracking per-dependency
- Retry logic, bandwidth limiting
- Priority ordering (required deps first)

### 2e: Dependency Tree Resolution
- Walk full dependency tree and identify all unresolved items
- Batch resolution suggestions
- One-click "resolve all" for simple cases

---

## 3. Prerequisites

- ✅ Dependencies Phase 1-3 (PLAN-Dependencies.md)
- ✅ Dependencies Phase 4 (UI Polish)
- Blob inventory system (PLAN-Model-Inventory.md)

---

## 4. Open Questions

| Question | Status |
|----------|--------|
| Which model directories to scan? | OPEN - configurable per-UI |
| How to match by hash vs filename? | OPEN - hash preferred, filename fallback |
| Avatar-engine API contract? | OPEN - needs avatar-engine design |
| Download concurrency limits? | OPEN - likely 2-3 concurrent |
| Should `apply_resolution()` update lock.json or invalidate it? | OPEN (DOMAIN-AUDIT Open Q #2) |
| `Pack.source` = "creation source" or "all content source"? | OPEN (DOMAIN-AUDIT Open Q #3) |

---

## 5. Domain Audit Findings (2026-05-02)

Z `plans/audits/DOMAIN-AUDIT.md` + `plans/audits/codex-domain-audit.md`. Tyto nálezy
patří k **resolve-redesign** (`feat/resolve-model-redesign` branch) i k aktuálnímu
resolveru na `main`.

### H3 [HIGH] — `apply_dependency_resolution` nepropisuje do `Pack.source`

**Finding:** Na resolve-redesign branchi (`feat/resolve-model-redesign`) má
`DependencySelector` nové pole `canonical_source: Optional[CanonicalSource]`.
`apply_dependency_resolution` zapíše vybranou kandidátku do `selector.canonical_source`,
ale **`Pack.source` zůstane beze změny**. Důsledek: dvě paralelní hierarchie identity:

- `Pack.source: PackSource` → "kde jsem byl importován"
- `DependencySelector.canonical_source: CanonicalSource` → "kde je teď fyzický soubor"

Po resolve může být `Pack.source` zastaralý (pack se importoval z Civitai, ale resolve
ho přesměroval na HuggingFace mirror). UI a API klienti čtou jeden, druhý, nebo oba —
bez jasné policy.

**Recommendation — vyžaduje rozhodnutí (Open Q #2 + #3):**

Volba A — `Pack.source` je "creation source" (jen jak vznikl, immutable po importu).
`canonical_source` je current truth. UI rozliší.

Volba B — Po resolve se `Pack.source` aktualizuje na current resolved source.
`creation_source` (immutable) je nový pole.

Volba C — Lock.json je single source of truth pro current state, `Pack.source` zůstane
creation marker. `apply_resolution` **nepřepisuje selector.canonical_source**, jen lock.

**Severity:** HIGH (architektonické rozhodnutí, blokuje resolve-redesign merge)
**Refs:** branch `feat/resolve-model-redesign`, `pack_service.py apply_resolution`,
DOMAIN-AUDIT Section 5 + 8.

### M5 [MEDIUM] — `base_model_aliases` placeholder zero IDs

**Finding:** `_get_default_base_model_aliases()` v `models.py:271-307` definuje aliasy
pro SD1.5, SDXL, Illustrious, Pony. Všechny mají `model_id=0, version_id=0, file_id=0`
s komentářem **"These are placeholder values - real IDs should be filled in"**.

```python
"SD1.5": BaseModelAlias(
    kind=AssetKind.CHECKPOINT,
    default_expose_filename="v1-5-pruned-emaonly.safetensors",
    selector=BaseModelAliasSelector(
        strategy=SelectorStrategy.CIVITAI_FILE,
        civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
    )
),
```

**Důsledek:** Když resolver narazí na unresolved dependency a chce použít base model
alias, dostane `model_id=0` → buď failne, nebo si stáhne náhodný/neexistující model.
`BaseModelHintResolver` (`dependency_resolver.py`) se kvůli tomu nikdy nechytí.

**Recommendation:**

1. **Vyplnit reálné Civitai IDs** pro 4 well-known modely (SD1.5, SDXL, Illustrious, Pony).
   To může selhat — "official" model na Civitai pro SD1.5 možná neexistuje.
2. **Alternativně:** přepnout strategy na `HF_FILE` a použít HuggingFace IDs
   (runwayml/stable-diffusion-v1-5, stabilityai/stable-diffusion-xl-base-1.0, atd.).
3. **Nebo:** odstranit defaults a nechat aliasy prázdné. User si je nakonfiguruje sám.
   (Aktuálně v UI není konfigurace base aliasů, takže to znamená "feature off".)

**Severity:** MEDIUM (silent failure mode — `BaseModelHintResolver` selže neznatelně)
**Refs:** `models.py:271-307`, DOMAIN-AUDIT Section 11 + 12.

### M9 [MEDIUM] — `BaseModelHintResolver` swallowuje errory

**Finding:** `dependency_resolver.py:264` má `except Exception: pass` v nested try/except,
takže žádný error z Civitai API call, JSON parse, nebo lookup logic se neloguje. Když
resolve neuspěje, není jak zjistit proč.

```python
except Exception:
    pass  # ← line 264

return None
```

**Recommendation:** Změnit na `logger.warning("BaseModelHint resolve failed", exc_info=True)`.
Vrátit `None` zůstane, ale debugging je možný. Stejný pattern projít i v ostatních
resolverech (CivitaiFile, CivitaiLatest, HuggingFace, Url, LocalFile).

**Severity:** MEDIUM (debug pain, nikoli runtime crash)
**Refs:** `dependency_resolver.py:264`, DOMAIN-AUDIT Section 5.

### Souvislost s resolve-redesign

Branch `feat/resolve-model-redesign` přepisuje resolveer na nový model (CanonicalSource,
EvidenceItem, ResolutionCandidate). Nálezy H3, M5, M9 se týkají i nové architektury:

- **H3** musí být zodpovězeno PŘED merge resolve-redesign branche.
- **M5** přechází i na nový model (BaseModelAlias zůstává).
- **M9** je code-quality fix — opravit i v nových resolverech na branchi.

**Pre-merge gate:** Zodpovědět DOMAIN-AUDIT Open Q #2 + #3 + #12 (migration policy pro
existující `synapse.pack.v2` soubory po canonical-source landingu).

---

*Created: 2026-02-19*
*Last Updated: 2026-05-02 — added Domain Audit Findings section*
