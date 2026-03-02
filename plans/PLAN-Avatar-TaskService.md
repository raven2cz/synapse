# Plan 2: AvatarTaskService — Multi-Task AI Architecture

> **Predecessor:** Plan 1 (avatar.yaml relocation + src/ai/ cleanup) — ✅ DONE
> **Scope:** Generalizace AvatarAIService na multi-task službu s registry, skill-based prompty a fallback řetězci.
> **Kvalita:** Medical device grade — 100% spolehlivost, graceful degradation, vždy manuální alternativa.
> **Status:** ✅ DONE (2026-02-27) — 1615 testů, 0 failures, 3 bugy nalezeny a opraveny.

## Context

`AvatarAIService` ~~je single-purpose — umí jen parameter extraction~~ byl refaktorován na `AvatarTaskService` s generickým `execute_task()`. Specifikace (`PLAN-AI-Services.md` §1.2) definuje 8 task typů. Každý task potřebuje:

1. **AI cestu** — avatar-engine s task-specific system promptem (skill markdown)
2. **Polo-automatickou cestu** — rule-based/heuristická alternativa (regexp, lookup table)
3. **Manuální cestu** — GUI pro ruční zadání (EditParametersModal, EditDependenciesModal, atd.)

✅ Infrastruktura pro libovolný počet task typů je hotová. Implementovány 2 tasky: `parameter_extraction` a `model_tagging`.

## Ověřené předpoklady (praktické testy)

| Test | Výsledek |
|------|----------|
| Engine restart s jiným system promptem | ✅ Funguje, restart 1.7s |
| Markdown skill jako system prompt | ✅ Validní JSON output |
| Provider kompatibilita (stejný prompt) | ✅ Gemini + Codex = identické klíče (100% shoda) |
| Claude z avatar-engine | ✅ Funguje v produkci (nelze testovat z nested session) |
| Full pipeline: TaskService → GenerationParameters → pack.json → reload | ✅ 4 dedikované testy |

---

## Architektura ✅

### Přehled

```
                    ┌─────────────────────────────────┐
                    │         AvatarTaskService        │
                    │   (one service, many task types) │
                    └──────────┬──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
    │  TaskRegistry  │ │   AICache    │ │ AvatarEngine │
    │  (instance,    │ │ (shared,     │ │ (lazy, one   │
    │   injected     │ │  per-task    │ │  at a time,  │
    │   into service)│ │  key prefix) │ │  lock covers │
    └────────────────┘ └──────────────┘ │  full exec)  │
                                        └──────────────┘
```

### Task = Skill markdown + Python handler

Každý task type se skládá ze dvou částí:

**1. Skill markdown** (`config/avatar/skills/*.md`) — domain knowledge + task instructions
**2. Python handler** (`src/avatar/tasks/*.py`) — parse, validate, fallback

### Engine lifecycle — thread-safe execution

- **Jeden engine** (ne pool) — lazy singleton
- Engine trackuje `_current_task_type`
- Při změně task typu: `stop() → None → new engine → start()` (1.7s)
- Při stejném task typu: reuse (0ms overhead)
- **KRITICKÉ:** Lock pokrývá celý cyklus `_ensure_engine + chat_sync()` (ne jen engine swap)
- Double-call race guard: re-check cache po získání locku

### Fallback řetězec (3 úrovně)

```
1. AI (avatar-engine)     → task-specific prompt → structured JSON
   ↓ (failure)
2. Semi-automatic         → rule-based regexp, lookup table, heuristic
   ↓ (failure/unavailable)
3. Manual GUI             → EditParametersModal, EditDependenciesModal, atd.
```

### Cache klíč

Formát: `{task_type}:{provider}:{model}:{input_data}` → interně hashováno přes `AICache.get_cache_key()` (SHA-256[:16])

- Cache ukládá **čistá data** (bez `_extracted_by` metadata)
- `_enrich_output()` přidává metadata **po** čtení z cache (vytváří kopii — mutation-safe)
- Sdílený `AICache`, TTL a `cache_enabled` z `config.extraction`

---

## Implementace ✅

### Krok 1: Rozšířit `AITask` ABC ✅

**Soubor:** `src/avatar/tasks/base.py`

- `SKILL_NAMES: tuple = ()` (immutable tuple)
- `build_system_prompt(skills_content)` — abstract
- `get_fallback()` — optional, default None
- `get_cache_prefix()` — returns `task_type`

### Krok 2: Vytvořit TaskRegistry ✅

**Soubor:** `src/avatar/tasks/registry.py`

- Instance-level (ne class-level singleton) — předchází test pollution
- `register()`, `get()`, `list_tasks()`, `reset()`
- `get_default_registry()` auto-registers `ParameterExtractionTask` + `ModelTaggingTask`

### Krok 3: Vytvořit AvatarTaskService ✅

**Soubor:** `src/avatar/task_service.py`

