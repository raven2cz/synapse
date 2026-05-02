Reading additional input from stdin...
OpenAI Codex v0.128.0 (research preview)
--------
workdir: /home/box/git/github/synapse
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, /home/box/.codex/memories]
reasoning effort: high
reasoning summaries: none
session id: 019de83f-fb87-7d00-8aa5-9d43f981bd67
--------
user
AUDIT TASK — Synapse Release 1, point 1: feat/resolve-model-redesign branch.

CONTEXT:
- Branch contains 26 commits, ~22k LOC, 6 phases — finding exact models for dependencies (Civitai/HF/Local Resolve, AI scoring, evidence providers, preview analysis).
- IMPORTANT: branch is on local copy, but we suspect last commit is on ANOTHER MACHINE (not pushed). Audit only what's available here.
- Main spec: plans/PLAN-Resolve-Model.md (v0.7.1, 1769 lines, on the branch).
- We are currently on 'main' branch. The resolve-model branch is checked out as 'feat/resolve-model-redesign'.

YOUR JOB — Audit the resolve redesign as it exists locally:

READ (use git to access branch — these files might be on the branch only):
  git show feat/resolve-model-redesign:plans/PLAN-Resolve-Model.md
  git show feat/resolve-model-redesign:src/store/resolve_service.py
  git show feat/resolve-model-redesign:src/store/resolve_models.py
  git show feat/resolve-model-redesign:src/store/resolve_config.py
  git show feat/resolve-model-redesign:src/store/evidence_providers.py
  git show feat/resolve-model-redesign:src/store/enrichment.py
  git show feat/resolve-model-redesign:src/store/local_file_service.py
  git show feat/resolve-model-redesign:src/store/hash_cache.py
  git show feat/resolve-model-redesign:src/avatar/tasks/dependency_resolution.py (or similar)
  git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx
  git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx
  git show feat/resolve-model-redesign:apps/web/e2e/resolve-dependency.spec.ts
  git show feat/resolve-model-redesign:apps/web/e2e/helpers/resolve.helpers.ts

You can also: git diff main..feat/resolve-model-redesign --stat to see all changes.

JOB:

1. PHASE COVERAGE — Phases 0-6: status of each according to PLAN-Resolve-Model.md vs reality in code.

2. EVIDENCE PROVIDERS — Civitai hash, HF LFS OID, local hash, AI evidence — implemented? wired into the resolver chain? Missing pieces?

3. UI INTEGRATION — DependencyResolverModal: Civitai tab, HuggingFace tab, Local Resolve tab, Apply, AI gate. What is integrated, what is mocked?

4. PREVIEW ANALYSIS — Tab + hint enrichment — actually wired or test-only?

5. AI INTEGRATION — DependencyResolutionTask, AIEvidenceProvider — does it call avatar-engine? Fallback when AI off?

6. TESTS — unit + integration + smoke + E2E. Real coverage vs ceremonial.

7. SPEC vs CODE — gaps in PLAN-Resolve-Model.md not yet implemented.

8. REFACTOR CANDIDATES — what is overcomplicated, duplicated, or unclear.

9. OPEN QUESTIONS for owner.

Output: markdown ~300-600 lines, file:line refs, NEEDS VERIFICATION marks.
deprecated: `[features].collab` is deprecated. Use `[features].multi_agent` instead.
Enable it with `--enable multi_agent` or `[features].multi_agent` in config.toml. See https://developers.openai.com/codex/config-basic#feature-flags for details.
codex
I’ll audit the branch without switching away from `main`, using `git show` and targeted searches so I don’t disturb the working tree. I’m starting with the plan, diff stat, and the core resolver files to map spec phases to code.
exec
/bin/bash -lc "git show feat/resolve-model-redesign:plans/PLAN-Resolve-Model.md | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	# PLAN: Resolve Model Redesign
     2	
     3	**Version:** v0.11.0 — Phase 0+1+2+2.5+3+4 COMPLETE
     4	**Status:** Phase 4 DOKONCENA — cleanup + validace hotovo
     5	**Priority:** HIGH
     6	**Created:** 2026-03-07
     7	**Author:** raven2cz + Claude Opus 4.6
     8	**Branch:** feat/resolve-model-redesign
     9	**Reviews:** Gemini 3.1 (2x), Codex 5.4 (3x) — vsechny zapracovany + implementation map
    10	
    11	---
    12	
    13	## 1. Cil
    14	
    15	Kompletni redesign systemu pro resolvovani model dependencies v packach.
    16	Resolver slouzi pro VSECHNY typy dependencies (checkpoint, LoRA, VAE, controlnet,
    17	embedding, upscaler) — ne jen base model.
    18	
    19	Modely mohou byt na **Civitai, HuggingFace, nebo lokalne**. System prohledava
    20	vsechny relevantni zdroje a preferuje konkretni signaly nad obecnymi.
    21	
    22	---
    23	
    24	## 2. Architekturni principy
    25	
    26	### 2a. Suggest / Apply — jadro celeho systemu
    27	
    28	Kazda resolve cesta (AI, manualni, lokalni, import) prochazi dvema kroky:
    29	
    30	```
    31	suggest_resolution(pack, dep_id, context)
    32	    -> List[ResolutionCandidate]
    33	
    34	apply_resolution(pack, dep_id, candidate_id)
    35	    -> Jediny write path pres pack_service
    36	```
    37	
    38	**Pravidla:**
    39	- AI NIKDY primo mutuje `pack.json` / `pack.lock.json`
    40	- Kazdy kandidat ma stabilni `candidate_id` (UUID) — NE index
    41	- Apply prijima `candidate_id`, ne pozici v seznamu (suggestions se mohou zmenit)
    42	- Manualni resolve (Civitai/HF/Local tab) taky produkuje ResolutionCandidate
    43	  a prochazi apply — zadna specialni cesta
    44	- Import: auto-apply pokud JEDEN dominantni kandidat s confidence v TIER-1/TIER-2
    45	  a zadny dalsi kandidat v rozmezi 0.15 confidence
    46	- Import: vice kandidatu s podobnou confidence → mark "unresolved" pro UI
    47	
    48	### 2b. Evidence Ladder — hierarchie dle KONKRETNOSTI
    49	
    50	Klicovy princip: **cim konkretnejsi signal, tim vyssi priorita.**
    51	
    52	Evidence je organizovana do **neprekryvajicich se confidence tier:**
    53	
    54	```
    55	TIER-1 (0.90 - 1.00) — Jednoznacna identifikace
    56	  E1: Hash match         SHA256 nalezen na Civitai nebo HuggingFace
    57	
    58	TIER-2 (0.75 - 0.89) — Presna identifikace z pouziti
    59	  E2: Preview embedded   ComfyUI workflow / A1111 params z PNG chunks
    60	  E3: Preview API meta   meta.Model / meta.resources z Civitai API
    61	
    62	TIER-3 (0.50 - 0.74) — Stredni jistota
    63	  E5: File metadata      Filename patterns, architecture detection
    64	  E6: Configured aliases store.yaml mapping → Civitai nebo HF cil
    65	
    66	TIER-4 (0.30 - 0.49) — Vodítko, ne resolve
    67	  E4: Source metadata    Civitai baseModel ("SDXL", "SD 1.5") — kategorie, ne model
    68	  (POZN: E4/E5 cislovani z historickych duvodu — E5 je konkretnejsi nez E4)
    69	
    70	TIER-AI (0.50 - 0.89) — AI doplnuje, NIKDY neprebije TIER-1
    71	  E7: AI analysis        Cross-reference, Civitai+HF search, reasoning
    72	                         Confidence OMEZENA na max(TIER-2) = 0.89
    73	                         AI NEMUZE prekrocit TIER-1 (hash match)
    74	```
    75	
    76	**Scoring pravidla:**
    77	- Kazdy evidence item produkuje confidence STRIKTNE v ramci sveho tieru
    78	- AI je omezena ceiling na 0.89 — nemuze prekrocit hash match
    79	- Kombinovani vice signalu: **provenance grouping** (viz 2g)
    80	- Konflikty (E2 rika jiny model nez E3) → snizit confidence obou, nabidnout oba kandidaty
    81	- Auto-apply: kandidat musi byt v TIER-1 nebo TIER-2 a zadny jiny kandidat
    82	  nesmi byt v rozmezi 0.15 confidence
    83	
    84	### 2c. Provider Eligibility per AssetKind
    85	
    86	NE "vzdy oba providery", ale **dle relevance** pro dany typ:
    87	
    88	| AssetKind | Civitai search | HF search | HF hash lookup | Poznamka |
    89	|-----------|---------------|-----------|----------------|----------|
    90	| checkpoint | Yes | Yes | Yes (LFS pointer) | Zakladni modely casto na HF |
    91	| lora | Yes | No | No | HF LoRA ekosystem je minimalni |
    92	| vae | Yes | Yes | Limited | Nektere VAE na HF (kl-f8, mse) |
    93	| controlnet | Yes | Yes | Limited | ControlNet repos na HF |
    94	| embedding | Yes | No | No | Prevazne Civitai |
    95	| upscaler | Yes | Limited | No | Nektere upscalery na HF |
    96	
    97	**Pravidla:**
    98	- `suggest_resolution()` prohledava JEN eligible providery pro dany AssetKind
    99	- Zabranuje zbytecne latenci a sumu u nepodporovanych kombinaci
   100	- Konfigurovatelne v `resolve_config.py` — rozsiritelne
   101	
   102	### 2d. HuggingFace Discovery — realisticky design
   103	
   104	HF discovery je fundamentalne OBTIZNEJSI nez Civitai:
   105	- HF NEMA hash lookup API (jako Civitai `find_model_by_hash`)
   106	- HF search API (`/api/models`) filtruje dle tags, ale NE dle SHA256
   107	- Mnoho modelu je v single-file repos (ne diffusers), ktere `filter: "diffusers"` mine
   108	- SHA256 je dostupna jen z LFS pointeru (nutno fetchnout pointer, ne cely soubor)
   109	
   110	**Strategie pro HF resolve:**
   111	
   112	1. **Filename-based search** (bez AI)
   113	   - Z preview metadata: `ckpt_name: "illustriousXL_v060.safetensors"`
   114	   - Vyhledat na HF API: `/api/models?search=illustriousXL`
   115	   - Profiltrovat vysledky dle file extension a AssetKind
   116	   - Nizsi confidence (TIER-3) — filename neni jednoznacny
   117	
   118	2. **Known repos mapping** (bez AI)
   119	   - Staticka mapa znamych modelu: `"SD 1.5" → runwayml/stable-diffusion-v1-5`
   120	   - Soucasti `base_model_aliases` v store.yaml
   121	   - Confidence dle presnosti shody
   122	
   123	3. **AI-assisted discovery** (s avatarem)
   124	   - AI je pro HF discovery NEJEFEKTIVNEJSI nastroj
   125	   - Umi interpretovat: model cards, repo README, file strukturu
   126	   - MCP tool `search_huggingface` (novy) + existujici znalosti
   127	   - Pokud vice AI provideru dostupnych: zkusit vice (fallback chain)
   128	   - AI muze cross-referencovat nalezeny HF repo s Civitai daty
   129	
   130	4. **LFS pointer SHA256 verification** (post-discovery)
   131	   - Po nalezeni kandidata: fetch LFS pointer (male HTTP request, ne cely model)
   132	   - Extrahovat SHA256 z pointer souboru
   133	   - Porovnat s hash z evidence → potvrdi/vyvrati kandidata
   134	   - Zvysi confidence na TIER-1 pokud hash sedi
   135	
   136	**Realita:** Pro nove/neznáme modely na HF je AI prakticky JEDINA cesta.
   137	Deterministicke metody (search, aliases) pokryvaji jen známe modely.
   138	
   139	### 2e. Preview Image Metadata — pravidla extrakce
   140	
   141	Preview obrazky obsahuji nejpresnejsi data o skutecne pouzitem modelu.
   142	Ale ne vsechna data jsou primo pouzitelna.
   143	
   144	**Zdroj 1: Civitai API metadata (uz mame v sidecar .json!)**
   145	- `meta.Model` / `meta.model_name` → checkpoint name
   146	- `meta.resources[]` → seznam pouzitych modelu (checkpoint, LoRA, VAE...)
   147	  s `name`, `type`, `weight`, nekdy `hash`
   148	
   149	**Zdroj 2: PNG embedded metadata (vyzaduje parser)**
   150	- A1111: `tEXt[parameters]` → "Model: dreamshaper_8, ..."
   151	- ComfyUI: `tEXt[prompt]` → JSON workflow → `CheckpointLoaderSimple.ckpt_name`
   152	- **POZOR:** Civitai CDN muze stripovat PNG chunks (nutne overit v Phase 0)
   153	
   154	**Normalizace a filtrovani (C3, C6):**
   155	
   156	```python
   157	class PreviewModelHint:
   158	    filename: str              # "illustriousXL_v060.safetensors"
   159	    kind: Optional[AssetKind]  # checkpoint, lora, vae... (z ComfyUI node type)
   160	    source_image: str          # Ktery preview image
   161	    source_type: Literal["api_meta", "png_embedded"]
   162	    raw_value: str             # Surova hodnota pro debug
   163	    resolvable: bool           # False pokud privatni/neznamy format
   164	```
   165	
   166	**Pravidla:**
   167	- **Kind-aware filtrovani:** Pokud resolvujeme checkpoint, pouzit JEN checkpoint hints
   168	- **Provenance grouping:** E2 a E3 z TEHOZ obrazku = JEDEN evidence group.
   169	  Pokud oba rikaji "illustriousXL_v060" → confidence se nepocita 2x,
   170	  pouzije se VYSSI z nich (E2 > E3 v hierarchii)
   171	- **Unresolvable stav:** Pokud filename nenalezen na zadnem provideru
   172	  a nevyhovuje zadnemu aliasu → oznacit hint jako `resolvable: false`,
   173	  nezapocitavat do confidence
   174	- **Private/custom modely:** Filename jako "my_custom_merge_v3" pravdepodobne
   175	  neexistuje remote → nizka confidence, neauto-applyovat
   176	
   177	### 2f. Genericka resolve architektura
   178	
   179	```
   180	POST /api/packs/{name}/dependencies/{dep_id}/suggest
   181	  Body: { include_ai?: bool, analyze_previews?: bool }
   182	  -> { candidates: List[ResolutionCandidate], request_id: str }
   183	
   184	POST /api/packs/{name}/dependencies/{dep_id}/apply
   185	  Body: { candidate_id: str }   # UUID z suggest response
   186	  -> Aktualizuje pack.json + pack.lock PRES pack_service
   187	
   188	Pro manualni resolve (uzivatel vybral z Civitai/HF/Local tabu):
   189	POST /api/packs/{name}/dependencies/{dep_id}/apply
   190	  Body: { manual: { strategy, selector_data, canonical_source? } }
   191	  -> Validace pres validation matrix → apply pres pack_service
   192	  -> Manualni data TAKY prochazi validaci (min fields, kompatibilita)
   193	```
   194	
   195	**candidate_id vs candidate_index (C4):**
   196	- Suggest vraci kandidaty s UUID `candidate_id`
   197	- Backend si drzi candidates v krat. cache (TTL 5min, keyed by request_id)
   198	- Apply pouziva `candidate_id` — stabilni i kdyz se suggestions mezi tim zmenily
   199	- Pokud candidate_id expired → 409 Conflict, frontend znovu zavola suggest
   200	
   201	### 2g. Provenance Grouping a Scoring
   202	
   203	**Problem (C6):** E2 (PNG embedded) a E3 (API meta) z tehoz preview obrazku
   204	popisuji STEJNOU skutecnost. Bez groupingu se stejna informace pocita 2x.
   205	
   206	**Reseni:**
   207	
   208	```python
   209	class EvidenceGroup:
   210	    """Evidence items z tehoz zdroje (napr. jeden preview image)."""
   211	    provenance: str        # "preview:preview_001.png"
   212	    items: List[EvidenceItem]
   213	    combined_confidence: float  # max(item.confidence) v ramci skupiny
   214	
   215	# Scoring:
   216	# 1. Seskupit evidence dle provenance
   217	# 2. Kazda skupina prispiva svym combined_confidence (max, ne soucet)
   218	# 3. Nezavisle skupiny se kombinuji Noisy-OR:
   219	#    P(correct) = 1 - product(1 - group.confidence for group in groups)
   220	# 4. Final confidence JE OMEZENA tier stropem nejlepsiho evidence
   221	#    (hash match → max 1.0, preview → max 0.89, alias → max 0.74)
   222	```
   223	
   224	**Priklad:**
   225	- Preview image 1: E2=0.85 (ComfyUI workflow), E3=0.82 (API meta) → group confidence = 0.85
   226	- Preview image 2: E3=0.78 (API meta jiny obrazek) → group confidence = 0.78
   227	- Combined: 1 - (1-0.85)*(1-0.78) = 0.967 → ale ceiling = 0.89 (TIER-2) → final = 0.89
   228	- Pokud pridame E1 hash match: ceiling = 1.0 → final = 0.967
   229	
   230	### 2h. Cross-Kind Compatibility Validation (G2)
   231	
   232	`apply_resolution()` validuje kompatibilitu resolvovane dependency s packem:
   233	
   234	```python
   235	COMPATIBILITY_RULES = {
   236	    # base_model_category → compatible_categories
   237	    "SD 1.5": {"SD 1.5"},
   238	    "SDXL": {"SDXL", "Pony"},   # Pony je SDXL-based
   239	    "Illustrious": {"SDXL", "Illustrious"},
   240	    "Flux": {"Flux"},
   241	    "SD 3.5": {"SD 3.5"},
   242	}
   243	```
   244	
   245	**Pravidla:**
   246	- Pokud pack.base_model = "SDXL" a resolvovana LoRA je pro "SD 1.5" → WARNING
   247	- Warning neblokuje apply (uzivatel muze overridnout) ale zobrazi se v UI
   248	- Pro checkpoint/base model resolve: zadna kompatibilita (je to sam base model)
   249	- Mapping je konfigurovatelny v store.yaml
   250	
   251	### 2i. Dual-source model pro local binding
   252	
   253	```python
   254	class DependencySelector(BaseModel):
   255	    strategy: SelectorStrategy
   256	    civitai: Optional[CivitaiSelector] = None
   257	    huggingface: Optional[HuggingFaceSelector] = None
   258	    base_model: Optional[str] = None
   259	    url: Optional[str] = None
   260	    local_path: Optional[str] = None

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_service.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	ResolveService — orchestration for dependency resolution.
     3	
     4	9th service in Store facade. Suggest/Apply two-phase pattern.
     5	Based on PLAN-Resolve-Model.md v0.7.1 section 11e.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import hashlib
    11	import json
    12	import logging
    13	import time
    14	from collections import defaultdict
    15	from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable
    16	
    17	from .models import (
    18	    AssetKind,
    19	    DependencySelector,
    20	    SelectorStrategy,
    21	)
    22	from .resolve_config import check_cross_kind_compatibility, get_kind_config, get_tier_for_confidence
    23	from .resolve_models import (
    24	    ApplyResult,
    25	    CandidateSeed,
    26	    EvidenceGroup,
    27	    EvidenceHit,
    28	    ManualResolveData,
    29	    PreviewModelHint,
    30	    ResolveContext,
    31	    ResolutionCandidate,
    32	    SuggestOptions,
    33	    SuggestResult,
    34	)
    35	from .resolve_scoring import group_by_provenance, score_candidate
    36	from .resolve_validation import validate_before_apply, validate_selector_fields
    37	
    38	logger = logging.getLogger(__name__)
    39	
    40	# Cache TTL: 5 minutes
    41	CACHE_TTL_SECONDS = 300
    42	
    43	
    44	@runtime_checkable
    45	class CandidateCacheStore(Protocol):
    46	    """Abstraction for candidate cache — injectable, testable."""
    47	
    48	    def store(
    49	        self, request_id: str, fingerprint: str,
    50	        candidates: List[ResolutionCandidate],
    51	    ) -> None: ...
    52	
    53	    def get(
    54	        self, request_id: str, candidate_id: str,
    55	    ) -> Optional[ResolutionCandidate]: ...
    56	
    57	    def check_fingerprint(
    58	        self, request_id: str, fingerprint: str,
    59	    ) -> bool: ...
    60	
    61	    def cleanup_expired(self) -> None: ...
    62	
    63	
    64	class InMemoryCandidateCache:
    65	    """Default in-process cache. TTL 5min. With fingerprint check."""
    66	
    67	    def __init__(self, ttl: float = CACHE_TTL_SECONDS):
    68	        self._ttl = ttl
    69	        self._store: Dict[str, Dict[str, Any]] = {}
    70	
    71	    def store(
    72	        self, request_id: str, fingerprint: str,
    73	        candidates: List[ResolutionCandidate],
    74	    ) -> None:
    75	        self._store[request_id] = {
    76	            "fingerprint": fingerprint,
    77	            "candidates": {c.candidate_id: c for c in candidates},
    78	            "stored_at": time.time(),
    79	        }
    80	
    81	    def get(
    82	        self, request_id: str, candidate_id: str,
    83	    ) -> Optional[ResolutionCandidate]:
    84	        entry = self._store.get(request_id)
    85	        if entry is None:
    86	            return None
    87	        if time.time() - entry["stored_at"] > self._ttl:
    88	            del self._store[request_id]
    89	            return None
    90	        return entry["candidates"].get(candidate_id)
    91	
    92	    def check_fingerprint(self, request_id: str, fingerprint: str) -> bool:
    93	        entry = self._store.get(request_id)
    94	        if entry is None:
    95	            return False
    96	        return entry["fingerprint"] == fingerprint
    97	
    98	    def cleanup_expired(self) -> None:
    99	        now = time.time()
   100	        expired = [
   101	            k for k, v in self._store.items()
   102	            if now - v["stored_at"] > self._ttl
   103	        ]
   104	        for k in expired:
   105	            del self._store[k]
   106	
   107	    def find_by_candidate_id(
   108	        self, candidate_id: str,
   109	    ) -> Optional[ResolutionCandidate]:
   110	        """Search all non-expired requests for a candidate by ID."""
   111	        now = time.time()
   112	        for entry in self._store.values():
   113	            if now - entry["stored_at"] > self._ttl:
   114	                continue
   115	            c = entry["candidates"].get(candidate_id)
   116	            if c:
   117	                return c
   118	        return None
   119	
   120	
   121	class ResolveService:
   122	    """Orchestration for dependency resolution.
   123	
   124	    9th service in Store facade.
   125	    Does NOT hold own clients — accesses through pack_service (R2).
   126	    Does NOT know PackService backwards — unidirectional flow (R1).
   127	    Avatar through getter callable (R3).
   128	    """
   129	
   130	    def __init__(
   131	        self,
   132	        layout: Any,  # StoreLayout
   133	        pack_service: Any,  # PackService
   134	        avatar_getter: Callable[[], Any] = lambda: None,
   135	        providers: Optional[Dict[str, Any]] = None,
   136	        candidate_cache: Optional[CandidateCacheStore] = None,
   137	        config_getter: Optional[Callable[[], Any]] = None,
   138	    ):
   139	        self._layout = layout
   140	        self._pack_service = pack_service
   141	        self._avatar_getter = avatar_getter
   142	        self._providers = providers
   143	        self._cache = candidate_cache or InMemoryCandidateCache()
   144	        self._config_getter = config_getter
   145	
   146	    def _ensure_providers(self) -> None:
   147	        """Lazy init. Providers use getters, not direct references."""
   148	        if self._providers is not None:
   149	            return
   150	        from .evidence_providers import (
   151	            AIEvidenceProvider,
   152	            AliasEvidenceProvider,
   153	            FileMetaEvidenceProvider,
   154	            HashEvidenceProvider,
   155	            PreviewMetaEvidenceProvider,
   156	            SourceMetaEvidenceProvider,
   157	        )
   158	        ps_getter = lambda: self._pack_service
   159	        layout_getter = lambda: self._layout
   160	        self._providers = {
   161	            "hash_match": HashEvidenceProvider(ps_getter),
   162	            "preview_meta": PreviewMetaEvidenceProvider(ps_getter),
   163	            "file_meta": FileMetaEvidenceProvider(),
   164	            "alias": AliasEvidenceProvider(layout_getter),
   165	            "source_meta": SourceMetaEvidenceProvider(),
   166	            "ai": AIEvidenceProvider(self._avatar_getter, config_getter=self._config_getter),
   167	        }
   168	
   169	    def suggest(
   170	        self,
   171	        pack: Any,
   172	        dep_id: str,
   173	        options: Optional[SuggestOptions] = None,
   174	    ) -> SuggestResult:
   175	        """Suggest resolution candidates for a dependency.
   176	
   177	        1. Build ResolveContext
   178	        2. Run providers (by tier order, only supports()==True)
   179	        3. Merge EvidenceHit by candidate.key
   180	        4. Score (Noisy-OR with provenance grouping + tier ceiling)
   181	        5. Sort, assign rank, cache
   182	        6. Return SuggestResult
   183	        """
   184	        if options is None:
   185	            options = SuggestOptions()
   186	
   187	        self._ensure_providers()
   188	
   189	        # Build context
   190	        dep = _find_dependency(pack, dep_id)
   191	        if dep is None:
   192	            return SuggestResult(warnings=[f"Dependency {dep_id} not found"])
   193	
   194	        kind = getattr(dep, "kind", AssetKind.UNKNOWN)
   195	        if isinstance(kind, str):
   196	            try:
   197	                kind = AssetKind(kind)
   198	            except ValueError:
   199	                kind = AssetKind.UNKNOWN
   200	
   201	        # Get preview hints — prefer override from import pipeline
   202	        if options.preview_hints_override is not None:
   203	            preview_hints = options.preview_hints_override
   204	        else:
   205	            preview_hints = getattr(dep, "_preview_hints", [])
   206	
   207	        ctx = ResolveContext(
   208	            pack=pack,
   209	            dependency=dep,
   210	            dep_id=dep_id,
   211	            kind=kind,
   212	            preview_hints=preview_hints,
   213	            layout=self._layout,
   214	        )
   215	
   216	        # Gather evidence from all providers
   217	        all_hits: List[EvidenceHit] = []
   218	        warnings: List[str] = []
   219	
   220	        # Sort providers by tier (lower tier = higher priority)
   221	        sorted_providers = sorted(
   222	            self._providers.items(),
   223	            key=lambda p: getattr(p[1], "tier", 99),
   224	        )
   225	
   226	        for name, provider in sorted_providers:
   227	            # Skip AI if not requested
   228	            if name == "ai" and not options.include_ai:
   229	                continue
   230	
   231	            if not provider.supports(ctx):
   232	                continue
   233	
   234	            try:
   235	                result = provider.gather(ctx)
   236	                all_hits.extend(result.hits)
   237	                warnings.extend(result.warnings)
   238	                if result.error:
   239	                    warnings.append(f"{name}: {result.error}")
   240	            except Exception as e:
   241	                warnings.append(f"Provider {name} failed: {e}")
   242	                logger.warning("Provider %s failed: %s", name, e, exc_info=True)
   243	
   244	        # Merge by candidate key and score
   245	        candidates = self._merge_and_score(all_hits, kind, pack, options)
   246	
   247	        # Build result
   248	        fingerprint = _compute_pack_fingerprint(pack)
   249	        result = SuggestResult(
   250	            candidates=candidates[:options.max_candidates],
   251	            pack_fingerprint=fingerprint,
   252	            warnings=warnings,
   253	            preview_hints=preview_hints,
   254	        )
   255	
   256	        # Cache for apply
   257	        self._cache.store(result.request_id, fingerprint, result.candidates)
   258	
   259	        return result
   260	

exec
/bin/bash -lc 'git rev-parse --abbrev-ref HEAD && git rev-parse feat/resolve-model-redesign && git diff --stat main..feat/resolve-model-redesign' in /home/box/git/github/synapse
 succeeded in 117ms:
 apps/web/e2e/helpers/resolve.helpers.ts            |  415 ++++
 apps/web/e2e/resolve-dependency.spec.ts            |  455 ++++
 .../src/__tests__/pack-data-invalidation.test.ts   |    6 +-
 apps/web/src/__tests__/pack-detail-hooks.test.ts   |    1 -
 apps/web/src/__tests__/preview-analysis.test.ts    |  352 +++
 apps/web/src/components/layout/Layout.tsx          |    4 +-
 apps/web/src/components/modules/PackDetailPage.tsx |  191 +-
 .../components/modules/pack-detail/constants.ts    |    5 +-
 .../components/modules/pack-detail/hooks/index.ts  |    8 +
 .../pack-detail/hooks/useAvatarAvailable.ts        |   25 +
 .../modules/pack-detail/hooks/usePackData.ts       |  188 +-
 .../pack-detail/hooks/usePreviewAnalysis.ts        |   26 +
 .../pack-detail/modals/BaseModelResolverModal.tsx  |  765 ------
 .../pack-detail/modals/DependencyResolverModal.tsx |  653 ++++++
 .../modules/pack-detail/modals/LocalResolveTab.tsx |  660 ++++++
 .../pack-detail/modals/PreviewAnalysisTab.tsx      |  435 ++++
 .../components/modules/pack-detail/modals/index.ts |    7 +-
 .../sections/PackDependenciesSection.tsx           |   30 +-
 .../src/components/modules/pack-detail/types.ts    |  177 +-
 apps/web/src/i18n/locales/cs.json                  |    1 -
 apps/web/src/i18n/locales/en.json                  |    1 -
 apps/web/src/lib/avatar/api.ts                     |    3 +-
 config/avatar.yaml.example                         |   16 +-
 config/avatar/skills/huggingface-integration.md    |  111 +
 config/avatar/skills/model-resolution.md           |  354 +++
 plans/PLAN-Resolution.md                           |   69 -
 plans/PLAN-Resolve-Model.md                        | 2439 ++++++++++++++++++++
 plans/SPEC-Local-Resolve.md                        |  449 ++++
 plans/ai_extraction_spec.md                        |   55 +-
 plans/session/MEMORY.md                            |   73 +
 plans/session/README.md                            |   92 +
 .../claude-session-synapse-2026-03-08.tar.gz       |  Bin 0 -> 94038919 bytes
 plans/session/download-system.md                   |   42 +
 plans/sessions/README.md                           |   30 -
 plans/sessions/nsfw-filter-session-2026-03-06.zip  |  Bin 864486 -> 0 bytes
 pyproject.toml                                     |    2 +-
 pytest.ini                                         |    1 +
 src/avatar/__init__.py                             |    2 +-
 src/avatar/mcp/store_server.py                     |  174 +-
 src/avatar/task_service.py                         |   29 +-
 src/avatar/tasks/base.py                           |    6 +
 src/avatar/tasks/dependency_resolution.py          |  166 ++
 src/avatar/tasks/registry.py                       |    2 +
 src/clients/civitai_client.py                      |   78 +-
 src/clients/huggingface_client.py                  |   38 +-
 src/store/__init__.py                              |  206 +-
 src/store/api.py                                   |  595 +++--
 src/store/enrichment.py                            |  377 +++
 src/store/evidence_providers.py                    |  906 ++++++++
 src/store/hash_cache.py                            |  166 ++
 src/store/local_file_service.py                    |  654 ++++++
 src/store/models.py                                |   25 +
 src/store/pack_service.py                          |   74 +
 src/store/resolve_config.py                        |  213 ++
 src/store/resolve_models.py                        |  179 ++
 src/store/resolve_scoring.py                       |   94 +
 src/store/resolve_service.py                       |  499 ++++
 src/store/resolve_validation.py                    |  111 +
 src/utils/preview_meta_extractor.py                |  592 +++++
 tests/calibration/__init__.py                      |    0
 tests/calibration/test_cdn_png_metadata.py         |  253 ++
 tests/e2e_resolve_claude.py                        |  388 ++++
 tests/e2e_resolve_real.py                          |  417 ++++
 tests/helpers/fixtures.py                          |    9 +
 tests/integration/test_ai_resolve_integration.py   |  525 +++++
 tests/integration/test_ai_resolve_smoke.py         |  290 +++
 .../test_avatar_settings_integration.py            |    3 +-
 tests/integration/test_mcp_smoke.py                |    2 +-
 .../test_preview_analysis_integration.py           |  562 +++++
 tests/integration/test_resolve_integration.py      |  332 +++
 tests/integration/test_resolve_smoke.py            |  124 +
 tests/lint/test_architecture.py                    |    1 -
 tests/store/test_api_critical.py                   |   19 +-
 tests/store/test_api_preview_analysis.py           |  173 ++
 tests/store/test_api_v2_critical.py                |   78 +-
 tests/unit/avatar/test_compat.py                   |    8 +-
 .../unit/avatar/test_dependency_resolution_task.py |  593 +++++
 tests/unit/avatar/test_mcp_tools.py                |   31 +
 tests/unit/avatar/test_task_registry.py            |   18 +-
 tests/unit/store/test_enrichment.py                |  242 ++
 tests/unit/store/test_evidence_providers.py        |  918 ++++++++
 tests/unit/store/test_hash_cache.py                |  162 ++
 tests/unit/store/test_local_file_service.py        |  361 +++
 tests/unit/store/test_phase1_block_d.py            |  331 +++
 tests/unit/store/test_phase1_bug_fixes.py          |  269 +++
 tests/unit/store/test_phase1_import_pipeline.py    |  596 +++++
 tests/unit/store/test_phase5_deferred.py           |  381 +++
 tests/unit/store/test_resolve_config.py            |  209 ++
 tests/unit/store/test_resolve_models.py            |  243 ++
 tests/unit/store/test_resolve_review_fixes.py      |  855 +++++++
 tests/unit/store/test_resolve_scoring.py           |  229 ++
 tests/unit/store/test_resolve_service.py           |  358 +++
 tests/unit/store/test_resolve_validation.py        |  340 +++
 tests/unit/utils/test_preview_meta_extractor.py    |  933 ++++++++
 uv.lock                                            |    8 +-
 95 files changed, 22233 insertions(+), 1355 deletions(-)

codex
The plan on this branch identifies itself as v0.11.0 and says phases 0 through 4 are complete, which differs from your context’s v0.7.1 note. I’m checking the implementation and tests against the branch’s own plan text, and I’ll call out version/status drift explicitly.
exec
/bin/bash -lc "git show feat/resolve-model-redesign:plans/PLAN-Resolve-Model.md | nl -ba | sed -n '260,620p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	    local_path: Optional[str] = None
   261	    constraints: Optional[SelectorConstraints] = None
   262	
   263	    # NOVY: Kanonicky zdroj pro update system
   264	    canonical_source: Optional[CanonicalSource] = None
   265	
   266	class CanonicalSource(BaseModel):
   267	    """Remote identity pro update tracking — nezavisle na install strategy."""
   268	    provider: Literal["civitai", "huggingface"]
   269	    model_id: Optional[int] = None      # Civitai
   270	    version_id: Optional[int] = None    # Civitai
   271	    file_id: Optional[int] = None       # Civitai
   272	    repo_id: Optional[str] = None       # HuggingFace
   273	    filename: Optional[str] = None
   274	    subfolder: Optional[str] = None     # HF repos s vice subfolders (C9)
   275	    revision: Optional[str] = None      # HF commit/tag
   276	    sha256: Optional[str] = None
   277	```
   278	
   279	### 2j. ResolutionCandidate model
   280	
   281	```python
   282	class ResolutionCandidate(BaseModel):
   283	    candidate_id: str                          # UUID — stabilni identifikator
   284	    rank: int
   285	    confidence: float                          # 0.0 - 1.0, v ramci tier stropu
   286	    tier: int                                  # 1-4 (dle nejlepsi evidence)
   287	    strategy: SelectorStrategy
   288	    selector_data: Dict[str, Any]
   289	    canonical_source: Optional[CanonicalSource] = None
   290	
   291	    evidence_groups: List[EvidenceGroup]        # Provenance-grouped evidence
   292	    display_name: str                          # "Illustrious XL v0.6"
   293	    display_description: Optional[str] = None
   294	    provider: Optional[Literal["civitai", "huggingface", "local"]] = None
   295	    compatibility_warnings: List[str] = []     # Cross-kind warnings
   296	
   297	class EvidenceGroup(BaseModel):
   298	    provenance: str                            # "preview:001.png" / "hash" / "alias:SDXL"
   299	    items: List[EvidenceItem]
   300	    combined_confidence: float
   301	
   302	class EvidenceItem(BaseModel):
   303	    source: Literal["hash_match", "preview_embedded", "preview_api_meta",
   304	                     "source_metadata", "file_metadata", "alias_config",
   305	                     "ai_analysis"]
   306	    description: str
   307	    confidence: float
   308	    raw_value: Optional[str] = None
   309	```
   310	
   311	---
   312	
   313	## 3. Aktualni problemy (overene auditem)
   314	
   315	| Problem | Zavaznost | Overeno | Popis |
   316	|---------|-----------|---------|-------|
   317	| MCP not passed to AvatarEngine | CRITICAL | task_service.py:319 | Engine BEZ `mcp_servers`. |
   318	| Preview metadata nepouzita pro resolve | CRITICAL | — | `meta.Model`, `meta.resources[]` v sidecar JSON ignorovany. |
   319	| Resolve je Civitai-centric | CRITICAL | — | Base modely casto na HF. HF search jen `diffusers` filter. |
   320	| Zadny PNG metadata parser | HIGH | — | A1111/ComfyUI data v PNG se nectou. |
   321	| AI nedostava strukturovana metadata | HIGH | pack_service.py:545 | Jen description text. |
   322	| `model_tagging` se nevola pri importu | HIGH | pack_service.py:536-561 | |
   323	| `pack.base_model` prepsano filename stemem | HIGH | api.py:2323 | Korupce dat. |
   324	| Regex parsovani provider IDs z URL | HIGH | api.py:2400-2430 | Tichy fallback 0/"". |
   325	| Mutace obchazeji pack_service | HIGH | api.py (15+ mist) | Prima layout.save_pack(). |
   326	| Design checkpoint-centric | HIGH | BaseModelResolverModal | Vse hardcoded na checkpoint. |
   327	| Chybi CanonicalSource | HIGH | models.py | Zadne remote identity pole. |
   328	| SHA256 lokalnich modelu blokuje | HIGH | — | 2-6GB+ main thread. |
   329	| Chybi cross-kind validace | MED | — | LoRA pro SD1.5 na SDXL pack = tichy problem. |
   330	| TS union chybi 'incompatible' | MED | lib/avatar/api.ts:19 | |
   331	| AI gate `enabled` misto `available` | MED | Layout.tsx:52 | |
   332	| `model_tagging` validace odmitne hint-only | MED | model_tagging.py | |
   333	| Jen CIVITAI_MODEL_LATEST updatable | MED | update_service.py:45-49 | |
   334	
   335	---
   336	
   337	## 4. Compatibility Matrix
   338	
   339	| AssetKind | Local Folders | Civitai Filter | HF Eligible | Extensions | Updatable |
   340	|-----------|--------------|----------------|-------------|------------|-----------|
   341	| checkpoint | models/checkpoints | type=Checkpoint | Yes | .safetensors, .ckpt | Yes |
   342	| lora | models/loras | type=LORA | No | .safetensors | Yes |
   343	| vae | models/vae | type=VAE | Yes | .safetensors, .pt | Yes |
   344	| controlnet | models/controlnet | type=Controlnet | Yes | .safetensors, .pth | Yes |
   345	| embedding | models/embeddings | type=TextualInversion | No | .safetensors, .pt, .bin | Yes |
   346	| upscaler | models/upscale_models | type=Upscaler | Limited | .pth, .safetensors | Yes |
   347	
   348	---
   349	
   350	## 5. Per-Strategy Validation Matrix
   351	
   352	| Strategy | Min Selector Fields | Min Lock Fields | Installable | Updatable | Canonical Req |
   353	|----------|-------------------|-----------------|-------------|-----------|---------------|
   354	| CIVITAI_FILE | model_id, version_id, file_id | sha256, filename, size | Yes | No (pinned) | Auto-filled |
   355	| CIVITAI_MODEL_LATEST | model_id | version_id, file_id, sha256 | Yes | Yes | Auto-filled |
   356	| HUGGINGFACE_FILE | repo_id, filename | sha256, revision | Yes | No (pinned) | Auto-filled |
   357	| LOCAL_FILE | local_path | sha256, mtime, size | N/A | Via canonical | Optional |
   358	| URL_DOWNLOAD | url | sha256, filename | Yes | No | Optional |
   359	| BASE_MODEL_HINT | base_model (alias) | — | Via alias | No | — |
   360	
   361	**Pravidla:**
   362	- `suggest_resolution()` vraci jen kandidaty splnujici Min Selector Fields
   363	- `apply_resolution()` ODMITNE nesplnujici minimum + cross-kind check (2h)
   364	- Zadne ticne fallbacky — kompletni data nebo error
   365	- Alias cil muze byt Civitai NEBO HuggingFace repo
   366	
   367	---
   368	
   369	## 6. Import pipeline — cilovy stav
   370	
   371	```
   372	pack_service.py: import_civitai()
   373	    |
   374	    |-- 1. Fetch Civitai metadata
   375	    |       -> model_id, version_id, files[], baseModel, tags, trainedWords
   376	    |
   377	    |-- 2. extract_parameters(description, metadata_context)
   378	    |       -> gen params (sampler, steps, cfg...)
   379	    |       -> metadata_context = { base_model, tags, trigger_words }
   380	    |
   381	    |-- 3. Analyze preview metadata (NOVY KROK)
   382	    |       Pro kazdy preview image:
   383	    |       a) Civitai API meta (sidecar .json): meta.Model, meta.resources[]
   384	    |       b) PNG embedded meta (pokud CDN nezstripoval): A1111/ComfyUI
   385	    |       c) Kind-aware filtrovani: jen relevant hints pro dany dep typ
   386	    |       d) Provenance grouping: hints ze stejneho obrazku = 1 grupa
   387	    |       -> List[PreviewModelHint]
   388	    |
   389	    |-- 4. suggest_resolution(pack, dep) pro kazdou dependency
   390	    |       Evidence ladder (tier system):
   391	    |
   392	    |       TIER-1: E1 hash match (SHA256 z Civitai file → lookup Civitai + HF dle eligibility)
   393	    |       TIER-2: E2/E3 preview metadata (s provenance grouping)
   394	    |       TIER-3: E5 file metadata, E6 aliases (vcetne HF cilu)
   395	    |       TIER-4: E4 source metadata (baseModel jako filtr)
   396	    |       TIER-AI: E7 pokud available AND zadny TIER-1/2 kandidat:
   397	    |           - model_tagging() pro hints
   398	    |           - MCP: search_civitai, search_huggingface (dle eligibility)
   399	    |           - Cross-reference, AI ceiling = 0.89
   400	    |           - Pokud vice AI provideru: fallback chain
   401	    |
   402	    |       -> List[ResolutionCandidate] s evidence groups a confidence
   403	    |
   404	    |-- 5. Auto-apply / mark unresolved
   405	    |       -> 1 kandidat v TIER-1/2 s >= 0.15 margin nad dalsim → auto-apply
   406	    |       -> Vice kandidatu s podobnou confidence → "unresolved" pro UI
   407	    |       -> Zadny kandidat → nechej dependency pro manual resolve
   408	    |       -> Auto-apply VZDY pres pack_service write path
   409	```
   410	
   411	---
   412	
   413	## 7. UI: DependencyResolverModal
   414	
   415	```
   416	DependencyResolverModal(dep_id, kind: AssetKind)
   417	    |
   418	    |-- Candidates list (vysledky suggest_resolution)
   419	    |   |-- Serazene dle tier + confidence
   420	    |   |-- USER-FRIENDLY confidence prezentace (NE raw cisla):
   421	    |   |     ✅ "Exact match"       (TIER-1, 0.90+)
   422	    |   |     🔵 "High confidence"   (TIER-2, 0.75+)
   423	    |   |     ⚠️  "Possible match"   (TIER-3, 0.50+)
   424	    |   |     ❓ "Hint — verify"     (TIER-4, 0.30+)
   425	    |   |-- Evidence summary (human-readable): "Hash match on HF", "Found in preview metadata"
   426	    |   |-- Provider icon (Civitai / HF / Local)
   427	    |   |-- Compatibility warnings (zluty badge pokud cross-kind issue)
   428	    |   |-- Akce u kazdeho kandidata:
   429	    |   |     "Apply"              — resolve dependency (metadata only)
   430	    |   |     "Apply & Download"   — resolve + spusti download v jednom kroku
   431	    |   |     (obe akce vzdy dostupne — Apply pro planovani, Apply & Download pro okamzite pouziti)
   432	    |
   433	    |-- SMART TAB ORDERING:
   434	    |   |-- Default aktivni tab = tab s nejlepsim kandidatem (ne vzdy AI)
   435	    |   |-- Pokud candidates list uz ma TIER-1/2 → default = Candidates (zadny tab aktivni)
   436	    |   |-- Pokud prazdne candidates → default = Preview Analysis (nejintuitivnejsi)
   437	    |   |-- Taby serazeny dle relevance, ne fixne
   438	    |
   439	    |-- Tab: Preview Analysis
   440	    |   |-- Grid cover/preview obrazku packu
   441	    |   |-- Klik na obrazek → extrakce metadata:
   442	    |   |     - Civitai API meta (sidecar .json)
   443	    |   |     - PNG embedded meta (A1111/ComfyUI) pokud dostupne
   444	    |   |-- Zobrazeni: model name, sampler, LoRAs, s kind oznacenim
   445	    |   |-- "Use this model" → create candidate + apply (pres validaci)
   446	    |   |-- Unresolvable hints sedi but oznaceny (nelze najit remote)
   447	    |
   448	    |-- Tab: AI Resolve (pokud avatar available)
   449	    |   |-- "Analyze" pro AI hledani na Civitai + HF (dle eligibility)
   450	    |   |-- Evidence chain zobrazeni
   451	    |   |-- Vysledky se pridaji do candidates list s TIER-AI
   452	    |   |-- Pokud vice AI provideru: "Try another provider" option
   453	    |
   454	    |-- Tab: Local Models
   455	    |   |-- Scan dle AssetKind (compatibility matrix)
   456	    |   |-- Background SHA256 s progress (hash cache ready z Phase 0)
   457	    |   |-- AI dohledava canonical_source pokud available
   458	    |
   459	    |-- Tab: Civitai Search
   460	    |   |-- Typed payloady (model_id, version_id, file_id)
   461	    |   |-- Filtr dle kind z compatibility matrix
   462	    |
   463	    |-- Tab: HuggingFace Search (pokud HF eligible pro dany kind)
   464	    |   |-- Typed payloady (repo_id, filename, subfolder, revision, sha256)
   465	    |   |-- LFS pointer verification pro hash confirm
   466	
   467	AI GATE:
   468	  - useAvatarAvailable() hook: gate na `available === true`
   469	  - AI tab NEZOBRAZENY pokud !available
   470	  - HF tab NEZOBRAZENY pokud kind neni HF eligible
   471	
   472	RESOLUTION != DOWNLOAD (obe cesty dostupne):
   473	  - "Apply" = resolve only — produkuje metadata (DependencySelector + CanonicalSource)
   474	    Uzivatel planuje download pozdeji (batch download, disk space management)
   475	  - "Apply & Download" = resolve + okamzity download v jednom kroku
   476	    Napojeni na existujici POST /api/packs/{pack}/download-asset
   477	  - Download je VZDY dostupny i samostatne v deps sekci (pro jiz resolvovane deps)
   478	
   479	INLINE RESOLVE (progressive disclosure):
   480	  - V PackDependenciesSection: pokud suggest vrati TIER-1/2 kandidata,
   481	    zobrazit INLINE: "Found: Illustrious XL v0.6 ✅ [Apply] [Apply & Download]"
   482	  - Uzivatel NEMUSI otvirat modal pro jednoduche pripady
   483	  - "More options..." link otvira plny DependencyResolverModal
   484	  - Pokud zadny kandidat nebo nizka confidence → rovnou "Resolve..." tlacitko (modal)
   485	```
   486	
   487	---
   488	
   489	## 8. Existujici implementace
   490	
   491	### Frontend
   492	
   493	| Soubor | Popis | Osud |
   494	|--------|-------|------|
   495	| `BaseModelResolverModal.tsx` (766 r.) | 3 taby, checkpoint-only | NAHRADIT |
   496	| `PackDetailPage.tsx:160-224` | Query hooks pro resolve | REFAKTOR |
   497	| `PackDependenciesSection.tsx` | Deps display + "Resolve" button | UPRAVIT |
   498	| `GenerationDataPanel.tsx` | Zobrazuje meta | INSPIRACE pro Preview Analysis |
   499	
   500	### Backend
   501	
   502	| Soubor | Popis | Osud |
   503	|--------|-------|------|
   504	| `src/store/api.py:2255-2472` | /resolve-base-model, prima mutace | NAHRADIT |
   505	| `src/store/dependency_resolver.py` | Protocol + 6 resolveru | ZACHOVAT, ROZSIRIT |
   506	| `src/store/pack_service.py:536-561` | Import: jen extract_parameters | ROZSIRIT |
   507	| `src/core/pack_builder.py:315-638` | Preview download, sidecar .json | ZACHOVAT |
   508	| `src/store/update_service.py:45-49` | UPDATABLE_STRATEGIES | ROZSIRIT pozdeji |
   509	| `apps/api/src/routers/browse.py:906-952` | HF search (jen diffusers filter) | ROZSIRIT |
   510	| `apps/api/src/routers/browse.py:1203+` | Civitai search | ZACHOVAT |
   511	
   512	### Avatar/AI
   513	
   514	| Soubor | Popis | Osud |
   515	|--------|-------|------|
   516	| `src/avatar/tasks/model_tagging.py` | Skill generation-params | UPRAVIT validaci |
   517	| `src/avatar/task_service.py:319` | Engine BEZ mcp_servers | OPRAVIT |
   518	| `src/avatar/mcp/store_server.py` | 21 MCP tools (Civitai only hash lookup) | ROZSIRIT o HF |
   519	| `src/avatar/routes.py:71-107` | /api/avatar/status (6 stavu) | ZACHOVAT |
   520	
   521	### Data
   522	
   523	| Soubor | Popis | Osud |
   524	|--------|-------|------|
   525	| `src/store/models.py:374-382` | DependencySelector | ROZSIRIT (canonical_source) |
   526	| `src/store/models.py:267-307` | base_model_aliases (Civitai cile) | ROZSIRIT o HF |
   527	| `lib/avatar/api.ts:19-28` | AvatarStatus chybi 'incompatible' | OPRAVIT |
   528	| Preview sidecar .json | meta.Model, meta.resources | POUZIT pro resolve |
   529	
   530	---
   531	
   532	## 9. Bugy k oprave
   533	
   534	### BUG 1: extractBaseModelHint() — regex na HTML description
   535	**Soubor:** BaseModelResolverModal.tsx:123-140
   536	**Fix:** Smazat. Pouzit pack.base_model + preview metadata.
   537	
   538	### BUG 2: model_tagging se nevola pri importu
   539	**Soubor:** pack_service.py:536-561
   540	**Fix:** Pridat do import pipeline (evidence E7). Relaxovat validaci.
   541	
   542	### BUG 3: pack.base_model prepsano filename stemem
   543	**Soubor:** api.py:2286,2323
   544	**Fix:** apply_resolution() NIKDY neprepise filename stemem.
   545	
   546	### BUG 4: Regex parsovani provider IDs z URL
   547	**Soubor:** api.py:2400-2430
   548	**Fix:** Typed API, zadne parsovani z URL.
   549	
   550	### BUG 5: TS union chybi 'incompatible'
   551	**Soubor:** lib/avatar/api.ts:19
   552	**Fix:** Pridat stav + engine_min_version.
   553	
   554	### BUG 6: AI gate enabled misto available
   555	**Soubor:** Layout.tsx:52
   556	**Fix:** Gate na available === true.
   557	
   558	---
   559	
   560	## 10. Faze implementace
   561	
   562	### Phase 0: Resolve infrastruktura + data model + calibration
   563	
   564	**Cil:** Polozit vsechny zaklady. Overit predpoklady (CDN, confidence).
   565	
   566	**Deliverables:**
   567	
   568	**Data model:** ✅ IMPL
   569	1. ✅ CanonicalSource model — models.py (s subfolder polem)
   570	2. ✅ ResolutionCandidate + EvidenceGroup + EvidenceItem modely — `resolve_models.py`
   571	3. ✅ PreviewModelHint model — `resolve_models.py`
   572	4. ✅ Cross-kind compatibility rules config — `resolve_config.py`
   573	
   574	**Konfigurace:** ✅ IMPL
   575	5. ✅ Compatibility matrix — `src/store/resolve_config.py` (AssetKindConfig, TIER_CONFIGS, COMPATIBILITY_RULES)
   576	6. ✅ Validation matrix — `src/store/resolve_validation.py` (STRATEGY_REQUIREMENTS, validate_candidate, validate_before_apply)
   577	7. ✅ base_model_aliases — AliasEvidenceProvider cte z config.json pres layout.load_config() (Phase 6)
   578	
   579	**Scoring:** ✅ IMPL
   580	- ✅ `src/store/resolve_scoring.py` — Noisy-OR, provenance grouping, tier ceiling
   581	
   582	**Evidence Providers:** ✅ IMPL
   583	- ✅ `src/store/evidence_providers.py` — 6 provideru (Hash, Preview, File, Alias, Source, AI)
   584	- ✅ EvidenceProvider Protocol s @runtime_checkable
   585	
   586	**ResolveService:** ✅ IMPL
   587	- ✅ `src/store/resolve_service.py` — suggest/apply orchestrace, candidate cache, lazy providers
   588	
   589	**Hash cache:** ✅ IMPL
   590	- ✅ `src/store/hash_cache.py` — persistent cache, mtime+size invalidace, compute_sha256
   591	
   592	**Preview metadata extractor:** ✅ IMPL
   593	8. ✅ `src/utils/preview_meta_extractor.py`
   594	   - ✅ Cteni sidecar .json → meta.Model, meta.resources[] (s kind-aware filtrovanim)
   595	   - ✅ PNG tEXt chunk parser (PIL) → A1111 params, ComfyUI workflow JSON
   596	   - ✅ Target specificky ComfyUI nody: CheckpointLoaderSimple, LoraLoader, VAELoader
   597	   - ✅ Vraci List[PreviewModelHint] s provenance tagy
   598	
   599	**Calibration (C5):** ✅ PROVEDENO
   600	9. ✅ **CDN metadata test** — `tests/calibration/test_cdn_png_metadata.py`
   601	   - ✅ VYSLEDEK: CDN servíruje JPEG/WebP, NE originální PNG
   602	   - ✅ E2 (PNG embedded) degradováno na "best effort"
   603	   - ✅ E3 (API meta ze sidecar .json) je PRIMARY zdroj preview evidence
   604	10. ⚠️ **Confidence calibration** — odlozeno (vyzaduje import flow s realnymi daty)
   605	
   606	    **Postup pro budouci kalibraci s realnymi daty:**
   607	
   608	    A. **Sber dat (1-2 hodiny):**
   609	       1. Vybrat 20-30 packu s ruznymi typy (checkpoint, LoRA, embedding)
   610	       2. Pro kazdy: `store.suggest(pack, dep_id)` → ulozit candidates + confidence
   611	       3. Rucne oznacit spravny vysledek (ground truth)
   612	       4. Ulozit do `tests/calibration/calibration_data.json`
   613	
   614	    B. **Analyza (skript):**
   615	       ```python
   616	       # Pro kazdy provider zvlast:
   617	       # 1. Precision@1: kolik top-1 candidates je spravnych?
   618	       # 2. Tier distribuce: kolik spravnych je v T1 vs T2 vs T3?
   619	       # 3. Margin distribuce: jake jsou gapy mezi top-1 a top-2?
   620	       # 4. False positive rate: kolik T1 candidates je spatnych?

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_service.py | nl -ba | sed -n '260,620p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	
   261	    def apply(
   262	        self,
   263	        pack_name: str,
   264	        dep_id: str,
   265	        candidate_id: str,
   266	        request_id: Optional[str] = None,
   267	    ) -> ApplyResult:
   268	        """Apply a candidate from a previous suggest.
   269	
   270	        1. Find candidate in cache (by request_id + candidate_id)
   271	        2. Validate: min fields + cross-kind check
   272	        3. Delegate to pack_service.apply_dependency_resolution()
   273	        4. Return ApplyResult
   274	        """
   275	        # Find candidate
   276	        candidate = None
   277	        if request_id:
   278	            candidate = self._cache.get(request_id, candidate_id)
   279	        else:
   280	            # Search all cached requests for this candidate_id
   281	            candidate = self._find_candidate_in_cache(candidate_id)
   282	
   283	        if candidate is None:
   284	            return ApplyResult(
   285	                success=False,
   286	                message="Candidate not found or expired. Please re-run suggest.",
   287	            )
   288	
   289	        # Build selector from candidate
   290	        selector = self._candidate_to_selector(candidate)
   291	
   292	        # Check fingerprint staleness (warn but don't block)
   293	        stale_warnings: List[str] = []
   294	        if request_id and pack_name:
   295	            try:
   296	                pack_for_fp = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
   297	                if pack_for_fp:
   298	                    current_fp = _compute_pack_fingerprint(pack_for_fp)
   299	                    if not self._cache.check_fingerprint(request_id, current_fp):
   300	                        stale_warnings.append(
   301	                            "Pack has changed since suggest was run. "
   302	                            "Results may be stale — consider re-running suggest."
   303	                        )
   304	            except Exception:
   305	                pass  # Non-critical check
   306	
   307	        # Validate
   308	        pack = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
   309	        dep = _find_dependency(pack, dep_id) if pack else None
   310	        kind = getattr(dep, "kind", AssetKind.UNKNOWN) if dep else AssetKind.UNKNOWN
   311	        pack_base_model = getattr(pack, "base_model", None) if pack else None
   312	
   313	        validation = validate_before_apply(
   314	            selector, kind,
   315	            pack_base_model=pack_base_model,
   316	            candidate_base_model=getattr(candidate, "base_model", None),
   317	        )
   318	
   319	        if not validation.success:
   320	            return validation
   321	
   322	        # Delegate write to pack_service
   323	        try:
   324	            if hasattr(self._pack_service, "apply_dependency_resolution"):
   325	                self._pack_service.apply_dependency_resolution(
   326	                    pack_name=pack_name,
   327	                    dep_id=dep_id,
   328	                    selector=selector,
   329	                    canonical_source=candidate.canonical_source,
   330	                    lock_entry=None,
   331	                    display_name=candidate.display_name,
   332	                )
   333	            all_warnings = stale_warnings + (validation.compatibility_warnings or [])
   334	            return ApplyResult(
   335	                success=True,
   336	                message="Resolution applied",
   337	                compatibility_warnings=all_warnings,
   338	            )
   339	        except Exception as e:
   340	            return ApplyResult(success=False, message=f"Apply failed: {e}")
   341	
   342	    def apply_manual(
   343	        self,
   344	        pack_name: str,
   345	        dep_id: str,
   346	        manual: ManualResolveData,
   347	    ) -> ApplyResult:
   348	        """Apply manual resolve data. Same validation as apply."""
   349	        selector = DependencySelector(
   350	            strategy=manual.strategy,
   351	            civitai=manual.civitai,
   352	            huggingface=manual.huggingface,
   353	            local_path=manual.local_path,
   354	            url=manual.url,
   355	            canonical_source=manual.canonical_source,
   356	        )
   357	
   358	        # Load pack and dep for cross-kind validation
   359	        pack = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
   360	        dep = _find_dependency(pack, dep_id) if pack else None
   361	        kind = getattr(dep, "kind", AssetKind.UNKNOWN) if dep else AssetKind.UNKNOWN
   362	        pack_base_model = getattr(pack, "base_model", None) if pack else None
   363	
   364	        # Full validation (fields + cross-kind compatibility)
   365	        validation = validate_before_apply(
   366	            selector, kind,
   367	            pack_base_model=pack_base_model,
   368	            candidate_base_model=None,
   369	        )
   370	        if not validation.success:
   371	            return validation
   372	
   373	        # Delegate write
   374	        try:
   375	            if hasattr(self._pack_service, "apply_dependency_resolution"):
   376	                self._pack_service.apply_dependency_resolution(
   377	                    pack_name=pack_name,
   378	                    dep_id=dep_id,
   379	                    selector=selector,
   380	                    canonical_source=manual.canonical_source,
   381	                    lock_entry=None,
   382	                    display_name=manual.display_name,
   383	                )
   384	            return ApplyResult(
   385	                success=True,
   386	                message="Manual resolution applied",
   387	                compatibility_warnings=validation.compatibility_warnings or [],
   388	            )
   389	        except Exception as e:
   390	            return ApplyResult(success=False, message=f"Apply failed: {e}")
   391	
   392	    def _merge_and_score(
   393	        self,
   394	        hits: List[EvidenceHit],
   395	        kind: AssetKind,
   396	        pack: Any,
   397	        options: SuggestOptions,
   398	    ) -> List[ResolutionCandidate]:
   399	        """Merge evidence hits by candidate key, score, and rank."""
   400	        # Group hits by candidate key
   401	        by_key: Dict[str, List[EvidenceHit]] = defaultdict(list)
   402	        seeds: Dict[str, CandidateSeed] = {}
   403	
   404	        for hit in hits:
   405	            key = hit.candidate.key
   406	            by_key[key].append(hit)
   407	            if key not in seeds:
   408	                seeds[key] = hit.candidate
   409	            elif hit.candidate.base_model and not seeds[key].base_model:
   410	                # Later seed has base_model that first-seen lacked — update
   411	                seeds[key] = hit.candidate
   412	
   413	        # Score each candidate
   414	        candidates: List[ResolutionCandidate] = []
   415	        pack_base_model = getattr(pack, "base_model", None)
   416	
   417	        for key, key_hits in by_key.items():
   418	            seed = seeds[key]
   419	            groups = group_by_provenance(key_hits)
   420	            group_list = list(groups.values())
   421	            confidence = score_candidate(group_list)
   422	            tier = get_tier_for_confidence(confidence)
   423	
   424	            # Cross-kind compatibility check
   425	            candidate_base_model = (
   426	                seed.base_model
   427	                or getattr(seed.selector, "base_model", None)
   428	            )
   429	            compat_warnings = check_cross_kind_compatibility(
   430	                pack_base_model, candidate_base_model, kind,
   431	            )
   432	
   433	            candidate = ResolutionCandidate(
   434	                confidence=confidence,
   435	                tier=tier,
   436	                strategy=seed.selector.strategy,
   437	                selector_data=seed.selector.model_dump(exclude_none=True),
   438	                canonical_source=seed.canonical_source,
   439	                evidence_groups=group_list,
   440	                display_name=seed.display_name,
   441	                display_description=seed.display_description,
   442	                provider=seed.provider_name,
   443	                base_model=candidate_base_model,
   444	                compatibility_warnings=compat_warnings,
   445	            )
   446	            candidates.append(candidate)
   447	
   448	        # Sort by confidence descending
   449	        candidates.sort(key=lambda c: c.confidence, reverse=True)
   450	
   451	        # Assign ranks
   452	        for i, c in enumerate(candidates):
   453	            c.rank = i + 1
   454	
   455	        return candidates
   456	
   457	    def _candidate_to_selector(
   458	        self, candidate: ResolutionCandidate,
   459	    ) -> DependencySelector:
   460	        """Reconstruct DependencySelector from a candidate."""
   461	        return DependencySelector(**{
   462	            k: v for k, v in candidate.selector_data.items()
   463	            if k in DependencySelector.model_fields
   464	        })
   465	
   466	    def _find_candidate_in_cache(
   467	        self, candidate_id: str,
   468	    ) -> Optional[ResolutionCandidate]:
   469	        """Search all cached requests for a candidate.
   470	
   471	        Falls back to linear search through known request_ids.
   472	        Only works with InMemoryCandidateCache (known implementation).
   473	        """
   474	        cache = self._cache
   475	        if isinstance(cache, InMemoryCandidateCache):
   476	            return cache.find_by_candidate_id(candidate_id)
   477	        return None
   478	
   479	
   480	# --- Helpers ---
   481	
   482	def _find_dependency(pack: Any, dep_id: str) -> Any:
   483	    """Find a dependency by ID in a pack."""
   484	    deps = getattr(pack, "dependencies", [])
   485	    if not deps:
   486	        return None
   487	    for dep in deps:
   488	        if getattr(dep, "id", None) == dep_id:
   489	            return dep
   490	    return None
   491	
   492	
   493	def _compute_pack_fingerprint(pack: Any) -> str:
   494	    """Compute a fingerprint for stale detection."""
   495	    try:
   496	        data = pack.model_dump() if hasattr(pack, "model_dump") else str(pack)
   497	        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]
   498	    except Exception:
   499	        return ""

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_models.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Resolve system DTOs — all data transfer objects for dependency resolution.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 sections 2b, 2j, 11c.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from typing import Any, Dict, List, Literal, Optional
    10	from uuid import uuid4
    11	
    12	from pydantic import BaseModel, Field
    13	
    14	from .models import (
    15	    AssetKind,
    16	    CanonicalSource,
    17	    CivitaiSelector,
    18	    DependencySelector,
    19	    HuggingFaceSelector,
    20	    SelectorStrategy,
    21	)
    22	
    23	# --- Evidence source types ---
    24	
    25	EvidenceSource = Literal[
    26	    "hash_match",          # E1: SHA256 lookup (Tier 1)
    27	    "preview_embedded",    # E2: PNG tEXt metadata (Tier 2)
    28	    "preview_api_meta",    # E3: Civitai API sidecar meta (Tier 2)
    29	    "source_metadata",     # E4: Civitai baseModel field (Tier 4)
    30	    "file_metadata",       # E5: Filename patterns (Tier 3)
    31	    "alias_config",        # E6: Configured aliases (Tier 3)
    32	    "ai_analysis",         # E7: AI-assisted analysis (ceiling 0.89)
    33	]
    34	
    35	
    36	# --- Evidence items ---
    37	
    38	class EvidenceItem(BaseModel):
    39	    """A single piece of evidence from one source."""
    40	    source: EvidenceSource
    41	    description: str
    42	    confidence: float  # 0.0 - 1.0, within tier bounds
    43	    raw_value: Optional[str] = None
    44	
    45	
    46	class EvidenceGroup(BaseModel):
    47	    """Evidence items from the same provenance (e.g., one preview image).
    48	
    49	    Within a group: combined_confidence = max(item.confidence).
    50	    Between groups: Noisy-OR combination.
    51	    """
    52	    provenance: str  # "preview:001.png", "hash:sha256", "alias:SDXL"
    53	    items: List[EvidenceItem] = Field(default_factory=list)
    54	    combined_confidence: float = 0.0
    55	
    56	
    57	# --- Candidate models ---
    58	
    59	class CandidateSeed(BaseModel):
    60	    """What an evidence provider found — a candidate with identification."""
    61	    key: str  # Deduplication key: "civitai:model_id:version_id" or "local:/path"
    62	    selector: DependencySelector
    63	    canonical_source: Optional[CanonicalSource] = None
    64	    display_name: str
    65	    display_description: Optional[str] = None
    66	    provider_name: Optional[Literal["civitai", "huggingface", "local", "url"]] = None
    67	    base_model: Optional[str] = None  # e.g. "SDXL", "SD 1.5" — for cross-kind check
    68	
    69	
    70	class EvidenceHit(BaseModel):
    71	    """One finding = candidate + evidence why."""
    72	    candidate: CandidateSeed
    73	    provenance: str  # Which preview/hash/alias produced this
    74	    item: EvidenceItem
    75	
    76	
    77	class ResolutionCandidate(BaseModel):
    78	    """A ranked candidate for dependency resolution."""
    79	    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    80	    rank: int = 0
    81	    confidence: float = Field(ge=0.0, le=1.0)
    82	    tier: int = Field(ge=1, le=4)  # Confidence tier (1=highest, 4=lowest)
    83	    strategy: SelectorStrategy
    84	    selector_data: Dict[str, Any] = Field(default_factory=dict)
    85	    canonical_source: Optional[CanonicalSource] = None
    86	    evidence_groups: List[EvidenceGroup] = Field(default_factory=list)
    87	    display_name: str = ""
    88	    display_description: Optional[str] = None
    89	    provider: Optional[Literal["civitai", "huggingface", "local", "url"]] = None
    90	    base_model: Optional[str] = None  # e.g. "SDXL", "SD 1.5"
    91	    compatibility_warnings: List[str] = Field(default_factory=list)
    92	
    93	
    94	# --- Preview model hints ---
    95	
    96	class PreviewModelHint(BaseModel):
    97	    """A model reference extracted from a preview image's metadata."""
    98	    filename: str              # "illustriousXL_v060.safetensors"
    99	    kind: Optional[AssetKind] = None  # From ComfyUI node type
   100	    source_image: str          # Which preview image
   101	    source_type: Literal["api_meta", "png_embedded"]
   102	    raw_value: str             # Raw value for debugging
   103	    resolvable: bool = True    # False if private/unknown format
   104	    hash: Optional[str] = None         # Short SHA hash if available
   105	    weight: Optional[float] = None     # LoRA weight if available
   106	
   107	
   108	class PreviewAnalysisResult(BaseModel):
   109	    """Preview image with extracted hints + raw generation params."""
   110	    filename: str
   111	    url: Optional[str] = None
   112	    thumbnail_url: Optional[str] = None
   113	    media_type: Literal["image", "video", "unknown"] = "image"
   114	    width: Optional[int] = None
   115	    height: Optional[int] = None
   116	    nsfw: bool = False
   117	    hints: List[PreviewModelHint] = Field(default_factory=list)
   118	    generation_params: Optional[Dict[str, Any]] = None
   119	
   120	
   121	# --- Provider result ---
   122	
   123	class ProviderResult(BaseModel):
   124	    """Output of one evidence provider's gather() call."""
   125	    hits: List[EvidenceHit] = Field(default_factory=list)
   126	    warnings: List[str] = Field(default_factory=list)
   127	    error: Optional[str] = None
   128	
   129	
   130	# --- Request/Response contracts ---
   131	
   132	class SuggestOptions(BaseModel):
   133	    """Options for suggest_resolution."""
   134	    include_ai: bool = False       # Default OFF for import (R5)
   135	    analyze_previews: bool = True
   136	    max_candidates: int = 10
   137	    preview_hints_override: Optional[List[PreviewModelHint]] = None  # External hints (import pipeline)
   138	
   139	
   140	class SuggestResult(BaseModel):
   141	    """Result of suggest — list of candidates + metadata."""
   142	    request_id: str = Field(default_factory=lambda: str(uuid4()))
   143	    candidates: List[ResolutionCandidate] = Field(default_factory=list)
   144	    pack_fingerprint: str = ""  # SHA hash of pack.json for stale detection
   145	    warnings: List[str] = Field(default_factory=list)
   146	    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
   147	
   148	
   149	class ApplyResult(BaseModel):
   150	    """Result of apply — success/failure."""
   151	    success: bool
   152	    message: str = ""
   153	    compatibility_warnings: List[str] = Field(default_factory=list)
   154	
   155	
   156	class ManualResolveData(BaseModel):
   157	    """Data from manual resolve (Civitai/HF/Local tab)."""
   158	    strategy: SelectorStrategy
   159	    civitai: Optional[CivitaiSelector] = None
   160	    huggingface: Optional[HuggingFaceSelector] = None
   161	    local_path: Optional[str] = None
   162	    url: Optional[str] = None
   163	    canonical_source: Optional[CanonicalSource] = None
   164	    display_name: Optional[str] = None
   165	
   166	
   167	# --- Resolve context (passed to providers) ---
   168	
   169	class ResolveContext(BaseModel):
   170	    """Context passed to evidence providers."""
   171	    pack: Any  # Pack object
   172	    dependency: Any  # PackDependency
   173	    dep_id: str = ""
   174	    kind: AssetKind = AssetKind.UNKNOWN
   175	    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
   176	    layout: Any = None  # StoreLayout (for file-system access)
   177	
   178	    class Config:
   179	        arbitrary_types_allowed = True

exec
/bin/bash -lc "git show feat/resolve-model-redesign:plans/PLAN-Resolve-Model.md | nl -ba | sed -n '620,1080p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   620	       # 4. False positive rate: kolik T1 candidates je spatnych?
   621	       ```
   622	
   623	    C. **Parametry k ladeni:**
   624	       - `AUTO_APPLY_MARGIN` (0.15) — zvysit pokud false positive rate > 5%
   625	       - `AI_CONFIDENCE_CEILING` (0.89) — snizit pokud AI casto chybuje v T1
   626	       - Per-provider confidence v `ASSET_KIND_CONFIG` — hlavne hash (0.95) vs name (0.70)
   627	       - `COMPATIBILITY_RULES` — pridat chybejici base_model kombinace
   628	
   629	    D. **Metriky pro uspech:**
   630	       - Auto-apply accuracy > 95% (zneho co auto-apply vybere, 95%+ musi byt spravne)
   631	       - Recall > 80% (80%+ deps s BASE_MODEL_HINT musi dostat alespon 1 spravny candidate)
   632	       - False T1 rate < 3% (max 3% T1 candidates je spatnych)
   633	
   634	**Hash cache zaklady (G1):** ✅ IMPL
   635	11. ✅ Hash cache modul — `src/store/hash_cache.py`
   636	    - ✅ Cache structure: `{ path: { sha256, mtime, size, computed_at } }`
   637	    - ✅ Persistence: `data/registry/local_model_hashes.json`
   638	    - ✅ Invalidace: mtime+size change → rehash
   639	    - ✅ Async hash computation — compute_sha256_async() v hash_cache.py (Phase 5)
   640	
   641	**API:** ✅ IMPL+INTEG (Phase 1)
   642	12. ✅ Suggest/Apply endpointy — 3 API endpointy v `api.py`: suggest-resolution, apply-resolution, apply-manual-resolution
   643	13. ✅ Apply pres pack_service write path — `PackService.apply_dependency_resolution()` implementovano
   644	    - ✅ `/resolve-base-model` oznaceno jako deprecated (OpenAPI `deprecated=True`)
   645	
   646	**Phase 1 BUG fixy:** ✅ IMPL+INTEG
   647	- ✅ BUG 1: `extractBaseModelHint()` smazano z `BaseModelResolverModal.tsx`, nahrazeno `pack.base_model` prop
   648	- ✅ BUG 2: `model_tagging()` rule-based fallback bezi pri importu (merges tags, no MCP)
   649	- ✅ BUG 3: `pack.base_model` NEVER overwritten with filename stem
   650	- ✅ BUG 4: typed API IDs (model_id, version_id, repo_id) na `ResolveBaseModelRequest`
   651	
   652	**Phase 1 Import pipeline:** ✅ IMPL+INTEG
   653	- ✅ `SuggestOptions.preview_hints_override` — external hints z import pipeline
   654	- ✅ `Store._post_import_resolve()` — post-import orchestrace (suggest E1-E6, auto-apply TIER-1/2 s margin 0.15)
   655	- ✅ `Store.suggest_resolution()` / `apply_resolution()` — delegate metody na Store facade
   656	- ✅ `Store.migrate_resolve_deps(dry_run=True/False)` — migration helper pro stare packy
   657	
   658	**Gates:** ❌ Phase 2
   659	14. ✅ `can_use_ai()` gate — useAvatarAvailable hook + AI tab visibility in DependencyResolverModal
   660	15. ✅ Fix BUG 5: TS union + incompatible — AvatarStatus.state includes 'incompatible', engine_min_version added
   661	16. ✅ Fix BUG 6: AI gate available — Layout.tsx gates on `available === true` instead of `enabled !== false`
   662	
   663	**Testy:** ✅ 291 TESTU (+ 2 calibration external)
   664	- ✅ Unit: modely (22), config (37), validation (26), scoring (23), hash_cache (15), evidence_providers (34), resolve_service (19), preview_extractor (27)
   665	- ✅ Review fix testy (46): tier boundary gaps, zero-value validation, fingerprint stale warning, atomic cache write, scoring spec examples, suggest→apply round-trip, real Pydantic models
   666	- ✅ Phase 1 Block A+B (13): BUG 3, BUG 4, PackService.apply_dependency_resolution, Store facade, API schemas
   667	- ✅ Phase 1 Block C (16): SuggestOptions hints override, ResolveService suggest s override, post-import resolve orchestrace, Store delegate metody, auto-apply logika
   668	- ✅ Phase 1 Block D (11): model_tagging rule-based, migration helper dry-run/apply/skip/error
   669	- ✅ Calibration: CDN PNG metadata (2, external)
   670	- ✅ Integration testy — test_resolve_integration.py (17 testu, Phase 6)
   671	- ✅ Smoke testy — test_resolve_smoke.py (10 testu, Phase 6)
   672	
   673	**Phase 1 Review cyklus:** ✅ DOKONCEN
   674	- ✅ Claude review: overeni vsech zmen, konzistence s planem
   675	- ✅ Gemini 3.1 review: 8 issues — 1 opraven (missing request_id v migrate), 7 odlozeno/by-design
   676	- ✅ Codex 5.4 review: 6 issues — 2 opraveny (post-import skip pinned deps, apply 4xx na failure), 4 odlozeno (SSRF=Phase 3, UI typed IDs=Phase 2, cache binding=Phase 2, HF race=pre-existing)
   677	
   678	**Phase 1 Review fixy aplikovane:**
   679	- Fix: `_post_import_resolve` preskakuje deps s jinou strategii nez BASE_MODEL_HINT (Codex 4)
   680	- Fix: Apply endpointy vracejí 4xx při neúspěchu místo 200 (Codex 6)
   681	- Fix: `migrate_resolve_deps` předává request_id do apply (Gemini 1)
   682	
   683	**Review cyklus:** ✅ DOKONCEN
   684	- ✅ Claude review: 7 issues nalezeno a opraveno (unused imports, import inside loop, cache abstraction leak)
   685	- ✅ Gemini 3.1 review: 8 issues — 5 opraveno (tier gaps, FD leak, atomic write, broad except, validation), 3 odlozeno (thread safety=CLI app, search phase=Phase 1, TODO candidate_base_model=Phase 1)
   686	- ✅ Codex 5.4 review: 6 issues — 3 opraveno (model_id=0, fingerprint stale, ensure_providers truthiness), 3 odlozeno (apply no-op=Phase 1, provider field access=Phase 1 adapter, key unification=Phase 1 search)
   687	- ✅ Verified s realnymi Pydantic modely (Pack, PackDependency) — NE jen MagicMock
   688	
   689	**Review fixy aplikovane:**
   690	- Fix: tier boundary gaps — `>=` comparison misto range matching (Gemini 1.1)
   691	- Fix: PIL Image.open() s context managerem — FD leak (Gemini 1.3)
   692	- Fix: atomic cache write — temp file + replace() (Gemini 3.1)
   693	- Fix: model_id=0 rejected validaci (Codex 3)
   694	- Fix: fingerprint stale check v apply() (Codex 6)
   695	- Fix: exc_info=True v provider error logu (Gemini 4.2)
   696	- Fix: _ensure_providers truthiness bug — `is not None` misto `if self._providers:` (nalezeno testy)
   697	
   698	### Phase 1: Import pipeline + bug fixy
   699	
   700	**Cil:** Import z Civitai pouziva evidence ladder vcetne preview metadata.
   701	
   702	**Deliverables:**
   703	
   704	1. ✅ Fix BUG 1: `extractBaseModelHint()` smazano, nahrazeno `pack.base_model` prop
   705	2. ✅ Fix BUG 3: apply nikdy neprepise base_model filename stemem
   706	3. ✅ Fix BUG 4: typed API misto regex parsing (model_id, version_id, repo_id)
   707	
   708	4. ✅ **Import pipeline integrace:**
   709	   - ✅ Krok 3: analyze preview metadata (sidecar .json, dle calibration PNG tez)
   710	   - ✅ Krok 4: suggest_resolution() s evidence ladder E1-E6
   711	   - ✅ Krok 5: auto-apply dle tier pravidel (TIER-1/2, margin 0.15)
   712	   - ✅ Konfigurovatelny threshold — ResolveConfig.auto_apply_margin v config.json (Phase 6)
   713	
   714	5. ⚠️ Enriched AI context pro extract_parameters() — odlozeno (vyzaduje zmenu AvatarTaskService API)
   715	
   716	6. ✅ Deprecate /resolve-base-model (OpenAPI deprecated=True, docstring warning)
   717	
   718	7. ✅ Fix BUG 2: model_tagging() rule-based fallback bezi pri importu
   719	
   720	8. ✅ **Migration helper** (C8): `Store.migrate_resolve_deps(dry_run=True/False)`
   721	   - ✅ Projde packy s BASE_MODEL_HINT deps, spusti suggest
   722	   - ✅ Dry-run mode → reportuje co by se zmenilo
   723	   - ✅ Apply mode → auto-apply s tier/margin pravidly
   724	   - ✅ Error handling, ambiguous/low_confidence detection
   725	
   726	**Testy:** ✅ 40 NOVYCH TESTU
   727	- ✅ Unit Block A+B (13): BUG 3, BUG 4, PackService integration, Store facade, API schemas
   728	- ✅ Unit Block C (16): hints override, suggest s override, post-import resolve, delegates, auto-apply
   729	- ✅ Unit Block D (11): model_tagging, migration helper
   730	- ⚠️ Integration: import s evidence ladder — az po review
   731	- ⚠️ Smoke: kompletni import z Civitai s resolve — az po review
   732	
   733	### Phase 2: AI-enhanced resolution + UI
   734	
   735	**Cil:** MCP-enabled AI dependency resolution. DependencyResolverModal s Preview Analysis tabem.
   736	
   737	**DULEZITE:** Tato faze pridava AI vrstvu (E7) nad existujici E1-E6 evidence providers z Phase 0/1.
   738	AI NIKDY neprebije hash match (TIER-1). AI ceiling = 0.89. Prompty MUSI byt v konfiguracnich
   739	souborech (skills), NE hardcoded v Python kodu.
   740	
   741	---
   742	
   743	#### Phase 2 — Implementacni bloky
   744	
   745	##### BLOK A: Skill soubory (konfigurace — prompty + domain knowledge)
   746	
   747	Prompty pro AI ziji v `config/avatar/skills/*.md`. System je nacita dynamicky pres
   748	`src/avatar/skills.py` → `load_skills(skill_names)` → predava do `AITask.build_system_prompt()`.
   749	Uzivatel je muze editovat bez zmeny kodu. Custom override: `~/.synapse/avatar/custom-skills/`.
   750	
   751	| # | Soubor | Stav | Popis |
   752	|---|--------|------|-------|
   753	| A1 | `config/avatar/skills/model-resolution.md` | ✅ HOTOVO (otestovano) | **HLAVNI prompt pro AI dependency resolution.** ~240 radku. Otestovano na 3 scenarich (Illustrious, RealVisXL, no-match). Review: 6 issues nalezeno a opraveno. |
   754	| A2 | `config/avatar/skills/dependency-resolution.md` | ✅ Existuje (40 radku) | Obecny popis asset dependency modelu. Pouziva se jako reference knowledge. Bez zmen. |
   755	| A3 | `config/avatar/skills/model-types.md` | ✅ Existuje (32 radku) | Base model architectures (SD1.5, SDXL, Flux, Pony). Reference knowledge. Bez zmen. |
   756	| A4 | `config/avatar/skills/civitai-integration.md` | ✅ Existuje (70 radku) | Civitai API docs, CDN patterns. Reference knowledge. Bez zmen. |
   757	| A5 | `config/avatar/skills/huggingface-integration.md` | ✅ HOTOVO (novy) | HF Hub API reference: search, tree, download URL, LFS hash, repo types, common repos, eligibility matrix. ~95 radku. |
   758	
   759	**A1 — `model-resolution.md` — HOTOVO A OTESTOVANO**
   760	
   761	Soubor (~240 radku) obsahuje:
   762	1. **Ucel a task description** — co AI dela
   763	2. **Available tools** — 4 MCP tools: `search_civitai`, `analyze_civitai_model`, `search_huggingface`, `find_model_by_hash`
   764	3. **Input format** — presna struktura vstupu (PACK INFO, DEPENDENCY, EVIDENCE, PREVIEW HINTS)
   765	4. **4-krokova search strategie** — Analyze → Civitai search → Civitai analyze (version IDs) → HF search → Evaluate
   766	5. **Output JSON schema** — candidates[] + search_summary, field requirements per provider
   767	6. **Confidence scoring** — base ranges + adjustments + ceiling rule `min(calc, 0.89)`
   768	7. **Candidate deduplication** — same model on Civitai+HF = dva separate kandidaty
   769	8. **10 pravidel** — ceiling, no hallucination, max 5 candidates, max 5 tool calls, etc.
   770	9. **3 few-shot priklady** — strong match, no match (private), multiple candidates
   771	
   772	**Testovano na 3 scenarich:**
   773	- Illustrious LoRA → checkpoint: ✅ spravne nasel Illustrious XL
   774	- RealVisXL portrait → checkpoint: ✅ V4.0 s version_id+file_id, SD1.5 mismatch omitted
   775	- Private custom model: ✅ prazdny vysledek, zadna hallucinace
   776	
   777	**Review nalezl 6 issues, vsechny opraveny:**
   778	1. ✅ version_id/file_id null → pridano Step 2b (analyze_civitai_model)
   779	2. ✅ search_summary chybi → povinne pole
   780	3. ✅ confidence math v reasoning → explicitni aritmetika
   781	4. ✅ ceiling po adjustments → `min(calc, 0.89)` as final step
   782	5. ✅ architecture mismatch → omit rule
   783	6. ✅ retry bounds → max 5 tool calls, max 2 retry variace
   784	
   785	**A5 — `huggingface-integration.md` — NOVY SOUBOR**
   786	
   787	Reference knowledge pro AI (~95 radku): HF Hub API (search, tree, resolve endpoints),
   788	source identifier schema, repo types (single-file vs diffusers), file format detection,
   789	LFS hash verification, common model repos tabulka, eligibility per AssetKind.
   790	
   791	##### BLOK B: MCP tools (kod — nastroje, ktere AI pouziva)
   792	
   793	AI pres MCP protokol vola nastroje registrovane v `src/avatar/mcp/store_server.py`.
   794	Existujici MCP tools (21 kusu) jsou vsechny PLNE implementovane — zadne mocky.
   795	
   796	| # | Tool | Stav | Popis |
   797	|---|------|------|-------|
   798	| B1 | `search_civitai` | ✅ Existuje | Civitai search. Overit zda output format vraci model_id, version_id, file_id (pro typed CivitaiSelector). |
   799	| B2 | `search_huggingface` | ❌ NEEXISTUJE | **NOVY MCP tool.** HF API search, filename search, model card inspection, LFS pointer SHA256 fetch. Sirsi nez browse.py (ne jen diffusers filter). |
   800	| B3 | `find_model_by_hash` | ✅ Existuje | Hash lookup. Overit zda podporuje HF LFS pointery vedle Civitai. |
   801	| B4 | `suggest_asset_sources` | ✅ Existuje | Zdroje pro stazeni assetu. Muze byt uzitecne pro AI jako doplnkovy tool. |
   802	
   803	**B2 — `search_huggingface` MUSI podporovat:**
   804	- HF Hub API search (models endpoint) — ne jen diffusers pipeline filter
   805	- Filename search v HF repo (tree endpoint) — pro single-file repo (safetensors, ckpt)
   806	- Model card inspection (README.md) — base model info, tags
   807	- LFS pointer SHA256 fetch — pro hash matching (E1 evidence na HF)
   808	- Input: query string, optional filters (pipeline_tag, tags, library)
   809	- Output: seznam vysledku s repo_id, filenames, sizes, hashes, tags
   810	- Rate limiting a error handling
   811	
   812	##### BLOK C: Avatar task system rozsireni (kod)
   813	
   814	Existujici system: `AITask` ABC → `SKILL_NAMES` → skills loading → `build_system_prompt()` →
   815	LLM volani → `parse_result()` → `validate_output()`. Registrace v `TaskRegistry`.
   816	Engine vytvaren per-task v `AvatarTaskService._ensure_engine_for_task()`.
   817	
   818	| # | Soubor | Stav | Zmena |
   819	|---|--------|------|-------|
   820	| C1 | `src/avatar/tasks/base.py` | ✅ HOTOVO | Pridano `needs_mcp: bool = False` a `timeout_s: int = 120` na `AITask` ABC |
   821	| C2 | `src/avatar/task_service.py` | ✅ HOTOVO | V `_ensure_engine_for_task()` predava `mcp_servers` + `timeout=task.timeout_s` do AvatarEngine |
   822	| C3 | `src/avatar/tasks/dependency_resolution.py` | ✅ HOTOVO | `DependencyResolutionTask` — 5 skill files, needs_mcp=True, timeout_s=180, confidence ceiling enforcement |
   823	| C4 | `src/avatar/tasks/registry.py` | ✅ HOTOVO | `DependencyResolutionTask()` zaregistrovan v default registry |
   824	
   825	**C3 — `DependencyResolutionTask` design:**
   826	
   827	```python
   828	class DependencyResolutionTask(AITask):
   829	    task_type = "dependency_resolution"
   830	    SKILL_NAMES = ("model-resolution", "dependency-resolution", "model-types", "civitai-integration", "huggingface-integration")
   831	    needs_mcp = True          # AI pouziva search_civitai + analyze_civitai_model + search_huggingface + find_model_by_hash
   832	    timeout_s = 180           # MCP volani jsou pomalejsi nez pure prompt
   833	
   834	    def build_system_prompt(self, skills_content: str) -> str:
   835	        # skills_content = concatenace VSECH 4 skill souboru (nactenych dynamicky)
   836	        # Task NEPRIDAVA vlastni hardcoded prompt — VSECHEN prompt je ve skill souborech
   837	        return skills_content
   838	
   839	    def parse_result(self, raw_output: Dict) -> Dict:
   840	        # Mapuje AI JSON output → strukturovany format pro AIEvidenceProvider:
   841	        # - Extrahuje candidates[] z AI vystupu
   842	        # - Pro kazdy: display_name, provider (civitai/hf), confidence, reasoning
   843	        # - Pro civitai: model_id, version_id, file_id
   844	        # - Pro hf: repo_id, filename
   845	        # - Orizne confidence na max 0.89 (AI ceiling)
   846	        ...
   847	
   848	    def validate_output(self, output: Any) -> bool:
   849	        # Overuje:
   850	        # - output je dict s klicem "candidates" (list)
   851	        # - Kazdy kandidat ma povinne fieldy: display_name, confidence, reasoning
   852	        # - confidence je float v rozmezi 0.0-0.89
   853	        # - provider je "civitai" | "huggingface" | None
   854	        ...
   855	
   856	    def get_fallback(self) -> None:
   857	        return None  # Zadny fallback — E1-E6 evidence providers uz bezi nezavisle na AI
   858	```
   859	
   860	**KRITICKE:** `build_system_prompt()` NEMA pridavat vlastni hardcoded text. VSECHEN prompt
   861	obsah musi byt v skill souborech (`config/avatar/skills/`), aby sel editovat bez zmeny kodu.
   862	Jedina vyjimka: formatovani input dat (pack metadata) do promptu — to je v kodu, protoze
   863	je to strukturovana data transformace, ne prompt engineering.
   864	
   865	##### BLOK D: AIEvidenceProvider (kod — napojeni AI do resolve pipeline)
   866	
   867	| # | Soubor | Stav | Zmena |
   868	|---|--------|------|-------|
   869	| D1 | `src/store/evidence_providers.py` | ✅ HOTOVO | `AIEvidenceProvider` prepsany: `_build_ai_input()` formatuje strukturovany text, `_ai_candidate_to_hit()` mapuje civitai+hf kandidaty na EvidenceHit, spravne pouziva `TaskResult` (ne raw dict) |
   870	| D2 | `can_use_ai()` gate funkce | ✅ Phase 6 | `AIEvidenceProvider.supports()` kontroluje `is_ai_enabled(config)` + avatar dostupnost. Config: `resolve.enable_ai: bool`. |
   871	
   872	**D1 — AIEvidenceProvider opravy (vs. puvodni stub):**
   873	- `execute_task()` prijima string, ne dict → `_build_ai_input(ctx)` formatuje PACK INFO + DEPENDENCY + PREVIEW HINTS
   874	- Vysledek je `TaskResult` dataclass, ne dict → `task_result.success`, `task_result.output`
   875	- Podpora Civitai i HuggingFace kandidatu → `_ai_candidate_to_hit()` routi dle `provider`
   876	- CIVITAI_FILE strategie pokud mame `version_id` + `file_id`, jinak CIVITAI_MODEL_LATEST
   877	- Dedup key: `civitai:{model_id}:{version_id}` nebo `hf:{repo_id}:{filename}`
   878	- 18 unit testu v `tests/unit/store/test_evidence_providers.py`
   879	
   880	##### BLOK E: ResolveService rozsireni (kod — AI merge do suggest pipeline)
   881	
   882	| # | Soubor | Stav | Zmena |
   883	|---|--------|------|-------|
   884	| E1 | `src/store/resolve_service.py` | ✅ Existuje | **ROZSIRIT suggest():** Pokud `include_ai=True` a zadny TIER-1/2 kandidat z E1-E6, pustit AIEvidenceProvider. Merge + re-rank vysledky. |
   885	| E2 | Auto-apply threshold | Hard-coded 0.15 | **PRESUNOUT** do `store.yaml` jako `resolve.auto_apply_margin: 0.15` |
   886	| E3 | AI confidence ceiling | Hard-coded 0.89 | **DEFINOVAT** v `resolve_config.py` jako `AI_CONFIDENCE_CEILING = 0.89` |
   887	| E4 | DRY auto-apply helper | Duplicitni logika | **KONSOLIDOVAT** `_post_import_resolve()` a `migrate_resolve_deps()` do sdilene helper funkce |
   888	| E5 | Cache binding | Chybi | **PRIDAT** apply kontroluje `pack_name+dep_id` v cached candidates (Codex P1 #3) |
   889	
   890	##### BLOK F: UI — DependencyResolverModal + inline resolve (frontend)
   891	
   892	| # | Soubor | Stav | Zmena |
   893	|---|--------|------|-------|
   894	| F1 | `DependencyResolverModal.tsx` | ✅ IMPL+INTEG | **NOVY modal** — 5 tabu (Candidates, Preview, AI Resolve, Civitai, HF). CandidateCard, EvidenceGroups, confidence tiers. Integrovan v PackDetailPage. |
   895	| F2 | `usePackData.ts` | ✅ IMPL+INTEG | **ROZSIRENO:** suggestResolution, applyResolution, applyAndDownload mutace. isSuggesting/isApplying/isApplyingAndDownloading states. |
   896	| F3 | `PackDependenciesSection.tsx` | ✅ IMPL+INTEG | **ROZSIRENO:** onOpenDependencyResolver prop, per-asset resolve button opens modal (fallback to onResolvePack). |
   897	| F4 | `PackDetailPage.tsx` | ✅ IMPL+INTEG | **ROZSIRENO:** Resolver state, handlers (open/suggest/apply/applyAndDownload), eager suggest, DependencyResolverModal JSX, useAvatarAvailable. |
   898	| F5 | `useAvatarAvailable()` hook | ✅ IMPL+INTEG | **NOVY hook** — kontroluje avatarStatus.available via TanStack Query. Exportovan z hooks/index.ts. |
   899	| F6 | TS typy pro resolve | ✅ IMPL+INTEG | **PRIDANO:** ResolutionCandidate, SuggestResult, ApplyResult, EvidenceItemInfo, EvidenceGroupInfo, ConfidenceLevel, HF_ELIGIBLE_KINDS do types.ts. |
   900	| F7 | BUG 5: TS union + incompatible | ✅ OPRAVENO | AvatarStatus.state union rozsiren o 'incompatible', pridano engine_min_version field (lib/avatar/api.ts). |
   901	| F8 | BUG 6: AI gate v UI | ✅ OPRAVENO | Layout.tsx: zmeneno z `enabled !== false` na `available === true`. Koment upraven. |
   902	| F9 | HF tab | ✅ IMPL | DependencyResolverModal: HF tab ma `visible: HF_ELIGIBLE_KINDS.has(kind)` — skryty pro lora/embedding/upscaler. |
   903	
   904	##### BLOK G: HF search backend rozsireni
   905	
   906	| # | Soubor | Stav | Zmena |
   907	|---|--------|------|-------|
   908	| G1 | `src/clients/huggingface.py` nebo `browse.py` | ✅ Existuje (browse.py) | **ROZSIRIT:** Ne jen diffusers filter. Single-file repo support. |
   909	| G2 | HF LFS pointer SHA256 | ❌ Chybi | Fetch SHA256 z HF LFS pointeru pro hash matching (E1 evidence na HF) |
   910	
   911	##### BLOK H: Konfigurace a konstanty
   912	
   913	| # | Co | Kde | Popis |
   914	|---|-----|-----|-------|
   915	| H1 | Provider eligibility matrix | `src/store/resolve_config.py` | Ktera AssetKind muze hledat na HF — tabulka z sekce 2c. Musi byt editovatelna (config, ne hardcoded). |
   916	| H2 | AI confidence ceiling | `src/store/resolve_config.py` | `AI_CONFIDENCE_CEILING = 0.89` |
   917	| H3 | Auto-apply margin | `store.yaml` | `resolve.auto_apply_margin: 0.15` |
   918	| H4 | AI timeout | `src/avatar/tasks/dependency_resolution.py` | `timeout_s = 180` (konfigurovatelne v budoucnu pres avatar.yaml) |
   919	
   920	---
   921	
   922	#### Phase 2 — Poradi implementace (doporucene)
   923	
   924	```
   925	1. ✅ BLOK A: Skill soubory (model-resolution.md, huggingface-integration.md)
   926	2. ✅ BLOK C: AITask rozsireni (base.py, task_service.py, dependency_resolution.py, registry.py)
   927	3. ✅ BLOK B: search_huggingface MCP tool + fix analyze_civitai_model
   928	4. ✅ BLOK D: AIEvidenceProvider rewrite (_build_ai_input, _ai_candidate_to_hit, HF support)
   929	5. ✅ BLOK E: ResolveService — E1 uz fungovalo (include_ai flag + provider registration). E2-E5 refinementy odlozeny.
   930	6. ✅ BLOK H: Konfigurace a konstanty — AI_CONFIDENCE_CEILING, HF_ELIGIBLE_KINDS, AUTO_APPLY_MARGIN v resolve_config.py
   931	7. ✅ BLOK G: HF backend rozsireni — search_huggingface MCP tool hotov, _hf_hash_lookup() v evidence_providers.py
   932	8. ✅ BLOK F: UI — DependencyResolverModal + inline resolve (5-tab modal, 3 mutace, eager suggest)
   933	```
   934	
   935	**STAV:** PHASE 2 KOMPLETNI. Všechny bloky A-H hotovy. Celý chain funguje:
   936	`ResolveService.suggest(include_ai=True)` → `AIEvidenceProvider._build_ai_input()` →
   937	`AvatarTaskService.execute_task("dependency_resolution", ...)` → skills loaded →
   938	AvatarEngine + MCP tools → `DependencyResolutionTask.parse_result()` → confidence ceiling →
   939	`_ai_candidate_to_hit()` (civitai/hf) → `_merge_and_score()` → `SuggestResult`.
   940	
   941	---
   942	
   943	#### Phase 2 — Testy (aktualni stav)
   944	
   945	| Typ | Pocet | Soubor |
   946	|-----|-------|--------|
   947	| Unit: DependencyResolutionTask | 45 | `tests/unit/avatar/test_dependency_resolution_task.py` |
   948	| Unit: AIEvidenceProvider | 18 | `tests/unit/store/test_evidence_providers.py` (AI section) |
   949	| Unit: TaskRegistry | 59 total (3 new) | `tests/unit/avatar/test_task_registry.py` |
   950	| Integration: AI resolve chain | 23 | `tests/integration/test_ai_resolve_integration.py` |
   951	| Smoke: ResolveService+AI | 7 | `tests/integration/test_ai_resolve_smoke.py` |
   952	
   953	**Celkem Phase 2 unit/integ:** 93 testu pro AI resolution + 17 novych (config, evidence, MCP fallback).
   954	**E2E real provider testy:** 15 testu (5 scenaru × 3 providery), 100% PASS.
   955	Viz detailni test plan v sekci 11o
   956	
   957	#### Phase 2 — Review & Final Integration (2026-03-08)
   958	
   959	**Backend (Blocks G, H):**
   960	- ✅ `HF_ELIGIBLE_KINDS` frozenset, `AUTO_APPLY_MARGIN = 0.15` in resolve_config.py
   961	- ✅ AI_CONFIDENCE_CEILING deduplicated (dependency_resolution.py re-exports from resolve_config.py)
   962	- ✅ `_hf_hash_lookup()` in evidence_providers.py — verifies HF LFS SHA256 against known hash
   963	- ✅ 15 new config+evidence tests (8 HF eligibility, 3 auto-apply margin, 4 HF hash lookup)
   964	
   965	**Frontend (Block F):**
   966	- ✅ DependencyResolverModal.tsx — 5-tab modal (Candidates, Preview, AI Resolve, Civitai, HF)
   967	- ✅ usePackData.ts — 3 mutations (suggest/apply/applyAndDownload) + error toasts
   968	- ✅ useAvatarAvailable.ts hook — gates AI tab on `available === true`
   969	- ✅ PackDependenciesSection.tsx — per-asset resolve button → opens DependencyResolverModal
   970	- ✅ PackDetailPage.tsx — orchestrator state, handlers, eager suggest with stale-response guard
   971	- ✅ BUG 5 (TS union + incompatible), BUG 6 (AI gate available vs enabled)
   972	- ✅ HF tab visibility gated on HF_ELIGIBLE_KINDS
   973	- ✅ pack-data-invalidation.test.ts updated (2 new mutations categorized)
   974	
   975	**3-Review Cycle:**
   976	- **Claude:** Fixed hook ordering bug (openModal/closeModal before resolver handlers)
   977	- **Gemini:** Found race condition in eager suggest, missing catch handlers, nested buttons — all fixed
   978	- **Codex:** Found nested interactive controls in CandidateCard, unhandled AI resolve rejection — all fixed
   979	- **Testy:** 2096 backend passed (8 pre-existing failures), 1141 frontend passed, 0 new failures
   980	
   981	**Meilisearch Integration (2026-03-08):**
   982	- ✅ `CivitaiClient.search_meilisearch()` — fulltext search pres Civitai Meilisearch index
   983	  - Civitai REST API (`/api/v1/models?query=...`) nevraci mnoho modelu (Illustrious-XL, Detail Tweaker)
   984	  - Meilisearch (`search-new.civitai.com/multi-search`) je stejny index jako Civitai web UI — najde vse
   985	  - Token konfigurovatelny pres `CIVITAI_MEILISEARCH_TOKEN` env var (public token, ne secret)
   986	- ✅ MCP `search_civitai` tool: Meilisearch-first, REST API fallback
   987	- ✅ Defensive types handling v `search_models()` (string + list input)
   988	- ✅ 2 nove unit testy: meilisearch_success_skips_rest, meilisearch_failure_falls_back_to_rest
   989	
   990	**Claude Permission Fix (2026-03-08):**
   991	- ✅ `task_service.py` predava `permission_mode`/`allowed_tools` z avatar.yaml do AvatarEngine kwargs
   992	  - Root cause: AvatarEngine bez config objektu pouziva kwargs, task_service je nepredaval
   993	  - Claude defaultoval na `acceptEdits` → odmital MCP tools bez interaktivniho potvrzeni
   994	- ✅ `avatar.yaml.example` aktualizovan: `permission_mode: bypassPermissions` + `allowed_tools` s MCP wildcard
   995	- ✅ `~/.synapse/store/state/avatar.yaml` aktualizovan
   996	
   997	**E2E Testy s realnymi AI providery (2026-03-08):**
   998	- ✅ `tests/e2e_resolve_real.py` — 5 scenaru × 2 providery (gemini, codex) = 10 testu
   999	- ✅ `tests/e2e_resolve_claude.py` — 5 scenaru × claude (standalone, nelze v Claude Code)
  1000	- Scenare: SDXL Base, Illustrious XL, Flux.1 Dev, Detail Tweaker LoRA, Pony V6 XL
  1001	
  1002	**Finalni E2E vysledky — 15/15 PASS (100%):**
  1003	
  1004	| Scenario | Gemini 3 Pro | Codex 5.3 | Claude Opus 4.6 |
  1005	|---|---|---|---|
  1006	| SDXL Base Checkpoint | PASS 89% (Civitai+HF) | PASS 89% (Civitai+HF) | PASS 89% (Civitai+HF) |
  1007	| Illustrious XL | PASS 80% (Civitai) | PASS 79% (Civitai) | PASS 75% (Civitai) |
  1008	| Flux.1 Dev | PASS 89% (Civitai+HF) | PASS 87% (HF) | PASS 89% (HF) |
  1009	| Detail Tweaker LoRA | PASS 89% (Civitai) | PASS 87% (Civitai) | PASS 89% (Civitai) |
  1010	| Pony V6 XL | PASS 88% (Civitai+HF) | PASS 89% (Civitai+HF) | PASS 89% (Civitai+HF) |
  1011	
  1012	**Code Review (post-Meilisearch):**
  1013	- 0 Critical, 3 Medium, 8 Low issues nalezeny
  1014	- Medium: token → env var (opraveno), nsfwLevel parsing (opraveno), limit bounds (opraveno)
  1015	- Low: security warning v example config (opraveno), fallback komentare (opraveno), 2 nove testy (opraveno)
  1016	- 1988 backend tests passed, 0 failed
  1017	
  1018	**Phase 2 STAV: ✅ KOMPLETNI** — commit `4958309`, branch `feat/resolve-model-redesign`
  1019	
  1020	---
  1021	
  1022	#### Phase 2.5: Preview Enrichment + Bug Fixes (2026-03-09)
  1023	
  1024	**Cil:** Odstranit `model_id=0` placeholder gap — preview/file hinty ted resolvuji skutecne Civitai IDs.
  1025	
  1026	**Problem:**
  1027	- `PreviewMetaEvidenceProvider` a `FileMetaEvidenceProvider` vytvarily kandidaty s `model_id=0`
  1028	- `resolve_validation.py` odmitalo `model_id=0` jako "invalid zero value"
  1029	- `_post_import_resolve()` nekontrolovala `ApplyResult.success` — false "Auto-applied" log
  1030	- Celkove: preview hinty nikdy nevedly k realnym downloadable kandidatum bez AI provideru
  1031	
  1032	**Reseni: Enrichment v PreviewMetaEvidenceProvider** (stejny pattern jako HashEvidenceProvider):
  1033	1. ✅ Provider prijima `pack_service_getter` → pristup k Civitai klientu
  1034	2. ✅ Hash lookup: `civitai.get_model_by_hash(hint.hash)` → realne `model_id/version_id/file_id`
  1035	3. ✅ Name search fallback: `search_meilisearch(stem)` → name+kind matching → `get_model()` pro latest
  1036	4. ✅ Hash cache pro deduplikaci API callu v ramci jednoho `suggest()`
  1037	5. ✅ Confidence boost +0.05 pro enriched kandidaty
  1038	6. ✅ Backward compatible: bez `pack_service_getter` funguje v placeholder modu
  1039	
  1040	**Bug fixy:**
  1041	- ✅ `_post_import_resolve()` ted kontroluje `apply_result.success` + predava `request_id`
  1042	- ✅ Apply failure se loguje jako warning, ne false success
  1043	
  1044	**Zmeny:**
  1045	| Soubor | Zmena |
  1046	|--------|-------|
  1047	| `src/store/evidence_providers.py` | PreviewMetaEvidenceProvider enrichment (hash+name), helpers |
  1048	| `src/store/resolve_service.py:160` | Wiring: `PreviewMetaEvidenceProvider(ps_getter)` |
  1049	| `src/store/__init__.py:635` | Bug fix: check `apply_result.success` |
  1050	| `tests/unit/store/test_evidence_providers.py` | +10 testu (TestPreviewMetaEnrichment) |
  1051	| `tests/unit/store/test_phase1_import_pipeline.py` | +1 test, 1 fix |
  1052	
  1053	**Testy:** 1827 backend + 1153 frontend = 2980 passed, 0 failed
  1054	
  1055	**Identifikace problemu:** Analyze Claude + Explore agent + Codex 5.4 (3 nezavisle analyzy)
  1056	
  1057	---
  1058	
  1059	### Phase 3: Local Resolve — import lokalnich souboru ✅ KOMPLETNI
  1060	
  1061	**Cil:** Uzivatel muze resolvovat dependenci z lokalniho souboru misto stahovani.
  1062	Soubor se hashuje, zkopiruje do blob store, a enrichuje se metadata z Civitai/HF.
  1063	
  1064	**Stav:** ✅ KOMPLETNI — commit `6f8b485` (2026-03-10), branch `feat/resolve-model-redesign`
  1065	
  1066	**Tri scenare:**
  1067	
  1068	**A) Dep uz ma remote zdroj (Civitai/HF):** ✅ IMPL+INTEG
  1069	- Dep je resolved na civitai_file(model_id=123, sha256=abc...) ale soubor neni stazeny
  1070	- Uzivatel otevre Local tab, zvoli slozku
  1071	- System porovna SHA256/filename → doporuci konkretni soubor ("tohle vypada jako ten spravny")
  1072	- Uzivatel potvrdi → copy do blob store, dep resolvovana
  1073	- **Implementace:** `LocalFileService.recommend()` s confidence scoring:
  1074	  sha256_exact (1.0) > filename_exact (0.85) > filename_stem (0.6) > none (0.0)
  1075	
  1076	**B) Dep nema remote zdroj, enrichment pres hash:** ✅ IMPL+INTEG
  1077	- Custom pack, dep ma jen nazev (napr. `juggernaut_xl.safetensors`)
  1078	- Uzivatel vybere soubor → system hashuje (SHA256)
  1079	- Hash → Civitai by-hash API → najde model_id, version_id, canonical_source
  1080	- ~~Hash → HuggingFace lookup (pokud Civitai nevi)~~ (HF enrichment az Phase 4)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_config.py | nl -ba | sed -n '1,280p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Resolve configuration — tier boundaries, asset kind config, compatibility rules.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 sections 2b, 2c, 2h, 4, 5.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from dataclasses import dataclass, field
    10	from typing import Any, Dict, FrozenSet, Optional, Set
    11	
    12	from .models import AssetKind
    13	
    14	
    15	# =============================================================================
    16	# Confidence Tiers — non-overlapping ranges
    17	# =============================================================================
    18	
    19	@dataclass(frozen=True)
    20	class TierConfig:
    21	    """Configuration for a confidence tier."""
    22	    tier: int
    23	    min: float   # inclusive
    24	    max: float   # inclusive
    25	    label: str
    26	
    27	
    28	TIER_CONFIGS = [
    29	    TierConfig(tier=1, min=0.90, max=1.00, label="Exact match"),
    30	    TierConfig(tier=2, min=0.75, max=0.89, label="High confidence"),
    31	    TierConfig(tier=3, min=0.50, max=0.74, label="Possible match"),
    32	    TierConfig(tier=4, min=0.30, max=0.49, label="Hint only"),
    33	]
    34	
    35	# AI confidence ceiling — AI can never exceed TIER-2 max
    36	AI_CONFIDENCE_CEILING = 0.89
    37	
    38	
    39	def get_tier_for_confidence(confidence: float) -> int:
    40	    """Return the tier number for a given confidence value.
    41	
    42	    Uses >= comparison against tier minimums (sorted descending) to avoid
    43	    gaps between tier boundaries.
    44	    """
    45	    for tc in TIER_CONFIGS:  # Already sorted T1→T4 (descending min)
    46	        if confidence >= tc.min:
    47	            return tc.tier
    48	    return 4  # Below all tier minimums
    49	
    50	
    51	def get_tier_ceiling(tier: int) -> float:
    52	    """Return the maximum confidence allowed for a given tier."""
    53	    for tc in TIER_CONFIGS:
    54	        if tc.tier == tier:
    55	            return tc.max
    56	    return 0.49  # Default to Tier 4 ceiling
    57	
    58	
    59	def get_tier_label(tier: int) -> str:
    60	    """Return human-readable label for a tier."""
    61	    for tc in TIER_CONFIGS:
    62	        if tc.tier == tier:
    63	            return tc.label
    64	    return "Unknown"
    65	
    66	
    67	# =============================================================================
    68	# Asset Kind Configuration — per-kind settings for resolution
    69	# =============================================================================
    70	
    71	@dataclass(frozen=True)
    72	class AssetKindConfig:
    73	    """Per-kind configuration for model resolution."""
    74	    extensions: FrozenSet[str]
    75	    civitai_filter: Optional[str] = None
    76	    hf_eligible: bool = False
    77	    hf_hash_lookup: bool = False
    78	
    79	
    80	ASSET_KIND_CONFIG: Dict[AssetKind, AssetKindConfig] = {
    81	    AssetKind.CHECKPOINT: AssetKindConfig(
    82	        extensions=frozenset({".safetensors", ".ckpt"}),
    83	        civitai_filter="Checkpoint",
    84	        hf_eligible=True,
    85	        hf_hash_lookup=True,
    86	    ),
    87	    AssetKind.LORA: AssetKindConfig(
    88	        extensions=frozenset({".safetensors"}),
    89	        civitai_filter="LORA",
    90	        hf_eligible=False,
    91	        hf_hash_lookup=False,
    92	    ),
    93	    AssetKind.VAE: AssetKindConfig(
    94	        extensions=frozenset({".safetensors", ".pt"}),
    95	        civitai_filter="VAE",
    96	        hf_eligible=True,
    97	        hf_hash_lookup=False,
    98	    ),
    99	    AssetKind.CONTROLNET: AssetKindConfig(
   100	        extensions=frozenset({".safetensors", ".pth"}),
   101	        civitai_filter="Controlnet",
   102	        hf_eligible=True,
   103	        hf_hash_lookup=False,
   104	    ),
   105	    AssetKind.EMBEDDING: AssetKindConfig(
   106	        extensions=frozenset({".safetensors", ".pt", ".bin"}),
   107	        civitai_filter="TextualInversion",
   108	        hf_eligible=False,
   109	        hf_hash_lookup=False,
   110	    ),
   111	    AssetKind.UPSCALER: AssetKindConfig(
   112	        extensions=frozenset({".pth", ".safetensors"}),
   113	        civitai_filter="Upscaler",
   114	        hf_eligible=False,
   115	        hf_hash_lookup=False,
   116	    ),
   117	}
   118	
   119	
   120	def get_kind_config(kind: AssetKind) -> AssetKindConfig:
   121	    """Get configuration for an asset kind. Returns defaults for unknown kinds."""
   122	    return ASSET_KIND_CONFIG.get(kind, AssetKindConfig(
   123	        extensions=frozenset({".safetensors"}),
   124	    ))
   125	
   126	
   127	# Convenience set: asset kinds eligible for HuggingFace search
   128	HF_ELIGIBLE_KINDS: FrozenSet[AssetKind] = frozenset(
   129	    kind for kind, cfg in ASSET_KIND_CONFIG.items() if cfg.hf_eligible
   130	)
   131	
   132	# Auto-apply margin: minimum confidence gap between top-1 and top-2 candidate
   133	# for automatic resolution during import. Candidates within this margin
   134	# are presented to user for manual selection.
   135	AUTO_APPLY_MARGIN = 0.15
   136	
   137	
   138	def get_auto_apply_margin(config: Any = None) -> float:
   139	    """Get auto-apply margin from config, falling back to default constant."""
   140	    try:
   141	        if config is not None:
   142	            resolve = getattr(config, "resolve", None)
   143	            if resolve is not None:
   144	                val = getattr(resolve, "auto_apply_margin", None)
   145	                if isinstance(val, (int, float)):
   146	                    return float(val)
   147	    except (AttributeError, TypeError, ValueError) as e:
   148	        import logging
   149	        logging.getLogger(__name__).debug("Failed to read auto_apply_margin from config: %s", e)
   150	    return AUTO_APPLY_MARGIN
   151	
   152	
   153	def is_ai_enabled(config: Any = None) -> bool:
   154	    """Check if AI-assisted resolution is enabled in config."""
   155	    try:
   156	        if config is not None:
   157	            resolve = getattr(config, "resolve", None)
   158	            if resolve is not None:
   159	                val = getattr(resolve, "enable_ai", None)
   160	                if isinstance(val, bool):
   161	                    return val
   162	    except (AttributeError, TypeError) as e:
   163	        import logging
   164	        logging.getLogger(__name__).debug("Failed to read enable_ai from config: %s", e)
   165	    return True
   166	
   167	
   168	# =============================================================================
   169	# Cross-Kind Compatibility Rules
   170	# =============================================================================
   171	
   172	# base_model_category → compatible categories
   173	COMPATIBILITY_RULES: Dict[str, Set[str]] = {
   174	    "SD 1.5": {"SD 1.5"},
   175	    "SDXL": {"SDXL", "Pony"},
   176	    "Illustrious": {"SDXL", "Illustrious"},
   177	    "Pony": {"SDXL", "Pony"},
   178	    "Flux": {"Flux"},
   179	    "Flux.1 D": {"Flux", "Flux.1 D"},
   180	    "Flux.1 S": {"Flux", "Flux.1 S"},
   181	    "SD 3.5": {"SD 3.5"},
   182	}
   183	
   184	
   185	def check_cross_kind_compatibility(
   186	    pack_base_model: Optional[str],
   187	    candidate_base_model: Optional[str],
   188	    kind: AssetKind,
   189	) -> list[str]:
   190	    """Check if a candidate is compatible with the pack's base model.
   191	
   192	    Returns list of warning strings (empty = compatible).
   193	    No check for checkpoints — they define the base model.
   194	    """
   195	    # Checkpoints define the base model, no compatibility check
   196	    if kind == AssetKind.CHECKPOINT:
   197	        return []
   198	
   199	    # If either is unknown, can't check
   200	    if not pack_base_model or not candidate_base_model:
   201	        return []
   202	
   203	    pack_compat = COMPATIBILITY_RULES.get(pack_base_model)
   204	    if pack_compat is None:
   205	        return []  # Unknown base model, skip check
   206	
   207	    if candidate_base_model not in pack_compat:
   208	        return [
   209	            f"Base model mismatch: pack uses '{pack_base_model}' "
   210	            f"but candidate is for '{candidate_base_model}'"
   211	        ]
   212	
   213	    return []

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/evidence_providers.py | nl -ba | sed -n '1,360p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Evidence providers — 6 providers for dependency resolution evidence gathering.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 section 11d.
     5	
     6	Providers:
     7	- HashEvidenceProvider (E1, Tier 1): SHA256 lookup on Civitai/HF
     8	- PreviewMetaEvidenceProvider (E2+E3, Tier 2): Preview metadata
     9	- FileMetaEvidenceProvider (E5, Tier 3): Filename patterns
    10	- AliasEvidenceProvider (E6, Tier 3): Configured aliases
    11	- SourceMetaEvidenceProvider (E4, Tier 4): Civitai baseModel field
    12	- AIEvidenceProvider (E7, Tier AI): AI-assisted analysis (ceiling 0.89)
    13	"""
    14	
    15	from __future__ import annotations
    16	
    17	import logging
    18	from typing import Any, Callable, Optional, Protocol, runtime_checkable
    19	
    20	from .models import AssetKind, DependencySelector, SelectorStrategy, CivitaiSelector
    21	from .resolve_config import AI_CONFIDENCE_CEILING, get_kind_config, is_ai_enabled
    22	from .resolve_models import (
    23	    CandidateSeed,
    24	    EvidenceHit,
    25	    EvidenceItem,
    26	    PreviewModelHint,
    27	    ProviderResult,
    28	    ResolveContext,
    29	)
    30	
    31	logger = logging.getLogger(__name__)
    32	
    33	
    34	@runtime_checkable
    35	class EvidenceProvider(Protocol):
    36	    """Protocol for evidence providers.
    37	
    38	    Same pattern as DependencyResolver — duck typing, @runtime_checkable.
    39	    """
    40	
    41	    @property
    42	    def tier(self) -> int:
    43	        """Confidence tier of this provider (1-4)."""
    44	        ...
    45	
    46	    def supports(self, context: ResolveContext) -> bool:
    47	        """Whether this provider is relevant for the given context."""
    48	        ...
    49	
    50	    def gather(self, context: ResolveContext) -> ProviderResult:
    51	        """Gather evidence. Returns hits with candidates + evidence."""
    52	        ...
    53	
    54	
    55	class HashEvidenceProvider:
    56	    """E1: SHA256 lookup on Civitai + HuggingFace. Tier 1."""
    57	
    58	    tier = 1
    59	
    60	    def __init__(self, pack_service_getter: Callable):
    61	        self._ps = pack_service_getter
    62	
    63	    def supports(self, ctx: ResolveContext) -> bool:
    64	        return True  # Always applicable if we have a hash
    65	
    66	    def gather(self, ctx: ResolveContext) -> ProviderResult:
    67	        """Look up hash from existing lock or Civitai file metadata."""
    68	        hits = []
    69	        warnings = []
    70	
    71	        dep = ctx.dependency
    72	        if dep is None:
    73	            return ProviderResult()
    74	
    75	        # Get SHA256 from lock data if available
    76	        sha256 = None
    77	        lock = getattr(dep, "lock", None)
    78	        if lock:
    79	            sha256 = getattr(lock, "sha256", None)
    80	
    81	        if not sha256:
    82	            return ProviderResult()
    83	
    84	        pack_service = self._ps()
    85	        if pack_service is None:
    86	            return ProviderResult(error="PackService not available")
    87	
    88	        # Try Civitai hash lookup
    89	        civitai = getattr(pack_service, "civitai", None)
    90	        if civitai:
    91	            try:
    92	                result = civitai.get_model_by_hash(sha256)
    93	                if result:
    94	                    # CivitaiModelVersion is a dataclass — use getattr, not .get()
    95	                    model_id = getattr(result, "model_id", None) or getattr(result, "modelId", None)
    96	                    version_id = getattr(result, "id", None)
    97	                    file_id = _extract_file_id(result, sha256)
    98	                    display_name = getattr(result, "name", "Unknown")
    99	
   100	                    if model_id and version_id:
   101	                        # Extract base_model from Civitai API response
   102	                        candidate_base_model = (
   103	                            getattr(result, "base_model", None)
   104	                            or getattr(result, "baseModel", None)
   105	                        )
   106	                        seed = CandidateSeed(
   107	                            key=f"civitai:{model_id}:{version_id}",
   108	                            selector=DependencySelector(
   109	                                strategy=SelectorStrategy.CIVITAI_FILE,
   110	                                civitai=CivitaiSelector(
   111	                                    model_id=model_id,
   112	                                    version_id=version_id,
   113	                                    file_id=file_id,
   114	                                ),
   115	                            ),
   116	                            display_name=display_name,
   117	                            provider_name="civitai",
   118	                            base_model=candidate_base_model,
   119	                        )
   120	                        hits.append(EvidenceHit(
   121	                            candidate=seed,
   122	                            provenance=f"hash:{sha256[:12]}",
   123	                            item=EvidenceItem(
   124	                                source="hash_match",
   125	                                description=f"SHA256 match on Civitai",
   126	                                confidence=0.95,
   127	                                raw_value=sha256,
   128	                            ),
   129	                        ))
   130	            except Exception as e:
   131	                warnings.append(f"Civitai hash lookup failed: {e}")
   132	
   133	        # HF hash lookup (only if kind is eligible for HF hash check)
   134	        kind_config = get_kind_config(ctx.kind)
   135	        if kind_config.hf_hash_lookup:
   136	            hf_hit = _hf_hash_lookup(pack_service, sha256, ctx)
   137	            if hf_hit:
   138	                hits.append(hf_hit)
   139	
   140	        return ProviderResult(hits=hits, warnings=warnings)
   141	
   142	
   143	class PreviewMetaEvidenceProvider:
   144	    """E2+E3: Preview metadata (PNG embedded + API sidecar). Tier 2.
   145	
   146	    Enriches preview hints with real Civitai model IDs via:
   147	    1. Hash lookup (get_model_by_hash) — most reliable
   148	    2. Name search (meilisearch/search_models) — fallback
   149	    3. Placeholder (model_id=0) — last resort for AI/manual resolution
   150	    """
   151	
   152	    tier = 2
   153	
   154	    def __init__(self, pack_service_getter: Optional[Callable] = None):
   155	        self._ps = pack_service_getter
   156	
   157	    def supports(self, ctx: ResolveContext) -> bool:
   158	        return bool(ctx.preview_hints)
   159	
   160	    def gather(self, ctx: ResolveContext) -> ProviderResult:
   161	        """Convert preview hints to evidence hits, enriching with real IDs."""
   162	        hits = []
   163	        warnings = []
   164	
   165	        civitai = self._get_civitai()
   166	        # Cache resolved hashes to avoid duplicate API calls within one suggest
   167	        hash_cache: dict[str, Optional[dict]] = {}
   168	
   169	        for hint in ctx.preview_hints:
   170	            if not hint.resolvable:
   171	                continue
   172	
   173	            confidence = 0.85 if hint.source_type == "png_embedded" else 0.82
   174	            source = ("preview_embedded" if hint.source_type == "png_embedded"
   175	                      else "preview_api_meta")
   176	
   177	            # Try to resolve real Civitai IDs
   178	            resolved = self._resolve_hint(hint, civitai, hash_cache, warnings)
   179	
   180	            if resolved:
   181	                model_id, version_id, file_id, display_name = resolved
   182	                seed = CandidateSeed(
   183	                    key=f"civitai:{model_id}:{version_id}",
   184	                    selector=DependencySelector(
   185	                        strategy=SelectorStrategy.CIVITAI_FILE,
   186	                        civitai=CivitaiSelector(
   187	                            model_id=model_id,
   188	                            version_id=version_id,
   189	                            file_id=file_id,
   190	                        ),
   191	                    ),
   192	                    display_name=display_name,
   193	                    provider_name="civitai",
   194	                )
   195	                # Boost confidence when we have real IDs
   196	                confidence = min(confidence + 0.05, 0.90)
   197	            else:
   198	                seed = CandidateSeed(
   199	                    key=f"preview:{hint.filename}",
   200	                    selector=DependencySelector(
   201	                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
   202	                        civitai=CivitaiSelector(model_id=0),  # Unresolved
   203	                    ),
   204	                    display_name=hint.filename,
   205	                    provider_name="civitai",
   206	                )
   207	
   208	            hits.append(EvidenceHit(
   209	                candidate=seed,
   210	                provenance=f"preview:{hint.source_image}",
   211	                item=EvidenceItem(
   212	                    source=source,
   213	                    description=f"{hint.source_type}: {hint.filename}",
   214	                    confidence=confidence,
   215	                    raw_value=hint.raw_value,
   216	                ),
   217	            ))
   218	
   219	        return ProviderResult(hits=hits, warnings=warnings)
   220	
   221	    def _get_civitai(self) -> Any:
   222	        """Get Civitai client from pack_service, or None."""
   223	        if self._ps is None:
   224	            return None
   225	        ps = self._ps()
   226	        if ps is None:
   227	            return None
   228	        return getattr(ps, "civitai", None)
   229	
   230	    def _resolve_hint(
   231	        self,
   232	        hint: PreviewModelHint,
   233	        civitai: Any,
   234	        hash_cache: dict,
   235	        warnings: list,
   236	    ) -> Optional[tuple]:
   237	        """Try to resolve a hint to (model_id, version_id, file_id, display_name).
   238	
   239	        Strategy:
   240	        1. Hash lookup (most reliable, single API call)
   241	        2. Name search via Meilisearch (fallback)
   242	        """
   243	        if civitai is None:
   244	            return None
   245	
   246	        # 1. Hash lookup
   247	        if hint.hash:
   248	            result = self._lookup_by_hash(hint.hash, civitai, hash_cache, warnings)
   249	            if result:
   250	                return result
   251	
   252	        # 2. Name search fallback
   253	        return self._search_by_name(hint, civitai, warnings)
   254	
   255	    def _lookup_by_hash(
   256	        self,
   257	        hash_value: str,
   258	        civitai: Any,
   259	        hash_cache: dict,
   260	        warnings: list,
   261	    ) -> Optional[tuple]:
   262	        """Look up model by hash, with caching."""
   263	        if hash_value in hash_cache:
   264	            cached = hash_cache[hash_value]
   265	            if cached is None:
   266	                return None
   267	            return cached
   268	
   269	        try:
   270	            result = civitai.get_model_by_hash(hash_value)
   271	            if result:
   272	                # CivitaiModelVersion is a dataclass — use attrs, not .get()
   273	                model_id = getattr(result, "model_id", None)
   274	                version_id = getattr(result, "id", None)
   275	                display_name = getattr(result, "name", "Unknown")
   276	                file_id = _extract_file_id_from_version(result, hash_value)
   277	
   278	                if model_id and version_id:
   279	                    resolved = (model_id, version_id, file_id, display_name)
   280	                    hash_cache[hash_value] = resolved
   281	                    return resolved
   282	
   283	            hash_cache[hash_value] = None
   284	        except Exception as e:
   285	            warnings.append(f"Preview hash lookup failed for {hash_value[:10]}: {e}")
   286	            hash_cache[hash_value] = None
   287	
   288	        return None
   289	
   290	    def _search_by_name(
   291	        self,
   292	        hint: PreviewModelHint,
   293	        civitai: Any,
   294	        warnings: list,
   295	    ) -> Optional[tuple]:
   296	        """Search Civitai by model name extracted from hint."""
   297	        # Build search query from filename stem
   298	        stem = _extract_stem(hint.filename)
   299	        if not stem or len(stem) < 3:
   300	            return None
   301	
   302	        try:
   303	            # Prefer Meilisearch (faster, better fuzzy matching)
   304	            search_fn = getattr(civitai, "search_meilisearch", None)
   305	            if search_fn is None:
   306	                search_fn = getattr(civitai, "search_models", None)
   307	            if search_fn is None:
   308	                return None
   309	
   310	            results = search_fn(query=stem, limit=5)
   311	            items = results.get("items", []) if isinstance(results, dict) else []
   312	
   313	            if not items:
   314	                return None
   315	
   316	            # Find best match: prefer exact name match, then kind match
   317	            for item in items:
   318	                item_name = (item.get("name") or "").lower()
   319	                item_type = (item.get("type") or "").lower()
   320	                model_id = item.get("id")
   321	
   322	                if not model_id:
   323	                    continue
   324	
   325	                # Check kind compatibility
   326	                if hint.kind and not _kind_matches_civitai_type(hint.kind, item_type):
   327	                    continue
   328	
   329	                # Check name similarity (normalize underscores/spaces for comparison)
   330	                stem_norm = stem.lower().replace("_", " ").replace("-", " ")
   331	                name_norm = item_name.replace("_", " ").replace("-", " ")
   332	                if stem_norm not in name_norm and name_norm not in stem_norm:
   333	                    continue
   334	
   335	                # Get latest version from model details
   336	                version_id = None
   337	                file_id = None
   338	                try:
   339	                    model_data = civitai.get_model(model_id)
   340	                    if model_data:
   341	                        versions = model_data.get("modelVersions", [])
   342	                        if versions:
   343	                            latest = versions[0]
   344	                            version_id = latest.get("id")
   345	                            files = latest.get("files", [])
   346	                            if files:
   347	                                file_id = files[0].get("id")
   348	                except Exception:
   349	                    pass
   350	
   351	                if version_id:
   352	                    display_name = item.get("name", stem)
   353	                    return (model_id, version_id, file_id, display_name)
   354	
   355	        except Exception as e:
   356	            logger.debug("[preview-provider] Name search failed for '%s': %s", stem, e)
   357	
   358	        return None
   359	
   360	

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/evidence_providers.py | nl -ba | sed -n '360,760p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   360	
   361	class FileMetaEvidenceProvider:
   362	    """E5: Filename patterns, architecture detection. Tier 3."""
   363	
   364	    tier = 3
   365	
   366	    def supports(self, ctx: ResolveContext) -> bool:
   367	        return True
   368	
   369	    def gather(self, ctx: ResolveContext) -> ProviderResult:
   370	        """Extract evidence from filename patterns."""
   371	        dep = ctx.dependency
   372	        if dep is None:
   373	            return ProviderResult()
   374	
   375	        filename = getattr(dep, "filename", None) or getattr(dep, "name", None)
   376	        if not filename:
   377	            return ProviderResult()
   378	
   379	        hits = []
   380	
   381	        # Extract stem and try to match known patterns
   382	        stem = _extract_stem(filename)
   383	        if stem:
   384	            seed = CandidateSeed(
   385	                key=f"file:{stem}",
   386	                selector=DependencySelector(
   387	                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
   388	                    civitai=CivitaiSelector(model_id=0),  # Needs search
   389	                ),
   390	                display_name=stem,
   391	                provider_name="civitai",
   392	            )
   393	            hits.append(EvidenceHit(
   394	                candidate=seed,
   395	                provenance=f"file:{filename}",
   396	                item=EvidenceItem(
   397	                    source="file_metadata",
   398	                    description=f"Filename stem: {stem}",
   399	                    confidence=0.60,
   400	                    raw_value=filename,
   401	                ),
   402	            ))
   403	
   404	        return ProviderResult(hits=hits)
   405	
   406	
   407	class AliasEvidenceProvider:
   408	    """E6: Configured aliases (Civitai + HF targets). Tier 3."""
   409	
   410	    tier = 3
   411	
   412	    def __init__(self, layout_getter: Callable):
   413	        self._layout = layout_getter
   414	
   415	    def supports(self, ctx: ResolveContext) -> bool:
   416	        return True
   417	
   418	    def gather(self, ctx: ResolveContext) -> ProviderResult:
   419	        """Look up configured aliases from store config."""
   420	        layout = self._layout()
   421	        if layout is None:
   422	            return ProviderResult()
   423	
   424	        # Read base_model_aliases from config
   425	        aliases = _read_aliases(layout)
   426	        if not aliases:
   427	            return ProviderResult()
   428	
   429	        dep = ctx.dependency
   430	        if dep is None:
   431	            return ProviderResult()
   432	
   433	        # Check if dependency name matches an alias
   434	        dep_name = getattr(dep, "name", None) or getattr(dep, "filename", None)
   435	        base_model = getattr(dep, "base_model", None)
   436	
   437	        hits = []
   438	        for alias_key, alias_target in aliases.items():
   439	            if dep_name and alias_key.lower() in dep_name.lower():
   440	                hit = _alias_to_hit(alias_key, alias_target)
   441	                if hit:
   442	                    hits.append(hit)
   443	            elif base_model and alias_key == base_model:
   444	                hit = _alias_to_hit(alias_key, alias_target)
   445	                if hit:
   446	                    hits.append(hit)
   447	
   448	        return ProviderResult(hits=hits)
   449	
   450	
   451	class SourceMetaEvidenceProvider:
   452	    """E4: Civitai baseModel field (hint only). Tier 4."""
   453	
   454	    tier = 4
   455	
   456	    def supports(self, ctx: ResolveContext) -> bool:
   457	        return True
   458	
   459	    def gather(self, ctx: ResolveContext) -> ProviderResult:
   460	        """Use Civitai baseModel as a low-confidence hint."""
   461	        dep = ctx.dependency
   462	        if dep is None:
   463	            return ProviderResult()
   464	
   465	        base_model = getattr(dep, "base_model", None)
   466	        if not base_model:
   467	            return ProviderResult()
   468	
   469	        seed = CandidateSeed(
   470	            key=f"source_meta:{base_model}",
   471	            selector=DependencySelector(
   472	                strategy=SelectorStrategy.BASE_MODEL_HINT,
   473	                base_model=base_model,
   474	            ),
   475	            display_name=base_model,
   476	            provider_name="civitai",
   477	        )
   478	
   479	        return ProviderResult(hits=[
   480	            EvidenceHit(
   481	                candidate=seed,
   482	                provenance=f"source:{base_model}",
   483	                item=EvidenceItem(
   484	                    source="source_metadata",
   485	                    description=f"Civitai baseModel: {base_model}",
   486	                    confidence=0.40,
   487	                    raw_value=base_model,
   488	                ),
   489	            ),
   490	        ])
   491	
   492	
   493	class AIEvidenceProvider:
   494	    """E7: AI-assisted analysis (MCP-backed). Ceiling 0.89.
   495	
   496	    Delegates to AvatarTaskService.execute_task("dependency_resolution", ...)
   497	    which uses MCP tools (search_civitai, analyze_civitai_model,
   498	    search_huggingface, find_model_by_hash) to find matching models.
   499	
   500	    Input is formatted as structured text matching the format expected by
   501	    config/avatar/skills/model-resolution.md.
   502	    """
   503	
   504	    tier = 2  # AI can reach up to Tier 2
   505	
   506	    def __init__(self, avatar_getter: Callable, config_getter: Optional[Callable] = None):
   507	        self._get_avatar = avatar_getter
   508	        self._get_config = config_getter
   509	
   510	    def supports(self, ctx: ResolveContext) -> bool:
   511	        # Check config flag first
   512	        if self._get_config is not None:
   513	            config = self._get_config()
   514	            if not is_ai_enabled(config):
   515	                return False
   516	        return self._get_avatar() is not None
   517	
   518	    def gather(self, ctx: ResolveContext) -> ProviderResult:
   519	        """Build structured input, call AI task, convert candidates to hits."""
   520	        avatar = self._get_avatar()
   521	        if avatar is None:
   522	            return ProviderResult(error="Avatar not available")
   523	
   524	        try:
   525	            input_text = _build_ai_input(ctx)
   526	            task_result = avatar.execute_task("dependency_resolution", input_text)
   527	
   528	            if not task_result.success:
   529	                return ProviderResult(
   530	                    error=f"AI task failed: {task_result.error}",
   531	                    warnings=[f"AI analysis failed: {task_result.error}"],
   532	                )
   533	
   534	            output = task_result.output
   535	            if not isinstance(output, dict):
   536	                logger.debug("[ai_provider] Non-dict output: %s", type(output).__name__)
   537	                return ProviderResult(warnings=["AI returned non-dict output"])
   538	
   539	            candidates = output.get("candidates", [])
   540	            if not isinstance(candidates, list):
   541	                return ProviderResult(warnings=["AI returned invalid candidates"])
   542	
   543	            hits = []
   544	            for c in candidates:
   545	                hit = _ai_candidate_to_hit(c, ctx.dep_id)
   546	                if hit:
   547	                    hits.append(hit)
   548	
   549	            summary = output.get("search_summary", "")
   550	            warnings = [f"AI search: {summary}"] if summary else []
   551	
   552	            return ProviderResult(hits=hits, warnings=warnings)
   553	        except Exception as e:
   554	            logger.warning("[ai-provider] gather failed: %s", e, exc_info=True)
   555	            return ProviderResult(error=f"AI analysis failed: {e}")
   556	
   557	
   558	# --- Helpers ---
   559	
   560	def _extract_file_id(version_data: Any, sha256: str) -> Optional[int]:
   561	    """Extract file_id from Civitai version data by matching hash.
   562	
   563	    Handles both dict and dataclass (CivitaiModelVersion) inputs.
   564	    """
   565	    files = getattr(version_data, "files", None)
   566	    if files is None and isinstance(version_data, dict):
   567	        files = version_data.get("files", [])
   568	    if not files:
   569	        return None
   570	    for f in files:
   571	        if isinstance(f, dict):
   572	            hashes = f.get("hashes", {})
   573	            if hashes.get("SHA256", "").lower() == sha256.lower():
   574	                return f.get("id")
   575	    return None
   576	
   577	
   578	def _extract_first_file_id(version_data: dict) -> Optional[int]:
   579	    """Extract file_id of the primary (first) file from version data."""
   580	    files = version_data.get("files", [])
   581	    if files:
   582	        return files[0].get("id")
   583	    return None
   584	
   585	
   586	def _extract_file_id_from_version(version_obj: Any, hash_value: str) -> Optional[int]:
   587	    """Extract file_id from CivitaiModelVersion dataclass by matching hash."""
   588	    files = getattr(version_obj, "files", [])
   589	    for f in files:
   590	        if isinstance(f, dict):
   591	            hashes = f.get("hashes", {})
   592	            for h in hashes.values():
   593	                if isinstance(h, str) and h.lower() == hash_value.lower():
   594	                    return f.get("id")
   595	    # Fallback: return first file id
   596	    if files and isinstance(files[0], dict):
   597	        return files[0].get("id")
   598	    return None
   599	
   600	
   601	def _kind_matches_civitai_type(kind: AssetKind, civitai_type: str) -> bool:
   602	    """Check if an AssetKind matches a Civitai model type string."""
   603	    kind_to_types = {
   604	        AssetKind.CHECKPOINT: {"checkpoint", "model"},
   605	        AssetKind.LORA: {"lora", "locon"},
   606	        AssetKind.VAE: {"vae"},
   607	        AssetKind.CONTROLNET: {"controlnet"},
   608	        AssetKind.EMBEDDING: {"textualinversion", "embedding"},
   609	        AssetKind.UPSCALER: {"upscaler"},
   610	    }
   611	    allowed = kind_to_types.get(kind, set())
   612	    return civitai_type.lower() in allowed
   613	
   614	
   615	def _hf_hash_lookup(
   616	    pack_service: Any, sha256: str, ctx: ResolveContext
   617	) -> Optional[EvidenceHit]:
   618	    """Check if a SHA256 matches an LFS file in a known HF repo.
   619	
   620	    Only works when the dependency already has a HuggingFace selector
   621	    (from alias or previous resolve). HF has no reverse hash lookup API,
   622	    so we verify against the specific repo/file referenced in the selector.
   623	    """
   624	    dep = ctx.dependency
   625	    selector = getattr(dep, "selector", None)
   626	    if not selector:
   627	        return None
   628	
   629	    hf_sel = getattr(selector, "huggingface", None)
   630	    if not hf_sel:
   631	        return None
   632	
   633	    repo_id = getattr(hf_sel, "repo_id", None)
   634	    filename = getattr(hf_sel, "filename", None)
   635	    if not repo_id or not filename:
   636	        return None
   637	
   638	    hf_client = getattr(pack_service, "huggingface", None)
   639	    if hf_client is None:
   640	        return None
   641	
   642	    try:
   643	        repo_info = hf_client.get_repo_files(repo_id)
   644	        for file_info in repo_info.files:
   645	            if file_info.filename == filename and file_info.sha256:
   646	                if file_info.sha256.lower() == sha256.lower():
   647	                    from .models import HuggingFaceSelector
   648	                    seed = CandidateSeed(
   649	                        key=f"hf:{repo_id}:{filename}",
   650	                        selector=DependencySelector(
   651	                            strategy=SelectorStrategy.HUGGINGFACE_FILE,
   652	                            huggingface=HuggingFaceSelector(
   653	                                repo_id=repo_id,
   654	                                filename=filename,
   655	                                revision=getattr(hf_sel, "revision", None) or "main",
   656	                            ),
   657	                        ),
   658	                        display_name=f"{repo_id}/{filename}",
   659	                        provider_name="huggingface",
   660	                    )
   661	                    return EvidenceHit(
   662	                        candidate=seed,
   663	                        provenance=f"hash:{sha256[:12]}",
   664	                        item=EvidenceItem(
   665	                            source="hash_match",
   666	                            description="SHA256 match on HuggingFace LFS",
   667	                            confidence=0.95,
   668	                            raw_value=sha256,
   669	                        ),
   670	                    )
   671	    except Exception as e:
   672	        logger.debug("[hash-provider] HF LFS hash check failed: %s", e)
   673	
   674	    return None
   675	
   676	
   677	def _extract_stem(filename: str) -> Optional[str]:
   678	    """Extract model stem from filename, removing version suffixes."""
   679	    # Remove extension
   680	    name = filename
   681	    for ext in (".safetensors", ".ckpt", ".pt", ".pth", ".bin"):
   682	        if name.lower().endswith(ext):
   683	            name = name[:-len(ext)]
   684	            break
   685	
   686	    if not name:
   687	        return None
   688	
   689	    return name
   690	
   691	
   692	def _read_aliases(layout: Any) -> dict:
   693	    """Read base_model_aliases from store config (config.json)."""
   694	    load_config = getattr(layout, "load_config", None)
   695	    if load_config is None:
   696	        return {}
   697	
   698	    try:
   699	        config = load_config()
   700	        aliases = getattr(config, "base_model_aliases", {})
   701	        if not aliases:
   702	            return {}
   703	        # Convert Pydantic models to dicts for _alias_to_hit()
   704	        result = {}
   705	        for k, v in aliases.items():
   706	            result[k] = v.model_dump() if hasattr(v, "model_dump") else v
   707	        return result
   708	    except Exception as e:
   709	        logger.debug("[alias_provider] Failed to read aliases from config: %s", e)
   710	        return {}
   711	
   712	
   713	def _alias_to_hit(alias_key: str, alias_target: dict) -> Optional[EvidenceHit]:
   714	    """Convert an alias mapping to an EvidenceHit."""
   715	    # Support both flat {"civitai": ...} and nested {"selector": {"civitai": ...}}
   716	    selector = alias_target.get("selector", alias_target)
   717	    civitai = selector.get("civitai") if isinstance(selector, dict) else None
   718	    if civitai and isinstance(civitai, dict):
   719	        model_id = civitai.get("model_id")
   720	        if model_id:
   721	            seed = CandidateSeed(
   722	                key=f"alias:{alias_key}",
   723	                selector=DependencySelector(
   724	                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
   725	                    civitai=CivitaiSelector(model_id=model_id),
   726	                ),
   727	                display_name=alias_key,
   728	                provider_name="civitai",
   729	            )
   730	            return EvidenceHit(
   731	                candidate=seed,
   732	                provenance=f"alias:{alias_key}",
   733	                item=EvidenceItem(
   734	                    source="alias_config",
   735	                    description=f"Alias: {alias_key} → Civitai model {model_id}",
   736	                    confidence=0.70,
   737	                    raw_value=alias_key,
   738	                ),
   739	            )
   740	
   741	    hf = selector.get("huggingface") if isinstance(selector, dict) else None
   742	    if hf and isinstance(hf, dict):
   743	        repo_id = hf.get("repo_id")
   744	        if repo_id:
   745	            from .models import HuggingFaceSelector
   746	            seed = CandidateSeed(
   747	                key=f"alias:{alias_key}",
   748	                selector=DependencySelector(
   749	                    strategy=SelectorStrategy.HUGGINGFACE_FILE,
   750	                    huggingface=HuggingFaceSelector(
   751	                        repo_id=repo_id,
   752	                        filename=hf.get("filename", ""),
   753	                    ),
   754	                ),
   755	                display_name=alias_key,
   756	                provider_name="huggingface",
   757	            )
   758	            return EvidenceHit(
   759	                candidate=seed,
   760	                provenance=f"alias:{alias_key}",

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/evidence_providers.py | nl -ba | sed -n '760,1040p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   760	                provenance=f"alias:{alias_key}",
   761	                item=EvidenceItem(
   762	                    source="alias_config",
   763	                    description=f"Alias: {alias_key} → HF {repo_id}",
   764	                    confidence=0.70,
   765	                    raw_value=alias_key,
   766	                ),
   767	            )
   768	
   769	    return None
   770	
   771	
   772	# --- AI helpers ---
   773	
   774	def _build_ai_input(ctx: ResolveContext) -> str:
   775	    """Build structured text input for the AI dependency resolution task.
   776	
   777	    Matches the format expected by config/avatar/skills/model-resolution.md.
   778	    """
   779	    pack = ctx.pack
   780	    dep = ctx.dependency
   781	    kind = ctx.kind.value if ctx.kind else "unknown"
   782	
   783	    lines = ["PACK INFO:"]
   784	    lines.append(f"  name: {getattr(pack, 'name', 'unknown')}")
   785	    lines.append(f"  type: {getattr(pack, 'type', 'unknown')}")
   786	    lines.append(f"  base_model: {getattr(pack, 'base_model', None)}")
   787	
   788	    desc = getattr(pack, 'description', '') or ''
   789	    lines.append(f"  description: {desc[:500]}")
   790	
   791	    tags = getattr(pack, 'tags', []) or []
   792	    lines.append(f"  tags: [{', '.join(str(t) for t in tags[:20])}]")
   793	
   794	    lines.append("")
   795	    lines.append("DEPENDENCY TO RESOLVE:")
   796	    lines.append(f"  id: {ctx.dep_id}")
   797	    lines.append(f"  kind: {kind}")
   798	
   799	    # hint: base_model from selector or pack-level base_model
   800	    selector = getattr(dep, 'selector', None)
   801	    hint = None
   802	    if selector:
   803	        hint = getattr(selector, 'base_model', None)
   804	    if not hint:
   805	        hint = getattr(pack, 'base_model', None)
   806	    lines.append(f"  hint: {hint}")
   807	
   808	    expose = getattr(dep, 'expose', None)
   809	    expose_fn = getattr(expose, 'filename', None) if expose else None
   810	    lines.append(f"  expose_filename: {expose_fn}")
   811	
   812	    # Preview hints
   813	    if ctx.preview_hints:
   814	        lines.append("")
   815	        lines.append("PREVIEW HINTS:")
   816	        for hint_item in ctx.preview_hints:
   817	            src = getattr(hint_item, 'source_image', 'unknown')
   818	            fn = getattr(hint_item, 'filename', '')
   819	            raw = getattr(hint_item, 'raw_value', '')
   820	            lines.append(f"  - {src}: model=\"{fn}\", raw=\"{raw}\"")
   821	    else:
   822	        lines.append("")
   823	        lines.append("EXISTING EVIDENCE (from rule-based providers):")
   824	        lines.append("  (none)")
   825	
   826	    return "\n".join(lines)
   827	
   828	
   829	def _ai_candidate_to_hit(
   830	    candidate: dict, dep_id: str
   831	) -> Optional[EvidenceHit]:
   832	    """Convert a single AI candidate dict to an EvidenceHit.
   833	
   834	    Supports both civitai and huggingface providers.
   835	    """
   836	    if not isinstance(candidate, dict):
   837	        return None
   838	
   839	    provider = candidate.get("provider", "")
   840	    display_name = candidate.get("display_name", "AI suggestion")
   841	    confidence = candidate.get("confidence", 0.0)
   842	    reasoning = candidate.get("reasoning", "AI analysis")
   843	
   844	    if not isinstance(confidence, (int, float)):
   845	        confidence = 0.0
   846	    confidence = min(float(confidence), AI_CONFIDENCE_CEILING)
   847	
   848	    if provider == "civitai":
   849	        model_id = candidate.get("model_id")
   850	        if not model_id:
   851	            return None
   852	        version_id = candidate.get("version_id")
   853	        file_id = candidate.get("file_id")
   854	
   855	        # Use CIVITAI_FILE if we have version+file, otherwise CIVITAI_MODEL_LATEST
   856	        if version_id and file_id:
   857	            strategy = SelectorStrategy.CIVITAI_FILE
   858	        else:
   859	            strategy = SelectorStrategy.CIVITAI_MODEL_LATEST
   860	
   861	        seed = CandidateSeed(
   862	            key=f"civitai:{model_id}:{version_id or 'latest'}",
   863	            selector=DependencySelector(
   864	                strategy=strategy,
   865	                civitai=CivitaiSelector(
   866	                    model_id=model_id,
   867	                    version_id=version_id,
   868	                    file_id=file_id,
   869	                ),
   870	            ),
   871	            display_name=display_name,
   872	            provider_name="civitai",
   873	        )
   874	    elif provider == "huggingface":
   875	        from .models import HuggingFaceSelector
   876	        repo_id = candidate.get("repo_id")
   877	        filename = candidate.get("filename")
   878	        if not repo_id or not filename:
   879	            return None
   880	
   881	        seed = CandidateSeed(
   882	            key=f"hf:{repo_id}:{filename}",
   883	            selector=DependencySelector(
   884	                strategy=SelectorStrategy.HUGGINGFACE_FILE,
   885	                huggingface=HuggingFaceSelector(
   886	                    repo_id=repo_id,
   887	                    filename=filename,
   888	                    revision=candidate.get("revision", "main"),
   889	                ),
   890	            ),
   891	            display_name=display_name,
   892	            provider_name="huggingface",
   893	        )
   894	    else:
   895	        return None
   896	
   897	    return EvidenceHit(
   898	        candidate=seed,
   899	        provenance=f"ai:{dep_id}",
   900	        item=EvidenceItem(
   901	            source="ai_analysis",
   902	            description=reasoning,
   903	            confidence=confidence,
   904	            raw_value=str(candidate),
   905	        ),
   906	    )

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/enrichment.py | nl -ba | sed -n '1,420p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Enrichment utilities — shared hash/name lookup for local file imports and evidence providers.
     3	
     4	Extracted from PreviewMetaEvidenceProvider for reuse across:
     5	- LocalFileService.import_file() (primary)
     6	- PreviewMetaEvidenceProvider._resolve_hint() (refactored)
     7	- Future: batch import, auto-scan
     8	"""
     9	
    10	from __future__ import annotations
    11	
    12	import logging
    13	from dataclasses import dataclass, field
    14	from pathlib import Path
    15	from typing import Any, Optional
    16	
    17	from .models import (
    18	    AssetKind,
    19	    CanonicalSource,
    20	    CivitaiSelector,
    21	    HuggingFaceSelector,
    22	    SelectorStrategy,
    23	)
    24	
    25	logger = logging.getLogger(__name__)
    26	
    27	
    28	@dataclass
    29	class EnrichmentResult:
    30	    """What we learned about a file from remote lookups."""
    31	
    32	    source: str  # "civitai_hash", "civitai_name", "huggingface", "filename_only"
    33	    strategy: SelectorStrategy = SelectorStrategy.LOCAL_FILE
    34	    canonical_source: Optional[CanonicalSource] = None
    35	    civitai: Optional[CivitaiSelector] = None
    36	    huggingface: Optional[HuggingFaceSelector] = None
    37	    display_name: Optional[str] = None
    38	    base_model: Optional[str] = None
    39	    warnings: list[str] = field(default_factory=list)
    40	
    41	
    42	def enrich_by_hash(
    43	    sha256: str,
    44	    civitai_client: Any,
    45	    kind: Optional[AssetKind] = None,
    46	) -> Optional[EnrichmentResult]:
    47	    """Look up a SHA256 hash on Civitai. Returns enrichment or None.
    48	
    49	    Accepts both full SHA256 (64 chars) and short AutoV2 hashes (10 chars).
    50	    """
    51	    if civitai_client is None:
    52	        return None
    53	
    54	    try:
    55	        result = civitai_client.get_model_by_hash(sha256)
    56	        if not result:
    57	            return None
    58	
    59	        # CivitaiModelVersion is a dataclass — use getattr, not .get()
    60	        model_id = getattr(result, "model_id", None)
    61	        version_id = getattr(result, "id", None)
    62	        display_name = getattr(result, "name", None)
    63	        base_model = getattr(result, "base_model", None) or getattr(
    64	            result, "baseModel", None
    65	        )
    66	
    67	        if not model_id or not version_id:
    68	            return None
    69	
    70	        file_id = _extract_file_id_from_version(result, sha256)
    71	
    72	        return EnrichmentResult(
    73	            source="civitai_hash",
    74	            strategy=SelectorStrategy.CIVITAI_FILE,
    75	            canonical_source=CanonicalSource(
    76	                provider="civitai",
    77	                model_id=model_id,
    78	                version_id=version_id,
    79	            ),
    80	            civitai=CivitaiSelector(
    81	                model_id=model_id,
    82	                version_id=version_id,
    83	                file_id=file_id,
    84	            ),
    85	            display_name=display_name,
    86	            base_model=base_model,
    87	        )
    88	    except Exception as e:
    89	        logger.debug("[enrichment] Hash lookup failed for %s: %s", sha256[:16], e)
    90	        return None
    91	
    92	
    93	def enrich_by_name(
    94	    filename_stem: str,
    95	    civitai_client: Any,
    96	    kind: Optional[AssetKind] = None,
    97	) -> Optional[EnrichmentResult]:
    98	    """Search by filename stem on Civitai. Returns enrichment or None."""
    99	    if civitai_client is None or not filename_stem or len(filename_stem) < 3:
   100	        return None
   101	
   102	    try:
   103	        # Prefer Meilisearch (faster, better fuzzy matching)
   104	        search_fn = getattr(civitai_client, "search_meilisearch", None)
   105	        if search_fn is None:
   106	            search_fn = getattr(civitai_client, "search_models", None)
   107	        if search_fn is None:
   108	            return None
   109	
   110	        results = search_fn(query=filename_stem, limit=5)
   111	        items = results.get("items", []) if isinstance(results, dict) else []
   112	        if not items:
   113	            return None
   114	
   115	        stem_norm = _normalize_name(filename_stem)
   116	
   117	        for item in items:
   118	            item_name = item.get("name") or ""
   119	            item_type = (item.get("type") or "").lower()
   120	            model_id = item.get("id")
   121	
   122	            if not model_id:
   123	                continue
   124	
   125	            # Kind compatibility check
   126	            if kind and not _kind_matches_civitai_type(kind, item_type):
   127	                continue
   128	
   129	            # Name similarity check
   130	            name_norm = _normalize_name(item_name)
   131	            if stem_norm not in name_norm and name_norm not in stem_norm:
   132	                continue
   133	
   134	            # Get latest version
   135	            version_id, file_id, base_model = _get_latest_version(
   136	                civitai_client, model_id
   137	            )
   138	            if not version_id:
   139	                continue
   140	
   141	            return EnrichmentResult(
   142	                source="civitai_name",
   143	                strategy=SelectorStrategy.CIVITAI_FILE,
   144	                canonical_source=CanonicalSource(
   145	                    provider="civitai",
   146	                    model_id=model_id,
   147	                    version_id=version_id,
   148	                ),
   149	                civitai=CivitaiSelector(
   150	                    model_id=model_id,
   151	                    version_id=version_id,
   152	                    file_id=file_id,
   153	                ),
   154	                display_name=item.get("name", filename_stem),
   155	                base_model=base_model,
   156	            )
   157	
   158	    except Exception as e:
   159	        logger.debug(
   160	            "[enrichment] Name search failed for '%s': %s", filename_stem, e
   161	        )
   162	
   163	    return None
   164	
   165	
   166	def enrich_by_hf(
   167	    filename_stem: str,
   168	    hf_client: Any,
   169	    kind: Optional[AssetKind] = None,
   170	) -> Optional[EnrichmentResult]:
   171	    """Search HuggingFace Hub by filename stem. Returns enrichment or None.
   172	
   173	    Searches for model repos matching the filename, then checks for
   174	    matching safetensors/ckpt files with LFS SHA256 hashes.
   175	    """
   176	    if hf_client is None or not filename_stem or len(filename_stem) < 3:
   177	        return None
   178	
   179	    search_fn = getattr(hf_client, "search_models", None)
   180	    if search_fn is None:
   181	        return None
   182	
   183	    try:
   184	        results = search_fn(query=filename_stem, limit=5)
   185	        if not results:
   186	            return None
   187	
   188	        stem_norm = _normalize_name(filename_stem)
   189	
   190	        # Limit to top 2 repos to avoid excessive blocking network calls
   191	        for model in results[:2]:
   192	            repo_id = model.get("id", "")
   193	            if not repo_id:
   194	                continue
   195	
   196	            model_name = repo_id.split("/")[-1] if "/" in repo_id else repo_id
   197	            name_norm = _normalize_name(model_name)
   198	
   199	            if stem_norm not in name_norm and name_norm not in stem_norm:
   200	                continue
   201	
   202	            # Found a matching repo — try to get file list
   203	            get_files_fn = getattr(hf_client, "get_repo_files", None)
   204	            if get_files_fn is None:
   205	                # Return with just repo_id, no filename
   206	                return EnrichmentResult(
   207	                    source="huggingface",
   208	                    strategy=SelectorStrategy.HUGGINGFACE_FILE,
   209	                    huggingface=HuggingFaceSelector(
   210	                        repo_id=repo_id,
   211	                        filename="",
   212	                    ),
   213	                    display_name=model_name,
   214	                    base_model=_extract_hf_base_model(model),
   215	                )
   216	
   217	            try:
   218	                repo_info = get_files_fn(repo_id)
   219	                files = getattr(repo_info, "files", [])
   220	                # Find best matching safetensors file
   221	                for f in files:
   222	                    fname = getattr(f, "filename", "")
   223	                    if not fname.endswith((".safetensors", ".ckpt", ".pt")):
   224	                        continue
   225	                    return EnrichmentResult(
   226	                        source="huggingface",
   227	                        strategy=SelectorStrategy.HUGGINGFACE_FILE,
   228	                        canonical_source=CanonicalSource(
   229	                            provider="huggingface",
   230	                            sha256=getattr(f, "sha256", None),
   231	                        ),
   232	                        huggingface=HuggingFaceSelector(
   233	                            repo_id=repo_id,
   234	                            filename=fname,
   235	                        ),
   236	                        display_name=model_name,
   237	                        base_model=_extract_hf_base_model(model),
   238	                    )
   239	            except Exception:
   240	                pass
   241	
   242	    except Exception as e:
   243	        logger.debug("[enrichment] HF search failed for '%s': %s", filename_stem, e)
   244	
   245	    return None
   246	
   247	
   248	# Shared base model tag mapping — used by enrichment and MCP tools
   249	HF_BASE_MODEL_TAGS: dict[str, str] = {
   250	    "stable-diffusion-xl": "SDXL",
   251	    "sdxl": "SDXL",
   252	    "stable-diffusion": "SD 1.5",
   253	    "sd-1.5": "SD 1.5",
   254	    "flux": "Flux",
   255	    "pony": "Pony",
   256	    "sd-3.5": "SD 3.5",
   257	}
   258	
   259	
   260	def _extract_hf_base_model(model: dict) -> Optional[str]:
   261	    """Extract base model category from HF model tags."""
   262	    tags = model.get("tags", [])
   263	    for tag in tags:
   264	        tag_lower = tag.lower()
   265	        for pattern, base in HF_BASE_MODEL_TAGS.items():
   266	            if pattern in tag_lower:
   267	                return base
   268	    return None
   269	
   270	
   271	def enrich_file(
   272	    sha256: str,
   273	    filename: str,
   274	    civitai_client: Any,
   275	    kind: Optional[AssetKind] = None,
   276	    hf_client: Any = None,
   277	) -> EnrichmentResult:
   278	    """Full enrichment pipeline: hash → name(Civitai) → name(HF) → filename-only fallback.
   279	
   280	    Always returns a result — worst case is filename_only with display_name.
   281	    """
   282	    stem = extract_stem(filename)
   283	
   284	    # 1. Hash lookup on Civitai (most reliable)
   285	    result = enrich_by_hash(sha256, civitai_client, kind)
   286	    if result:
   287	        return result
   288	
   289	    # 2. Name search on Civitai (fallback)
   290	    result = enrich_by_name(stem, civitai_client, kind)
   291	    if result:
   292	        return result
   293	
   294	    # 3. Name search on HuggingFace (second fallback)
   295	    result = enrich_by_hf(stem, hf_client, kind)
   296	    if result:
   297	        return result
   298	
   299	    # 4. Filename-only fallback (always succeeds)
   300	    return EnrichmentResult(
   301	        source="filename_only",
   302	        display_name=stem or filename,
   303	    )
   304	
   305	
   306	# --- Helpers ---
   307	
   308	
   309	def extract_stem(filename: str) -> str:
   310	    """Extract clean model name from filename.
   311	
   312	    Examples:
   313	        "ponyDiffusionV6XL.safetensors" → "ponyDiffusionV6XL"
   314	        "sd_xl_turbo_1.0_fp16.safetensors" → "sd xl turbo 1.0 fp16"
   315	    """
   316	    stem = Path(filename).stem
   317	    # Normalize separators for display
   318	    return stem.replace("_", " ").replace("-", " ").strip()
   319	
   320	
   321	def _normalize_name(name: str) -> str:
   322	    """Normalize a name for comparison."""
   323	    return name.lower().replace("_", " ").replace("-", " ")
   324	
   325	
   326	def _kind_matches_civitai_type(kind: AssetKind, civitai_type: str) -> bool:
   327	    """Check if an AssetKind matches a Civitai model type string."""
   328	    kind_to_types = {
   329	        AssetKind.CHECKPOINT: {"checkpoint", "model"},
   330	        AssetKind.LORA: {"lora", "locon"},
   331	        AssetKind.VAE: {"vae"},
   332	        AssetKind.CONTROLNET: {"controlnet"},
   333	        AssetKind.EMBEDDING: {"textualinversion", "embedding"},
   334	        AssetKind.UPSCALER: {"upscaler"},
   335	    }
   336	    allowed = kind_to_types.get(kind, set())
   337	    return civitai_type.lower() in allowed
   338	
   339	
   340	def _extract_file_id_from_version(version_obj: Any, hash_value: str) -> Optional[int]:
   341	    """Extract file_id from CivitaiModelVersion dataclass by matching hash."""
   342	    files = getattr(version_obj, "files", [])
   343	    for f in files:
   344	        if isinstance(f, dict):
   345	            hashes = f.get("hashes", {})
   346	            for h in hashes.values():
   347	                if isinstance(h, str) and h.lower() == hash_value.lower():
   348	                    return f.get("id")
   349	    # Fallback: first file
   350	    if files and isinstance(files[0], dict):
   351	        return files[0].get("id")
   352	    return None
   353	
   354	
   355	def _get_latest_version(
   356	    civitai_client: Any, model_id: int
   357	) -> tuple[Optional[int], Optional[int], Optional[str]]:
   358	    """Get (version_id, file_id, base_model) from latest model version."""
   359	    try:
   360	        model_data = civitai_client.get_model(model_id)
   361	        if not model_data:
   362	            return None, None, None
   363	
   364	        versions = model_data.get("modelVersions", [])
   365	        if not versions:
   366	            return None, None, None
   367	
   368	        latest = versions[0]
   369	        version_id = latest.get("id")
   370	        base_model = latest.get("baseModel")
   371	
   372	        files = latest.get("files", [])
   373	        file_id = files[0].get("id") if files else None
   374	
   375	        return version_id, file_id, base_model
   376	    except Exception:
   377	        return None, None, None

codex
The backend is not purely stubbed: the resolver, DTOs, config, scoring, and most providers exist. The first concrete gap I see is that some providers still emit placeholder `model_id=0` candidates, which can rank as suggestions but fail validation or require enrichment before apply.
exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/local_file_service.py | nl -ba | sed -n '1,360p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Local File Service — browse, validate, and import local model files.
     3	
     4	Lets users resolve dependencies from files already on disk instead of downloading.
     5	
     6	Three scenarios:
     7	A) Dep has known remote source → recommend matching files by SHA256/filename
     8	B) Unknown file → hash → Civitai/HF lookup → enrich metadata
     9	C) No remote match → filename search → fallback to display_name from stem
    10	
    11	Security:
    12	- Path traversal prevention (no .., resolved path check)
    13	- Extension allowlist (.safetensors, .ckpt, .pt, .bin, .pth, .onnx, .sft)
    14	- Regular file check (no symlinks to sensitive locations, no devices)
    15	- fstat on opened handle for TOCTOU prevention
    16	"""
    17	
    18	from __future__ import annotations
    19	
    20	import logging
    21	import os
    22	import shutil
    23	import stat
    24	from dataclasses import dataclass, field
    25	from pathlib import Path
    26	from typing import Any, Callable, Literal, Optional
    27	
    28	from pydantic import BaseModel, Field
    29	
    30	from .blob_store import compute_sha256
    31	from .enrichment import EnrichmentResult, enrich_file, extract_stem
    32	from .hash_cache import HashCache
    33	from .models import AssetKind
    34	
    35	logger = logging.getLogger(__name__)
    36	
    37	# --- Constants ---
    38	
    39	ALLOWED_EXTENSIONS = frozenset(
    40	    {".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".onnx", ".sft", ".gguf"}
    41	)
    42	
    43	# Extension filtering by AssetKind (for smarter browsing)
    44	KIND_EXTENSIONS: dict[AssetKind, frozenset[str]] = {
    45	    AssetKind.CHECKPOINT: frozenset({".safetensors", ".ckpt", ".pt"}),
    46	    AssetKind.LORA: frozenset({".safetensors", ".pt"}),
    47	    AssetKind.VAE: frozenset({".safetensors", ".pt", ".bin"}),
    48	    AssetKind.CONTROLNET: frozenset({".safetensors", ".pt", ".bin", ".pth"}),
    49	    AssetKind.EMBEDDING: frozenset({".safetensors", ".pt", ".bin"}),
    50	    AssetKind.UPSCALER: frozenset({".safetensors", ".pt", ".bin", ".pth", ".onnx"}),
    51	    AssetKind.CLIP: frozenset({".safetensors", ".bin"}),
    52	    AssetKind.UNET: frozenset({".safetensors", ".pt", ".gguf"}),
    53	}
    54	
    55	
    56	# --- Data Models ---
    57	
    58	
    59	@dataclass
    60	class LocalFileInfo:
    61	    """A single file found during directory browsing."""
    62	
    63	    name: str  # "ponyDiffusionV6XL.safetensors"
    64	    path: str  # Absolute path
    65	    size: int  # bytes
    66	    mtime: float  # Modification time
    67	    extension: str  # ".safetensors"
    68	    cached_hash: Optional[str] = None  # SHA256 if already in hash cache
    69	
    70	
    71	@dataclass
    72	class FileRecommendation:
    73	    """A file with a match score for a specific dependency."""
    74	
    75	    file: LocalFileInfo
    76	    match_type: Literal["sha256_exact", "filename_exact", "filename_stem", "size_match", "none"]
    77	    confidence: float  # 0.0 - 1.0
    78	    reason: str  # "SHA256 matches expected hash"
    79	
    80	
    81	class BrowseResult(BaseModel):
    82	    """Result of browsing a local directory."""
    83	
    84	    directory: str
    85	    files: list[dict] = Field(default_factory=list)  # Serialized LocalFileInfo
    86	    total_count: int = 0
    87	    error: Optional[str] = None
    88	
    89	
    90	class LocalImportResult(BaseModel):
    91	    """Result of importing a local file."""
    92	
    93	    success: bool
    94	    sha256: Optional[str] = None
    95	    file_size: Optional[int] = None
    96	    display_name: Optional[str] = None
    97	    enrichment_source: Optional[str] = None  # "civitai_hash", "civitai_name", "filename_only"
    98	    canonical_source: Optional[dict] = None
    99	    message: str = ""
   100	
   101	
   102	# --- Security ---
   103	
   104	
   105	class PathValidationError(Exception):
   106	    """Raised when a path fails security validation."""
   107	
   108	    pass
   109	
   110	
   111	def validate_path(path: str) -> Path:
   112	    """Validate a local file path for security.
   113	
   114	    Returns resolved Path on success, raises PathValidationError on failure.
   115	
   116	    Checks:
   117	    1. Path is absolute
   118	    2. No '..' components
   119	    3. Resolved path matches (no symlink tricks to sensitive locations)
   120	    4. File has allowlisted extension
   121	    5. File is a regular file (not device, socket, pipe, etc.)
   122	    """
   123	    if not path:
   124	        raise PathValidationError("Empty path")
   125	
   126	    p = Path(path)
   127	
   128	    # 1. Must be absolute
   129	    if not p.is_absolute():
   130	        raise PathValidationError(f"Path must be absolute: {path}")
   131	
   132	    # 2. No '..' components
   133	    if ".." in p.parts:
   134	        raise PathValidationError(f"Path traversal not allowed: {path}")
   135	
   136	    # 3. Resolve and compare (catches symlinks that escape)
   137	    try:
   138	        resolved = p.resolve(strict=True)
   139	    except OSError as e:
   140	        raise PathValidationError(f"Cannot resolve path: {e}") from e
   141	
   142	    # 4. Extension check
   143	    ext = resolved.suffix.lower()
   144	    if ext not in ALLOWED_EXTENSIONS:
   145	        raise PathValidationError(
   146	            f"Extension '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
   147	        )
   148	
   149	    # 5. Must be a regular file (fstat on resolved path)
   150	    try:
   151	        st = resolved.stat()
   152	    except OSError as e:
   153	        raise PathValidationError(f"Cannot stat file: {e}") from e
   154	
   155	    if not stat.S_ISREG(st.st_mode):
   156	        raise PathValidationError(f"Not a regular file: {path}")
   157	
   158	    return resolved
   159	
   160	
   161	def validate_directory(path: str) -> Path:
   162	    """Validate a directory path for browsing.
   163	
   164	    Returns resolved Path on success, raises PathValidationError on failure.
   165	    """
   166	    if not path:
   167	        raise PathValidationError("Empty path")
   168	
   169	    p = Path(path)
   170	
   171	    if not p.is_absolute():
   172	        raise PathValidationError(f"Path must be absolute: {path}")
   173	
   174	    if ".." in p.parts:
   175	        raise PathValidationError(f"Path traversal not allowed: {path}")
   176	
   177	    try:
   178	        resolved = p.resolve(strict=True)
   179	    except OSError as e:
   180	        raise PathValidationError(f"Cannot resolve path: {e}") from e
   181	
   182	    if not resolved.is_dir():
   183	        raise PathValidationError(f"Not a directory: {path}")
   184	
   185	    return resolved
   186	
   187	
   188	# --- Service ---
   189	
   190	
   191	class LocalFileService:
   192	    """Service for browsing, validating, and importing local model files.
   193	
   194	    Follows Store facade pattern — injected as 10th service in Store.__init__.
   195	    """
   196	
   197	    def __init__(
   198	        self,
   199	        hash_cache: HashCache,
   200	        blob_store: Any,  # BlobStore (avoid circular import)
   201	        pack_service_getter: Optional[Callable] = None,
   202	    ):
   203	        self._hash_cache = hash_cache
   204	        self._blob_store = blob_store
   205	        self._ps = pack_service_getter
   206	
   207	    def browse(
   208	        self,
   209	        directory: str,
   210	        kind: Optional[AssetKind] = None,
   211	    ) -> BrowseResult:
   212	        """List model files in a directory, optionally filtered by kind.
   213	
   214	        Args:
   215	            directory: Absolute path to directory
   216	            kind: If provided, filter by kind-specific extensions
   217	        """
   218	        try:
   219	            dir_path = validate_directory(directory)
   220	        except PathValidationError as e:
   221	            return BrowseResult(directory=directory, error=str(e))
   222	
   223	        # Determine allowed extensions
   224	        extensions = ALLOWED_EXTENSIONS
   225	        if kind and kind in KIND_EXTENSIONS:
   226	            extensions = KIND_EXTENSIONS[kind]
   227	
   228	        files: list[LocalFileInfo] = []
   229	        try:
   230	            for entry in sorted(dir_path.iterdir(), key=lambda e: e.name.lower()):
   231	                if not entry.is_file():
   232	                    continue
   233	                ext = entry.suffix.lower()
   234	                if ext not in extensions:
   235	                    continue
   236	
   237	                try:
   238	                    st = entry.stat()
   239	                except OSError:
   240	                    continue
   241	
   242	                # Check hash cache for precomputed hash
   243	                cached_hash = self._hash_cache.get(entry)
   244	
   245	                files.append(
   246	                    LocalFileInfo(
   247	                        name=entry.name,
   248	                        path=str(entry),
   249	                        size=st.st_size,
   250	                        mtime=st.st_mtime,
   251	                        extension=ext,
   252	                        cached_hash=cached_hash,
   253	                    )
   254	                )
   255	        except PermissionError:
   256	            return BrowseResult(
   257	                directory=directory, error=f"Permission denied: {directory}"
   258	            )
   259	        except OSError as e:
   260	            return BrowseResult(directory=directory, error=str(e))
   261	
   262	        return BrowseResult(
   263	            directory=directory,
   264	            files=[_file_info_to_dict(f) for f in files],
   265	            total_count=len(files),
   266	        )
   267	
   268	    def recommend(
   269	        self,
   270	        directory: str,
   271	        dep: Any,  # PackDependency
   272	        kind: Optional[AssetKind] = None,
   273	    ) -> list[FileRecommendation]:
   274	        """Scan directory and rank files by match likelihood to a dependency.
   275	
   276	        Uses dependency's known SHA256, filename, and name to score files.
   277	        """
   278	        browse_result = self.browse(directory, kind)
   279	        if browse_result.error or not browse_result.files:
   280	            return []
   281	
   282	        # Extract dependency hints
   283	        dep_sha256 = _get_dep_sha256(dep)
   284	        dep_filename = getattr(dep, "filename", None) or getattr(dep, "name", None) or ""
   285	        dep_stem = extract_stem(dep_filename).lower() if dep_filename else ""
   286	
   287	        recommendations: list[FileRecommendation] = []
   288	
   289	        for file_dict in browse_result.files:
   290	            file_info = _dict_to_file_info(file_dict)
   291	            rec = self._score_file(file_info, dep_sha256, dep_filename, dep_stem)
   292	            recommendations.append(rec)
   293	
   294	        # Sort by confidence descending, then by name
   295	        recommendations.sort(key=lambda r: (-r.confidence, r.file.name.lower()))
   296	        return recommendations
   297	
   298	    def _score_file(
   299	        self,
   300	        file_info: LocalFileInfo,
   301	        dep_sha256: Optional[str],
   302	        dep_filename: str,
   303	        dep_stem: str,
   304	    ) -> FileRecommendation:
   305	        """Score a single file against dependency hints."""
   306	        # 1. Exact SHA256 match (if cached hash available)
   307	        if dep_sha256 and file_info.cached_hash:
   308	            if file_info.cached_hash.lower() == dep_sha256.lower():
   309	                return FileRecommendation(
   310	                    file=file_info,
   311	                    match_type="sha256_exact",
   312	                    confidence=1.0,
   313	                    reason="SHA256 hash matches expected",
   314	                )
   315	
   316	        # 2. Exact filename match
   317	        if dep_filename and file_info.name.lower() == dep_filename.lower():
   318	            return FileRecommendation(
   319	                file=file_info,
   320	                match_type="filename_exact",
   321	                confidence=0.85,
   322	                reason=f"Filename matches: {dep_filename}",
   323	            )
   324	
   325	        # 3. Stem similarity
   326	        if dep_stem:
   327	            file_stem = extract_stem(file_info.name).lower()
   328	            if dep_stem in file_stem or file_stem in dep_stem:
   329	                return FileRecommendation(
   330	                    file=file_info,
   331	                    match_type="filename_stem",
   332	                    confidence=0.6,
   333	                    reason=f"Name contains: {dep_stem}",
   334	                )
   335	
   336	        # 4. No match
   337	        return FileRecommendation(
   338	            file=file_info,
   339	            match_type="none",
   340	            confidence=0.0,
   341	            reason="",
   342	        )
   343	
   344	    def import_file(
   345	        self,
   346	        file_path: str,
   347	        pack_name: str,
   348	        dep_id: str,
   349	        *,
   350	        skip_enrichment: bool = False,
   351	        progress_callback: Optional[Callable[[str, float], None]] = None,
   352	    ) -> LocalImportResult:
   353	        """Import a local file into blob store and resolve dependency.
   354	
   355	        Steps:
   356	        1. Validate path (security)
   357	        2. Hash file (SHA256) — uses hash cache
   358	        3. Copy to blob store (or skip if blob already exists)
   359	        4. Enrich metadata (Civitai/HF lookup)
   360	        5. Apply resolution to dependency

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/local_file_service.py | nl -ba | sed -n '360,760p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   360	        5. Apply resolution to dependency
   361	
   362	        Args:
   363	            file_path: Absolute path to model file
   364	            pack_name: Target pack name
   365	            dep_id: Target dependency ID
   366	            skip_enrichment: Skip remote lookups (for testing)
   367	            progress_callback: Optional (stage, progress_0_to_1) callback
   368	        """
   369	        # 1. Validate path
   370	        try:
   371	            resolved_path = validate_path(file_path)
   372	        except PathValidationError as e:
   373	            return LocalImportResult(success=False, message=str(e))
   374	
   375	        file_size = resolved_path.stat().st_size
   376	
   377	        # 2. Hash (use cache if available)
   378	        if progress_callback:
   379	            progress_callback("hashing", 0.0)
   380	
   381	        sha256 = self._hash_cache.get(resolved_path)
   382	        if sha256 is None:
   383	            sha256 = compute_sha256(resolved_path)
   384	            self._hash_cache.compute_and_cache(resolved_path)
   385	            sha256 = self._hash_cache.get(resolved_path) or sha256
   386	
   387	        if progress_callback:
   388	            progress_callback("hashing", 1.0)
   389	
   390	        # 3. Copy to blob store (dedup: skip if exists)
   391	        if progress_callback:
   392	            progress_callback("copying", 0.0)
   393	
   394	        blob_path = self._blob_store.blob_path(sha256)
   395	        if not blob_path.exists():
   396	            blob_path.parent.mkdir(parents=True, exist_ok=True)
   397	            # Atomic write: copy to unique .tmp, then os.replace() to final location
   398	            # Prevents race condition if two imports run for the same file
   399	            import uuid as _uuid
   400	            tmp_path = blob_path.parent / f"{blob_path.name}.{_uuid.uuid4().hex[:8]}.tmp"
   401	            try:
   402	                # Try reflink first (instant, zero-copy), then hardlink, then copy
   403	                if not _try_reflink(resolved_path, tmp_path):
   404	                    if not _try_hardlink(resolved_path, tmp_path):
   405	                        shutil.copy2(resolved_path, tmp_path)
   406	                os.replace(str(tmp_path), str(blob_path))
   407	            except Exception:
   408	                tmp_path.unlink(missing_ok=True)
   409	                raise
   410	
   411	        if progress_callback:
   412	            progress_callback("copying", 1.0)
   413	
   414	        # 4. Enrich metadata
   415	        enrichment = EnrichmentResult(source="filename_only", display_name=extract_stem(resolved_path.name))
   416	        if not skip_enrichment:
   417	            if progress_callback:
   418	                progress_callback("enriching", 0.0)
   419	
   420	            civitai = self._get_civitai()
   421	            hf = self._get_hf_client()
   422	            kind = self._get_dep_kind(pack_name, dep_id)
   423	            enrichment = enrich_file(sha256, resolved_path.name, civitai, kind, hf_client=hf)
   424	
   425	            if progress_callback:
   426	                progress_callback("enriching", 1.0)
   427	
   428	        # 5. Apply resolution
   429	        if progress_callback:
   430	            progress_callback("applying", 0.0)
   431	
   432	        apply_error = self._apply_resolution(
   433	            pack_name, dep_id, sha256, file_size, resolved_path, enrichment
   434	        )
   435	
   436	        if progress_callback:
   437	            progress_callback("applying", 1.0)
   438	
   439	        # Save hash cache
   440	        self._hash_cache.save()
   441	
   442	        if apply_error:
   443	            return LocalImportResult(
   444	                success=False,
   445	                sha256=sha256,
   446	                file_size=file_size,
   447	                message=f"Import succeeded but apply failed: {apply_error}",
   448	            )
   449	
   450	        return LocalImportResult(
   451	            success=True,
   452	            sha256=sha256,
   453	            file_size=file_size,
   454	            display_name=enrichment.display_name,
   455	            enrichment_source=enrichment.source,
   456	            canonical_source=(
   457	                enrichment.canonical_source.model_dump()
   458	                if enrichment.canonical_source
   459	                else None
   460	            ),
   461	            message="File imported and dependency resolved",
   462	        )
   463	
   464	    def _get_civitai(self) -> Any:
   465	        """Get Civitai client via pack_service."""
   466	        if self._ps is None:
   467	            return None
   468	        ps = self._ps()
   469	        if ps is None:
   470	            return None
   471	        return getattr(ps, "civitai", None)
   472	
   473	    def _get_hf_client(self) -> Any:
   474	        """Get HuggingFace client via pack_service."""
   475	        if self._ps is None:
   476	            return None
   477	        ps = self._ps()
   478	        if ps is None:
   479	            return None
   480	        return getattr(ps, "hf_client", None)
   481	
   482	    def _get_dep_kind(self, pack_name: str, dep_id: str) -> Optional[AssetKind]:
   483	        """Get AssetKind for a dependency."""
   484	        if self._ps is None:
   485	            return None
   486	        ps = self._ps()
   487	        if ps is None:
   488	            return None
   489	        try:
   490	            pack = ps.get_pack(pack_name)
   491	            if pack:
   492	                for dep in pack.dependencies:
   493	                    if dep.id == dep_id:
   494	                        return getattr(dep, "kind", None)
   495	        except Exception:
   496	            pass
   497	        return None
   498	
   499	    def _apply_resolution(
   500	        self,
   501	        pack_name: str,
   502	        dep_id: str,
   503	        sha256: str,
   504	        file_size: int,
   505	        file_path: Path,
   506	        enrichment: EnrichmentResult,
   507	    ) -> Optional[str]:
   508	        """Apply the resolution to the dependency. Returns error message or None."""
   509	        if self._ps is None:
   510	            return "No pack service available"
   511	
   512	        ps = self._ps()
   513	        if ps is None:
   514	            return "Pack service not initialized"
   515	
   516	        try:
   517	            from .models import DependencySelector, SelectorStrategy
   518	            from .resolve_models import ManualResolveData
   519	
   520	            # Build selector based on enrichment
   521	            if enrichment.civitai and enrichment.strategy == SelectorStrategy.CIVITAI_FILE:
   522	                selector_data = ManualResolveData(
   523	                    strategy=SelectorStrategy.CIVITAI_FILE,
   524	                    civitai=enrichment.civitai,
   525	                    local_path=str(file_path),
   526	                    canonical_source=enrichment.canonical_source,
   527	                    display_name=enrichment.display_name,
   528	                )
   529	            elif enrichment.huggingface:
   530	                selector_data = ManualResolveData(
   531	                    strategy=SelectorStrategy.HUGGINGFACE_FILE,
   532	                    huggingface=enrichment.huggingface,
   533	                    local_path=str(file_path),
   534	                    canonical_source=enrichment.canonical_source,
   535	                    display_name=enrichment.display_name,
   536	                )
   537	            else:
   538	                selector_data = ManualResolveData(
   539	                    strategy=SelectorStrategy.LOCAL_FILE,
   540	                    local_path=str(file_path),
   541	                    display_name=enrichment.display_name,
   542	                )
   543	
   544	            # Use resolve_service.apply_manual if available
   545	            store = getattr(ps, "_store", None)
   546	            if store and hasattr(store, "resolve_service"):
   547	                result = store.resolve_service.apply_manual(
   548	                    pack_name, dep_id, selector_data
   549	                )
   550	                if not result.success:
   551	                    return result.message
   552	                return None
   553	
   554	            # Fallback: direct pack_service write
   555	            if hasattr(ps, "apply_dependency_resolution"):
   556	                selector = DependencySelector(
   557	                    strategy=selector_data.strategy,
   558	                    civitai=selector_data.civitai,
   559	                    huggingface=selector_data.huggingface,
   560	                    local_path=selector_data.local_path,
   561	                    canonical_source=selector_data.canonical_source,
   562	                )
   563	                ps.apply_dependency_resolution(
   564	                    pack_name=pack_name,
   565	                    dep_id=dep_id,
   566	                    selector=selector,
   567	                    canonical_source=selector_data.canonical_source,
   568	                    lock_entry=None,
   569	                    display_name=selector_data.display_name,
   570	                )
   571	                return None
   572	
   573	            return "No apply method available"
   574	        except Exception as e:
   575	            logger.error("[local-import] Apply failed: %s", e, exc_info=True)
   576	            return str(e)
   577	
   578	
   579	# --- File copy strategies ---
   580	
   581	
   582	def _try_reflink(src: Path, dst: Path) -> bool:
   583	    """Try copy-on-write reflink (Btrfs, XFS, APFS). Zero extra disk space."""
   584	    try:
   585	        # Linux: use ioctl FICLONE or cp --reflink=always
   586	        import subprocess
   587	
   588	        result = subprocess.run(
   589	            ["cp", "--reflink=always", str(src), str(dst)],
   590	            capture_output=True,
   591	            timeout=10,
   592	        )
   593	        return result.returncode == 0
   594	    except Exception:
   595	        return False
   596	
   597	
   598	def _try_hardlink(src: Path, dst: Path) -> bool:
   599	    """Try hardlink (same filesystem only). Zero extra disk space."""
   600	    try:
   601	        os.link(str(src), str(dst))
   602	        return True
   603	    except OSError:
   604	        return False
   605	
   606	
   607	# --- Helpers ---
   608	
   609	
   610	def _file_info_to_dict(info: LocalFileInfo) -> dict:
   611	    """Serialize LocalFileInfo to dict for API response."""
   612	    return {
   613	        "name": info.name,
   614	        "path": info.path,
   615	        "size": info.size,
   616	        "mtime": info.mtime,
   617	        "extension": info.extension,
   618	        "cached_hash": info.cached_hash,
   619	    }
   620	
   621	
   622	def _dict_to_file_info(d: dict) -> LocalFileInfo:
   623	    """Deserialize dict to LocalFileInfo."""
   624	    return LocalFileInfo(
   625	        name=d["name"],
   626	        path=d["path"],
   627	        size=d["size"],
   628	        mtime=d["mtime"],
   629	        extension=d["extension"],
   630	        cached_hash=d.get("cached_hash"),
   631	    )
   632	
   633	
   634	def _get_dep_sha256(dep: Any) -> Optional[str]:
   635	    """Extract expected SHA256 from dependency selector or lock."""
   636	    selector = getattr(dep, "selector", None)
   637	    if selector is None:
   638	        return None
   639	
   640	    # Check civitai selector
   641	    civitai = getattr(selector, "civitai", None)
   642	    if civitai:
   643	        sha = getattr(civitai, "sha256", None)
   644	        if sha:
   645	            return sha
   646	
   647	    # Check lock entry
   648	    lock = getattr(dep, "lock", None) or getattr(dep, "resolved", None)
   649	    if lock:
   650	        sha = getattr(lock, "sha256", None)
   651	        if sha:
   652	            return sha
   653	
   654	    return None

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/hash_cache.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Hash cache — persistent cache for local model file hashes.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 section G1, Phase 0 item 11.
     5	
     6	Cache structure: { path: { sha256, mtime, size, computed_at } }
     7	Persistence: data/registry/local_model_hashes.json
     8	Invalidation: mtime+size change → rehash
     9	"""
    10	
    11	from __future__ import annotations
    12	
    13	import hashlib
    14	import json
    15	import logging
    16	import time
    17	from dataclasses import asdict, dataclass
    18	from pathlib import Path
    19	from typing import Dict, Optional
    20	
    21	logger = logging.getLogger(__name__)
    22	
    23	HASH_CACHE_FILENAME = "local_model_hashes.json"
    24	CHUNK_SIZE = 1024 * 1024 * 8  # 8MB chunks for SHA256
    25	
    26	
    27	@dataclass
    28	class HashEntry:
    29	    """Cached hash entry for a local file."""
    30	    sha256: str
    31	    mtime: float
    32	    size: int
    33	    computed_at: float  # Unix timestamp
    34	
    35	
    36	class HashCache:
    37	    """Persistent hash cache for local model files.
    38	
    39	    Stores SHA256 hashes keyed by file path. Invalidates when
    40	    mtime or size changes. Full background scan is Phase 3;
    41	    this module provides the cache + sync hash computation.
    42	    """
    43	
    44	    def __init__(self, registry_path: Path):
    45	        """Initialize with path to the registry directory.
    46	
    47	        Cache file will be stored at registry_path / local_model_hashes.json.
    48	        """
    49	        self._cache_file = registry_path / HASH_CACHE_FILENAME
    50	        self._entries: Dict[str, HashEntry] = {}
    51	        self._dirty = False
    52	        self._load()
    53	
    54	    def _load(self) -> None:
    55	        """Load cache from disk."""
    56	        if not self._cache_file.exists():
    57	            return
    58	
    59	        try:
    60	            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
    61	            for path_str, entry_data in data.items():
    62	                self._entries[path_str] = HashEntry(**entry_data)
    63	        except (json.JSONDecodeError, OSError, TypeError) as e:
    64	            logger.warning("Failed to load hash cache from %s: %s", self._cache_file, e)
    65	            self._entries = {}
    66	
    67	    def save(self) -> None:
    68	        """Persist cache to disk (only if dirty). Uses atomic write (temp + rename)."""
    69	        if not self._dirty:
    70	            return
    71	
    72	        try:
    73	            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
    74	            data = {path: asdict(entry) for path, entry in self._entries.items()}
    75	            content = json.dumps(data, indent=2)
    76	            # Atomic write: write to temp file, then rename
    77	            tmp_file = self._cache_file.with_suffix(".tmp")
    78	            tmp_file.write_text(content, encoding="utf-8")
    79	            tmp_file.replace(self._cache_file)
    80	            self._dirty = False
    81	        except OSError as e:
    82	            logger.warning("Failed to save hash cache to %s: %s", self._cache_file, e)
    83	
    84	    def get(self, file_path: Path) -> Optional[str]:
    85	        """Get cached SHA256 for a file, or None if stale/missing.
    86	
    87	        Returns the hash only if the file's mtime and size match the cache.
    88	        """
    89	        key = str(file_path)
    90	        entry = self._entries.get(key)
    91	        if entry is None:
    92	            return None
    93	
    94	        try:
    95	            stat = file_path.stat()
    96	        except OSError:
    97	            return None
    98	
    99	        if stat.st_mtime != entry.mtime or stat.st_size != entry.size:
   100	            return None
   101	
   102	        return entry.sha256
   103	
   104	    def compute_and_cache(self, file_path: Path) -> str:
   105	        """Compute SHA256 for a file and store in cache.
   106	
   107	        This is a synchronous operation. For async, use compute_hash_async().
   108	        """
   109	        sha256 = compute_sha256(file_path)
   110	        stat = file_path.stat()
   111	
   112	        self._entries[str(file_path)] = HashEntry(
   113	            sha256=sha256,
   114	            mtime=stat.st_mtime,
   115	            size=stat.st_size,
   116	            computed_at=time.time(),
   117	        )
   118	        self._dirty = True
   119	
   120	        return sha256
   121	
   122	    def get_or_compute(self, file_path: Path) -> str:
   123	        """Get cached hash or compute and cache it."""
   124	        cached = self.get(file_path)
   125	        if cached is not None:
   126	            return cached
   127	        return self.compute_and_cache(file_path)
   128	
   129	    def invalidate(self, file_path: Path) -> None:
   130	        """Remove a file from the cache."""
   131	        key = str(file_path)
   132	        if key in self._entries:
   133	            del self._entries[key]
   134	            self._dirty = True
   135	
   136	    def clear(self) -> None:
   137	        """Clear all entries."""
   138	        self._entries.clear()
   139	        self._dirty = True
   140	
   141	    @property
   142	    def size(self) -> int:
   143	        """Number of cached entries."""
   144	        return len(self._entries)
   145	
   146	
   147	def compute_sha256(file_path: Path) -> str:
   148	    """Compute SHA256 hash of a file."""
   149	    h = hashlib.sha256()
   150	    with open(file_path, "rb") as f:
   151	        while True:
   152	            chunk = f.read(CHUNK_SIZE)
   153	            if not chunk:
   154	                break
   155	            h.update(chunk)
   156	    return h.hexdigest()
   157	
   158	
   159	async def compute_sha256_async(file_path: Path) -> str:
   160	    """Compute SHA256 hash of a file without blocking the event loop.
   161	
   162	    Offloads the I/O-heavy computation to a thread pool via asyncio.to_thread().
   163	    Use this in FastAPI endpoints for large files (7GB+ checkpoints).
   164	    """
   165	    import asyncio
   166	    return await asyncio.to_thread(compute_sha256, file_path)

exec
/bin/bash -lc "git grep -n \"suggest-resolution\\|apply-resolution\\|local\" feat/resolve-model-redesign -- src/store/api.py | sed -n '1,200p'" in /home/box/git/github/synapse
 succeeded in 0ms:
feat/resolve-model-redesign:src/store/api.py:495:    target: str = "local"  # "local", "backup", or "both"
feat/resolve-model-redesign:src/store/api.py:707:    target: str = Query("local", description="Delete from: local, backup, both"),
feat/resolve-model-redesign:src/store/api.py:869:                nonlocal last_update_time, last_downloaded
feat/resolve-model-redesign:src/store/api.py:980:    Backup a blob from local to backup storage.
feat/resolve-model-redesign:src/store/api.py:1009:    Restore a blob from backup to local storage.
feat/resolve-model-redesign:src/store/api.py:1011:    Copies the blob from backup storage to local.
feat/resolve-model-redesign:src/store/api.py:1013:    404 if not found on backup, 507 if insufficient local space.
feat/resolve-model-redesign:src/store/api.py:1041:    The blob remains on local storage if it exists there.
feat/resolve-model-redesign:src/store/api.py:1065:    Sync blobs between local and backup storage.
feat/resolve-model-redesign:src/store/api.py:1102:    target: str = Query("local", description="Target: local, backup, or both"),
feat/resolve-model-redesign:src/store/api.py:1143:    Pull (restore) all blobs for a pack from backup to local.
feat/resolve-model-redesign:src/store/api.py:1146:    Use case: Need pack models locally but want to stay on global profile.
feat/resolve-model-redesign:src/store/api.py:1190:    Push (backup) all blobs for a pack from local to backup.
feat/resolve-model-redesign:src/store/api.py:1192:    Optionally removes local copies after successful backup.
feat/resolve-model-redesign:src/store/api.py:1242:    Returns location (local_only, backup_only, both, nowhere) for each blob.
feat/resolve-model-redesign:src/store/api.py:1264:                    "local_only": 0,
feat/resolve-model-redesign:src/store/api.py:1276:            "local_only": 0,
feat/resolve-model-redesign:src/store/api.py:1291:            on_local = store.blob_store.blob_exists(sha256)
feat/resolve-model-redesign:src/store/api.py:1294:            if on_local and on_backup:
feat/resolve-model-redesign:src/store/api.py:1297:            elif on_local:
feat/resolve-model-redesign:src/store/api.py:1298:                location = "local_only"
feat/resolve-model-redesign:src/store/api.py:1299:                summary["local_only"] += 1
feat/resolve-model-redesign:src/store/api.py:1317:                "on_local": on_local,
feat/resolve-model-redesign:src/store/api.py:1361:                "local_only": result.summary.local_only,
feat/resolve-model-redesign:src/store/api.py:1371:                    "local_mtime": item.local_mtime,
feat/resolve-model-redesign:src/store/api.py:1373:                    "local_size": item.local_size,
feat/resolve-model-redesign:src/store/api.py:1387:                "local_only": 0,
feat/resolve-model-redesign:src/store/api.py:1403:                "local_only": 0,
feat/resolve-model-redesign:src/store/api.py:1439:                "local_only": result.summary.local_only,
feat/resolve-model-redesign:src/store/api.py:1450:                    "local_mtime": item.local_mtime,
feat/resolve-model-redesign:src/store/api.py:1452:                    "local_size": item.local_size,
feat/resolve-model-redesign:src/store/api.py:1520:                        local_path = previews_dir / preview.filename
feat/resolve-model-redesign:src/store/api.py:1521:                        if local_path.exists():
feat/resolve-model-redesign:src/store/api.py:1526:            # 2. Fallback to first preview from pack.previews with existing local file
feat/resolve-model-redesign:src/store/api.py:1530:                        local_path = previews_dir / preview.filename
feat/resolve-model-redesign:src/store/api.py:1531:                        if local_path.exists():
feat/resolve-model-redesign:src/store/api.py:1615:            source = "local"
feat/resolve-model-redesign:src/store/api.py:1679:                        asset_info["local_path"] = str(store.blob_store.blob_path(resolved.artifact.sha256))
feat/resolve-model-redesign:src/store/api.py:1708:                # For videos, use the local .mp4 URL as thumbnail.
feat/resolve-model-redesign:src/store/api.py:1709:                # MediaPreview.tsx detects local video URLs and uses forceVideoDisplay
feat/resolve-model-redesign:src/store/api.py:1786:                "local_path": None,
feat/resolve-model-redesign:src/store/api.py:1796:                workflow_info["local_path"] = str(f)
feat/resolve-model-redesign:src/store/api.py:1821:                "local_path": str(f),
feat/resolve-model-redesign:src/store/api.py:2170:    """Import a local model file into ComfyUI models directory.
feat/resolve-model-redesign:src/store/api.py:2270:    local_path: Optional[str] = None
feat/resolve-model-redesign:src/store/api.py:2302:@v2_packs_router.post("/{pack_name}/suggest-resolution")
feat/resolve-model-redesign:src/store/api.py:2338:        logger.error(f"[suggest-resolution] Error: {e}")
feat/resolve-model-redesign:src/store/api.py:2342:@v2_packs_router.post("/{pack_name}/apply-resolution")
feat/resolve-model-redesign:src/store/api.py:2366:        logger.error(f"[apply-resolution] Error: {e}")
feat/resolve-model-redesign:src/store/api.py:2397:            if not request.local_path:
feat/resolve-model-redesign:src/store/api.py:2400:                    detail="Local file strategy requires local_path",
feat/resolve-model-redesign:src/store/api.py:2428:            local_path=request.local_path,
feat/resolve-model-redesign:src/store/api.py:2479:    """Request to import a local file as a resolved dependency."""
feat/resolve-model-redesign:src/store/api.py:2485:@store_router.get("/browse-local")
feat/resolve-model-redesign:src/store/api.py:2486:def browse_local_directory(
feat/resolve-model-redesign:src/store/api.py:2491:    """List model files in a local directory."""
feat/resolve-model-redesign:src/store/api.py:2499:    return store.local_file_service.browse(path, kind_enum).model_dump()
feat/resolve-model-redesign:src/store/api.py:2502:@v2_packs_router.get("/{pack_name}/recommend-local")
feat/resolve-model-redesign:src/store/api.py:2503:def recommend_local_files(
feat/resolve-model-redesign:src/store/api.py:2524:    recommendations = store.local_file_service.recommend(directory, dep, kind)
feat/resolve-model-redesign:src/store/api.py:2546:@v2_packs_router.post("/{pack_name}/import-local")
feat/resolve-model-redesign:src/store/api.py:2547:async def import_local_file(
feat/resolve-model-redesign:src/store/api.py:2553:    """Import a local file into blob store and resolve dependency.
feat/resolve-model-redesign:src/store/api.py:2566:    from .local_file_service import validate_path, PathValidationError
feat/resolve-model-redesign:src/store/api.py:2596:            result = store.local_file_service.import_file(
feat/resolve-model-redesign:src/store/api.py:2609:            logger.error("[import-local] Error: %s", e, exc_info=True)
feat/resolve-model-redesign:src/store/api.py:2788:                nonlocal last_update_time, last_downloaded
feat/resolve-model-redesign:src/store/api.py:3154:                # Check if all blobs exist locally
feat/resolve-model-redesign:src/store/api.py:4184:        # Delete the file if it exists locally
feat/resolve-model-redesign:src/store/api.py:4226:                    "local_path": str(f),

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/avatar/tasks/dependency_resolution.py | nl -ba | sed -n '1,280p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Dependency Resolution Task
     3	
     4	AI-powered dependency resolution for model packs. Uses MCP tools
     5	(search_civitai, analyze_civitai_model, search_huggingface, find_model_by_hash)
     6	to find matching models for unresolved dependencies.
     7	
     8	The entire prompt lives in config/avatar/skills/model-resolution.md.
     9	This module only handles: input formatting, output parsing, and validation.
    10	"""
    11	
    12	import logging
    13	from typing import Any, Dict, List, Optional
    14	
    15	from .base import AITask
    16	
    17	# Re-export for backward compatibility (tests import from here)
    18	from src.store.resolve_config import AI_CONFIDENCE_CEILING  # noqa: F401
    19	
    20	logger = logging.getLogger(__name__)
    21	
    22	# Required fields per provider type
    23	_CIVITAI_REQUIRED = {"display_name", "provider", "model_id", "confidence", "reasoning"}
    24	_HF_REQUIRED = {"display_name", "provider", "repo_id", "filename", "confidence", "reasoning"}
    25	_COMMON_REQUIRED = {"display_name", "provider", "confidence", "reasoning"}
    26	
    27	
    28	class DependencyResolutionTask(AITask):
    29	    """AI task for resolving model pack dependencies via MCP tool search.
    30	
    31	    Flow:
    32	    1. Caller formats pack metadata + dependency info into structured text
    33	    2. Skills content (model-resolution.md + reference docs) = full system prompt
    34	    3. AvatarEngine calls MCP tools (search, analyze) and returns JSON candidates
    35	    4. parse_result() normalizes candidates and enforces confidence ceiling
    36	    5. validate_output() ensures structural validity
    37	
    38	    The prompt is NOT hardcoded here — it lives in config/avatar/skills/model-resolution.md
    39	    so it can be edited without code changes.
    40	    """
    41	
    42	    task_type = "dependency_resolution"
    43	    SKILL_NAMES = (
    44	        "model-resolution",
    45	        "dependency-resolution",
    46	        "model-types",
    47	        "civitai-integration",
    48	        "huggingface-integration",
    49	    )
    50	    needs_mcp = True
    51	    timeout_s = 180
    52	
    53	    def build_system_prompt(self, skills_content: str) -> str:
    54	        """Return skills content as the complete system prompt.
    55	
    56	        Unlike other tasks, the entire prompt is in the skill files.
    57	        model-resolution.md contains the task instructions, output format,
    58	        confidence rules, and few-shot examples. The other 4 skill files
    59	        provide reference knowledge (API docs, model types, etc.).
    60	        """
    61	        return skills_content
    62	
    63	    def parse_result(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
    64	        """Parse AI output into normalized candidate list.
    65	
    66	        Handles:
    67	        - Extracts candidates list from output
    68	        - Enforces AI_CONFIDENCE_CEILING on each candidate
    69	        - Validates per-provider required fields
    70	        - Sorts by confidence descending
    71	        - Preserves search_summary for diagnostics
    72	
    73	        Returns:
    74	            Dict with "candidates" (list) and "search_summary" (str).
    75	        """
    76	        if not isinstance(raw_output, dict):
    77	            return {"candidates": [], "search_summary": "Invalid AI output format"}
    78	
    79	        candidates_raw = raw_output.get("candidates", [])
    80	        if not isinstance(candidates_raw, list):
    81	            return {"candidates": [], "search_summary": "Missing candidates list"}
    82	
    83	        parsed_candidates: List[Dict[str, Any]] = []
    84	
    85	        for candidate in candidates_raw:
    86	            if not isinstance(candidate, dict):
    87	                continue
    88	
    89	            # Enforce confidence ceiling
    90	            confidence = candidate.get("confidence", 0.0)
    91	            if not isinstance(confidence, (int, float)):
    92	                confidence = 0.0
    93	            candidate["confidence"] = min(float(confidence), AI_CONFIDENCE_CEILING)
    94	
    95	            # Validate required fields based on provider
    96	            provider = candidate.get("provider", "")
    97	            if provider == "civitai":
    98	                if not _CIVITAI_REQUIRED.issubset(candidate.keys()):
    99	                    missing = _CIVITAI_REQUIRED - candidate.keys()
   100	                    logger.warning(
   101	                        "[dep-resolution] Civitai candidate missing fields: %s",
   102	                        missing,
   103	                    )
   104	                    continue
   105	            elif provider == "huggingface":
   106	                if not _HF_REQUIRED.issubset(candidate.keys()):
   107	                    missing = _HF_REQUIRED - candidate.keys()
   108	                    logger.warning(
   109	                        "[dep-resolution] HuggingFace candidate missing fields: %s",
   110	                        missing,
   111	                    )
   112	                    continue
   113	            else:
   114	                if not _COMMON_REQUIRED.issubset(candidate.keys()):
   115	                    continue
   116	
   117	            parsed_candidates.append(candidate)
   118	
   119	        # Sort by confidence descending
   120	        parsed_candidates.sort(key=lambda c: c["confidence"], reverse=True)
   121	
   122	        return {
   123	            "candidates": parsed_candidates,
   124	            "search_summary": raw_output.get("search_summary", ""),
   125	        }
   126	
   127	    def validate_output(self, output: Any) -> bool:
   128	        """Validate parsed output structure.
   129	
   130	        Accepts:
   131	        - Empty candidates list (valid "no match" result)
   132	        - Non-empty candidates with valid confidence bounds
   133	
   134	        Rejects:
   135	        - Non-dict output
   136	        - Missing "candidates" key
   137	        - Candidates with confidence > AI_CONFIDENCE_CEILING
   138	        """
   139	        if not isinstance(output, dict):
   140	            return False
   141	
   142	        candidates = output.get("candidates")
   143	        if not isinstance(candidates, list):
   144	            return False
   145	
   146	        # Empty candidates is a valid "no match" result
   147	        if not candidates:
   148	            return True
   149	
   150	        # Validate each candidate
   151	        for c in candidates:
   152	            if not isinstance(c, dict):
   153	                return False
   154	            conf = c.get("confidence", -1)
   155	            if not isinstance(conf, (int, float)):
   156	                return False
   157	            if conf < 0 or conf > AI_CONFIDENCE_CEILING:
   158	                return False
   159	            if not c.get("display_name"):
   160	                return False
   161	
   162	        return True
   163	
   164	    def get_fallback(self) -> None:
   165	        """No fallback — E1-E6 evidence providers run independently of AI."""
   166	        return None

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/avatar/task_service.py | nl -ba | sed -n '280,380p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   280	        """Add _extracted_by and _ai_fields tracking metadata to output.
   281	
   282	        Works on dict outputs only. Returns the enriched copy.
   283	        """
   284	        if not isinstance(output, dict):
   285	            return output
   286	        enriched = dict(output)
   287	        enriched["_extracted_by"] = provider_id
   288	        enriched["_ai_fields"] = [
   289	            k for k in enriched.keys() if not k.startswith("_")
   290	        ]
   291	        return enriched
   292	
   293	    def _ensure_engine_for_task(self, task: AITask):
   294	        """Get or restart engine for task. MUST be called under _engine_lock."""
   295	        if self._engine and self._current_task_type == task.task_type:
   296	            return self._engine
   297	
   298	        # Clean stop before restart
   299	        if self._engine:
   300	            try:
   301	                self._engine.stop_sync()
   302	            except Exception as e:
   303	                logger.warning("[task-service] Engine stop failed: %s", e)
   304	            self._engine = None
   305	            self._current_task_type = None
   306	
   307	        # Load skills + create engine
   308	        skills_content = self._load_skills(task.SKILL_NAMES)
   309	        system_prompt = task.build_system_prompt(skills_content)
   310	
   311	        try:
   312	            from avatar_engine import AvatarEngine
   313	        except ImportError:
   314	            raise ImportError(
   315	                "avatar-engine is not installed. "
   316	                "See docs/avatar/getting-started.md for installation instructions."
   317	            )
   318	
   319	        engine_kwargs: dict = {
   320	            "provider": self._provider,
   321	            "model": self._model or None,
   322	            "system_prompt": system_prompt,
   323	            "timeout": task.timeout_s,
   324	            "safety_instructions": "unrestricted",
   325	        }
   326	
   327	        # Pass provider-specific config (permission_mode, allowed_tools, etc.)
   328	        # AvatarEngine reads these from kwargs when config object is not passed.
   329	        raw_provider_cfg = self.config._raw.get(self._provider, {})
   330	        if isinstance(raw_provider_cfg, dict):
   331	            for key in ("permission_mode", "allowed_tools", "additional_dirs",
   332	                        "approval_mode", "strict_mcp_config"):
   333	                if key in raw_provider_cfg:
   334	                    engine_kwargs[key] = raw_provider_cfg[key]
   335	
   336	        # MCP-enabled tasks get access to MCP servers (e.g., search tools)
   337	        if task.needs_mcp and self.config.mcp_servers:
   338	            engine_kwargs["mcp_servers"] = self.config.mcp_servers
   339	
   340	        engine = AvatarEngine(**engine_kwargs)
   341	        engine.start_sync()
   342	        self._engine = engine
   343	        self._current_task_type = task.task_type
   344	
   345	        logger.info(
   346	            "[task-service] Engine started for %s: provider=%s, model=%s",
   347	            task.task_type,
   348	            self._provider,
   349	            self._model or "default",
   350	        )
   351	
   352	        return self._engine
   353	
   354	    def _load_skills(self, skill_names: tuple) -> str:
   355	        """Load skill markdown files by name. Graceful on missing files."""
   356	        if not self.config.skills_dir:
   357	            return ""
   358	
   359	        from .skills import load_skill
   360	
   361	        parts = []
   362	        for name in skill_names:
   363	            path = self.config.skills_dir / f"{name}.md"
   364	            if path.exists():
   365	                content = load_skill(path)
   366	                if content.strip():
   367	                    parts.append(content)
   368	            else:
   369	                logger.warning("[task-service] Skill file not found: %s", path)
   370	        return "\n\n---\n\n".join(parts)
   371	
   372	    # -- Convenience wrappers --
   373	
   374	    def extract_parameters(
   375	        self,
   376	        description: str,
   377	        use_cache: bool = True,
   378	    ) -> TaskResult:
   379	        """Extract generation parameters from description.
   380	

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/api.py | nl -ba | sed -n '2240,2438p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  2240	
  2241	
  2242	# =============================================================================
  2243	# Resolve Endpoints — suggest/apply dependency resolution (Phase 1)
  2244	# =============================================================================
  2245	
  2246	
  2247	class SuggestRequest(BaseModel):
  2248	    """Request for resolution suggestions."""
  2249	    dep_id: str
  2250	    include_ai: bool = False
  2251	    max_candidates: int = 10
  2252	
  2253	
  2254	class ApplyRequest(BaseModel):
  2255	    """Request to apply a resolution candidate."""
  2256	    dep_id: str
  2257	    candidate_id: str
  2258	    request_id: Optional[str] = None
  2259	
  2260	
  2261	class ManualApplyRequest(BaseModel):
  2262	    """Request to apply a manual resolution."""
  2263	    dep_id: str
  2264	    strategy: str
  2265	    civitai_model_id: Optional[int] = None
  2266	    civitai_version_id: Optional[int] = None
  2267	    civitai_file_id: Optional[int] = None
  2268	    hf_repo_id: Optional[str] = None
  2269	    hf_filename: Optional[str] = None
  2270	    local_path: Optional[str] = None
  2271	    url: Optional[str] = None
  2272	    display_name: Optional[str] = None
  2273	
  2274	
  2275	@v2_packs_router.get("/{pack_name}/preview-analysis")
  2276	def get_preview_analysis(
  2277	    pack_name: str,
  2278	    store=Depends(require_initialized),
  2279	):
  2280	    """Extract model hints and generation params from pack preview images."""
  2281	    try:
  2282	        pack = store.get_pack(pack_name)
  2283	        if not pack:
  2284	            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
  2285	
  2286	        from src.utils.preview_meta_extractor import analyze_pack_previews
  2287	        previews_path = store.layout.pack_previews_path(pack_name)
  2288	        results = analyze_pack_previews(previews_path, pack.previews or [])
  2289	
  2290	        return {
  2291	            "pack_name": pack_name,
  2292	            "previews": [r.model_dump() for r in results],
  2293	            "total_hints": sum(len(r.hints) for r in results),
  2294	        }
  2295	    except HTTPException:
  2296	        raise
  2297	    except Exception as e:
  2298	        logger.error(f"[preview-analysis] Error: {e}")
  2299	        raise HTTPException(status_code=400, detail=str(e))
  2300	
  2301	
  2302	@v2_packs_router.post("/{pack_name}/suggest-resolution")
  2303	def suggest_resolution(
  2304	    pack_name: str,
  2305	    request: SuggestRequest,
  2306	    store=Depends(require_initialized),
  2307	):
  2308	    """Suggest resolution candidates for a dependency."""
  2309	    try:
  2310	        pack = store.get_pack(pack_name)
  2311	        if not pack:
  2312	            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
  2313	
  2314	        # Validate dep_id exists in pack
  2315	        dep_ids = [d.id for d in (pack.dependencies or [])]
  2316	        if request.dep_id not in dep_ids:
  2317	            raise HTTPException(
  2318	                status_code=404,
  2319	                detail=f"Dependency '{request.dep_id}' not found in pack '{pack_name}'",
  2320	            )
  2321	
  2322	        from .resolve_models import SuggestOptions
  2323	        options = SuggestOptions(
  2324	            include_ai=request.include_ai,
  2325	            max_candidates=min(request.max_candidates or 20, 50),
  2326	        )
  2327	        result = store.resolve_service.suggest(pack, request.dep_id, options)
  2328	        return {
  2329	            "request_id": result.request_id,
  2330	            "candidates": [c.model_dump() for c in result.candidates],
  2331	            "pack_fingerprint": result.pack_fingerprint,
  2332	            "warnings": result.warnings,
  2333	            "preview_hints": [h.model_dump() for h in result.preview_hints],
  2334	        }
  2335	    except HTTPException:
  2336	        raise
  2337	    except Exception as e:
  2338	        logger.error(f"[suggest-resolution] Error: {e}")
  2339	        raise HTTPException(status_code=400, detail=str(e))
  2340	
  2341	
  2342	@v2_packs_router.post("/{pack_name}/apply-resolution")
  2343	def apply_resolution(
  2344	    pack_name: str,
  2345	    request: ApplyRequest,
  2346	    store=Depends(require_initialized),
  2347	):
  2348	    """Apply a previously suggested resolution candidate."""
  2349	    try:
  2350	        pack = store.get_pack(pack_name)
  2351	        if not pack:
  2352	            raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
  2353	
  2354	        result = store.resolve_service.apply(
  2355	            pack_name=pack_name,
  2356	            dep_id=request.dep_id,
  2357	            candidate_id=request.candidate_id,
  2358	            request_id=request.request_id,
  2359	        )
  2360	        if not result.success:
  2361	            raise HTTPException(status_code=400, detail=result.message)
  2362	        return result.model_dump()
  2363	    except HTTPException:
  2364	        raise
  2365	    except Exception as e:
  2366	        logger.error(f"[apply-resolution] Error: {e}")
  2367	        raise HTTPException(status_code=400, detail=str(e))
  2368	
  2369	
  2370	@v2_packs_router.post("/{pack_name}/apply-manual-resolution")
  2371	def apply_manual_resolution(
  2372	    pack_name: str,
  2373	    request: ManualApplyRequest,
  2374	    store=Depends(require_initialized),
  2375	):
  2376	    """Apply a manual resolution (from Civitai/HF/Local tab)."""
  2377	    try:
  2378	        from .models import CivitaiSelector, HuggingFaceSelector, SelectorStrategy
  2379	        from .resolve_models import ManualResolveData
  2380	
  2381	        strategy = SelectorStrategy(request.strategy)
  2382	
  2383	        # Validate strategy-specific required fields at API boundary
  2384	        if strategy == SelectorStrategy.CIVITAI_FILE:
  2385	            if not request.civitai_model_id or not request.civitai_version_id:
  2386	                raise HTTPException(
  2387	                    status_code=422,
  2388	                    detail="Civitai strategy requires civitai_model_id and civitai_version_id",
  2389	                )
  2390	        elif strategy == SelectorStrategy.HUGGINGFACE_FILE:
  2391	            if not request.hf_repo_id or not request.hf_filename:
  2392	                raise HTTPException(
  2393	                    status_code=422,
  2394	                    detail="HuggingFace strategy requires hf_repo_id and hf_filename",
  2395	                )
  2396	        elif strategy == SelectorStrategy.LOCAL_FILE:
  2397	            if not request.local_path:
  2398	                raise HTTPException(
  2399	                    status_code=422,
  2400	                    detail="Local file strategy requires local_path",
  2401	                )
  2402	        elif strategy == SelectorStrategy.URL_DOWNLOAD:
  2403	            if not request.url:
  2404	                raise HTTPException(
  2405	                    status_code=422,
  2406	                    detail="URL download strategy requires url",
  2407	                )
  2408	
  2409	        civitai = None
  2410	        if request.civitai_model_id:
  2411	            civitai = CivitaiSelector(
  2412	                model_id=request.civitai_model_id,
  2413	                version_id=request.civitai_version_id or 0,
  2414	                file_id=request.civitai_file_id,
  2415	            )
  2416	
  2417	        huggingface = None
  2418	        if request.hf_repo_id:
  2419	            huggingface = HuggingFaceSelector(
  2420	                repo_id=request.hf_repo_id,
  2421	                filename=request.hf_filename or "",
  2422	            )
  2423	
  2424	        manual = ManualResolveData(
  2425	            strategy=strategy,
  2426	            civitai=civitai,
  2427	            huggingface=huggingface,
  2428	            local_path=request.local_path,
  2429	            url=request.url,
  2430	            display_name=request.display_name,
  2431	        )
  2432	
  2433	        result = store.resolve_service.apply_manual(pack_name, request.dep_id, manual)
  2434	        if not result.success:
  2435	            raise HTTPException(status_code=400, detail=result.message)
  2436	        return result.model_dump()
  2437	    except HTTPException:
  2438	        raise

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/api.py | nl -ba | sed -n '2438,2625p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  2438	        raise
  2439	    except Exception as e:
  2440	        logger.error(f"[apply-manual-resolution] Error: {e}")
  2441	        raise HTTPException(status_code=400, detail=str(e))
  2442	
  2443	
  2444	# =============================================================================
  2445	# Local File Import Endpoints
  2446	# =============================================================================
  2447	
  2448	_active_imports: Dict[str, dict] = {}
  2449	_import_executor = None  # Lazy-init ThreadPoolExecutor
  2450	
  2451	MAX_CONCURRENT_IMPORTS = 2
  2452	MAX_IMPORT_HISTORY = 50
  2453	
  2454	
  2455	def _get_import_executor():
  2456	    """Get or create import thread pool (max 2 concurrent imports)."""
  2457	    global _import_executor
  2458	    if _import_executor is None:
  2459	        from concurrent.futures import ThreadPoolExecutor
  2460	        _import_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_IMPORTS, thread_name_prefix="import")
  2461	    return _import_executor
  2462	
  2463	
  2464	def _cleanup_old_imports():
  2465	    """Remove old completed/failed imports to prevent memory leak."""
  2466	    if len(_active_imports) <= MAX_IMPORT_HISTORY:
  2467	        return
  2468	    completed = [
  2469	        (k, v) for k, v in _active_imports.items()
  2470	        if v.get("status") in ("completed", "failed")
  2471	    ]
  2472	    completed.sort(key=lambda x: x[1].get("_finished_at", 0))
  2473	    to_remove = len(_active_imports) - MAX_IMPORT_HISTORY
  2474	    for k, _ in completed[:to_remove]:
  2475	        del _active_imports[k]
  2476	
  2477	
  2478	class ImportLocalRequest(BaseModel):
  2479	    """Request to import a local file as a resolved dependency."""
  2480	    dep_id: str
  2481	    file_path: str
  2482	    skip_enrichment: bool = False
  2483	
  2484	
  2485	@store_router.get("/browse-local")
  2486	def browse_local_directory(
  2487	    path: str = Query(..., description="Directory path to browse"),
  2488	    kind: Optional[str] = Query(None, description="Filter by AssetKind"),
  2489	    store=Depends(require_initialized),
  2490	):
  2491	    """List model files in a local directory."""
  2492	    from .models import AssetKind as AK
  2493	    kind_enum = None
  2494	    if kind:
  2495	        try:
  2496	            kind_enum = AK(kind)
  2497	        except ValueError:
  2498	            pass
  2499	    return store.local_file_service.browse(path, kind_enum).model_dump()
  2500	
  2501	
  2502	@v2_packs_router.get("/{pack_name}/recommend-local")
  2503	def recommend_local_files(
  2504	    pack_name: str,
  2505	    dep_id: str = Query(...),
  2506	    directory: str = Query(...),
  2507	    store=Depends(require_initialized),
  2508	):
  2509	    """Scan directory and recommend files matching a dependency."""
  2510	    from .models import AssetKind as AK
  2511	    pack = store.get_pack(pack_name)
  2512	    if not pack:
  2513	        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
  2514	
  2515	    dep = None
  2516	    for d in pack.dependencies:
  2517	        if d.id == dep_id:
  2518	            dep = d
  2519	            break
  2520	    if not dep:
  2521	        raise HTTPException(status_code=404, detail=f"Dependency not found: {dep_id}")
  2522	
  2523	    kind = getattr(dep, "kind", None)
  2524	    recommendations = store.local_file_service.recommend(directory, dep, kind)
  2525	
  2526	    return {
  2527	        "recommendations": [
  2528	            {
  2529	                "file": {
  2530	                    "name": r.file.name,
  2531	                    "path": r.file.path,
  2532	                    "size": r.file.size,
  2533	                    "mtime": r.file.mtime,
  2534	                    "extension": r.file.extension,
  2535	                    "cached_hash": r.file.cached_hash,
  2536	                },
  2537	                "match_type": r.match_type,
  2538	                "confidence": r.confidence,
  2539	                "reason": r.reason,
  2540	            }
  2541	            for r in recommendations
  2542	        ]
  2543	    }
  2544	
  2545	
  2546	@v2_packs_router.post("/{pack_name}/import-local")
  2547	async def import_local_file(
  2548	    pack_name: str,
  2549	    request: ImportLocalRequest,
  2550	    background_tasks: BackgroundTasks,
  2551	    store=Depends(require_initialized),
  2552	):
  2553	    """Import a local file into blob store and resolve dependency.
  2554	
  2555	    For large files, runs hashing/copying in a background thread.
  2556	    Returns import_id for progress tracking.
  2557	    """
  2558	    import uuid
  2559	    import threading
  2560	
  2561	    pack = store.get_pack(pack_name)
  2562	    if not pack:
  2563	        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")
  2564	
  2565	    # Validate file path early
  2566	    from .local_file_service import validate_path, PathValidationError
  2567	    try:
  2568	        resolved = validate_path(request.file_path)
  2569	        file_size = resolved.stat().st_size
  2570	    except PathValidationError as e:
  2571	        raise HTTPException(status_code=400, detail=str(e))
  2572	
  2573	    import_id = str(uuid.uuid4())[:8]
  2574	    _active_imports[import_id] = {
  2575	        "import_id": import_id,
  2576	        "pack_name": pack_name,
  2577	        "dep_id": request.dep_id,
  2578	        "filename": resolved.name,
  2579	        "file_size": file_size,
  2580	        "status": "pending",
  2581	        "stage": "",
  2582	        "progress": 0.0,
  2583	        "result": None,
  2584	    }
  2585	
  2586	    def progress_callback(stage: str, progress: float):
  2587	        if import_id in _active_imports:
  2588	            _active_imports[import_id]["stage"] = stage
  2589	            _active_imports[import_id]["progress"] = progress
  2590	            _active_imports[import_id]["status"] = "importing"
  2591	
  2592	    def run_import():
  2593	        import time as _time
  2594	        try:
  2595	            _active_imports[import_id]["status"] = "importing"
  2596	            result = store.local_file_service.import_file(
  2597	                file_path=request.file_path,
  2598	                pack_name=pack_name,
  2599	                dep_id=request.dep_id,
  2600	                skip_enrichment=request.skip_enrichment,
  2601	                progress_callback=progress_callback,
  2602	            )
  2603	            if import_id in _active_imports:
  2604	                _active_imports[import_id]["status"] = "completed" if result.success else "failed"
  2605	                _active_imports[import_id]["progress"] = 1.0
  2606	                _active_imports[import_id]["result"] = result.model_dump()
  2607	                _active_imports[import_id]["_finished_at"] = _time.time()
  2608	        except Exception as e:
  2609	            logger.error("[import-local] Error: %s", e, exc_info=True)
  2610	            if import_id in _active_imports:
  2611	                _active_imports[import_id]["status"] = "failed"
  2612	                _active_imports[import_id]["result"] = {"success": False, "message": str(e)}
  2613	                _active_imports[import_id]["_finished_at"] = _time.time()
  2614	
  2615	    _cleanup_old_imports()
  2616	    _get_import_executor().submit(run_import)
  2617	
  2618	    return {
  2619	        "import_id": import_id,
  2620	        "pack_name": pack_name,
  2621	        "dep_id": request.dep_id,
  2622	        "filename": resolved.name,
  2623	        "file_size": file_size,
  2624	        "status": "pending",
  2625	    }

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/avatar/mcp/store_server.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Synapse Store MCP Server — Tools for AI avatar.
     3	
     4	Provides 21 tools for querying packs, inventory, backup status,
     5	storage statistics, Civitai interaction, workflow analysis, and
     6	dependency resolution. Uses FastMCP with stdio transport.
     7	
     8	All tool implementations are in _*_impl() functions for testability
     9	without requiring the mcp package.
    10	
    11	Tool groups:
    12	  - Store (10): list_packs, get_pack_details, search_packs, get_pack_parameters,
    13	    get_inventory_summary, find_orphan_blobs, find_missing_blobs, get_backup_status,
    14	    check_pack_updates, get_storage_stats
    15	  - Civitai (4): search_civitai, analyze_civitai_model, compare_model_versions,
    16	    import_civitai_model
    17	  - Workflow (4): scan_workflow, scan_workflow_file, check_workflow_availability,
    18	    list_custom_nodes
    19	  - Dependencies (3): resolve_workflow_dependencies, find_model_by_hash,
    20	    suggest_asset_sources
    21	"""
    22	
    23	from __future__ import annotations
    24	
    25	import json
    26	import logging
    27	import threading
    28	from pathlib import Path
    29	from typing import Any, Optional
    30	
    31	logger = logging.getLogger(__name__)
    32	
    33	# Guard MCP import — module is usable without mcp installed (for tests)
    34	try:
    35	    from mcp.server.fastmcp import FastMCP
    36	
    37	    MCP_AVAILABLE = True
    38	except ImportError:
    39	    MCP_AVAILABLE = False
    40	
    41	# Lazy Store singleton (thread-safe)
    42	_store_instance = None
    43	_store_lock = threading.Lock()
    44	
    45	
    46	def _log_tool_call(tool_name: str, **kwargs: Any) -> None:
    47	    """Log MCP tool invocation at DEBUG level."""
    48	    args = ", ".join(f"{k}={v!r}" for k, v in kwargs.items() if v)
    49	    logger.debug("[mcp] %s(%s)", tool_name, args)
    50	
    51	
    52	def _get_store() -> Any:
    53	    """Get or create Store singleton (same pattern as src/store/api.py)."""
    54	    global _store_instance
    55	    if _store_instance is None:
    56	        with _store_lock:
    57	            if _store_instance is None:
    58	                from src.store import Store
    59	                from config.settings import get_config
    60	
    61	                cfg = get_config()
    62	                civitai_api_key = None
    63	                if hasattr(cfg, "api") and hasattr(cfg.api, "civitai_token"):
    64	                    civitai_api_key = cfg.api.civitai_token
    65	
    66	                _store_instance = Store(root=cfg.store.root, civitai_api_key=civitai_api_key)
    67	                logger.info(
    68	                    "[mcp] Store initialized: root=%s, civitai_token=%s",
    69	                    cfg.store.root,
    70	                    "set" if civitai_api_key else "not set",
    71	                )
    72	    return _store_instance
    73	
    74	
    75	def _reset_store() -> None:
    76	    """Reset Store singleton (for testing)."""
    77	    global _store_instance
    78	    with _store_lock:
    79	        _store_instance = None
    80	
    81	
    82	def _format_size(size_bytes: int) -> str:
    83	    """Format bytes into human-readable size."""
    84	    if size_bytes < 1024:
    85	        return f"{size_bytes} B"
    86	    elif size_bytes < 1024 * 1024:
    87	        return f"{size_bytes / 1024:.1f} KB"
    88	    elif size_bytes < 1024 * 1024 * 1024:
    89	        return f"{size_bytes / (1024 * 1024):.1f} MB"
    90	    else:
    91	        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    92	
    93	
    94	# =============================================================================
    95	# Tool implementations (_impl functions for testability)
    96	# =============================================================================
    97	
    98	
    99	_MAX_LIMIT = 100
   100	
   101	
   102	def _list_packs_impl(store: Any = None, name_filter: str = "", limit: int = 20) -> str:
   103	    """List all packs in the Synapse store."""
   104	    try:
   105	        if store is None:
   106	            store = _get_store()
   107	
   108	        limit = max(1, min(limit, _MAX_LIMIT))
   109	        pack_names = store.list_packs()
   110	
   111	        # Apply filter
   112	        if name_filter:
   113	            filter_lower = name_filter.lower()
   114	            pack_names = [n for n in pack_names if filter_lower in n.lower()]
   115	
   116	        # Apply limit
   117	        total = len(pack_names)
   118	        pack_names = pack_names[:limit]
   119	
   120	        if not pack_names:
   121	            if name_filter:
   122	                return f"No packs found matching '{name_filter}'."
   123	            return "No packs in the store."
   124	
   125	        lines = [f"Found {total} pack{'s' if total != 1 else ''}:"]
   126	        if total > limit:
   127	            lines[0] += f" (showing first {limit})"
   128	        lines.append("")
   129	
   130	        for i, name in enumerate(pack_names, 1):
   131	            try:
   132	                pack = store.get_pack(name)
   133	                pack_type = pack.pack_type.value if hasattr(pack.pack_type, "value") else str(pack.pack_type)
   134	                base = f" — Base: {pack.base_model}" if pack.base_model else ""
   135	                dep_count = len(pack.dependencies)
   136	                source = pack.source.provider.value if pack.source else "unknown"
   137	                lines.append(
   138	                    f"{i}. {name} ({pack_type}){base}"
   139	                )
   140	                lines.append(
   141	                    f"   {dep_count} dependenc{'y' if dep_count == 1 else 'ies'}, Source: {source}"
   142	                )
   143	            except Exception as e:
   144	                logger.debug("Failed to load pack '%s': %s", name, e)
   145	                lines.append(f"{i}. {name} (error loading details)")
   146	
   147	        return "\n".join(lines)
   148	    except Exception as e:
   149	        logger.error("list_packs failed: %s", e, exc_info=True)
   150	        return f"Error: {e}"
   151	
   152	
   153	def _get_pack_details_impl(store: Any = None, pack_name: str = "") -> str:
   154	    """Get detailed information about a specific pack."""
   155	    try:
   156	        if store is None:
   157	            store = _get_store()
   158	
   159	        if not pack_name:
   160	            return "Error: pack_name is required."
   161	
   162	        try:
   163	            pack = store.get_pack(pack_name)
   164	        except Exception as e:
   165	            logger.debug("get_pack('%s') failed: %s", pack_name, e)
   166	            return f"Error: Pack '{pack_name}' not found."
   167	
   168	        pack_type = pack.pack_type.value if hasattr(pack.pack_type, "value") else str(pack.pack_type)
   169	        source_provider = pack.source.provider.value if pack.source else "unknown"
   170	
   171	        lines = [
   172	            f"Pack: {pack.name}",
   173	            f"Type: {pack_type}",
   174	        ]
   175	
   176	        if pack.base_model:
   177	            lines.append(f"Base Model: {pack.base_model}")
   178	        if pack.version:
   179	            lines.append(f"Version: {pack.version}")
   180	        if pack.author:
   181	            lines.append(f"Author: {pack.author}")
   182	        if pack.description:
   183	            desc = pack.description[:200] + "..." if len(pack.description) > 200 else pack.description
   184	            lines.append(f"Description: {desc}")
   185	
   186	        lines.append(f"Source: {source_provider}")
   187	        if pack.source and pack.source.url:
   188	            lines.append(f"URL: {pack.source.url}")
   189	
   190	        if pack.trigger_words:
   191	            lines.append(f"Trigger Words: {', '.join(pack.trigger_words)}")
   192	
   193	        if pack.tags:
   194	            lines.append(f"Tags: {', '.join(pack.tags[:10])}")
   195	
   196	        # Dependencies
   197	        if pack.dependencies:
   198	            lines.append(f"\nDependencies ({len(pack.dependencies)}):")
   199	            for dep in pack.dependencies:
   200	                kind = dep.kind.value if hasattr(dep.kind, "value") else str(dep.kind)
   201	                filename = dep.expose.filename if dep.expose else dep.id
   202	                lines.append(f"  - {filename} ({kind})")
   203	
   204	        # Parameters (directly on Pack, not under resources)
   205	        if pack.parameters:
   206	            params = pack.parameters
   207	            lines.append("\nGeneration Parameters:")
   208	            if params.sampler:
   209	                lines.append(f"  Sampler: {params.sampler}")
   210	            if params.scheduler:
   211	                lines.append(f"  Scheduler: {params.scheduler}")
   212	            if params.steps:
   213	                lines.append(f"  Steps: {params.steps}")
   214	            if params.cfg_scale:
   215	                lines.append(f"  CFG Scale: {params.cfg_scale}")
   216	            if params.clip_skip:
   217	                lines.append(f"  Clip Skip: {params.clip_skip}")
   218	            if params.width and params.height:
   219	                lines.append(f"  Size: {params.width}x{params.height}")
   220	            if params.strength:
   221	                lines.append(f"  Strength: {params.strength}")
   222	
   223	        return "\n".join(lines)
   224	    except Exception as e:
   225	        logger.error("get_pack_details failed: %s", e, exc_info=True)
   226	        return f"Error: {e}"
   227	
   228	
   229	def _search_packs_impl(store: Any = None, query: str = "") -> str:
   230	    """Search packs by name or metadata."""
   231	    try:
   232	        if store is None:
   233	            store = _get_store()
   234	
   235	        if not query:
   236	            return "Error: query is required."
   237	
   238	        result = store.search(query)
   239	
   240	        if not result.items:
   241	            return f"No packs found matching '{query}'."
   242	
   243	        lines = [f"Found {len(result.items)} pack{'s' if len(result.items) != 1 else ''} matching '{query}':", ""]
   244	
   245	        for i, item in enumerate(result.items, 1):
   246	            source = f", Source: {item.provider}" if item.provider else ""
   247	            lines.append(f"{i}. {item.pack_name} ({item.pack_type}){source}")
   248	
   249	        return "\n".join(lines)
   250	    except Exception as e:
   251	        logger.error("search_packs failed: %s", e, exc_info=True)
   252	        return f"Error: {e}"
   253	
   254	
   255	def _get_pack_parameters_impl(store: Any = None, pack_name: str = "") -> str:
   256	    """Get generation parameters for a pack."""
   257	    try:
   258	        if store is None:
   259	            store = _get_store()
   260	

exec
/bin/bash -lc "git grep -n \"search_huggingface\\|find_model_by_hash\\|@mcp.tool\" feat/resolve-model-redesign -- src/avatar/mcp/store_server.py | sed -n '1,240p'" in /home/box/git/github/synapse
 succeeded in 0ms:
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:19:  - Dependencies (3): resolve_workflow_dependencies, find_model_by_hash,
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1143:def _find_model_by_hash_impl(
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1179:        logger.error("find_model_by_hash failed: %s", e, exc_info=True)
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1229:def _search_huggingface_impl(
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1355:        logger.error("search_huggingface failed: %s", e, exc_info=True)
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1366:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1372:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1378:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1384:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1390:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1396:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1402:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1408:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1414:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1420:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1428:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1434:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1440:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1446:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1454:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1460:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1466:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1472:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1480:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1486:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1487:    def find_model_by_hash(hash_value: str) -> str:
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1489:        _log_tool_call("find_model_by_hash", hash_value=hash_value)
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1490:        return _find_model_by_hash_impl(hash_value=hash_value)
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1492:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1498:    @mcp.tool()
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1499:    def search_huggingface(query: str, kind: str = "", limit: int = 5) -> str:
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1501:        _log_tool_call("search_huggingface", query=query, kind=kind, limit=limit)
feat/resolve-model-redesign:src/avatar/mcp/store_server.py:1502:        return _search_huggingface_impl(query=query, kind=kind, limit=limit)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/avatar/mcp/store_server.py | nl -ba | sed -n '520,900p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   520	            "Storage Statistics:",
   521	            "",
   522	            f"  Total blobs: {summary.blobs_total}",
   523	            f"  Total size: {_format_size(summary.bytes_total)}",
   524	        ]
   525	
   526	        if summary.disk_total is not None:
   527	            used = summary.disk_total - (summary.disk_free or 0)
   528	            pct = (used / summary.disk_total * 100) if summary.disk_total > 0 else 0
   529	            lines.append(f"  Disk usage: {_format_size(used)} / {_format_size(summary.disk_total)} ({pct:.1f}%)")
   530	
   531	        # Per-kind breakdown
   532	        if summary.bytes_by_kind:
   533	            lines.append("")
   534	            lines.append("  Size by kind:")
   535	            for kind, size in sorted(summary.bytes_by_kind.items(), key=lambda x: x[1], reverse=True):
   536	                pct = (size / summary.bytes_total * 100) if summary.bytes_total > 0 else 0
   537	                lines.append(f"    {kind}: {_format_size(size)} ({pct:.1f}%)")
   538	
   539	        # Top 5 largest packs
   540	        pack_names = store.list_packs()
   541	        pack_sizes = []
   542	        for name in pack_names:
   543	            try:
   544	                pack = store.get_pack(name)
   545	                lock = store.get_pack_lock(name)
   546	                if lock:
   547	                    total = sum(
   548	                        r.artifact.size_bytes or 0
   549	                        for r in lock.resolved
   550	                        if r.artifact and r.artifact.size_bytes
   551	                    )
   552	                    if total > 0:
   553	                        pack_sizes.append((name, total))
   554	            except Exception as e:
   555	                logger.debug("Failed to compute size for pack '%s': %s", name, e)
   556	
   557	        if pack_sizes:
   558	            pack_sizes.sort(key=lambda x: x[1], reverse=True)
   559	            top = pack_sizes[:5]
   560	            lines.append("")
   561	            lines.append(f"  Top {len(top)} largest packs:")
   562	            for name, size in top:
   563	                lines.append(f"    {name}: {_format_size(size)}")
   564	
   565	        return "\n".join(lines)
   566	    except Exception as e:
   567	        logger.error("get_storage_stats failed: %s", e, exc_info=True)
   568	        return f"Error: {e}"
   569	
   570	
   571	# =============================================================================
   572	# Civitai tool implementations (Group A)
   573	# =============================================================================
   574	
   575	
   576	def _search_civitai_impl(
   577	    store: Any = None,
   578	    civitai: Any = None,
   579	    query: str = "",
   580	    types: str = "",
   581	    sort: str = "Most Downloaded",
   582	    limit: int = 10,
   583	) -> str:
   584	    """Search for models on Civitai."""
   585	    try:
   586	        if not query:
   587	            return "Error: query is required."
   588	
   589	        limit = max(1, min(limit, _MAX_LIMIT))
   590	
   591	        if civitai is None:
   592	            if store is None:
   593	                store = _get_store()
   594	            civitai = store.pack_service.civitai
   595	
   596	        type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
   597	
   598	        # Try Meilisearch first (full-text, same index as Civitai web UI).
   599	        # Falls back to REST API on failure OR empty results (belt-and-suspenders:
   600	        # some models are indexed differently between Meilisearch and REST).
   601	        items = []
   602	        try:
   603	            ms_response = civitai.search_meilisearch(
   604	                query=query,
   605	                types=type_list,
   606	                limit=limit,
   607	            )
   608	            items = ms_response.get("items", [])
   609	        except Exception as ms_err:
   610	            logger.debug("Meilisearch search failed, falling back to REST: %s", ms_err)
   611	
   612	        # Fallback to REST API if Meilisearch returned nothing
   613	        if not items:
   614	            response = civitai.search_models(
   615	                query=query,
   616	                types=type_list,
   617	                sort=sort,
   618	                limit=limit,
   619	            )
   620	            items = response.get("items", [])
   621	
   622	        if not items:
   623	            return f"No models found on Civitai matching '{query}'."
   624	
   625	        lines = [f"Found {len(items)} model{'s' if len(items) != 1 else ''} on Civitai:", ""]
   626	
   627	        for i, model in enumerate(items, 1):
   628	            name = model.get("name", "Unknown")
   629	            model_type = model.get("type", "Unknown")
   630	            model_id = model.get("id", 0)
   631	            versions = model.get("modelVersions", [])
   632	            version_count = len(versions)
   633	            latest = versions[0].get("name", "") if versions else ""
   634	            base = versions[0].get("baseModel", "") if versions else ""
   635	
   636	            lines.append(f"{i}. {name} ({model_type}, ID: {model_id})")
   637	            info_parts = []
   638	            if version_count:
   639	                info_parts.append(f"{version_count} version{'s' if version_count != 1 else ''}")
   640	            if latest:
   641	                info_parts.append(f"Latest: {latest}")
   642	            if base:
   643	                info_parts.append(f"Base: {base}")
   644	            if info_parts:
   645	                lines.append(f"   {', '.join(info_parts)}")
   646	
   647	        return "\n".join(lines)
   648	    except Exception as e:
   649	        logger.error("search_civitai failed: %s", e, exc_info=True)
   650	        return f"Error: {e}"
   651	
   652	
   653	def _analyze_civitai_model_impl(
   654	    store: Any = None,
   655	    civitai: Any = None,
   656	    url: str = "",
   657	) -> str:
   658	    """Analyze a Civitai model: versions, files, base model, tags."""
   659	    try:
   660	        if not url:
   661	            return "Error: url is required."
   662	
   663	        if civitai is None:
   664	            if store is None:
   665	                store = _get_store()
   666	            civitai = store.pack_service.civitai
   667	
   668	        model_id, version_id = civitai.parse_civitai_url(url)
   669	        model_data = civitai.get_model(model_id)
   670	
   671	        name = model_data.get("name", "Unknown")
   672	        model_type = model_data.get("type", "Unknown")
   673	        tags = model_data.get("tags", [])
   674	        creator = model_data.get("creator", {})
   675	        creator_name = creator.get("username", "Unknown") if creator else "Unknown"
   676	        description = model_data.get("description", "")
   677	        if description and len(description) > 300:
   678	            description = description[:300] + "..."
   679	
   680	        lines = [
   681	            f"Model: {name}",
   682	            f"Type: {model_type}",
   683	            f"ID: {model_id}",
   684	            f"Creator: {creator_name}",
   685	        ]
   686	
   687	        if tags:
   688	            lines.append(f"Tags: {', '.join(tags[:10])}")
   689	        if description:
   690	            lines.append(f"Description: {description}")
   691	
   692	        versions = model_data.get("modelVersions", [])
   693	        lines.append(f"\nVersions ({len(versions)}):")
   694	
   695	        for v in versions:
   696	            v_name = v.get("name", "")
   697	            v_id = v.get("id", 0)
   698	            base = v.get("baseModel", "")
   699	            files = v.get("files", [])
   700	            total_size = sum(f.get("sizeKB", 0) for f in files)
   701	            trained_words = v.get("trainedWords", [])
   702	
   703	            lines.append(f"\n  {v_name} (ID: {v_id})")
   704	            if base:
   705	                lines.append(f"    Base Model: {base}")
   706	            if files:
   707	                lines.append(f"    Files: {len(files)}, Total: {_format_size(int(total_size * 1024))}")
   708	                for f in files:
   709	                    f_name = f.get("name", "")
   710	                    f_id = f.get("id", 0)
   711	                    f_size = f.get("sizeKB", 0)
   712	                    primary = " [primary]" if f.get("primary") else ""
   713	                    lines.append(f"      - {f_name} (file_id: {f_id}, {_format_size(int(f_size * 1024))}){primary}")
   714	                    f_hashes = f.get("hashes", {})
   715	                    if f_hashes.get("SHA256"):
   716	                        lines.append(f"        SHA256: {f_hashes['SHA256']}")
   717	                    if f_hashes.get("AutoV2"):
   718	                        lines.append(f"        AutoV2: {f_hashes['AutoV2']}")
   719	            if trained_words:
   720	                lines.append(f"    Trigger Words: {', '.join(trained_words)}")
   721	
   722	        return "\n".join(lines)
   723	    except ValueError as e:
   724	        return f"Error: {e}"
   725	    except Exception as e:
   726	        logger.error("analyze_civitai_model failed: %s", e, exc_info=True)
   727	        return f"Error: {e}"
   728	
   729	
   730	def _compare_model_versions_impl(
   731	    store: Any = None,
   732	    civitai: Any = None,
   733	    url: str = "",
   734	) -> str:
   735	    """Compare versions of a Civitai model side-by-side."""
   736	    try:
   737	        if not url:
   738	            return "Error: url is required."
   739	
   740	        if civitai is None:
   741	            if store is None:
   742	                store = _get_store()
   743	            civitai = store.pack_service.civitai
   744	
   745	        model_id, _ = civitai.parse_civitai_url(url)
   746	        model_data = civitai.get_model(model_id)
   747	
   748	        name = model_data.get("name", "Unknown")
   749	        versions = model_data.get("modelVersions", [])
   750	
   751	        if len(versions) < 2:
   752	            return f"Model '{name}' has only {len(versions)} version — nothing to compare."
   753	
   754	        lines = [f"Version comparison for {name}:", ""]
   755	
   756	        # Header
   757	        lines.append(f"{'Property':<20} | " + " | ".join(
   758	            f"{v.get('name', '?'):<20}" for v in versions[:5]
   759	        ))
   760	        lines.append("-" * (22 + 23 * min(len(versions), 5)))
   761	
   762	        # Base model
   763	        lines.append(f"{'Base Model':<20} | " + " | ".join(
   764	            f"{v.get('baseModel', 'N/A'):<20}" for v in versions[:5]
   765	        ))
   766	
   767	        # File count
   768	        lines.append(f"{'Files':<20} | " + " | ".join(
   769	            f"{len(v.get('files', [])):<20}" for v in versions[:5]
   770	        ))
   771	
   772	        # Total size
   773	        sizes = []
   774	        for v in versions[:5]:
   775	            total_kb = sum(f.get("sizeKB", 0) for f in v.get("files", []))
   776	            sizes.append(_format_size(int(total_kb * 1024)))
   777	        lines.append(f"{'Total Size':<20} | " + " | ".join(
   778	            f"{s:<20}" for s in sizes
   779	        ))
   780	
   781	        # Trained words
   782	        lines.append(f"{'Trigger Words':<20} | " + " | ".join(
   783	            f"{len(v.get('trainedWords', [])):<20}" for v in versions[:5]
   784	        ))
   785	
   786	        # Published date
   787	        lines.append(f"{'Published':<20} | " + " | ".join(
   788	            f"{(v.get('publishedAt', 'N/A') or 'N/A')[:10]:<20}" for v in versions[:5]
   789	        ))
   790	
   791	        if len(versions) > 5:
   792	            lines.append(f"\n... and {len(versions) - 5} more versions")
   793	
   794	        return "\n".join(lines)
   795	    except ValueError as e:
   796	        return f"Error: {e}"
   797	    except Exception as e:
   798	        logger.error("compare_model_versions failed: %s", e, exc_info=True)
   799	        return f"Error: {e}"
   800	
   801	
   802	def _import_civitai_model_impl(
   803	    store: Any = None,
   804	    civitai: Any = None,
   805	    url: str = "",
   806	    pack_name: str = "",
   807	    download_previews: bool = True,
   808	) -> str:
   809	    """Import a model from Civitai into the Synapse store.
   810	
   811	    WARNING: This modifies the store. Creates pack directory, downloads model
   812	    files (potentially several GB).
   813	    """
   814	    try:
   815	        if not url:
   816	            return "Error: url is required."
   817	
   818	        if store is None:
   819	            store = _get_store()
   820	
   821	        kwargs: dict[str, Any] = {
   822	            "url": url,
   823	            "download_previews": download_previews,
   824	        }
   825	        if pack_name:
   826	            kwargs["pack_name"] = pack_name
   827	
   828	        pack = store.import_civitai(**kwargs)
   829	        logger.info("[mcp] Imported pack '%s' from %s (%d deps)", pack.name, url, len(pack.dependencies))
   830	
   831	        lines = [
   832	            f"Successfully imported pack: {pack.name}",
   833	            "",
   834	            f"  Type: {pack.pack_type.value if hasattr(pack.pack_type, 'value') else pack.pack_type}",
   835	        ]
   836	        if pack.base_model:
   837	            lines.append(f"  Base Model: {pack.base_model}")
   838	        lines.append(f"  Dependencies: {len(pack.dependencies)}")
   839	        if pack.source and pack.source.url:
   840	            lines.append(f"  Source: {pack.source.url}")
   841	
   842	        return "\n".join(lines)
   843	    except ValueError as e:
   844	        return f"Error: {e}"
   845	    except Exception as e:
   846	        logger.error("import_civitai_model failed: %s", e, exc_info=True)
   847	        return f"Error: {e}"
   848	
   849	
   850	# =============================================================================
   851	# Workflow tool implementations (Group B)
   852	# =============================================================================
   853	
   854	
   855	def _scan_workflow_impl(
   856	    workflow_json: str = "",
   857	) -> str:
   858	    """Scan a ComfyUI workflow JSON for model dependencies and custom nodes."""
   859	    try:
   860	        if not workflow_json:
   861	            return "Error: workflow_json is required."
   862	
   863	        try:
   864	            workflow_data = json.loads(workflow_json)
   865	        except json.JSONDecodeError as e:
   866	            return f"Error: Invalid JSON — {e}"
   867	
   868	        from src.workflows.scanner import WorkflowScanner
   869	
   870	        scanner = WorkflowScanner()
   871	        result = scanner.scan_workflow(workflow_data)
   872	        unique_assets = scanner.get_unique_assets(result)
   873	
   874	        lines = ["Workflow Scan Results:", ""]
   875	
   876	        if result.errors:
   877	            lines.append(f"Warnings: {', '.join(result.errors)}")
   878	            lines.append("")
   879	
   880	        lines.append(f"Nodes: {len(result.all_nodes)}")
   881	        lines.append(f"Assets: {len(unique_assets)}")
   882	        lines.append(f"Custom Nodes: {len(result.custom_node_types)}")
   883	
   884	        if unique_assets:
   885	            lines.append("\nModel Dependencies:")
   886	            for asset in unique_assets:
   887	                kind = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
   888	                lines.append(f"  - {asset.name} ({kind}, from {asset.node_type})")
   889	
   890	        if result.custom_node_types:
   891	            lines.append("\nCustom Node Types:")
   892	            for node_type in sorted(result.custom_node_types):
   893	                lines.append(f"  - {node_type}")
   894	
   895	        if not unique_assets and not result.custom_node_types:
   896	            lines.append("\nNo model dependencies or custom nodes found.")
   897	
   898	        return "\n".join(lines)
   899	    except Exception as e:
   900	        logger.error("scan_workflow failed: %s", e, exc_info=True)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/clients/huggingface_client.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	HuggingFace Client
     3	
     4	Handles downloads from HuggingFace Hub including:
     5	- Single file downloads
     6	- Repository snapshot downloads
     7	- Revision/branch handling
     8	- Resume support
     9	- Token authentication for gated repos
    10	"""
    11	
    12	import os
    13	import re
    14	import hashlib
    15	import requests
    16	from pathlib import Path
    17	from typing import Optional, Dict, Any, List, Callable
    18	from dataclasses import dataclass
    19	from urllib.parse import quote
    20	
    21	from ..core.models import (
    22	    AssetDependency, AssetType, AssetSource, AssetHash,
    23	    HuggingFaceSource, ASSET_TYPE_FOLDERS
    24	)
    25	
    26	
    27	@dataclass
    28	class HFFileInfo:
    29	    """Information about a file in a HuggingFace repository."""
    30	    filename: str
    31	    size: int
    32	    sha256: Optional[str]
    33	    lfs: bool
    34	    
    35	    @classmethod
    36	    def from_api_response(cls, data: Dict[str, Any]) -> 'HFFileInfo':
    37	        lfs_info = data.get("lfs")
    38	        sha256 = None
    39	        if isinstance(lfs_info, dict):
    40	            oid = lfs_info.get("oid", "")
    41	            # HF LFS OID format: "sha256:<hex>" — strip prefix
    42	            sha256 = oid.split(":", 1)[-1] if oid else None
    43	        return cls(
    44	            filename=data.get("path", ""),
    45	            size=data.get("size", 0),
    46	            sha256=sha256,
    47	            lfs=lfs_info is not None,
    48	        )
    49	
    50	
    51	@dataclass
    52	class HFRepoInfo:
    53	    """Information about a HuggingFace repository."""
    54	    repo_id: str
    55	    revision: str
    56	    files: List[HFFileInfo]
    57	    
    58	    @classmethod
    59	    def from_api_response(cls, repo_id: str, revision: str, data: List[Dict[str, Any]]) -> 'HFRepoInfo':
    60	        return cls(
    61	            repo_id=repo_id,
    62	            revision=revision,
    63	            files=[HFFileInfo.from_api_response(f) for f in data if f.get("type") == "file"],
    64	        )
    65	
    66	
    67	class HuggingFaceClient:
    68	    """
    69	    Client for HuggingFace Hub downloads.
    70	    
    71	    Features:
    72	    - Single file and repository downloads
    73	    - Resume support for large files
    74	    - Token authentication for gated models
    75	    - Revision/branch support
    76	    - Progress callbacks
    77	    """
    78	    
    79	    BASE_URL = "https://huggingface.co"
    80	    API_URL = "https://huggingface.co/api"
    81	    
    82	    # Known model file patterns and their types
    83	    FILE_TYPE_PATTERNS = {
    84	        r".*\.safetensors$": AssetType.CHECKPOINT,
    85	        r".*lora.*\.safetensors$": AssetType.LORA,
    86	        r".*vae.*\.safetensors$": AssetType.VAE,
    87	        r".*text_encoder.*\.safetensors$": AssetType.TEXT_ENCODER,
    88	        r".*diffusion_model.*\.safetensors$": AssetType.DIFFUSION_MODEL,
    89	        r".*unet.*\.safetensors$": AssetType.DIFFUSION_MODEL,
    90	        r".*clip.*\.safetensors$": AssetType.CLIP,
    91	        r".*controlnet.*\.safetensors$": AssetType.CONTROLNET,
    92	        r".*upscale.*\.safetensors$": AssetType.UPSCALER,
    93	    }
    94	    
    95	    # Folder-based type detection
    96	    FOLDER_TYPE_MAP = {
    97	        "text_encoders": AssetType.TEXT_ENCODER,
    98	        "text_encoder": AssetType.TEXT_ENCODER,
    99	        "vae": AssetType.VAE,
   100	        "unet": AssetType.DIFFUSION_MODEL,
   101	        "diffusion_models": AssetType.DIFFUSION_MODEL,
   102	        "controlnet": AssetType.CONTROLNET,
   103	        "loras": AssetType.LORA,
   104	        "embeddings": AssetType.EMBEDDING,
   105	    }
   106	    
   107	    def __init__(
   108	        self,
   109	        token: Optional[str] = None,
   110	        timeout: int = 30,
   111	    ):
   112	        self.token = token or os.environ.get("HF_TOKEN")
   113	        self.timeout = timeout
   114	        
   115	        self.session = requests.Session()
   116	        if self.token:
   117	            self.session.headers["Authorization"] = f"Bearer {self.token}"
   118	        self.session.headers["User-Agent"] = "Synapse/1.0"
   119	    
   120	    def search_models(
   121	        self,
   122	        query: str,
   123	        limit: int = 5,
   124	        pipeline_tag: Optional[str] = None,
   125	    ) -> List[Dict[str, Any]]:
   126	        """Search HuggingFace Hub models by query string.
   127	
   128	        Returns list of model dicts with: id, tags, pipeline_tag, downloads, sha (latest commit).
   129	        Used by HF enrichment and MCP tool.
   130	        """
   131	        url = f"{self.API_URL}/models"
   132	        params: Dict[str, Any] = {
   133	            "search": query,
   134	            "limit": min(limit, 20),
   135	            "sort": "downloads",
   136	            "direction": "-1",
   137	        }
   138	        if pipeline_tag:
   139	            params["pipeline_tag"] = pipeline_tag
   140	
   141	        try:
   142	            response = self.session.get(url, params=params, timeout=self.timeout)
   143	            response.raise_for_status()
   144	            return response.json()
   145	        except Exception:
   146	            return []
   147	
   148	    def get_repo_info(self, repo_id: str, revision: str = "main") -> Optional[Dict[str, Any]]:
   149	        """Get basic repository information."""
   150	        try:
   151	            url = f"{self.API_URL}/models/{repo_id}"
   152	            response = self.session.get(url, timeout=self.timeout)
   153	            response.raise_for_status()
   154	            return response.json()
   155	        except Exception:
   156	            return None
   157	    
   158	    def get_repo_files(
   159	        self,
   160	        repo_id: str,
   161	        revision: str = "main",
   162	        path: str = "",
   163	    ) -> HFRepoInfo:
   164	        """List files in a repository."""
   165	        url = f"{self.API_URL}/models/{repo_id}/tree/{revision}"
   166	        if path:
   167	            url += f"/{path}"
   168	        
   169	        response = self.session.get(url, timeout=self.timeout)
   170	        response.raise_for_status()
   171	        
   172	        return HFRepoInfo.from_api_response(repo_id, revision, response.json())
   173	    
   174	    def get_file_url(
   175	        self,
   176	        repo_id: str,
   177	        filename: str,
   178	        revision: str = "main",
   179	    ) -> str:
   180	        """Get download URL for a file."""
   181	        encoded_filename = quote(filename, safe="/")
   182	        return f"{self.BASE_URL}/{repo_id}/resolve/{revision}/{encoded_filename}"
   183	    
   184	    def parse_hf_url(self, url: str) -> tuple[str, str, str]:
   185	        """
   186	        Parse a HuggingFace URL to extract repo_id, filename, and revision.
   187	        
   188	        Supports formats:
   189	        - https://huggingface.co/owner/repo/blob/main/path/file.safetensors
   190	        - https://huggingface.co/owner/repo/resolve/main/path/file.safetensors
   191	        """
   192	        # Remove base URL
   193	        path = url.replace(self.BASE_URL + "/", "")
   194	        
   195	        # Match pattern: owner/repo/(blob|resolve)/revision/filepath
   196	        match = re.match(
   197	            r"([^/]+/[^/]+)/(?:blob|resolve)/([^/]+)/(.+)",
   198	            path
   199	        )
   200	        
   201	        if match:
   202	            repo_id = match.group(1)
   203	            revision = match.group(2)
   204	            filename = match.group(3)
   205	            return repo_id, filename, revision
   206	        
   207	        # Simple format: owner/repo
   208	        parts = path.split("/")
   209	        if len(parts) >= 2:
   210	            return f"{parts[0]}/{parts[1]}", "", "main"
   211	        
   212	        raise ValueError(f"Invalid HuggingFace URL: {url}")
   213	    
   214	    def detect_asset_type(self, filename: str, subfolder: Optional[str] = None) -> AssetType:
   215	        """Detect asset type from filename and path."""
   216	        # Check folder first
   217	        if subfolder:
   218	            folder_name = subfolder.rstrip("/").split("/")[-1].lower()
   219	            if folder_name in self.FOLDER_TYPE_MAP:
   220	                return self.FOLDER_TYPE_MAP[folder_name]
   221	        
   222	        # Check filename patterns
   223	        filename_lower = filename.lower()
   224	        for pattern, asset_type in self.FILE_TYPE_PATTERNS.items():
   225	            if re.match(pattern, filename_lower):
   226	                return asset_type
   227	        
   228	        # Default to checkpoint for .safetensors
   229	        if filename_lower.endswith(".safetensors"):
   230	            return AssetType.CHECKPOINT
   231	        
   232	        return AssetType.UNKNOWN
   233	    
   234	    def create_asset_dependency(
   235	        self,
   236	        repo_id: str,
   237	        filename: str,
   238	        revision: str = "main",
   239	        subfolder: Optional[str] = None,
   240	        file_size: Optional[int] = None,
   241	        sha256: Optional[str] = None,
   242	    ) -> AssetDependency:
   243	        """Create an AssetDependency from HuggingFace file info."""
   244	        
   245	        # Detect asset type
   246	        asset_type = self.detect_asset_type(filename, subfolder)
   247	        
   248	        # Build local path
   249	        folder = ASSET_TYPE_FOLDERS.get(asset_type, "unknown")
   250	        local_filename = filename.split("/")[-1]
   251	        local_path = f"{folder}/{local_filename}"
   252	        
   253	        # Build hash
   254	        asset_hash = AssetHash(sha256=sha256) if sha256 else None
   255	        
   256	        return AssetDependency(
   257	            name=f"{repo_id}/{filename}",
   258	            asset_type=asset_type,
   259	            source=AssetSource.HUGGINGFACE,
   260	            huggingface=HuggingFaceSource(

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/avatar/mcp/store_server.py | nl -ba | sed -n '1120,1370p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1120	        if asset_deps:
  1121	            lines.append(f"Model Assets ({len(asset_deps)}):")
  1122	            for dep in asset_deps:
  1123	                kind = dep.asset_type.value if hasattr(dep.asset_type, "value") else str(dep.asset_type)
  1124	                source = dep.source.value if hasattr(dep.source, "value") else str(dep.source)
  1125	                lines.append(f"  - {dep.name} ({kind})")
  1126	                lines.append(f"    Source: {source}")
  1127	                if hasattr(dep, "huggingface") and dep.huggingface:
  1128	                    lines.append(f"    HF Repo: {dep.huggingface.repo_id}")
  1129	                    lines.append(f"    HF File: {dep.huggingface.filename}")
  1130	
  1131	        if node_deps:
  1132	            lines.append(f"\nCustom Node Packages ({len(node_deps)}):")
  1133	            for dep in node_deps:
  1134	                lines.append(f"  - {dep.name}")
  1135	                lines.append(f"    Git: {dep.git_url}")
  1136	
  1137	        return "\n".join(lines)
  1138	    except Exception as e:
  1139	        logger.error("resolve_workflow_deps failed: %s", e, exc_info=True)
  1140	        return f"Error: {e}"
  1141	
  1142	
  1143	def _find_model_by_hash_impl(
  1144	    store: Any = None,
  1145	    civitai: Any = None,
  1146	    hash_value: str = "",
  1147	) -> str:
  1148	    """Find a model on Civitai by SHA256 or AutoV2 hash."""
  1149	    try:
  1150	        if not hash_value:
  1151	            return "Error: hash_value is required."
  1152	
  1153	        if civitai is None:
  1154	            if store is None:
  1155	                store = _get_store()
  1156	            civitai = store.pack_service.civitai
  1157	
  1158	        result = civitai.get_model_by_hash(hash_value)
  1159	
  1160	        if result is None:
  1161	            return f"No model found for hash: {hash_value}"
  1162	
  1163	        lines = [f"Found model version for hash {hash_value[:16]}...:", ""]
  1164	        lines.append(f"  Version: {result.name} (ID: {result.id})")
  1165	        lines.append(f"  Model ID: {result.model_id}")
  1166	        if hasattr(result, "base_model") and result.base_model:
  1167	            lines.append(f"  Base Model: {result.base_model}")
  1168	        if hasattr(result, "model_name"):
  1169	            lines.append(f"  Model Name: {result.model_name}")
  1170	
  1171	        if hasattr(result, "files") and result.files:
  1172	            lines.append(f"  Files: {len(result.files)}")
  1173	            for f in result.files:
  1174	                f_name = f.get("name", "") if isinstance(f, dict) else getattr(f, "name", "")
  1175	                lines.append(f"    - {f_name}")
  1176	
  1177	        return "\n".join(lines)
  1178	    except Exception as e:
  1179	        logger.error("find_model_by_hash failed: %s", e, exc_info=True)
  1180	        return f"Error: {e}"
  1181	
  1182	
  1183	def _suggest_asset_sources_impl(
  1184	    asset_names: str = "",
  1185	) -> str:
  1186	    """Suggest download sources for asset names."""
  1187	    try:
  1188	        if not asset_names:
  1189	            return "Error: asset_names is required (comma-separated list)."
  1190	
  1191	        names = [n.strip() for n in asset_names.split(",") if n.strip()]
  1192	        if not names:
  1193	            return "Error: No valid asset names provided."
  1194	
  1195	        from src.workflows.scanner import ScannedAsset
  1196	        from src.workflows.resolver import DependencyResolver
  1197	        from src.core.models import AssetType
  1198	
  1199	        resolver = DependencyResolver()
  1200	
  1201	        lines = [f"Source suggestions for {len(names)} asset{'s' if len(names) != 1 else ''}:", ""]
  1202	
  1203	        for name in names:
  1204	            # Create a minimal ScannedAsset for pattern matching
  1205	            asset = ScannedAsset(
  1206	                name=name,
  1207	                asset_type=AssetType.UNKNOWN,
  1208	                node_type="Unknown",
  1209	                node_id=0,
  1210	            )
  1211	            source = resolver.suggest_asset_source(asset)
  1212	            source_str = source.value if hasattr(source, "value") else str(source)
  1213	
  1214	            lines.append(f"  - {name}")
  1215	            lines.append(f"    Suggested source: {source_str}")
  1216	
  1217	            # Add extra info for known HF models
  1218	            if name in resolver.KNOWN_HF_MODELS:
  1219	                hf_info = resolver.KNOWN_HF_MODELS[name]
  1220	                lines.append(f"    HF Repo: {hf_info['repo_id']}")
  1221	                lines.append(f"    HF File: {hf_info['filename']}")
  1222	
  1223	        return "\n".join(lines)
  1224	    except Exception as e:
  1225	        logger.error("suggest_asset_sources failed: %s", e, exc_info=True)
  1226	        return f"Error: {e}"
  1227	
  1228	
  1229	def _search_huggingface_impl(
  1230	    query: str = "",
  1231	    kind: str = "",
  1232	    limit: int = 5,
  1233	) -> str:
  1234	    """Search for models on HuggingFace Hub and list their files."""
  1235	    try:
  1236	        if not query:
  1237	            return "Error: query is required."
  1238	
  1239	        import requests as _requests
  1240	
  1241	        limit = max(1, min(limit, 10))
  1242	
  1243	        # Step 1: Search HF Hub API
  1244	        params: dict = {"search": query, "limit": limit}
  1245	        if kind:
  1246	            # Map Synapse kind to HF pipeline_tag where applicable
  1247	            kind_to_pipeline = {
  1248	                "checkpoint": "text-to-image",
  1249	                "controlnet": "text-to-image",  # ControlNets also tagged text-to-image
  1250	            }
  1251	            pipeline = kind_to_pipeline.get(kind.lower())
  1252	            if pipeline:
  1253	                params["pipeline_tag"] = pipeline
  1254	
  1255	        resp = _requests.get(
  1256	            "https://huggingface.co/api/models",
  1257	            params=params,
  1258	            timeout=15,
  1259	        )
  1260	        resp.raise_for_status()
  1261	        models = resp.json()
  1262	
  1263	        if not models:
  1264	            return f"No models found on HuggingFace matching '{query}'."
  1265	
  1266	        lines = [f"Found {len(models)} model{'s' if len(models) != 1 else ''} on HuggingFace:", ""]
  1267	
  1268	        for i, model in enumerate(models, 1):
  1269	            repo_id = model.get("id", "")
  1270	            downloads = model.get("downloads", 0)
  1271	            pipeline_tag = model.get("pipeline_tag", "")
  1272	            tags = model.get("tags", [])
  1273	            last_modified = model.get("lastModified", "")
  1274	
  1275	            lines.append(f"{i}. {repo_id}")
  1276	            info_parts = []
  1277	            if downloads:
  1278	                info_parts.append(f"Downloads: {downloads:,}")
  1279	            if pipeline_tag:
  1280	                info_parts.append(f"Pipeline: {pipeline_tag}")
  1281	            if last_modified:
  1282	                info_parts.append(f"Updated: {last_modified[:10]}")
  1283	            if info_parts:
  1284	                lines.append(f"   {', '.join(info_parts)}")
  1285	
  1286	            # Detect base model from tags (shared constant)
  1287	            from src.store.enrichment import HF_BASE_MODEL_TAGS
  1288	            detected_base = None
  1289	            for _t in tags:
  1290	                _tl = _t.lower()
  1291	                for _pat, _bm in HF_BASE_MODEL_TAGS.items():
  1292	                    if _pat in _tl:
  1293	                        detected_base = _bm
  1294	                        break
  1295	                if detected_base:
  1296	                    break
  1297	            if detected_base:
  1298	                lines.append(f"   Base model: {detected_base}")
  1299	
  1300	            # Show relevant tags (skip generic ones)
  1301	            skip_tags = {"diffusers", "safetensors", "region:us", "endpoints_compatible"}
  1302	            relevant_tags = [t for t in tags if t not in skip_tags and not t.startswith("diffusers:")]
  1303	            if relevant_tags:
  1304	                lines.append(f"   Tags: {', '.join(relevant_tags[:8])}")
  1305	
  1306	            # Step 2: Fetch file listing for each repo (top-level only)
  1307	            try:
  1308	                tree_resp = _requests.get(
  1309	                    f"https://huggingface.co/api/models/{repo_id}/tree/main",
  1310	                    timeout=10,
  1311	                )
  1312	                tree_resp.raise_for_status()
  1313	                tree = tree_resp.json()
  1314	
  1315	                # Filter to model files (safetensors, ckpt, bin, pt)
  1316	                model_exts = {".safetensors", ".ckpt", ".bin", ".pt"}
  1317	                model_files = [
  1318	                    f for f in tree
  1319	                    if f.get("type") == "file"
  1320	                    and any(f.get("path", "").endswith(ext) for ext in model_exts)
  1321	                ]
  1322	
  1323	                if model_files:
  1324	                    lines.append(f"   Model files ({len(model_files)}):")
  1325	                    for mf in model_files[:5]:
  1326	                        path = mf.get("path", "")
  1327	                        size = mf.get("size", 0)
  1328	                        lfs = mf.get("lfs")
  1329	                        sha256 = ""
  1330	                        if lfs and isinstance(lfs, dict):
  1331	                            sha256 = lfs.get("oid", "") or lfs.get("sha256", "")
  1332	
  1333	                        size_str = _format_size(size) if size else "?"
  1334	                        lines.append(f"     - {path} ({size_str})")
  1335	                        if sha256:
  1336	                            lines.append(f"       SHA256: {sha256}")
  1337	                    if len(model_files) > 5:
  1338	                        lines.append(f"     ... and {len(model_files) - 5} more files")
  1339	                else:
  1340	                    # Check if it's a diffusers-format repo
  1341	                    has_model_index = any(
  1342	                        f.get("path") == "model_index.json" for f in tree
  1343	                    )
  1344	                    if has_model_index:
  1345	                        lines.append("   Format: diffusers pipeline (multi-file, not single checkpoint)")
  1346	                    else:
  1347	                        lines.append("   No model files found in root")
  1348	            except Exception:
  1349	                lines.append("   (could not fetch file listing)")
  1350	
  1351	            lines.append("")  # blank line between results
  1352	
  1353	        return "\n".join(lines)
  1354	    except Exception as e:
  1355	        logger.error("search_huggingface failed: %s", e, exc_info=True)
  1356	        return f"Error: {e}"
  1357	
  1358	
  1359	# =============================================================================
  1360	# MCP Tool registration (only when mcp is available)
  1361	# =============================================================================
  1362	
  1363	if MCP_AVAILABLE:
  1364	    mcp = FastMCP("synapse-store")
  1365	
  1366	    @mcp.tool()
  1367	    def list_packs(name_filter: str = "", limit: int = 20) -> str:
  1368	        """List all packs in the Synapse store. Optionally filter by name and limit results."""
  1369	        _log_tool_call("list_packs", name_filter=name_filter, limit=limit)
  1370	        return _list_packs_impl(name_filter=name_filter, limit=limit)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/avatar/mcp/store_server.py | nl -ba | sed -n '1360,1510p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1360	# MCP Tool registration (only when mcp is available)
  1361	# =============================================================================
  1362	
  1363	if MCP_AVAILABLE:
  1364	    mcp = FastMCP("synapse-store")
  1365	
  1366	    @mcp.tool()
  1367	    def list_packs(name_filter: str = "", limit: int = 20) -> str:
  1368	        """List all packs in the Synapse store. Optionally filter by name and limit results."""
  1369	        _log_tool_call("list_packs", name_filter=name_filter, limit=limit)
  1370	        return _list_packs_impl(name_filter=name_filter, limit=limit)
  1371	
  1372	    @mcp.tool()
  1373	    def get_pack_details(pack_name: str) -> str:
  1374	        """Get detailed information about a specific pack including dependencies and parameters."""
  1375	        _log_tool_call("get_pack_details", pack_name=pack_name)
  1376	        return _get_pack_details_impl(pack_name=pack_name)
  1377	
  1378	    @mcp.tool()
  1379	    def search_packs(query: str) -> str:
  1380	        """Search packs by name or dependency ID."""
  1381	        _log_tool_call("search_packs", query=query)
  1382	        return _search_packs_impl(query=query)
  1383	
  1384	    @mcp.tool()
  1385	    def get_pack_parameters(pack_name: str) -> str:
  1386	        """Get generation parameters (sampler, steps, CFG, size) for a pack."""
  1387	        _log_tool_call("get_pack_parameters", pack_name=pack_name)
  1388	        return _get_pack_parameters_impl(pack_name=pack_name)
  1389	
  1390	    @mcp.tool()
  1391	    def get_inventory_summary() -> str:
  1392	        """Get a summary of the blob inventory: counts, sizes, orphans, missing."""
  1393	        _log_tool_call("get_inventory_summary")
  1394	        return _get_inventory_summary_impl()
  1395	
  1396	    @mcp.tool()
  1397	    def find_orphan_blobs() -> str:
  1398	        """Find blobs not referenced by any pack (candidates for cleanup)."""
  1399	        _log_tool_call("find_orphan_blobs")
  1400	        return _find_orphan_blobs_impl()
  1401	
  1402	    @mcp.tool()
  1403	    def find_missing_blobs() -> str:
  1404	        """Find blobs referenced by packs but missing from local storage."""
  1405	        _log_tool_call("find_missing_blobs")
  1406	        return _find_missing_blobs_impl()
  1407	
  1408	    @mcp.tool()
  1409	    def get_backup_status() -> str:
  1410	        """Get backup storage status: connection, blob count, free space."""
  1411	        _log_tool_call("get_backup_status")
  1412	        return _get_backup_status_impl()
  1413	
  1414	    @mcp.tool()
  1415	    def check_pack_updates(pack_name: str = "") -> str:
  1416	        """Check for available updates. Leave pack_name empty to check all packs. Note: checking all packs makes one API call per pack to Civitai, which may be slow for large libraries."""
  1417	        _log_tool_call("check_pack_updates", pack_name=pack_name)
  1418	        return _check_pack_updates_impl(pack_name=pack_name)
  1419	
  1420	    @mcp.tool()
  1421	    def get_storage_stats() -> str:
  1422	        """Get detailed storage statistics: total size, per-kind breakdown, largest packs."""
  1423	        _log_tool_call("get_storage_stats")
  1424	        return _get_storage_stats_impl()
  1425	
  1426	    # ----- Civitai tools (Group A) -----
  1427	
  1428	    @mcp.tool()
  1429	    def search_civitai(query: str, types: str = "", sort: str = "Most Downloaded", limit: int = 10) -> str:
  1430	        """Search for models on Civitai. Filter by types (comma-separated: LORA, Checkpoint, etc.) and sort order."""
  1431	        _log_tool_call("search_civitai", query=query, types=types, sort=sort)
  1432	        return _search_civitai_impl(query=query, types=types, sort=sort, limit=limit)
  1433	
  1434	    @mcp.tool()
  1435	    def analyze_civitai_model(url: str) -> str:
  1436	        """Analyze a Civitai model URL: all versions, files, sizes, base model, trigger words, tags."""
  1437	        _log_tool_call("analyze_civitai_model", url=url)
  1438	        return _analyze_civitai_model_impl(url=url)
  1439	
  1440	    @mcp.tool()
  1441	    def compare_model_versions(url: str) -> str:
  1442	        """Compare all versions of a Civitai model side-by-side: base model, size, files, trigger words."""
  1443	        _log_tool_call("compare_model_versions", url=url)
  1444	        return _compare_model_versions_impl(url=url)
  1445	
  1446	    @mcp.tool()
  1447	    def import_civitai_model(url: str, pack_name: str = "", download_previews: bool = True) -> str:
  1448	        """Import a model from Civitai into the Synapse store. WARNING: This modifies the store — creates pack directory and downloads model files (potentially several GB)."""
  1449	        _log_tool_call("import_civitai_model", url=url, pack_name=pack_name)
  1450	        return _import_civitai_model_impl(url=url, pack_name=pack_name, download_previews=download_previews)
  1451	
  1452	    # ----- Workflow tools (Group B) -----
  1453	
  1454	    @mcp.tool()
  1455	    def scan_workflow(workflow_json: str) -> str:
  1456	        """Analyze a ComfyUI workflow JSON string for model dependencies and custom node requirements."""
  1457	        _log_tool_call("scan_workflow", workflow_json=f"({len(workflow_json)} chars)")
  1458	        return _scan_workflow_impl(workflow_json=workflow_json)
  1459	
  1460	    @mcp.tool()
  1461	    def scan_workflow_file(path: str) -> str:
  1462	        """Analyze a ComfyUI workflow file (.json) for model dependencies and custom nodes."""
  1463	        _log_tool_call("scan_workflow_file", path=path)
  1464	        return _scan_workflow_file_impl(path=path)
  1465	
  1466	    @mcp.tool()
  1467	    def check_workflow_availability(workflow_json: str) -> str:
  1468	        """Check which workflow model dependencies are locally available in the Synapse store."""
  1469	        _log_tool_call("check_workflow_availability", workflow_json=f"({len(workflow_json)} chars)")
  1470	        return _check_workflow_availability_impl(workflow_json=workflow_json)
  1471	
  1472	    @mcp.tool()
  1473	    def list_custom_nodes(workflow_json: str) -> str:
  1474	        """List custom node packages required by a workflow with git repository URLs."""
  1475	        _log_tool_call("list_custom_nodes", workflow_json=f"({len(workflow_json)} chars)")
  1476	        return _list_custom_nodes_impl(workflow_json=workflow_json)
  1477	
  1478	    # ----- Dependency resolution tools (Group C) -----
  1479	
  1480	    @mcp.tool()
  1481	    def resolve_workflow_dependencies(workflow_json: str) -> str:
  1482	        """Resolve all workflow dependencies: maps assets to download sources (Civitai/HuggingFace/local) and custom nodes to git repos."""
  1483	        _log_tool_call("resolve_workflow_dependencies", workflow_json=f"({len(workflow_json)} chars)")
  1484	        return _resolve_workflow_deps_impl(workflow_json=workflow_json)
  1485	
  1486	    @mcp.tool()
  1487	    def find_model_by_hash(hash_value: str) -> str:
  1488	        """Find a model on Civitai by SHA256 or AutoV2 hash. Useful for identifying unknown model files."""
  1489	        _log_tool_call("find_model_by_hash", hash_value=hash_value)
  1490	        return _find_model_by_hash_impl(hash_value=hash_value)
  1491	
  1492	    @mcp.tool()
  1493	    def suggest_asset_sources(asset_names: str) -> str:
  1494	        """Suggest download sources for model files. Provide comma-separated asset names (e.g. 'model.safetensors, vae.safetensors')."""
  1495	        _log_tool_call("suggest_asset_sources", asset_names=asset_names)
  1496	        return _suggest_asset_sources_impl(asset_names=asset_names)
  1497	
  1498	    @mcp.tool()
  1499	    def search_huggingface(query: str, kind: str = "", limit: int = 5) -> str:
  1500	        """Search for models on HuggingFace Hub. Returns repo IDs, file listings with SHA256 hashes, and download counts. Filter by kind (checkpoint, vae, controlnet)."""
  1501	        _log_tool_call("search_huggingface", query=query, kind=kind, limit=limit)
  1502	        return _search_huggingface_impl(query=query, kind=kind, limit=limit)
  1503	else:
  1504	    mcp = None

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/clients/huggingface_client.py | nl -ba | sed -n '260,520p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	            huggingface=HuggingFaceSource(
   261	                repo_id=repo_id,
   262	                filename=filename,
   263	                revision=revision,
   264	                subfolder=subfolder,
   265	            ),
   266	            filename=local_filename,
   267	            file_size=file_size,
   268	            hash=asset_hash,
   269	            local_path=local_path,
   270	            required=True,
   271	        )
   272	    
   273	    def download_file(
   274	        self,
   275	        repo_id: str,
   276	        filename: str,
   277	        destination: Path,
   278	        revision: str = "main",
   279	        expected_hash: Optional[str] = None,
   280	        chunk_size: int = 8192,
   281	        progress_callback: Optional[Callable[[int, int], None]] = None,
   282	        resume: bool = True,
   283	    ) -> bool:
   284	        """
   285	        Download a file from HuggingFace Hub.
   286	        
   287	        Args:
   288	            repo_id: Repository ID (owner/repo)
   289	            filename: File path within repository
   290	            destination: Local file path
   291	            revision: Git revision (branch, tag, commit)
   292	            expected_hash: Expected SHA256 hash
   293	            chunk_size: Download chunk size
   294	            progress_callback: Callback(downloaded_bytes, total_bytes)
   295	            resume: Enable resume for interrupted downloads
   296	        
   297	        Returns:
   298	            True if download successful and hash verified
   299	        """
   300	        url = self.get_file_url(repo_id, filename, revision)
   301	        
   302	        destination.parent.mkdir(parents=True, exist_ok=True)
   303	        
   304	        headers = {}
   305	        if self.token:
   306	            headers["Authorization"] = f"Bearer {self.token}"
   307	        
   308	        mode = "wb"
   309	        initial_size = 0
   310	        
   311	        # Check for partial download
   312	        if resume and destination.exists():
   313	            initial_size = destination.stat().st_size
   314	            headers["Range"] = f"bytes={initial_size}-"
   315	            mode = "ab"
   316	        
   317	        response = self.session.get(
   318	            url,
   319	            headers=headers,
   320	            stream=True,
   321	            timeout=300,
   322	            allow_redirects=True,
   323	        )
   324	        
   325	        # Handle range response
   326	        if response.status_code == 416:  # Range not satisfiable
   327	            return self._verify_hash(destination, expected_hash)
   328	        
   329	        response.raise_for_status()
   330	        
   331	        # Get total size
   332	        total_size = int(response.headers.get("content-length", 0)) + initial_size
   333	        downloaded = initial_size
   334	        
   335	        # Download with progress
   336	        with open(destination, mode) as f:
   337	            for chunk in response.iter_content(chunk_size=chunk_size):
   338	                if chunk:
   339	                    f.write(chunk)
   340	                    downloaded += len(chunk)
   341	                    if progress_callback:
   342	                        progress_callback(downloaded, total_size)
   343	        
   344	        # Verify hash
   345	        return self._verify_hash(destination, expected_hash)
   346	    
   347	    def _verify_hash(self, path: Path, expected_hash: Optional[str]) -> bool:
   348	        """Verify file SHA256 hash."""
   349	        if not expected_hash:
   350	            return True
   351	        
   352	        sha256 = hashlib.sha256()
   353	        with open(path, "rb") as f:
   354	            for chunk in iter(lambda: f.read(8192), b""):
   355	                sha256.update(chunk)
   356	        
   357	        actual_hash = sha256.hexdigest()
   358	        return actual_hash.lower() == expected_hash.lower()
   359	    
   360	    def download_repo_files(
   361	        self,
   362	        repo_id: str,
   363	        destination_dir: Path,
   364	        patterns: Optional[List[str]] = None,
   365	        revision: str = "main",
   366	        progress_callback: Optional[Callable[[str, int, int], None]] = None,
   367	    ) -> List[Path]:
   368	        """
   369	        Download multiple files from a repository.
   370	        
   371	        Args:
   372	            repo_id: Repository ID
   373	            destination_dir: Local directory for downloads
   374	            patterns: File patterns to match (e.g., ["*.safetensors"])
   375	            revision: Git revision
   376	            progress_callback: Callback(filename, downloaded_bytes, total_bytes)
   377	        
   378	        Returns:
   379	            List of downloaded file paths
   380	        """
   381	        repo_info = self.get_repo_files(repo_id, revision)
   382	        downloaded = []
   383	        
   384	        for file_info in repo_info.files:
   385	            # Check patterns
   386	            if patterns:
   387	                matches = False
   388	                for pattern in patterns:
   389	                    if re.match(pattern.replace("*", ".*"), file_info.filename):
   390	                        matches = True
   391	                        break
   392	                if not matches:
   393	                    continue
   394	            
   395	            # Download file
   396	            dest_path = destination_dir / file_info.filename
   397	            
   398	            def file_progress(downloaded_bytes: int, total_bytes: int):
   399	                if progress_callback:
   400	                    progress_callback(file_info.filename, downloaded_bytes, total_bytes)
   401	            
   402	            success = self.download_file(
   403	                repo_id,
   404	                file_info.filename,
   405	                dest_path,
   406	                revision=revision,
   407	                expected_hash=file_info.sha256,
   408	                progress_callback=file_progress,
   409	            )
   410	            
   411	            if success:
   412	                downloaded.append(dest_path)
   413	        
   414	        return downloaded
   415	
   416	
   417	def create_huggingface_client() -> HuggingFaceClient:
   418	    """Factory function to create a configured HuggingFaceClient."""
   419	    return HuggingFaceClient(
   420	        token=os.environ.get("HF_TOKEN"),
   421	    )

codex
AI does call through `AvatarTaskService.execute_task("dependency_resolution", ...)`, and `task_service.py` now passes MCP servers for MCP-needing tasks. The MCP side has a HuggingFace search tool, but it is a text-returning helper and still only checks top-level repo files; that is weaker than the spec’s full tree/model-card/LFS verification language.
exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * DependencyResolverModal
     3	 *
     4	 * Generic modal for resolving ANY dependency type (checkpoint, LoRA, VAE, etc.).
     5	 * Replaces BaseModelResolverModal for all non-base-model dependencies.
     6	 *
     7	 * Tabs:
     8	 * 1. Candidates — auto-suggested results from evidence providers
     9	 * 2. Preview Analysis — metadata from preview images (if available)
    10	 * 3. AI Resolve — AI-powered search (if avatar available)
    11	 * 4. Civitai — manual Civitai search
    12	 * 5. HuggingFace — manual HF search (only for eligible kinds)
    13	 *
    14	 * Design follows BaseModelResolverModal aesthetic:
    15	 * - Dark theme with synapse accent
    16	 * - Rounded cards with selection state
    17	 * - Loading spinners, empty states
    18	 */
    19	
    20	import { useState, useEffect, useCallback } from 'react'
    21	import { useTranslation } from 'react-i18next'
    22	import {
    23	  X,
    24	  Loader2,
    25	  Check,
    26	  Search,
    27	  Sparkles,
    28	  Image,
    29	  Globe,
    30	  Database,
    31	  AlertTriangle,
    32	  ChevronDown,
    33	  ChevronRight,
    34	  Shield,
    35	  ShieldCheck,
    36	  ShieldQuestion,
    37	  ShieldAlert,
    38	  Download,
    39	  Info,
    40	  HardDrive,
    41	} from 'lucide-react'
    42	import { clsx } from 'clsx'
    43	import { Button } from '@/components/ui/Button'
    44	import type {
    45	  AssetType,
    46	  ResolutionCandidate,
    47	  SuggestResult,
    48	  SuggestOptions,
    49	  EvidenceGroupInfo,
    50	  ConfidenceLevel,
    51	} from '../types'
    52	import { HF_ELIGIBLE_KINDS } from '../types'
    53	import { ANIMATION_PRESETS } from '../constants'
    54	import { PreviewAnalysisTab } from './PreviewAnalysisTab'
    55	import { LocalResolveTab } from './LocalResolveTab'
    56	
    57	// =============================================================================
    58	// Types
    59	// =============================================================================
    60	
    61	type ResolverTab = 'candidates' | 'preview' | 'local' | 'ai-resolve' | 'civitai' | 'huggingface'
    62	
    63	export interface DependencyResolverModalProps {
    64	  isOpen: boolean
    65	  onClose: () => void
    66	  packName: string
    67	  depId: string
    68	  depName: string
    69	  kind: AssetType
    70	  baseModelHint?: string
    71	
    72	  // Candidates from suggest
    73	  candidates: ResolutionCandidate[]
    74	  isSuggesting: boolean
    75	  requestId?: string
    76	
    77	  // Actions
    78	  onSuggest: (options?: SuggestOptions) => Promise<SuggestResult>
    79	  onApply: (candidateId: string) => void
    80	  onApplyAndDownload: (candidateId: string) => void
    81	  isApplying: boolean
    82	
    83	  // Avatar
    84	  avatarAvailable: boolean
    85	}
    86	
    87	// =============================================================================
    88	// Helpers
    89	// =============================================================================
    90	
    91	function getConfidenceLevel(candidate: ResolutionCandidate): ConfidenceLevel {
    92	  if (candidate.tier === 1) return 'exact'
    93	  if (candidate.tier === 2) return 'high'
    94	  if (candidate.tier === 3) return 'possible'
    95	  return 'hint'
    96	}
    97	
    98	const CONFIDENCE_DISPLAY: Record<
    99	  ConfidenceLevel,
   100	  { icon: typeof ShieldCheck; label: string; color: string; bg: string }
   101	> = {
   102	  exact: {
   103	    icon: ShieldCheck,
   104	    label: 'Exact match',
   105	    color: 'text-green-400',
   106	    bg: 'bg-green-500/15',
   107	  },
   108	  high: {
   109	    icon: Shield,
   110	    label: 'High confidence',
   111	    color: 'text-blue-400',
   112	    bg: 'bg-blue-500/15',
   113	  },
   114	  possible: {
   115	    icon: ShieldQuestion,
   116	    label: 'Possible match',
   117	    color: 'text-amber-400',
   118	    bg: 'bg-amber-500/15',
   119	  },
   120	  hint: {
   121	    icon: ShieldAlert,
   122	    label: 'Hint — verify',
   123	    color: 'text-text-muted',
   124	    bg: 'bg-slate-mid/30',
   125	  },
   126	}
   127	
   128	function getDefaultTab(
   129	  candidates: ResolutionCandidate[],
   130	  avatarAvailable: boolean,
   131	): ResolverTab {
   132	  if (candidates.some((c) => c.tier <= 2)) return 'candidates'
   133	  if (candidates.length === 0) return 'candidates'
   134	  if (avatarAvailable) return 'ai-resolve'
   135	  return 'candidates'
   136	}
   137	
   138	// =============================================================================
   139	// Sub-components
   140	// =============================================================================
   141	
   142	interface TabDef {
   143	  id: ResolverTab
   144	  label: string
   145	  icon: React.ReactNode
   146	  visible: boolean
   147	}
   148	
   149	function TabButton({
   150	  tab,
   151	  currentTab,
   152	  onClick,
   153	  icon,
   154	  label,
   155	  badge,
   156	}: {
   157	  tab: ResolverTab
   158	  currentTab: ResolverTab
   159	  onClick: () => void
   160	  icon: React.ReactNode
   161	  label: string
   162	  badge?: number
   163	}) {
   164	  const isActive = tab === currentTab
   165	
   166	  return (
   167	    <button
   168	      onClick={onClick}
   169	      className={clsx(
   170	        'flex items-center justify-center gap-2 py-3 px-3',
   171	        'transition-all duration-200 font-medium text-sm whitespace-nowrap',
   172	        isActive
   173	          ? 'text-synapse border-b-2 border-synapse bg-synapse/10'
   174	          : 'text-text-muted hover:text-text-primary hover:bg-slate-mid/30'
   175	      )}
   176	    >
   177	      {icon}
   178	      {label}
   179	      {badge !== undefined && badge > 0 && (
   180	        <span
   181	          className={clsx(
   182	            'ml-1 px-1.5 py-0.5 rounded-full text-xs font-bold',
   183	            isActive ? 'bg-synapse/20 text-synapse' : 'bg-slate-mid text-text-muted'
   184	          )}
   185	        >
   186	          {badge}
   187	        </span>
   188	      )}
   189	    </button>
   190	  )
   191	}
   192	
   193	function CandidateCard({
   194	  candidate,
   195	  isSelected,
   196	  onSelect,
   197	  isExpanded,
   198	  onToggleExpand,
   199	}: {
   200	  candidate: ResolutionCandidate
   201	  isSelected: boolean
   202	  onSelect: () => void
   203	  isExpanded: boolean
   204	  onToggleExpand: () => void
   205	}) {
   206	  const level = getConfidenceLevel(candidate)
   207	  const display = CONFIDENCE_DISPLAY[level]
   208	  const IconComponent = display.icon
   209	
   210	  return (
   211	    <div
   212	      className={clsx(
   213	        'rounded-xl overflow-hidden transition-all duration-200',
   214	        isSelected
   215	          ? 'bg-synapse/20 border-2 border-synapse'
   216	          : 'bg-slate-dark border border-slate-mid hover:border-slate-mid/80'
   217	      )}
   218	    >
   219	      <div role="button" tabIndex={0} onClick={onSelect} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect() }} className="w-full text-left p-4 cursor-pointer">
   220	        <div className="flex items-start gap-3">
   221	          {/* Confidence indicator */}
   222	          <div className={clsx('p-2 rounded-lg flex-shrink-0', display.bg)}>
   223	            <IconComponent className={clsx('w-5 h-5', display.color)} />
   224	          </div>
   225	
   226	          {/* Content */}
   227	          <div className="min-w-0 flex-1">
   228	            <div className="flex items-center gap-2">
   229	              <p className="text-text-primary font-medium truncate">
   230	                {candidate.display_name}
   231	              </p>
   232	              {isSelected && <Check className="w-4 h-4 text-synapse flex-shrink-0" />}
   233	            </div>
   234	
   235	            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
   236	              <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', display.bg, display.color)}>
   237	                {display.label}
   238	              </span>
   239	              {candidate.provider && (
   240	                <span className="px-2 py-0.5 bg-slate-mid/50 text-text-muted text-xs rounded">
   241	                  {candidate.provider}
   242	                </span>
   243	              )}
   244	              {candidate.base_model && (
   245	                <span className="px-2 py-0.5 bg-pulse/20 text-pulse text-xs rounded">
   246	                  {candidate.base_model}
   247	                </span>
   248	              )}
   249	            </div>
   250	
   251	            {/* Compatibility warnings */}
   252	            {candidate.compatibility_warnings.length > 0 && (
   253	              <div className="mt-2 flex items-start gap-1.5">
   254	                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
   255	                <p className="text-xs text-amber-400">
   256	                  {candidate.compatibility_warnings[0]}
   257	                </p>
   258	              </div>
   259	            )}
   260	          </div>

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx | nl -ba | sed -n '260,560p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	          </div>
   261	
   262	          {/* Expand toggle */}
   263	          <button
   264	            onClick={(e) => {
   265	              e.stopPropagation()
   266	              onToggleExpand()
   267	            }}
   268	            className="p-1 hover:bg-slate-mid/30 rounded transition-colors flex-shrink-0"
   269	          >
   270	            {isExpanded ? (
   271	              <ChevronDown className="w-4 h-4 text-text-muted" />
   272	            ) : (
   273	              <ChevronRight className="w-4 h-4 text-text-muted" />
   274	            )}
   275	          </button>
   276	        </div>
   277	      </div>
   278	
   279	      {/* Evidence details */}
   280	      {isExpanded && candidate.evidence_groups.length > 0 && (
   281	        <div className="border-t border-slate-mid px-4 py-3 space-y-2">
   282	          <p className="text-xs text-text-muted font-medium uppercase tracking-wider">
   283	            Evidence
   284	          </p>
   285	          {candidate.evidence_groups.map((group, gi) => (
   286	            <EvidenceGroupCard key={gi} group={group} />
   287	          ))}
   288	          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-mid/50">
   289	            <Info className="w-3.5 h-3.5 text-text-muted" />
   290	            <p className="text-xs text-text-muted">
   291	              Score: {(candidate.confidence * 100).toFixed(0)}% (Tier {candidate.tier})
   292	            </p>
   293	          </div>
   294	        </div>
   295	      )}
   296	    </div>
   297	  )
   298	}
   299	
   300	function EvidenceGroupCard({ group }: { group: EvidenceGroupInfo }) {
   301	  return (
   302	    <div className="pl-3 border-l-2 border-slate-mid/50">
   303	      <p className="text-xs text-text-muted font-mono">{group.provenance}</p>
   304	      {group.items.map((item, i) => (
   305	        <div key={i} className="mt-1">
   306	          <p className="text-xs text-text-primary">{item.description}</p>
   307	          <p className="text-xs text-text-muted">
   308	            {item.source} &mdash; {(item.confidence * 100).toFixed(0)}%
   309	          </p>
   310	        </div>
   311	      ))}
   312	    </div>
   313	  )
   314	}
   315	
   316	// =============================================================================
   317	// Main Component
   318	// =============================================================================
   319	
   320	export function DependencyResolverModal({
   321	  isOpen,
   322	  onClose,
   323	  packName,
   324	  depId,
   325	  depName,
   326	  kind,
   327	  baseModelHint,
   328	  candidates,
   329	  isSuggesting,
   330	  requestId: _requestId,
   331	  onSuggest,
   332	  onApply,
   333	  onApplyAndDownload,
   334	  isApplying,
   335	  avatarAvailable,
   336	}: DependencyResolverModalProps) {
   337	  const { t } = useTranslation()
   338	
   339	  // Tab state
   340	  const [tab, setTab] = useState<ResolverTab>('candidates')
   341	  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
   342	  const [expandedCandidateId, setExpandedCandidateId] = useState<string | null>(null)
   343	  const [isAiSearching, setIsAiSearching] = useState(false)
   344	
   345	  // Build tabs list
   346	  const tabs: TabDef[] = [
   347	    { id: 'candidates', label: 'Candidates', icon: <Search className="w-4 h-4" />, visible: true },
   348	    { id: 'preview', label: 'Preview', icon: <Image className="w-4 h-4" />, visible: true },
   349	    { id: 'local', label: 'Local File', icon: <HardDrive className="w-4 h-4" />, visible: true },
   350	    { id: 'ai-resolve', label: 'AI Resolve', icon: <Sparkles className="w-4 h-4" />, visible: avatarAvailable },
   351	    { id: 'civitai', label: 'Civitai', icon: <Globe className="w-4 h-4" />, visible: true },
   352	    { id: 'huggingface', label: 'HuggingFace', icon: <Database className="w-4 h-4" />, visible: HF_ELIGIBLE_KINDS.has(kind) },
   353	  ]
   354	  const visibleTabs = tabs.filter((t) => t.visible)
   355	
   356	  // Reset when modal opens
   357	  useEffect(() => {
   358	    if (isOpen) {
   359	      setTab(getDefaultTab(candidates, avatarAvailable))
   360	      setSelectedCandidateId(null)
   361	      setExpandedCandidateId(null)
   362	      setIsAiSearching(false)
   363	    }
   364	  }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps
   365	
   366	  // Auto-select top candidate if TIER-1/2
   367	  useEffect(() => {
   368	    if (candidates.length > 0 && candidates[0].tier <= 2) {
   369	      setSelectedCandidateId(candidates[0].candidate_id)
   370	    }
   371	  }, [candidates])
   372	
   373	  const handleAiResolve = useCallback(async () => {
   374	    setIsAiSearching(true)
   375	    try {
   376	      const result = await onSuggest({ include_ai: true })
   377	      if (result.candidates.length > 0) {
   378	        setTab('candidates')
   379	      }
   380	    } catch {
   381	      // Error toast handled by mutation onError
   382	    } finally {
   383	      setIsAiSearching(false)
   384	    }
   385	  }, [onSuggest])
   386	
   387	  const selectedCandidate = candidates.find((c) => c.candidate_id === selectedCandidateId)
   388	
   389	  if (!isOpen) return null
   390	
   391	  return (
   392	    <div
   393	      className={clsx(
   394	        'fixed inset-0 bg-black/80 backdrop-blur-sm z-50',
   395	        'flex items-center justify-center p-4',
   396	        ANIMATION_PRESETS.fadeIn
   397	      )}
   398	      onClick={(e) => {
   399	        if (e.target === e.currentTarget) onClose()
   400	      }}
   401	    >
   402	      <div
   403	        className={clsx(
   404	          'bg-slate-deep border border-slate-mid rounded-2xl',
   405	          'max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col',
   406	          'shadow-2xl',
   407	          ANIMATION_PRESETS.scaleIn
   408	        )}
   409	        onClick={(e) => e.stopPropagation()}
   410	      >
   411	        {/* Header */}
   412	        <div className="border-b border-slate-mid p-4">
   413	          <div className="flex items-center justify-between">
   414	            <div className="flex items-center gap-3">
   415	              <div className="p-2 rounded-lg bg-synapse/15">
   416	                <Search className="w-5 h-5 text-synapse" />
   417	              </div>
   418	              <div>
   419	                <h2 className="text-lg font-bold text-text-primary">
   420	                  {t('pack.resolve.title', 'Resolve Dependency')}
   421	                </h2>
   422	                <p className="text-sm text-text-muted">
   423	                  {depName}
   424	                  {baseModelHint && (
   425	                    <span className="ml-2 text-synapse font-mono text-xs">
   426	                      {baseModelHint}
   427	                    </span>
   428	                  )}
   429	                </p>
   430	              </div>
   431	            </div>
   432	            <button
   433	              onClick={onClose}
   434	              className="p-2 hover:bg-slate-dark/50 rounded-lg transition-colors"
   435	            >
   436	              <X className="w-5 h-5 text-text-muted" />
   437	            </button>
   438	          </div>
   439	        </div>
   440	
   441	        {/* Tabs */}
   442	        <div className="flex border-b border-slate-mid overflow-x-auto">
   443	          {visibleTabs.map((tabDef) => (
   444	            <TabButton
   445	              key={tabDef.id}
   446	              tab={tabDef.id}
   447	              currentTab={tab}
   448	              onClick={() => setTab(tabDef.id)}
   449	              icon={tabDef.icon}
   450	              label={tabDef.label}
   451	              badge={tabDef.id === 'candidates' ? candidates.length : undefined}
   452	            />
   453	          ))}
   454	        </div>
   455	
   456	        {/* Content */}
   457	        <div className="flex-1 overflow-y-auto p-4">
   458	          {/* Candidates Tab */}
   459	          {tab === 'candidates' && (
   460	            <div className="space-y-2">
   461	              {isSuggesting ? (
   462	                <div className="flex flex-col items-center justify-center py-12 gap-3">
   463	                  <Loader2 className="w-8 h-8 animate-spin text-synapse" />
   464	                  <p className="text-sm text-text-muted">
   465	                    {t('pack.resolve.searching', 'Searching for matches...')}
   466	                  </p>
   467	                </div>
   468	              ) : candidates.length === 0 ? (
   469	                <div className="flex flex-col items-center justify-center py-12 gap-3">
   470	                  <Search className="w-10 h-10 text-text-muted/50" />
   471	                  <p className="text-text-muted text-center">
   472	                    {t('pack.resolve.noCandidates', 'No candidates found.')}
   473	                  </p>
   474	                  {avatarAvailable && (
   475	                    <Button onClick={handleAiResolve} disabled={isAiSearching}>
   476	                      {isAiSearching ? (
   477	                        <Loader2 className="w-4 h-4 animate-spin" />
   478	                      ) : (
   479	                        <Sparkles className="w-4 h-4" />
   480	                      )}
   481	                      {t('pack.resolve.tryAi', 'Try AI Search')}
   482	                    </Button>
   483	                  )}
   484	                </div>
   485	              ) : (
   486	                candidates.map((candidate) => (
   487	                  <CandidateCard
   488	                    key={candidate.candidate_id}
   489	                    candidate={candidate}
   490	                    isSelected={selectedCandidateId === candidate.candidate_id}
   491	                    onSelect={() => setSelectedCandidateId(candidate.candidate_id)}
   492	                    isExpanded={expandedCandidateId === candidate.candidate_id}
   493	                    onToggleExpand={() =>
   494	                      setExpandedCandidateId(
   495	                        expandedCandidateId === candidate.candidate_id
   496	                          ? null
   497	                          : candidate.candidate_id
   498	                      )
   499	                    }
   500	                  />
   501	                ))
   502	              )}
   503	            </div>
   504	          )}
   505	
   506	          {/* Preview Analysis Tab */}
   507	          {tab === 'preview' && (
   508	            <PreviewAnalysisTab
   509	              packName={packName}
   510	              depKind={kind}
   511	              candidates={candidates}
   512	              onSelectCandidate={(candidateId) => {
   513	                setSelectedCandidateId(candidateId)
   514	                setTab('candidates')
   515	              }}
   516	            />
   517	          )}
   518	
   519	          {/* Local File Tab */}
   520	          {tab === 'local' && (
   521	            <LocalResolveTab
   522	              packName={packName}
   523	              depId={depId}
   524	              depName={depName}
   525	              kind={kind}
   526	              onResolved={onClose}
   527	            />
   528	          )}
   529	
   530	          {/* AI Resolve Tab */}
   531	          {tab === 'ai-resolve' && (
   532	            <div className="flex flex-col items-center justify-center py-12 gap-4">
   533	              <div className="p-4 rounded-2xl bg-gradient-to-br from-synapse/20 to-pulse/10 border border-synapse/30">
   534	                <Sparkles className="w-10 h-10 text-synapse" />
   535	              </div>
   536	              <div className="text-center max-w-md">
   537	                <h3 className="text-text-primary font-semibold mb-2">
   538	                  {t('pack.resolve.aiTitle', 'AI-Powered Search')}
   539	                </h3>
   540	                <p className="text-sm text-text-muted">
   541	                  {t(
   542	                    'pack.resolve.aiDescription',
   543	                    'AI will search Civitai and HuggingFace to find the best matching model for this dependency.'
   544	                  )}
   545	                </p>
   546	              </div>
   547	              <Button
   548	                onClick={handleAiResolve}
   549	                disabled={isAiSearching || isSuggesting}
   550	                className="px-8"
   551	              >
   552	                {isAiSearching ? (
   553	                  <>
   554	                    <Loader2 className="w-4 h-4 animate-spin" />
   555	                    {t('pack.resolve.aiSearching', 'Searching...')}
   556	                  </>
   557	                ) : (
   558	                  <>
   559	                    <Sparkles className="w-4 h-4" />
   560	                    {t('pack.resolve.aiSearch', 'Search with AI')}

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx | nl -ba | sed -n '560,760p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   560	                    {t('pack.resolve.aiSearch', 'Search with AI')}
   561	                  </>
   562	                )}
   563	              </Button>
   564	              {isAiSearching && (
   565	                <p className="text-xs text-text-muted">
   566	                  {t('pack.resolve.aiNote', 'This may take up to 30 seconds...')}
   567	                </p>
   568	              )}
   569	            </div>
   570	          )}
   571	
   572	          {/* Civitai Tab */}
   573	          {tab === 'civitai' && (
   574	            <div className="flex flex-col items-center justify-center py-12 gap-3">
   575	              <Globe className="w-10 h-10 text-text-muted/50" />
   576	              <p className="text-text-muted text-center">
   577	                {t(
   578	                  'pack.resolve.civitaiPlaceholder',
   579	                  'Manual Civitai search coming in Phase 4.'
   580	                )}
   581	              </p>
   582	              <p className="text-xs text-text-muted">
   583	                {t(
   584	                  'pack.resolve.useAiInstead',
   585	                  'Use AI Resolve for automated Civitai search.'
   586	                )}
   587	              </p>
   588	            </div>
   589	          )}
   590	
   591	          {/* HuggingFace Tab */}
   592	          {tab === 'huggingface' && (
   593	            <div className="flex flex-col items-center justify-center py-12 gap-3">
   594	              <Database className="w-10 h-10 text-text-muted/50" />
   595	              <p className="text-text-muted text-center">
   596	                {t(
   597	                  'pack.resolve.hfPlaceholder',
   598	                  'Manual HuggingFace search coming in Phase 4.'
   599	                )}
   600	              </p>
   601	              <p className="text-xs text-text-muted">
   602	                {t(
   603	                  'pack.resolve.useAiInstead',
   604	                  'Use AI Resolve for automated HuggingFace search.'
   605	                )}
   606	              </p>
   607	            </div>
   608	          )}
   609	        </div>
   610	
   611	        {/* Footer */}
   612	        <div className="p-4 border-t border-slate-mid bg-slate-dark/50 flex gap-3">
   613	          <Button variant="secondary" onClick={onClose} className="flex-1">
   614	            {t('common.cancel', 'Cancel')}
   615	          </Button>
   616	          <Button
   617	            onClick={() => selectedCandidate && onApply(selectedCandidate.candidate_id)}
   618	            disabled={!selectedCandidate || isApplying}
   619	            variant="secondary"
   620	            className="flex-1"
   621	          >
   622	            {isApplying ? (
   623	              <Loader2 className="w-4 h-4 animate-spin" />
   624	            ) : (
   625	              <>
   626	                <Check className="w-4 h-4" />
   627	                {t('pack.resolve.apply', 'Apply')}
   628	              </>
   629	            )}
   630	          </Button>
   631	          <Button
   632	            onClick={() =>
   633	              selectedCandidate && onApplyAndDownload(selectedCandidate.candidate_id)
   634	            }
   635	            disabled={!selectedCandidate || isApplying}
   636	            className="flex-1"
   637	          >
   638	            {isApplying ? (
   639	              <Loader2 className="w-4 h-4 animate-spin" />
   640	            ) : (
   641	              <>
   642	                <Download className="w-4 h-4" />
   643	                {t('pack.resolve.applyDownload', 'Apply & Download')}
   644	              </>
   645	            )}
   646	          </Button>
   647	        </div>
   648	      </div>
   649	    </div>
   650	  )
   651	}
   652	
   653	export default DependencyResolverModal

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * LocalResolveTab — Import local model files to resolve dependencies.
     3	 *
     4	 * Three scenarios:
     5	 * A) Dep has known remote source → recommend matching files
     6	 * B) Unknown file → hash → Civitai/HF lookup → enrich
     7	 * C) No remote match → filename search → fallback
     8	 *
     9	 * UX states:
    10	 * 1. Directory input (with recent paths from localStorage)
    11	 * 2. File listing with recommendations
    12	 * 3. Import progress (hash → copy → enrich → apply)
    13	 * 4. Success / error result
    14	 */
    15	
    16	import { useState, useEffect, useCallback, useRef } from 'react'
    17	import {
    18	  FolderOpen,
    19	  Loader2,
    20	  Check,
    21	  Star,
    22	  FileBox,
    23	  ArrowRight,
    24	  Clock,
    25	  AlertTriangle,
    26	  CheckCircle2,
    27	  XCircle,
    28	  HardDrive,
    29	  Sparkles,
    30	  Link2,
    31	} from 'lucide-react'
    32	import { clsx } from 'clsx'
    33	import { Button } from '@/components/ui/Button'
    34	import { formatSize } from '../utils'
    35	import type {
    36	  LocalFileInfo,
    37	  FileRecommendation,
    38	  LocalImportStatus,
    39	} from '../types'
    40	import { ANIMATION_PRESETS } from '../constants'
    41	
    42	// =============================================================================
    43	// Types
    44	// =============================================================================
    45	
    46	interface LocalResolveTabProps {
    47	  packName: string
    48	  depId: string
    49	  depName?: string
    50	  kind?: string
    51	  /** Known SHA256 (for Scenario A recommendations) */
    52	  expectedSha256?: string
    53	  /** Known filename (for Scenario A recommendations) */
    54	  expectedFilename?: string
    55	  /** Called when import completes successfully */
    56	  onResolved: () => void
    57	}
    58	
    59	type TabState = 'browse' | 'importing' | 'success' | 'error'
    60	
    61	const RECENT_PATHS_KEY = 'synapse:local-resolve:recent-paths'
    62	const MAX_RECENT_PATHS = 5
    63	
    64	const STAGE_LABELS: Record<string, string> = {
    65	  hashing: 'Computing SHA256 hash...',
    66	  copying: 'Copying to blob store...',
    67	  enriching: 'Looking up metadata...',
    68	  applying: 'Applying resolution...',
    69	}
    70	
    71	// =============================================================================
    72	// Helpers
    73	// =============================================================================
    74	
    75	function getRecentPaths(): string[] {
    76	  try {
    77	    return JSON.parse(localStorage.getItem(RECENT_PATHS_KEY) || '[]')
    78	  } catch {
    79	    return []
    80	  }
    81	}
    82	
    83	function addRecentPath(path: string) {
    84	  const paths = getRecentPaths().filter((p) => p !== path)
    85	  paths.unshift(path)
    86	  localStorage.setItem(
    87	    RECENT_PATHS_KEY,
    88	    JSON.stringify(paths.slice(0, MAX_RECENT_PATHS))
    89	  )
    90	}
    91	
    92	function formatDate(mtime: number): string {
    93	  return new Date(mtime * 1000).toLocaleDateString(undefined, {
    94	    year: 'numeric',
    95	    month: 'short',
    96	    day: 'numeric',
    97	  })
    98	}
    99	
   100	function matchTypeIcon(type: string) {
   101	  switch (type) {
   102	    case 'sha256_exact':
   103	      return <CheckCircle2 className="w-4 h-4 text-green-400" />
   104	    case 'filename_exact':
   105	      return <Check className="w-4 h-4 text-blue-400" />
   106	    case 'filename_stem':
   107	      return <Star className="w-4 h-4 text-amber-400" />
   108	    default:
   109	      return <FileBox className="w-4 h-4 text-text-muted" />
   110	  }
   111	}
   112	
   113	function matchTypeBadge(type: string): { label: string; color: string } | null {
   114	  switch (type) {
   115	    case 'sha256_exact':
   116	      return { label: 'Hash match', color: 'bg-green-500/15 text-green-400 border-green-500/30' }
   117	    case 'filename_exact':
   118	      return { label: 'Name match', color: 'bg-blue-500/15 text-blue-400 border-blue-500/30' }
   119	    case 'filename_stem':
   120	      return { label: 'Similar', color: 'bg-amber-500/15 text-amber-400 border-amber-500/30' }
   121	    default:
   122	      return null
   123	  }
   124	}
   125	
   126	// =============================================================================
   127	// Component
   128	// =============================================================================
   129	
   130	export function LocalResolveTab(props: LocalResolveTabProps) {
   131	  const { packName, depId, onResolved } = props
   132	  const [tabState, setTabState] = useState<TabState>('browse')
   133	  const [directoryPath, setDirectoryPath] = useState('')
   134	  const [recommendations, setRecommendations] = useState<FileRecommendation[]>([])
   135	  const [selectedFile, setSelectedFile] = useState<LocalFileInfo | null>(null)
   136	  const [isLoading, setIsLoading] = useState(false)
   137	  const [browseError, setBrowseError] = useState<string | null>(null)
   138	  const [importStatus, setImportStatus] = useState<LocalImportStatus | null>(null)
   139	  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
   140	  const inputRef = useRef<HTMLInputElement>(null)
   141	
   142	  // Cleanup polling on unmount
   143	  useEffect(() => {
   144	    return () => {
   145	      if (pollRef.current) clearInterval(pollRef.current)
   146	    }
   147	  }, [])
   148	
   149	  // --- Browse directory ---
   150	  const handleBrowse = useCallback(async (path?: string) => {
   151	    const dirPath = path || directoryPath.trim()
   152	    if (!dirPath) return
   153	
   154	    setIsLoading(true)
   155	    setBrowseError(null)
   156	    setRecommendations([])
   157	    setSelectedFile(null)
   158	
   159	    try {
   160	      // Use recommend endpoint if we have dep context
   161	      const url = `/api/packs/${encodeURIComponent(packName)}/recommend-local?dep_id=${encodeURIComponent(depId)}&directory=${encodeURIComponent(dirPath)}`
   162	      const res = await fetch(url)
   163	
   164	      if (!res.ok) {
   165	        const err = await res.json().catch(() => ({ detail: res.statusText }))
   166	        throw new Error(err.detail || 'Failed to browse directory')
   167	      }
   168	
   169	      const data = await res.json()
   170	      const recs: FileRecommendation[] = data.recommendations || []
   171	      setRecommendations(recs)
   172	
   173	      if (recs.length === 0) {
   174	        setBrowseError('No model files found in this directory.')
   175	      }
   176	
   177	      // Auto-select top recommendation if high confidence
   178	      if (recs.length > 0 && recs[0].confidence >= 0.85) {
   179	        setSelectedFile(recs[0].file)
   180	      }
   181	
   182	      // Save to recent paths
   183	      addRecentPath(dirPath)
   184	      if (!path) setDirectoryPath(dirPath)
   185	    } catch (e) {
   186	      setBrowseError(e instanceof Error ? e.message : 'Unknown error')
   187	    } finally {
   188	      setIsLoading(false)
   189	    }
   190	  }, [directoryPath, packName, depId])
   191	
   192	  // --- Import file ---
   193	  const handleImport = useCallback(async () => {
   194	    if (!selectedFile) return
   195	
   196	    // Clear any stale polling interval (e.g., double-click)
   197	    if (pollRef.current) {
   198	      clearInterval(pollRef.current)
   199	      pollRef.current = null
   200	    }
   201	
   202	    setTabState('importing')
   203	    setImportStatus(null)
   204	
   205	    try {
   206	      const res = await fetch(
   207	        `/api/packs/${encodeURIComponent(packName)}/import-local`,
   208	        {
   209	          method: 'POST',
   210	          headers: { 'Content-Type': 'application/json' },
   211	          body: JSON.stringify({
   212	            dep_id: depId,
   213	            file_path: selectedFile.path,
   214	          }),
   215	        }
   216	      )
   217	
   218	      if (!res.ok) {
   219	        const err = await res.json().catch(() => ({ detail: res.statusText }))
   220	        throw new Error(err.detail || 'Failed to start import')
   221	      }
   222	
   223	      const data = await res.json()
   224	      const importId = data.import_id
   225	
   226	      // Start polling for progress
   227	      setImportStatus({
   228	        ...data,
   229	        status: 'pending',
   230	        stage: '',
   231	        progress: 0,
   232	        result: null,
   233	      })
   234	
   235	      pollRef.current = setInterval(async () => {  // 1s interval — large file ops take minutes
   236	        try {
   237	          const statusRes = await fetch(`/api/store/imports/${importId}`)
   238	          if (statusRes.status === 404) {
   239	            // Import lost (e.g., server restart) — stop polling
   240	            if (pollRef.current) clearInterval(pollRef.current)
   241	            pollRef.current = null
   242	            setTabState('error')
   243	            setImportStatus((prev) => prev ? {
   244	              ...prev,
   245	              status: 'failed',
   246	              result: { success: false, message: 'Import session lost. Please try again.' },
   247	            } : null)
   248	            return
   249	          }
   250	          if (!statusRes.ok) return
   251	
   252	          const status: LocalImportStatus = await statusRes.json()
   253	          setImportStatus(status)
   254	
   255	          if (status.status === 'completed' || status.status === 'failed') {
   256	            if (pollRef.current) clearInterval(pollRef.current)
   257	            pollRef.current = null
   258	
   259	            if (status.status === 'completed' && status.result?.success) {
   260	              setTabState('success')

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx | nl -ba | sed -n '260,560p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	              setTabState('success')
   261	              onResolved()
   262	            } else {
   263	              setTabState('error')
   264	            }
   265	          }
   266	        } catch {
   267	          // Silent retry
   268	        }
   269	      }, 1000)
   270	    } catch (e) {
   271	      setTabState('error')
   272	      setImportStatus({
   273	        import_id: '',
   274	        pack_name: packName,
   275	        dep_id: depId,
   276	        filename: selectedFile.name,
   277	        file_size: selectedFile.size,
   278	        status: 'failed',
   279	        stage: '',
   280	        progress: 0,
   281	        result: {
   282	          success: false,
   283	          message: e instanceof Error ? e.message : 'Unknown error',
   284	        },
   285	      })
   286	    }
   287	  }, [selectedFile, packName, depId, onResolved])
   288	
   289	  const handleReset = useCallback(() => {
   290	    setTabState('browse')
   291	    setImportStatus(null)
   292	    setSelectedFile(null)
   293	  }, [])
   294	
   295	  // --- Render ---
   296	
   297	  // State: Importing
   298	  if (tabState === 'importing' && importStatus) {
   299	    return (
   300	      <div className={clsx('flex flex-col items-center py-10 gap-6', ANIMATION_PRESETS.fadeIn)}>
   301	        <div className="p-4 rounded-2xl bg-synapse/10 border border-synapse/20">
   302	          <HardDrive className="w-10 h-10 text-synapse animate-pulse" />
   303	        </div>
   304	
   305	        <div className="text-center w-full max-w-sm">
   306	          <h3 className="text-text-primary font-semibold mb-1">
   307	            Importing {importStatus.filename}
   308	          </h3>
   309	          <p className="text-xs text-text-muted mb-4">
   310	            {formatSize(importStatus.file_size)}
   311	          </p>
   312	
   313	          {/* Progress bar */}
   314	          <div className="w-full bg-slate-dark rounded-full h-2.5 mb-2 overflow-hidden border border-slate-mid/30">
   315	            <div
   316	              className="h-full rounded-full bg-gradient-to-r from-synapse to-pulse transition-all duration-300 ease-out"
   317	              style={{ width: `${Math.round(importStatus.progress * 100)}%` }}
   318	            />
   319	          </div>
   320	
   321	          <div className="flex justify-between text-xs">
   322	            <span className="text-text-muted">
   323	              {STAGE_LABELS[importStatus.stage] || 'Preparing...'}
   324	            </span>
   325	            <span className="text-synapse font-mono">
   326	              {Math.round(importStatus.progress * 100)}%
   327	            </span>
   328	          </div>
   329	
   330	          {/* Stage indicators */}
   331	          <div className="mt-6 space-y-2">
   332	            {['hashing', 'copying', 'enriching', 'applying'].map((stage) => {
   333	              const current = importStatus.stage
   334	              const stages = ['hashing', 'copying', 'enriching', 'applying']
   335	              const currentIdx = stages.indexOf(current)
   336	              const stageIdx = stages.indexOf(stage)
   337	              const isDone = stageIdx < currentIdx
   338	              const isCurrent = stage === current
   339	              const isPending = stageIdx > currentIdx
   340	
   341	              return (
   342	                <div key={stage} className="flex items-center gap-3 text-sm">
   343	                  {isDone ? (
   344	                    <Check className="w-4 h-4 text-green-400 flex-shrink-0" />
   345	                  ) : isCurrent ? (
   346	                    <Loader2 className="w-4 h-4 text-synapse animate-spin flex-shrink-0" />
   347	                  ) : (
   348	                    <div className="w-4 h-4 rounded-full border border-slate-mid flex-shrink-0" />
   349	                  )}
   350	                  <span
   351	                    className={clsx(
   352	                      isDone && 'text-text-muted line-through',
   353	                      isCurrent && 'text-text-primary font-medium',
   354	                      isPending && 'text-text-muted/50'
   355	                    )}
   356	                  >
   357	                    {STAGE_LABELS[stage]}
   358	                  </span>
   359	                </div>
   360	              )
   361	            })}
   362	          </div>
   363	        </div>
   364	      </div>
   365	    )
   366	  }
   367	
   368	  // State: Success
   369	  if (tabState === 'success' && importStatus?.result) {
   370	    const result = importStatus.result
   371	    return (
   372	      <div className={clsx('flex flex-col items-center py-10 gap-5', ANIMATION_PRESETS.fadeIn)}>
   373	        <div className="p-4 rounded-2xl bg-green-500/10 border border-green-500/20">
   374	          <CheckCircle2 className="w-10 h-10 text-green-400" />
   375	        </div>
   376	
   377	        <div className="text-center max-w-sm">
   378	          <h3 className="text-text-primary font-semibold mb-1">
   379	            Successfully imported!
   380	          </h3>
   381	          <p className="text-sm text-text-muted">
   382	            {result.display_name || importStatus.filename}
   383	          </p>
   384	        </div>
   385	
   386	        {/* Details card */}
   387	        <div className="w-full max-w-sm bg-slate-dark/80 rounded-xl border border-slate-mid/50 p-4 space-y-3">
   388	          {result.sha256 && (
   389	            <div className="flex justify-between text-xs">
   390	              <span className="text-text-muted">SHA256</span>
   391	              <span className="text-text-primary font-mono">{result.sha256.slice(0, 16)}...</span>
   392	            </div>
   393	          )}
   394	          {result.file_size && (
   395	            <div className="flex justify-between text-xs">
   396	              <span className="text-text-muted">Size</span>
   397	              <span className="text-text-primary">{formatSize(result.file_size)}</span>
   398	            </div>
   399	          )}
   400	
   401	          {/* Enrichment info */}
   402	          {result.enrichment_source && result.enrichment_source !== 'filename_only' && (
   403	            <div className="pt-2 border-t border-slate-mid/30">
   404	              <div className="flex items-center gap-2 mb-2">
   405	                <Link2 className="w-3.5 h-3.5 text-synapse" />
   406	                <span className="text-xs font-medium text-synapse">Enrichment</span>
   407	              </div>
   408	              <p className="text-xs text-text-muted">
   409	                {result.enrichment_source === 'civitai_hash' && (
   410	                  <>Found on Civitai via hash match. Canonical source saved for updates.</>
   411	                )}
   412	                {result.enrichment_source === 'civitai_name' && (
   413	                  <>Found on Civitai via name search. Canonical source saved for updates.</>
   414	                )}
   415	                {result.enrichment_source === 'huggingface' && (
   416	                  <>Found on HuggingFace. Canonical source saved for updates.</>
   417	                )}
   418	              </p>
   419	            </div>
   420	          )}
   421	
   422	          {result.enrichment_source === 'filename_only' && (
   423	            <div className="pt-2 border-t border-slate-mid/30">
   424	              <div className="flex items-center gap-2">
   425	                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
   426	                <span className="text-xs text-amber-400">
   427	                  No remote source found — updates won't be tracked
   428	                </span>
   429	              </div>
   430	            </div>
   431	          )}
   432	        </div>
   433	
   434	        <Button variant="secondary" onClick={handleReset} size="sm">
   435	          Import another file
   436	        </Button>
   437	      </div>
   438	    )
   439	  }
   440	
   441	  // State: Error
   442	  if (tabState === 'error') {
   443	    const errorMsg = importStatus?.result?.message || 'Import failed'
   444	    return (
   445	      <div className={clsx('flex flex-col items-center py-10 gap-5', ANIMATION_PRESETS.fadeIn)}>
   446	        <div className="p-4 rounded-2xl bg-error/10 border border-error/20">
   447	          <XCircle className="w-10 h-10 text-error" />
   448	        </div>
   449	
   450	        <div className="text-center max-w-sm">
   451	          <h3 className="text-text-primary font-semibold mb-1">Import failed</h3>
   452	          <p className="text-sm text-error/80">{errorMsg}</p>
   453	        </div>
   454	
   455	        <Button variant="secondary" onClick={handleReset} size="sm">
   456	          Try again
   457	        </Button>
   458	      </div>
   459	    )
   460	  }
   461	
   462	  // State: Browse (default)
   463	  const recentPaths = getRecentPaths()
   464	  const hasRecommendations = recommendations.length > 0
   465	  const topMatch = hasRecommendations ? recommendations[0] : null
   466	  const hasTopMatch = topMatch && topMatch.confidence >= 0.6
   467	
   468	  return (
   469	    <div className={clsx('space-y-4', ANIMATION_PRESETS.fadeIn)}>
   470	      {/* Directory input */}
   471	      <div>
   472	        <label className="block text-xs font-medium text-text-muted mb-2">
   473	          Model directory
   474	        </label>
   475	        <div className="flex gap-2">
   476	          <input
   477	            ref={inputRef}
   478	            type="text"
   479	            value={directoryPath}
   480	            onChange={(e) => setDirectoryPath(e.target.value)}
   481	            onKeyDown={(e) => {
   482	              if (e.key === 'Enter') handleBrowse()
   483	            }}
   484	            placeholder="/home/user/models/checkpoints"
   485	            className={clsx(
   486	              'flex-1 px-4 py-2.5 rounded-xl text-sm',
   487	              'bg-slate-dark border border-slate-mid/50',
   488	              'text-text-primary placeholder:text-text-muted/40',
   489	              'focus:outline-none focus:border-synapse/50 focus:ring-1 focus:ring-synapse/30',
   490	              'transition-all duration-200'
   491	            )}
   492	          />
   493	          <Button
   494	            onClick={() => handleBrowse()}
   495	            disabled={!directoryPath.trim() || isLoading}
   496	            isLoading={isLoading}
   497	            variant="secondary"
   498	          >
   499	            <FolderOpen className="w-4 h-4" />
   500	            Browse
   501	          </Button>
   502	        </div>
   503	      </div>
   504	
   505	      {/* Recent paths */}
   506	      {!hasRecommendations && recentPaths.length > 0 && (
   507	        <div>
   508	          <p className="text-xs text-text-muted mb-2 flex items-center gap-1.5">
   509	            <Clock className="w-3 h-3" />
   510	            Recent
   511	          </p>
   512	          <div className="flex flex-wrap gap-1.5">
   513	            {recentPaths.map((path) => (
   514	              <button
   515	                key={path}
   516	                onClick={() => {
   517	                  setDirectoryPath(path)
   518	                  handleBrowse(path)
   519	                }}
   520	                className={clsx(
   521	                  'px-3 py-1.5 rounded-lg text-xs',
   522	                  'bg-slate-dark/60 border border-slate-mid/30',
   523	                  'text-text-muted hover:text-text-primary hover:border-synapse/30',
   524	                  'transition-all duration-150 truncate max-w-[280px]'
   525	                )}
   526	                title={path}
   527	              >
   528	                {path}
   529	              </button>
   530	            ))}
   531	          </div>
   532	        </div>
   533	      )}
   534	
   535	      {/* Error */}
   536	      {browseError && (
   537	        <div className="flex items-start gap-2 p-3 rounded-xl bg-error/5 border border-error/20">
   538	          <AlertTriangle className="w-4 h-4 text-error flex-shrink-0 mt-0.5" />
   539	          <p className="text-sm text-error/80">{browseError}</p>
   540	        </div>
   541	      )}
   542	
   543	      {/* Recommended badge */}
   544	      {hasTopMatch && (
   545	        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-green-500/5 border border-green-500/20">
   546	          <Sparkles className="w-4 h-4 text-green-400" />
   547	          <p className="text-xs text-green-400">
   548	            <span className="font-medium">Recommended match found!</span>
   549	            {' '}
   550	            {topMatch!.reason}
   551	          </p>
   552	        </div>
   553	      )}
   554	
   555	      {/* File list */}
   556	      {hasRecommendations && (
   557	        <div className="space-y-1.5 max-h-[320px] overflow-y-auto pr-1">
   558	          {recommendations.map((rec) => {
   559	            const isSelected = selectedFile?.path === rec.file.path
   560	            const badge = matchTypeBadge(rec.match_type)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx | nl -ba | sed -n '560,760p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   560	            const badge = matchTypeBadge(rec.match_type)
   561	
   562	            return (
   563	              <button
   564	                key={rec.file.path}
   565	                onClick={() => setSelectedFile(rec.file)}
   566	                className={clsx(
   567	                  'w-full text-left p-3 rounded-xl',
   568	                  'transition-all duration-200',
   569	                  'flex items-center gap-3',
   570	                  isSelected
   571	                    ? 'bg-synapse/15 border-2 border-synapse shadow-sm shadow-synapse/10'
   572	                    : rec.confidence >= 0.6
   573	                      ? 'bg-slate-dark/80 border border-green-500/20 hover:border-synapse/30'
   574	                      : 'bg-slate-dark/50 border border-slate-mid/30 hover:border-slate-mid/50'
   575	                )}
   576	              >
   577	                {/* Match icon */}
   578	                <div className="flex-shrink-0">
   579	                  {matchTypeIcon(rec.match_type)}
   580	                </div>
   581	
   582	                {/* File info */}
   583	                <div className="min-w-0 flex-1">
   584	                  <div className="flex items-center gap-2">
   585	                    <p
   586	                      className={clsx(
   587	                        'font-medium truncate text-sm',
   588	                        isSelected ? 'text-synapse' : 'text-text-primary'
   589	                      )}
   590	                    >
   591	                      {rec.file.name}
   592	                    </p>
   593	                    {badge && (
   594	                      <span
   595	                        className={clsx(
   596	                          'px-1.5 py-0.5 rounded text-[10px] font-semibold border whitespace-nowrap',
   597	                          badge.color
   598	                        )}
   599	                      >
   600	                        {badge.label}
   601	                      </span>
   602	                    )}
   603	                  </div>
   604	                  <div className="flex items-center gap-3 mt-0.5">
   605	                    <span className="text-xs text-text-muted">
   606	                      {formatSize(rec.file.size)}
   607	                    </span>
   608	                    <span className="text-xs text-text-muted/50">
   609	                      {formatDate(rec.file.mtime)}
   610	                    </span>
   611	                    {rec.reason && rec.match_type !== 'none' && (
   612	                      <span className="text-xs text-text-muted/60 truncate">
   613	                        {rec.reason}
   614	                      </span>
   615	                    )}
   616	                  </div>
   617	                </div>
   618	
   619	                {/* Selection indicator */}
   620	                {isSelected && (
   621	                  <Check className="w-5 h-5 text-synapse flex-shrink-0" />
   622	                )}
   623	              </button>
   624	            )
   625	          })}
   626	        </div>
   627	      )}
   628	
   629	      {/* Import button */}
   630	      {hasRecommendations && (
   631	        <div className="flex justify-end pt-2">
   632	          <Button
   633	            onClick={handleImport}
   634	            disabled={!selectedFile}
   635	            className="min-w-[160px]"
   636	          >
   637	            <HardDrive className="w-4 h-4" />
   638	            Use This File
   639	            <ArrowRight className="w-4 h-4" />
   640	          </Button>
   641	        </div>
   642	      )}
   643	
   644	      {/* Empty state hint */}
   645	      {!hasRecommendations && !isLoading && !browseError && (
   646	        <div className="flex flex-col items-center py-8 gap-3">
   647	          <div className="p-3 rounded-2xl bg-slate-dark/60 border border-slate-mid/30">
   648	            <FolderOpen className="w-8 h-8 text-text-muted/40" />
   649	          </div>
   650	          <p className="text-sm text-text-muted text-center max-w-xs">
   651	            Enter a directory path where your model files are stored
   652	          </p>
   653	          <p className="text-xs text-text-muted/60 text-center">
   654	            Supports .safetensors, .ckpt, .pt, .bin, .onnx
   655	          </p>
   656	        </div>
   657	      )}
   658	    </div>
   659	  )
   660	}

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * PreviewAnalysisTab
     3	 *
     4	 * Shows preview images with extracted model hints and generation params.
     5	 * Part of DependencyResolverModal — replaces the former placeholder.
     6	 */
     7	
     8	import { useState, useMemo } from 'react'
     9	import { useTranslation } from 'react-i18next'
    10	import {
    11	  Loader2,
    12	  Image as ImageIcon,
    13	  Copy,
    14	  ArrowRight,
    15	  Hash,
    16	  Box,
    17	  Layers,
    18	  Hexagon,
    19	  AlertCircle,
    20	} from 'lucide-react'
    21	import { clsx } from 'clsx'
    22	import { toast } from '@/stores/toastStore'
    23	import { usePreviewAnalysis } from '../hooks/usePreviewAnalysis'
    24	import type {
    25	  AssetType,
    26	  PreviewAnalysisItem,
    27	  PreviewModelHintInfo,
    28	  ResolutionCandidate,
    29	} from '../types'
    30	
    31	// =============================================================================
    32	// Types
    33	// =============================================================================
    34	
    35	export interface PreviewAnalysisTabProps {
    36	  packName: string
    37	  depKind: AssetType
    38	  candidates: ResolutionCandidate[]
    39	  onSelectCandidate: (candidateId: string) => void
    40	}
    41	
    42	// =============================================================================
    43	// Kind display config
    44	// =============================================================================
    45	
    46	const KIND_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof Box }> = {
    47	  checkpoint: { label: 'Checkpoint', color: 'text-blue-400', bg: 'bg-blue-500/15', icon: Box },
    48	  lora: { label: 'LoRA', color: 'text-purple-400', bg: 'bg-purple-500/15', icon: Layers },
    49	  vae: { label: 'VAE', color: 'text-emerald-400', bg: 'bg-emerald-500/15', icon: Hexagon },
    50	  controlnet: { label: 'ControlNet', color: 'text-amber-400', bg: 'bg-amber-500/15', icon: Layers },
    51	  embedding: { label: 'Embedding', color: 'text-cyan-400', bg: 'bg-cyan-500/15', icon: Hash },
    52	  upscaler: { label: 'Upscaler', color: 'text-pink-400', bg: 'bg-pink-500/15', icon: Layers },
    53	}
    54	
    55	function getKindDisplay(kind: string | null) {
    56	  if (!kind) return { label: 'Unknown', color: 'text-text-muted', bg: 'bg-slate-mid/30', icon: AlertCircle }
    57	  return KIND_CONFIG[kind] || { label: kind, color: 'text-text-muted', bg: 'bg-slate-mid/30', icon: AlertCircle }
    58	}
    59	
    60	// =============================================================================
    61	// Sub-components
    62	// =============================================================================
    63	
    64	function PreviewThumbnail({
    65	  preview,
    66	  isSelected,
    67	  onClick,
    68	}: {
    69	  preview: PreviewAnalysisItem
    70	  isSelected: boolean
    71	  onClick: () => void
    72	}) {
    73	  const hintCount = preview.hints.length
    74	
    75	  return (
    76	    <button
    77	      onClick={onClick}
    78	      className={clsx(
    79	        'relative rounded-lg overflow-hidden aspect-square',
    80	        'transition-all duration-200 group',
    81	        isSelected
    82	          ? 'ring-2 ring-synapse ring-offset-1 ring-offset-slate-deep'
    83	          : 'ring-1 ring-slate-mid hover:ring-slate-mid/80'
    84	      )}
    85	    >
    86	      {preview.url ? (
    87	        <img
    88	          src={preview.thumbnail_url || preview.url}
    89	          alt={preview.filename}
    90	          className="w-full h-full object-cover"
    91	          loading="lazy"
    92	        />
    93	      ) : (
    94	        <div className="w-full h-full bg-slate-dark flex items-center justify-center">
    95	          <ImageIcon className="w-6 h-6 text-text-muted/30" />
    96	        </div>
    97	      )}
    98	
    99	      {/* Hint count badge */}
   100	      {hintCount > 0 && (
   101	        <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-synapse/90 text-white">
   102	          {hintCount}
   103	        </span>
   104	      )}
   105	
   106	      {/* Video indicator */}
   107	      {preview.media_type === 'video' && (
   108	        <span className="absolute bottom-1 left-1 px-1 py-0.5 rounded text-[9px] font-medium bg-black/60 text-white">
   109	          VIDEO
   110	        </span>
   111	      )}
   112	    </button>
   113	  )
   114	}
   115	
   116	function HintRow({
   117	  hint,
   118	  depKind,
   119	  onUse,
   120	  canUse,
   121	}: {
   122	  hint: PreviewModelHintInfo
   123	  depKind: AssetType
   124	  onUse: () => void
   125	  canUse: boolean
   126	}) {
   127	  const display = getKindDisplay(hint.kind)
   128	  const KindIcon = display.icon
   129	  const isMatchingKind = hint.kind === depKind || hint.kind === null
   130	  const dimmed = !hint.resolvable
   131	
   132	  return (
   133	    <div
   134	      className={clsx(
   135	        'flex items-center gap-2 py-1.5 px-2 rounded-md',
   136	        dimmed ? 'opacity-50' : 'hover:bg-slate-mid/20'
   137	      )}
   138	    >
   139	      <KindIcon className={clsx('w-3.5 h-3.5 flex-shrink-0', display.color)} />
   140	      <span className="text-sm text-text-primary truncate flex-1 font-mono" title={hint.raw_value}>
   141	        {hint.filename}
   142	      </span>
   143	
   144	      {/* Kind badge */}
   145	      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-medium', display.bg, display.color)}>
   146	        {display.label}
   147	      </span>
   148	
   149	      {/* Hash */}
   150	      {hint.hash && (
   151	        <span className="text-[10px] text-text-muted font-mono" title={`Hash: ${hint.hash}`}>
   152	          {hint.hash.slice(0, 8)}
   153	        </span>
   154	      )}
   155	
   156	      {/* Weight */}
   157	      {hint.weight != null && (
   158	        <span className="text-[10px] text-text-muted">
   159	          w:{hint.weight}
   160	        </span>
   161	      )}
   162	
   163	      {/* Use button */}
   164	      {isMatchingKind && canUse && !dimmed && (
   165	        <button
   166	          onClick={onUse}
   167	          className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-synapse hover:bg-synapse/10 transition-colors"
   168	          title="Use this model reference"
   169	        >
   170	          Use
   171	          <ArrowRight className="w-3 h-3" />
   172	        </button>
   173	      )}
   174	
   175	      {dimmed && (
   176	        <span className="text-[10px] text-text-muted italic">unresolvable</span>
   177	      )}
   178	    </div>
   179	  )
   180	}
   181	
   182	function GenerationParamsDisplay({ params }: { params: Record<string, any> }) {
   183	  const { t } = useTranslation()
   184	
   185	  // Key display items
   186	  const items: [string, string | number][] = []
   187	  if (params.sampler) items.push(['Sampler', params.sampler])
   188	  if (params.steps) items.push(['Steps', params.steps])
   189	  if (params.cfgScale || params.cfg_scale) items.push(['CFG', params.cfgScale || params.cfg_scale])
   190	  if (params.seed) items.push(['Seed', params.seed])
   191	  if (params.Size) items.push(['Size', params.Size])
   192	  if (params['Clip skip']) items.push(['Clip skip', params['Clip skip']])
   193	  if (params['Denoising strength']) items.push(['Denoise', params['Denoising strength']])
   194	
   195	  const prompt = params.prompt
   196	  const negativePrompt = params.negativePrompt || params.negative_prompt
   197	
   198	  const handleCopyPrompt = () => {
   199	    if (prompt) {
   200	      navigator.clipboard.writeText(prompt).then(
   201	        () => toast.success(t('common.copied', 'Copied to clipboard')),
   202	        () => toast.error(t('common.copyFailed', 'Failed to copy'))
   203	      )
   204	    }
   205	  }
   206	
   207	  return (
   208	    <div className="space-y-2">
   209	      {/* Param grid */}
   210	      {items.length > 0 && (
   211	        <div className="flex flex-wrap gap-x-4 gap-y-1">
   212	          {items.map(([label, value]) => (
   213	            <span key={label} className="text-xs">
   214	              <span className="text-text-muted">{label}:</span>{' '}
   215	              <span className="text-text-primary font-mono">{String(value)}</span>
   216	            </span>
   217	          ))}
   218	        </div>
   219	      )}
   220	
   221	      {/* Prompt */}
   222	      {prompt && (
   223	        <div className="mt-2">
   224	          <div className="flex items-center justify-between mb-1">
   225	            <span className="text-xs text-text-muted font-medium">Prompt</span>
   226	            <button
   227	              onClick={handleCopyPrompt}
   228	              className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
   229	            >
   230	              <Copy className="w-3 h-3" />
   231	              Copy
   232	            </button>
   233	          </div>
   234	          <p className="text-xs text-text-primary/80 line-clamp-3 font-mono bg-slate-dark/50 rounded px-2 py-1.5">
   235	            {prompt}
   236	          </p>
   237	        </div>
   238	      )}
   239	
   240	      {/* Negative prompt */}
   241	      {negativePrompt && (
   242	        <div>
   243	          <span className="text-xs text-text-muted font-medium">Negative</span>
   244	          <p className="text-xs text-text-muted/70 line-clamp-2 font-mono bg-slate-dark/50 rounded px-2 py-1 mt-0.5">
   245	            {negativePrompt}
   246	          </p>
   247	        </div>
   248	      )}
   249	    </div>
   250	  )
   251	}
   252	
   253	// =============================================================================
   254	// Main Component
   255	// =============================================================================
   256	
   257	export function PreviewAnalysisTab({
   258	  packName,
   259	  depKind,
   260	  candidates,

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx | nl -ba | sed -n '260,520p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	  candidates,
   261	  onSelectCandidate,
   262	}: PreviewAnalysisTabProps) {
   263	  const { t } = useTranslation()
   264	  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
   265	
   266	  const { data, isLoading, error } = usePreviewAnalysis(packName, true)
   267	
   268	  // Filter previews that have hints
   269	  const previewsWithHints = useMemo(() => {
   270	    if (!data?.previews) return []
   271	    return data.previews
   272	  }, [data])
   273	
   274	  const selectedPreview = selectedIndex !== null && selectedIndex < previewsWithHints.length
   275	    ? previewsWithHints[selectedIndex] : null
   276	
   277	  // Find matching candidate for a hint
   278	  const findCandidateForHint = (hint: PreviewModelHintInfo): string | null => {
   279	    // Look for a candidate whose evidence references this preview hint
   280	    for (const c of candidates) {
   281	      for (const g of c.evidence_groups) {
   282	        // Check provenance — preview evidence has "preview:<filename>" pattern
   283	        if (g.provenance.startsWith('preview:')) {
   284	          for (const item of g.items) {
   285	            if (
   286	              item.raw_value &&
   287	              (item.raw_value === hint.raw_value ||
   288	                item.raw_value === hint.filename)
   289	            ) {
   290	              return c.candidate_id
   291	            }
   292	          }
   293	        }
   294	      }
   295	      // Also try matching by display name
   296	      const normalized = hint.filename.replace(/\.safetensors$|\.ckpt$|\.pt$/i, '').toLowerCase()
   297	      if (c.display_name.toLowerCase().includes(normalized)) {
   298	        return c.candidate_id
   299	      }
   300	    }
   301	    return null
   302	  }
   303	
   304	  const handleUseHint = (hint: PreviewModelHintInfo) => {
   305	    const candidateId = findCandidateForHint(hint)
   306	    if (candidateId) {
   307	      onSelectCandidate(candidateId)
   308	    } else {
   309	      toast.info(
   310	        t('pack.resolve.previewRunSuggest', 'No matching candidate found. Run suggestion first.')
   311	      )
   312	    }
   313	  }
   314	
   315	  // Loading state
   316	  if (isLoading) {
   317	    return (
   318	      <div className="flex flex-col items-center justify-center py-12 gap-3">
   319	        <Loader2 className="w-8 h-8 text-synapse animate-spin" />
   320	        <p className="text-sm text-text-muted">
   321	          {t('pack.resolve.previewLoading', 'Analyzing preview images...')}
   322	        </p>
   323	      </div>
   324	    )
   325	  }
   326	
   327	  // Error state
   328	  if (error) {
   329	    return (
   330	      <div className="flex flex-col items-center justify-center py-12 gap-3">
   331	        <AlertCircle className="w-8 h-8 text-red-400" />
   332	        <p className="text-sm text-red-400">{error.message}</p>
   333	      </div>
   334	    )
   335	  }
   336	
   337	  // Empty state
   338	  if (!data || previewsWithHints.length === 0) {
   339	    return (
   340	      <div className="flex flex-col items-center justify-center py-12 gap-3">
   341	        <ImageIcon className="w-10 h-10 text-text-muted/50" />
   342	        <p className="text-text-muted text-center">
   343	          {t('pack.resolve.noPreviewData', 'No preview metadata available for this dependency.')}
   344	        </p>
   345	      </div>
   346	    )
   347	  }
   348	
   349	  return (
   350	    <div className="space-y-4">
   351	      {/* Header */}
   352	      <div className="flex items-center justify-between">
   353	        <p className="text-sm text-text-muted">
   354	          {t('pack.resolve.previewHintsCount', '{{count}} model hints from {{total}} previews', {
   355	            count: data.total_hints,
   356	            total: previewsWithHints.length,
   357	          })}
   358	        </p>
   359	      </div>
   360	
   361	      {/* Thumbnail grid */}
   362	      <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 gap-2">
   363	        {previewsWithHints.map((preview, index) => (
   364	          <PreviewThumbnail
   365	            key={preview.filename}
   366	            preview={preview}
   367	            isSelected={selectedIndex === index}
   368	            onClick={() => setSelectedIndex(selectedIndex === index ? null : index)}
   369	          />
   370	        ))}
   371	      </div>
   372	
   373	      {/* Selected preview detail panel */}
   374	      {selectedPreview && (
   375	        <div className="rounded-xl bg-slate-dark border border-slate-mid overflow-hidden">
   376	          {/* Header */}
   377	          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-mid">
   378	            <div className="flex items-center gap-2 min-w-0">
   379	              <ImageIcon className="w-4 h-4 text-synapse flex-shrink-0" />
   380	              <span className="text-sm text-text-primary font-medium truncate">
   381	                {selectedPreview.filename}
   382	              </span>
   383	            </div>
   384	            {(selectedPreview.width || selectedPreview.height) && (
   385	              <span className="text-xs text-text-muted flex-shrink-0">
   386	                {selectedPreview.width}&times;{selectedPreview.height}
   387	              </span>
   388	            )}
   389	          </div>
   390	
   391	          <div className="p-4 space-y-4">
   392	            {/* Model References */}
   393	            {selectedPreview.hints.length > 0 && (
   394	              <div>
   395	                <h4 className="text-xs text-text-muted font-medium uppercase tracking-wider mb-2">
   396	                  {t('pack.resolve.previewModelRefs', 'Model References')}
   397	                </h4>
   398	                <div className="space-y-0.5">
   399	                  {selectedPreview.hints.map((hint, i) => (
   400	                    <HintRow
   401	                      key={`${hint.filename}-${i}`}
   402	                      hint={hint}
   403	                      depKind={depKind}
   404	                      onUse={() => handleUseHint(hint)}
   405	                      canUse={candidates.length > 0}
   406	                    />
   407	                  ))}
   408	                </div>
   409	              </div>
   410	            )}
   411	
   412	            {/* No hints for this preview */}
   413	            {selectedPreview.hints.length === 0 && (
   414	              <p className="text-sm text-text-muted italic">
   415	                {t('pack.resolve.previewNoHints', 'No model references found in this preview.')}
   416	              </p>
   417	            )}
   418	
   419	            {/* Generation Parameters */}
   420	            {selectedPreview.generation_params && Object.keys(selectedPreview.generation_params).length > 0 && (
   421	              <div>
   422	                <h4 className="text-xs text-text-muted font-medium uppercase tracking-wider mb-2">
   423	                  {t('pack.resolve.previewGenParams', 'Generation Parameters')}
   424	                </h4>
   425	                <GenerationParamsDisplay params={selectedPreview.generation_params} />
   426	              </div>
   427	            )}
   428	          </div>
   429	        </div>
   430	      )}
   431	    </div>
   432	  )
   433	}
   434	
   435	export default PreviewAnalysisTab

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/hooks/usePackData.ts | nl -ba | sed -n '1,280p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * usePackData Hook
     3	 *
     4	 * Centralized data management for pack detail page.
     5	 * Handles all pack queries and mutations.
     6	 */
     7	
     8	import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
     9	import { useNavigate } from 'react-router-dom'
    10	import { toast } from '@/stores/toastStore'
    11	import type {
    12	  PackDetail,
    13	  PackBackupStatusResponse,
    14	  SuggestResult,
    15	  SuggestOptions,
    16	  ApplyResult,
    17	} from '../types'
    18	import { QUERY_KEYS } from '../constants'
    19	
    20	// =============================================================================
    21	// Types
    22	// =============================================================================
    23	
    24	export interface UsePackDataOptions {
    25	  /**
    26	   * Pack name to load
    27	   */
    28	  packName: string
    29	
    30	  /**
    31	   * Callback after successful deletion
    32	   */
    33	  onDeleteSuccess?: () => void
    34	}
    35	
    36	export interface UsePackDataReturn {
    37	  // Queries
    38	  pack: PackDetail | undefined
    39	  isLoading: boolean
    40	  error: Error | null
    41	  backupStatus: PackBackupStatusResponse | undefined
    42	  isBackupStatusLoading: boolean
    43	
    44	  // Mutations
    45	  deletePack: () => void
    46	  isDeleting: boolean
    47	
    48	  usePack: () => void
    49	  isUsingPack: boolean
    50	
    51	  updatePack: (data: { user_tags: string[] }) => void
    52	  isUpdatingPack: boolean
    53	
    54	  updateParameters: (data: Record<string, unknown>) => void
    55	  isUpdatingParameters: boolean
    56	
    57	
    58	  resolvePack: () => void
    59	  isResolvingPack: boolean
    60	
    61	  suggestResolution: (depId: string, options?: SuggestOptions) => Promise<SuggestResult>
    62	  isSuggesting: boolean
    63	
    64	  applyResolution: (depId: string, candidateId: string, requestId?: string) => Promise<ApplyResult>
    65	  isApplying: boolean
    66	
    67	  applyAndDownload: (depId: string, candidateId: string, requestId?: string) => Promise<void>
    68	  isApplyingAndDownloading: boolean
    69	
    70	  generateWorkflow: () => void
    71	  isGeneratingWorkflow: boolean
    72	
    73	  createSymlink: (filename: string) => void
    74	  isCreatingSymlink: boolean
    75	
    76	  removeSymlink: (filename: string) => void
    77	  isRemovingSymlink: boolean
    78	
    79	  deleteWorkflow: (filename: string) => void
    80	  isDeletingWorkflow: boolean
    81	
    82	  uploadWorkflow: (data: { file: File; name: string; description?: string }) => void
    83	  isUploadingWorkflow: boolean
    84	
    85	  deleteResource: (depId: string, deleteDependency?: boolean) => void
    86	  isDeletingResource: boolean
    87	
    88	  setAsBaseModel: (depId: string) => void
    89	  isSettingBaseModel: boolean
    90	
    91	  pullPack: () => void
    92	  isPullingPack: boolean
    93	
    94	  pushPack: (cleanup: boolean) => void
    95	  isPushingPack: boolean
    96	
    97	  // Preview & Description Mutations (Phase 6)
    98	  updateDescription: (description: string) => void
    99	  isUpdatingDescription: boolean
   100	
   101	  // Batch update - preferred method for EditPreviewsModal
   102	  batchUpdatePreviews: (data: {
   103	    files?: File[]
   104	    order?: string[]
   105	    coverFilename?: string
   106	    deleted?: string[]
   107	  }) => Promise<unknown>
   108	  isBatchUpdatingPreviews: boolean
   109	
   110	  // Individual mutations (kept for backwards compatibility)
   111	  uploadPreview: (data: { file: File; position?: number; nsfw?: boolean }) => void
   112	  uploadPreviewAsync: (data: { file: File; position?: number; nsfw?: boolean }) => Promise<unknown>
   113	  isUploadingPreview: boolean
   114	
   115	  deletePreview: (filename: string) => void
   116	  deletePreviewAsync: (filename: string) => Promise<unknown>
   117	  isDeletingPreview: boolean
   118	
   119	  reorderPreviews: (order: string[]) => void
   120	  reorderPreviewsAsync: (order: string[]) => Promise<unknown>
   121	  isReorderingPreviews: boolean
   122	
   123	  setCoverPreview: (filename: string) => void
   124	  setCoverPreviewAsync: (filename: string) => Promise<unknown>
   125	  isSettingCover: boolean
   126	
   127	  // Refetch
   128	  refetch: () => void
   129	  refetchBackupStatus: () => void
   130	}
   131	
   132	// =============================================================================
   133	// Hook Implementation
   134	// =============================================================================
   135	
   136	export function usePackData({
   137	  packName,
   138	  onDeleteSuccess,
   139	}: UsePackDataOptions): UsePackDataReturn {
   140	  const queryClient = useQueryClient()
   141	  const navigate = useNavigate()
   142	
   143	  // =========================================================================
   144	  // Pack Detail Query
   145	  // =========================================================================
   146	
   147	  const {
   148	    data: pack,
   149	    isLoading,
   150	    error,
   151	    refetch,
   152	  } = useQuery<PackDetail, Error>({
   153	    queryKey: QUERY_KEYS.pack(packName),
   154	    queryFn: async () => {
   155	      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`)
   156	      if (!res.ok) {
   157	        const errText = await res.text()
   158	        throw new Error(`Failed to fetch pack: ${res.status} - ${errText}`)
   159	      }
   160	      return res.json()
   161	    },
   162	    enabled: !!packName,
   163	  })
   164	
   165	  // =========================================================================
   166	  // Backup Status Query
   167	  // =========================================================================
   168	
   169	  const {
   170	    data: backupStatus,
   171	    isLoading: isBackupStatusLoading,
   172	    refetch: refetchBackupStatus,
   173	  } = useQuery<PackBackupStatusResponse>({
   174	    queryKey: QUERY_KEYS.packBackup(packName),
   175	    queryFn: async () => {
   176	      const res = await fetch(`/api/store/backup/pack-status/${encodeURIComponent(packName)}`)
   177	      if (!res.ok) {
   178	        return {
   179	          pack: packName,
   180	          backup_enabled: false,
   181	          backup_connected: false,
   182	          blobs: [],
   183	          summary: { total: 0, local_only: 0, backup_only: 0, both: 0, nowhere: 0, total_bytes: 0 },
   184	        }
   185	      }
   186	      return res.json()
   187	    },
   188	    enabled: !!packName,
   189	    staleTime: 30000,
   190	  })
   191	
   192	  // =========================================================================
   193	  // Delete Pack Mutation
   194	  // =========================================================================
   195	
   196	  const deleteMutation = useMutation({
   197	    mutationFn: async () => {
   198	      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, { method: 'DELETE' })
   199	      if (!res.ok) {
   200	        const errText = await res.text()
   201	        throw new Error(`Failed to delete pack: ${errText}`)
   202	      }
   203	      return res.json()
   204	    },
   205	    onSuccess: () => {
   206	      queryClient.invalidateQueries({ queryKey: ['packs'] })
   207	      toast.success('Pack deleted')
   208	      onDeleteSuccess?.()
   209	      navigate('/')
   210	    },
   211	    onError: (error: Error) => {
   212	      toast.error(`Failed to delete pack: ${error.message}`)
   213	    },
   214	  })
   215	
   216	  // =========================================================================
   217	  // Use Pack Mutation
   218	  // =========================================================================
   219	
   220	  const usePackMutation = useMutation({
   221	    mutationFn: async () => {
   222	      const res = await fetch('/api/profiles/use', {
   223	        method: 'POST',
   224	        headers: { 'Content-Type': 'application/json' },
   225	        body: JSON.stringify({
   226	          pack: packName,
   227	          ui_set: 'local',
   228	          sync: true,
   229	        }),
   230	      })
   231	      if (!res.ok) {
   232	        const errText = await res.text()
   233	        throw new Error(`Failed to activate pack: ${errText}`)
   234	      }
   235	      return res.json()
   236	    },
   237	    onSuccess: (data) => {
   238	      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
   239	      const profileName = data?.new_profile || `work__${packName}`
   240	      toast.success(`Activated: ${profileName}`)
   241	    },
   242	    onError: (error: Error) => {
   243	      toast.error(`Failed to activate: ${error.message}`)
   244	    },
   245	  })
   246	
   247	  // =========================================================================
   248	  // Update Pack Mutation
   249	  // =========================================================================
   250	
   251	  const updatePackMutation = useMutation({
   252	    mutationFn: async (data: { user_tags: string[] }) => {
   253	      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, {
   254	        method: 'PATCH',
   255	        headers: { 'Content-Type': 'application/json' },
   256	        body: JSON.stringify(data),
   257	      })
   258	      if (!res.ok) {
   259	        const errText = await res.text()
   260	        throw new Error(`Failed to update pack: ${errText}`)
   261	      }
   262	      return res.json()
   263	    },
   264	    onSuccess: () => {
   265	      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   266	      queryClient.invalidateQueries({ queryKey: ['packs'] })
   267	      toast.success('Pack updated')
   268	    },
   269	    onError: (error: Error) => {
   270	      toast.error(`Failed to update pack: ${error.message}`)
   271	    },
   272	  })
   273	
   274	  // =========================================================================
   275	  // Update Parameters Mutation
   276	  // =========================================================================
   277	
   278	  const updateParametersMutation = useMutation({
   279	    mutationFn: async (data: Record<string, unknown>) => {
   280	      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/parameters`, {

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/hooks/usePackData.ts | nl -ba | sed -n '340,520p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   340	            max_candidates: options?.max_candidates ?? 10,
   341	          }),
   342	        }
   343	      )
   344	      if (!res.ok) {
   345	        const errText = await res.text()
   346	        throw new Error(`Failed to suggest resolution: ${errText}`)
   347	      }
   348	      return res.json() as Promise<SuggestResult>
   349	    },
   350	    onError: (error: Error) => {
   351	      toast.error(`Failed to suggest resolution: ${error.message}`)
   352	    },
   353	  })
   354	
   355	  // =========================================================================
   356	  // Apply Resolution Mutation
   357	  // =========================================================================
   358	
   359	  const applyResolutionMutation = useMutation({
   360	    mutationFn: async ({
   361	      depId,
   362	      candidateId,
   363	      requestId,
   364	    }: {
   365	      depId: string
   366	      candidateId: string
   367	      requestId?: string
   368	    }) => {
   369	      const res = await fetch(
   370	        `/api/packs/${encodeURIComponent(packName)}/apply-resolution`,
   371	        {
   372	          method: 'POST',
   373	          headers: { 'Content-Type': 'application/json' },
   374	          body: JSON.stringify({
   375	            dep_id: depId,
   376	            candidate_id: candidateId,
   377	            request_id: requestId,
   378	          }),
   379	        }
   380	      )
   381	      if (!res.ok) {
   382	        const errText = await res.text()
   383	        throw new Error(`Failed to apply resolution: ${errText}`)
   384	      }
   385	      return res.json() as Promise<ApplyResult>
   386	    },
   387	    onSuccess: () => {
   388	      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   389	      queryClient.invalidateQueries({ queryKey: ['packs'] })
   390	      toast.success('Resolution applied')
   391	    },
   392	    onError: (error: Error) => {
   393	      toast.error(`Failed to apply resolution: ${error.message}`)
   394	    },
   395	  })
   396	
   397	  // =========================================================================
   398	  // Apply & Download Mutation (compound action)
   399	  // =========================================================================
   400	
   401	  const applyAndDownloadMutation = useMutation({
   402	    mutationFn: async ({
   403	      depId,
   404	      candidateId,
   405	      requestId,
   406	    }: {
   407	      depId: string
   408	      candidateId: string
   409	      requestId?: string
   410	    }) => {
   411	      // Step 1: Apply resolution
   412	      const applyRes = await fetch(
   413	        `/api/packs/${encodeURIComponent(packName)}/apply-resolution`,
   414	        {
   415	          method: 'POST',
   416	          headers: { 'Content-Type': 'application/json' },
   417	          body: JSON.stringify({
   418	            dep_id: depId,
   419	            candidate_id: candidateId,
   420	            request_id: requestId,
   421	          }),
   422	        }
   423	      )
   424	      if (!applyRes.ok) {
   425	        const errText = await applyRes.text()
   426	        throw new Error(`Failed to apply resolution: ${errText}`)
   427	      }
   428	      const result = (await applyRes.json()) as ApplyResult
   429	      if (!result.success) {
   430	        throw new Error(result.message || 'Apply failed')
   431	      }
   432	
   433	      // Step 2: Refetch pack to get updated asset info
   434	      await queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   435	
   436	      // Step 3: Trigger download via existing download-asset endpoint
   437	      const downloadRes = await fetch(
   438	        `/api/packs/${encodeURIComponent(packName)}/download-asset`,
   439	        {
   440	          method: 'POST',
   441	          headers: { 'Content-Type': 'application/json' },
   442	          body: JSON.stringify({ asset_name: depId }),
   443	        }
   444	      )
   445	      if (!downloadRes.ok) {
   446	        const errText = await downloadRes.text()
   447	        throw new Error(`Resolution applied, but download failed: ${errText}`)
   448	      }
   449	    },
   450	    onSuccess: () => {
   451	      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   452	      queryClient.invalidateQueries({ queryKey: ['packs'] })
   453	      toast.success('Resolution applied, download started')
   454	    },
   455	    onError: (error: Error) => {
   456	      toast.error(error.message)
   457	    },
   458	  })
   459	
   460	  // =========================================================================
   461	  // Workflow Mutations
   462	  // =========================================================================
   463	
   464	  const generateWorkflowMutation = useMutation({
   465	    mutationFn: async () => {
   466	      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/generate-workflow`, {
   467	        method: 'POST',
   468	      })
   469	      if (!res.ok) {
   470	        const errText = await res.text()
   471	        throw new Error(`Failed to generate workflow: ${errText}`)
   472	      }
   473	      return res.json()
   474	    },
   475	    onSuccess: () => {
   476	      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   477	      toast.success('Workflow generated')
   478	    },
   479	    onError: (error: Error) => {
   480	      toast.error(`Failed to generate workflow: ${error.message}`)
   481	    },
   482	  })
   483	
   484	  const createSymlinkMutation = useMutation({
   485	    mutationFn: async (filename: string) => {
   486	      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/symlink`, {
   487	        method: 'POST',
   488	        headers: { 'Content-Type': 'application/json' },
   489	        body: JSON.stringify({ filename }),
   490	      })
   491	      if (!res.ok) {
   492	        const errText = await res.text()
   493	        throw new Error(`Failed to create symlink: ${errText}`)
   494	      }
   495	      return res.json()
   496	    },
   497	    onSuccess: () => {
   498	      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   499	      toast.success('Workflow symlink created')
   500	    },
   501	    onError: (error: Error) => {
   502	      toast.error(`Failed to create symlink: ${error.message}`)
   503	    },
   504	  })
   505	
   506	  const removeSymlinkMutation = useMutation({
   507	    mutationFn: async (filename: string) => {
   508	      const res = await fetch(
   509	        `/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(filename)}/symlink`,
   510	        { method: 'DELETE' }
   511	      )
   512	      if (!res.ok) {
   513	        const errText = await res.text()
   514	        throw new Error(`Failed to remove symlink: ${errText}`)
   515	      }
   516	      return res.json()
   517	    },
   518	    onSuccess: () => {
   519	      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pack(packName) })
   520	      toast.success('Workflow symlink removed')

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/PackDetailPage.tsx | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * PackDetailPage
     3	 *
     4	 * Integrated pack detail page using modular components from pack-detail/.
     5	 *
     6	 * ARCHITECTURE:
     7	 * - Hooks: usePackData, usePackDownloads, usePackEdit, usePackPlugin
     8	 * - Sections: PackHeader, PackGallery, PackInfoSection, etc.
     9	 * - Modals: EditPackModal, DependencyResolverModal, etc.
    10	 * - Plugins: CivitaiPlugin, CustomPlugin, InstallPlugin
    11	 *
    12	 * This file is the orchestrator - it connects hooks to components.
    13	 */
    14	
    15	import { useState, useMemo, useCallback } from 'react'
    16	import { useParams, useNavigate } from 'react-router-dom'
    17	import { useTranslation } from 'react-i18next'
    18	import { ArrowLeft } from 'lucide-react'
    19	
    20	import { FullscreenMediaViewer } from '@/components/ui/FullscreenMediaViewer'
    21	import { BreathingOrb } from '@/components/ui/BreathingOrb'
    22	import { Button } from '@/components/ui/Button'
    23	
    24	// Modular pack-detail components
    25	import {
    26	  // Hooks
    27	  usePackData,
    28	  usePackDownloads,
    29	  usePackEdit,
    30	  usePackPlugin,
    31	  useAvatarAvailable,
    32	  // Sections
    33	  PackHeader,
    34	  PackGallery,
    35	  PackInfoSection,
    36	  PackDependenciesSection,
    37	  PackDepsSection,
    38	  PackWorkflowsSection,
    39	  PackParametersSection,
    40	  PackStorageSection,
    41	  PackUserTagsSection,
    42	  // Modals
    43	  EditPackModal,
    44	  EditParametersModal,
    45	  UploadWorkflowModal,
    46	  DependencyResolverModal,
    47	  EditPreviewsModal,
    48	  DescriptionEditorModal,
    49	  // Shared
    50	  ErrorBoundary,
    51	  SectionErrorBoundary,
    52	  // Types
    53	  type AssetInfo,
    54	  type AssetType,
    55	  type ModalState,
    56	  type ResolutionCandidate,
    57	  type SuggestResult,
    58	  // Constants
    59	  DEFAULT_MODAL_STATE,
    60	} from './pack-detail'
    61	
    62	// Legacy components still used
    63	import {
    64	  PullConfirmDialog,
    65	  PushConfirmDialog,
    66	} from './packs'
    67	
    68	// =============================================================================
    69	// Component
    70	// =============================================================================
    71	
    72	function PackDetailPageContent() {
    73	  const { packName: packNameParam } = useParams<{ packName: string }>()
    74	  const navigate = useNavigate()
    75	  const { t } = useTranslation()
    76	
    77	  // Decode pack name from URL
    78	  const packName = packNameParam ? decodeURIComponent(packNameParam) : ''
    79	
    80	  // ==========================================================================
    81	  // Hooks
    82	  // ==========================================================================
    83	
    84	  // Main pack data and mutations
    85	  const packData = usePackData({
    86	    packName,
    87	    onDeleteSuccess: () => navigate('/'),
    88	  })
    89	
    90	  // Download progress tracking
    91	  const downloads = usePackDownloads({
    92	    packName,
    93	  })
    94	
    95	  // Edit mode state
    96	  const editState = usePackEdit({
    97	    initialPack: packData.pack,
    98	    onSave: async (changes) => {
    99	      if (changes.user_tags) {
   100	        await packData.updatePack({ user_tags: changes.user_tags })
   101	      }
   102	    },
   103	  })
   104	
   105	  // Avatar availability (for AI resolve tab)
   106	  const { avatarAvailable } = useAvatarAvailable()
   107	
   108	  // ==========================================================================
   109	  // Modal State
   110	  // ==========================================================================
   111	
   112	  const [modals, setModals] = useState<ModalState>({ ...DEFAULT_MODAL_STATE })
   113	
   114	  const openModal = useCallback((key: keyof ModalState | string) => {
   115	    setModals((prev) => ({ ...prev, [key]: true }))
   116	  }, [])
   117	
   118	  const closeModal = useCallback((key: keyof ModalState | string) => {
   119	    setModals((prev) => ({ ...prev, [key]: false }))
   120	  }, [])
   121	
   122	  // ==========================================================================
   123	  // Dependency Resolver State
   124	  // ==========================================================================
   125	
   126	  const [resolveDepId, setResolveDepId] = useState<string | null>(null)
   127	  const [resolveDepName, setResolveDepName] = useState('')
   128	  const [resolveDepKind, setResolveDepKind] = useState<AssetType>('checkpoint')
   129	  const [resolveCandidates, setResolveCandidates] = useState<ResolutionCandidate[]>([])
   130	  const [resolveRequestId, setResolveRequestId] = useState<string | undefined>()
   131	
   132	  const handleOpenDependencyResolver = useCallback(
   133	    (asset: AssetInfo) => {
   134	      setResolveDepId(asset.name)
   135	      setResolveDepName(asset.filename || asset.name)
   136	      setResolveDepKind((asset.asset_type as AssetType) || 'checkpoint')
   137	      setResolveCandidates([])
   138	      setResolveRequestId(undefined)
   139	      openModal('dependencyResolver')
   140	
   141	      // Eager suggest (without AI) — best-effort, user can retry in modal
   142	      const depName = asset.name
   143	      packData
   144	        .suggestResolution(depName, { include_ai: false })
   145	        .then((result: SuggestResult) => {
   146	          // Guard against stale response (user may have opened a different dep)
   147	          setResolveDepId((currentId) => {
   148	            if (currentId === depName) {
   149	              setResolveCandidates(result.candidates)
   150	              setResolveRequestId(result.request_id)
   151	            }
   152	            return currentId
   153	          })
   154	        })
   155	        .catch((err) => {
   156	          console.warn('[PackDetailPage] Eager suggest failed:', err?.message)
   157	        })
   158	    },
   159	    [openModal, packData]
   160	  )
   161	
   162	  const handleSuggestResolution = useCallback(
   163	    async (options?: { include_ai?: boolean; max_candidates?: number }) => {
   164	      if (!resolveDepId) throw new Error('No dependency selected')
   165	      const result = await packData.suggestResolution(resolveDepId, options)
   166	      setResolveCandidates(result.candidates)
   167	      setResolveRequestId(result.request_id)
   168	      return result
   169	    },
   170	    [resolveDepId, packData]
   171	  )
   172	
   173	  const handleApplyResolution = useCallback(
   174	    (candidateId: string) => {
   175	      if (!resolveDepId) return
   176	      packData
   177	        .applyResolution(resolveDepId, candidateId, resolveRequestId)
   178	        .then(() => closeModal('dependencyResolver'))
   179	        .catch(() => {}) // Error toast shown by mutation onError
   180	    },
   181	    [resolveDepId, resolveRequestId, packData, closeModal]
   182	  )
   183	
   184	  const handleApplyAndDownload = useCallback(
   185	    (candidateId: string) => {
   186	      if (!resolveDepId) return
   187	      packData
   188	        .applyAndDownload(resolveDepId, candidateId, resolveRequestId)
   189	        .then(() => closeModal('dependencyResolver'))
   190	        .catch(() => {}) // Error toast shown by mutation onError
   191	    },
   192	    [resolveDepId, resolveRequestId, packData, closeModal]
   193	  )
   194	
   195	  // ==========================================================================
   196	  // Plugin System
   197	  // ==========================================================================
   198	
   199	  const { plugin, context: pluginContext } = usePackPlugin({
   200	    pack: packData.pack,
   201	    isEditing: editState.isEditing,
   202	    hasUnsavedChanges: editState.hasUnsavedChanges,
   203	    modals,
   204	    openModal,
   205	    closeModal,
   206	    refetch: packData.refetch,
   207	  })
   208	
   209	  // ==========================================================================
   210	  // Fullscreen Gallery
   211	  // ==========================================================================
   212	
   213	  const [fullscreenIndex, setFullscreenIndex] = useState<number>(-1)
   214	
   215	  const isFullscreenOpen = fullscreenIndex >= 0
   216	
   217	  const mediaItems = useMemo(() => {
   218	    return (
   219	      packData.pack?.previews.map((p) => ({
   220	        url: p.url || '',
   221	        type: (p.media_type === 'video' ? 'video' : 'image') as 'video' | 'image',
   222	        thumbnailUrl: p.thumbnail_url,
   223	        nsfw: p.nsfw,
   224	        width: p.width,
   225	        height: p.height,
   226	        meta: p.meta as Record<string, unknown> | undefined,
   227	      })) || []
   228	    )
   229	  }, [packData.pack?.previews])
   230	
   231	  // ==========================================================================
   232	  // Base Model Resolver State
   233	  // ==========================================================================
   234	
   235	  // ==========================================================================
   236	  // Handlers
   237	  // ==========================================================================
   238	
   239	  // Dependencies section handlers
   240	  const downloadingAssetsSet = useMemo(() => {
   241	    const set = new Set<string>()
   242	    downloads.activeDownloads.forEach((d) => {
   243	      if (d.status === 'downloading' || d.status === 'pending') {
   244	        set.add(d.asset_name)
   245	      }
   246	    })
   247	    return set
   248	  }, [downloads.activeDownloads])
   249	
   250	  const handleRestoreFromBackup = useCallback(
   251	    async (_asset: AssetInfo) => {
   252	      // Trigger restore from backup - this would typically call a specific API
   253	      // For now, we can use pullPack which restores all from backup
   254	      packData.pullPack()
   255	    },
   256	    [packData]
   257	  )
   258	
   259	  // Push dialog state
   260	  const [pushWithCleanup, setPushWithCleanup] = useState(false)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/PackDetailPage.tsx | nl -ba | sed -n '260,520p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	  const [pushWithCleanup, setPushWithCleanup] = useState(false)
   261	
   262	  // ==========================================================================
   263	  // Render
   264	  // ==========================================================================
   265	
   266	  // Loading state
   267	  if (packData.isLoading) {
   268	    return (
   269	      <div className="flex items-center justify-center min-h-[60vh]">
   270	        <BreathingOrb size="lg" text={t('packDetail.loading')} />
   271	      </div>
   272	    )
   273	  }
   274	
   275	  // Error state
   276	  if (packData.error) {
   277	    return (
   278	      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
   279	        <div className="text-red-400 text-center">
   280	          <p className="text-lg font-medium">{t('packDetail.loadFailed')}</p>
   281	          <p className="text-sm mt-2">{packData.error.message}</p>
   282	        </div>
   283	        <Button variant="secondary" onClick={() => navigate('/')}>
   284	          <ArrowLeft className="w-4 h-4" />
   285	          {t('packDetail.backToPacks')}
   286	        </Button>
   287	      </div>
   288	    )
   289	  }
   290	
   291	  // No pack found
   292	  if (!packData.pack) {
   293	    return (
   294	      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
   295	        <p className="text-text-muted">{t('packDetail.notFound')}</p>
   296	        <Button variant="secondary" onClick={() => navigate('/')}>
   297	          <ArrowLeft className="w-4 h-4" />
   298	          {t('packDetail.backToPacks')}
   299	        </Button>
   300	      </div>
   301	    )
   302	  }
   303	
   304	  const { pack, backupStatus } = packData
   305	
   306	  return (
   307	    <div className="space-y-8 pb-12">
   308	      {/* Back Button */}
   309	      <Button
   310	        variant="secondary"
   311	        onClick={() => navigate('/')}
   312	        className="opacity-70 hover:opacity-100 transition-opacity"
   313	      >
   314	        <ArrowLeft className="w-4 h-4" />
   315	        {t('packDetail.backToPacks')}
   316	      </Button>
   317	
   318	      {/* Header Section */}
   319	      {/*
   320	        Edit mode: We use modal-based editing via per-section Edit buttons
   321	        (Gallery, Description, Parameters, User Tags). The header Edit button
   322	        is for inline editing which isn't implemented yet, so we don't pass onStartEdit.
   323	      */}
   324	      <PackHeader
   325	        pack={pack}
   326	        onUsePack={packData.usePack}
   327	        onDelete={packData.deletePack}
   328	        isUsingPack={packData.isUsingPack}
   329	        isDeleting={packData.isDeleting}
   330	        animationDelay={0}
   331	        // Plugin header actions are rendered inside PackHeader via pluginActions prop
   332	        pluginActions={pluginContext && plugin?.renderHeaderActions?.(pluginContext)}
   333	      />
   334	
   335	      {/* Gallery Section */}
   336	      {pack.previews && pack.previews.length > 0 && (
   337	        <SectionErrorBoundary sectionName="Gallery" onRetry={packData.refetch}>
   338	          <PackGallery
   339	            previews={pack.previews}
   340	            onPreviewClick={(index) => setFullscreenIndex(index)}
   341	            onEdit={plugin?.features?.canEditPreviews ? () => openModal('editPreviews') : undefined}
   342	            animationDelay={50}
   343	          />
   344	        </SectionErrorBoundary>
   345	      )}
   346	
   347	      {/* Info Section */}
   348	      <SectionErrorBoundary sectionName="Information" onRetry={packData.refetch}>
   349	        <PackInfoSection
   350	          pack={pack}
   351	          onEditDescription={plugin?.features?.canEditMetadata ? () => openModal('markdownEditor') : undefined}
   352	          animationDelay={100}
   353	        />
   354	      </SectionErrorBoundary>
   355	
   356	      {/* User Tags Section - always editable even for Civitai packs */}
   357	      <SectionErrorBoundary sectionName="User Tags" onRetry={packData.refetch}>
   358	        <PackUserTagsSection
   359	          tags={pack.user_tags || []}
   360	          onEdit={() => openModal('editPack')}
   361	          animationDelay={125}
   362	        />
   363	      </SectionErrorBoundary>
   364	
   365	      {/* Dependencies Section */}
   366	      <SectionErrorBoundary sectionName="Dependencies" onRetry={packData.refetch}>
   367	        <PackDependenciesSection
   368	          assets={pack.assets}
   369	          backupStatus={backupStatus}
   370	          downloadingAssets={downloadingAssetsSet}
   371	          getAssetDownload={downloads.getAssetDownload}
   372	          onDownloadAll={downloads.downloadAll}
   373	          onDownloadAsset={downloads.downloadAsset}
   374	          onRestoreFromBackup={handleRestoreFromBackup}
   375	          onDeleteResource={packData.deleteResource}
   376	
   377	          onResolvePack={packData.resolvePack}
   378	          onOpenDependencyResolver={handleOpenDependencyResolver}
   379	          onSetAsBaseModel={(asset) => packData.setAsBaseModel(asset.name)}
   380	          isDownloadAllPending={downloads.isDownloadingAll}
   381	          isResolvePending={packData.isResolvingPack}
   382	          animationDelay={150}
   383	        />
   384	      </SectionErrorBoundary>
   385	
   386	      {/* Pack Dependencies Section (pack-to-pack) - right after file dependencies */}
   387	      {pluginContext && (
   388	        <SectionErrorBoundary sectionName="Pack Dependencies" onRetry={packData.refetch}>
   389	          <PackDepsSection context={pluginContext} />
   390	        </SectionErrorBoundary>
   391	      )}
   392	
   393	      {/* Workflows Section */}
   394	      <SectionErrorBoundary sectionName="Workflows" onRetry={packData.refetch}>
   395	        <PackWorkflowsSection
   396	          workflows={pack.workflows}
   397	          packName={pack.name}
   398	          needsBaseModel={pack.has_unresolved}
   399	          onCreateSymlink={packData.createSymlink}
   400	          onRemoveSymlink={packData.removeSymlink}
   401	          onDeleteWorkflow={packData.deleteWorkflow}
   402	          onGenerateWorkflow={packData.generateWorkflow}
   403	          onOpenUploadModal={() => openModal('uploadWorkflow')}
   404	          isCreateSymlinkPending={packData.isCreatingSymlink}
   405	          isRemoveSymlinkPending={packData.isRemovingSymlink}
   406	          isDeletePending={packData.isDeletingWorkflow}
   407	          isGeneratePending={packData.isGeneratingWorkflow}
   408	          animationDelay={200}
   409	        />
   410	      </SectionErrorBoundary>
   411	
   412	      {/* Parameters Section */}
   413	      <SectionErrorBoundary sectionName="Parameters" onRetry={packData.refetch}>
   414	        <PackParametersSection
   415	          parameters={pack.parameters}
   416	          modelInfo={pack.model_info}
   417	          onEdit={() => openModal('editParameters')}
   418	          animationDelay={250}
   419	        />
   420	      </SectionErrorBoundary>
   421	
   422	      {/* Storage Section */}
   423	      <SectionErrorBoundary sectionName="Storage" onRetry={packData.refetch}>
   424	        <PackStorageSection
   425	          backupStatus={backupStatus}
   426	          isLoading={packData.isBackupStatusLoading}
   427	          onPull={() => openModal('pullConfirm')}
   428	          onPush={() => {
   429	            setPushWithCleanup(false)
   430	            openModal('pushConfirm')
   431	          }}
   432	          onPushAndFree={() => {
   433	            setPushWithCleanup(true)
   434	            openModal('pushConfirm')
   435	          }}
   436	          isPulling={packData.isPullingPack}
   437	          isPushing={packData.isPushingPack}
   438	          animationDelay={300}
   439	        />
   440	      </SectionErrorBoundary>
   441	
   442	      {/* =====================================================================
   443	          PLUGIN SECTIONS
   444	          ===================================================================== */}
   445	
   446	      {/* Plugin Extra Sections (CivitaiPlugin: updates, CustomPlugin: pack deps, etc.) */}
   447	      {pluginContext && plugin?.renderExtraSections && (
   448	        <SectionErrorBoundary
   449	          sectionName={`${plugin.name || 'Plugin'} Sections`}
   450	          onRetry={packData.refetch}
   451	        >
   452	          {plugin.renderExtraSections(pluginContext)}
   453	        </SectionErrorBoundary>
   454	      )}
   455	
   456	      {/* Plugin Modals - wrapped in error boundary for safety */}
   457	      <ErrorBoundary
   458	        onError={(error) => {
   459	          console.error('[PackDetailPage] Plugin modal error:', error)
   460	        }}
   461	      >
   462	        {pluginContext && plugin?.renderModals?.(pluginContext)}
   463	      </ErrorBoundary>
   464	
   465	      {/* =====================================================================
   466	          MODALS
   467	          ===================================================================== */}
   468	
   469	      {/* Fullscreen Gallery Viewer */}
   470	      <FullscreenMediaViewer
   471	        isOpen={isFullscreenOpen}
   472	        items={mediaItems}
   473	        initialIndex={fullscreenIndex}
   474	        onClose={() => setFullscreenIndex(-1)}
   475	      />
   476	
   477	      {/* Edit Pack Modal (User Tags) */}
   478	      <EditPackModal
   479	        isOpen={modals.editPack}
   480	        initialTags={pack.user_tags}
   481	        onSave={(tags) => {
   482	          packData.updatePack({ user_tags: tags })
   483	          closeModal('editPack')
   484	        }}
   485	        onClose={() => closeModal('editPack')}
   486	        isSaving={packData.isUpdatingPack}
   487	      />
   488	
   489	      {/* Edit Parameters Modal */}
   490	      <EditParametersModal
   491	        isOpen={modals.editParameters}
   492	        initialParameters={
   493	          pack.parameters
   494	            ? Object.fromEntries(
   495	                Object.entries(pack.parameters).map(([k, v]) => [k, String(v ?? '')])
   496	              )
   497	            : {}
   498	        }
   499	        onSave={(params) => {
   500	          packData.updateParameters(params as Record<string, unknown>)
   501	          closeModal('editParameters')
   502	        }}
   503	        onClose={() => closeModal('editParameters')}
   504	        isSaving={packData.isUpdatingParameters}
   505	      />
   506	
   507	      {/* Upload Workflow Modal */}
   508	      <UploadWorkflowModal
   509	        isOpen={modals.uploadWorkflow}
   510	        onUpload={(data) => {
   511	          packData.uploadWorkflow(data)
   512	          closeModal('uploadWorkflow')
   513	        }}
   514	        onClose={() => closeModal('uploadWorkflow')}
   515	        isUploading={packData.isUploadingWorkflow}
   516	      />
   517	
   518	      {/* Dependency Resolver Modal */}
   519	      <DependencyResolverModal
   520	        isOpen={modals.dependencyResolver}

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/PackDetailPage.tsx | nl -ba | sed -n '518,580p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   518	      {/* Dependency Resolver Modal */}
   519	      <DependencyResolverModal
   520	        isOpen={modals.dependencyResolver}
   521	        onClose={() => {
   522	          closeModal('dependencyResolver')
   523	          setResolveDepId(null)
   524	        }}
   525	        packName={pack.name}
   526	        depId={resolveDepId || ''}
   527	        depName={resolveDepName}
   528	        kind={resolveDepKind}
   529	        candidates={resolveCandidates}
   530	        isSuggesting={packData.isSuggesting}
   531	        requestId={resolveRequestId}
   532	        onSuggest={handleSuggestResolution}
   533	        onApply={handleApplyResolution}
   534	        onApplyAndDownload={handleApplyAndDownload}
   535	        isApplying={packData.isApplying || packData.isApplyingAndDownloading}
   536	        avatarAvailable={avatarAvailable}
   537	      />
   538	
   539	      {/* Edit Previews Modal */}
   540	      <EditPreviewsModal
   541	        isOpen={modals.editPreviews}
   542	        previews={pack.previews}
   543	        coverUrl={pack.cover_url}
   544	        onSave={async (data) => {
   545	          try {
   546	            // Get deleted filenames from original pack
   547	            const deletedFilenames = data.removedIndices
   548	              ?.map(index => pack.previews[index]?.filename)
   549	              .filter(Boolean) as string[] | undefined
   550	
   551	            // Get new order (only existing files, not blob URLs)
   552	            const order = data.previews
   553	              .filter(p => !p.url?.startsWith('blob:'))
   554	              .map(p => p.filename)
   555	
   556	            // Get cover filename if changed
   557	            let coverFilename: string | undefined
   558	            const packCoverUrl = pack.cover_url
   559	            if (data.coverUrl && data.coverUrl !== packCoverUrl) {
   560	              const coverPreview = data.previews.find(p => p.url === data.coverUrl)
   561	              if (coverPreview?.filename && !coverPreview.url?.startsWith('blob:')) {
   562	                coverFilename = coverPreview.filename
   563	              }
   564	            }
   565	
   566	            // Single batch update - atomic, no race conditions
   567	            await packData.batchUpdatePreviews({
   568	              files: data.addedFiles,
   569	              order,
   570	              coverFilename,
   571	              deleted: deletedFilenames,
   572	            })
   573	
   574	            closeModal('editPreviews')
   575	          } catch (error) {
   576	            console.error('[PackDetailPage] Error saving previews:', error)
   577	          }
   578	        }}
   579	        onClose={() => closeModal('editPreviews')}
   580	        isSaving={packData.isBatchUpdatingPreviews}

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/hooks/usePreviewAnalysis.ts | nl -ba | sed -n '1,140p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * usePreviewAnalysis Hook
     3	 *
     4	 * Fetches preview analysis data (model hints + generation params) for a pack.
     5	 */
     6	
     7	import { useQuery } from '@tanstack/react-query'
     8	import type { PreviewAnalysisResponse } from '../types'
     9	
    10	export function usePreviewAnalysis(packName: string, enabled: boolean) {
    11	  return useQuery<PreviewAnalysisResponse>({
    12	    queryKey: ['pack', packName, 'preview-analysis'],
    13	    queryFn: async () => {
    14	      const res = await fetch(
    15	        `/api/packs/${encodeURIComponent(packName)}/preview-analysis`
    16	      )
    17	      if (!res.ok) {
    18	        const errText = await res.text()
    19	        throw new Error(`Failed to fetch preview analysis: ${errText}`)
    20	      }
    21	      return res.json()
    22	    },
    23	    enabled,
    24	    staleTime: 5 * 60 * 1000, // 5 min — data doesn't change until re-import
    25	  })
    26	}

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts | nl -ba | sed -n '1,120p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * useAvatarAvailable Hook
     3	 *
     4	 * Checks whether the AI avatar is available for dependency resolution.
     5	 * Used to conditionally show the "AI Resolve" tab in DependencyResolverModal.
     6	 */
     7	
     8	import { useQuery } from '@tanstack/react-query'
     9	import { avatarKeys, getAvatarStatus } from '@/lib/avatar/api'
    10	
    11	export function useAvatarAvailable() {
    12	  const { data: status } = useQuery({
    13	    queryKey: avatarKeys.status(),
    14	    queryFn: getAvatarStatus,
    15	    staleTime: 60_000, // Cache for 1 minute
    16	    retry: 1,
    17	  })
    18	
    19	  return {
    20	    avatarAvailable: status?.available ?? false,
    21	    activeProvider: status?.active_provider ?? null,
    22	  }
    23	}
    24	
    25	export default useAvatarAvailable

exec
/bin/bash -lc "git grep -n \"pytest.mark.skip\\|mock\\|MagicMock\\|TODO\\|NEEDS\\|skip\" feat/resolve-model-redesign -- tests/unit/store/test_evidence_providers.py tests/integration/test_ai_resolve_integration.py tests/e2e_resolve_real.py apps/web/e2e/resolve-dependency.spec.ts apps/web/e2e/helpers/resolve.helpers.ts | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
feat/resolve-model-redesign:apps/web/e2e/helpers/resolve.helpers.ts:2: * Shared helpers and mock data for resolve E2E tests.
feat/resolve-model-redesign:apps/web/e2e/helpers/resolve.helpers.ts:247: * Call in beforeEach to mock the backend completely.
feat/resolve-model-redesign:apps/web/e2e/helpers/resolve.helpers.ts:409:/** Navigate to the mock pack detail page */
feat/resolve-model-redesign:apps/web/e2e/resolve-dependency.spec.ts:2: * Dependency Resolution E2E — Tier 1 (offline, mocked backend)
feat/resolve-model-redesign:apps/web/e2e/resolve-dependency.spec.ts:224:    // Avatar is not available (mocked as stopped) → AI tab should be hidden
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:8:NOT MagicMock. Only the avatar engine (HTTP/subprocess) is mocked.
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:14:from unittest.mock import MagicMock, patch
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:42:# Fixtures: Real Pydantic objects (not MagicMock)
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:47:    """Create a mock pack with real-looking attributes."""
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:48:    pack = MagicMock()
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:58:    """Create a mock dependency with real-looking attributes."""
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:59:    dep = MagicMock()
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:64:    dep.expose = MagicMock()
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:253:    """Integration: AIEvidenceProvider calls mock avatar, gets correct hits."""
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:256:        """Create mock avatar that returns specific candidates."""
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:257:        avatar = MagicMock()
feat/resolve-model-redesign:tests/integration/test_ai_resolve_integration.py:374:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:5:from unittest.mock import MagicMock, patch
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:32:        "pack": MagicMock(name="test_pack"),
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:33:        "dependency": MagicMock(name="test_dep"),
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:77:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:85:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:86:        dep.lock = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:89:        # CivitaiModelVersion is a dataclass — mock with attributes
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:90:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:91:        mock_version = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:92:        mock_version.model_id = 100
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:93:        mock_version.id = 200
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:94:        mock_version.name = "Test Model"
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:95:        mock_version.base_model = "SDXL"
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:96:        mock_version.files = [{"id": 300, "hashes": {"SHA256": "abc123def456"}}]
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:97:        civitai.get_model_by_hash.return_value = mock_version
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:99:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:112:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:113:        dep.lock = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:116:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:119:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:134:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:135:        dep.lock = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:137:        dep.selector = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:142:        hf_file = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:146:        hf_client = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:147:        hf_client.get_repo_files.return_value = MagicMock(files=[hf_file])
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:149:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:152:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:171:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:172:        dep.lock = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:174:        dep.selector = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:179:        hf_file = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:183:        hf_client = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:184:        hf_client.get_repo_files.return_value = MagicMock(files=[hf_file])
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:186:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:189:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:201:    def test_hf_hash_skipped_for_non_eligible_kind(self):
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:202:        """HF hash lookup skipped for kinds like LORA."""
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:205:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:206:        dep.lock = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:208:        dep.selector = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:213:        hf_client = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:214:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:217:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:228:    def test_hf_hash_no_selector_skips(self):
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:229:        """No HF selector on dep → skip HF lookup."""
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:230:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:231:        dep.lock = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:233:        dep.selector = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:236:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:239:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:305:    def test_unresolvable_hints_skipped(self):
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:325:        """Create a mock CivitaiModelVersion dataclass."""
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:326:        v = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:335:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:338:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:365:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:374:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:416:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:419:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:443:        """Name search skips results with wrong model type."""
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:444:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:456:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:479:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:482:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:500:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:503:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:535:    def test_short_stem_skips_name_search(self):
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:536:        """Stems < 3 chars skip name search to avoid noisy results."""
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:537:        civitai = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:540:        ps = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:563:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:576:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:605:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:617:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:627:    """Create a mock TaskResult matching avatar.tasks.base.TaskResult."""
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:628:    tr = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:645:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:657:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:675:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:693:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:698:        pack = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:705:        dep = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:706:        dep.selector = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:708:        dep.expose = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:723:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:758:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:783:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:813:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:844:    def test_gather_skips_invalid_candidates(self):
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:845:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:866:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:877:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:888:        avatar = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_evidence_providers.py:898:        avatar = MagicMock()

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/e2e/resolve-dependency.spec.ts | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	/**
     2	 * Dependency Resolution E2E — Tier 1 (offline, mocked backend)
     3	 *
     4	 * Tests the full resolve flow: opening modal, viewing candidates,
     5	 * applying resolution, local file import, preview analysis tab.
     6	 * All API calls intercepted via page.route().
     7	 */
     8	
     9	import { test, expect } from '@playwright/test'
    10	import {
    11	  setupResolveRoutes,
    12	  setupLocalFileRoutes,
    13	  navigateToPackDetail,
    14	  MOCK_PACK_NAME,
    15	  MOCK_PACK_DETAIL,
    16	  MOCK_SUGGEST_RESULT,
    17	  MOCK_SUGGEST_EMPTY,
    18	  MOCK_APPLY_RESULT,
    19	} from './helpers/resolve.helpers'
    20	
    21	test.describe('Dependency Resolution', () => {
    22	  test.beforeEach(async ({ page }) => {
    23	    await setupResolveRoutes(page)
    24	  })
    25	
    26	  // ─── Modal Opening ──────────────────────────────────────────────
    27	
    28	  test('unresolved base model dep shows Select Model button', async ({ page }) => {
    29	    await navigateToPackDetail(page)
    30	
    31	    const selectBtn = page.getByRole('button', { name: 'Select Model' })
    32	    await expect(selectBtn).toBeVisible({ timeout: 10_000 })
    33	  })
    34	
    35	  test('clicking Select Model opens DependencyResolverModal', async ({ page }) => {
    36	    await navigateToPackDetail(page)
    37	
    38	    await page.getByRole('button', { name: 'Select Model' }).click()
    39	
    40	    // Modal should appear with dep name in header
    41	    await expect(page.getByText('base-checkpoint')).toBeVisible({ timeout: 5_000 })
    42	    // Should have tab buttons
    43	    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible()
    44	  })
    45	
    46	  test('modal shows candidates from eager suggest', async ({ page }) => {
    47	    await navigateToPackDetail(page)
    48	    await page.getByRole('button', { name: 'Select Model' }).click()
    49	
    50	    // Wait for candidates to load (eager suggest fires on modal open)
    51	    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    52	    await expect(page.getByText('Animagine XL 3.1')).toBeVisible()
    53	  })
    54	
    55	  test('modal shows candidate count badge on tab', async ({ page }) => {
    56	    await navigateToPackDetail(page)
    57	    await page.getByRole('button', { name: 'Select Model' }).click()
    58	
    59	    // Candidates tab should show count
    60	    const candidatesTab = page.getByRole('button', { name: /Candidates/i })
    61	    await expect(candidatesTab).toBeVisible({ timeout: 10_000 })
    62	    // Badge with "2" for two candidates
    63	    await expect(candidatesTab).toContainText('2')
    64	  })
    65	
    66	  // ─── Candidate Selection & Apply ─────────────────────────────────
    67	
    68	  test('clicking a candidate selects it', async ({ page }) => {
    69	    await navigateToPackDetail(page)
    70	    await page.getByRole('button', { name: 'Select Model' }).click()
    71	    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    72	
    73	    // Click the first candidate
    74	    await page.getByText('Illustrious XL v0.6').click()
    75	
    76	    // Apply button should be enabled
    77	    const applyBtn = page.getByRole('button', { name: /^Apply$/i })
    78	    await expect(applyBtn).toBeEnabled()
    79	  })
    80	
    81	  test('Apply sends apply-resolution request and closes modal', async ({ page }) => {
    82	    let applyCallMade = false
    83	    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
    84	      applyCallMade = true
    85	      route.fulfill({
    86	        status: 200,
    87	        contentType: 'application/json',
    88	        body: JSON.stringify(MOCK_APPLY_RESULT),
    89	      })
    90	    })
    91	
    92	    await navigateToPackDetail(page)
    93	    await page.getByRole('button', { name: 'Select Model' }).click()
    94	    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    95	    await page.getByText('Illustrious XL v0.6').click()
    96	
    97	    await page.getByRole('button', { name: /^Apply$/i }).click()
    98	
    99	    // Modal should close after apply
   100	    await expect(page.getByText('Illustrious XL v0.6')).toBeHidden({ timeout: 5_000 })
   101	    expect(applyCallMade).toBe(true)
   102	  })
   103	
   104	  test('Apply & Download sends request and closes modal', async ({ page }) => {
   105	    let applyCallMade = false
   106	    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
   107	      applyCallMade = true
   108	      route.fulfill({
   109	        status: 200,
   110	        contentType: 'application/json',
   111	        body: JSON.stringify(MOCK_APPLY_RESULT),
   112	      })
   113	    })
   114	
   115	    await navigateToPackDetail(page)
   116	    await page.getByRole('button', { name: 'Select Model' }).click()
   117	    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
   118	    await page.getByText('Illustrious XL v0.6').click()
   119	
   120	    await page.getByRole('button', { name: /Apply & Download/i }).click()
   121	
   122	    // Apply & Download may close modal or keep it open while downloading
   123	    await page.waitForTimeout(2000)
   124	    expect(applyCallMade).toBe(true)
   125	  })
   126	
   127	  // ─── Confidence Tiers ────────────────────────────────────────────
   128	
   129	  test('candidates show confidence tier badges', async ({ page }) => {
   130	    await navigateToPackDetail(page)
   131	    await page.getByRole('button', { name: 'Select Model' }).click()
   132	    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
   133	
   134	    // Tier 2 candidate should show "High confidence" indicator
   135	    await expect(page.getByText(/High confidence/i).or(page.getByText(/88%/i))).toBeVisible()
   136	  })
   137	
   138	  // ─── Empty State ─────────────────────────────────────────────────
   139	
   140	  test('no candidates shows empty state', async ({ page }) => {
   141	    // Override with empty suggest
   142	    await page.route(`**/api/packs/${MOCK_PACK_NAME}/suggest-resolution`, (route) => {
   143	      route.fulfill({
   144	        status: 200,
   145	        contentType: 'application/json',
   146	        body: JSON.stringify(MOCK_SUGGEST_EMPTY),
   147	      })
   148	    })
   149	
   150	    await navigateToPackDetail(page)
   151	    await page.getByRole('button', { name: 'Select Model' }).click()
   152	
   153	    // Should show empty/no candidates message or default to preview tab
   154	    const candidatesTab = page.getByRole('button', { name: /Candidates/i })
   155	    await expect(candidatesTab).toBeVisible({ timeout: 10_000 })
   156	  })
   157	
   158	  // ─── Tab Navigation ──────────────────────────────────────────────
   159	
   160	  test('can switch between modal tabs', async ({ page }) => {
   161	    await navigateToPackDetail(page)
   162	    await page.getByRole('button', { name: 'Select Model' }).click()
   163	    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })
   164	
   165	    // Switch to Preview tab
   166	    const previewTab = page.getByRole('button', { name: /Preview/i })
   167	    if (await previewTab.isVisible()) {
   168	      await previewTab.click()
   169	      // Preview content should appear (thumbnail grid or loading)
   170	      await page.waitForTimeout(500)
   171	    }
   172	
   173	    // Switch to Local File tab
   174	    const localTab = page.getByRole('button', { name: /Local/i })
   175	    if (await localTab.isVisible()) {
   176	      await localTab.click()
   177	      // Should see directory input (use specific placeholder)
   178	      await expect(page.locator('input[type="text"]').last()).toBeVisible()
   179	    }
   180	
   181	    // Switch to Civitai tab
   182	    const civitaiTab = page.getByRole('button', { name: /Civitai/i })
   183	    if (await civitaiTab.isVisible()) {
   184	      await civitaiTab.click()
   185	    }
   186	  })
   187	
   188	  test('HuggingFace tab visible for checkpoint (HF-eligible)', async ({ page }) => {
   189	    await navigateToPackDetail(page)
   190	    await page.getByRole('button', { name: 'Select Model' }).click()
   191	    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })
   192	
   193	    // Checkpoint is HF-eligible → HF tab should be visible
   194	    await expect(page.getByRole('button', { name: /HuggingFace/i })).toBeVisible()
   195	  })
   196	
   197	  test('HuggingFace tab hidden for LoRA (not HF-eligible)', async ({ page }) => {
   198	    // Override pack: make the unresolved dep a LoRA instead of checkpoint
   199	    const loraAssets = MOCK_PACK_DETAIL.assets.map(a =>
   200	      a.name === 'base-checkpoint'
   201	        ? { ...a, asset_type: 'lora', is_base_model: false }
   202	        : a
   203	    )
   204	    await setupResolveRoutes(page, {
   205	      packDetail: { ...MOCK_PACK_DETAIL, assets: loraAssets },
   206	    })
   207	
   208	    await navigateToPackDetail(page)
   209	    // For non-base-model LoRA, the button should say "Resolve" not "Select Model"
   210	    await page.getByRole('button', { name: 'Resolve' }).click()
   211	    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })
   212	
   213	    // LoRA is NOT HF-eligible → HF tab should be hidden
   214	    await expect(page.getByRole('button', { name: /HuggingFace/i })).toBeHidden()
   215	  })
   216	
   217	  // ─── AI Tab Gate ─────────────────────────────────────────────────
   218	
   219	  test('AI Resolve tab hidden when avatar not available', async ({ page }) => {
   220	    await navigateToPackDetail(page)
   221	    await page.getByRole('button', { name: 'Select Model' }).click()
   222	    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })
   223	
   224	    // Avatar is not available (mocked as stopped) → AI tab should be hidden
   225	    await expect(page.getByRole('button', { name: /AI Resolve/i })).toBeHidden()
   226	  })
   227	
   228	  test('AI Resolve tab visible when avatar is available', async ({ page }) => {
   229	    // Override avatar status to available
   230	    await page.route('**/api/avatar/status', (route) => {
   231	      route.fulfill({
   232	        status: 200,
   233	        contentType: 'application/json',
   234	        body: JSON.stringify({ state: 'ready', available: true, enabled: true }),
   235	      })
   236	    })
   237	
   238	    await navigateToPackDetail(page)
   239	    await page.getByRole('button', { name: 'Select Model' }).click()
   240	    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })
   241	
   242	    await expect(page.getByRole('button', { name: /AI Resolve/i })).toBeVisible()
   243	  })
   244	
   245	  // ─── Cancel/Close ────────────────────────────────────────────────
   246	
   247	  test('Cancel button closes modal without applying', async ({ page }) => {
   248	    let applyCallMade = false
   249	    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
   250	      applyCallMade = true
   251	      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
   252	    })
   253	
   254	    await navigateToPackDetail(page)
   255	    await page.getByRole('button', { name: 'Select Model' }).click()
   256	    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
   257	
   258	    await page.getByRole('button', { name: /Cancel/i }).click()
   259	
   260	    // Modal should close

exec
/bin/bash -lc "git show feat/resolve-model-redesign:tests/e2e_resolve_real.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	#!/usr/bin/env python3
     2	"""
     3	Real E2E test: AI-powered dependency resolution with live providers.
     4	
     5	Tests the full suggest pipeline with REAL AI providers (Gemini, Claude/Opus, Codex)
     6	against 5 test scenarios:
     7	  - 3 base model checkpoints (SDXL, Illustrious, Flux.1 Dev)
     8	  - 2 LoRAs (anime style LoRA, realistic photo LoRA)
     9	
    10	Usage:
    11	  uv run python tests/e2e_resolve_real.py
    12	
    13	Requirements:
    14	  - gemini, claude, codex CLIs installed
    15	  - Valid auth for each provider
    16	  - avatar-engine skills in config/avatar/skills/
    17	"""
    18	
    19	from __future__ import annotations
    20	
    21	import json
    22	import logging
    23	import sys
    24	import time
    25	from dataclasses import dataclass, field
    26	from pathlib import Path
    27	from typing import Any, Dict, List, Optional
    28	
    29	# Add project root to path
    30	sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    31	
    32	from src.avatar.config import load_avatar_config, AvatarConfig
    33	from src.avatar.task_service import AvatarTaskService
    34	from src.store.evidence_providers import AIEvidenceProvider
    35	from src.store.models import (
    36	    AssetKind,
    37	    DependencySelector,
    38	    ExposeConfig,
    39	    Pack,
    40	    PackDependency,
    41	    PackSource,
    42	    ProviderName,
    43	    SelectorStrategy,
    44	)
    45	from src.store.resolve_config import AI_CONFIDENCE_CEILING
    46	from src.store.resolve_models import (
    47	    ResolveContext,
    48	    SuggestOptions,
    49	    PreviewModelHint,
    50	)
    51	from src.store.resolve_service import ResolveService
    52	
    53	logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    54	logger = logging.getLogger("e2e_resolve")
    55	logger.setLevel(logging.INFO)
    56	# Enable task-service debug for diagnostics
    57	logging.getLogger("src.avatar.task_service").setLevel(logging.DEBUG)
    58	
    59	
    60	# =============================================================================
    61	# Test Scenarios
    62	# =============================================================================
    63	
    64	@dataclass
    65	class TestScenario:
    66	    """A test scenario for dependency resolution."""
    67	    name: str
    68	    pack_type: str
    69	    base_model: str
    70	    dep_id: str
    71	    dep_kind: AssetKind
    72	    expose_filename: str
    73	    description: str
    74	    tags: list[str] = field(default_factory=list)
    75	    preview_hints: list[dict] = field(default_factory=list)
    76	    # Expected: what we consider a "correct" resolution
    77	    expected_providers: list[str] = field(default_factory=list)  # civitai, huggingface
    78	    expected_keywords: list[str] = field(default_factory=list)  # keywords in display_name
    79	
    80	
    81	SCENARIOS: list[TestScenario] = [
    82	    # --- 3 Base Models ---
    83	    TestScenario(
    84	        name="SDXL Base Checkpoint",
    85	        pack_type="lora",
    86	        base_model="SDXL",
    87	        dep_id="base_checkpoint",
    88	        dep_kind=AssetKind.CHECKPOINT,
    89	        expose_filename="sd_xl_base_1.0.safetensors",
    90	        description="Anime LoRA trained on SDXL base model. Requires SDXL 1.0 checkpoint.",
    91	        tags=["anime", "sdxl", "style"],
    92	        preview_hints=[
    93	            {"filename": "sd_xl_base_1.0.safetensors", "raw_value": "SDXL Base 1.0",
    94	             "source_type": "api_meta"},
    95	        ],
    96	        expected_providers=["civitai", "huggingface"],
    97	        expected_keywords=["sdxl", "xl", "base", "1.0"],
    98	    ),
    99	    TestScenario(
   100	        name="Illustrious XL Checkpoint",
   101	        pack_type="lora",
   102	        base_model="Illustrious",
   103	        dep_id="base_checkpoint",
   104	        dep_kind=AssetKind.CHECKPOINT,
   105	        expose_filename="illustriousXL_v060.safetensors",
   106	        description="Anime character LoRA based on Illustrious XL. High quality illustration style.",
   107	        tags=["anime", "illustrious", "character"],
   108	        preview_hints=[
   109	            {"filename": "illustriousXL_v060.safetensors", "raw_value": "Illustrious XL v0.60",
   110	             "source_type": "api_meta"},
   111	        ],
   112	        expected_providers=["civitai"],
   113	        expected_keywords=["illustrious"],
   114	    ),
   115	    TestScenario(
   116	        name="Flux.1 Dev Checkpoint",
   117	        pack_type="lora",
   118	        base_model="Flux.1 D",
   119	        dep_id="base_checkpoint",
   120	        dep_kind=AssetKind.CHECKPOINT,
   121	        expose_filename="flux1-dev.safetensors",
   122	        description="Flux LoRA for photorealistic generation. Requires Flux.1 Dev checkpoint from Black Forest Labs.",
   123	        tags=["flux", "photorealistic", "realistic"],
   124	        preview_hints=[
   125	            {"filename": "flux1-dev.safetensors", "raw_value": "FLUX.1 [dev]",
   126	             "source_type": "api_meta"},
   127	        ],
   128	        expected_providers=["huggingface"],
   129	        expected_keywords=["flux", "dev", "black-forest"],
   130	    ),
   131	    # --- 2 LoRAs ---
   132	    TestScenario(
   133	        name="Detail Tweaker LoRA (SDXL)",
   134	        pack_type="checkpoint",
   135	        base_model="SDXL",
   136	        dep_id="detail_lora",
   137	        dep_kind=AssetKind.LORA,
   138	        expose_filename="add-detail-xl.safetensors",
   139	        description="SDXL checkpoint pack. Uses Detail Tweaker XL LoRA for enhanced detail rendering.",
   140	        tags=["sdxl", "detail", "enhancer"],
   141	        preview_hints=[
   142	            {"filename": "add-detail-xl.safetensors", "raw_value": "Detail Tweaker XL",
   143	             "source_type": "api_meta"},
   144	        ],
   145	        expected_providers=["civitai"],
   146	        expected_keywords=["detail", "tweaker"],
   147	    ),
   148	    TestScenario(
   149	        name="Pony Diffusion V6 XL (LoRA dependency)",
   150	        pack_type="lora",
   151	        base_model="Pony",
   152	        dep_id="base_checkpoint",
   153	        dep_kind=AssetKind.CHECKPOINT,
   154	        expose_filename="ponyDiffusionV6XL.safetensors",
   155	        description="Anime LoRA trained on Pony Diffusion V6 XL. Requires the Pony V6 checkpoint.",
   156	        tags=["pony", "anime", "pdxl"],
   157	        preview_hints=[
   158	            {"filename": "ponyDiffusionV6XL.safetensors", "raw_value": "Pony Diffusion V6 XL",
   159	             "source_type": "api_meta"},
   160	        ],
   161	        expected_providers=["civitai"],
   162	        expected_keywords=["pony", "diffusion", "v6"],
   163	    ),
   164	]
   165	
   166	
   167	# =============================================================================
   168	# Test Runner
   169	# =============================================================================
   170	
   171	@dataclass
   172	class CandidateResult:
   173	    display_name: str
   174	    provider: str
   175	    confidence: float
   176	    base_model: str
   177	    reasoning: str
   178	
   179	
   180	@dataclass
   181	class TestResult:
   182	    scenario: str
   183	    provider_name: str
   184	    success: bool
   185	    candidates: list[CandidateResult]
   186	    top_match: str
   187	    top_confidence: float
   188	    correct: bool  # Does top match look correct?
   189	    duration_s: float
   190	    error: str = ""
   191	    warnings: list[str] = field(default_factory=list)
   192	
   193	
   194	def _build_pack(scenario: TestScenario) -> Pack:
   195	    """Build a minimal Pack object for the scenario."""
   196	    return Pack(
   197	        schema="1.0",
   198	        name=f"test-{scenario.name.lower().replace(' ', '-')}",
   199	        pack_type=scenario.pack_type,
   200	        source=PackSource(provider=ProviderName.CIVITAI, model_id=99999),
   201	        base_model=scenario.base_model,
   202	        description=scenario.description,
   203	        tags=scenario.tags,
   204	        dependencies=[
   205	            PackDependency(
   206	                id=scenario.dep_id,
   207	                kind=scenario.dep_kind,
   208	                required=True,
   209	                selector=DependencySelector(
   210	                    strategy=SelectorStrategy.BASE_MODEL_HINT,
   211	                    base_model=scenario.base_model,
   212	                ),
   213	                expose=ExposeConfig(filename=scenario.expose_filename),
   214	            ),
   215	        ],
   216	    )
   217	
   218	
   219	def _build_context(scenario: TestScenario, pack: Pack) -> ResolveContext:
   220	    """Build ResolveContext for the scenario."""
   221	    dep = pack.dependencies[0]
   222	    hints = [
   223	        PreviewModelHint(
   224	            filename=h["filename"],
   225	            raw_value=h["raw_value"],
   226	            source_type=h["source_type"],
   227	            source_image=h.get("source_image", "preview_001.png"),
   228	        )
   229	        for h in scenario.preview_hints
   230	    ]
   231	    return ResolveContext(
   232	        pack=pack,
   233	        dependency=dep,
   234	        kind=scenario.dep_kind,
   235	        preview_hints=hints,
   236	    )
   237	
   238	
   239	def _evaluate_correctness(scenario: TestScenario, candidates: list[dict]) -> bool:
   240	    """Check if top candidate looks correct based on expected keywords."""
   241	    if not candidates:
   242	        return False
   243	    top = candidates[0]
   244	    name = (top.get("display_name", "") or "").lower()
   245	    # Check if any expected keyword appears in the display name
   246	    return any(kw.lower() in name for kw in scenario.expected_keywords)
   247	
   248	
   249	def run_scenario_with_provider(
   250	    scenario: TestScenario,
   251	    provider_name: str,
   252	) -> TestResult:
   253	    """Run a single scenario with a specific AI provider."""
   254	    pack = _build_pack(scenario)
   255	    ctx = _build_context(scenario, pack)
   256	
   257	    # Create fresh config for each run to avoid state leakage
   258	    config = load_avatar_config()
   259	    config.extraction.cache_enabled = False
   260	    config.provider = provider_name

exec
/bin/bash -lc "git show feat/resolve-model-redesign:tests/e2e_resolve_real.py | nl -ba | sed -n '260,520p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   260	    config.provider = provider_name
   261	    avatar = AvatarTaskService(config=config)
   262	
   263	    # Create AIEvidenceProvider directly
   264	    ai_provider = AIEvidenceProvider(avatar_getter=lambda: avatar)
   265	
   266	    start = time.time()
   267	    try:
   268	        result = ai_provider.gather(ctx)
   269	        duration = time.time() - start
   270	
   271	        # Extract candidates from EvidenceHit objects
   272	        candidates = []
   273	        for hit in result.hits:
   274	            candidates.append({
   275	                "display_name": hit.candidate.display_name or hit.candidate.key,
   276	                "provider": hit.candidate.provider_name or "unknown",
   277	                "confidence": hit.item.confidence,
   278	                "base_model": "",  # Not directly on EvidenceHit
   279	                "reasoning": hit.item.raw_value or hit.item.description,
   280	            })
   281	
   282	        # Sort by confidence
   283	        candidates.sort(key=lambda c: c["confidence"], reverse=True)
   284	
   285	        correct = _evaluate_correctness(scenario, candidates)
   286	        top = candidates[0] if candidates else {}
   287	
   288	        return TestResult(
   289	            scenario=scenario.name,
   290	            provider_name=provider_name,
   291	            success=True,
   292	            candidates=[
   293	                CandidateResult(
   294	                    display_name=c["display_name"],
   295	                    provider=c["provider"],
   296	                    confidence=c["confidence"],
   297	                    base_model=c["base_model"],
   298	                    reasoning=c.get("reasoning", ""),
   299	                )
   300	                for c in candidates[:5]
   301	            ],
   302	            top_match=top.get("display_name", "NONE"),
   303	            top_confidence=top.get("confidence", 0.0),
   304	            correct=correct,
   305	            duration_s=duration,
   306	            warnings=result.warnings,
   307	        )
   308	    except Exception as e:
   309	        duration = time.time() - start
   310	        return TestResult(
   311	            scenario=scenario.name,
   312	            provider_name=provider_name,
   313	            success=False,
   314	            candidates=[],
   315	            top_match="ERROR",
   316	            top_confidence=0.0,
   317	            correct=False,
   318	            duration_s=duration,
   319	            error=str(e),
   320	        )
   321	
   322	
   323	# =============================================================================
   324	# Main
   325	# =============================================================================
   326	
   327	# claude excluded: bridge process exits in non-interactive context (sandbox limitation)
   328	PROVIDERS = ["gemini", "codex"]
   329	
   330	
   331	def main():
   332	    results: list[TestResult] = []
   333	
   334	    total = len(SCENARIOS) * len(PROVIDERS)
   335	    idx = 0
   336	
   337	    for scenario in SCENARIOS:
   338	        for provider in PROVIDERS:
   339	            idx += 1
   340	            logger.info(
   341	                "[%d/%d] %s x %s ...",
   342	                idx, total, scenario.name, provider,
   343	            )
   344	            result = run_scenario_with_provider(scenario, provider)
   345	            results.append(result)
   346	
   347	            status = "PASS" if result.correct else ("FAIL" if result.success else "ERR")
   348	            logger.info(
   349	                "  → %s  top=%s  conf=%.0f%%  %.1fs",
   350	                status,
   351	                result.top_match[:40],
   352	                result.top_confidence * 100,
   353	                result.duration_s,
   354	            )
   355	
   356	    # Print results table
   357	    print("\n" + "=" * 120)
   358	    print("RESOLVE MODEL E2E TEST RESULTS")
   359	    print("=" * 120)
   360	    print(
   361	        f"{'Scenario':<30} {'Provider':<10} {'Status':<6} "
   362	        f"{'Top Match':<40} {'Conf':<6} {'Time':<7} {'Correct':<8}"
   363	    )
   364	    print("-" * 120)
   365	
   366	    pass_count = 0
   367	    fail_count = 0
   368	    err_count = 0
   369	
   370	    for r in results:
   371	        status = "PASS" if r.correct else ("FAIL" if r.success else "ERR")
   372	        if r.correct:
   373	            pass_count += 1
   374	        elif r.success:
   375	            fail_count += 1
   376	        else:
   377	            err_count += 1
   378	
   379	        print(
   380	            f"{r.scenario:<30} {r.provider_name:<10} {status:<6} "
   381	            f"{r.top_match[:38]:<40} {r.top_confidence*100:>4.0f}%  "
   382	            f"{r.duration_s:>5.1f}s  {'YES' if r.correct else 'NO':>5}"
   383	        )
   384	
   385	    print("-" * 120)
   386	    print(
   387	        f"Total: {len(results)} tests | "
   388	        f"PASS: {pass_count} | FAIL: {fail_count} | ERR: {err_count} | "
   389	        f"AI ceiling: {AI_CONFIDENCE_CEILING*100:.0f}%"
   390	    )
   391	    print("=" * 120)
   392	
   393	    # Detailed results
   394	    print("\n\nDETAILED CANDIDATES:")
   395	    print("=" * 120)
   396	    for r in results:
   397	        if not r.candidates:
   398	            continue
   399	        print(f"\n{r.scenario} x {r.provider_name}:")
   400	        for i, c in enumerate(r.candidates[:3], 1):
   401	            print(
   402	                f"  #{i} [{c.provider}] {c.display_name} "
   403	                f"(conf={c.confidence*100:.0f}%, base={c.base_model})"
   404	            )
   405	            if c.reasoning:
   406	                print(f"      → {c.reasoning[:80]}")
   407	        if r.warnings:
   408	            print(f"  Warnings: {r.warnings}")
   409	        if r.error:
   410	            print(f"  Error: {r.error}")
   411	
   412	    # Exit code
   413	    sys.exit(0 if err_count == 0 else 1)
   414	
   415	
   416	if __name__ == "__main__":
   417	    main()

exec
/bin/bash -lc "git show feat/resolve-model-redesign:tests/integration/test_resolve_integration.py | nl -ba | sed -n '1,240p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Integration tests — ResolveService suggest/apply lifecycle with real components.
     3	
     4	Tests real ResolveService + mock PackService/Layout, verifying:
     5	- suggest → apply round-trip
     6	- Multi-provider evidence merge
     7	- Stale fingerprint detection
     8	- Config-based AI gate
     9	- Alias provider reads from config
    10	"""
    11	
    12	import pytest
    13	from unittest.mock import MagicMock, patch
    14	
    15	from src.store.models import (
    16	    AssetKind,
    17	    CivitaiSelector,
    18	    DependencySelector,
    19	    SelectorStrategy,
    20	    ResolveConfig,
    21	)
    22	from src.store.resolve_config import get_auto_apply_margin, is_ai_enabled
    23	from src.store.resolve_models import (
    24	    CandidateSeed,
    25	    EvidenceGroup,
    26	    EvidenceHit,
    27	    EvidenceItem,
    28	    ResolutionCandidate,
    29	    ResolveContext,
    30	    SuggestOptions,
    31	    SuggestResult,
    32	)
    33	from src.store.resolve_service import ResolveService
    34	
    35	
    36	# --- Helpers ---
    37	
    38	def _make_dep(kind=AssetKind.CHECKPOINT, filename="model.safetensors", sha256=None):
    39	    dep = MagicMock()
    40	    dep.id = "dep-1"
    41	    dep.kind = kind
    42	    dep.name = filename
    43	    dep.expose = MagicMock()
    44	    dep.expose.filename = filename
    45	    dep.lock = MagicMock()
    46	    dep.lock.sha256 = sha256
    47	    dep.selector = DependencySelector(strategy=SelectorStrategy.BASE_MODEL_HINT)
    48	    dep.base_model = "SDXL"
    49	    dep._preview_hints = []
    50	    return dep
    51	
    52	
    53	def _make_pack(deps=None, base_model="SDXL"):
    54	    pack = MagicMock()
    55	    pack.name = "test-pack"
    56	    pack.base_model = base_model
    57	    pack.dependencies = deps or [_make_dep()]
    58	    return pack
    59	
    60	
    61	def _make_service(providers=None, config=None):
    62	    """Create ResolveService with mock pack_service and layout."""
    63	    layout = MagicMock()
    64	    layout.load_pack.return_value = _make_pack()
    65	    ps = MagicMock()
    66	    ps.layout = layout
    67	
    68	    config_getter = (lambda: config) if config else None
    69	    return ResolveService(
    70	        layout=layout,
    71	        pack_service=ps,
    72	        providers=providers or {},
    73	        config_getter=config_getter,
    74	    )
    75	
    76	
    77	class FakeProvider:
    78	    """Configurable fake evidence provider for testing."""
    79	
    80	    def __init__(self, tier=1, hits=None, error=None):
    81	        self.tier = tier
    82	        self._hits = hits or []
    83	        self._error = error
    84	
    85	    def supports(self, ctx):
    86	        return True
    87	
    88	    def gather(self, ctx):
    89	        from src.store.resolve_models import ProviderResult
    90	        return ProviderResult(hits=self._hits, error=self._error)
    91	
    92	
    93	def _make_hit(key="civitai:100:200", provenance="hash:abc", confidence=0.95, base_model=None):
    94	    seed = CandidateSeed(
    95	        key=key,
    96	        selector=DependencySelector(
    97	            strategy=SelectorStrategy.CIVITAI_FILE,
    98	            civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
    99	        ),
   100	        display_name="Test Model",
   101	        base_model=base_model,
   102	    )
   103	    return EvidenceHit(
   104	        candidate=seed,
   105	        provenance=provenance,
   106	        item=EvidenceItem(
   107	            source="hash_match",
   108	            description="test",
   109	            confidence=confidence,
   110	            raw_value="abc",
   111	        ),
   112	    )
   113	
   114	
   115	# =============================================================================
   116	# Suggest → Apply lifecycle
   117	# =============================================================================
   118	
   119	class TestSuggestApplyLifecycle:
   120	    """Integration: suggest produces candidates, apply consumes them."""
   121	
   122	    def test_suggest_then_apply_succeeds(self):
   123	        hit = _make_hit(confidence=0.95)
   124	        service = _make_service(providers={"hash": FakeProvider(hits=[hit])})
   125	
   126	        pack = _make_pack()
   127	        result = service.suggest(pack, "dep-1")
   128	
   129	        assert len(result.candidates) == 1
   130	        assert result.candidates[0].confidence == 0.95
   131	
   132	        # Apply the top candidate
   133	        apply_result = service.apply(
   134	            "test-pack", "dep-1", result.candidates[0].candidate_id,
   135	            request_id=result.request_id,
   136	        )
   137	        assert apply_result.success
   138	
   139	    def test_apply_without_suggest_fails(self):
   140	        service = _make_service()
   141	        result = service.apply("test-pack", "dep-1", "nonexistent-id")
   142	        assert not result.success
   143	        assert "not found" in result.message.lower()
   144	
   145	    def test_suggest_merges_same_key_from_different_providers(self):
   146	        """Two providers returning same candidate key → merged, higher confidence."""
   147	        hit1 = _make_hit(key="civitai:100:200", provenance="hash:abc", confidence=0.95)
   148	        hit2 = _make_hit(key="civitai:100:200", provenance="preview:img.jpg", confidence=0.70)
   149	
   150	        service = _make_service(providers={
   151	            "hash": FakeProvider(tier=1, hits=[hit1]),
   152	            "preview": FakeProvider(tier=2, hits=[hit2]),
   153	        })
   154	
   155	        result = service.suggest(_make_pack(), "dep-1")
   156	        assert len(result.candidates) == 1
   157	        # Merged confidence should be higher than either individual
   158	        assert result.candidates[0].confidence > 0.95
   159	
   160	    def test_suggest_returns_multiple_candidates(self):
   161	        """Different candidate keys → separate candidates, sorted by confidence."""
   162	        hit1 = _make_hit(key="civitai:100:200", confidence=0.95)
   163	        hit2 = _make_hit(key="civitai:300:400", confidence=0.60)
   164	        hit2.candidate = CandidateSeed(
   165	            key="civitai:300:400",
   166	            selector=DependencySelector(
   167	                strategy=SelectorStrategy.CIVITAI_FILE,
   168	                civitai=CivitaiSelector(model_id=300, version_id=400, file_id=500),
   169	            ),
   170	            display_name="Other Model",
   171	        )
   172	
   173	        service = _make_service(providers={"hash": FakeProvider(hits=[hit1, hit2])})
   174	        result = service.suggest(_make_pack(), "dep-1")
   175	
   176	        assert len(result.candidates) == 2
   177	        assert result.candidates[0].confidence > result.candidates[1].confidence
   178	
   179	
   180	# =============================================================================
   181	# Config-based features
   182	# =============================================================================
   183	
   184	class TestConfigIntegration:
   185	    """Integration: config affects resolution behavior."""
   186	
   187	    def test_get_auto_apply_margin_from_config(self):
   188	        config = MagicMock()
   189	        config.resolve = ResolveConfig(auto_apply_margin=0.25)
   190	        assert get_auto_apply_margin(config) == 0.25
   191	
   192	    def test_get_auto_apply_margin_fallback(self):
   193	        assert get_auto_apply_margin(None) == 0.15
   194	
   195	    def test_is_ai_enabled_from_config(self):
   196	        config = MagicMock()
   197	        config.resolve = ResolveConfig(enable_ai=False)
   198	        assert is_ai_enabled(config) is False
   199	
   200	    def test_is_ai_enabled_default_true(self):
   201	        assert is_ai_enabled(None) is True
   202	
   203	    def test_ai_provider_disabled_by_config(self):
   204	        """AIEvidenceProvider.supports() returns False when config disables AI."""
   205	        from src.store.evidence_providers import AIEvidenceProvider
   206	
   207	        config = MagicMock()
   208	        config.resolve = ResolveConfig(enable_ai=False)
   209	
   210	        provider = AIEvidenceProvider(
   211	            avatar_getter=lambda: MagicMock(),
   212	            config_getter=lambda: config,
   213	        )
   214	        ctx = MagicMock()
   215	        assert provider.supports(ctx) is False
   216	
   217	    def test_ai_provider_enabled_by_default(self):
   218	        from src.store.evidence_providers import AIEvidenceProvider
   219	
   220	        provider = AIEvidenceProvider(
   221	            avatar_getter=lambda: MagicMock(),
   222	            config_getter=None,
   223	        )
   224	        ctx = MagicMock()
   225	        assert provider.supports(ctx) is True
   226	
   227	    def test_resolve_config_default_values(self):
   228	        rc = ResolveConfig()
   229	        assert rc.auto_apply_margin == 0.15
   230	        assert rc.enable_ai is True
   231	
   232	
   233	# =============================================================================
   234	# Alias provider
   235	# =============================================================================
   236	
   237	class TestAliasProviderIntegration:
   238	    """Integration: AliasEvidenceProvider reads from config.json."""
   239	
   240	    def test_read_aliases_from_config(self):

exec
/bin/bash -lc "git show feat/resolve-model-redesign:tests/integration/test_resolve_smoke.py | nl -ba | sed -n '1,180p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Smoke tests — full resolve lifecycle with real Store (tmp_path).
     3	
     4	Tests the complete suggest/auto-apply flow as it runs during import,
     5	using real Store + mock deps.
     6	"""
     7	
     8	import pytest
     9	from unittest.mock import MagicMock
    10	
    11	from src.store.models import (
    12	    DependencySelector,
    13	    SelectorStrategy,
    14	    ResolveConfig,
    15	)
    16	
    17	
    18	# --- Fixtures ---
    19	
    20	@pytest.fixture
    21	def minimal_store(tmp_path):
    22	    """Create a minimal Store with real layout for resolve testing."""
    23	    from src.store import Store
    24	    store = Store(root=tmp_path)
    25	    return store
    26	
    27	
    28	# =============================================================================
    29	# Auto-apply flow
    30	# =============================================================================
    31	
    32	class TestAutoApplyFlow:
    33	    """Smoke: _post_import_resolve auto-applies dominant candidates."""
    34	
    35	    def test_post_import_resolve_with_no_deps(self, minimal_store):
    36	        """Pack with no dependencies should not crash."""
    37	        pack = MagicMock()
    38	        pack.name = "empty-pack"
    39	        pack.dependencies = []
    40	
    41	        minimal_store._post_import_resolve(pack)
    42	
    43	    def test_post_import_resolve_skips_pinned_deps(self, minimal_store):
    44	        """Dependencies with non-BASE_MODEL_HINT strategy are skipped."""
    45	        dep = MagicMock()
    46	        dep.id = "dep-1"
    47	        dep.selector = DependencySelector(strategy=SelectorStrategy.CIVITAI_FILE)
    48	
    49	        pack = MagicMock()
    50	        pack.name = "pinned-pack"
    51	        pack.dependencies = [dep]
    52	        pack.previews = []
    53	
    54	        # Should complete without errors — pinned deps are skipped
    55	        minimal_store._post_import_resolve(pack)
    56	
    57	
    58	# =============================================================================
    59	# Migration helper
    60	# =============================================================================
    61	
    62	class TestMigrationHelper:
    63	    """Smoke: migrate_resolve_deps iterates packs and reports actions."""
    64	
    65	    def test_migrate_dry_run_empty_store(self, minimal_store):
    66	        """Empty store → empty results."""
    67	        results = minimal_store.migrate_resolve_deps(dry_run=True)
    68	        assert results == []
    69	
    70	    def test_migrate_reports_errors_gracefully(self, minimal_store):
    71	        """Broken pack should be skipped, not crash migration."""
    72	        minimal_store.list_packs = lambda: ["broken-pack"]
    73	        minimal_store.get_pack = MagicMock(side_effect=Exception("corrupt"))
    74	
    75	        results = minimal_store.migrate_resolve_deps(dry_run=True)
    76	        assert results == []
    77	
    78	
    79	# =============================================================================
    80	# Config integration
    81	# =============================================================================
    82	
    83	class TestConfigInStore:
    84	    """Smoke: Store uses config for resolve settings."""
    85	
    86	    def test_try_load_config_graceful(self, minimal_store):
    87	        """_try_load_config should not crash even if config missing."""
    88	        # May return None (no config.json) or config object — either is fine
    89	        config = minimal_store._try_load_config()
    90	        # Just verify it doesn't raise
    91	        assert config is None or hasattr(config, "resolve")
    92	
    93	    def test_resolve_config_defaults(self):
    94	        """ResolveConfig model should have correct defaults."""
    95	        rc = ResolveConfig()
    96	        assert rc.auto_apply_margin == 0.15
    97	        assert rc.enable_ai is True
    98	
    99	
   100	# =============================================================================
   101	# Resolve service wiring
   102	# =============================================================================
   103	
   104	class TestResolveServiceWiring:
   105	    """Smoke: ResolveService is properly wired in Store."""
   106	
   107	    def test_resolve_service_exists(self, minimal_store):
   108	        assert hasattr(minimal_store, "resolve_service")
   109	        assert minimal_store.resolve_service is not None
   110	
   111	    def test_resolve_service_has_config_getter(self, minimal_store):
   112	        assert minimal_store.resolve_service._config_getter is not None
   113	
   114	    def test_suggest_on_missing_dep(self, minimal_store):
   115	        """Suggest for nonexistent dep returns empty with warning."""
   116	        pack = MagicMock()
   117	        pack.dependencies = []
   118	        result = minimal_store.resolve_service.suggest(pack, "nonexistent")
   119	        assert result.candidates == []
   120	        assert any("not found" in w.lower() for w in result.warnings)
   121	
   122	    def test_apply_resolution_method(self, minimal_store):
   123	        """Store.apply_resolution delegates to resolve_service."""
   124	        assert hasattr(minimal_store, "apply_resolution")

exec
/bin/bash -lc "git show feat/resolve-model-redesign:plans/PLAN-Resolve-Model.md | nl -ba | sed -n '1058,1500p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1058	
  1059	### Phase 3: Local Resolve — import lokalnich souboru ✅ KOMPLETNI
  1060	
  1061	**Cil:** Uzivatel muze resolvovat dependenci z lokalniho souboru misto stahovani.
  1062	Soubor se hashuje, zkopiruje do blob store, a enrichuje se metadata z Civitai/HF.
  1063	
  1064	**Stav:** ✅ KOMPLETNI — commit `6f8b485` (2026-03-10), branch `feat/resolve-model-redesign`
  1065	
  1066	**Tri scenare:**
  1067	
  1068	**A) Dep uz ma remote zdroj (Civitai/HF):** ✅ IMPL+INTEG
  1069	- Dep je resolved na civitai_file(model_id=123, sha256=abc...) ale soubor neni stazeny
  1070	- Uzivatel otevre Local tab, zvoli slozku
  1071	- System porovna SHA256/filename → doporuci konkretni soubor ("tohle vypada jako ten spravny")
  1072	- Uzivatel potvrdi → copy do blob store, dep resolvovana
  1073	- **Implementace:** `LocalFileService.recommend()` s confidence scoring:
  1074	  sha256_exact (1.0) > filename_exact (0.85) > filename_stem (0.6) > none (0.0)
  1075	
  1076	**B) Dep nema remote zdroj, enrichment pres hash:** ✅ IMPL+INTEG
  1077	- Custom pack, dep ma jen nazev (napr. `juggernaut_xl.safetensors`)
  1078	- Uzivatel vybere soubor → system hashuje (SHA256)
  1079	- Hash → Civitai by-hash API → najde model_id, version_id, canonical_source
  1080	- ~~Hash → HuggingFace lookup (pokud Civitai nevi)~~ (HF enrichment az Phase 4)
  1081	- Dep je plne enrichovana + soubor v blob store
  1082	- **Overeno na realnych datech:** 4 soubory (add-detail-xl, ponyDiffusionV6XL, frostbitev2, pixel_art_style) — vsechny uspesne enrichovany z Civitai
  1083	
  1084	**C) Hash nic nenajde, enrichment pres jmeno:** ✅ IMPL+INTEG
  1085	- Hash nenajde nic na Civitai ani HF
  1086	- Filename stem (napr. `juggernaut_xl_v9` → "juggernaut xl v9") → name search na Civitai (Meilisearch)
  1087	- Pokud najde → doplni canonical_source, metadata
  1088	- Pokud nenajde → ulozi jako LOCAL_FILE strategie s display_name z filename
  1089	- Vzdy se ulozi aspon: sha256, file size, display_name z filename
  1090	- **Overeno na realnych datech:** ltx-2-19b-lora-camera-control-dolly-left.safetensors → filename_only fallback
  1091	
  1092	**Deliverables:**
  1093	
  1094	1. ✅ **Backend: Directory browsing** — `GET /api/store/browse-local`
  1095	   - Parametry: `path` (adresar), `kind` (AssetKind pro filtraci pripon)
  1096	   - Vraci seznam souboru: name, size, mtime, extension, cached_hash
  1097	   - Security: path traversal prevence, allowlisted extensions (.safetensors, .ckpt, .pt, .bin, .pth, .onnx, .sft, .gguf)
  1098	   - Regular file check (no symlinks, no devices)
  1099	   - **Implementace:** `store_router.get("/browse-local")` → `LocalFileService.browse()`
  1100	
  1101	2. ✅ **Backend: Import local file** — `POST /api/packs/{pack_name}/import-local`
  1102	   - Parametry: pack_name, dep_id, file_path, skip_enrichment
  1103	   - Flow: validate path → SHA256 hash (s cache) → atomic copy do blob store → enrich → apply resolution
  1104	   - Enrichment pipeline: `enrich_file()` → hash lookup (Civitai) → name search (Meilisearch) → filename_only fallback
  1105	   - Background import: `ThreadPoolExecutor(max_workers=2)`, `_cleanup_old_imports(MAX_IMPORT_HISTORY=50)`
  1106	   - Progress polling: `GET /api/store/imports/{import_id}` (1000ms interval)
  1107	   - **Implementace:** `v2_packs_router.post("/{pack_name}/import-local")` → `_active_imports` dict + polling
  1108	
  1109	3. ✅ **Backend: Smart file recommendation** — `GET /api/packs/{pack_name}/recommend-local`
  1110	   - Parametry: pack_name, dep_id, directory
  1111	   - Pokud dep ma known SHA256 nebo filename → scan adresar a doporucit match
  1112	   - Poradi: exact SHA256 match (1.0) > filename exact (0.85) > filename stem (0.6) > none (0.0)
  1113	   - **Implementace:** `v2_packs_router.get("/{pack_name}/recommend-local")` → `LocalFileService.recommend()`
  1114	
  1115	4. ✅ **Frontend: Local File tab v DependencyResolverModal**
  1116	   - 4 stavy: browse → importing → success → error
  1117	   - Browse: directory input, recent paths (localStorage), file listing s recommendations
  1118	   - Importing: progress bar s gradient, stage indicators (hashing → copying → enriching → applying)
  1119	   - Success: checkmark, file details, enrichment info (civitai_hash / civitai_name / filename_only)
  1120	   - Error: error message s retry
  1121	   - **Implementace:** `LocalResolveTab.tsx` (~530 radku), integrovano v `DependencyResolverModal.tsx`
  1122	
  1123	5. ✅ **Security hardening:**
  1124	   - Path validace: absolute path required, no `..` traversal, resolved path check
  1125	   - Extension allowlist: `.safetensors`, `.ckpt`, `.pt`, `.bin`, `.pth`, `.onnx`, `.sft`, `.gguf`
  1126	   - Regular file check (stat.S_ISREG) — no symlinks, directories, devices
  1127	   - TOCTOU prevence: fstat na otevreny handle
  1128	   - Atomic blob copy: UUID-based `.tmp` → `os.replace()` (race condition safe)
  1129	   - Copy strategies: reflink (zero-copy, Btrfs/XFS) → hardlink (same FS) → shutil.copy2 (fallback)
  1130	
  1131	6. ✅ **Shared enrichment module** — `src/store/enrichment.py` (267 radku)
  1132	   - `enrich_by_hash()` — SHA256 lookup na Civitai (get_model_by_hash)
  1133	   - `enrich_by_name()` — Filename stem search na Civitai (Meilisearch-first, REST fallback)
  1134	   - `enrich_file()` — Pipeline: hash → name → filename_only fallback (vzdy vraci vysledek)
  1135	   - `extract_stem()` — Clean model name z filename
  1136	   - Helpers: `_normalize_name()`, `_kind_matches_civitai_type()`, `_extract_file_id_from_version()`, `_get_latest_version()`
  1137	   - Sdileno s `PreviewMetaEvidenceProvider` (Phase 2.5) a `LocalFileService` (Phase 3)
  1138	
  1139	**Store integrace:** ✅
  1140	- `LocalFileService` jako 10. sluzba v `Store.__init__()` (DI pattern)
  1141	- Pristup k `HashCache`, `BlobStore`, `PackService` pres gettery (lazy, no circular deps)
  1142	- `_apply_resolution()` buduje `ManualResolveData` dle enrichment strategie (CIVITAI_FILE / HUGGINGFACE_FILE / LOCAL_FILE)
  1143	- Deleguje na `resolve_service.apply_manual()` nebo `pack_service.apply_dependency_resolution()` (fallback)
  1144	
  1145	**Testy:** ✅ 57 NOVYCH TESTU
  1146	- Unit enrichment (26): `tests/unit/store/test_enrichment.py`
  1147	  - TestExtractStem (7), TestNormalizeName (3), TestKindMatchesCivitaiType (6)
  1148	  - TestEnrichByHash (4), TestEnrichByName (3), TestEnrichFile (3)
  1149	- Unit local_file_service (31): `tests/unit/store/test_local_file_service.py`
  1150	  - TestValidatePath (9), TestValidateDirectory (5), TestBrowse (7)
  1151	  - TestRecommend (5), TestImportFile (4), TestEnrichment (1)
  1152	
  1153	**Real-world testovani (2026-03-10):** ✅ OVERENO
  1154	- Legacy repo: `/home/box/.synapse/repo-legacy/` (492 GB, 94 souboru)
  1155	- Browse checkpoints: 7 souboru, Browse loras: 19 souboru
  1156	- Import `tifa_lockhart_offset.safetensors` (302 MB) — skip_enrichment=True → OK
  1157	- Import `add-detail-xl.safetensors` (218 MB) — civitai_hash match → model 122359 "Detail Tweaker XL"
  1158	- Import `ponyDiffusionV6XL.safetensors` (6.4 GB) — civitai_hash match → model 257749 "Pony Diffusion V6 XL" (6.7s)
  1159	- Import `frostbitev2_Illu_dwnsty.safetensors` (109 MB) — civitai_hash match → model 947081
  1160	- Import `ltx-2-19b-lora-camera-control-dolly-left.safetensors` (312 MB) — filename_only fallback (ne na Civitai)
  1161	- API flow: browse-local (200 OK), recommend-local (200 OK), import-local + polling (completed)
  1162	- `pixel_art_style_z_image_turbo.safetensors` — API import+polling: civitai_hash → model 1770073
  1163	
  1164	**Bug nalezeny a opraveny behem implementace:**
  1165	- `v2_store_router` neexistoval v `api.py` → opraveno na `store_router` (3 vyskyty)
  1166	- `CanonicalSource(type="civitai")` → `provider="civitai"` (Pydantic field je `provider`, ne `type`)
  1167	- Test `test_rejects_directory` — directory fails on extension check first, not regular file check
  1168	
  1169	**Review:** ✅ 2 kola
  1170	- **Round 1:** Memory leak (MAX_IMPORT_HISTORY), unbounded threads (ThreadPoolExecutor), race condition (atomic write), polling too fast (500→1000ms)
  1171	- **Round 2:** Deterministic tmp collision (UUID-based), polling double-click guard, model_dump() false positive
  1172	
  1173	**Zmeny v souborech:**
  1174	| Soubor | Zmena |
  1175	|--------|-------|
  1176	| `src/store/enrichment.py` | **NOVY** — shared enrichment module (267 radku) |
  1177	| `src/store/local_file_service.py` | **NOVY** — LocalFileService: browse, recommend, import_file (~450 radku) |
  1178	| `src/store/__init__.py` | +HashCache init, +LocalFileService jako 10. sluzba |
  1179	| `src/store/api.py` | +5 endpointu (browse-local, recommend-local, import-local, imports, imports/{id}), ThreadPoolExecutor |
  1180	| `apps/web/.../modals/LocalResolveTab.tsx` | **NOVY** — Local File tab s 4 stavy (~530 radku) |
  1181	| `apps/web/.../modals/DependencyResolverModal.tsx` | +Local File tab integrace, +HardDrive icon |
  1182	| `apps/web/.../types.ts` | +LocalFileInfo, FileRecommendation, BrowseLocalResult, LocalImportStatus |
  1183	| `apps/web/.../constants.ts` | +localBrowse, localRecommend, localImport query keys |
  1184	| `plans/SPEC-Local-Resolve.md` | **NOVY** — full specifikace (architektura, security, API, UX, testy) |
  1185	| `tests/unit/store/test_enrichment.py` | **NOVY** — 26 testu |
  1186	| `tests/unit/store/test_local_file_service.py` | **NOVY** — 31 testu |
  1187	
  1188	**Celkem testy po Phase 3:** 2131 backend + frontend passed, 0 failed
  1189	
  1190	### Phase 4: Provider polish + download + cleanup
  1191	
  1192	**Cil:** Typed payloady, cleanup, download napojeni.
  1193	**Status:** ✅ DOKONCENO (2026-03-10) — 2 commity: `8b0b910`, `6cf7db1`
  1194	
  1195	**Deliverables:**
  1196	
  1197	1. ✅ Typed provider payloady end-to-end — odmitat nekompletni
  1198	   - `apply-manual-resolution` endpoint rejects incomplete payloads per strategy (422)
  1199	   - Civitai: requires `civitai_model_id` + `civitai_version_id`
  1200	   - HuggingFace: requires `hf_repo_id` + `hf_filename`
  1201	   - Local: requires `local_path`
  1202	   - URL: requires `url`
  1203	2. ✅ Audit resolve endpointu — validace vstupu
  1204	   - `suggest-resolution`: validates dep_id exists in pack (404), max_candidates capped at 50
  1205	   - `apply-resolution`: validates pack exists (404)
  1206	   - `apply_manual()`: loads pack for cross-kind validation (was missing)
  1207	3. ~~Resolution → Download napojeni~~ — DEFERRED (download system uz funguje pres existing `download-asset` endpoint, neni treba nove napojeni)
  1208	4. ✅ Cleanup: smazat stary endpoint /resolve-base-model, BaseModelResolverModal, ~~extractBaseModelHint~~ (uz smazano)
  1209	   - Smazano 1289 radku deprecated kodu
  1210	   - `BaseModelResolverModal.tsx` (749 radku) — DELETED
  1211	   - `/resolve-base-model` endpoint + `ResolveBaseModelRequest` — REMOVED from api.py
  1212	   - `resolveBaseModelMutation` — REMOVED from usePackData.ts
  1213	   - `baseModelResolver` — REMOVED from ModalState, DEFAULT_MODAL_STATE, types.ts, constants.ts
  1214	   - PackDependenciesSection redirected to DependencyResolverModal
  1215	   - PackDetailPage cleaned (removed useQuery, QUERY_KEYS unused imports)
  1216	   - i18n keys removed from en.json, cs.json
  1217	   - Tests updated: test_api_v2_critical.py, test_phase1_bug_fixes.py, test_api_critical.py, test_architecture.py
  1218	   - Frontend tests updated: pack-data-invalidation.test.ts, pack-detail-hooks.test.ts
  1219	
  1220	**Testy:** 2203 backend + frontend all passed, 7 new validation tests added
  1221	
  1222	**Zmenene soubory (Phase 4):**
  1223	- `src/store/api.py` — removed endpoint, added validation
  1224	- `src/store/resolve_service.py` — apply_manual cross-kind validation
  1225	- `apps/web/src/components/modules/PackDetailPage.tsx` — cleanup
  1226	- `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts` — removed mutation
  1227	- `apps/web/src/components/modules/pack-detail/modals/BaseModelResolverModal.tsx` — DELETED
  1228	- `apps/web/src/components/modules/pack-detail/modals/index.ts` — removed export
  1229	- `apps/web/src/components/modules/pack-detail/sections/PackDependenciesSection.tsx` — redirect
  1230	- `apps/web/src/components/modules/pack-detail/types.ts` — removed baseModelResolver
  1231	- `apps/web/src/components/modules/pack-detail/constants.ts` — removed default
  1232	- `apps/web/src/i18n/locales/{en,cs}.json` — removed keys
  1233	- `tests/unit/store/test_resolve_validation.py` — 7 new tests
  1234	- `tests/store/test_api_v2_critical.py` — removed deprecated tests
  1235	- `tests/unit/store/test_phase1_bug_fixes.py` — removed BUG4 tests
  1236	- `tests/store/test_api_critical.py` — updated assertions
  1237	- `tests/lint/test_architecture.py` — removed endpoint requirement
  1238	
  1239	### Phase 5: Deferred polish — 6 items ✅ DOKONCENO (2026-03-10)
  1240	
  1241	**Cil:** Implementovat vsech 6 odlozenych bodu pro kompletni resolve system.
  1242	
  1243	#### 5.1 candidate_base_model v apply() — ResolutionCandidate rozsireni
  1244	- **Problem:** `apply()` line 314: `candidate_base_model=None` — cross-kind check disabled
  1245	- **Fix:** Pridat `base_model: Optional[str] = None` na `ResolutionCandidate`
  1246	- **Kde se plni:** `_merge_and_score()` — extrahovat z `canonical_source` nebo `selector_data`
  1247	- **Evidence providery** uz maji base_model v CandidateSeed — propagovat do candidate
  1248	
  1249	#### 5.2 AUTO_APPLY_MARGIN konfigurovatelny
  1250	- **Problem:** Hard-coded `0.15` na 2 mistech (resolve_config.py + __init__.py:645)
  1251	- **Fix:** Pouzit `AUTO_APPLY_MARGIN` konstantu z resolve_config.py na obou mistech
  1252	- **Konfigurace:** Pridat `resolve.auto_apply_margin` do config/settings.py `SynapseConfig`
  1253	- **Default:** 0.15 (zachovat kompatibilitu)
  1254	
  1255	#### 5.3 Async hash computation
  1256	- **Problem:** `compute_sha256()` blokuje na velkych souborech (7GB+ checkpointy)
  1257	- **Fix:** Pridat `compute_sha256_async()` do hash_cache.py — `asyncio.to_thread()` wrapper
  1258	- **Pouziti:** FastAPI endpointy mohou volat async verzi; sync zustava pro CLI/import
  1259	
  1260	#### 5.4 HF enrichment v local import
  1261	- **Problem:** `enrich_file()` hleda jen na Civitai, ne na HuggingFace
  1262	- **Fix:** Pridat `enrich_by_hf()` — HF API search by filename stem
  1263	- **Pipeline:** hash(Civitai) → name(Civitai) → name(HF) → filename_only
  1264	- **Parametr:** `hf_client: Optional[Any] = None` do `enrich_file()`
  1265	
  1266	#### 5.5 HF LFS pointer SHA256 (G2)
  1267	- **Problem:** HuggingFaceClient.get_repo_files() UZ vraci LFS OID (=SHA256)
  1268	- **Fix:** Pridat `search_models()` metodu na HuggingFaceClient pro HF Hub API search
  1269	- **Pouziti:** HF enrichment + MCP tool search_huggingface
  1270	
  1271	#### 5.6 search_huggingface MCP tool — structured output
  1272	- **Problem:** Tool vraci formatted text, ne JSON. AI nemuze extrahovat hashes
  1273	- **Fix:** Doplnit base_model z repo tags, vratit JSON-friendly output
  1274	- **Pozn:** Tool uz funguje dobre pro AI — text format je OK pro LLM. Doplnime base_model info
  1275	
  1276	**Soubory:**
  1277	- `src/store/resolve_models.py` — ResolutionCandidate.base_model + CandidateSeed.base_model
  1278	- `src/store/resolve_service.py` — propagace base_model, pouziti v apply(), merge fix
  1279	- `src/store/resolve_config.py` — AUTO_APPLY_MARGIN import
  1280	- `src/store/__init__.py` — pouzit AUTO_APPLY_MARGIN, migrate_resolve_deps check apply result
  1281	- `src/store/hash_cache.py` — compute_sha256_async()
  1282	- `src/store/enrichment.py` — enrich_by_hf(), HF_BASE_MODEL_TAGS shared constant, limit top 2
  1283	- `src/store/local_file_service.py` — pass hf_client to enrich_file()
  1284	- `src/clients/huggingface_client.py` — search_models()
  1285	- `src/avatar/mcp/store_server.py` — base_model detection uses shared HF_BASE_MODEL_TAGS
  1286	- Testy: 24 tests v test_phase5_deferred.py
  1287	
  1288	**Review findings (opraveno):**
  1289	- Gemini: deduplikovany base_model_tags → shared HF_BASE_MODEL_TAGS
  1290	- Gemini: enrich_by_hf limitovano na top 2 repos (ne vsech 5)
  1291	- Codex: migrate_resolve_deps ted kontroluje apply_result.success
  1292	- Codex: base_model propagace fix — prefer seed s base_model v _merge_and_score
  1293	- Codex: local_file_service.py ted predava hf_client do enrich_file()
  1294	
  1295	**Pre-existing bugfixes (nalezene pri review, commit `e3fcba3`):**
  1296	- evidence_providers.py: `.get()` na CivitaiModelVersion dataclass → `getattr()` (tichy pad Tier-1 evidence)
  1297	- huggingface_client.py: HFFileInfo LFS OID cteni z top-level → `lfs.oid` s `sha256:` prefix strip
  1298	- Testy aktualizovany na dataclass-like mocky
  1299	
  1300	### Phase 6: Final polish — config, aliases, tests, AI gate ✅ DOKONCENO (2026-03-10)
  1301	
  1302	**Cil:** Posledni odlozene body — konfigurovatelny resolve, alias bugfix, chybejici testy, AI gate.
  1303	**Status:** ✅ DOKONCENO — vsech 5 bodu implementovano, 27 novych testu, 3-tier review
  1304	
  1305	#### 6.1 Fix _read_aliases() — cte store.yaml misto config.json
  1306	- **Problem:** `evidence_providers.py:677` cte `store.yaml` ale config je `config.json`
  1307	- **Fix:** Pouzit `layout.load_config()` → `config.base_model_aliases`
  1308	- **Soucasny stav:** AliasEvidenceProvider NIKDY nenajde aliasy (soubor neexistuje)
  1309	
  1310	#### 6.2 Konfigurovatelny AUTO_APPLY_MARGIN
  1311	- **Problem:** Konstanta v kodu, uzivatel nemuze zmenit
  1312	- **Fix:** Pridat `ResolveConfig` model do `models.py`, field `auto_apply_margin: float = 0.15`
  1313	- **Cteni:** `resolve_config.py` funkce `get_auto_apply_margin(config)` s fallback na 0.15
  1314	- **Pouziti:** `__init__.py` _post_import_resolve + migrate_resolve_deps
  1315	
  1316	#### 6.3 can_use_ai() gate
  1317	- **Problem:** `AIEvidenceProvider.supports()` jen kontroluje `avatar is not None`
  1318	- **Fix:** Pridat `resolve.enable_ai: bool = True` do `ResolveConfig`
  1319	- **Pouziti:** `supports()` zkontroluje config flag + avatar dostupnost
  1320	
  1321	#### 6.4 Integration testy — import s evidence ladder
  1322	- **Pattern:** Realny ResolveService + mock PackService + FakeCivitai
  1323	- **Scenare:** suggest→apply lifecycle, multi-provider merge, stale fingerprint
  1324	
  1325	#### 6.5 Smoke testy — kompletni import z Civitai s resolve
  1326	- **Pattern:** Realny Store (tmp_path) + FakeCivitai + mock HTTP
  1327	- **Scenare:** import→suggest→auto-apply, migration helper, error recovery
  1328	
  1329	**Soubory:**
  1330	- `src/store/models.py` — ResolveConfig model
  1331	- `src/store/resolve_config.py` — get_auto_apply_margin(), get_resolve_config()
  1332	- `src/store/evidence_providers.py` — fix _read_aliases(), can_use_ai
  1333	- `src/store/__init__.py` — pouzit konfigurovatelny margin
  1334	- `tests/integration/test_resolve_integration.py` — NEW
  1335	- `tests/integration/test_resolve_smoke.py` — NEW
  1336	
  1337	---
  1338	
  1339	## 11. Implementation Design — presna mapa napojeni (v2)
  1340	
  1341	Revidovano po Gemini+Codex review implementacniho designu v0.7.0.
  1342	Opraveny: cyklicka zavislost, avatar injection timing, EvidenceProvider kontrakt,
  1343	chybejici DTO, candidate cache, test plan.
  1344	
  1345	### 11a. Existujici architekturni vzory (DODRZOVAT)
  1346	
  1347	Synapse pouziva konzistentni vzory, do kterych se MUSIME napojit:
  1348	
  1349	| Vzor | Kde pouzivan | Jak rozsirime |
  1350	|------|-------------|--------------|
  1351	| **Store = Facade** | `__init__.py` drzi 8 sluzeb, constructor DI | Pridat `resolve_service` jako 9. sluzbu, `local_file_service` jako 10. |
  1352	| **Protocol-based registry** | `DependencyResolver` protocol, `_ensure_resolvers()` lazy init | `EvidenceProvider` protocol, `_ensure_providers()` lazy init |
  1353	| **AITask ABC + TaskRegistry** | `tasks/base.py`, `tasks/registry.py`, auto-discovered | Pridat `DependencyResolutionTask` do registry |
  1354	| **Shared services** | DownloadService, BlobStore sdilene pres Store | ResolveService dostane sdilene sluzby |
  1355	| **Lazy-loaded clients** | `@property` v PackService pro civitai/hf | ResolveService pouzije tytez |
  1356	| **FastAPI Depends()** | `store=Depends(require_initialized)` | Nove endpointy stejna injection |
  1357	| **TanStack Query mutations** | `usePackData` hook centralizuje mutace | Pridat suggest/apply mutace |
  1358	| **Props-based modaly** | BaseModelResolverModal, data up via callbacks | DependencyResolverModal stejny vzor |
  1359	
  1360	### 11b. Klicove designove rozhodnuti (z review)
  1361	
  1362	**R1: Zadna cyklicka zavislost**
  1363	- ResolveService → PackService (pro apply write path) = OK
  1364	- PackService NEZNA ResolveService (zadna zpetna reference)
  1365	- Post-import resolve orchestrovano z `Store.import_civitai()` (facade)
  1366	- Stejna jednosmernost jako zbytek Store architektury
  1367	
  1368	**R2: Klienty pres PackService, ne duplicitne**
  1369	- ResolveService NEDRZI vlastni civitai/hf klienty
  1370	- Pristupuje pres `pack_service.civitai` / `pack_service.huggingface` (lazy-loaded properties)
  1371	- Jediny vlastnik klientu = PackService
  1372	
  1373	**R3: Avatar pres getter, ne primo**
  1374	- `avatar_getter: Callable[[], AvatarTaskService | None]`
  1375	- Provider zavola getter at runtime → bezpecne i pokud avatar pripojen pozdeji
  1376	- Zadny timing problem s _ensure_providers()
  1377	
  1378	**R4: Provider vraci kandidata + evidenci dohromady**
  1379	- NE holou evidenci (kde by kandidat mel byt sestaven nekde jinde)
  1380	- `ProviderResult` obsahuje `List[EvidenceHit]` kde kazdy hit ma `CandidateSeed` + `EvidenceItem`
  1381	- ResolveService jen mergi a rankuje — neinterpretuje evidence
  1382	
  1383	**R5: Import-time AI default OFF**
  1384	- `include_ai=False` pro import (deterministicke urovne E1-E6 staci pro vetsinu)
  1385	- AI jen pri explicitnim suggest v UI nebo pro unresolved deps
  1386	- Duvod: AvatarTaskService serializes engine za jednim lockem → multi-dep AI = pomale
  1387	
  1388	### 11c. DTO definice (vsechny na jednom miste)
  1389	
  1390	```python
  1391	# src/store/resolve_models.py — vsechny DTO pro resolve system
  1392	
  1393	from pydantic import BaseModel, Field
  1394	from typing import Any, Dict, List, Literal, Optional
  1395	from uuid import uuid4
  1396	
  1397	# --- Evidence kontrakty ---
  1398	
  1399	class CandidateSeed(BaseModel):
  1400	    """Identifikace kandidata — co provider nasel."""
  1401	    key: str                                   # Deduplikacni klic (hash+provider)
  1402	    selector: DependencySelector               # Kompletni selector data
  1403	    canonical_source: Optional[CanonicalSource] = None
  1404	    display_name: str                          # "Illustrious XL v0.6"
  1405	    display_description: Optional[str] = None
  1406	    provider_name: Optional[Literal["civitai", "huggingface", "local"]] = None
  1407	
  1408	class EvidenceHit(BaseModel):
  1409	    """Jeden nalez = kandidat + dukaz proc."""
  1410	    candidate: CandidateSeed
  1411	    provenance: str                            # "preview:001.png", "hash:sha256", "alias:SDXL"
  1412	    item: EvidenceItem                         # Konkretni dukaz
  1413	
  1414	class EvidenceItem(BaseModel):
  1415	    source: Literal["hash_match", "preview_embedded", "preview_api_meta",
  1416	                     "source_metadata", "file_metadata", "alias_config",
  1417	                     "ai_analysis"]
  1418	    description: str
  1419	    confidence: float
  1420	    raw_value: Optional[str] = None
  1421	
  1422	class ProviderResult(BaseModel):
  1423	    """Vystup jednoho evidence provideru."""
  1424	    hits: List[EvidenceHit] = Field(default_factory=list)
  1425	    warnings: List[str] = Field(default_factory=list)
  1426	    error: Optional[str] = None
  1427	
  1428	# --- Request/Response kontrakty ---
  1429	
  1430	class SuggestOptions(BaseModel):
  1431	    """Volby pro suggest_resolution."""
  1432	    include_ai: bool = False                   # Default OFF (R5)
  1433	    analyze_previews: bool = True
  1434	    max_candidates: int = 10
  1435	
  1436	class SuggestResult(BaseModel):
  1437	    """Vysledek suggest — seznam kandidatu + metadata."""
  1438	    request_id: str = Field(default_factory=lambda: str(uuid4()))
  1439	    candidates: List[ResolutionCandidate] = Field(default_factory=list)
  1440	    pack_fingerprint: str = ""                 # SHA hash pack.json pro stale detection
  1441	    warnings: List[str] = Field(default_factory=list)
  1442	
  1443	class ApplyResult(BaseModel):
  1444	    """Vysledek apply — uspech/neuspech."""
  1445	    success: bool
  1446	    message: str = ""
  1447	    compatibility_warnings: List[str] = Field(default_factory=list)
  1448	
  1449	class ManualResolveData(BaseModel):
  1450	    """Data z manualniho resolve (Civitai/HF/Local tab)."""
  1451	    strategy: SelectorStrategy
  1452	    civitai: Optional[CivitaiSelector] = None
  1453	    huggingface: Optional[HuggingFaceSelector] = None
  1454	    local_path: Optional[str] = None
  1455	    url: Optional[str] = None
  1456	    canonical_source: Optional[CanonicalSource] = None
  1457	    display_name: Optional[str] = None
  1458	
  1459	# --- Resolve context (predavano providerum) ---
  1460	
  1461	class ResolveContext(BaseModel):
  1462	    """Kontext predavany evidence providerum."""
  1463	    pack: Any                                  # Pack objekt (ne Pydantic)
  1464	    dependency: Any                            # PackDependency
  1465	    dep_id: str
  1466	    kind: AssetKind
  1467	    preview_hints: List[PreviewModelHint] = Field(default_factory=list)
  1468	    layout: Any = None                         # StoreLayout (pro file-system access)
  1469	
  1470	    class Config:
  1471	        arbitrary_types_allowed = True
  1472	```
  1473	
  1474	### 11d. EvidenceProvider Protocol
  1475	
  1476	```python
  1477	# src/store/evidence_providers.py
  1478	
  1479	@runtime_checkable
  1480	class EvidenceProvider(Protocol):
  1481	    """
  1482	    Protocol pro evidence providery.
  1483	    Stejny vzor jako DependencyResolver — duck typing, @runtime_checkable.
  1484	
  1485	    Kazdy provider:
  1486	    1. Zkontroluje supports() — je relevantni pro dany AssetKind?
  1487	    2. gather() — sbira evidence, vraci ProviderResult s EvidenceHit items
  1488	    3. Kazdy EvidenceHit obsahuje CandidateSeed (CO nasel) + EvidenceItem (PROC)
  1489	    """
  1490	
  1491	    @property
  1492	    def tier(self) -> int:
  1493	        """Confidence tier tohoto provideru (1-4)."""
  1494	        ...
  1495	
  1496	    def supports(self, context: ResolveContext) -> bool:
  1497	        """Zda je provider relevantni pro dany context (kind, dostupnost sluzby)."""
  1498	        ...
  1499	
  1500	    def gather(self, context: ResolveContext) -> ProviderResult:

exec
/bin/bash -lc "git show feat/resolve-model-redesign:plans/PLAN-Resolve-Model.md | nl -ba | sed -n '1500,1860p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1500	    def gather(self, context: ResolveContext) -> ProviderResult:
  1501	        """Sbira evidence. Vraci hits s kandidaty + dukazy."""
  1502	        ...
  1503	```
  1504	
  1505	**Implementace (6 provideru):**
  1506	
  1507	```python
  1508	class HashEvidenceProvider:
  1509	    """E1: SHA256 lookup na Civitai + HF. Tier 1."""
  1510	    tier = 1
  1511	
  1512	    def __init__(self, pack_service_getter):
  1513	        self._ps = pack_service_getter  # Callable → PackService
  1514	
  1515	    def supports(self, ctx):
  1516	        return True  # Vzdy, pokud mame hash
  1517	
  1518	    def gather(self, ctx):
  1519	        # Lookup hash z existujiciho lock nebo z Civitai file metadata
  1520	        # → civitai: pack_service.civitai.get_model_by_hash()
  1521	        # → hf: LFS pointer check (pokud eligible)
  1522	        ...
  1523	
  1524	class PreviewMetaEvidenceProvider:
  1525	    """E2+E3: Preview metadata (PNG + API sidecar). Tier 2."""
  1526	    tier = 2
  1527	    def supports(self, ctx): return bool(ctx.preview_hints)
  1528	    def gather(self, ctx): ...  # Kind-aware filtrovani, provenance grouping
  1529	
  1530	class FileMetaEvidenceProvider:
  1531	    """E5: Filename patterns, architecture. Tier 3."""
  1532	    tier = 3
  1533	    def supports(self, ctx): return True
  1534	    def gather(self, ctx): ...
  1535	
  1536	class AliasEvidenceProvider:
  1537	    """E6: Configured aliases (Civitai + HF cile). Tier 3."""
  1538	    tier = 3
  1539	    def __init__(self, layout_getter):
  1540	        self._layout = layout_getter  # Callable → StoreLayout
  1541	    def supports(self, ctx): return True
  1542	    def gather(self, ctx): ...  # Cteni base_model_aliases z config
  1543	
  1544	class SourceMetaEvidenceProvider:
  1545	    """E4: Civitai baseModel field (jen voditko). Tier 4."""
  1546	    tier = 4
  1547	    def supports(self, ctx): return True
  1548	    def gather(self, ctx): ...
  1549	
  1550	class AIEvidenceProvider:
  1551	    """E7: AI analysis (MCP-backed). Ceiling 0.89."""
  1552	    tier = 2  # AI muze byt az Tier 2
  1553	
  1554	    def __init__(self, avatar_getter):
  1555	        self._get_avatar = avatar_getter  # Callable → Optional[AvatarTaskService]
  1556	
  1557	    def supports(self, ctx):
  1558	        avatar = self._get_avatar()
  1559	        return avatar is not None and can_use_ai()
  1560	
  1561	    def gather(self, ctx):
  1562	        avatar = self._get_avatar()
  1563	        if avatar is None:
  1564	            return ProviderResult(error="Avatar not available")
  1565	        result = avatar.execute_task("dependency_resolution", ...)
  1566	        ...  # Parse do EvidenceHit items
  1567	```
  1568	
  1569	### 11e. ResolveService — jadro (opraveny design)
  1570	
  1571	```python
  1572	# src/store/resolve_service.py
  1573	
  1574	class ResolveService:
  1575	    """
  1576	    Orchestrace dependency resolution.
  1577	    9. sluzba v Store facade.
  1578	
  1579	    NEDRZI vlastni klienty — pristupuje pres pack_service (R2).
  1580	    NEZNA PackService zpetne — jednosmerny tok (R1).
  1581	    Avatar pres getter callable (R3).
  1582	    """
  1583	    def __init__(
  1584	        self,
  1585	        layout: StoreLayout,
  1586	        pack_service: PackService,
  1587	        avatar_getter: Callable[[], Optional[AvatarTaskService]] = lambda: None,
  1588	        providers: Optional[Dict[str, EvidenceProvider]] = None,
  1589	        candidate_cache: Optional[CandidateCacheStore] = None,
  1590	    ):
  1591	        self._layout = layout
  1592	        self._pack_service = pack_service
  1593	        self._avatar_getter = avatar_getter
  1594	        self._providers = providers
  1595	        self._cache = candidate_cache or InMemoryCandidateCache()
  1596	
  1597	    def _ensure_providers(self) -> None:
  1598	        """Lazy init. Providers pouzivaji gettery, ne prime reference."""
  1599	        if self._providers:
  1600	            return
  1601	        from .evidence_providers import (
  1602	            HashEvidenceProvider, PreviewMetaEvidenceProvider,
  1603	            FileMetaEvidenceProvider, AliasEvidenceProvider,
  1604	            SourceMetaEvidenceProvider, AIEvidenceProvider,
  1605	        )
  1606	        ps_getter = lambda: self._pack_service
  1607	        layout_getter = lambda: self._layout
  1608	        self._providers = {
  1609	            "hash_match": HashEvidenceProvider(ps_getter),
  1610	            "preview_meta": PreviewMetaEvidenceProvider(),
  1611	            "file_meta": FileMetaEvidenceProvider(),
  1612	            "alias": AliasEvidenceProvider(layout_getter),
  1613	            "source_meta": SourceMetaEvidenceProvider(),
  1614	            "ai": AIEvidenceProvider(self._avatar_getter),
  1615	        }
  1616	
  1617	    def suggest(self, pack: Pack, dep_id: str, options: SuggestOptions) -> SuggestResult:
  1618	        """
  1619	        1. Sestavi ResolveContext
  1620	        2. Projde providers (dle tier poradi, jen supports()==True)
  1621	        3. Merge EvidenceHit po candidate.key
  1622	        4. Score (Noisy-OR s provenance grouping + tier ceiling)
  1623	        5. Sort, assign UUID candidate_id, cache
  1624	        6. Vrati SuggestResult
  1625	        """
  1626	        ...
  1627	
  1628	    def apply(self, pack_name: str, dep_id: str, candidate_id: str) -> ApplyResult:
  1629	        """
  1630	        1. Najde kandidata v cache (dle request_id + candidate_id)
  1631	        2. Overi pack fingerprint (stale detection)
  1632	        3. Validace: min fields (validation matrix) + cross-kind check
  1633	        4. Deleguje na pack_service.apply_dependency_resolution()
  1634	        5. Vrati ApplyResult
  1635	        """
  1636	        ...
  1637	
  1638	    def apply_manual(self, pack_name: str, dep_id: str, manual: ManualResolveData) -> ApplyResult:
  1639	        """
  1640	        Stejna validace jako apply, ale data z manualniho UI.
  1641	        Taky deleguje na pack_service.apply_dependency_resolution().
  1642	        """
  1643	        ...
  1644	```
  1645	
  1646	### 11f. Candidate cache
  1647	
  1648	```python
  1649	# Soucasti resolve_service.py nebo samostatny modul
  1650	
  1651	class CandidateCacheStore(Protocol):
  1652	    """Abstrakce pro candidate cache — injectable, testable."""
  1653	    def store(self, request_id: str, fingerprint: str,
  1654	              candidates: List[ResolutionCandidate]) -> None: ...
  1655	    def get(self, request_id: str, candidate_id: str) -> Optional[ResolutionCandidate]: ...
  1656	    def check_fingerprint(self, request_id: str, fingerprint: str) -> bool: ...
  1657	    def cleanup_expired(self) -> None: ...
  1658	
  1659	class InMemoryCandidateCache:
  1660	    """Default in-process cache. TTL 5min. S fingerprint kontrolou."""
  1661	    # POZN: Synapse bezi jako single-worker uvicorn (ne multi-worker)
  1662	    # Pro multi-worker: nahradit za file-based nebo Redis cache
  1663	    ...
  1664	```
  1665	
  1666	### 11g. PackService rozsireni — apply write path (R1)
  1667	
  1668	```python
  1669	# V pack_service.py — nova metoda:
  1670	
  1671	def apply_dependency_resolution(
  1672	    self,
  1673	    pack_name: str,
  1674	    dep_id: str,
  1675	    selector: DependencySelector,
  1676	    canonical_source: Optional[CanonicalSource],
  1677	    lock_entry: Optional[Dict[str, Any]],
  1678	    display_name: Optional[str] = None,
  1679	) -> None:
  1680	    """
  1681	    Jediny write path pro dependency resolve.
  1682	    Aktualizuje pack.json + pack.lock.json ATOMICKY.
  1683	
  1684	    NIKDY neprepise pack.base_model filename stemem (BUG 3 fix).
  1685	    """
  1686	    pack = self.layout.load_pack(pack_name)
  1687	    lock = self.layout.load_pack_lock(pack_name) or PackLock(pack_name=pack_name)
  1688	
  1689	    # Najdi dependency
  1690	    dep = next((d for d in pack.dependencies if d.id == dep_id), None)
  1691	    if dep is None:
  1692	        raise ValueError(f"Dependency {dep_id} not found")
  1693	
  1694	    # Update selector + canonical_source
  1695	    dep.selector = selector
  1696	    if canonical_source:
  1697	        dep.selector.canonical_source = canonical_source
  1698	
  1699	    # Update lock entry
  1700	    if lock_entry:
  1701	        lock.artifacts[dep_id] = ResolvedArtifact(**lock_entry)
  1702	
  1703	    # Atomicky zapis
  1704	    self.layout.save_pack(pack)
  1705	    self.layout.save_pack_lock(lock)
  1706	```
  1707	
  1708	### 11h. Store facade — orchestrace (R1)
  1709	
  1710	```python
  1711	# V src/store/__init__.py:
  1712	
  1713	# === V __init__() za inventory_service: ===
  1714	
  1715	self.resolve_service = ResolveService(
  1716	    layout=self.layout,
  1717	    pack_service=self.pack_service,
  1718	    avatar_getter=lambda: self._avatar_task_service,  # R3: getter
  1719	)
  1720	
  1721	# === Delegovane metody: ===
  1722	
  1723	def suggest_resolution(self, pack_name, dep_id, options=None):
  1724	    pack = self.get_pack(pack_name)
  1725	    return self.resolve_service.suggest(pack, dep_id, options or SuggestOptions())
  1726	
  1727	def apply_resolution(self, pack_name, dep_id, candidate_id):
  1728	    return self.resolve_service.apply(pack_name, dep_id, candidate_id)
  1729	
  1730	# === V import_civitai() — post-import orchestrace: ===
  1731	
  1732	def import_civitai(self, url, ...):
  1733	    # 1-2. Existujici import logika v pack_service
  1734	    pack = self.pack_service.import_from_civitai(url, ...)
  1735	
  1736	    # 3. Post-import resolve (orchestrovano z Store, NE z PackService)
  1737	    if pack and pack.dependencies:
  1738	        from .utils.preview_meta_extractor import extract_preview_hints
  1739	        hints = extract_preview_hints(pack, self.layout)
  1740	        for dep in pack.dependencies:
  1741	            result = self.resolve_service.suggest(pack, dep.id, SuggestOptions(
  1742	                include_ai=False,  # R5: default OFF pri importu
  1743	                preview_hints_override=hints,
  1744	            ))
  1745	            # Auto-apply pokud TIER-1/2 s dostatecnym marginem
  1746	            if result.candidates and result.candidates[0].tier <= 2:
  1747	                top = result.candidates[0]
  1748	                margin = (top.confidence - result.candidates[1].confidence
  1749	                         if len(result.candidates) > 1 else 1.0)
  1750	                if margin >= 0.15:
  1751	                    self.resolve_service.apply(pack.name, dep.id, top.candidate_id)
  1752	
  1753	    return pack
  1754	
  1755	# === Avatar injection (post-init): ===
  1756	
  1757	def set_avatar_service(self, avatar_task_service):
  1758	    """Volano z api.py po inicializaci avatar."""
  1759	    self._avatar_task_service = avatar_task_service
  1760	    # Getter v resolve_service uz automaticky vidi novou hodnotu (R3)
  1761	```
  1762	
  1763	### 11i. Avatar task rozsireni
  1764	
  1765	```python
  1766	# src/avatar/tasks/base.py — pridat do AITask:
  1767	class AITask(ABC):
  1768	    task_type: str = ""
  1769	    SKILL_NAMES: Tuple[str, ...] = ()
  1770	    needs_mcp: bool = False     # NOVY: flag pro MCP-enabled execution
  1771	    timeout_s: int = 120        # NOVY: konfigurovatelny timeout
  1772	
  1773	# src/avatar/task_service.py — _ensure_engine_for_task():
  1774	engine = AvatarEngine(
  1775	    provider=self._provider,
  1776	    model=self._model or None,
  1777	    system_prompt=system_prompt,
  1778	    timeout=task.timeout_s,                                           # NOVY
  1779	    safety_instructions="unrestricted",
  1780	    mcp_servers=self.config.mcp_servers if task.needs_mcp else None,  # NOVY
  1781	)
  1782	
  1783	# src/avatar/tasks/dependency_resolution.py — novy task:
  1784	class DependencyResolutionTask(AITask):
  1785	    task_type = "dependency_resolution"
  1786	    SKILL_NAMES = ("model-resolution", "dependency-resolution", "model-types", "civitai-integration", "huggingface-integration")
  1787	    needs_mcp = True
  1788	    timeout_s = 180  # MCP volani jsou pomalejsi
  1789	
  1790	    def build_system_prompt(self, skills_content): ...
  1791	    def parse_result(self, raw_output): ...
  1792	    def validate_output(self, output): ...
  1793	    def get_fallback(self): return None  # E1-E6 uz pokryto resolve_service
  1794	
  1795	# src/avatar/tasks/registry.py — registrace:
  1796	from .dependency_resolution import DependencyResolutionTask
  1797	_default_registry.register(DependencyResolutionTask())
  1798	```
  1799	
  1800	### 11j. API endpointy
  1801	
  1802	```python
  1803	# src/store/api.py — v2_packs_router:
  1804	
  1805	class SuggestRequest(BaseModel):
  1806	    include_ai: bool = False          # Default OFF (R5)
  1807	    analyze_previews: bool = True
  1808	
  1809	class ApplyRequest(BaseModel):
  1810	    candidate_id: Optional[str] = None
  1811	    manual: Optional[ManualResolveData] = None
  1812	
  1813	@v2_packs_router.post("/{pack_name}/dependencies/{dep_id}/suggest")
  1814	def suggest_dependency_resolution(
  1815	    pack_name: str, dep_id: str,
  1816	    request: SuggestRequest,
  1817	    store=Depends(require_initialized),
  1818	):
  1819	    options = SuggestOptions(
  1820	        include_ai=request.include_ai,
  1821	        analyze_previews=request.analyze_previews,
  1822	    )
  1823	    return store.suggest_resolution(pack_name, dep_id, options)
  1824	
  1825	@v2_packs_router.post("/{pack_name}/dependencies/{dep_id}/apply")
  1826	def apply_dependency_resolution(
  1827	    pack_name: str, dep_id: str,
  1828	    request: ApplyRequest,
  1829	    store=Depends(require_initialized),
  1830	):
  1831	    if request.candidate_id:
  1832	        return store.apply_resolution(pack_name, dep_id, request.candidate_id)
  1833	    elif request.manual:
  1834	        return store.resolve_service.apply_manual(pack_name, dep_id, request.manual)
  1835	    raise HTTPException(400, "candidate_id or manual required")
  1836	```
  1837	
  1838	### 11k. Frontend — usePackData + DependencyResolverModal
  1839	
  1840	```typescript
  1841	// usePackData.ts — nove mutace:
  1842	
  1843	const suggestResolutionMutation = useMutation({
  1844	  mutationFn: async ({ depId, options }: SuggestParams) => {
  1845	    const res = await fetch(
  1846	      `/api/packs/${enc(packName)}/dependencies/${depId}/suggest`,
  1847	      { method: 'POST', headers: CT_JSON, body: JSON.stringify(options ?? {}) }
  1848	    )
  1849	    if (!res.ok) throw new Error(await res.text())
  1850	    return res.json() as Promise<SuggestResult>
  1851	  },
  1852	})
  1853	
  1854	const applyResolutionMutation = useMutation({
  1855	  mutationFn: async ({ depId, candidateId, manual }: ApplyParams) => {
  1856	    const res = await fetch(
  1857	      `/api/packs/${enc(packName)}/dependencies/${depId}/apply`,
  1858	      { method: 'POST', headers: CT_JSON, body: JSON.stringify(
  1859	        candidateId ? { candidate_id: candidateId } : { manual }
  1860	      )}

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/__init__.py | nl -ba | sed -n '560,760p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   560	            cover_url: User-selected thumbnail URL for pack cover
   561	            selected_version_ids: List of version IDs to import (creates one dependency per version)
   562	            additional_previews: Extra previews with nsfw flags [{url, nsfw}]
   563	
   564	        Returns:
   565	            Created Pack
   566	        """
   567	        from .pack_service import PreviewDownloadConfig
   568	
   569	        # Build download config from wizard options
   570	        download_config = PreviewDownloadConfig(
   571	            download_images=download_images,
   572	            download_videos=download_videos,
   573	            include_nsfw=include_nsfw,
   574	            video_quality=video_quality,
   575	            download_from_all_versions=download_from_all_versions,
   576	        )
   577	
   578	        pack = self.pack_service.import_from_civitai(
   579	            url=url,
   580	            download_previews=download_previews,
   581	            max_previews=max_previews,
   582	            pack_name=pack_name,
   583	            download_config=download_config,
   584	            cover_url=cover_url,
   585	            selected_version_ids=selected_version_ids,
   586	            additional_previews=additional_previews,
   587	        )
   588	
   589	        if add_to_global:
   590	            self.profile_service.add_pack_to_global(pack.name)
   591	
   592	        # Post-import: resolve dependencies via evidence ladder
   593	        self._post_import_resolve(pack)
   594	
   595	        return pack
   596	
   597	    def _try_load_config(self) -> Any:
   598	        """Load store config, returning None on failure."""
   599	        try:
   600	            return self.layout.load_config()
   601	        except Exception:
   602	            return None
   603	
   604	    def _post_import_resolve(self, pack: Pack) -> None:
   605	        """Run suggest/auto-apply for pack dependencies after import.
   606	
   607	        Extracts preview hints, runs suggest (E1-E6, no AI),
   608	        and auto-applies if a dominant TIER-1/2 candidate exists.
   609	        """
   610	        if not pack.dependencies:
   611	            return
   612	
   613	        try:
   614	            from src.utils.preview_meta_extractor import extract_preview_hints
   615	
   616	            # Collect preview filenames from pack
   617	            preview_filenames = []
   618	            for p in getattr(pack, "previews", []) or []:
   619	                fname = getattr(p, "filename", None) or getattr(p, "local_path", None)
   620	                if fname:
   621	                    preview_filenames.append(fname)
   622	
   623	            previews_path = self.layout.pack_previews_path(pack.name)
   624	            hints = extract_preview_hints(previews_path, preview_filenames) if preview_filenames else []
   625	
   626	            for dep in pack.dependencies:
   627	                # Skip deps that already have a concrete pinned selector
   628	                if dep.selector.strategy != SelectorStrategy.BASE_MODEL_HINT:
   629	                    continue
   630	
   631	                try:
   632	                    result = self.resolve_service.suggest(
   633	                        pack, dep.id,
   634	                        SuggestOptions(
   635	                            include_ai=False,
   636	                            preview_hints_override=hints,
   637	                        ),
   638	                    )
   639	
   640	                    if not result.candidates:
   641	                        continue
   642	
   643	                    top = result.candidates[0]
   644	                    if top.tier > 2:
   645	                        continue
   646	
   647	                    # Check margin: no other candidate within auto_apply_margin
   648	                    from .resolve_config import get_auto_apply_margin
   649	                    auto_margin = get_auto_apply_margin(self._try_load_config())
   650	                    if len(result.candidates) > 1:
   651	                        margin = top.confidence - result.candidates[1].confidence
   652	                    else:
   653	                        margin = 1.0
   654	
   655	                    if margin >= auto_margin:
   656	                        apply_result = self.resolve_service.apply(
   657	                            pack.name, dep.id, top.candidate_id,
   658	                            request_id=result.request_id,
   659	                        )
   660	                        if apply_result.success:
   661	                            logger.info(
   662	                                "[post-import] Auto-applied %s for dep '%s' (tier=%d, confidence=%.2f)",
   663	                                top.display_name, dep.id, top.tier, top.confidence,
   664	                            )
   665	                        else:
   666	                            logger.warning(
   667	                                "[post-import] Apply failed for dep '%s': %s",
   668	                                dep.id, apply_result.message,
   669	                            )
   670	
   671	                except Exception as e:
   672	                    logger.warning("[post-import] Resolve failed for dep '%s': %s", dep.id, e)
   673	
   674	        except Exception as e:
   675	            logger.warning("[post-import] Preview hint extraction failed: %s", e)
   676	
   677	    def resolve(
   678	        self,
   679	        pack_name: str,
   680	        progress_callback: Optional[Callable[[str, str], None]] = None,
   681	    ) -> PackLock:
   682	        """
   683	        Resolve all dependencies for a pack.
   684	        
   685	        Args:
   686	            pack_name: Pack to resolve
   687	            progress_callback: Optional callback (dep_id, status)
   688	        
   689	        Returns:
   690	            Updated PackLock
   691	        """
   692	        return self.pack_service.resolve_pack(pack_name, progress_callback)
   693	    
   694	    def install(
   695	        self,
   696	        pack_name: str,
   697	        progress_callback: Optional[Callable[[str, int, int], None]] = None,
   698	    ) -> List[str]:
   699	        """
   700	        Install all blobs for a pack.
   701	        
   702	        Args:
   703	            pack_name: Pack to install
   704	            progress_callback: Optional callback (dep_id, downloaded, total)
   705	        
   706	        Returns:
   707	            List of installed SHA256 hashes
   708	        """
   709	        return self.pack_service.install_pack(pack_name, progress_callback)
   710	
   711	    def suggest_resolution(
   712	        self,
   713	        pack_name: str,
   714	        dep_id: str,
   715	        options: Optional["SuggestOptions"] = None,
   716	    ) -> "SuggestResult":
   717	        """Suggest resolution candidates for a dependency."""
   718	        pack = self.get_pack(pack_name)
   719	        return self.resolve_service.suggest(pack, dep_id, options or SuggestOptions())
   720	
   721	    def apply_resolution(
   722	        self,
   723	        pack_name: str,
   724	        dep_id: str,
   725	        candidate_id: str,
   726	        request_id: Optional[str] = None,
   727	    ) -> "ApplyResult":
   728	        """Apply a resolution candidate."""
   729	        return self.resolve_service.apply(pack_name, dep_id, candidate_id, request_id)
   730	
   731	    def migrate_resolve_deps(
   732	        self,
   733	        dry_run: bool = True,
   734	    ) -> List[dict]:
   735	        """Migration helper: suggest resolution for deps without canonical_source.
   736	
   737	        Iterates all packs, finds deps with BASE_MODEL_HINT strategy
   738	        (not yet resolved), runs suggest, and optionally auto-applies.
   739	
   740	        Args:
   741	            dry_run: If True, only report what would change. If False, apply.
   742	
   743	        Returns:
   744	            List of dicts with migration results per pack/dep.
   745	        """
   746	        results = []
   747	        for pack_name in self.list_packs():
   748	            try:
   749	                pack = self.get_pack(pack_name)
   750	            except Exception:
   751	                continue
   752	
   753	            for dep in pack.dependencies:
   754	                # Only migrate deps that still use BASE_MODEL_HINT
   755	                if dep.selector.strategy != SelectorStrategy.BASE_MODEL_HINT:
   756	                    continue
   757	
   758	                entry = {
   759	                    "pack": pack_name,
   760	                    "dep_id": dep.id,

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/__init__.py | nl -ba | sed -n '760,860p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   760	                    "dep_id": dep.id,
   761	                    "current_strategy": dep.selector.strategy.value,
   762	                    "action": "skip",
   763	                    "candidates": [],
   764	                }
   765	
   766	                try:
   767	                    result = self.resolve_service.suggest(
   768	                        pack, dep.id,
   769	                        SuggestOptions(include_ai=False),
   770	                    )
   771	                    if result.candidates:
   772	                        top = result.candidates[0]
   773	                        entry["candidates"] = [
   774	                            {"name": c.display_name, "confidence": c.confidence, "tier": c.tier}
   775	                            for c in result.candidates[:3]
   776	                        ]
   777	
   778	                        if top.tier <= 2:
   779	                            from .resolve_config import get_auto_apply_margin
   780	                            auto_margin = get_auto_apply_margin(self._try_load_config())
   781	                            margin = 1.0
   782	                            if len(result.candidates) > 1:
   783	                                margin = top.confidence - result.candidates[1].confidence
   784	
   785	                            if margin >= auto_margin:
   786	                                if dry_run:
   787	                                    entry["action"] = "would_apply"
   788	                                    entry["would_apply"] = top.display_name
   789	                                else:
   790	                                    apply_result = self.resolve_service.apply(
   791	                                        pack_name, dep.id, top.candidate_id,
   792	                                        request_id=result.request_id,
   793	                                    )
   794	                                    if apply_result.success:
   795	                                        entry["action"] = "applied"
   796	                                        entry["applied"] = top.display_name
   797	                                    else:
   798	                                        entry["action"] = "apply_failed"
   799	                                        entry["error"] = apply_result.message
   800	                            else:
   801	                                entry["action"] = "ambiguous"
   802	                        else:
   803	                            entry["action"] = "low_confidence"
   804	                except Exception as e:
   805	                    entry["action"] = "error"
   806	                    entry["error"] = str(e)
   807	
   808	                results.append(entry)
   809	
   810	        return results
   811	
   812	    # =========================================================================
   813	    # Profile Operations
   814	    # =========================================================================
   815	    
   816	    def list_profiles(self) -> List[str]:
   817	        """List all profile names."""
   818	        return self.layout.list_profiles()
   819	    
   820	    def get_profile(self, profile_name: str) -> Profile:
   821	        """Get a profile by name."""
   822	        return self.layout.load_profile(profile_name)
   823	    
   824	    def get_global_profile(self) -> Profile:
   825	        """Get the global profile."""
   826	        return self.profile_service.load_global()
   827	    
   828	    def sync(
   829	        self,
   830	        profile_name: str,
   831	        ui_targets: Optional[List[str]] = None,
   832	        ui_set: Optional[str] = None,
   833	        install_missing: bool = True,
   834	    ) -> Dict[str, BuildReport]:
   835	        """
   836	        Sync a profile: install missing blobs and build views.
   837	        
   838	        Args:
   839	            profile_name: Profile to sync
   840	            ui_targets: List of UI names. If None, uses ui_set.
   841	            ui_set: Name of UI set to use. Uses default if None.
   842	            install_missing: If True, download missing blobs
   843	        
   844	        Returns:
   845	            Dict mapping ui -> BuildReport
   846	        """
   847	        if ui_targets is None:
   848	            ui_targets = self.get_ui_targets(ui_set)
   849	        
   850	        return self.profile_service.sync_profile(
   851	            profile_name,
   852	            ui_targets,
   853	            install_missing,
   854	        )
   855	    
   856	    # =========================================================================
   857	    # Use/Back Operations
   858	    # =========================================================================
   859	    
   860	    def use(

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/pack_service.py | nl -ba | sed -n '760,860p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   760	                                    file_id=alias.selector.civitai.file_id,
   761	                                ),
   762	                                download=ArtifactDownload(urls=[]),
   763	                                integrity=ArtifactIntegrity(sha256_verified=False),
   764	                            ),
   765	                        ))
   766	                    else:
   767	                        unresolved.append(UnresolvedDependency(
   768	                            dependency_id=dep.id,
   769	                            reason="unknown_base_model_alias",
   770	                            details={"base_model": dep.selector.base_model},
   771	                        ))
   772	                except Exception:
   773	                    unresolved.append(UnresolvedDependency(
   774	                        dependency_id=dep.id,
   775	                        reason="base_model_resolution_failed",
   776	                        details={"base_model": dep.selector.base_model},
   777	                    ))
   778	
   779	        logger.info(f"[PackService] Lock created: {len(resolved)} resolved, {len(unresolved)} unresolved")
   780	
   781	        return PackLock(
   782	            pack=pack.name,
   783	            resolved_at=datetime.now().isoformat(),
   784	            resolved=resolved,
   785	            unresolved=unresolved,
   786	        )
   787	
   788	    # =========================================================================
   789	    # Preview Download with Video Support
   790	    # =========================================================================
   791	
   792	    def _download_previews(
   793	        self,
   794	        pack_name: str,
   795	        version_data: Dict[str, Any],
   796	        max_count: int = 100,
   797	        detailed_version_images: Optional[List[Dict[str, Any]]] = None,
   798	        download_images: bool = True,
   799	        download_videos: bool = True,
   800	        include_nsfw: bool = True,
   801	        video_quality: int = 1080,
   802	        progress_callback: Optional[ProgressCallback] = None,
   803	    ) -> List[PreviewInfo]:
   804	        """
   805	        Download preview media for a pack with full video support.
   806	
   807	        Downloads are parallelized with ThreadPoolExecutor(max_workers=4) for
   808	        significantly faster import of packs with many previews.
   809	
   810	        This method handles downloading preview content from Civitai with
   811	        support for both images and videos. It includes configurable filtering
   812	        by media type and NSFW status, optimized video URLs, and progress
   813	        tracking for large downloads.
   814	        """
   815	        from concurrent.futures import ThreadPoolExecutor, as_completed
   816	        from ..utils.media_detection import (
   817	            detect_media_type,
   818	            get_video_thumbnail_url,
   819	            get_optimized_video_url,
   820	        )
   821	
   822	        # Use detailed_version_images if available (contains all versions),
   823	        # otherwise fall back to version_data.images (single version)
   824	        if detailed_version_images:
   825	            images = detailed_version_images[:max_count]
   826	        else:
   827	            images = version_data.get("images", [])[:max_count]
   828	
   829	        previews_dir = self.layout.pack_previews_path(pack_name)
   830	        previews_dir.mkdir(parents=True, exist_ok=True)
   831	
   832	        # Create lookup map for detailed images by URL (metadata merge)
   833	        detailed_map: Dict[str, Dict[str, Any]] = {}
   834	        if detailed_version_images:
   835	            for img in detailed_version_images:
   836	                url = img.get("url")
   837	                if url:
   838	                    detailed_map[url] = img
   839	
   840	        # =====================================================================
   841	        # Phase 1: Collect download tasks (serial, fast — no I/O)
   842	        # =====================================================================
   843	        download_tasks: List[Dict[str, Any]] = []
   844	        downloaded_urls: set = set()
   845	        preview_number = 0
   846	        total_count = len(images)
   847	
   848	        for i, img_data in enumerate(images):
   849	            url = img_data.get("url")
   850	            if not url:
   851	                continue
   852	
   853	            if url in downloaded_urls:
   854	                logger.debug(f"[PackService] Skipping duplicate URL: {url[:60]}...")
   855	                continue
   856	
   857	            # MERGE: Get richer data if available
   858	            detailed_img = detailed_map.get(url)
   859	            source_img = detailed_img if detailed_img else img_data
   860	

exec
/bin/bash -lc "git grep -n \"class DependencySelector\\|class CanonicalSource\\|class ResolveConfig\\|HUGGINGFACE_FILE\\|LOCAL_FILE\" feat/resolve-model-redesign -- src/store/models.py | sed -n '1,120p'" in /home/box/git/github/synapse
 succeeded in 0ms:
feat/resolve-model-redesign:src/store/models.py:59:    HUGGINGFACE_FILE = "huggingface_file"
feat/resolve-model-redesign:src/store/models.py:61:    LOCAL_FILE = "local_file"
feat/resolve-model-redesign:src/store/models.py:243:class ResolveConfig(BaseModel):
feat/resolve-model-redesign:src/store/models.py:381:class CanonicalSource(BaseModel):
feat/resolve-model-redesign:src/store/models.py:398:class DependencySelector(BaseModel):

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/models.py | nl -ba | sed -n '40,80p' && git show feat/resolve-model-redesign:src/store/models.py | nl -ba | sed -n '235,420p'" in /home/box/git/github/synapse
 succeeded in 0ms:
    40	    DIFFUSION_MODEL = "diffusion_model"
    41	    EMBEDDING = "embedding"
    42	    CUSTOM_NODE = "custom_node"
    43	    UNET = "unet"
    44	    UNKNOWN = "unknown"
    45	
    46	
    47	class ProviderName(str, Enum):
    48	    """Supported asset providers."""
    49	    CIVITAI = "civitai"
    50	    HUGGINGFACE = "huggingface"
    51	    LOCAL = "local"
    52	    URL = "url"
    53	
    54	
    55	class SelectorStrategy(str, Enum):
    56	    """Selector strategies for resolving dependencies."""
    57	    CIVITAI_FILE = "civitai_file"
    58	    CIVITAI_MODEL_LATEST = "civitai_model_latest"
    59	    HUGGINGFACE_FILE = "huggingface_file"
    60	    BASE_MODEL_HINT = "base_model_hint"
    61	    LOCAL_FILE = "local_file"
    62	    URL_DOWNLOAD = "url_download"
    63	
    64	
    65	class UpdatePolicyMode(str, Enum):
    66	    """Update policy modes for dependencies."""
    67	    PINNED = "pinned"
    68	    FOLLOW_LATEST = "follow_latest"
    69	
    70	
    71	class ConflictMode(str, Enum):
    72	    """Conflict resolution modes."""
    73	    LAST_WINS = "last_wins"
    74	    FIRST_WINS = "first_wins"
    75	    STRICT = "strict"
    76	
    77	
    78	class PackCategory(str, Enum):
    79	    """
    80	    Category determines pack's origin and editability.
   235	class BackupConfig(BaseModel):
   236	    """Configuration for backup storage."""
   237	    enabled: bool = False
   238	    path: Optional[str] = None  # e.g., "/mnt/external/synapse-backup" or "D:\\SynapseBackup"
   239	    auto_backup_new: bool = False  # Automatically backup new blobs
   240	    warn_before_delete_last_copy: bool = True  # Warn when deleting last copy
   241	
   242	
   243	class ResolveConfig(BaseModel):
   244	    """Configuration for dependency resolution."""
   245	    auto_apply_margin: float = Field(default=0.15, ge=0.0, le=1.0)  # Min confidence gap for auto-apply
   246	    enable_ai: bool = True  # Enable AI-assisted resolution (E7 provider)
   247	
   248	
   249	class StoreConfig(BaseModel):
   250	    """Main store configuration (state/config.json)."""
   251	    schema_: str = Field(default="synapse.config.v2", alias="schema")
   252	    defaults: ConfigDefaults = Field(default_factory=ConfigDefaults)
   253	    ui: UIConfig = Field(default_factory=UIConfig)
   254	    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
   255	    base_model_aliases: Dict[str, BaseModelAlias] = Field(default_factory=dict)
   256	    backup: BackupConfig = Field(default_factory=BackupConfig)
   257	    resolve: ResolveConfig = Field(default_factory=ResolveConfig)
   258	
   259	    model_config = {"populate_by_name": True}
   260	    
   261	    @classmethod
   262	    def create_default(cls) -> "StoreConfig":
   263	        """Create default configuration with all defaults populated."""
   264	        config = cls()
   265	        config.ui.kind_map = UIConfig.get_default_kind_maps()
   266	        config.providers = {
   267	            "civitai": ProviderConfig(),
   268	            "huggingface": ProviderConfig(
   269	                primary_file_only_default=False,
   270	                preferred_ext=[".safetensors", ".bin", ".gguf"]
   271	            ),
   272	        }
   273	        # Default base model aliases for common models
   274	        config.base_model_aliases = cls._get_default_base_model_aliases()
   275	        return config
   276	    
   277	    @staticmethod
   278	    def _get_default_base_model_aliases() -> Dict[str, BaseModelAlias]:
   279	        """Get default base model aliases for well-known models."""
   280	        return {
   281	            # These are placeholder values - real IDs should be filled in
   282	            "SD1.5": BaseModelAlias(
   283	                kind=AssetKind.CHECKPOINT,
   284	                default_expose_filename="v1-5-pruned-emaonly.safetensors",
   285	                selector=BaseModelAliasSelector(
   286	                    strategy=SelectorStrategy.CIVITAI_FILE,
   287	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   288	                )
   289	            ),
   290	            "SDXL": BaseModelAlias(
   291	                kind=AssetKind.CHECKPOINT,
   292	                default_expose_filename="sd_xl_base_1.0.safetensors",
   293	                selector=BaseModelAliasSelector(
   294	                    strategy=SelectorStrategy.CIVITAI_FILE,
   295	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   296	                )
   297	            ),
   298	            "Illustrious": BaseModelAlias(
   299	                kind=AssetKind.CHECKPOINT,
   300	                default_expose_filename="illustrious_v1.safetensors",
   301	                selector=BaseModelAliasSelector(
   302	                    strategy=SelectorStrategy.CIVITAI_FILE,
   303	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   304	                )
   305	            ),
   306	            "Pony": BaseModelAlias(
   307	                kind=AssetKind.CHECKPOINT,
   308	                default_expose_filename="ponyDiffusionV6XL.safetensors",
   309	                selector=BaseModelAliasSelector(
   310	                    strategy=SelectorStrategy.CIVITAI_FILE,
   311	                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
   312	                )
   313	            ),
   314	        }
   315	
   316	
   317	# =============================================================================
   318	# UI Sets Model (state/ui_sets.json)
   319	# =============================================================================
   320	
   321	class UISets(BaseModel):
   322	    """UI sets configuration (state/ui_sets.json)."""
   323	    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
   324	    sets: Dict[str, List[str]] = Field(default_factory=dict)
   325	    
   326	    model_config = {"populate_by_name": True}
   327	    
   328	    @classmethod
   329	    def create_default(cls) -> "UISets":
   330	        """
   331	        Create default UI sets.
   332	        
   333	        Includes:
   334	        - Named sets (local, all)
   335	        - Implicit singleton sets for each UI (comfyui, forge, a1111, sdnext)
   336	          This allows UI to send ui_set="comfyui" and it works.
   337	        """
   338	        return cls(
   339	            sets={
   340	                # Named sets
   341	                "local": ["comfyui", "forge"],
   342	                "comfy_only": ["comfyui"],
   343	                "all": ["comfyui", "forge", "a1111", "sdnext"],
   344	                # Implicit singleton sets - each UI can be targeted directly
   345	                "comfyui": ["comfyui"],
   346	                "forge": ["forge"],
   347	                "a1111": ["a1111"],
   348	                "sdnext": ["sdnext"],
   349	            }
   350	        )
   351	
   352	
   353	# =============================================================================
   354	# Pack Models (state/packs/<Pack>/pack.json)
   355	# =============================================================================
   356	
   357	class CivitaiSelector(BaseModel):
   358	    """Civitai-specific selector data."""
   359	    model_config = ConfigDict(protected_namespaces=())
   360	    
   361	    model_id: int
   362	    version_id: Optional[int] = None
   363	    file_id: Optional[int] = None
   364	
   365	
   366	class HuggingFaceSelector(BaseModel):
   367	    """HuggingFace-specific selector data."""
   368	    repo_id: str
   369	    filename: str
   370	    revision: Optional[str] = None
   371	    subfolder: Optional[str] = None
   372	
   373	
   374	class SelectorConstraints(BaseModel):
   375	    """Constraints for file selection."""
   376	    primary_file_only: bool = True
   377	    file_ext: List[str] = Field(default_factory=lambda: [".safetensors"])
   378	    base_model_hint: Optional[str] = None
   379	
   380	
   381	class CanonicalSource(BaseModel):
   382	    """Remote identity for update tracking — independent of install strategy.
   383	
   384	    Allows a locally-installed file to track its canonical remote source
   385	    for update checking and re-downloading.
   386	    """
   387	    provider: Literal["civitai", "huggingface"]
   388	    model_id: Optional[int] = None       # Civitai
   389	    version_id: Optional[int] = None     # Civitai
   390	    file_id: Optional[int] = None        # Civitai
   391	    repo_id: Optional[str] = None        # HuggingFace
   392	    filename: Optional[str] = None
   393	    subfolder: Optional[str] = None      # HF repos with multiple subfolders
   394	    revision: Optional[str] = None       # HF commit/tag
   395	    sha256: Optional[str] = None
   396	
   397	
   398	class DependencySelector(BaseModel):
   399	    """Selector for resolving a dependency."""
   400	    strategy: SelectorStrategy
   401	    civitai: Optional[CivitaiSelector] = None
   402	    huggingface: Optional[HuggingFaceSelector] = None
   403	    base_model: Optional[str] = None  # For base_model_hint strategy
   404	    url: Optional[str] = None  # For url_download strategy
   405	    local_path: Optional[str] = None  # For local_file strategy
   406	    constraints: Optional[SelectorConstraints] = None
   407	    canonical_source: Optional[CanonicalSource] = None
   408	
   409	
   410	class UpdatePolicy(BaseModel):
   411	    """Update policy for a dependency."""
   412	    mode: UpdatePolicyMode = UpdatePolicyMode.PINNED
   413	    
   414	    @classmethod
   415	    def from_string(cls, value: str) -> "UpdatePolicy":
   416	        """Create UpdatePolicy from string shorthand."""
   417	        return cls(mode=UpdatePolicyMode(value))
   418	
   419	
   420	class ExposeConfig(BaseModel):

exec
/bin/bash -lc "git grep -n \"apply_dependency_resolution\" feat/resolve-model-redesign -- src/store/pack_service.py src/store/__init__.py tests | sed -n '1,160p'" in /home/box/git/github/synapse
 succeeded in 0ms:
feat/resolve-model-redesign:src/store/pack_service.py:1217:    def apply_dependency_resolution(
feat/resolve-model-redesign:src/store/pack_service.py:1260:            "[apply_dependency_resolution] %s/%s → strategy=%s%s",
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:7:- PackService.apply_dependency_resolution() — single write path
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:79:    def test_apply_dependency_resolution_preserves_base_model(self, tmp_path):
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:80:        """apply_dependency_resolution changes selector, NOT base_model."""
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:95:        ps.apply_dependency_resolution(
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:113:# PackService.apply_dependency_resolution()
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:132:        ps.apply_dependency_resolution("test-lora-pack", "main_lora", new_selector)
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:157:        ps.apply_dependency_resolution(
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:177:            ps.apply_dependency_resolution(
feat/resolve-model-redesign:tests/unit/store/test_phase1_bug_fixes.py:191:        ps.apply_dependency_resolution(
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:177:        ps.apply_dependency_resolution = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:441:        ps.apply_dependency_resolution = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:545:        ps.apply_dependency_resolution.assert_called_once()
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:546:        call_kwargs = ps.apply_dependency_resolution.call_args
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:797:        ps.apply_dependency_resolution = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:817:        ps.apply_dependency_resolution.assert_called_once()
feat/resolve-model-redesign:tests/unit/store/test_resolve_review_fixes.py:820:        call_kw = ps.apply_dependency_resolution.call_args.kwargs
feat/resolve-model-redesign:tests/unit/store/test_resolve_service.py:295:        ps.apply_dependency_resolution = MagicMock()
feat/resolve-model-redesign:tests/unit/store/test_resolve_service.py:316:        ps.apply_dependency_resolution = MagicMock()

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/pack_service.py | nl -ba | sed -n '1220,1295p'" in /home/box/git/github/synapse
 succeeded in 0ms:
  1220	        dep_id: str,
  1221	        selector: DependencySelector,
  1222	        canonical_source: Optional[CanonicalSource] = None,
  1223	        lock_entry: Optional[ResolvedDependency] = None,
  1224	        display_name: Optional[str] = None,
  1225	    ) -> None:
  1226	        """Apply a resolved dependency selector to a pack.
  1227	
  1228	        This is the SINGLE write path for ResolveService — it updates
  1229	        pack.json with the new selector and optionally canonical_source.
  1230	        Does NOT touch pack.lock.json (that's resolve_pack's job).
  1231	
  1232	        Args:
  1233	            pack_name: Pack to update.
  1234	            dep_id: Dependency ID to update.
  1235	            selector: New DependencySelector to apply.
  1236	            canonical_source: Optional canonical source for update tracking.
  1237	            lock_entry: Optional pre-resolved lock entry (not used yet).
  1238	            display_name: Optional display name (logged, not stored).
  1239	        """
  1240	        pack = self.layout.load_pack(pack_name)
  1241	
  1242	        # Find dependency
  1243	        dep = None
  1244	        for d in pack.dependencies:
  1245	            if d.id == dep_id:
  1246	                dep = d
  1247	                break
  1248	
  1249	        if dep is None:
  1250	            raise ValueError(f"Dependency '{dep_id}' not found in pack '{pack_name}'")
  1251	
  1252	        # Update selector
  1253	        dep.selector = selector
  1254	
  1255	        # Set canonical_source if provided
  1256	        if canonical_source:
  1257	            dep.selector.canonical_source = canonical_source
  1258	
  1259	        logger.info(
  1260	            "[apply_dependency_resolution] %s/%s → strategy=%s%s",
  1261	            pack_name, dep_id, selector.strategy.value,
  1262	            f" ({display_name})" if display_name else "",
  1263	        )
  1264	
  1265	        self.layout.save_pack(pack)
  1266	
  1267	    def _ensure_resolvers(self) -> None:
  1268	        """Lazily initialize default resolvers if none were provided."""
  1269	        if self._resolvers:
  1270	            return
  1271	
  1272	        from .dependency_resolver import (
  1273	            BaseModelHintResolver,
  1274	            CivitaiFileResolver,
  1275	            CivitaiLatestResolver,
  1276	            HuggingFaceResolver,
  1277	            LocalFileResolver,
  1278	            UrlResolver,
  1279	        )
  1280	
  1281	        self._resolvers = {
  1282	            SelectorStrategy.CIVITAI_FILE: CivitaiFileResolver(self.civitai),
  1283	            SelectorStrategy.CIVITAI_MODEL_LATEST: CivitaiLatestResolver(self.civitai),
  1284	            SelectorStrategy.BASE_MODEL_HINT: BaseModelHintResolver(self.civitai, self.layout),
  1285	            SelectorStrategy.HUGGINGFACE_FILE: HuggingFaceResolver(),
  1286	            SelectorStrategy.URL_DOWNLOAD: UrlResolver(),
  1287	            SelectorStrategy.LOCAL_FILE: LocalFileResolver(),
  1288	        }
  1289	
  1290	    def _resolve_dependency(
  1291	        self,
  1292	        pack: Pack,
  1293	        dep: PackDependency,
  1294	        existing_lock: Optional[PackLock],
  1295	    ) -> Optional[ResolvedArtifact]:

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_validation.py | nl -ba | sed -n '1,180p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Resolve validation — per-strategy minimum field checks and cross-kind validation.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 sections 5, 2h.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from typing import Dict, List, Optional, Tuple
    10	
    11	from .models import AssetKind, DependencySelector, SelectorStrategy
    12	from .resolve_config import check_cross_kind_compatibility
    13	from .resolve_models import ApplyResult
    14	
    15	# Per-strategy required fields: (field_path, human_label)
    16	STRATEGY_REQUIREMENTS: Dict[SelectorStrategy, List[Tuple[str, str]]] = {
    17	    SelectorStrategy.CIVITAI_FILE: [
    18	        ("civitai.model_id", "Civitai model ID"),
    19	        ("civitai.version_id", "Civitai version ID"),
    20	        ("civitai.file_id", "Civitai file ID"),
    21	    ],
    22	    SelectorStrategy.CIVITAI_MODEL_LATEST: [
    23	        ("civitai.model_id", "Civitai model ID"),
    24	    ],
    25	    SelectorStrategy.HUGGINGFACE_FILE: [
    26	        ("huggingface.repo_id", "HuggingFace repo ID"),
    27	        ("huggingface.filename", "HuggingFace filename"),
    28	    ],
    29	    SelectorStrategy.LOCAL_FILE: [
    30	        ("local_path", "Local file: requires local_path"),
    31	    ],
    32	    SelectorStrategy.URL_DOWNLOAD: [
    33	        ("url", "Download URL"),
    34	    ],
    35	    SelectorStrategy.BASE_MODEL_HINT: [
    36	        ("base_model", "Base model alias"),
    37	    ],
    38	}
    39	
    40	
    41	def _get_field(selector: DependencySelector, field_path: str) -> object:
    42	    """Get a nested field from selector by dot-separated path."""
    43	    parts = field_path.split(".")
    44	    obj = selector
    45	    for part in parts:
    46	        if obj is None:
    47	            return None
    48	        obj = getattr(obj, part, None)
    49	    return obj
    50	
    51	
    52	def validate_selector_fields(selector: DependencySelector) -> ApplyResult:
    53	    """Validate that a selector has all required fields for its strategy.
    54	
    55	    Returns ApplyResult with success=False if validation fails.
    56	    """
    57	    reqs = STRATEGY_REQUIREMENTS.get(selector.strategy, [])
    58	    missing = []
    59	
    60	    for field_path, label in reqs:
    61	        value = _get_field(selector, field_path)
    62	        if value is None or value == "":
    63	            missing.append(label)
    64	        elif isinstance(value, int) and value == 0:
    65	            missing.append(f"{label} (invalid zero value)")
    66	
    67	    if missing:
    68	        return ApplyResult(
    69	            success=False,
    70	            message=f"Selector validation failed: Missing required field: {missing[0]}",
    71	        )
    72	
    73	    return ApplyResult(success=True, message="Validation passed")
    74	
    75	
    76	def validate_candidate(
    77	    selector: DependencySelector,
    78	    kind: AssetKind,
    79	    pack_base_model: Optional[str] = None,
    80	    candidate_base_model: Optional[str] = None,
    81	) -> ApplyResult:
    82	    """Full validation: field check + cross-kind compatibility.
    83	
    84	    Returns ApplyResult. On success, compatibility_warnings may be non-empty
    85	    (warnings don't block apply, but should be shown to the user).
    86	    """
    87	    # Step 1: Field validation
    88	    field_result = validate_selector_fields(selector)
    89	    if not field_result.success:
    90	        return field_result
    91	
    92	    # Step 2: Cross-kind compatibility
    93	    warnings = check_cross_kind_compatibility(
    94	        pack_base_model, candidate_base_model, kind,
    95	    )
    96	
    97	    return ApplyResult(
    98	        success=True,
    99	        message="Validation passed",
   100	        compatibility_warnings=warnings,
   101	    )
   102	
   103	
   104	def validate_before_apply(
   105	    selector: DependencySelector,
   106	    kind: AssetKind,
   107	    pack_base_model: Optional[str] = None,
   108	    candidate_base_model: Optional[str] = None,
   109	) -> ApplyResult:
   110	    """Convenience alias for validate_candidate."""
   111	    return validate_candidate(selector, kind, pack_base_model, candidate_base_model)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/store/resolve_scoring.py | nl -ba | sed -n '1,180p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Resolve scoring — Noisy-OR combination, provenance grouping, tier ceiling.
     3	
     4	Based on PLAN-Resolve-Model.md v0.7.1 section 2g.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	from collections import defaultdict
    10	from typing import Dict, List
    11	
    12	from .resolve_config import TIER_CONFIGS, get_tier_for_confidence
    13	from .resolve_models import EvidenceGroup, EvidenceHit, EvidenceItem
    14	
    15	
    16	def group_by_provenance(hits: List[EvidenceHit]) -> Dict[str, EvidenceGroup]:
    17	    """Group evidence hits by provenance, per candidate.
    18	
    19	    Within each group: combined_confidence = max(item.confidence).
    20	    """
    21	    groups: Dict[str, List[EvidenceItem]] = defaultdict(list)
    22	
    23	    for hit in hits:
    24	        groups[hit.provenance].append(hit.item)
    25	
    26	    result: Dict[str, EvidenceGroup] = {}
    27	    for provenance, items in groups.items():
    28	        combined = max(item.confidence for item in items)
    29	        result[provenance] = EvidenceGroup(
    30	            provenance=provenance,
    31	            items=items,
    32	            combined_confidence=combined,
    33	        )
    34	
    35	    return result
    36	
    37	
    38	def noisy_or(confidences: List[float]) -> float:
    39	    """Combine independent confidence values using Noisy-OR.
    40	
    41	    P(correct) = 1 - product(1 - c_i for each c_i)
    42	    """
    43	    if not confidences:
    44	        return 0.0
    45	
    46	    product = 1.0
    47	    for c in confidences:
    48	        product *= (1.0 - c)
    49	
    50	    return 1.0 - product
    51	
    52	
    53	def get_tier_ceiling(groups: List[EvidenceGroup]) -> float:
    54	    """Get the tier ceiling — the max of the best evidence tier.
    55	
    56	    The final confidence is capped by the maximum confidence allowed
    57	    by the best (lowest-numbered) tier present in the evidence.
    58	    """
    59	    if not groups:
    60	        return 0.49  # Default: Tier 4 ceiling
    61	
    62	    best_tier = 4
    63	    for group in groups:
    64	        for item in group.items:
    65	            tier = get_tier_for_confidence(item.confidence)
    66	            if tier < best_tier:
    67	                best_tier = tier
    68	
    69	    # Return the max confidence of that tier
    70	    for tc in TIER_CONFIGS:
    71	        if tc.tier == best_tier:
    72	            return tc.max
    73	
    74	    return 0.49
    75	
    76	
    77	def score_candidate(groups: List[EvidenceGroup]) -> float:
    78	    """Score a candidate using provenance grouping + Noisy-OR + tier ceiling.
    79	
    80	    Steps:
    81	    1. Each group contributes its combined_confidence (max within group)
    82	    2. Independent groups combine via Noisy-OR
    83	    3. Final confidence is capped by the tier ceiling of the best evidence
    84	    """
    85	    if not groups:
    86	        return 0.0
    87	
    88	    # Step 1+2: Noisy-OR of group confidences
    89	    group_confidences = [g.combined_confidence for g in groups]
    90	    raw_score = noisy_or(group_confidences)
    91	
    92	    # Step 3: Cap by tier ceiling
    93	    ceiling = get_tier_ceiling(groups)
    94	    return min(raw_score, ceiling)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/utils/preview_meta_extractor.py | nl -ba | sed -n '1,260p'" in /home/box/git/github/synapse
 succeeded in 0ms:
     1	"""
     2	Preview metadata extractor — sidecar JSON reader + PNG tEXt parser.
     3	
     4	Extracts model hints from preview images for dependency resolution.
     5	Based on PLAN-Resolve-Model.md v0.7.1 sections 2e, Phase 0 item 8.
     6	
     7	Sources:
     8	- Civitai API sidecar .json: meta.Model, meta.resources[]
     9	- PNG tEXt chunks: A1111 parameters, ComfyUI workflow JSON
    10	"""
    11	
    12	from __future__ import annotations
    13	
    14	import json
    15	import logging
    16	import re
    17	import struct
    18	from dataclasses import dataclass, field
    19	from pathlib import Path
    20	from typing import Any, Dict, List, Optional
    21	
    22	from src.store.models import AssetKind
    23	from src.store.resolve_models import PreviewAnalysisResult, PreviewModelHint
    24	
    25	logger = logging.getLogger(__name__)
    26	
    27	
    28	# =============================================================================
    29	# ComfyUI Node Registry
    30	# =============================================================================
    31	
    32	@dataclass
    33	class ComfyUINodeDef:
    34	    """Definition of a ComfyUI node type for model extraction."""
    35	    kind: AssetKind
    36	    input_keys: List[str] = field(default_factory=list)
    37	
    38	
    39	COMFYUI_NODE_REGISTRY: Dict[str, ComfyUINodeDef] = {
    40	    # Checkpoints
    41	    "CheckpointLoaderSimple": ComfyUINodeDef(AssetKind.CHECKPOINT, ["ckpt_name"]),
    42	    "CheckpointLoader": ComfyUINodeDef(AssetKind.CHECKPOINT, ["ckpt_name"]),
    43	    "UNETLoader": ComfyUINodeDef(AssetKind.CHECKPOINT, ["unet_name"]),
    44	
    45	    # LoRA
    46	    "LoraLoader": ComfyUINodeDef(AssetKind.LORA, ["lora_name"]),
    47	    "LoRALoader": ComfyUINodeDef(AssetKind.LORA, ["lora_name"]),
    48	    "LoraLoaderModelOnly": ComfyUINodeDef(AssetKind.LORA, ["lora_name"]),
    49	
    50	    # VAE
    51	    "VAELoader": ComfyUINodeDef(AssetKind.VAE, ["vae_name"]),
    52	
    53	    # ControlNet
    54	    "ControlNetLoader": ComfyUINodeDef(AssetKind.CONTROLNET, ["control_net_name"]),
    55	    "DiffControlNetLoader": ComfyUINodeDef(AssetKind.CONTROLNET, ["model"]),
    56	
    57	    # CLIP
    58	    "CLIPLoader": ComfyUINodeDef(AssetKind.EMBEDDING, ["clip_name"]),
    59	    "DualCLIPLoader": ComfyUINodeDef(AssetKind.EMBEDDING, ["clip_name1", "clip_name2"]),
    60	    "CLIPVisionLoader": ComfyUINodeDef(AssetKind.EMBEDDING, ["clip_name"]),
    61	
    62	    # Upscaler
    63	    "UpscaleModelLoader": ComfyUINodeDef(AssetKind.UPSCALER, ["model_name"]),
    64	    "ImageUpscaleWithModel": ComfyUINodeDef(AssetKind.UPSCALER, ["model_name"]),
    65	
    66	    # IPAdapter / Style
    67	    "IPAdapterModelLoader": ComfyUINodeDef(AssetKind.LORA, ["ipadapter_file"]),
    68	    "StyleModelLoader": ComfyUINodeDef(AssetKind.LORA, ["style_model_name"]),
    69	
    70	    # AnimateDiff
    71	    "ADE_AnimateDiffLoaderWithContext": ComfyUINodeDef(AssetKind.CHECKPOINT, ["model_name"]),
    72	
    73	    # HighRes-Fix Script (has control_net_name + pixel_upscaler)
    74	    "HighRes-Fix Script": ComfyUINodeDef(AssetKind.CONTROLNET, ["control_net_name"]),
    75	}
    76	
    77	
    78	# Civitai resource type → AssetKind
    79	RESOURCE_TYPE_KIND: Dict[str, AssetKind] = {
    80	    "model": AssetKind.CHECKPOINT,
    81	    "checkpoint": AssetKind.CHECKPOINT,
    82	    "lora": AssetKind.LORA,
    83	    "vae": AssetKind.VAE,
    84	    "controlnet": AssetKind.CONTROLNET,
    85	    "embedding": AssetKind.EMBEDDING,
    86	    "textualinversion": AssetKind.EMBEDDING,
    87	    "upscaler": AssetKind.UPSCALER,
    88	}
    89	
    90	# Generation param keys to extract from sidecar meta
    91	_GEN_PARAM_KEYS = frozenset({
    92	    "prompt", "negativePrompt", "sampler", "steps", "cfgScale",
    93	    "seed", "Size", "Model hash", "Clip skip", "Denoising strength",
    94	})
    95	
    96	
    97	def extract_preview_hints(
    98	    previews_path: Path,
    99	    preview_filenames: List[str],
   100	) -> List[PreviewModelHint]:
   101	    """Extract model hints from preview images.
   102	
   103	    Reads sidecar .json files and (if available) PNG tEXt metadata.
   104	
   105	    Args:
   106	        previews_path: Path to the previews directory (resources/previews/).
   107	        preview_filenames: List of preview image filenames (e.g., ["001.png"]).
   108	
   109	    Returns:
   110	        List of PreviewModelHint with provenance tags.
   111	    """
   112	    hints: List[PreviewModelHint] = []
   113	
   114	    for filename in preview_filenames:
   115	        # Source 1: Sidecar JSON (Civitai API meta)
   116	        sidecar_hints = _extract_from_sidecar(previews_path, filename)
   117	        hints.extend(sidecar_hints)
   118	
   119	        # Source 2: PNG tEXt chunks (check magic bytes, not extension —
   120	        # Civitai often serves PNG files with .jpeg extension)
   121	        png_hints = _extract_from_png(previews_path, filename)
   122	        hints.extend(png_hints)
   123	
   124	    return hints
   125	
   126	
   127	def analyze_pack_previews(
   128	    previews_path: Path,
   129	    previews: List[Any],
   130	) -> List[PreviewAnalysisResult]:
   131	    """Full analysis: extract hints + generation params for each preview.
   132	
   133	    Args:
   134	        previews_path: Path to previews directory.
   135	        previews: Pack.previews list (PreviewInfo objects).
   136	
   137	    Returns:
   138	        List of PreviewAnalysisResult with hints and generation params.
   139	    """
   140	    results: List[PreviewAnalysisResult] = []
   141	
   142	    for preview in previews:
   143	        filename = getattr(preview, "filename", None)
   144	        if not filename:
   145	            continue
   146	
   147	        # Read sidecar once, extract both hints and gen params
   148	        sidecar_data = _read_sidecar(previews_path, filename)
   149	        hints: List[PreviewModelHint] = []
   150	        gen_params: Optional[Dict[str, Any]] = None
   151	
   152	        if sidecar_data is not None:
   153	            hints.extend(_parse_sidecar_meta(sidecar_data, filename))
   154	            gen_params = _extract_generation_params_from_data(sidecar_data)
   155	
   156	        # PNG tEXt (check magic bytes, not extension)
   157	        hints.extend(_extract_from_png(previews_path, filename))
   158	
   159	        results.append(PreviewAnalysisResult(
   160	            filename=filename,
   161	            url=getattr(preview, "url", None),
   162	            thumbnail_url=getattr(preview, "thumbnail_url", None),
   163	            media_type=getattr(preview, "media_type", "image"),
   164	            width=getattr(preview, "width", None),
   165	            height=getattr(preview, "height", None),
   166	            nsfw=getattr(preview, "nsfw", False),
   167	            hints=hints,
   168	            generation_params=gen_params,
   169	        ))
   170	
   171	    return results
   172	
   173	
   174	def _sanitize_filename(filename: str) -> Optional[str]:
   175	    """Validate and sanitize a preview filename to prevent path traversal.
   176	
   177	    Returns None if the filename is unsafe (contains path separators or ..).
   178	    """
   179	    if not filename or ".." in filename or "/" in filename or "\\" in filename:
   180	        return None
   181	    return filename
   182	
   183	
   184	def _read_sidecar(
   185	    previews_path: Path,
   186	    image_filename: str,
   187	) -> Optional[Dict[str, Any]]:
   188	    """Read and parse a sidecar JSON file. Returns None if missing or invalid."""
   189	    safe_name = _sanitize_filename(image_filename)
   190	    if safe_name is None:
   191	        logger.warning("Unsafe filename rejected: %s", image_filename)
   192	        return None
   193	    sidecar_path = previews_path / f"{safe_name}.json"
   194	    if not sidecar_path.exists():
   195	        return None
   196	
   197	    try:
   198	        return json.loads(sidecar_path.read_text(encoding="utf-8"))
   199	    except (json.JSONDecodeError, OSError) as e:
   200	        logger.warning("Failed to read sidecar %s: %s", sidecar_path, e)
   201	        return None
   202	
   203	
   204	def _extract_generation_params(
   205	    previews_path: Path,
   206	    image_filename: str,
   207	) -> Optional[Dict[str, Any]]:
   208	    """Extract raw generation parameters from sidecar JSON."""
   209	    data = _read_sidecar(previews_path, image_filename)
   210	    if data is None:
   211	        return None
   212	    return _extract_generation_params_from_data(data)
   213	
   214	
   215	def _extract_generation_params_from_data(
   216	    data: Dict[str, Any],
   217	) -> Optional[Dict[str, Any]]:
   218	    """Extract generation parameters from already-parsed sidecar data."""
   219	    # Support both formats: {"meta": {...}} wrapper and flat {...}
   220	    meta = data.get("meta")
   221	    if not isinstance(meta, dict):
   222	        meta = data
   223	
   224	    params: Dict[str, Any] = {}
   225	    for key in _GEN_PARAM_KEYS:
   226	        if key in meta:
   227	            params[key] = meta[key]
   228	
   229	    # Also collect these common variants
   230	    if "cfg_scale" in meta:
   231	        params["cfgScale"] = meta["cfg_scale"]
   232	    if "negative_prompt" in meta:
   233	        params["negativePrompt"] = meta["negative_prompt"]
   234	
   235	    return params if params else None
   236	
   237	
   238	def _extract_from_sidecar(
   239	    previews_path: Path,
   240	    image_filename: str,
   241	) -> List[PreviewModelHint]:
   242	    """Extract hints from Civitai API sidecar JSON.
   243	
   244	    Sidecar files are stored as <image_filename>.json (e.g., 001.png.json).
   245	    """
   246	    data = _read_sidecar(previews_path, image_filename)
   247	    if data is None:
   248	        return []
   249	    return _parse_sidecar_meta(data, image_filename)
   250	
   251	
   252	def _parse_sidecar_meta(
   253	    data: Dict[str, Any],
   254	    source_image: str,
   255	) -> List[PreviewModelHint]:
   256	    """Parse Civitai API meta from sidecar JSON.
   257	
   258	    Supports both formats:
   259	    - Wrapped: {"meta": {"Model": "...", "resources": [...]}}
   260	    - Flat: {"Model": "...", "resources": [...]} (real Civitai sidecars)

exec
/bin/bash -lc "git show feat/resolve-model-redesign:src/utils/preview_meta_extractor.py | nl -ba | sed -n '252,620p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   252	def _parse_sidecar_meta(
   253	    data: Dict[str, Any],
   254	    source_image: str,
   255	) -> List[PreviewModelHint]:
   256	    """Parse Civitai API meta from sidecar JSON.
   257	
   258	    Supports both formats:
   259	    - Wrapped: {"meta": {"Model": "...", "resources": [...]}}
   260	    - Flat: {"Model": "...", "resources": [...]} (real Civitai sidecars)
   261	    """
   262	    hints: List[PreviewModelHint] = []
   263	
   264	    # BUG 7 fix: Support both wrapped and flat sidecar formats
   265	    meta = data.get("meta")
   266	    if not isinstance(meta, dict):
   267	        meta = data  # Flat format (real Civitai sidecars)
   268	
   269	    # Extract short hash for checkpoint hints
   270	    model_hash = meta.get("Model hash")
   271	    if isinstance(model_hash, str):
   272	        model_hash = model_hash.strip()
   273	    else:
   274	        model_hash = None
   275	
   276	    # meta.Model or meta.model_name → checkpoint hint
   277	    model_name = meta.get("Model") or meta.get("model_name")
   278	    model_name_normalized: Optional[str] = None
   279	    if model_name and isinstance(model_name, str):
   280	        model_name_normalized = _normalize_filename(model_name).lower()
   281	        hints.append(PreviewModelHint(
   282	            filename=_normalize_filename(model_name),
   283	            kind=AssetKind.CHECKPOINT,
   284	            source_image=source_image,
   285	            source_type="api_meta",
   286	            raw_value=model_name,
   287	            hash=model_hash,
   288	        ))
   289	
   290	    # meta.resources[] → additional model hints (dedup against Model field)
   291	    resources = meta.get("resources")
   292	    seen_resource_names: set[str] = set()
   293	    if isinstance(resources, list):
   294	        for res in resources:
   295	            if not isinstance(res, dict):
   296	                continue
   297	            hint = _parse_resource(res, source_image)
   298	            if hint:
   299	                # Skip if this resource duplicates the Model field checkpoint
   300	                if (model_name_normalized
   301	                        and hint.kind == AssetKind.CHECKPOINT
   302	                        and hint.filename.lower() == model_name_normalized):
   303	                    continue
   304	                seen_resource_names.add(hint.filename.lower())
   305	                hints.append(hint)
   306	
   307	    # Extract LoRA tags from prompt text (dedup against resources)
   308	    prompt_text = meta.get("prompt")
   309	    if isinstance(prompt_text, str):
   310	        lora_matches = re.findall(r"<lora:([^:>]+):([^>]+)>", prompt_text)
   311	        for lora_name, weight_str in lora_matches:
   312	            normalized = _normalize_filename(lora_name)
   313	            if normalized.lower() in seen_resource_names:
   314	                continue  # Already found in resources[]
   315	            weight = _parse_float(weight_str)
   316	            hints.append(PreviewModelHint(
   317	                filename=normalized,
   318	                kind=AssetKind.LORA,
   319	                source_image=source_image,
   320	                source_type="api_meta",
   321	                raw_value=lora_name,
   322	                weight=weight,
   323	            ))
   324	
   325	    return hints
   326	
   327	
   328	def _parse_resource(
   329	    resource: Dict[str, Any],
   330	    source_image: str,
   331	) -> Optional[PreviewModelHint]:
   332	    """Parse a single resource entry from meta.resources[]."""
   333	    name = resource.get("name")
   334	    if not name or not isinstance(name, str):
   335	        return None
   336	
   337	    res_type = (resource.get("type") or "").lower()
   338	    kind = RESOURCE_TYPE_KIND.get(res_type)
   339	
   340	    # Extract hash and weight from resource
   341	    res_hash = resource.get("hash")
   342	    if not isinstance(res_hash, str):
   343	        res_hash = None
   344	    weight = resource.get("weight")
   345	    if not isinstance(weight, (int, float)):
   346	        weight = None
   347	    else:
   348	        weight = float(weight)
   349	
   350	    return PreviewModelHint(
   351	        filename=_normalize_filename(name),
   352	        kind=kind,
   353	        source_image=source_image,
   354	        source_type="api_meta",
   355	        raw_value=name,
   356	        hash=res_hash,
   357	        weight=weight,
   358	    )
   359	
   360	
   361	_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
   362	
   363	
   364	def _read_png_text_chunks(file_path: Path) -> Dict[str, str]:
   365	    """Read tEXt chunks from a PNG file. Returns empty dict if not PNG.
   366	
   367	    Checks magic bytes — works regardless of file extension.
   368	    Civitai often serves PNG files with .jpeg extension.
   369	    """
   370	    try:
   371	        with open(file_path, "rb") as f:
   372	            sig = f.read(8)
   373	            if sig != _PNG_SIGNATURE:
   374	                return {}
   375	
   376	            chunks: Dict[str, str] = {}
   377	            while True:
   378	                header = f.read(8)
   379	                if len(header) < 8:
   380	                    break
   381	                length = struct.unpack(">I", header[:4])[0]
   382	                chunk_type = header[4:8]
   383	
   384	                # Only read tEXt chunks, skip everything else efficiently
   385	                if chunk_type == b"tEXt":
   386	                    chunk_data = f.read(length)
   387	                    f.read(4)  # CRC
   388	                    null_pos = chunk_data.find(b"\x00")
   389	                    if null_pos != -1:
   390	                        key = chunk_data[:null_pos].decode("latin-1")
   391	                        value = chunk_data[null_pos + 1 :].decode("utf-8", errors="replace")
   392	                        chunks[key] = value
   393	                elif chunk_type == b"IEND":
   394	                    break
   395	                else:
   396	                    # Skip chunk data + CRC without reading into memory
   397	                    f.seek(length + 4, 1)
   398	
   399	            return chunks
   400	    except OSError as e:
   401	        logger.warning("Failed to read PNG chunks from %s: %s", file_path, e)
   402	        return {}
   403	
   404	
   405	def _extract_from_png(
   406	    previews_path: Path,
   407	    image_filename: str,
   408	) -> List[PreviewModelHint]:
   409	    """Extract hints from PNG tEXt chunks (A1111/ComfyUI metadata).
   410	
   411	    Checks PNG magic bytes, not file extension — handles Civitai's
   412	    PNG-with-.jpeg-extension files correctly.
   413	    """
   414	    safe_name = _sanitize_filename(image_filename)
   415	    if safe_name is None:
   416	        return []
   417	    file_path = previews_path / safe_name
   418	    if not file_path.exists():
   419	        return []
   420	
   421	    text_data = _read_png_text_chunks(file_path)
   422	    if not text_data:
   423	        return []
   424	
   425	    hints: List[PreviewModelHint] = []
   426	
   427	    # A1111: tEXt[parameters] → "Model: dreamshaper_8, ..."
   428	    parameters = text_data.get("parameters", "")
   429	    if parameters:
   430	        a1111_hints = _parse_a1111_parameters(parameters, image_filename)
   431	        hints.extend(a1111_hints)
   432	
   433	    # ComfyUI: tEXt[prompt] → JSON workflow
   434	    prompt = text_data.get("prompt", "")
   435	    if prompt:
   436	        comfy_hints = _parse_comfyui_workflow(prompt, image_filename)
   437	        hints.extend(comfy_hints)
   438	
   439	    return hints
   440	
   441	
   442	def _parse_a1111_parameters(
   443	    parameters: str,
   444	    source_image: str,
   445	) -> List[PreviewModelHint]:
   446	    """Parse A1111 parameters string for model references."""
   447	    hints: List[PreviewModelHint] = []
   448	
   449	    # "Model: dreamshaper_8" or "Model: illustriousXL_v060"
   450	    model_match = re.search(r"Model:\s*([^\s,]+)", parameters)
   451	    if model_match:
   452	        model_name = model_match.group(1)
   453	        # Extract model hash if present
   454	        hash_match = re.search(r"Model hash:\s*([0-9a-fA-F]+)", parameters)
   455	        model_hash = hash_match.group(1) if hash_match else None
   456	        hints.append(PreviewModelHint(
   457	            filename=_normalize_filename(model_name),
   458	            kind=AssetKind.CHECKPOINT,
   459	            source_image=source_image,
   460	            source_type="png_embedded",
   461	            raw_value=model_name,
   462	            hash=model_hash,
   463	        ))
   464	
   465	    # LoRA references: "<lora:name:weight>"
   466	    lora_matches = re.findall(r"<lora:([^:>]+):([^>]+)>", parameters)
   467	    for lora_name, weight_str in lora_matches:
   468	        weight = _parse_float(weight_str)
   469	        hints.append(PreviewModelHint(
   470	            filename=_normalize_filename(lora_name),
   471	            kind=AssetKind.LORA,
   472	            source_image=source_image,
   473	            source_type="png_embedded",
   474	            raw_value=lora_name,
   475	            weight=weight,
   476	        ))
   477	
   478	    return hints
   479	
   480	
   481	def _parse_comfyui_workflow(
   482	    prompt_json: str,
   483	    source_image: str,
   484	) -> List[PreviewModelHint]:
   485	    """Parse ComfyUI workflow JSON for model references."""
   486	    try:
   487	        workflow = json.loads(prompt_json)
   488	    except json.JSONDecodeError:
   489	        return []
   490	
   491	    if not isinstance(workflow, dict):
   492	        return []
   493	
   494	    hints: List[PreviewModelHint] = []
   495	
   496	    for _node_id, node in workflow.items():
   497	        if not isinstance(node, dict):
   498	            continue
   499	
   500	        class_type = node.get("class_type", "")
   501	        inputs = node.get("inputs", {})
   502	        if not isinstance(inputs, dict):
   503	            continue
   504	
   505	        # Special: Power Lora Loader (rgthree) — nested lora_N dicts
   506	        if "power lora loader" in class_type.lower():
   507	            hints.extend(_parse_power_lora_loader(inputs, source_image))
   508	            continue
   509	
   510	        node_def = COMFYUI_NODE_REGISTRY.get(class_type)
   511	        if not node_def:
   512	            continue
   513	
   514	        # Check ALL input keys (supports multi-model nodes like DualCLIPLoader)
   515	        for key in node_def.input_keys:
   516	            value = inputs.get(key)
   517	            if value and isinstance(value, str):
   518	                hints.append(PreviewModelHint(
   519	                    filename=_normalize_filename(value),
   520	                    kind=node_def.kind,
   521	                    source_image=source_image,
   522	                    source_type="png_embedded",
   523	                    raw_value=value,
   524	                ))
   525	
   526	    return hints
   527	
   528	
   529	def _parse_power_lora_loader(
   530	    inputs: Dict[str, Any],
   531	    source_image: str,
   532	) -> List[PreviewModelHint]:
   533	    """Parse Power Lora Loader (rgthree) inputs.
   534	
   535	    Structure: lora_1: {on: bool, lora: "path.safetensors", strength: float}
   536	    Only extracts LoRAs that are enabled (on=true).
   537	    """
   538	    hints: List[PreviewModelHint] = []
   539	    for key, value in inputs.items():
   540	        if not key.startswith("lora_") or not isinstance(value, dict):
   541	            continue
   542	        if not value.get("on", False):
   543	            continue
   544	        lora_path = value.get("lora")
   545	        if not lora_path or not isinstance(lora_path, str):
   546	            continue
   547	        weight = value.get("strength")
   548	        if not isinstance(weight, (int, float)):
   549	            weight = None
   550	        else:
   551	            weight = float(weight)
   552	        hints.append(PreviewModelHint(
   553	            filename=_normalize_filename(lora_path),
   554	            kind=AssetKind.LORA,
   555	            source_image=source_image,
   556	            source_type="png_embedded",
   557	            raw_value=lora_path,
   558	            weight=weight,
   559	        ))
   560	    return hints
   561	
   562	
   563	def _normalize_filename(name: str) -> str:
   564	    """Normalize a model name to a filename-like form.
   565	
   566	    Strips path prefixes (e.g., "checkpoints/model.safetensors" → "model.safetensors").
   567	    """
   568	    # Strip path prefixes (ComfyUI often stores "checkpoints/model.safetensors")
   569	    name = name.replace("\\", "/")
   570	    if "/" in name:
   571	        name = name.rsplit("/", 1)[-1]
   572	
   573	    return name
   574	
   575	
   576	def _parse_float(s: str) -> Optional[float]:
   577	    """Safely parse a float string, returning None on failure."""
   578	    try:
   579	        return float(s)
   580	    except (ValueError, TypeError):
   581	        return None
   582	
   583	
   584	def filter_hints_by_kind(
   585	    hints: List[PreviewModelHint],
   586	    kind: AssetKind,
   587	) -> List[PreviewModelHint]:
   588	    """Filter hints to only those matching the target AssetKind.
   589	
   590	    Hints with kind=None are included (unknown kind, could match anything).
   591	    """
   592	    return [h for h in hints if h.kind is None or h.kind == kind]

exec
/bin/bash -lc "git grep -n \"preview_hints_override\\|analyze_previews\" feat/resolve-model-redesign -- src apps/web tests | sed -n '1,200p'" in /home/box/git/github/synapse
 succeeded in 0ms:
feat/resolve-model-redesign:src/store/__init__.py:636:                            preview_hints_override=hints,
feat/resolve-model-redesign:src/store/resolve_models.py:135:    analyze_previews: bool = True
feat/resolve-model-redesign:src/store/resolve_models.py:137:    preview_hints_override: Optional[List[PreviewModelHint]] = None  # External hints (import pipeline)
feat/resolve-model-redesign:src/store/resolve_service.py:202:        if options.preview_hints_override is not None:
feat/resolve-model-redesign:src/store/resolve_service.py:203:            preview_hints = options.preview_hints_override
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:5:- SuggestOptions.preview_hints_override
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:94:# SuggestOptions.preview_hints_override
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:98:    """Test that SuggestOptions accepts preview_hints_override."""
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:102:        assert opts.preview_hints_override is None
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:114:        opts = SuggestOptions(preview_hints_override=hints)
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:115:        assert len(opts.preview_hints_override) == 1
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:116:        assert opts.preview_hints_override[0].filename == "dreamshaper_8.safetensors"
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:119:        opts = SuggestOptions(preview_hints_override=[])
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:120:        assert opts.preview_hints_override == []
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:124:# ResolveService.suggest() uses preview_hints_override
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:131:        """When preview_hints_override is set, it should be used instead of dep._preview_hints."""
feat/resolve-model-redesign:tests/unit/store/test_phase1_import_pipeline.py:168:            preview_hints_override=hints,
feat/resolve-model-redesign:tests/unit/store/test_resolve_models.py:159:        assert opts.analyze_previews is True

exec
/bin/bash -lc "git show feat/resolve-model-redesign:apps/web/e2e/helpers/resolve.helpers.ts | nl -ba | sed -n '240,380p'" in /home/box/git/github/synapse
 succeeded in 0ms:
   240	  },
   241	}
   242	
   243	// ─── Route Setup ────────────────────────────────────────────────────
   244	
   245	/**
   246	 * Setup all API route intercepts for the resolve test pack.
   247	 * Call in beforeEach to mock the backend completely.
   248	 */
   249	export async function setupResolveRoutes(page: Page, overrides?: {
   250	  packDetail?: object
   251	  suggestResult?: object
   252	  applyResult?: object
   253	  previewAnalysis?: object
   254	}) {
   255	  const packDetail = overrides?.packDetail ?? MOCK_PACK_DETAIL
   256	  const suggestResult = overrides?.suggestResult ?? MOCK_SUGGEST_RESULT
   257	  const applyResult = overrides?.applyResult ?? MOCK_APPLY_RESULT
   258	  const previewAnalysis = overrides?.previewAnalysis ?? MOCK_PREVIEW_ANALYSIS
   259	
   260	  // Pack list (sidebar/navigation)
   261	  await page.route('**/api/packs', (route: Route) => {
   262	    if (route.request().method() === 'GET') {
   263	      route.fulfill({
   264	        status: 200,
   265	        contentType: 'application/json',
   266	        body: JSON.stringify([
   267	          { name: MOCK_PACK_NAME, pack_type: 'lora', installed: false, has_unresolved: true },
   268	        ]),
   269	      })
   270	    } else {
   271	      route.continue()
   272	    }
   273	  })
   274	
   275	  // Pack detail
   276	  await page.route(`**/api/packs/${MOCK_PACK_NAME}`, (route: Route) => {
   277	    route.fulfill({
   278	      status: 200,
   279	      contentType: 'application/json',
   280	      body: JSON.stringify(packDetail),
   281	    })
   282	  })
   283	
   284	  // Suggest resolution (pack-level: POST /api/packs/{pack}/suggest-resolution)
   285	  await page.route(`**/api/packs/${MOCK_PACK_NAME}/suggest-resolution`, (route: Route) => {
   286	    route.fulfill({
   287	      status: 200,
   288	      contentType: 'application/json',
   289	      body: JSON.stringify(suggestResult),
   290	    })
   291	  })
   292	
   293	  // Apply resolution (pack-level: POST /api/packs/{pack}/apply-resolution)
   294	  await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route: Route) => {
   295	    route.fulfill({
   296	      status: 200,
   297	      contentType: 'application/json',
   298	      body: JSON.stringify(applyResult),
   299	    })
   300	  })
   301	
   302	  // Preview analysis
   303	  await page.route(`**/api/packs/${MOCK_PACK_NAME}/preview-analysis**`, (route: Route) => {
   304	    route.fulfill({
   305	      status: 200,
   306	      contentType: 'application/json',
   307	      body: JSON.stringify(previewAnalysis),
   308	    })
   309	  })
   310	
   311	  // Avatar status (AI not available by default)
   312	  await page.route('**/api/avatar/status', (route: Route) => {
   313	    route.fulfill({
   314	      status: 200,
   315	      contentType: 'application/json',
   316	      body: JSON.stringify({ state: 'stopped', available: false, enabled: false }),
   317	    })
   318	  })
   319	
   320	  // Downloads (none active)
   321	  await page.route('**/api/store/downloads', (route: Route) => {
   322	    route.fulfill({
   323	      status: 200,
   324	      contentType: 'application/json',
   325	      body: JSON.stringify({ downloads: {} }),
   326	    })
   327	  })
   328	
   329	  // Backup status (not configured)
   330	  const backupResponse = {
   331	    pack: MOCK_PACK_NAME,
   332	    backup_enabled: false,
   333	    backup_connected: false,
   334	    blobs: [],
   335	    summary: { total: 0, local_only: 0, backup_only: 0, both: 0, nowhere: 0, total_bytes: 0 },
   336	  }
   337	  await page.route(`**/api/store/backup/pack-status/${MOCK_PACK_NAME}`, (route: Route) => {
   338	    route.fulfill({
   339	      status: 200,
   340	      contentType: 'application/json',
   341	      body: JSON.stringify(backupResponse),
   342	    })
   343	  })
   344	
   345	  // Preview images — return 1x1 transparent PNG
   346	  await page.route('**/previews/**', (route: Route) => {
   347	    route.fulfill({
   348	      status: 200,
   349	      contentType: 'image/png',
   350	      body: Buffer.from(
   351	        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
   352	        'base64'
   353	      ),
   354	    })
   355	  })
   356	}
   357	
   358	/**
   359	 * Setup local file browsing routes for Local Resolve tab tests.
   360	 */
   361	export async function setupLocalFileRoutes(page: Page) {
   362	  // Browse local directory
   363	  await page.route('**/api/store/browse-local**', (route: Route) => {
   364	    route.fulfill({
   365	      status: 200,
   366	      contentType: 'application/json',
   367	      body: JSON.stringify(MOCK_LOCAL_BROWSE),
   368	    })
   369	  })
   370	
   371	  // Recommend local file
   372	  await page.route(`**/api/packs/${MOCK_PACK_NAME}/recommend-local**`, (route: Route) => {
   373	    route.fulfill({
   374	      status: 200,
   375	      contentType: 'application/json',
   376	      body: JSON.stringify(MOCK_LOCAL_RECOMMEND),
   377	    })
   378	  })
   379	
   380	  // Import local file — returns import ID

codex
I have enough signal now to write the audit. I’m going to put the full markdown in `plans/audit-resolve-model-redesign-local.md` so it can be reviewed as an artifact, and I’ll keep the chat final to the main conclusions and path.
apply patch
patch: completed
/home/box/git/github/synapse/plans/audit-resolve-model-redesign-local.md
diff --git a/plans/audit-resolve-model-redesign-local.md b/plans/audit-resolve-model-redesign-local.md
new file mode 100644
index 0000000000000000000000000000000000000000..4e67f00b330a87af81d1cfa3cea437470b25d9a0
--- /dev/null
+++ b/plans/audit-resolve-model-redesign-local.md
@@ -0,0 +1,359 @@
+# Audit: Resolve Model Redesign, Local Branch State
+
+Branch audited: `feat/resolve-model-redesign` at `5b30b99071070678878088766ec0d73e063b29f2`.
+
+Scope note: audit used only the local branch contents available in this workspace. The user warned the newest commit may exist on another machine and may not be pushed; anything absent here is treated as absent locally.
+
+## Executive Summary
+
+1. The branch is much larger and newer than the stated context: `plans/PLAN-Resolve-Model.md` says `v0.11.0` and claims Phase 0+1+2+2.5+3+4 complete at the top, then later claims Phase 5 and Phase 6 complete too. See `plans/PLAN-Resolve-Model.md:3`, `plans/PLAN-Resolve-Model.md:1018`, `plans/PLAN-Resolve-Model.md:1239`, `plans/PLAN-Resolve-Model.md:1300`.
+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
+3. The implementation is not fully aligned with the main spec. The biggest gaps are: manual Civitai/HF tabs are placeholders, preview hints are not kind-filtered in the resolver chain, canonical source is mostly not populated for remote suggestions, `analyze_previews` is modeled but unused, and apply writes only `pack.json`, not `pack.lock.json`.
+4. Evidence provider coverage is partial. Civitai hash is implemented. HF hash is not a reverse lookup; it only verifies a pre-existing HF selector. Local hash exists through local import/cache, but not as a normal evidence provider in the suggest chain. AI evidence is wired into `ResolveService`, but runs whenever `include_ai=True`, not only after E1-E6 fail to produce Tier 1/2.
+5. Tests are extensive by count, but many important ones are mocked/ceremonial. Backend unit and integration tests cover a lot of mechanics. Frontend E2E is fully mocked. Live AI E2E is a standalone script, not a normal pytest/CI test. NEEDS VERIFICATION: actual latest CI status and whether the "real provider" scripts were run on this local branch state.
+
+## Branch Delta
+
+1. `git diff --stat main..feat/resolve-model-redesign` reports 95 files changed, about 22,233 insertions and 1,355 deletions.
+2. Major new backend files include `src/store/resolve_service.py`, `src/store/resolve_models.py`, `src/store/evidence_providers.py`, `src/store/enrichment.py`, `src/store/local_file_service.py`, `src/store/hash_cache.py`, and `src/avatar/tasks/dependency_resolution.py`.
+3. Major frontend changes replace `BaseModelResolverModal.tsx` with `DependencyResolverModal.tsx`, `LocalResolveTab.tsx`, and `PreviewAnalysisTab.tsx`.
+4. Test expansion is large: unit tests for resolve, evidence, local file service, preview extraction, AI task; integration/smoke tests; Playwright E2E; standalone live AI E2E scripts.
+
+## Spec Version Drift
+
+1. User context names `plans/PLAN-Resolve-Model.md` as v0.7.1, 1769 lines.
+2. Local branch plan is `v0.11.0`, with 2439 added lines in the diff stat and top-level status saying Phase 0+1+2+2.5+3+4 complete. See `plans/PLAN-Resolve-Model.md:3`.
+3. Many implementation files still say "Based on PLAN-Resolve-Model.md v0.7.1" in docstrings. See `src/store/resolve_service.py:5`, `src/store/resolve_models.py:4`, `src/store/evidence_providers.py:4`.
+4. NEEDS VERIFICATION: whether this plan/version mismatch is expected local history or drift from another machine.
+
+## Phase Coverage
+
+### Phase 0: Infrastructure, Model, Calibration
+
+Status: Mostly implemented, with caveats.
+
+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
+3. Tier boundaries, HF eligibility, compatibility rules, AI ceiling, and auto-apply margin exist. See `src/store/resolve_config.py:28`, `src/store/resolve_config.py:35`, `src/store/resolve_config.py:80`, `src/store/resolve_config.py:132`, `src/store/resolve_config.py:173`.
+4. Scoring implements provenance grouping, Noisy-OR, and tier ceiling. See `src/store/resolve_scoring.py:16`, `src/store/resolve_scoring.py:38`, `src/store/resolve_scoring.py:77`.
+5. Hash cache exists with mtime+size invalidation and atomic save. See `src/store/hash_cache.py:36`, `src/store/hash_cache.py:67`, `src/store/hash_cache.py:84`.
+6. Async hash helper exists. See `src/store/hash_cache.py:159`.
+7. Preview extractor exists for sidecar JSON and PNG tEXt chunks. See `src/utils/preview_meta_extractor.py:97`, `src/utils/preview_meta_extractor.py:127`, `src/utils/preview_meta_extractor.py:252`, `src/utils/preview_meta_extractor.py:405`.
+8. Caveat: calibration is not fully implemented. The plan itself says confidence calibration is deferred. See `plans/PLAN-Resolve-Model.md:604`.
+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
+
+### Phase 1: Import Pipeline and Bug Fixes
+
+Status: Implemented mechanically, but behavior is narrower than the spec implies.
+
+1. Store calls `_post_import_resolve(pack)` after Civitai import. See `src/store/__init__.py:592`.
+2. `_post_import_resolve()` extracts preview hints from downloaded previews, calls `resolve_service.suggest()` with `include_ai=False`, and auto-applies Tier 1/2 if margin passes. See `src/store/__init__.py:604`, `src/store/__init__.py:624`, `src/store/__init__.py:632`, `src/store/__init__.py:655`.
+3. It skips dependencies that are not `BASE_MODEL_HINT`, avoiding overwriting pinned deps. See `src/store/__init__.py:626`.
+4. It checks `ApplyResult.success` before logging success. See `src/store/__init__.py:656`, `src/store/__init__.py:660`.
+5. Suggest/apply API endpoints exist, but not at the exact spec path. The plan sketches `/dependencies/{dep_id}/suggest`; code uses pack-level body params: `/api/packs/{pack}/suggest-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+6. `SuggestRequest` has no `analyze_previews` field, even though `SuggestOptions` does. See `src/store/api.py:2247`, `src/store/resolve_models.py:135`.
+7. Caveat: `ResolveService.suggest()` ignores `options.analyze_previews`; it only uses `preview_hints_override` or `dep._preview_hints`. See `src/store/resolve_service.py:201`.
+8. Caveat: import preview hints are passed wholesale to every BASE_MODEL_HINT dep; filtering by dependency kind is not applied at this stage. See `src/store/__init__.py:636` and `src/store/evidence_providers.py:169`.
+
+### Phase 2: AI-Enhanced Resolution and UI
+
+Status: AI backend is wired; UI is partly wired; manual provider tabs are mocked/placeholders.
+
+1. `DependencyResolutionTask` exists, has `needs_mcp=True`, timeout 180s, and loads five skill files. See `src/avatar/tasks/dependency_resolution.py:42`, `src/avatar/tasks/dependency_resolution.py:43`, `src/avatar/tasks/dependency_resolution.py:50`.
+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
+3. `AIEvidenceProvider` builds structured text and calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:518`, `src/store/evidence_providers.py:525`.
+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+5. AI ceiling is enforced in both task parsing and evidence conversion. See `src/avatar/tasks/dependency_resolution.py:89`, `src/store/evidence_providers.py:844`.
+6. `ResolveService` registers AI provider. See `src/store/resolve_service.py:166`.
+7. `ResolveService.suggest()` skips AI unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+9. UI modal exists with Candidates, Preview, Local, AI, Civitai, and HF tabs. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:61`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:346`.
+10. AI tab is gated by `avatarAvailable`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:350`, `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+11. HF tab is gated by frontend `HF_ELIGIBLE_KINDS`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+12. Civitai manual tab is a placeholder: "Manual Civitai search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+13. HuggingFace manual tab is a placeholder: "Manual HuggingFace search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+14. This contradicts the plan's Phase 4 complete claim for provider polish/manual payloads from the UI. Backend manual apply exists; frontend manual search does not.
+
+### Phase 2.5: Preview Enrichment
+
+Status: Partially implemented.
+
+1. `PreviewMetaEvidenceProvider` enriches hints via Civitai hash lookup, then Civitai name search. See `src/store/evidence_providers.py:143`, `src/store/evidence_providers.py:177`, `src/store/evidence_providers.py:246`, `src/store/evidence_providers.py:252`.
+2. It uses `pack_service_getter` and is wired with PackService in `ResolveService._ensure_providers()`. See `src/store/evidence_providers.py:154`, `src/store/resolve_service.py:162`.
+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
+5. Gap: no kind filtering in `PreviewMetaEvidenceProvider.gather()`. It iterates all hints and does not check `hint.kind` against `ctx.kind`. See `src/store/evidence_providers.py:169`.
+6. The extractor has `filter_hints_by_kind()`, but `git grep` shows no production use. See `src/utils/preview_meta_extractor.py:584`.
+7. This is a direct spec gap: plan requires kind-aware filtering. See `plans/PLAN-Resolve-Model.md:167`.
+
+### Phase 3: Local Resolve
+
+Status: Implemented and UI-integrated.
+
+1. Backend local browse, recommendation, and import service exists. See `src/store/local_file_service.py:191`, `src/store/local_file_service.py:207`, `src/store/local_file_service.py:268`, `src/store/local_file_service.py:344`.
+2. Path validation requires absolute path, no `..`, resolved path exists, extension allowlist, regular file. See `src/store/local_file_service.py:111`.
+3. Local import hashes, copies into blob store, enriches, and applies resolution. See `src/store/local_file_service.py:377`, `src/store/local_file_service.py:390`, `src/store/local_file_service.py:414`, `src/store/local_file_service.py:428`.
+4. API endpoints exist: browse-local, recommend-local, import-local with background executor and polling. See `src/store/api.py:2485`, `src/store/api.py:2502`, `src/store/api.py:2546`.
+5. UI tab exists and calls recommend/import/poll endpoints. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:150`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+6. Caveat: local import applies via `resolve_service.apply_manual()` if reachable, otherwise falls back to `pack_service.apply_dependency_resolution()`. See `src/store/local_file_service.py:544`.
+7. Caveat: fallback path bypasses validation if `resolve_service` is not available. See `src/store/local_file_service.py:554`.
+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
+
+### Phase 4: Provider Polish, Download, Cleanup
+
+Status: Cleanup and validation mostly implemented; manual provider UI and lock/write behavior remain incomplete.
+
+1. Deprecated `BaseModelResolverModal.tsx` is deleted according to diff stat.
+2. `/resolve-base-model` appears removed; current resolve endpoints are `suggest-resolution`, `apply-resolution`, and `apply-manual-resolution`. See `src/store/api.py:2302`, `src/store/api.py:2342`, `src/store/api.py:2370`.
+3. API boundary validates manual strategy fields. See `src/store/api.py:2383`.
+4. `Apply & Download` UI does a compound apply then `/download-asset`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401`, `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:437`.
+5. NEEDS VERIFICATION: `download-asset` expects `asset_name`; UI sends `depId`. This may be correct if asset name equals dependency id, but the audit did not verify all pack shapes. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:442`.
+6. Major gap: Civitai and HF manual tabs are not implemented. They cannot produce typed payloads from UI. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+7. Major gap: `PackService.apply_dependency_resolution()` explicitly does not touch `pack.lock.json`, contrary to earlier spec language that apply updates pack.json and pack.lock atomically. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+8. `lock_entry` is accepted but unused. See `src/store/pack_service.py:1223`, `src/store/pack_service.py:1237`.
+
+### Phase 5: Deferred Polish
+
+Status: Mostly implemented, but not all to full spec strength.
+
+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
+2. `AUTO_APPLY_MARGIN` is centralized and config-readable. See `src/store/resolve_config.py:132`, `src/store/resolve_config.py:138`, `src/store/__init__.py:648`.
+3. `compute_sha256_async()` exists. See `src/store/hash_cache.py:159`.
+4. HF enrichment exists as `enrich_by_hf()` and is used in `enrich_file()`. See `src/store/enrichment.py:166`, `src/store/enrichment.py:294`.
+5. HuggingFace client parses LFS `lfs.oid` into SHA256. See `src/clients/huggingface_client.py:36`.
+6. HuggingFace client has `search_models()`. See `src/clients/huggingface_client.py:120`.
+7. Caveat: `LocalFileService._get_hf_client()` looks for `pack_service.hf_client`, but other code references `pack_service.huggingface` for HF access in the plan and evidence provider uses `pack_service.huggingface`. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`. NEEDS VERIFICATION: actual PackService attribute name.
+8. Caveat: MCP `search_huggingface` returns formatted text, not JSON. The plan says text may be OK for LLM, but "structured output" remains unresolved in code. See `plans/PLAN-Resolve-Model.md:1271`, `src/avatar/mcp/store_server.py:1229`.
+9. Caveat: MCP HF search only fetches top-level `tree/main`, not recursive subfolders or model cards. See `src/avatar/mcp/store_server.py:1306`.
+
+### Phase 6: Config, Aliases, Tests, AI Gate
+
+Status: Implemented mechanically, but alias defaults and test realism are weak.
+
+1. `ResolveConfig` exists under `StoreConfig.resolve`. See `src/store/models.py:243`, `src/store/models.py:257`.
+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
+3. `AIEvidenceProvider.supports()` checks config flag and avatar object. See `src/store/evidence_providers.py:510`.
+4. Alias provider reads `layout.load_config().base_model_aliases`. See `src/store/evidence_providers.py:692`.
+5. Alias provider supports Civitai and HF targets. See `src/store/evidence_providers.py:713`, `src/store/evidence_providers.py:741`.
+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
+7. Caveat: AI gate checks avatar object presence backend-side, not a status `available` field. It assumes a non-None avatar service is usable. See `src/store/evidence_providers.py:516`.
+
+## Evidence Providers
+
+### Civitai Hash Evidence
+
+Status: Implemented and wired.
+
+1. `HashEvidenceProvider` reads SHA256 from `dep.lock.sha256`. See `src/store/evidence_providers.py:75`.
+2. It calls `pack_service.civitai.get_model_by_hash(sha256)`. See `src/store/evidence_providers.py:88`.
+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
+4. It assigns `hash_match` evidence with confidence 0.95. See `src/store/evidence_providers.py:120`.
+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
+6. Gap: it only reads hash from `dep.lock`; it does not hash local files as part of suggest. See `src/store/evidence_providers.py:75`.
+
+### HuggingFace LFS OID Evidence
+
+Status: Partial verification only, not discovery/reverse lookup.
+
+1. HF LFS OID parsing exists in `HFFileInfo.from_api_response()`. See `src/clients/huggingface_client.py:36`.
+2. `HashEvidenceProvider` calls `_hf_hash_lookup()` only when kind config says `hf_hash_lookup=True`. See `src/store/evidence_providers.py:133`.
+3. Only checkpoints have `hf_hash_lookup=True`; VAE/controlnet are HF-eligible but hash lookup false. See `src/store/resolve_config.py:80`, `src/store/resolve_config.py:93`, `src/store/resolve_config.py:99`.
+4. `_hf_hash_lookup()` requires dependency selector already has HF repo and filename. See `src/store/evidence_providers.py:624`, `src/store/evidence_providers.py:629`.
+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
+6. `find_model_by_hash` MCP tool is Civitai-only. See `src/avatar/mcp/store_server.py:1143`.
+
+### Local Hash Evidence
+
+Status: Implemented in local import flow, not in resolver evidence chain.
+
+1. `HashCache` can cache SHA256 by file path. See `src/store/hash_cache.py:36`.
+2. `LocalFileService.recommend()` can compare cached hash with dependency expected hash. See `src/store/local_file_service.py:306`.
+3. `LocalFileService.import_file()` hashes selected file and uses hash cache. See `src/store/local_file_service.py:377`.
+4. `enrich_file()` then tries Civitai hash, Civitai name, HF name, filename fallback. See `src/store/enrichment.py:271`.
+5. There is no `LocalHashEvidenceProvider` in `ResolveService._ensure_providers()`. See `src/store/resolve_service.py:160`.
+6. So local hash is an import/local-tab feature, not part of normal `suggest_resolution()`.
+
+### AI Evidence
+
+Status: Wired, but broad and prompt-dependent.
+
+1. `AIEvidenceProvider` is registered in the provider chain. See `src/store/resolve_service.py:166`.
+2. It is skipped unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+3. It builds a text input with pack name/type/base_model/description/tags, dependency kind/hint/expose filename, and preview hints. See `src/store/evidence_providers.py:774`.
+4. It calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:526`.
+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+6. Fallback when AI is off: provider is skipped; E1-E6 still run. See `src/store/evidence_providers.py:510`, `src/store/resolve_service.py:226`.
+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
+
+## UI Integration
+
+### DependencyResolverModal
+
+Status: Integrated as the primary modal.
+
+1. `PackDetailPage` keeps resolver state and opens modal per asset. See `apps/web/src/components/modules/PackDetailPage.tsx:126`, `apps/web/src/components/modules/PackDetailPage.tsx:132`.
+2. Opening the modal eagerly calls `suggestResolution()` without AI. See `apps/web/src/components/modules/PackDetailPage.tsx:141`.
+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
+4. Candidate cards show confidence label, provider, base model, compatibility warning, evidence groups, and raw score when expanded. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:193`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:235`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:279`.
+5. Apply and Apply & Download buttons are wired. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:616`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:631`.
+
+### Civitai Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:351`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+
+### HuggingFace Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible only for frontend HF-eligible kinds. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+
+### Local Resolve Tab
+
+Status: Functional.
+
+1. It browses/recommends a directory using `/recommend-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:160`.
+2. It imports a selected file using `/import-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`.
+3. It polls `/api/store/imports/{import_id}`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+4. It displays browse/importing/success/error states. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:297`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:368`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:441`.
+
+### Apply
+
+Status: Wired, but cache binding is incomplete.
+
+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
+4. UUID collision risk is low, but missing pack/dep binding is a correctness gap already noted in the plan as deferred. See `plans/PLAN-Resolve-Model.md:888`.
+
+### AI Gate
+
+Status: Implemented frontend and backend, with different semantics.
+
+1. Frontend hides AI tab unless avatar status has `available=true`. See `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+2. Backend hides AI provider when config `resolve.enable_ai=false` or avatar getter returns None. See `src/store/evidence_providers.py:510`.
+3. Backend does not check avatar runtime status `available`; it assumes non-None service can run. NEEDS VERIFICATION.
+
+## Preview Analysis
+
+Status: UI tab and backend extractor are wired; it is partly display-only.
+
+1. Backend endpoint `/preview-analysis` analyzes preview sidecars and PNG text. See `src/store/api.py:2275`.
+2. Frontend hook fetches `/api/packs/{pack}/preview-analysis`. See `apps/web/src/components/modules/pack-detail/hooks/usePreviewAnalysis.ts:10`.
+3. Preview tab displays thumbnails, model references, hashes, weights, and generation params. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:64`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:116`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:182`.
+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
+7. In backend suggest, preview hints are only available if `_post_import_resolve()` passes overrides or if a dependency has `_preview_hints`. See `src/store/resolve_service.py:201`.
+8. The public suggest endpoint does not itself run preview analysis or pass preview hints. See `src/store/api.py:2302`, `src/store/api.py:2322`.
+9. The tab fetches preview analysis separately, but those hints are not fed back into `onSuggest()`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:507`.
+
+## AI Integration
+
+Status: Real task and service wiring exist; live provider claims need verification.
+
+1. `DependencyResolutionTask` is registered in default registry per plan; registry change present in diff stat, not deeply audited here. NEEDS VERIFICATION on exact registry line.
+2. Task prompt is skill-file based; `build_system_prompt()` returns skill content only. See `src/avatar/tasks/dependency_resolution.py:53`.
+3. Task parses and validates AI output with provider-specific required fields. See `src/avatar/tasks/dependency_resolution.py:63`, `src/avatar/tasks/dependency_resolution.py:127`.
+4. Task has no fallback; E1-E6 are expected to provide non-AI coverage. See `src/avatar/tasks/dependency_resolution.py:164`.
+5. `AvatarTaskService` starts `AvatarEngine` with MCP servers for `needs_mcp` tasks. See `src/avatar/task_service.py:336`.
+6. MCP includes `search_civitai`, `analyze_civitai_model`, `find_model_by_hash`, `suggest_asset_sources`, and `search_huggingface`. See `src/avatar/mcp/store_server.py:1428`, `src/avatar/mcp/store_server.py:1434`, `src/avatar/mcp/store_server.py:1486`, `src/avatar/mcp/store_server.py:1492`, `src/avatar/mcp/store_server.py:1498`.
+7. `find_model_by_hash` is Civitai-only despite AI prompt comments mentioning HF/hash capability. See `src/avatar/mcp/store_server.py:1143`.
+8. `search_huggingface` performs real HTTP through `requests`, not through the shared HF client/session/token. See `src/avatar/mcp/store_server.py:1239`.
+9. NEEDS VERIFICATION: whether avatar-engine permissions and MCP server config are actually present in local runtime config, not just `config/avatar.yaml.example`.
+
+## Tests
+
+### Unit Tests
+
+Status: Broad coverage, often mocked.
+
+1. Unit tests exist for models, config, validation, scoring, hash cache, providers, resolve service, preview extractor, local file service, enrichment, and AI task per diff stat.
+2. `tests/unit/store/test_evidence_providers.py` heavily uses `MagicMock`. See grep output: many `MagicMock` references, e.g. `tests/unit/store/test_evidence_providers.py:32`.
+3. This is fine for unit mechanics but does not prove real Civitai/HF data shape compatibility.
+4. Some tests do use Pydantic models in other files per plan, but the most provider-critical unit file is mock-heavy. NEEDS VERIFICATION against real clients.
+
+### Integration Tests
+
+Status: Present but partly fake.
+
+1. `test_resolve_integration.py` uses real `ResolveService` but mock PackService/Layout and fake providers. See `tests/integration/test_resolve_integration.py:1`, `tests/integration/test_resolve_integration.py:61`, `tests/integration/test_resolve_integration.py:77`.
+2. `test_resolve_smoke.py` creates a real `Store(tmp_path)` but still uses MagicMock packs/deps for several scenarios. See `tests/integration/test_resolve_smoke.py:20`, `tests/integration/test_resolve_smoke.py:37`.
+3. AI integration file claims real components but uses `MagicMock` for packs/deps and avatar. See `tests/integration/test_ai_resolve_integration.py:42`, grep lines.
+4. These tests validate orchestration, not full end-to-end provider correctness.
+
+### Smoke Tests
+
+Status: Present, low-to-medium realism.
+
+1. Store smoke checks service wiring and migration behavior. See `tests/integration/test_resolve_smoke.py:104`.
+2. It does not perform a real Civitai import with actual downloaded sidecars in normal CI. NEEDS VERIFICATION.
+
+### E2E Tests
+
+Status: Two categories: mocked Playwright and standalone live scripts.
+
+1. Playwright resolve E2E is explicitly offline and mocked. See `apps/web/e2e/resolve-dependency.spec.ts:1`.
+2. Helpers "mock the backend completely." See `apps/web/e2e/helpers/resolve.helpers.ts:245`.
+3. These tests cover UI flows but not backend resolver correctness.
+4. `tests/e2e_resolve_real.py` is a standalone script for live providers, not a pytest test by default. See `tests/e2e_resolve_real.py:10`, `tests/e2e_resolve_real.py:331`.
+5. It exits 0 if there are no provider errors, even if correctness failures occur; `sys.exit(0 if err_count == 0 else 1)` ignores `fail_count`. See `tests/e2e_resolve_real.py:412`.
+6. That makes it unsuitable as a hard correctness gate without modification.
+
+## Spec vs Code Gaps
+
+1. API shape mismatch: spec says `/dependencies/{dep_id}/suggest` and `/dependencies/{dep_id}/apply`; code uses pack-level `/suggest-resolution`, `/apply-resolution`, `/apply-manual-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+2. `analyze_previews` option is defined but not exposed in API or used in service. See `src/store/resolve_models.py:135`, `src/store/api.py:2247`, `src/store/resolve_service.py:201`.
+3. Preview provider does not filter hints by target kind. See `plans/PLAN-Resolve-Model.md:167`, `src/store/evidence_providers.py:169`.
+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. Manual Civitai and HF search tabs are placeholders. See `plans/PLAN-Resolve-Model.md:459`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+7. Candidate cache lacks pack/dep binding. See `plans/PLAN-Resolve-Model.md:888`, `src/store/resolve_service.py:75`.
+8. Apply does not update `pack.lock.json`; PackService says it intentionally does not touch lock. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
+10. HF search tool is not full tree/model-card inspection and not structured JSON. See `plans/PLAN-Resolve-Model.md:803`, `src/avatar/mcp/store_server.py:1229`.
+11. HF hash lookup is verification of an existing selector, not general HF reverse lookup. See `src/store/evidence_providers.py:618`.
+12. `HashEvidenceProvider.supports()` returns true for everything and only no-ops later; eligibility is not expressed at support level. See `src/store/evidence_providers.py:63`.
+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
+14. Default alias config also uses placeholder zero IDs. See `src/store/models.py:281`.
+
+## Refactor Candidates
+
+1. Consolidate Civitai name/hash enrichment. `PreviewMetaEvidenceProvider` duplicates logic that now exists in `src/store/enrichment.py`. See `src/store/evidence_providers.py:230`, `src/store/enrichment.py:42`.
+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
+4. Split AI provider orchestration into two passes: deterministic E1-E6 first, optional AI only if needed. See `src/store/resolve_service.py:216`.
+5. Add kind filtering at resolver input boundary, not only extractor helper. See `src/utils/preview_meta_extractor.py:584`.
+6. Create a shared HF search client/path for MCP, enrichment, and evidence rather than direct `requests` in MCP plus `HuggingFaceClient` elsewhere. See `src/avatar/mcp/store_server.py:1239`, `src/clients/huggingface_client.py:120`.
+7. Decide whether apply should write lock data. Current PackService doc contradicts the earlier spec. See `src/store/pack_service.py:1228`.
+8. Extract frontend provider manual search tabs into real components or remove placeholder tabs until implemented.
+9. Clarify `pack_service.hf_client` vs `pack_service.huggingface` naming. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`.
+10. Turn standalone live E2E scripts into pytest tests with explicit opt-in markers and fail on incorrect top match, not only provider errors. See `tests/e2e_resolve_real.py:412`.
+
+## Open Questions for Owner
+
+1. Is the local `v0.11.0` plan the source of truth, or should the audit compare against an older v0.7.1 from the missing machine?
+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
+3. Should Civitai/HF manual tabs be implemented before Release 1, point 1, or are placeholders acceptable?
+4. Should preview analysis hints feed back into `suggestResolution()` from the UI, or is preview analysis only informational after import?
+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
+6. What is the authoritative HF client attribute on PackService: `hf_client` or `huggingface`?
+7. Should AI run alongside deterministic providers when requested, or only after deterministic providers fail to produce Tier 1/2?
+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
+9. Is HF reverse hash lookup explicitly out of scope due to HF API limitations, with only known-repo LFS verification required?
+10. Which test command is the release gate: full pytest, Playwright E2E, live AI scripts, or a curated subset?
+11. Are live provider results from `tests/e2e_resolve_real.py` stored anywhere reproducible, or only printed to terminal?
+12. Should local import fallback bypass validation if `resolve_service` is unavailable, or should that path hard-fail?
+
+## Release Risk Assessment
+
+1. Backend core is real enough for continued integration work.
+2. The UX is not feature-complete for manual Civitai/HF resolution despite tab presence.
+3. Preview analysis is useful, but not fully integrated as a first-class resolve source in the UI.
+4. AI integration is plausible, but relies on runtime avatar/MCP configuration and prompt behavior; local code alone does not prove live reliability.
+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
+6. The largest spec compliance risk is that "Suggest / Apply is the single write path updating pack + lock" is not what PackService currently does.

diff --git a/plans/audit-resolve-model-redesign-local.md b/plans/audit-resolve-model-redesign-local.md
new file mode 100644
index 0000000000000000000000000000000000000000..4e67f00b330a87af81d1cfa3cea437470b25d9a0
--- /dev/null
+++ b/plans/audit-resolve-model-redesign-local.md
@@ -0,0 +1,359 @@
+# Audit: Resolve Model Redesign, Local Branch State
+
+Branch audited: `feat/resolve-model-redesign` at `5b30b99071070678878088766ec0d73e063b29f2`.
+
+Scope note: audit used only the local branch contents available in this workspace. The user warned the newest commit may exist on another machine and may not be pushed; anything absent here is treated as absent locally.
+
+## Executive Summary
+
+1. The branch is much larger and newer than the stated context: `plans/PLAN-Resolve-Model.md` says `v0.11.0` and claims Phase 0+1+2+2.5+3+4 complete at the top, then later claims Phase 5 and Phase 6 complete too. See `plans/PLAN-Resolve-Model.md:3`, `plans/PLAN-Resolve-Model.md:1018`, `plans/PLAN-Resolve-Model.md:1239`, `plans/PLAN-Resolve-Model.md:1300`.
+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
+3. The implementation is not fully aligned with the main spec. The biggest gaps are: manual Civitai/HF tabs are placeholders, preview hints are not kind-filtered in the resolver chain, canonical source is mostly not populated for remote suggestions, `analyze_previews` is modeled but unused, and apply writes only `pack.json`, not `pack.lock.json`.
+4. Evidence provider coverage is partial. Civitai hash is implemented. HF hash is not a reverse lookup; it only verifies a pre-existing HF selector. Local hash exists through local import/cache, but not as a normal evidence provider in the suggest chain. AI evidence is wired into `ResolveService`, but runs whenever `include_ai=True`, not only after E1-E6 fail to produce Tier 1/2.
+5. Tests are extensive by count, but many important ones are mocked/ceremonial. Backend unit and integration tests cover a lot of mechanics. Frontend E2E is fully mocked. Live AI E2E is a standalone script, not a normal pytest/CI test. NEEDS VERIFICATION: actual latest CI status and whether the "real provider" scripts were run on this local branch state.
+
+## Branch Delta
+
+1. `git diff --stat main..feat/resolve-model-redesign` reports 95 files changed, about 22,233 insertions and 1,355 deletions.
+2. Major new backend files include `src/store/resolve_service.py`, `src/store/resolve_models.py`, `src/store/evidence_providers.py`, `src/store/enrichment.py`, `src/store/local_file_service.py`, `src/store/hash_cache.py`, and `src/avatar/tasks/dependency_resolution.py`.
+3. Major frontend changes replace `BaseModelResolverModal.tsx` with `DependencyResolverModal.tsx`, `LocalResolveTab.tsx`, and `PreviewAnalysisTab.tsx`.
+4. Test expansion is large: unit tests for resolve, evidence, local file service, preview extraction, AI task; integration/smoke tests; Playwright E2E; standalone live AI E2E scripts.
+
+## Spec Version Drift
+
+1. User context names `plans/PLAN-Resolve-Model.md` as v0.7.1, 1769 lines.
+2. Local branch plan is `v0.11.0`, with 2439 added lines in the diff stat and top-level status saying Phase 0+1+2+2.5+3+4 complete. See `plans/PLAN-Resolve-Model.md:3`.
+3. Many implementation files still say "Based on PLAN-Resolve-Model.md v0.7.1" in docstrings. See `src/store/resolve_service.py:5`, `src/store/resolve_models.py:4`, `src/store/evidence_providers.py:4`.
+4. NEEDS VERIFICATION: whether this plan/version mismatch is expected local history or drift from another machine.
+
+## Phase Coverage
+
+### Phase 0: Infrastructure, Model, Calibration
+
+Status: Mostly implemented, with caveats.
+
+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
+3. Tier boundaries, HF eligibility, compatibility rules, AI ceiling, and auto-apply margin exist. See `src/store/resolve_config.py:28`, `src/store/resolve_config.py:35`, `src/store/resolve_config.py:80`, `src/store/resolve_config.py:132`, `src/store/resolve_config.py:173`.
+4. Scoring implements provenance grouping, Noisy-OR, and tier ceiling. See `src/store/resolve_scoring.py:16`, `src/store/resolve_scoring.py:38`, `src/store/resolve_scoring.py:77`.
+5. Hash cache exists with mtime+size invalidation and atomic save. See `src/store/hash_cache.py:36`, `src/store/hash_cache.py:67`, `src/store/hash_cache.py:84`.
+6. Async hash helper exists. See `src/store/hash_cache.py:159`.
+7. Preview extractor exists for sidecar JSON and PNG tEXt chunks. See `src/utils/preview_meta_extractor.py:97`, `src/utils/preview_meta_extractor.py:127`, `src/utils/preview_meta_extractor.py:252`, `src/utils/preview_meta_extractor.py:405`.
+8. Caveat: calibration is not fully implemented. The plan itself says confidence calibration is deferred. See `plans/PLAN-Resolve-Model.md:604`.
+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
+
+### Phase 1: Import Pipeline and Bug Fixes
+
+Status: Implemented mechanically, but behavior is narrower than the spec implies.
+
+1. Store calls `_post_import_resolve(pack)` after Civitai import. See `src/store/__init__.py:592`.
+2. `_post_import_resolve()` extracts preview hints from downloaded previews, calls `resolve_service.suggest()` with `include_ai=False`, and auto-applies Tier 1/2 if margin passes. See `src/store/__init__.py:604`, `src/store/__init__.py:624`, `src/store/__init__.py:632`, `src/store/__init__.py:655`.
+3. It skips dependencies that are not `BASE_MODEL_HINT`, avoiding overwriting pinned deps. See `src/store/__init__.py:626`.
+4. It checks `ApplyResult.success` before logging success. See `src/store/__init__.py:656`, `src/store/__init__.py:660`.
+5. Suggest/apply API endpoints exist, but not at the exact spec path. The plan sketches `/dependencies/{dep_id}/suggest`; code uses pack-level body params: `/api/packs/{pack}/suggest-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+6. `SuggestRequest` has no `analyze_previews` field, even though `SuggestOptions` does. See `src/store/api.py:2247`, `src/store/resolve_models.py:135`.
+7. Caveat: `ResolveService.suggest()` ignores `options.analyze_previews`; it only uses `preview_hints_override` or `dep._preview_hints`. See `src/store/resolve_service.py:201`.
+8. Caveat: import preview hints are passed wholesale to every BASE_MODEL_HINT dep; filtering by dependency kind is not applied at this stage. See `src/store/__init__.py:636` and `src/store/evidence_providers.py:169`.
+
+### Phase 2: AI-Enhanced Resolution and UI
+
+Status: AI backend is wired; UI is partly wired; manual provider tabs are mocked/placeholders.
+
+1. `DependencyResolutionTask` exists, has `needs_mcp=True`, timeout 180s, and loads five skill files. See `src/avatar/tasks/dependency_resolution.py:42`, `src/avatar/tasks/dependency_resolution.py:43`, `src/avatar/tasks/dependency_resolution.py:50`.
+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
+3. `AIEvidenceProvider` builds structured text and calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:518`, `src/store/evidence_providers.py:525`.
+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+5. AI ceiling is enforced in both task parsing and evidence conversion. See `src/avatar/tasks/dependency_resolution.py:89`, `src/store/evidence_providers.py:844`.
+6. `ResolveService` registers AI provider. See `src/store/resolve_service.py:166`.
+7. `ResolveService.suggest()` skips AI unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+9. UI modal exists with Candidates, Preview, Local, AI, Civitai, and HF tabs. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:61`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:346`.
+10. AI tab is gated by `avatarAvailable`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:350`, `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+11. HF tab is gated by frontend `HF_ELIGIBLE_KINDS`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+12. Civitai manual tab is a placeholder: "Manual Civitai search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+13. HuggingFace manual tab is a placeholder: "Manual HuggingFace search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+14. This contradicts the plan's Phase 4 complete claim for provider polish/manual payloads from the UI. Backend manual apply exists; frontend manual search does not.
+
+### Phase 2.5: Preview Enrichment
+
+Status: Partially implemented.
+
+1. `PreviewMetaEvidenceProvider` enriches hints via Civitai hash lookup, then Civitai name search. See `src/store/evidence_providers.py:143`, `src/store/evidence_providers.py:177`, `src/store/evidence_providers.py:246`, `src/store/evidence_providers.py:252`.
+2. It uses `pack_service_getter` and is wired with PackService in `ResolveService._ensure_providers()`. See `src/store/evidence_providers.py:154`, `src/store/resolve_service.py:162`.
+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
+5. Gap: no kind filtering in `PreviewMetaEvidenceProvider.gather()`. It iterates all hints and does not check `hint.kind` against `ctx.kind`. See `src/store/evidence_providers.py:169`.
+6. The extractor has `filter_hints_by_kind()`, but `git grep` shows no production use. See `src/utils/preview_meta_extractor.py:584`.
+7. This is a direct spec gap: plan requires kind-aware filtering. See `plans/PLAN-Resolve-Model.md:167`.
+
+### Phase 3: Local Resolve
+
+Status: Implemented and UI-integrated.
+
+1. Backend local browse, recommendation, and import service exists. See `src/store/local_file_service.py:191`, `src/store/local_file_service.py:207`, `src/store/local_file_service.py:268`, `src/store/local_file_service.py:344`.
+2. Path validation requires absolute path, no `..`, resolved path exists, extension allowlist, regular file. See `src/store/local_file_service.py:111`.
+3. Local import hashes, copies into blob store, enriches, and applies resolution. See `src/store/local_file_service.py:377`, `src/store/local_file_service.py:390`, `src/store/local_file_service.py:414`, `src/store/local_file_service.py:428`.
+4. API endpoints exist: browse-local, recommend-local, import-local with background executor and polling. See `src/store/api.py:2485`, `src/store/api.py:2502`, `src/store/api.py:2546`.
+5. UI tab exists and calls recommend/import/poll endpoints. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:150`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+6. Caveat: local import applies via `resolve_service.apply_manual()` if reachable, otherwise falls back to `pack_service.apply_dependency_resolution()`. See `src/store/local_file_service.py:544`.
+7. Caveat: fallback path bypasses validation if `resolve_service` is not available. See `src/store/local_file_service.py:554`.
+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
+
+### Phase 4: Provider Polish, Download, Cleanup
+
+Status: Cleanup and validation mostly implemented; manual provider UI and lock/write behavior remain incomplete.
+
+1. Deprecated `BaseModelResolverModal.tsx` is deleted according to diff stat.
+2. `/resolve-base-model` appears removed; current resolve endpoints are `suggest-resolution`, `apply-resolution`, and `apply-manual-resolution`. See `src/store/api.py:2302`, `src/store/api.py:2342`, `src/store/api.py:2370`.
+3. API boundary validates manual strategy fields. See `src/store/api.py:2383`.
+4. `Apply & Download` UI does a compound apply then `/download-asset`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401`, `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:437`.
+5. NEEDS VERIFICATION: `download-asset` expects `asset_name`; UI sends `depId`. This may be correct if asset name equals dependency id, but the audit did not verify all pack shapes. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:442`.
+6. Major gap: Civitai and HF manual tabs are not implemented. They cannot produce typed payloads from UI. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+7. Major gap: `PackService.apply_dependency_resolution()` explicitly does not touch `pack.lock.json`, contrary to earlier spec language that apply updates pack.json and pack.lock atomically. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+8. `lock_entry` is accepted but unused. See `src/store/pack_service.py:1223`, `src/store/pack_service.py:1237`.
+
+### Phase 5: Deferred Polish
+
+Status: Mostly implemented, but not all to full spec strength.
+
+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
+2. `AUTO_APPLY_MARGIN` is centralized and config-readable. See `src/store/resolve_config.py:132`, `src/store/resolve_config.py:138`, `src/store/__init__.py:648`.
+3. `compute_sha256_async()` exists. See `src/store/hash_cache.py:159`.
+4. HF enrichment exists as `enrich_by_hf()` and is used in `enrich_file()`. See `src/store/enrichment.py:166`, `src/store/enrichment.py:294`.
+5. HuggingFace client parses LFS `lfs.oid` into SHA256. See `src/clients/huggingface_client.py:36`.
+6. HuggingFace client has `search_models()`. See `src/clients/huggingface_client.py:120`.
+7. Caveat: `LocalFileService._get_hf_client()` looks for `pack_service.hf_client`, but other code references `pack_service.huggingface` for HF access in the plan and evidence provider uses `pack_service.huggingface`. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`. NEEDS VERIFICATION: actual PackService attribute name.
+8. Caveat: MCP `search_huggingface` returns formatted text, not JSON. The plan says text may be OK for LLM, but "structured output" remains unresolved in code. See `plans/PLAN-Resolve-Model.md:1271`, `src/avatar/mcp/store_server.py:1229`.
+9. Caveat: MCP HF search only fetches top-level `tree/main`, not recursive subfolders or model cards. See `src/avatar/mcp/store_server.py:1306`.
+
+### Phase 6: Config, Aliases, Tests, AI Gate
+
+Status: Implemented mechanically, but alias defaults and test realism are weak.
+
+1. `ResolveConfig` exists under `StoreConfig.resolve`. See `src/store/models.py:243`, `src/store/models.py:257`.
+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
+3. `AIEvidenceProvider.supports()` checks config flag and avatar object. See `src/store/evidence_providers.py:510`.
+4. Alias provider reads `layout.load_config().base_model_aliases`. See `src/store/evidence_providers.py:692`.
+5. Alias provider supports Civitai and HF targets. See `src/store/evidence_providers.py:713`, `src/store/evidence_providers.py:741`.
+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
+7. Caveat: AI gate checks avatar object presence backend-side, not a status `available` field. It assumes a non-None avatar service is usable. See `src/store/evidence_providers.py:516`.
+
+## Evidence Providers
+
+### Civitai Hash Evidence
+
+Status: Implemented and wired.
+
+1. `HashEvidenceProvider` reads SHA256 from `dep.lock.sha256`. See `src/store/evidence_providers.py:75`.
+2. It calls `pack_service.civitai.get_model_by_hash(sha256)`. See `src/store/evidence_providers.py:88`.
+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
+4. It assigns `hash_match` evidence with confidence 0.95. See `src/store/evidence_providers.py:120`.
+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
+6. Gap: it only reads hash from `dep.lock`; it does not hash local files as part of suggest. See `src/store/evidence_providers.py:75`.
+
+### HuggingFace LFS OID Evidence
+
+Status: Partial verification only, not discovery/reverse lookup.
+
+1. HF LFS OID parsing exists in `HFFileInfo.from_api_response()`. See `src/clients/huggingface_client.py:36`.
+2. `HashEvidenceProvider` calls `_hf_hash_lookup()` only when kind config says `hf_hash_lookup=True`. See `src/store/evidence_providers.py:133`.
+3. Only checkpoints have `hf_hash_lookup=True`; VAE/controlnet are HF-eligible but hash lookup false. See `src/store/resolve_config.py:80`, `src/store/resolve_config.py:93`, `src/store/resolve_config.py:99`.
+4. `_hf_hash_lookup()` requires dependency selector already has HF repo and filename. See `src/store/evidence_providers.py:624`, `src/store/evidence_providers.py:629`.
+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
+6. `find_model_by_hash` MCP tool is Civitai-only. See `src/avatar/mcp/store_server.py:1143`.
+
+### Local Hash Evidence
+
+Status: Implemented in local import flow, not in resolver evidence chain.
+
+1. `HashCache` can cache SHA256 by file path. See `src/store/hash_cache.py:36`.
+2. `LocalFileService.recommend()` can compare cached hash with dependency expected hash. See `src/store/local_file_service.py:306`.
+3. `LocalFileService.import_file()` hashes selected file and uses hash cache. See `src/store/local_file_service.py:377`.
+4. `enrich_file()` then tries Civitai hash, Civitai name, HF name, filename fallback. See `src/store/enrichment.py:271`.
+5. There is no `LocalHashEvidenceProvider` in `ResolveService._ensure_providers()`. See `src/store/resolve_service.py:160`.
+6. So local hash is an import/local-tab feature, not part of normal `suggest_resolution()`.
+
+### AI Evidence
+
+Status: Wired, but broad and prompt-dependent.
+
+1. `AIEvidenceProvider` is registered in the provider chain. See `src/store/resolve_service.py:166`.
+2. It is skipped unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+3. It builds a text input with pack name/type/base_model/description/tags, dependency kind/hint/expose filename, and preview hints. See `src/store/evidence_providers.py:774`.
+4. It calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:526`.
+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+6. Fallback when AI is off: provider is skipped; E1-E6 still run. See `src/store/evidence_providers.py:510`, `src/store/resolve_service.py:226`.
+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
+
+## UI Integration
+
+### DependencyResolverModal
+
+Status: Integrated as the primary modal.
+
+1. `PackDetailPage` keeps resolver state and opens modal per asset. See `apps/web/src/components/modules/PackDetailPage.tsx:126`, `apps/web/src/components/modules/PackDetailPage.tsx:132`.
+2. Opening the modal eagerly calls `suggestResolution()` without AI. See `apps/web/src/components/modules/PackDetailPage.tsx:141`.
+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
+4. Candidate cards show confidence label, provider, base model, compatibility warning, evidence groups, and raw score when expanded. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:193`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:235`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:279`.
+5. Apply and Apply & Download buttons are wired. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:616`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:631`.
+
+### Civitai Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:351`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+
+### HuggingFace Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible only for frontend HF-eligible kinds. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+
+### Local Resolve Tab
+
+Status: Functional.
+
+1. It browses/recommends a directory using `/recommend-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:160`.
+2. It imports a selected file using `/import-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`.
+3. It polls `/api/store/imports/{import_id}`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+4. It displays browse/importing/success/error states. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:297`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:368`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:441`.
+
+### Apply
+
+Status: Wired, but cache binding is incomplete.
+
+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
+4. UUID collision risk is low, but missing pack/dep binding is a correctness gap already noted in the plan as deferred. See `plans/PLAN-Resolve-Model.md:888`.
+
+### AI Gate
+
+Status: Implemented frontend and backend, with different semantics.
+
+1. Frontend hides AI tab unless avatar status has `available=true`. See `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+2. Backend hides AI provider when config `resolve.enable_ai=false` or avatar getter returns None. See `src/store/evidence_providers.py:510`.
+3. Backend does not check avatar runtime status `available`; it assumes non-None service can run. NEEDS VERIFICATION.
+
+## Preview Analysis
+
+Status: UI tab and backend extractor are wired; it is partly display-only.
+
+1. Backend endpoint `/preview-analysis` analyzes preview sidecars and PNG text. See `src/store/api.py:2275`.
+2. Frontend hook fetches `/api/packs/{pack}/preview-analysis`. See `apps/web/src/components/modules/pack-detail/hooks/usePreviewAnalysis.ts:10`.
+3. Preview tab displays thumbnails, model references, hashes, weights, and generation params. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:64`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:116`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:182`.
+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
+7. In backend suggest, preview hints are only available if `_post_import_resolve()` passes overrides or if a dependency has `_preview_hints`. See `src/store/resolve_service.py:201`.
+8. The public suggest endpoint does not itself run preview analysis or pass preview hints. See `src/store/api.py:2302`, `src/store/api.py:2322`.
+9. The tab fetches preview analysis separately, but those hints are not fed back into `onSuggest()`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:507`.
+
+## AI Integration
+
+Status: Real task and service wiring exist; live provider claims need verification.
+
+1. `DependencyResolutionTask` is registered in default registry per plan; registry change present in diff stat, not deeply audited here. NEEDS VERIFICATION on exact registry line.
+2. Task prompt is skill-file based; `build_system_prompt()` returns skill content only. See `src/avatar/tasks/dependency_resolution.py:53`.
+3. Task parses and validates AI output with provider-specific required fields. See `src/avatar/tasks/dependency_resolution.py:63`, `src/avatar/tasks/dependency_resolution.py:127`.
+4. Task has no fallback; E1-E6 are expected to provide non-AI coverage. See `src/avatar/tasks/dependency_resolution.py:164`.
+5. `AvatarTaskService` starts `AvatarEngine` with MCP servers for `needs_mcp` tasks. See `src/avatar/task_service.py:336`.
+6. MCP includes `search_civitai`, `analyze_civitai_model`, `find_model_by_hash`, `suggest_asset_sources`, and `search_huggingface`. See `src/avatar/mcp/store_server.py:1428`, `src/avatar/mcp/store_server.py:1434`, `src/avatar/mcp/store_server.py:1486`, `src/avatar/mcp/store_server.py:1492`, `src/avatar/mcp/store_server.py:1498`.
+7. `find_model_by_hash` is Civitai-only despite AI prompt comments mentioning HF/hash capability. See `src/avatar/mcp/store_server.py:1143`.
+8. `search_huggingface` performs real HTTP through `requests`, not through the shared HF client/session/token. See `src/avatar/mcp/store_server.py:1239`.
+9. NEEDS VERIFICATION: whether avatar-engine permissions and MCP server config are actually present in local runtime config, not just `config/avatar.yaml.example`.
+
+## Tests
+
+### Unit Tests
+
+Status: Broad coverage, often mocked.
+
+1. Unit tests exist for models, config, validation, scoring, hash cache, providers, resolve service, preview extractor, local file service, enrichment, and AI task per diff stat.
+2. `tests/unit/store/test_evidence_providers.py` heavily uses `MagicMock`. See grep output: many `MagicMock` references, e.g. `tests/unit/store/test_evidence_providers.py:32`.
+3. This is fine for unit mechanics but does not prove real Civitai/HF data shape compatibility.
+4. Some tests do use Pydantic models in other files per plan, but the most provider-critical unit file is mock-heavy. NEEDS VERIFICATION against real clients.
+
+### Integration Tests
+
+Status: Present but partly fake.
+
+1. `test_resolve_integration.py` uses real `ResolveService` but mock PackService/Layout and fake providers. See `tests/integration/test_resolve_integration.py:1`, `tests/integration/test_resolve_integration.py:61`, `tests/integration/test_resolve_integration.py:77`.
+2. `test_resolve_smoke.py` creates a real `Store(tmp_path)` but still uses MagicMock packs/deps for several scenarios. See `tests/integration/test_resolve_smoke.py:20`, `tests/integration/test_resolve_smoke.py:37`.
+3. AI integration file claims real components but uses `MagicMock` for packs/deps and avatar. See `tests/integration/test_ai_resolve_integration.py:42`, grep lines.
+4. These tests validate orchestration, not full end-to-end provider correctness.
+
+### Smoke Tests
+
+Status: Present, low-to-medium realism.
+
+1. Store smoke checks service wiring and migration behavior. See `tests/integration/test_resolve_smoke.py:104`.
+2. It does not perform a real Civitai import with actual downloaded sidecars in normal CI. NEEDS VERIFICATION.
+
+### E2E Tests
+
+Status: Two categories: mocked Playwright and standalone live scripts.
+
+1. Playwright resolve E2E is explicitly offline and mocked. See `apps/web/e2e/resolve-dependency.spec.ts:1`.
+2. Helpers "mock the backend completely." See `apps/web/e2e/helpers/resolve.helpers.ts:245`.
+3. These tests cover UI flows but not backend resolver correctness.
+4. `tests/e2e_resolve_real.py` is a standalone script for live providers, not a pytest test by default. See `tests/e2e_resolve_real.py:10`, `tests/e2e_resolve_real.py:331`.
+5. It exits 0 if there are no provider errors, even if correctness failures occur; `sys.exit(0 if err_count == 0 else 1)` ignores `fail_count`. See `tests/e2e_resolve_real.py:412`.
+6. That makes it unsuitable as a hard correctness gate without modification.
+
+## Spec vs Code Gaps
+
+1. API shape mismatch: spec says `/dependencies/{dep_id}/suggest` and `/dependencies/{dep_id}/apply`; code uses pack-level `/suggest-resolution`, `/apply-resolution`, `/apply-manual-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+2. `analyze_previews` option is defined but not exposed in API or used in service. See `src/store/resolve_models.py:135`, `src/store/api.py:2247`, `src/store/resolve_service.py:201`.
+3. Preview provider does not filter hints by target kind. See `plans/PLAN-Resolve-Model.md:167`, `src/store/evidence_providers.py:169`.
+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. Manual Civitai and HF search tabs are placeholders. See `plans/PLAN-Resolve-Model.md:459`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+7. Candidate cache lacks pack/dep binding. See `plans/PLAN-Resolve-Model.md:888`, `src/store/resolve_service.py:75`.
+8. Apply does not update `pack.lock.json`; PackService says it intentionally does not touch lock. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
+10. HF search tool is not full tree/model-card inspection and not structured JSON. See `plans/PLAN-Resolve-Model.md:803`, `src/avatar/mcp/store_server.py:1229`.
+11. HF hash lookup is verification of an existing selector, not general HF reverse lookup. See `src/store/evidence_providers.py:618`.
+12. `HashEvidenceProvider.supports()` returns true for everything and only no-ops later; eligibility is not expressed at support level. See `src/store/evidence_providers.py:63`.
+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
+14. Default alias config also uses placeholder zero IDs. See `src/store/models.py:281`.
+
+## Refactor Candidates
+
+1. Consolidate Civitai name/hash enrichment. `PreviewMetaEvidenceProvider` duplicates logic that now exists in `src/store/enrichment.py`. See `src/store/evidence_providers.py:230`, `src/store/enrichment.py:42`.
+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
+4. Split AI provider orchestration into two passes: deterministic E1-E6 first, optional AI only if needed. See `src/store/resolve_service.py:216`.
+5. Add kind filtering at resolver input boundary, not only extractor helper. See `src/utils/preview_meta_extractor.py:584`.
+6. Create a shared HF search client/path for MCP, enrichment, and evidence rather than direct `requests` in MCP plus `HuggingFaceClient` elsewhere. See `src/avatar/mcp/store_server.py:1239`, `src/clients/huggingface_client.py:120`.
+7. Decide whether apply should write lock data. Current PackService doc contradicts the earlier spec. See `src/store/pack_service.py:1228`.
+8. Extract frontend provider manual search tabs into real components or remove placeholder tabs until implemented.
+9. Clarify `pack_service.hf_client` vs `pack_service.huggingface` naming. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`.
+10. Turn standalone live E2E scripts into pytest tests with explicit opt-in markers and fail on incorrect top match, not only provider errors. See `tests/e2e_resolve_real.py:412`.
+
+## Open Questions for Owner
+
+1. Is the local `v0.11.0` plan the source of truth, or should the audit compare against an older v0.7.1 from the missing machine?
+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
+3. Should Civitai/HF manual tabs be implemented before Release 1, point 1, or are placeholders acceptable?
+4. Should preview analysis hints feed back into `suggestResolution()` from the UI, or is preview analysis only informational after import?
+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
+6. What is the authoritative HF client attribute on PackService: `hf_client` or `huggingface`?
+7. Should AI run alongside deterministic providers when requested, or only after deterministic providers fail to produce Tier 1/2?
+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
+9. Is HF reverse hash lookup explicitly out of scope due to HF API limitations, with only known-repo LFS verification required?
+10. Which test command is the release gate: full pytest, Playwright E2E, live AI scripts, or a curated subset?
+11. Are live provider results from `tests/e2e_resolve_real.py` stored anywhere reproducible, or only printed to terminal?
+12. Should local import fallback bypass validation if `resolve_service` is unavailable, or should that path hard-fail?
+
+## Release Risk Assessment
+
+1. Backend core is real enough for continued integration work.
+2. The UX is not feature-complete for manual Civitai/HF resolution despite tab presence.
+3. Preview analysis is useful, but not fully integrated as a first-class resolve source in the UI.
+4. AI integration is plausible, but relies on runtime avatar/MCP configuration and prompt behavior; local code alone does not prove live reliability.
+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
+6. The largest spec compliance risk is that "Suggest / Apply is the single write path updating pack + lock" is not what PackService currently does.

exec
/bin/bash -lc 'wc -l plans/audit-resolve-model-redesign-local.md' in /home/box/git/github/synapse
 succeeded in 0ms:
359 plans/audit-resolve-model-redesign-local.md

exec
/bin/bash -lc 'git status --short' in /home/box/git/github/synapse
 succeeded in 0ms:
?? plans/PLAN-Release-1-Roadmap.md
?? plans/audit-resolve-model-redesign-local.md
?? plans/audits/

diff --git a/plans/audit-resolve-model-redesign-local.md b/plans/audit-resolve-model-redesign-local.md
new file mode 100644
index 0000000000000000000000000000000000000000..4e67f00b330a87af81d1cfa3cea437470b25d9a0
--- /dev/null
+++ b/plans/audit-resolve-model-redesign-local.md
@@ -0,0 +1,359 @@
+# Audit: Resolve Model Redesign, Local Branch State
+
+Branch audited: `feat/resolve-model-redesign` at `5b30b99071070678878088766ec0d73e063b29f2`.
+
+Scope note: audit used only the local branch contents available in this workspace. The user warned the newest commit may exist on another machine and may not be pushed; anything absent here is treated as absent locally.
+
+## Executive Summary
+
+1. The branch is much larger and newer than the stated context: `plans/PLAN-Resolve-Model.md` says `v0.11.0` and claims Phase 0+1+2+2.5+3+4 complete at the top, then later claims Phase 5 and Phase 6 complete too. See `plans/PLAN-Resolve-Model.md:3`, `plans/PLAN-Resolve-Model.md:1018`, `plans/PLAN-Resolve-Model.md:1239`, `plans/PLAN-Resolve-Model.md:1300`.
+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
+3. The implementation is not fully aligned with the main spec. The biggest gaps are: manual Civitai/HF tabs are placeholders, preview hints are not kind-filtered in the resolver chain, canonical source is mostly not populated for remote suggestions, `analyze_previews` is modeled but unused, and apply writes only `pack.json`, not `pack.lock.json`.
+4. Evidence provider coverage is partial. Civitai hash is implemented. HF hash is not a reverse lookup; it only verifies a pre-existing HF selector. Local hash exists through local import/cache, but not as a normal evidence provider in the suggest chain. AI evidence is wired into `ResolveService`, but runs whenever `include_ai=True`, not only after E1-E6 fail to produce Tier 1/2.
+5. Tests are extensive by count, but many important ones are mocked/ceremonial. Backend unit and integration tests cover a lot of mechanics. Frontend E2E is fully mocked. Live AI E2E is a standalone script, not a normal pytest/CI test. NEEDS VERIFICATION: actual latest CI status and whether the "real provider" scripts were run on this local branch state.
+
+## Branch Delta
+
+1. `git diff --stat main..feat/resolve-model-redesign` reports 95 files changed, about 22,233 insertions and 1,355 deletions.
+2. Major new backend files include `src/store/resolve_service.py`, `src/store/resolve_models.py`, `src/store/evidence_providers.py`, `src/store/enrichment.py`, `src/store/local_file_service.py`, `src/store/hash_cache.py`, and `src/avatar/tasks/dependency_resolution.py`.
+3. Major frontend changes replace `BaseModelResolverModal.tsx` with `DependencyResolverModal.tsx`, `LocalResolveTab.tsx`, and `PreviewAnalysisTab.tsx`.
+4. Test expansion is large: unit tests for resolve, evidence, local file service, preview extraction, AI task; integration/smoke tests; Playwright E2E; standalone live AI E2E scripts.
+
+## Spec Version Drift
+
+1. User context names `plans/PLAN-Resolve-Model.md` as v0.7.1, 1769 lines.
+2. Local branch plan is `v0.11.0`, with 2439 added lines in the diff stat and top-level status saying Phase 0+1+2+2.5+3+4 complete. See `plans/PLAN-Resolve-Model.md:3`.
+3. Many implementation files still say "Based on PLAN-Resolve-Model.md v0.7.1" in docstrings. See `src/store/resolve_service.py:5`, `src/store/resolve_models.py:4`, `src/store/evidence_providers.py:4`.
+4. NEEDS VERIFICATION: whether this plan/version mismatch is expected local history or drift from another machine.
+
+## Phase Coverage
+
+### Phase 0: Infrastructure, Model, Calibration
+
+Status: Mostly implemented, with caveats.
+
+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
+3. Tier boundaries, HF eligibility, compatibility rules, AI ceiling, and auto-apply margin exist. See `src/store/resolve_config.py:28`, `src/store/resolve_config.py:35`, `src/store/resolve_config.py:80`, `src/store/resolve_config.py:132`, `src/store/resolve_config.py:173`.
+4. Scoring implements provenance grouping, Noisy-OR, and tier ceiling. See `src/store/resolve_scoring.py:16`, `src/store/resolve_scoring.py:38`, `src/store/resolve_scoring.py:77`.
+5. Hash cache exists with mtime+size invalidation and atomic save. See `src/store/hash_cache.py:36`, `src/store/hash_cache.py:67`, `src/store/hash_cache.py:84`.
+6. Async hash helper exists. See `src/store/hash_cache.py:159`.
+7. Preview extractor exists for sidecar JSON and PNG tEXt chunks. See `src/utils/preview_meta_extractor.py:97`, `src/utils/preview_meta_extractor.py:127`, `src/utils/preview_meta_extractor.py:252`, `src/utils/preview_meta_extractor.py:405`.
+8. Caveat: calibration is not fully implemented. The plan itself says confidence calibration is deferred. See `plans/PLAN-Resolve-Model.md:604`.
+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
+
+### Phase 1: Import Pipeline and Bug Fixes
+
+Status: Implemented mechanically, but behavior is narrower than the spec implies.
+
+1. Store calls `_post_import_resolve(pack)` after Civitai import. See `src/store/__init__.py:592`.
+2. `_post_import_resolve()` extracts preview hints from downloaded previews, calls `resolve_service.suggest()` with `include_ai=False`, and auto-applies Tier 1/2 if margin passes. See `src/store/__init__.py:604`, `src/store/__init__.py:624`, `src/store/__init__.py:632`, `src/store/__init__.py:655`.
+3. It skips dependencies that are not `BASE_MODEL_HINT`, avoiding overwriting pinned deps. See `src/store/__init__.py:626`.
+4. It checks `ApplyResult.success` before logging success. See `src/store/__init__.py:656`, `src/store/__init__.py:660`.
+5. Suggest/apply API endpoints exist, but not at the exact spec path. The plan sketches `/dependencies/{dep_id}/suggest`; code uses pack-level body params: `/api/packs/{pack}/suggest-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+6. `SuggestRequest` has no `analyze_previews` field, even though `SuggestOptions` does. See `src/store/api.py:2247`, `src/store/resolve_models.py:135`.
+7. Caveat: `ResolveService.suggest()` ignores `options.analyze_previews`; it only uses `preview_hints_override` or `dep._preview_hints`. See `src/store/resolve_service.py:201`.
+8. Caveat: import preview hints are passed wholesale to every BASE_MODEL_HINT dep; filtering by dependency kind is not applied at this stage. See `src/store/__init__.py:636` and `src/store/evidence_providers.py:169`.
+
+### Phase 2: AI-Enhanced Resolution and UI
+
+Status: AI backend is wired; UI is partly wired; manual provider tabs are mocked/placeholders.
+
+1. `DependencyResolutionTask` exists, has `needs_mcp=True`, timeout 180s, and loads five skill files. See `src/avatar/tasks/dependency_resolution.py:42`, `src/avatar/tasks/dependency_resolution.py:43`, `src/avatar/tasks/dependency_resolution.py:50`.
+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
+3. `AIEvidenceProvider` builds structured text and calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:518`, `src/store/evidence_providers.py:525`.
+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+5. AI ceiling is enforced in both task parsing and evidence conversion. See `src/avatar/tasks/dependency_resolution.py:89`, `src/store/evidence_providers.py:844`.
+6. `ResolveService` registers AI provider. See `src/store/resolve_service.py:166`.
+7. `ResolveService.suggest()` skips AI unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+9. UI modal exists with Candidates, Preview, Local, AI, Civitai, and HF tabs. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:61`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:346`.
+10. AI tab is gated by `avatarAvailable`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:350`, `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+11. HF tab is gated by frontend `HF_ELIGIBLE_KINDS`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+12. Civitai manual tab is a placeholder: "Manual Civitai search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+13. HuggingFace manual tab is a placeholder: "Manual HuggingFace search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+14. This contradicts the plan's Phase 4 complete claim for provider polish/manual payloads from the UI. Backend manual apply exists; frontend manual search does not.
+
+### Phase 2.5: Preview Enrichment
+
+Status: Partially implemented.
+
+1. `PreviewMetaEvidenceProvider` enriches hints via Civitai hash lookup, then Civitai name search. See `src/store/evidence_providers.py:143`, `src/store/evidence_providers.py:177`, `src/store/evidence_providers.py:246`, `src/store/evidence_providers.py:252`.
+2. It uses `pack_service_getter` and is wired with PackService in `ResolveService._ensure_providers()`. See `src/store/evidence_providers.py:154`, `src/store/resolve_service.py:162`.
+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
+5. Gap: no kind filtering in `PreviewMetaEvidenceProvider.gather()`. It iterates all hints and does not check `hint.kind` against `ctx.kind`. See `src/store/evidence_providers.py:169`.
+6. The extractor has `filter_hints_by_kind()`, but `git grep` shows no production use. See `src/utils/preview_meta_extractor.py:584`.
+7. This is a direct spec gap: plan requires kind-aware filtering. See `plans/PLAN-Resolve-Model.md:167`.
+
+### Phase 3: Local Resolve
+
+Status: Implemented and UI-integrated.
+
+1. Backend local browse, recommendation, and import service exists. See `src/store/local_file_service.py:191`, `src/store/local_file_service.py:207`, `src/store/local_file_service.py:268`, `src/store/local_file_service.py:344`.
+2. Path validation requires absolute path, no `..`, resolved path exists, extension allowlist, regular file. See `src/store/local_file_service.py:111`.
+3. Local import hashes, copies into blob store, enriches, and applies resolution. See `src/store/local_file_service.py:377`, `src/store/local_file_service.py:390`, `src/store/local_file_service.py:414`, `src/store/local_file_service.py:428`.
+4. API endpoints exist: browse-local, recommend-local, import-local with background executor and polling. See `src/store/api.py:2485`, `src/store/api.py:2502`, `src/store/api.py:2546`.
+5. UI tab exists and calls recommend/import/poll endpoints. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:150`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+6. Caveat: local import applies via `resolve_service.apply_manual()` if reachable, otherwise falls back to `pack_service.apply_dependency_resolution()`. See `src/store/local_file_service.py:544`.
+7. Caveat: fallback path bypasses validation if `resolve_service` is not available. See `src/store/local_file_service.py:554`.
+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
+
+### Phase 4: Provider Polish, Download, Cleanup
+
+Status: Cleanup and validation mostly implemented; manual provider UI and lock/write behavior remain incomplete.
+
+1. Deprecated `BaseModelResolverModal.tsx` is deleted according to diff stat.
+2. `/resolve-base-model` appears removed; current resolve endpoints are `suggest-resolution`, `apply-resolution`, and `apply-manual-resolution`. See `src/store/api.py:2302`, `src/store/api.py:2342`, `src/store/api.py:2370`.
+3. API boundary validates manual strategy fields. See `src/store/api.py:2383`.
+4. `Apply & Download` UI does a compound apply then `/download-asset`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401`, `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:437`.
+5. NEEDS VERIFICATION: `download-asset` expects `asset_name`; UI sends `depId`. This may be correct if asset name equals dependency id, but the audit did not verify all pack shapes. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:442`.
+6. Major gap: Civitai and HF manual tabs are not implemented. They cannot produce typed payloads from UI. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+7. Major gap: `PackService.apply_dependency_resolution()` explicitly does not touch `pack.lock.json`, contrary to earlier spec language that apply updates pack.json and pack.lock atomically. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+8. `lock_entry` is accepted but unused. See `src/store/pack_service.py:1223`, `src/store/pack_service.py:1237`.
+
+### Phase 5: Deferred Polish
+
+Status: Mostly implemented, but not all to full spec strength.
+
+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
+2. `AUTO_APPLY_MARGIN` is centralized and config-readable. See `src/store/resolve_config.py:132`, `src/store/resolve_config.py:138`, `src/store/__init__.py:648`.
+3. `compute_sha256_async()` exists. See `src/store/hash_cache.py:159`.
+4. HF enrichment exists as `enrich_by_hf()` and is used in `enrich_file()`. See `src/store/enrichment.py:166`, `src/store/enrichment.py:294`.
+5. HuggingFace client parses LFS `lfs.oid` into SHA256. See `src/clients/huggingface_client.py:36`.
+6. HuggingFace client has `search_models()`. See `src/clients/huggingface_client.py:120`.
+7. Caveat: `LocalFileService._get_hf_client()` looks for `pack_service.hf_client`, but other code references `pack_service.huggingface` for HF access in the plan and evidence provider uses `pack_service.huggingface`. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`. NEEDS VERIFICATION: actual PackService attribute name.
+8. Caveat: MCP `search_huggingface` returns formatted text, not JSON. The plan says text may be OK for LLM, but "structured output" remains unresolved in code. See `plans/PLAN-Resolve-Model.md:1271`, `src/avatar/mcp/store_server.py:1229`.
+9. Caveat: MCP HF search only fetches top-level `tree/main`, not recursive subfolders or model cards. See `src/avatar/mcp/store_server.py:1306`.
+
+### Phase 6: Config, Aliases, Tests, AI Gate
+
+Status: Implemented mechanically, but alias defaults and test realism are weak.
+
+1. `ResolveConfig` exists under `StoreConfig.resolve`. See `src/store/models.py:243`, `src/store/models.py:257`.
+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
+3. `AIEvidenceProvider.supports()` checks config flag and avatar object. See `src/store/evidence_providers.py:510`.
+4. Alias provider reads `layout.load_config().base_model_aliases`. See `src/store/evidence_providers.py:692`.
+5. Alias provider supports Civitai and HF targets. See `src/store/evidence_providers.py:713`, `src/store/evidence_providers.py:741`.
+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
+7. Caveat: AI gate checks avatar object presence backend-side, not a status `available` field. It assumes a non-None avatar service is usable. See `src/store/evidence_providers.py:516`.
+
+## Evidence Providers
+
+### Civitai Hash Evidence
+
+Status: Implemented and wired.
+
+1. `HashEvidenceProvider` reads SHA256 from `dep.lock.sha256`. See `src/store/evidence_providers.py:75`.
+2. It calls `pack_service.civitai.get_model_by_hash(sha256)`. See `src/store/evidence_providers.py:88`.
+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
+4. It assigns `hash_match` evidence with confidence 0.95. See `src/store/evidence_providers.py:120`.
+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
+6. Gap: it only reads hash from `dep.lock`; it does not hash local files as part of suggest. See `src/store/evidence_providers.py:75`.
+
+### HuggingFace LFS OID Evidence
+
+Status: Partial verification only, not discovery/reverse lookup.
+
+1. HF LFS OID parsing exists in `HFFileInfo.from_api_response()`. See `src/clients/huggingface_client.py:36`.
+2. `HashEvidenceProvider` calls `_hf_hash_lookup()` only when kind config says `hf_hash_lookup=True`. See `src/store/evidence_providers.py:133`.
+3. Only checkpoints have `hf_hash_lookup=True`; VAE/controlnet are HF-eligible but hash lookup false. See `src/store/resolve_config.py:80`, `src/store/resolve_config.py:93`, `src/store/resolve_config.py:99`.
+4. `_hf_hash_lookup()` requires dependency selector already has HF repo and filename. See `src/store/evidence_providers.py:624`, `src/store/evidence_providers.py:629`.
+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
+6. `find_model_by_hash` MCP tool is Civitai-only. See `src/avatar/mcp/store_server.py:1143`.
+
+### Local Hash Evidence
+
+Status: Implemented in local import flow, not in resolver evidence chain.
+
+1. `HashCache` can cache SHA256 by file path. See `src/store/hash_cache.py:36`.
+2. `LocalFileService.recommend()` can compare cached hash with dependency expected hash. See `src/store/local_file_service.py:306`.
+3. `LocalFileService.import_file()` hashes selected file and uses hash cache. See `src/store/local_file_service.py:377`.
+4. `enrich_file()` then tries Civitai hash, Civitai name, HF name, filename fallback. See `src/store/enrichment.py:271`.
+5. There is no `LocalHashEvidenceProvider` in `ResolveService._ensure_providers()`. See `src/store/resolve_service.py:160`.
+6. So local hash is an import/local-tab feature, not part of normal `suggest_resolution()`.
+
+### AI Evidence
+
+Status: Wired, but broad and prompt-dependent.
+
+1. `AIEvidenceProvider` is registered in the provider chain. See `src/store/resolve_service.py:166`.
+2. It is skipped unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+3. It builds a text input with pack name/type/base_model/description/tags, dependency kind/hint/expose filename, and preview hints. See `src/store/evidence_providers.py:774`.
+4. It calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:526`.
+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+6. Fallback when AI is off: provider is skipped; E1-E6 still run. See `src/store/evidence_providers.py:510`, `src/store/resolve_service.py:226`.
+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
+
+## UI Integration
+
+### DependencyResolverModal
+
+Status: Integrated as the primary modal.
+
+1. `PackDetailPage` keeps resolver state and opens modal per asset. See `apps/web/src/components/modules/PackDetailPage.tsx:126`, `apps/web/src/components/modules/PackDetailPage.tsx:132`.
+2. Opening the modal eagerly calls `suggestResolution()` without AI. See `apps/web/src/components/modules/PackDetailPage.tsx:141`.
+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
+4. Candidate cards show confidence label, provider, base model, compatibility warning, evidence groups, and raw score when expanded. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:193`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:235`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:279`.
+5. Apply and Apply & Download buttons are wired. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:616`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:631`.
+
+### Civitai Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:351`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+
+### HuggingFace Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible only for frontend HF-eligible kinds. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+
+### Local Resolve Tab
+
+Status: Functional.
+
+1. It browses/recommends a directory using `/recommend-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:160`.
+2. It imports a selected file using `/import-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`.
+3. It polls `/api/store/imports/{import_id}`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+4. It displays browse/importing/success/error states. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:297`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:368`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:441`.
+
+### Apply
+
+Status: Wired, but cache binding is incomplete.
+
+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
+4. UUID collision risk is low, but missing pack/dep binding is a correctness gap already noted in the plan as deferred. See `plans/PLAN-Resolve-Model.md:888`.
+
+### AI Gate
+
+Status: Implemented frontend and backend, with different semantics.
+
+1. Frontend hides AI tab unless avatar status has `available=true`. See `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+2. Backend hides AI provider when config `resolve.enable_ai=false` or avatar getter returns None. See `src/store/evidence_providers.py:510`.
+3. Backend does not check avatar runtime status `available`; it assumes non-None service can run. NEEDS VERIFICATION.
+
+## Preview Analysis
+
+Status: UI tab and backend extractor are wired; it is partly display-only.
+
+1. Backend endpoint `/preview-analysis` analyzes preview sidecars and PNG text. See `src/store/api.py:2275`.
+2. Frontend hook fetches `/api/packs/{pack}/preview-analysis`. See `apps/web/src/components/modules/pack-detail/hooks/usePreviewAnalysis.ts:10`.
+3. Preview tab displays thumbnails, model references, hashes, weights, and generation params. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:64`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:116`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:182`.
+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
+7. In backend suggest, preview hints are only available if `_post_import_resolve()` passes overrides or if a dependency has `_preview_hints`. See `src/store/resolve_service.py:201`.
+8. The public suggest endpoint does not itself run preview analysis or pass preview hints. See `src/store/api.py:2302`, `src/store/api.py:2322`.
+9. The tab fetches preview analysis separately, but those hints are not fed back into `onSuggest()`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:507`.
+
+## AI Integration
+
+Status: Real task and service wiring exist; live provider claims need verification.
+
+1. `DependencyResolutionTask` is registered in default registry per plan; registry change present in diff stat, not deeply audited here. NEEDS VERIFICATION on exact registry line.
+2. Task prompt is skill-file based; `build_system_prompt()` returns skill content only. See `src/avatar/tasks/dependency_resolution.py:53`.
+3. Task parses and validates AI output with provider-specific required fields. See `src/avatar/tasks/dependency_resolution.py:63`, `src/avatar/tasks/dependency_resolution.py:127`.
+4. Task has no fallback; E1-E6 are expected to provide non-AI coverage. See `src/avatar/tasks/dependency_resolution.py:164`.
+5. `AvatarTaskService` starts `AvatarEngine` with MCP servers for `needs_mcp` tasks. See `src/avatar/task_service.py:336`.
+6. MCP includes `search_civitai`, `analyze_civitai_model`, `find_model_by_hash`, `suggest_asset_sources`, and `search_huggingface`. See `src/avatar/mcp/store_server.py:1428`, `src/avatar/mcp/store_server.py:1434`, `src/avatar/mcp/store_server.py:1486`, `src/avatar/mcp/store_server.py:1492`, `src/avatar/mcp/store_server.py:1498`.
+7. `find_model_by_hash` is Civitai-only despite AI prompt comments mentioning HF/hash capability. See `src/avatar/mcp/store_server.py:1143`.
+8. `search_huggingface` performs real HTTP through `requests`, not through the shared HF client/session/token. See `src/avatar/mcp/store_server.py:1239`.
+9. NEEDS VERIFICATION: whether avatar-engine permissions and MCP server config are actually present in local runtime config, not just `config/avatar.yaml.example`.
+
+## Tests
+
+### Unit Tests
+
+Status: Broad coverage, often mocked.
+
+1. Unit tests exist for models, config, validation, scoring, hash cache, providers, resolve service, preview extractor, local file service, enrichment, and AI task per diff stat.
+2. `tests/unit/store/test_evidence_providers.py` heavily uses `MagicMock`. See grep output: many `MagicMock` references, e.g. `tests/unit/store/test_evidence_providers.py:32`.
+3. This is fine for unit mechanics but does not prove real Civitai/HF data shape compatibility.
+4. Some tests do use Pydantic models in other files per plan, but the most provider-critical unit file is mock-heavy. NEEDS VERIFICATION against real clients.
+
+### Integration Tests
+
+Status: Present but partly fake.
+
+1. `test_resolve_integration.py` uses real `ResolveService` but mock PackService/Layout and fake providers. See `tests/integration/test_resolve_integration.py:1`, `tests/integration/test_resolve_integration.py:61`, `tests/integration/test_resolve_integration.py:77`.
+2. `test_resolve_smoke.py` creates a real `Store(tmp_path)` but still uses MagicMock packs/deps for several scenarios. See `tests/integration/test_resolve_smoke.py:20`, `tests/integration/test_resolve_smoke.py:37`.
+3. AI integration file claims real components but uses `MagicMock` for packs/deps and avatar. See `tests/integration/test_ai_resolve_integration.py:42`, grep lines.
+4. These tests validate orchestration, not full end-to-end provider correctness.
+
+### Smoke Tests
+
+Status: Present, low-to-medium realism.
+
+1. Store smoke checks service wiring and migration behavior. See `tests/integration/test_resolve_smoke.py:104`.
+2. It does not perform a real Civitai import with actual downloaded sidecars in normal CI. NEEDS VERIFICATION.
+
+### E2E Tests
+
+Status: Two categories: mocked Playwright and standalone live scripts.
+
+1. Playwright resolve E2E is explicitly offline and mocked. See `apps/web/e2e/resolve-dependency.spec.ts:1`.
+2. Helpers "mock the backend completely." See `apps/web/e2e/helpers/resolve.helpers.ts:245`.
+3. These tests cover UI flows but not backend resolver correctness.
+4. `tests/e2e_resolve_real.py` is a standalone script for live providers, not a pytest test by default. See `tests/e2e_resolve_real.py:10`, `tests/e2e_resolve_real.py:331`.
+5. It exits 0 if there are no provider errors, even if correctness failures occur; `sys.exit(0 if err_count == 0 else 1)` ignores `fail_count`. See `tests/e2e_resolve_real.py:412`.
+6. That makes it unsuitable as a hard correctness gate without modification.
+
+## Spec vs Code Gaps
+
+1. API shape mismatch: spec says `/dependencies/{dep_id}/suggest` and `/dependencies/{dep_id}/apply`; code uses pack-level `/suggest-resolution`, `/apply-resolution`, `/apply-manual-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+2. `analyze_previews` option is defined but not exposed in API or used in service. See `src/store/resolve_models.py:135`, `src/store/api.py:2247`, `src/store/resolve_service.py:201`.
+3. Preview provider does not filter hints by target kind. See `plans/PLAN-Resolve-Model.md:167`, `src/store/evidence_providers.py:169`.
+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. Manual Civitai and HF search tabs are placeholders. See `plans/PLAN-Resolve-Model.md:459`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+7. Candidate cache lacks pack/dep binding. See `plans/PLAN-Resolve-Model.md:888`, `src/store/resolve_service.py:75`.
+8. Apply does not update `pack.lock.json`; PackService says it intentionally does not touch lock. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
+10. HF search tool is not full tree/model-card inspection and not structured JSON. See `plans/PLAN-Resolve-Model.md:803`, `src/avatar/mcp/store_server.py:1229`.
+11. HF hash lookup is verification of an existing selector, not general HF reverse lookup. See `src/store/evidence_providers.py:618`.
+12. `HashEvidenceProvider.supports()` returns true for everything and only no-ops later; eligibility is not expressed at support level. See `src/store/evidence_providers.py:63`.
+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
+14. Default alias config also uses placeholder zero IDs. See `src/store/models.py:281`.
+
+## Refactor Candidates
+
+1. Consolidate Civitai name/hash enrichment. `PreviewMetaEvidenceProvider` duplicates logic that now exists in `src/store/enrichment.py`. See `src/store/evidence_providers.py:230`, `src/store/enrichment.py:42`.
+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
+4. Split AI provider orchestration into two passes: deterministic E1-E6 first, optional AI only if needed. See `src/store/resolve_service.py:216`.
+5. Add kind filtering at resolver input boundary, not only extractor helper. See `src/utils/preview_meta_extractor.py:584`.
+6. Create a shared HF search client/path for MCP, enrichment, and evidence rather than direct `requests` in MCP plus `HuggingFaceClient` elsewhere. See `src/avatar/mcp/store_server.py:1239`, `src/clients/huggingface_client.py:120`.
+7. Decide whether apply should write lock data. Current PackService doc contradicts the earlier spec. See `src/store/pack_service.py:1228`.
+8. Extract frontend provider manual search tabs into real components or remove placeholder tabs until implemented.
+9. Clarify `pack_service.hf_client` vs `pack_service.huggingface` naming. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`.
+10. Turn standalone live E2E scripts into pytest tests with explicit opt-in markers and fail on incorrect top match, not only provider errors. See `tests/e2e_resolve_real.py:412`.
+
+## Open Questions for Owner
+
+1. Is the local `v0.11.0` plan the source of truth, or should the audit compare against an older v0.7.1 from the missing machine?
+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
+3. Should Civitai/HF manual tabs be implemented before Release 1, point 1, or are placeholders acceptable?
+4. Should preview analysis hints feed back into `suggestResolution()` from the UI, or is preview analysis only informational after import?
+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
+6. What is the authoritative HF client attribute on PackService: `hf_client` or `huggingface`?
+7. Should AI run alongside deterministic providers when requested, or only after deterministic providers fail to produce Tier 1/2?
+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
+9. Is HF reverse hash lookup explicitly out of scope due to HF API limitations, with only known-repo LFS verification required?
+10. Which test command is the release gate: full pytest, Playwright E2E, live AI scripts, or a curated subset?
+11. Are live provider results from `tests/e2e_resolve_real.py` stored anywhere reproducible, or only printed to terminal?
+12. Should local import fallback bypass validation if `resolve_service` is unavailable, or should that path hard-fail?
+
+## Release Risk Assessment
+
+1. Backend core is real enough for continued integration work.
+2. The UX is not feature-complete for manual Civitai/HF resolution despite tab presence.
+3. Preview analysis is useful, but not fully integrated as a first-class resolve source in the UI.
+4. AI integration is plausible, but relies on runtime avatar/MCP configuration and prompt behavior; local code alone does not prove live reliability.
+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
+6. The largest spec compliance risk is that "Suggest / Apply is the single write path updating pack + lock" is not what PackService currently does.

codex
Wrote the full audit here: [plans/audit-resolve-model-redesign-local.md](/home/box/git/github/synapse/plans/audit-resolve-model-redesign-local.md)

It is 359 lines and includes branch-local refs, phase coverage, evidence provider wiring, UI/mock status, preview/AI/test assessment, spec gaps, refactor candidates, and owner questions.

Main findings:
- Core backend is real and wired, but not fully spec-aligned.
- Civitai/HF manual tabs are placeholders.
- Preview analysis is display/select-only in UI, not a standalone apply path.
- Preview hints are not kind-filtered in the resolver chain.
- HF hash support is known-repo LFS verification, not reverse lookup.
- Most remote candidates do not populate `canonical_source`.
- `apply_dependency_resolution()` updates `pack.json` only, not `pack.lock.json`.
- Frontend E2E is fully mocked; live AI E2E is a standalone script and does not fail on incorrect matches.

I did not run tests. I also left existing unrelated untracked paths untouched (`plans/PLAN-Release-1-Roadmap.md`, `plans/audits/`).
diff --git a/plans/audit-resolve-model-redesign-local.md b/plans/audit-resolve-model-redesign-local.md
new file mode 100644
index 0000000000000000000000000000000000000000..4e67f00b330a87af81d1cfa3cea437470b25d9a0
--- /dev/null
+++ b/plans/audit-resolve-model-redesign-local.md
@@ -0,0 +1,359 @@
+# Audit: Resolve Model Redesign, Local Branch State
+
+Branch audited: `feat/resolve-model-redesign` at `5b30b99071070678878088766ec0d73e063b29f2`.
+
+Scope note: audit used only the local branch contents available in this workspace. The user warned the newest commit may exist on another machine and may not be pushed; anything absent here is treated as absent locally.
+
+## Executive Summary
+
+1. The branch is much larger and newer than the stated context: `plans/PLAN-Resolve-Model.md` says `v0.11.0` and claims Phase 0+1+2+2.5+3+4 complete at the top, then later claims Phase 5 and Phase 6 complete too. See `plans/PLAN-Resolve-Model.md:3`, `plans/PLAN-Resolve-Model.md:1018`, `plans/PLAN-Resolve-Model.md:1239`, `plans/PLAN-Resolve-Model.md:1300`.
+2. The core backend architecture exists: DTOs, `ResolveService`, candidate cache, validation, scoring, API endpoints, Store facade, post-import auto-apply, preview extractor, AI task, MCP tools, local import, and UI modal are present. See `src/store/resolve_service.py:121`, `src/store/resolve_models.py:77`, `src/store/api.py:2302`, `src/store/__init__.py:604`.
+3. The implementation is not fully aligned with the main spec. The biggest gaps are: manual Civitai/HF tabs are placeholders, preview hints are not kind-filtered in the resolver chain, canonical source is mostly not populated for remote suggestions, `analyze_previews` is modeled but unused, and apply writes only `pack.json`, not `pack.lock.json`.
+4. Evidence provider coverage is partial. Civitai hash is implemented. HF hash is not a reverse lookup; it only verifies a pre-existing HF selector. Local hash exists through local import/cache, but not as a normal evidence provider in the suggest chain. AI evidence is wired into `ResolveService`, but runs whenever `include_ai=True`, not only after E1-E6 fail to produce Tier 1/2.
+5. Tests are extensive by count, but many important ones are mocked/ceremonial. Backend unit and integration tests cover a lot of mechanics. Frontend E2E is fully mocked. Live AI E2E is a standalone script, not a normal pytest/CI test. NEEDS VERIFICATION: actual latest CI status and whether the "real provider" scripts were run on this local branch state.
+
+## Branch Delta
+
+1. `git diff --stat main..feat/resolve-model-redesign` reports 95 files changed, about 22,233 insertions and 1,355 deletions.
+2. Major new backend files include `src/store/resolve_service.py`, `src/store/resolve_models.py`, `src/store/evidence_providers.py`, `src/store/enrichment.py`, `src/store/local_file_service.py`, `src/store/hash_cache.py`, and `src/avatar/tasks/dependency_resolution.py`.
+3. Major frontend changes replace `BaseModelResolverModal.tsx` with `DependencyResolverModal.tsx`, `LocalResolveTab.tsx`, and `PreviewAnalysisTab.tsx`.
+4. Test expansion is large: unit tests for resolve, evidence, local file service, preview extraction, AI task; integration/smoke tests; Playwright E2E; standalone live AI E2E scripts.
+
+## Spec Version Drift
+
+1. User context names `plans/PLAN-Resolve-Model.md` as v0.7.1, 1769 lines.
+2. Local branch plan is `v0.11.0`, with 2439 added lines in the diff stat and top-level status saying Phase 0+1+2+2.5+3+4 complete. See `plans/PLAN-Resolve-Model.md:3`.
+3. Many implementation files still say "Based on PLAN-Resolve-Model.md v0.7.1" in docstrings. See `src/store/resolve_service.py:5`, `src/store/resolve_models.py:4`, `src/store/evidence_providers.py:4`.
+4. NEEDS VERIFICATION: whether this plan/version mismatch is expected local history or drift from another machine.
+
+## Phase Coverage
+
+### Phase 0: Infrastructure, Model, Calibration
+
+Status: Mostly implemented, with caveats.
+
+1. Data models exist: `ResolutionCandidate`, `EvidenceGroup`, `EvidenceItem`, `PreviewModelHint`, `SuggestOptions`, `ManualResolveData`, `ResolveContext`. See `src/store/resolve_models.py:38`, `src/store/resolve_models.py:77`, `src/store/resolve_models.py:96`, `src/store/resolve_models.py:132`.
+2. `CanonicalSource` and expanded `DependencySelector` exist in Store models. See `src/store/models.py:381`, `src/store/models.py:398`.
+3. Tier boundaries, HF eligibility, compatibility rules, AI ceiling, and auto-apply margin exist. See `src/store/resolve_config.py:28`, `src/store/resolve_config.py:35`, `src/store/resolve_config.py:80`, `src/store/resolve_config.py:132`, `src/store/resolve_config.py:173`.
+4. Scoring implements provenance grouping, Noisy-OR, and tier ceiling. See `src/store/resolve_scoring.py:16`, `src/store/resolve_scoring.py:38`, `src/store/resolve_scoring.py:77`.
+5. Hash cache exists with mtime+size invalidation and atomic save. See `src/store/hash_cache.py:36`, `src/store/hash_cache.py:67`, `src/store/hash_cache.py:84`.
+6. Async hash helper exists. See `src/store/hash_cache.py:159`.
+7. Preview extractor exists for sidecar JSON and PNG tEXt chunks. See `src/utils/preview_meta_extractor.py:97`, `src/utils/preview_meta_extractor.py:127`, `src/utils/preview_meta_extractor.py:252`, `src/utils/preview_meta_extractor.py:405`.
+8. Caveat: calibration is not fully implemented. The plan itself says confidence calibration is deferred. See `plans/PLAN-Resolve-Model.md:604`.
+9. Caveat: default base model aliases in `StoreConfig.create_default()` are placeholders with `model_id=0`, which validation later rejects. See `src/store/models.py:280`, `src/store/models.py:287`, `src/store/models.py:295`, `src/store/resolve_validation.py:64`.
+
+### Phase 1: Import Pipeline and Bug Fixes
+
+Status: Implemented mechanically, but behavior is narrower than the spec implies.
+
+1. Store calls `_post_import_resolve(pack)` after Civitai import. See `src/store/__init__.py:592`.
+2. `_post_import_resolve()` extracts preview hints from downloaded previews, calls `resolve_service.suggest()` with `include_ai=False`, and auto-applies Tier 1/2 if margin passes. See `src/store/__init__.py:604`, `src/store/__init__.py:624`, `src/store/__init__.py:632`, `src/store/__init__.py:655`.
+3. It skips dependencies that are not `BASE_MODEL_HINT`, avoiding overwriting pinned deps. See `src/store/__init__.py:626`.
+4. It checks `ApplyResult.success` before logging success. See `src/store/__init__.py:656`, `src/store/__init__.py:660`.
+5. Suggest/apply API endpoints exist, but not at the exact spec path. The plan sketches `/dependencies/{dep_id}/suggest`; code uses pack-level body params: `/api/packs/{pack}/suggest-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+6. `SuggestRequest` has no `analyze_previews` field, even though `SuggestOptions` does. See `src/store/api.py:2247`, `src/store/resolve_models.py:135`.
+7. Caveat: `ResolveService.suggest()` ignores `options.analyze_previews`; it only uses `preview_hints_override` or `dep._preview_hints`. See `src/store/resolve_service.py:201`.
+8. Caveat: import preview hints are passed wholesale to every BASE_MODEL_HINT dep; filtering by dependency kind is not applied at this stage. See `src/store/__init__.py:636` and `src/store/evidence_providers.py:169`.
+
+### Phase 2: AI-Enhanced Resolution and UI
+
+Status: AI backend is wired; UI is partly wired; manual provider tabs are mocked/placeholders.
+
+1. `DependencyResolutionTask` exists, has `needs_mcp=True`, timeout 180s, and loads five skill files. See `src/avatar/tasks/dependency_resolution.py:42`, `src/avatar/tasks/dependency_resolution.py:43`, `src/avatar/tasks/dependency_resolution.py:50`.
+2. `AvatarTaskService` passes timeout and MCP servers into `AvatarEngine` for MCP-enabled tasks. See `src/avatar/task_service.py:319`, `src/avatar/task_service.py:336`.
+3. `AIEvidenceProvider` builds structured text and calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:518`, `src/store/evidence_providers.py:525`.
+4. AI candidates map to Civitai and HF `EvidenceHit`s. See `src/store/evidence_providers.py:829`, `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+5. AI ceiling is enforced in both task parsing and evidence conversion. See `src/avatar/tasks/dependency_resolution.py:89`, `src/store/evidence_providers.py:844`.
+6. `ResolveService` registers AI provider. See `src/store/resolve_service.py:166`.
+7. `ResolveService.suggest()` skips AI unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+8. Gap: spec says AI should run only if no Tier 1/2 candidate exists from E1-E6. Code sorts all providers and runs AI along with the rest when `include_ai=True`; there is no pre-AI non-AI pass or Tier 1/2 short-circuit. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+9. UI modal exists with Candidates, Preview, Local, AI, Civitai, and HF tabs. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:61`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:346`.
+10. AI tab is gated by `avatarAvailable`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:350`, `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+11. HF tab is gated by frontend `HF_ELIGIBLE_KINDS`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+12. Civitai manual tab is a placeholder: "Manual Civitai search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+13. HuggingFace manual tab is a placeholder: "Manual HuggingFace search coming in Phase 4." See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+14. This contradicts the plan's Phase 4 complete claim for provider polish/manual payloads from the UI. Backend manual apply exists; frontend manual search does not.
+
+### Phase 2.5: Preview Enrichment
+
+Status: Partially implemented.
+
+1. `PreviewMetaEvidenceProvider` enriches hints via Civitai hash lookup, then Civitai name search. See `src/store/evidence_providers.py:143`, `src/store/evidence_providers.py:177`, `src/store/evidence_providers.py:246`, `src/store/evidence_providers.py:252`.
+2. It uses `pack_service_getter` and is wired with PackService in `ResolveService._ensure_providers()`. See `src/store/evidence_providers.py:154`, `src/store/resolve_service.py:162`.
+3. It still has a placeholder fallback with `CivitaiSelector(model_id=0)`. See `src/store/evidence_providers.py:198`, `src/store/evidence_providers.py:201`.
+4. That placeholder candidate can rank as Tier 2 with 0.82/0.85 confidence, but apply will fail validation because `model_id=0` is invalid. See `src/store/evidence_providers.py:173`, `src/store/resolve_validation.py:64`.
+5. Gap: no kind filtering in `PreviewMetaEvidenceProvider.gather()`. It iterates all hints and does not check `hint.kind` against `ctx.kind`. See `src/store/evidence_providers.py:169`.
+6. The extractor has `filter_hints_by_kind()`, but `git grep` shows no production use. See `src/utils/preview_meta_extractor.py:584`.
+7. This is a direct spec gap: plan requires kind-aware filtering. See `plans/PLAN-Resolve-Model.md:167`.
+
+### Phase 3: Local Resolve
+
+Status: Implemented and UI-integrated.
+
+1. Backend local browse, recommendation, and import service exists. See `src/store/local_file_service.py:191`, `src/store/local_file_service.py:207`, `src/store/local_file_service.py:268`, `src/store/local_file_service.py:344`.
+2. Path validation requires absolute path, no `..`, resolved path exists, extension allowlist, regular file. See `src/store/local_file_service.py:111`.
+3. Local import hashes, copies into blob store, enriches, and applies resolution. See `src/store/local_file_service.py:377`, `src/store/local_file_service.py:390`, `src/store/local_file_service.py:414`, `src/store/local_file_service.py:428`.
+4. API endpoints exist: browse-local, recommend-local, import-local with background executor and polling. See `src/store/api.py:2485`, `src/store/api.py:2502`, `src/store/api.py:2546`.
+5. UI tab exists and calls recommend/import/poll endpoints. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:150`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+6. Caveat: local import applies via `resolve_service.apply_manual()` if reachable, otherwise falls back to `pack_service.apply_dependency_resolution()`. See `src/store/local_file_service.py:544`.
+7. Caveat: fallback path bypasses validation if `resolve_service` is not available. See `src/store/local_file_service.py:554`.
+8. Caveat: `LocalImportResult` returns `canonical_source`, but `_apply_resolution()` sets canonical only for enrichment results that have it. Filename-only local file has no canonical update tracking. See `src/store/local_file_service.py:450`.
+
+### Phase 4: Provider Polish, Download, Cleanup
+
+Status: Cleanup and validation mostly implemented; manual provider UI and lock/write behavior remain incomplete.
+
+1. Deprecated `BaseModelResolverModal.tsx` is deleted according to diff stat.
+2. `/resolve-base-model` appears removed; current resolve endpoints are `suggest-resolution`, `apply-resolution`, and `apply-manual-resolution`. See `src/store/api.py:2302`, `src/store/api.py:2342`, `src/store/api.py:2370`.
+3. API boundary validates manual strategy fields. See `src/store/api.py:2383`.
+4. `Apply & Download` UI does a compound apply then `/download-asset`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:401`, `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:437`.
+5. NEEDS VERIFICATION: `download-asset` expects `asset_name`; UI sends `depId`. This may be correct if asset name equals dependency id, but the audit did not verify all pack shapes. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:442`.
+6. Major gap: Civitai and HF manual tabs are not implemented. They cannot produce typed payloads from UI. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+7. Major gap: `PackService.apply_dependency_resolution()` explicitly does not touch `pack.lock.json`, contrary to earlier spec language that apply updates pack.json and pack.lock atomically. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+8. `lock_entry` is accepted but unused. See `src/store/pack_service.py:1223`, `src/store/pack_service.py:1237`.
+
+### Phase 5: Deferred Polish
+
+Status: Mostly implemented, but not all to full spec strength.
+
+1. `ResolutionCandidate.base_model` exists and `ResolveService._merge_and_score()` populates it from provider seed. See `src/store/resolve_models.py:90`, `src/store/resolve_service.py:424`.
+2. `AUTO_APPLY_MARGIN` is centralized and config-readable. See `src/store/resolve_config.py:132`, `src/store/resolve_config.py:138`, `src/store/__init__.py:648`.
+3. `compute_sha256_async()` exists. See `src/store/hash_cache.py:159`.
+4. HF enrichment exists as `enrich_by_hf()` and is used in `enrich_file()`. See `src/store/enrichment.py:166`, `src/store/enrichment.py:294`.
+5. HuggingFace client parses LFS `lfs.oid` into SHA256. See `src/clients/huggingface_client.py:36`.
+6. HuggingFace client has `search_models()`. See `src/clients/huggingface_client.py:120`.
+7. Caveat: `LocalFileService._get_hf_client()` looks for `pack_service.hf_client`, but other code references `pack_service.huggingface` for HF access in the plan and evidence provider uses `pack_service.huggingface`. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`. NEEDS VERIFICATION: actual PackService attribute name.
+8. Caveat: MCP `search_huggingface` returns formatted text, not JSON. The plan says text may be OK for LLM, but "structured output" remains unresolved in code. See `plans/PLAN-Resolve-Model.md:1271`, `src/avatar/mcp/store_server.py:1229`.
+9. Caveat: MCP HF search only fetches top-level `tree/main`, not recursive subfolders or model cards. See `src/avatar/mcp/store_server.py:1306`.
+
+### Phase 6: Config, Aliases, Tests, AI Gate
+
+Status: Implemented mechanically, but alias defaults and test realism are weak.
+
+1. `ResolveConfig` exists under `StoreConfig.resolve`. See `src/store/models.py:243`, `src/store/models.py:257`.
+2. `is_ai_enabled()` checks `resolve.enable_ai`. See `src/store/resolve_config.py:153`.
+3. `AIEvidenceProvider.supports()` checks config flag and avatar object. See `src/store/evidence_providers.py:510`.
+4. Alias provider reads `layout.load_config().base_model_aliases`. See `src/store/evidence_providers.py:692`.
+5. Alias provider supports Civitai and HF targets. See `src/store/evidence_providers.py:713`, `src/store/evidence_providers.py:741`.
+6. Caveat: default aliases are placeholder `model_id=0`; if left unchanged they produce invalid candidates or no useful apply path. See `src/store/models.py:281`.
+7. Caveat: AI gate checks avatar object presence backend-side, not a status `available` field. It assumes a non-None avatar service is usable. See `src/store/evidence_providers.py:516`.
+
+## Evidence Providers
+
+### Civitai Hash Evidence
+
+Status: Implemented and wired.
+
+1. `HashEvidenceProvider` reads SHA256 from `dep.lock.sha256`. See `src/store/evidence_providers.py:75`.
+2. It calls `pack_service.civitai.get_model_by_hash(sha256)`. See `src/store/evidence_providers.py:88`.
+3. It emits a `CIVITAI_FILE` candidate when `model_id` and `version_id` exist. See `src/store/evidence_providers.py:100`.
+4. It assigns `hash_match` evidence with confidence 0.95. See `src/store/evidence_providers.py:120`.
+5. Gap: it does not create `canonical_source`. See `src/store/evidence_providers.py:106`.
+6. Gap: it only reads hash from `dep.lock`; it does not hash local files as part of suggest. See `src/store/evidence_providers.py:75`.
+
+### HuggingFace LFS OID Evidence
+
+Status: Partial verification only, not discovery/reverse lookup.
+
+1. HF LFS OID parsing exists in `HFFileInfo.from_api_response()`. See `src/clients/huggingface_client.py:36`.
+2. `HashEvidenceProvider` calls `_hf_hash_lookup()` only when kind config says `hf_hash_lookup=True`. See `src/store/evidence_providers.py:133`.
+3. Only checkpoints have `hf_hash_lookup=True`; VAE/controlnet are HF-eligible but hash lookup false. See `src/store/resolve_config.py:80`, `src/store/resolve_config.py:93`, `src/store/resolve_config.py:99`.
+4. `_hf_hash_lookup()` requires dependency selector already has HF repo and filename. See `src/store/evidence_providers.py:624`, `src/store/evidence_providers.py:629`.
+5. Therefore this is not a general "find model by SHA256 on HF"; it verifies a known HF candidate's file list. This matches HF API limitations, but it is weaker than "HF hash lookup" wording.
+6. `find_model_by_hash` MCP tool is Civitai-only. See `src/avatar/mcp/store_server.py:1143`.
+
+### Local Hash Evidence
+
+Status: Implemented in local import flow, not in resolver evidence chain.
+
+1. `HashCache` can cache SHA256 by file path. See `src/store/hash_cache.py:36`.
+2. `LocalFileService.recommend()` can compare cached hash with dependency expected hash. See `src/store/local_file_service.py:306`.
+3. `LocalFileService.import_file()` hashes selected file and uses hash cache. See `src/store/local_file_service.py:377`.
+4. `enrich_file()` then tries Civitai hash, Civitai name, HF name, filename fallback. See `src/store/enrichment.py:271`.
+5. There is no `LocalHashEvidenceProvider` in `ResolveService._ensure_providers()`. See `src/store/resolve_service.py:160`.
+6. So local hash is an import/local-tab feature, not part of normal `suggest_resolution()`.
+
+### AI Evidence
+
+Status: Wired, but broad and prompt-dependent.
+
+1. `AIEvidenceProvider` is registered in the provider chain. See `src/store/resolve_service.py:166`.
+2. It is skipped unless `include_ai=True`. See `src/store/resolve_service.py:226`.
+3. It builds a text input with pack name/type/base_model/description/tags, dependency kind/hint/expose filename, and preview hints. See `src/store/evidence_providers.py:774`.
+4. It calls `avatar.execute_task("dependency_resolution", input_text)`. See `src/store/evidence_providers.py:526`.
+5. It maps returned candidates into Civitai/HF selector seeds. See `src/store/evidence_providers.py:848`, `src/store/evidence_providers.py:874`.
+6. Fallback when AI is off: provider is skipped; E1-E6 still run. See `src/store/evidence_providers.py:510`, `src/store/resolve_service.py:226`.
+7. Gap: AI provider output does not populate `canonical_source`. See `src/store/evidence_providers.py:861`, `src/store/evidence_providers.py:881`.
+8. Gap: AI input says "EXISTING EVIDENCE (none)" unless no preview hints; it does not pass already-collected E1-E6 candidates/evidence into the AI call. See `src/store/evidence_providers.py:821`.
+
+## UI Integration
+
+### DependencyResolverModal
+
+Status: Integrated as the primary modal.
+
+1. `PackDetailPage` keeps resolver state and opens modal per asset. See `apps/web/src/components/modules/PackDetailPage.tsx:126`, `apps/web/src/components/modules/PackDetailPage.tsx:132`.
+2. Opening the modal eagerly calls `suggestResolution()` without AI. See `apps/web/src/components/modules/PackDetailPage.tsx:141`.
+3. Modal renders from candidates held in page state. See `apps/web/src/components/modules/PackDetailPage.tsx:529`.
+4. Candidate cards show confidence label, provider, base model, compatibility warning, evidence groups, and raw score when expanded. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:193`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:235`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:279`.
+5. Apply and Apply & Download buttons are wired. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:616`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:631`.
+
+### Civitai Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:351`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+
+### HuggingFace Tab
+
+Status: Mocked/placeholder.
+
+1. The tab is visible only for frontend HF-eligible kinds. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:352`.
+2. It contains only placeholder copy and no search input/API call/manual apply. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:591`.
+
+### Local Resolve Tab
+
+Status: Functional.
+
+1. It browses/recommends a directory using `/recommend-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:160`.
+2. It imports a selected file using `/import-local`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:206`.
+3. It polls `/api/store/imports/{import_id}`. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:235`.
+4. It displays browse/importing/success/error states. See `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:297`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:368`, `apps/web/src/components/modules/pack-detail/modals/LocalResolveTab.tsx:441`.
+
+### Apply
+
+Status: Wired, but cache binding is incomplete.
+
+1. Frontend passes `dep_id`, `candidate_id`, and `request_id`. See `apps/web/src/components/modules/pack-detail/hooks/usePackData.ts:369`.
+2. Backend applies by candidate cache and delegates to PackService. See `src/store/resolve_service.py:275`, `src/store/resolve_service.py:323`.
+3. Gap: candidate cache stores only request fingerprint and candidates, not `pack_name` or `dep_id`; if `request_id` is omitted, `apply()` searches all cached requests by candidate id. See `src/store/resolve_service.py:75`, `src/store/resolve_service.py:466`.
+4. UUID collision risk is low, but missing pack/dep binding is a correctness gap already noted in the plan as deferred. See `plans/PLAN-Resolve-Model.md:888`.
+
+### AI Gate
+
+Status: Implemented frontend and backend, with different semantics.
+
+1. Frontend hides AI tab unless avatar status has `available=true`. See `apps/web/src/components/modules/pack-detail/hooks/useAvatarAvailable.ts:19`.
+2. Backend hides AI provider when config `resolve.enable_ai=false` or avatar getter returns None. See `src/store/evidence_providers.py:510`.
+3. Backend does not check avatar runtime status `available`; it assumes non-None service can run. NEEDS VERIFICATION.
+
+## Preview Analysis
+
+Status: UI tab and backend extractor are wired; it is partly display-only.
+
+1. Backend endpoint `/preview-analysis` analyzes preview sidecars and PNG text. See `src/store/api.py:2275`.
+2. Frontend hook fetches `/api/packs/{pack}/preview-analysis`. See `apps/web/src/components/modules/pack-detail/hooks/usePreviewAnalysis.ts:10`.
+3. Preview tab displays thumbnails, model references, hashes, weights, and generation params. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:64`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:116`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:182`.
+4. "Use" does not create a new candidate or manual apply; it only tries to find an already-existing candidate in `candidates` and select it. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:277`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. If no matching candidate exists, UI tells user to run suggestion first. See `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:309`.
+6. Therefore "Preview Analysis tab + hint enrichment" is wired for display and candidate selection, but not a full standalone resolve path from hint to apply.
+7. In backend suggest, preview hints are only available if `_post_import_resolve()` passes overrides or if a dependency has `_preview_hints`. See `src/store/resolve_service.py:201`.
+8. The public suggest endpoint does not itself run preview analysis or pass preview hints. See `src/store/api.py:2302`, `src/store/api.py:2322`.
+9. The tab fetches preview analysis separately, but those hints are not fed back into `onSuggest()`. See `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:507`.
+
+## AI Integration
+
+Status: Real task and service wiring exist; live provider claims need verification.
+
+1. `DependencyResolutionTask` is registered in default registry per plan; registry change present in diff stat, not deeply audited here. NEEDS VERIFICATION on exact registry line.
+2. Task prompt is skill-file based; `build_system_prompt()` returns skill content only. See `src/avatar/tasks/dependency_resolution.py:53`.
+3. Task parses and validates AI output with provider-specific required fields. See `src/avatar/tasks/dependency_resolution.py:63`, `src/avatar/tasks/dependency_resolution.py:127`.
+4. Task has no fallback; E1-E6 are expected to provide non-AI coverage. See `src/avatar/tasks/dependency_resolution.py:164`.
+5. `AvatarTaskService` starts `AvatarEngine` with MCP servers for `needs_mcp` tasks. See `src/avatar/task_service.py:336`.
+6. MCP includes `search_civitai`, `analyze_civitai_model`, `find_model_by_hash`, `suggest_asset_sources`, and `search_huggingface`. See `src/avatar/mcp/store_server.py:1428`, `src/avatar/mcp/store_server.py:1434`, `src/avatar/mcp/store_server.py:1486`, `src/avatar/mcp/store_server.py:1492`, `src/avatar/mcp/store_server.py:1498`.
+7. `find_model_by_hash` is Civitai-only despite AI prompt comments mentioning HF/hash capability. See `src/avatar/mcp/store_server.py:1143`.
+8. `search_huggingface` performs real HTTP through `requests`, not through the shared HF client/session/token. See `src/avatar/mcp/store_server.py:1239`.
+9. NEEDS VERIFICATION: whether avatar-engine permissions and MCP server config are actually present in local runtime config, not just `config/avatar.yaml.example`.
+
+## Tests
+
+### Unit Tests
+
+Status: Broad coverage, often mocked.
+
+1. Unit tests exist for models, config, validation, scoring, hash cache, providers, resolve service, preview extractor, local file service, enrichment, and AI task per diff stat.
+2. `tests/unit/store/test_evidence_providers.py` heavily uses `MagicMock`. See grep output: many `MagicMock` references, e.g. `tests/unit/store/test_evidence_providers.py:32`.
+3. This is fine for unit mechanics but does not prove real Civitai/HF data shape compatibility.
+4. Some tests do use Pydantic models in other files per plan, but the most provider-critical unit file is mock-heavy. NEEDS VERIFICATION against real clients.
+
+### Integration Tests
+
+Status: Present but partly fake.
+
+1. `test_resolve_integration.py` uses real `ResolveService` but mock PackService/Layout and fake providers. See `tests/integration/test_resolve_integration.py:1`, `tests/integration/test_resolve_integration.py:61`, `tests/integration/test_resolve_integration.py:77`.
+2. `test_resolve_smoke.py` creates a real `Store(tmp_path)` but still uses MagicMock packs/deps for several scenarios. See `tests/integration/test_resolve_smoke.py:20`, `tests/integration/test_resolve_smoke.py:37`.
+3. AI integration file claims real components but uses `MagicMock` for packs/deps and avatar. See `tests/integration/test_ai_resolve_integration.py:42`, grep lines.
+4. These tests validate orchestration, not full end-to-end provider correctness.
+
+### Smoke Tests
+
+Status: Present, low-to-medium realism.
+
+1. Store smoke checks service wiring and migration behavior. See `tests/integration/test_resolve_smoke.py:104`.
+2. It does not perform a real Civitai import with actual downloaded sidecars in normal CI. NEEDS VERIFICATION.
+
+### E2E Tests
+
+Status: Two categories: mocked Playwright and standalone live scripts.
+
+1. Playwright resolve E2E is explicitly offline and mocked. See `apps/web/e2e/resolve-dependency.spec.ts:1`.
+2. Helpers "mock the backend completely." See `apps/web/e2e/helpers/resolve.helpers.ts:245`.
+3. These tests cover UI flows but not backend resolver correctness.
+4. `tests/e2e_resolve_real.py` is a standalone script for live providers, not a pytest test by default. See `tests/e2e_resolve_real.py:10`, `tests/e2e_resolve_real.py:331`.
+5. It exits 0 if there are no provider errors, even if correctness failures occur; `sys.exit(0 if err_count == 0 else 1)` ignores `fail_count`. See `tests/e2e_resolve_real.py:412`.
+6. That makes it unsuitable as a hard correctness gate without modification.
+
+## Spec vs Code Gaps
+
+1. API shape mismatch: spec says `/dependencies/{dep_id}/suggest` and `/dependencies/{dep_id}/apply`; code uses pack-level `/suggest-resolution`, `/apply-resolution`, `/apply-manual-resolution`. See `plans/PLAN-Resolve-Model.md:180`, `src/store/api.py:2302`.
+2. `analyze_previews` option is defined but not exposed in API or used in service. See `src/store/resolve_models.py:135`, `src/store/api.py:2247`, `src/store/resolve_service.py:201`.
+3. Preview provider does not filter hints by target kind. See `plans/PLAN-Resolve-Model.md:167`, `src/store/evidence_providers.py:169`.
+4. Preview tab "Use this model" does not create/apply a candidate; it only selects a matching existing candidate. See `plans/PLAN-Resolve-Model.md:445`, `apps/web/src/components/modules/pack-detail/modals/PreviewAnalysisTab.tsx:304`.
+5. Manual Civitai and HF search tabs are placeholders. See `plans/PLAN-Resolve-Model.md:459`, `apps/web/src/components/modules/pack-detail/modals/DependencyResolverModal.tsx:572`.
+6. AI execution policy differs: code runs AI whenever `include_ai=True`; spec says only if no Tier 1/2 candidate. See `plans/PLAN-Resolve-Model.md:396`, `src/store/resolve_service.py:226`.
+7. Candidate cache lacks pack/dep binding. See `plans/PLAN-Resolve-Model.md:888`, `src/store/resolve_service.py:75`.
+8. Apply does not update `pack.lock.json`; PackService says it intentionally does not touch lock. See `plans/PLAN-Resolve-Model.md:186`, `src/store/pack_service.py:1228`.
+9. `CanonicalSource` model exists but most evidence providers do not populate it. See `src/store/models.py:381`, `src/store/evidence_providers.py:106`, `src/store/evidence_providers.py:861`.
+10. HF search tool is not full tree/model-card inspection and not structured JSON. See `plans/PLAN-Resolve-Model.md:803`, `src/avatar/mcp/store_server.py:1229`.
+11. HF hash lookup is verification of an existing selector, not general HF reverse lookup. See `src/store/evidence_providers.py:618`.
+12. `HashEvidenceProvider.supports()` returns true for everything and only no-ops later; eligibility is not expressed at support level. See `src/store/evidence_providers.py:63`.
+13. `FileMetaEvidenceProvider` still emits `model_id=0` placeholder Civitai candidates. See `src/store/evidence_providers.py:384`.
+14. Default alias config also uses placeholder zero IDs. See `src/store/models.py:281`.
+
+## Refactor Candidates
+
+1. Consolidate Civitai name/hash enrichment. `PreviewMetaEvidenceProvider` duplicates logic that now exists in `src/store/enrichment.py`. See `src/store/evidence_providers.py:230`, `src/store/enrichment.py:42`.
+2. Make provider outputs either applyable or explicitly non-applyable. Placeholder `model_id=0` candidates should not appear as normal candidates with high confidence. See `src/store/evidence_providers.py:198`.
+3. Bind candidate cache entries to `pack_name` and `dep_id`; remove all-cache candidate lookup unless there is a strong use case. See `src/store/resolve_service.py:107`, `src/store/resolve_service.py:466`.
+4. Split AI provider orchestration into two passes: deterministic E1-E6 first, optional AI only if needed. See `src/store/resolve_service.py:216`.
+5. Add kind filtering at resolver input boundary, not only extractor helper. See `src/utils/preview_meta_extractor.py:584`.
+6. Create a shared HF search client/path for MCP, enrichment, and evidence rather than direct `requests` in MCP plus `HuggingFaceClient` elsewhere. See `src/avatar/mcp/store_server.py:1239`, `src/clients/huggingface_client.py:120`.
+7. Decide whether apply should write lock data. Current PackService doc contradicts the earlier spec. See `src/store/pack_service.py:1228`.
+8. Extract frontend provider manual search tabs into real components or remove placeholder tabs until implemented.
+9. Clarify `pack_service.hf_client` vs `pack_service.huggingface` naming. See `src/store/local_file_service.py:473`, `src/store/evidence_providers.py:638`.
+10. Turn standalone live E2E scripts into pytest tests with explicit opt-in markers and fail on incorrect top match, not only provider errors. See `tests/e2e_resolve_real.py:412`.
+
+## Open Questions for Owner
+
+1. Is the local `v0.11.0` plan the source of truth, or should the audit compare against an older v0.7.1 from the missing machine?
+2. Should `apply_resolution()` update `pack.lock.json`, or is the current "pack.json only; resolve_pack handles lock" behavior intentional?
+3. Should Civitai/HF manual tabs be implemented before Release 1, point 1, or are placeholders acceptable?
+4. Should preview analysis hints feed back into `suggestResolution()` from the UI, or is preview analysis only informational after import?
+5. Are placeholder candidates (`model_id=0`) acceptable in UI suggestions, or should non-applyable candidates be hidden/marked unresolvable?
+6. What is the authoritative HF client attribute on PackService: `hf_client` or `huggingface`?
+7. Should AI run alongside deterministic providers when requested, or only after deterministic providers fail to produce Tier 1/2?
+8. Should canonical source be required for all remote Civitai/HF candidates before apply?
+9. Is HF reverse hash lookup explicitly out of scope due to HF API limitations, with only known-repo LFS verification required?
+10. Which test command is the release gate: full pytest, Playwright E2E, live AI scripts, or a curated subset?
+11. Are live provider results from `tests/e2e_resolve_real.py` stored anywhere reproducible, or only printed to terminal?
+12. Should local import fallback bypass validation if `resolve_service` is unavailable, or should that path hard-fail?
+
+## Release Risk Assessment
+
+1. Backend core is real enough for continued integration work.
+2. The UX is not feature-complete for manual Civitai/HF resolution despite tab presence.
+3. Preview analysis is useful, but not fully integrated as a first-class resolve source in the UI.
+4. AI integration is plausible, but relies on runtime avatar/MCP configuration and prompt behavior; local code alone does not prove live reliability.
+5. The largest correctness risk is presenting high-confidence candidates that cannot apply because they contain placeholder IDs or lack canonical/update data.
+6. The largest spec compliance risk is that "Suggest / Apply is the single write path updating pack + lock" is not what PackService currently does.

tokens used
204,315
Wrote the full audit here: [plans/audit-resolve-model-redesign-local.md](/home/box/git/github/synapse/plans/audit-resolve-model-redesign-local.md)

It is 359 lines and includes branch-local refs, phase coverage, evidence provider wiring, UI/mock status, preview/AI/test assessment, spec gaps, refactor candidates, and owner questions.

Main findings:
- Core backend is real and wired, but not fully spec-aligned.
- Civitai/HF manual tabs are placeholders.
- Preview analysis is display/select-only in UI, not a standalone apply path.
- Preview hints are not kind-filtered in the resolver chain.
- HF hash support is known-repo LFS verification, not reverse lookup.
- Most remote candidates do not populate `canonical_source`.
- `apply_dependency_resolution()` updates `pack.json` only, not `pack.lock.json`.
- Frontend E2E is fully mocked; live AI E2E is a standalone script and does not fail on incorrect matches.

I did not run tests. I also left existing unrelated untracked paths untouched (`plans/PLAN-Release-1-Roadmap.md`, `plans/audits/`).