- `execute_task(task_type, input_data, use_cache)` → generická metoda
- `_ensure_engine_for_task(task)` → engine lifecycle management
- `_load_skills(skill_names)` → čte skill markdown
- `_enrich_output(output, provider_id)` → přidává `_extracted_by` + `_ai_fields` (kopie, ne mutace)
- `_extract_json(text)` → parsuje JSON z AI odpovědi (přímý, markdown fence, brace matching)
- `extract_parameters()` convenience wrapper

### Krok 4: ParameterExtractionTask ✅

**Soubor:** `src/avatar/tasks/parameter_extraction.py`

- `SKILL_NAMES = ("generation-params",)`
- `build_system_prompt()` = V2 prompt + skills
- `parse_result()` = strip `_` keys
- `get_fallback()` = `RuleBasedProvider` regexp

### Krok 5: ModelTaggingTask ✅

**Soubor:** `src/avatar/tasks/model_tagging.py`

- `SKILL_NAMES = ("model-tagging",)`
- Extrahuje: category, content_types, tags, trigger_words, base_model_hint
- `parse_result()` = normalizace (case, lists, known categories)
- `get_fallback()` = keyword-matching s priority ordering (list of tuples)

### Krok 6: Aktualizovat volající kód ✅

| Místo | Soubor | Stav |
|-------|--------|------|
| Pack import | `src/store/pack_service.py:536` | ✅ `from src.avatar.ai_service import AvatarAIService` (backward compat) |
| PATCH params | `src/store/api.py:3406` | ✅ |
| AI extract | `src/store/api.py:5136` | ✅ |
| AI cache | `src/store/api.py:5156-5188` | ✅ |
| Backward compat | `src/avatar/ai_service.py` | ✅ Re-export only (no class definitions) |

### Krok 7: Task list API endpoint ✅

**Soubor:** `src/store/api.py` — `GET /api/ai/tasks`

### Krok 8: Dokumentace ✅

- `config/avatar.yaml.example` — engine.tasks komentář
- `docs/avatar/` — aktualizace
- Architecture guards v `tests/lint/test_architecture.py`

---

## Soubory — souhrn změn ✅

| Soubor | Akce | Stav |
|--------|------|------|
| `src/avatar/tasks/base.py` | EDIT | ✅ `SKILL_NAMES`, `build_system_prompt`, `get_fallback` |
| `src/avatar/tasks/registry.py` | NEW | ✅ Instance-level TaskRegistry |
| `src/avatar/tasks/parameter_extraction.py` | EDIT | ✅ Full task implementation |
| `src/avatar/tasks/model_tagging.py` | NEW | ✅ Second real task type |
| `src/avatar/tasks/__init__.py` | EDIT | ✅ Exports |
| `src/avatar/task_service.py` | NEW | ✅ AvatarTaskService + `_extract_json()` |
| `src/avatar/ai_service.py` | EDIT | ✅ Backward compat re-export only |
| `src/avatar/cache.py` | EDIT | ✅ Shared cache |
| `src/avatar/providers/rule_based.py` | EDIT | ✅ Standalone fallback |
| `src/store/pack_service.py` | EDIT | ✅ Import update |
| `src/store/api.py` | EDIT | ✅ Import updates + `/tasks` endpoint |
| `config/avatar.yaml.example` | EDIT | ✅ engine.tasks komentář |

---

## Nalezené a opravené bugy

### Bug #1: Double `parse_result()` na cache hit ✅
Cache ukládá už naparsovaná data. Na cache hit se volal `parse_result()` znova — pro `ParameterExtractionTask` to stripovalo `_` klíče, pak se metadata přidávala znovu. Pro non-idempotent tasky by to bylo destruktivní.

**Oprava:** Cache hit přeskakuje `parse_result()`. Nový `_enrich_output()` přidává metadata po čtení z cache (vytváří kopii).

### Bug #2: Fallback chybějící `_extracted_by` metadata ✅
AI cesta přidávala `_extracted_by` a `_ai_fields`, ale fallback cesta ne. Frontend `PackParametersSection.tsx` spoléhá na tato metadata.

**Oprava:** `_enrich_output()` se volá i po fallback výsledku.

### Bug #3: Keyword priority v `_extract_tags_by_keywords()` ✅
"Concept art style illustrations" matchoval "illustration" místo "concept-art" kvůli pořadí iterace v dict.

**Oprava:** Změna z dict na list of tuples s multi-word kategoriemi na prvním místě.

---

## Testy ✅

### Celkem: 174 avatar-specifických testů (z 1615 celkem)

### Unit testy

| Soubor | Počet | Pokrytí |
|--------|-------|---------|
| `test_task_service.py` | 36 | execute_task, cache, fallback, engine lifecycle, _extract_json |
| `test_parameter_extraction_task.py` | 20 | build_system_prompt, parse_result, validate, fallback |
| `test_model_tagging_task.py` | 36 | build_system_prompt, parse_result, validate, keyword fallback |
| `test_task_registry.py` | 13 | register, get, list, reset, default registry, isolation |
| `test_cache.py` | — | Existující cache testy |
| `test_rule_based.py` | — | Existující regexp testy |

### Integration / Workflow testy

| Soubor | Počet | Pokrytí |
|--------|-------|---------|
| `test_task_service_workflows.py` | 29 | Multi-task round-trip, metadata konzistence, cache integrity, engine lifecycle, fallback chain, parse_result contract, GenerationParameters pipeline |
| `test_task_service_adversarial.py` | 33 | Black-box testy navržené Gemini + Codex: cache bypass, thundering herd, error recovery, input canonicalization, registry integrity |
| `test_avatar_ai_service.py` | 10 | Backward compat, extraction flow |
| `test_avatar_ai_smoke.py` | 10 | Realistic extraction, cache verification |
| `test_import_parameters.py` | 8 | PackService import → extraction → GenerationParameters → persist |

### Architecture guards

| Test | Soubor |
|------|--------|
| `test_no_legacy_ai_imports` | `test_architecture.py` |
| `test_task_service_no_legacy_ai_imports` | `test_architecture.py` |
| `test_ai_service_is_reexport_only` | `test_architecture.py` |
| `test_default_registry_has_parameter_extraction` | `test_architecture.py` |
| `test_default_registry_has_model_tagging` | `test_architecture.py` |

### E2E

| Test | Soubor |
|------|--------|
| `GET /api/ai/tasks` returns registered task types | `avatar-api.spec.ts` |

---

## Verifikace ✅

```
./scripts/verify.sh → 1615 passed, 0 failed, all checks green
```

---

## Budoucí rozšíření (OTEVŘENÉ)

### ❌ MCP tools v task service

Aktuálně `AvatarTaskService` spouští engine **bez MCP serverů** — čistě system prompt + skill markdown + jeden vstup → jeden JSON výstup. Ale `AvatarEngine` podporuje `mcp_servers` přes kwargs:

```python
# avatar_engine/engine.py:690
if self._kwargs.get("mcp_servers"):
    common["mcp_servers"] = self._kwargs["mcp_servers"]
```

Pro složitější tasky by task mohl předat MCP:
```python
engine = AvatarEngine(
    provider="gemini",
    system_prompt=task_prompt,
    mcp_servers={"synapse-store": {...}},  # ← task volá MCP tools
)
```

**Use cases kde to dává smysl:**
- `workflow_compatibility` — potřebuje volat `scan_workflow` + `check_workflow_availability`
- `dependency_resolution` — potřebuje `resolve_workflow_dependencies` + `find_model_by_hash`
- `recommendations` — potřebuje `search_civitai` + `get_pack_details`

**Co by to vyžadovalo:**
- Rozšířit `AITask` o `mcp_servers: Dict = {}` nebo `needs_mcp: bool = False`
- `_ensure_engine_for_task()` předá MCP config do `AvatarEngine(**kwargs)`
- Timeout management — MCP volání jsou pomalejší než pure prompt
- Test coverage pro MCP-enabled tasky (mock MCP server)

### ❌ User-facing avatar volá task service

Aktuálně existují dva izolované systémy:
1. **User-facing avatar** — mounted na `/api/avatar/engine/`, dlouhodobá session s MCP, uživatel chatuje
2. **Task service** — Python třída, programatické one-shot volání z backendu

Mohly by se propojit přes MCP tool v user-facing avataru:
```python
@mcp.tool()
def extract_parameters(pack_name: str) -> str:
    """Extract generation parameters for a pack using AI."""
    service = AvatarTaskService()
    pack = store.get_pack(pack_name)
    result = service.extract_parameters(pack.description)
    return json.dumps(result.output)
```

Uživatel by pak mohl říct _"extrahuj parametry pro model XY"_ a avatar by pod kapotou zavolal task service. **Ale není to očekávaný primární use case** — tasky jsou pro automatizované operace (import pack → extrahuj parametry → ulož), user-facing avatar je konverzační.

### ❌ Per-task cache konfigurace

Všechny tasky sdílejí `config.extraction.cache_enabled` a `cache_ttl_days`. Pro různé tasky může dávat smysl jiný TTL:
- `parameter_extraction` — 30 dní (stabilní výsledky)
- `model_tagging` — 30 dní (stabilní)
- `recommendations` — 1 den (dynamická data)
- `workflow_compatibility` — 7 dní (závisí na instalovaných nodech)

**Co by to vyžadovalo:**
- `AITask.cache_ttl_override: Optional[int] = None`
- `execute_task()` použije task-specific TTL pokud je definovaný
- Sekce `engine.tasks.<task_type>.cache_ttl_days` v avatar.yaml

### ❌ Zbývající task typy ze specifikace

Ze specifikace `PLAN-AI-Services.md` §1.2 zbývá:
- `description_translation` — překlad popisů modelů
- `workflow_compatibility` — kontrola kompatibility workflow s instalovanými modely
- `preview_analysis` — analýza preview obrázků (multimodal)
- `recommendations` — doporučení modelů na základě stylu/workflow
- `config_migration` — migrace konfigurací mezi verzemi
- `auto_dependencies` — automatické řešení závislostí

Infrastruktura (TaskRegistry, AITask ABC, fallback chain, cache) je připravená — pro každý nový task stačí:
1. Skill markdown v `config/avatar/skills/`
2. Python handler v `src/avatar/tasks/`
3. Registrace v `get_default_registry()`
