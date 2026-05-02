# PLAN: Synapse — Release 1 Finishing Roadmap

**Verze:** v0.4.0 (DRAFT)
**Status:** 🟡 ROADMAP — bodový přehled bodů **k dotažení**, AUDIT HOTOV, čeká na rozhodnutí
**Vytvořeno:** 2026-05-02
**Autor:** raven2cz + Claude Opus 4.7

> **Duální audit (Claude + Codex GPT-5.5 high effort) přes všech 6 bodů hotov 2026-05-02.**
> Konsolidované nálezy: **`plans/audits/CONSOLIDATED-FINDINGS.md`** — per bod
> "kde jsme · co chybí · otázky pro uživatele · napojení do aplikace".
> Raw codex výstupy: `plans/audits/codex-audit-{1..6}-*.md`.
>
> **Domain model audit (2026-05-02):** **`plans/audits/DOMAIN-AUDIT.md`** (Claude Opus 4.7) +
> **`plans/audits/codex-domain-audit.md`** (Codex GPT-5.5 high) — duální audit
> `src/store/models.py` a souvisejících služeb. Identifikuje konkrétní bugy (api.py `pack_path()`
> 8× neexistující metoda, cli.py:527 `pack_entry.enabled` neexistuje, StatusReport.shadowed=[]
> hardcoded, placeholder zero IDs v base_model_aliases, ConflictMode nikdy nečten,
> pack_dependencies nikdy expandovány do view, version_constraint nikdy enforcovaný, schema
> versioning bez migration kódu) a 10+ open questions pro vlastníka před rozšiřováním modelů.
> **Číst PŘED jakýmkoliv refactorem domain modelů!**
>
> **DOMAIN-AUDIT Section 14b** obsahuje detailní decision-session otázky v češtině s volbami
> A/B/C a konkrétními příklady — vlastník odpovídá zítra (2026-05-03) **na resolve-redesign
> branchi** (některé findings tam můžou být už vyřešené, ověřit před decision session).

---

## 🛠️ Stabilizační flow (2026-05-02 → 2026-05-03)

**Cíl:** Před implementací bodů Release 1 vyřešit všechny audit findings + zodpovědět open
questions na **stabilization branch** `stabilization/release-1`. Žádné direct commity do
main během stabilizace.

**Zítra (2026-05-03) postup:**

1. **Přepnout na `feat/resolve-model-redesign`** — zkontrolovat každý DOMAIN-AUDIT finding,
   jestli už není vyřešený. Škrtnout/aktualizovat, co je hotové.
2. **Decision session** — projít DOMAIN-AUDIT Section 14b (6 hlavních + 3 sub otázky),
   vlastník vyplní tabulku odpovědí.
3. **Vytvořit `plans/PLAN-Stabilization-Release-1.md`** — konkrétní fáze podle odpovědí.
4. **Audit toho plánu** Claudem + Codexem (multi-model review podle MEMORY.md pravidla #8).
5. **Implementace na `stabilization/release-1` branchi:**
   - Mechanické fixy (H1 `pack_path`, H2 `pack_entry.enabled`, M9 error swallowing).
   - Decision-driven refactory podle vlastníkových odpovědí.
   - Po každé fázi: 3-model review + všechny testy.
6. **User testing** — vlastník ručně otestuje na stabilization branch.
7. **Merge `stabilization/release-1` → `main`** až po user OK.

**Pak teprve:** začít Release 1 dílčí body (Resolve, Custom, Workflow, Install, Profiles, AI).

---

## ⚠️ Scope tohoto dokumentu (čti první)

**Release 1 obsahuje mnohonásobně více než tento roadmap.** Většina featur (Inventory,
Backup, Updates, Pack Edit, NSFW filter, i18n, Avatar Engine integrace, Browse, Packs,
Downloads, atd.) je **už hotová** — a tento dokument je o **nich nemluví**.

Tato roadmapa zachycuje **JEN body, které ještě potřebují dotažení / refactor / rozšíření**
před Release 1. Většinou jde o existující systémy, které vyžadují:
- doplnění chybějících kusů,
- refactor / cleanup,
- rozšíření, aby pokrývaly všechny use-cases.

---

## 🛑 Zákaz paralelních implementací (CRITICAL)

**NIKDY nevytvářet paralelní/separátní implementaci**, když existuje zavedený systém!
Toto je opakované pravidlo z `MEMORY.md` — Claude má tendenci to porušovat, protože si
existujícího systému nevšimne.

Před auditem / návrhem JAKÉHOKOLIV bodu níže:
1. **PROHLEDAT codebase** — existuje už služba/komponenta pro tento účel?
2. **NAPOJIT SE** na existující systém, **ne vytvářet nový**
3. **Zeptat se uživatele**, pokud si nejsi jistý

**Konkrétní příklady z minulosti:**
- App connector ≠ nový systém. **Jsou to Profiles** (`profile_service.py` + `view_builder.py`
  + `ProfilesPage.tsx`). Bod 5 = rozšíření Profiles, ne tvorba něčeho nového.
- Download flow používá `_active_downloads` + DownloadsPage polling, **ne** `BackgroundTasks`.

---

## 🤝 Pravidla pro audit, návrh implementace a review

Žádný bod níže se NEDĚLÁ Claudem sólo. Vždy multi-model:

### Audit (vždy duálně)
- **Claude Opus 4.7** — primární audit (čte kód, mapuje na spec)
- **Codex GPT-5.5 high effort** — nezávislý druhý audit
  ```bash
  codex exec --model gpt-5.5 --reasoning-effort high \
    "Audit these files for spec/implementation/integration gaps: <files>"
  ```
- Výsledky obou se **konfrontují**, sjednocené nálezy → do dílčího plánu

### Návrh implementace (vždy duálně)
- **Claude** primární návrh
- **Codex GPT-5.5 high effort** nezávislý návrh
- Konfrontace, sjednocení, výsledný design do plánu

### Review po fázi (vždy trojitě)
- **Claude** — projde každý změněný soubor
- **Codex GPT-5.5 high effort** — `codex review --commit <SHA>` nebo explicit files
- **Gemini 3.1** — `gemini -p "Review..." --yolo`
- **Sonnet 4.6 navíc** — additional review pass
  ```bash
  # přes avatar-engine nebo přímý CLI volání
  ```
- Všechny nálezy se validují, opravy commitnou před další fází.

**NIKDY nepřeskakovat tato pravidla.** Pokud Codex / Gemini / Sonnet není z nějakého důvodu
dostupný, ohlásit to uživateli a počkat na rozhodnutí — neimplementovat dál.

---

## 📋 Audit kontrolní seznam (pro každý bod níže)

Před prací na každém bodu **MUSÍ proběhnout audit**:

1. **Specifikace** — je hlavní design dotažený? Pokrývá všechny use-cases?
2. **Implementace** — odpovídá kódu specifikaci? Jsou v ní díry?
3. **Integrace** — je feature napojená na zbytek systému (UI, API, store, downloads,
   inventory, updates, AI)? Nebo izolovaný kus, který se nepoužívá?
4. **Testy** — existuje pyramida (unit + integration + smoke/E2E)? Pokrývá real-world flow?
5. **UX** — funguje to z pohledu uživatele end-to-end?

Teprve po auditu lze říct, **co** chybí, **proč** to chybí a **jak** to dotáhnout.

---

## 🎯 Cíl Release 1

Synapse jako **použitelný pack-first model manager** pro běžného uživatele
generativních UI (ComfyUI, Forge/Forge-Neo, A1111, SD.Next):

- Importuju packy z Civitai/HuggingFace nebo si vytvořím vlastní
- Vidím a spravuji modely v Inventory + Backupech
- Připojím Synapse k mým UI aplikacím a modely jsou tam dostupné
- Pro každý pack mám/vytvořím funkční workflow
- Dependencies se vyřeší (přesný model pro danou závislost)
- AI mi pomůže s komplexními úlohami (volitelně)

---

## 📋 Hlavní body Release 1

### 1. 🔄 `feat/resolve-model-redesign` — dokončit / refactor

**Co to je:** Redesign hledání přesných modelů pro danou závislost (Civitai / HuggingFace
/ Local Resolve, AI scoring, evidence providers, preview analysis).

**Kde:** Branch `feat/resolve-model-redesign` (26 commitů, +22k řádků). Hlavní spec
`plans/PLAN-Resolve-Model.md` (v0.7.1, na branchi).

**Aktuální blokátor:** Poslední commit chybí — je na druhém stroji. Práce **pokračuje doma**,
ne v této session.

**Po sloučení s druhým strojem audit:**
- Je celý dependency-resolve flow napojený do UI a používaný? (DependencyResolverModal,
  taby Civitai/HF/Local, Apply, AI gate)
- Jsou všechny evidence providery skutečně volané? (Civitai hash, HF LFS OID, local hash, AI)
- Funguje preview analysis tab + hint enrichment v reálu, nejen v testech?
- Co E2E Playwright testy reálně pokrývají vs. co simulují?
- Co chybí oproti specifikaci v `PLAN-Resolve-Model.md`?

**Akce:** Po pull z druhého stroje → `verify.sh` → audit dle bodů výše →
revize/doplnění `PLAN-Resolve-Model.md` → merge do main NEBO refactor.

---

### 2. 🎨 Custom Pack — hluboký audit + integrace

**Co to je:** Pack vytvořený lokálně od nuly (`PackCategory.CUSTOM`). Plně editovatelný,
uživatel přidává dependencies/parametry/workflow ručně. Pluginový systém s `CustomPlugin`.

**Kde:**
- Hlavní spec: `plans/PLAN-Pack-Edit.md` (sekce Pack Types + plugin systém)
- Backend: `PackCategory` enum v `src/store/models.py`
- Frontend: `apps/web/src/components/modules/pack-detail/plugins/CustomPlugin.tsx`

**Audit musí pokrýt:**
- **Specifikace:** Je v `PLAN-Pack-Edit.md` opravdu kompletní use-case od *vytvoření prázdného
  packu* až po *export/použití*? Nechybí kroky?
- **Vytvoření packu:** Existuje UI pro "Create Custom Pack" tlačítko / wizard? Funguje?
- **Editace:** Lze přidat/upravit všechny části (name, description, dependencies, params,
  workflows, gallery)? Nebo jen některé?
- **Dependencies:** Lze přidat dependency na lokální blob, na Civitai model, na HF model,
  na jiný pack (`pack_dependencies`)? Funguje resolving?
- **Workflow:** Lze pro custom pack vygenerovat / importovat workflow? (vazba na bod 4)
- **Persistence:** Ukládá se vše do `pack.json`? Backup? Inventory?
- **Export/Import:** Lze custom pack předat jinému uživateli / na jiný stroj?
- **Integrace s App Connectorem:** Když připojím ComfyUI, dostane se custom pack do modelové
  hierarchie? (vazba na bod 5)

**Výstup auditu:** Dokument s nálezy, prioritizací a požadavky → revize `PLAN-Pack-Edit.md`
nebo nový `PLAN-Custom-Pack-Completion.md`.

---

### 3. 🔧 Install Pack — kompletně dodělat

**Co to je:** Pack pro instalaci a správu UI prostředí (ComfyUI, Forge, A1111).
Script-based (bash/python), commands install/start/stop/verify/update.

**Kde:**
- Hlavní spec: `plans/PLAN-Install-Packs.md`
- Backend: `PackCategory.INSTALL` enum existuje
- Frontend: `InstallPlugin.tsx` (označený jako PROTOTYPE)
- Status: V `PLAN-Pack-Edit.md` označeno jako "FUTURE"

**Audit + dospecifikování musí pokrýt:**
- **Bezpečnost:** Spouštět script z packu znamená spustit cizí kód. Sandbox? Whitelist
  commandů? Confirmation dialog? **(CRITICAL — bez vyřešení nelze releasnout)**
- **Lifecycle:** install → start → stop → verify → update — jak je každý definován?
  Co se stane při selhání?
- **Console viewer:** Streamování stdout/stderr do UI v reálném čase
- **Environment status:** Jak Synapse pozná, že ComfyUI běží? (port check? PID file? API ping?)
- **Vazba na App Connector (bod 5):** Install pack vytvoří instalaci → App Connector ji
  pak používá pro symlinks. Jak se to propojí?
- **Vazba na update systém:** Update install packu = update UI prostředí. Konflikt s update
  modelů? Verzování?
- **Templates:** ComfyUI/Forge/A1111/SD.Next — připravené šablony, nebo uživatelské?

**Výstup auditu:** Revize `PLAN-Install-Packs.md` s konkrétními fázemi implementace,
bezpečnostním modelem a integračními body.

---

### 4. 🎬 Workflow Wizard — tvorba a import workflow

**Co to je:**
- **Tvorba:** Pro daný pack vygenerovat **default workflow** (ComfyUI / A1111 / Forge).
- **Import:** Importovat existující ComfyUI workflow (.json), který typicky vyžaduje
  **více packů / modelů** → import pak spojí s custom packem (vazba na bod 2).

**Kde:**
- Hlavní spec: `plans/PLAN-Workflow-Wizard.md`
- Aktuální stav v PLAN: má fáze 1+, podporované UI (ComfyUI/Forge/A1111/SD.Next)

**Audit musí pokrýt:**
- **Tvorba — generator interface:**
  - Kolik UI je reálně podporováno? Co jen v plánu?
  - Šablony existují? Jsou kompletní?
  - Vazba parametrů packu (`PackParametersSection`) → workflow nodes
- **Import:**
  - Parser ComfyUI workflow JSON → identifikace všech závislostí (modely, LoRA, VAE, custom nodes)
  - **Cross-link na resolve (bod 1):** identifikované závislosti se musí umět vyřešit
  - **Cross-link na custom pack (bod 2):** import vytvoří custom pack obsahující workflow + deps?
  - Detekce missing custom_nodes (Manager API?)
- **Editor:** Po importu lze workflow editovat? Nebo jen použít as-is?
- **Storage:** Kde se workflow ukládá? `pack.json`, samostatný `.json`, oboje?
- **Vazba na App Connector (bod 5):** Workflow musí umět najít modely v cílovém UI

**Výstup:** Revize `PLAN-Workflow-Wizard.md`, návrh integrace s Custom Pack flow.

---

### 5. 🔌 Profiles — rozšíření napojení na ComfyUI / A1111 / Forge / SD.Next 🔴 CRITICAL

> **POZOR:** Toto NENÍ nový "App Connector". Napojení na aplikace **už existuje**
> jako **Profiles** (`profile_service.py`, `view_builder.py`, `ProfilesPage.tsx`).
> Bod 5 = **rozšířit existující Profiles**, ne vytvářet paralelní systém!

**Co Profiles dělají dnes:**
- `global` profile + `work__<Pack>` work profiles
- `use <pack>` / `back` workflow (push/pop stack)
- Stavba views přes `ViewBuilder` (pravděpodobně právě symlinks per-app)
- Integrace s `BackupService` (auto-restore on use)
- API endpointy + CLI subcommand `synapse profiles`

**Co od Profiles chceme pro Release 1 (rozšíření):**
- **Single source of truth** pro modely napříč ComfyUI / A1111 / Forge / SD.Next
- Per-app handling — každé UI má jiné adresáře a jinou strukturu
- Updates modelů → views se přepojí automaticky
- Možnost poskytnout modely **třetím stranám** (sdílení mezi UIs)
- Zjednodušení používání modelů

**Audit musí pokrýt (na existujícím Profiles systému):**
- **Detekce instalací aplikací:** Pozná Profiles dnes ComfyUI / A1111 / Forge / SD.Next?
  Jak? Auto? Manuálně? Více instalací?
- **View building:** Co `view_builder.py` reálně dělá? Jaké struktury vytváří per-UI?
  Jaké UI dnes podporuje?
- **Mapping per-app — co existuje, co chybí:**
  - ComfyUI: `models/checkpoints/`, `models/loras/`, `models/vae/`, `custom_nodes/`...
  - A1111: `models/Stable-diffusion/`, `models/Lora/`, `models/VAE/`, `embeddings/`...
  - Forge / Forge-Neo: které mapping jsou hotové?
  - SD.Next: jak vypadá adresářová struktura, je podporovaná?
- **Symlink lifecycle:** Vytvoření, údržba, cleanup orphans, reaction na rename/delete blobu
- **Konflikty:** Stejný model už existuje v UI z předchozí instalace → jak to Profiles dnes řeší?
- **Updates:** Po update modelu (nový blob) → views se přepojí? Cross-link s `PLAN-Updates.md`
- **Třetí strany:** Co to konkrétně znamená pro Profiles? Export? Read-only API?
- **Reverse import:** Pokud má uživatel model už v UI, jde ho zaregistrovat zpět do Synapse
  přes Profiles? (Vazba na Local Resolve z bodu 1)
- **UI rozšíření:** Co `ProfilesPage.tsx` zobrazuje dnes? Co potřebujeme dodat?

**Výstup auditu:** Revize/rozšíření existujícího Profiles plánu (najít, kde je dokumentován)
NEBO nový `plans/PLAN-Profiles-Extensions.md` — **nikdy ne paralelní `PLAN-App-Connector.md`!**

**PRIORITA:** **CRITICAL** — bez funkčního Profiles propojení je Synapse jen "skladiště
souborů", ne manager.

---

### 6. 🤖 AI Integration — pomoc se složitými úkoly (volitelné)

**Co to je:** Vestavěná AI (avatar-engine) pomáhá řešit:
- Komplexní workflow úlohy (návrh, oprava, optimalizace)
- Doporučení modelů pro daný účel
- Resolving nejednoznačných závislostí
- Vysvětlení parametrů, generování popisů
- atd.

**Princip:** AI je **volitelná**. Když není dostupná → některé features omezené nebo
nedostupné, **uživatel jasně vidí, že to vyžaduje aktivovanou AI**.

**Kde:**
- Spec: `plans/PLAN-AI-Services.md`
- Avatar plány: `PLAN-Avatar-Engine-Integration.md`, `PLAN-Avatar-TaskService.md`,
  `PLAN-Avatar-v1.2-Dynamic-Models.md`, `PLAN-Avatar-Engine-Bugfixes.md`
- Backend: `src/avatar/` (config, routes, skills, task_service, mcp/store_server.py — 21 tools)

**Audit musí pokrýt:**
- **Inventář use-cases:** Pro jaké konkrétní úlohy v Synapse je AI dnes integrovaná?
  (resolve dependency, parameter extraction, model tagging, ...)
- **Graceful degradation:** Když avatar-engine není dostupný / běží:
  - UI to **zobrazuje uživateli**? Nebo selže potichu?
  - Existují fallbacky (rule-based)? Pro každou AI funkci?
  - Jasné UX označení "this needs AI" na vypnutých featurech
- **Cross-link s ostatními body:**
  - Bod 1 (resolve): AI scoring evidence — funguje? S fallback?
  - Bod 4 (workflow): AI generování / oprava workflow — existuje?
  - Bod 2 (custom pack): AI suggesty pro dependencies / parametry?
  - Bod 5 (app connector): AI pro mapping nestandardních modelů?
- **Konfigurace:** Uživatel volí provider/model/priority — kde, jak?
- **MCP tools (21 nástrojů):** Které jsou relevantní pro Release 1, které jsou nadbytečné?

**Výstup auditu:** Mapa "feature × s AI / bez AI", revize `PLAN-AI-Services.md`,
seznam UI změn pro graceful degradation.

---

## 🗂️ Mapování na existující/nové plány

| # | Bod | Existující plán | Nový plán potřeba |
|---|-----|-----------------|-------------------|
| 1 | Resolve Model | `PLAN-Resolve-Model.md` (na branchi) | ❌ — jen revize |
| 2 | Custom Pack | `PLAN-Pack-Edit.md` | ❓ Možná `PLAN-Custom-Pack-Completion.md` |
| 3 | Install Pack | `PLAN-Install-Packs.md` | ❌ — jen revize/dospecifikování |
| 4 | Workflow Wizard | `PLAN-Workflow-Wizard.md` | ❌ — revize + integrace s 1, 2 |
| 5 | Profiles (extension) | existující Profiles systém + `PLAN-Updates.md` | ❓ Možná `PLAN-Profiles-Extensions.md` (NIKDY ne `PLAN-App-Connector.md`!) |
| 6 | AI Integration | `PLAN-AI-Services.md` + Avatar plány | ❌ — revize + UX mapa |

---

## 🐛 Domain Audit Findings — Distribution Table

Z `plans/audits/DOMAIN-AUDIT.md` + `plans/audits/codex-domain-audit.md` (2026-05-02).
Každý bug/smell je distribuován do plánu, kde se má fix řešit. Detaily a recommendations
v auditních souborech.

### HIGH severity (runtime bugs / divergence rizika)

| # | Finding | File:Line | Cíl plán | Kategorie |
|---|---------|-----------|----------|-----------|
| H1 | `api.py` volá `store.layout.pack_path()` 8× — metoda neexistuje, jen `pack_dir` (`layout.py:169`). Runtime AttributeError na create_pack, preview upload, atd. | `api.py:3334, 3424, 4078, 4581, 4739, 4790, 4859, 4958` | `PLAN-Pack-Edit.md` | bug fix |
| H2 | `cli.py:527` čte `pack_entry.enabled` — pole na `ProfilePackEntry` neexistuje (jen `name`). Crash při `synapse profile show`. | `cli.py:527`, `models.py:1002` | `PLAN-Release-1-Roadmap.md` (Profiles) | bug fix |
| H3 | `apply_dependency_resolution` zapisuje do `selector.canonical_source`, ale ne do `Pack.source` → divergence mezi resolve výstupem a pack origin. | resolve branch: `pack_service.py` apply path | `PLAN-Resolution.md` + resolve branch | design |
| H4 | `pack_dependencies` nikdy expandované do `ViewBuilder.compute_plan()` — runtime view ignoruje deklarované pack deps. | `view_builder.py`, `models.py:837 Pack.pack_dependencies` | `PLAN-Dependencies.md` | design rozhodnutí |
| H5 | `version_constraint` na `PackDependencyRef` nikdy enforcovaný (žádný resolver/loader to nečte). | `models.py:438` | `PLAN-Dependencies.md` | design rozhodnutí |
| H6 | `AssetKind.CUSTOM_NODE` chybí v `UIKindMap` → ViewBuilder fallback `models/{kind.value}` zapíše custom_node do `models/custom_node/` místo `custom_nodes/`. | `models.py:121 UIKindMap`, `view_builder.py` fallback | `PLAN-Workflow-Wizard.md` | rozšíření |

### MEDIUM severity (modelové smells / nedotažené featury)

| # | Finding | File:Line | Cíl plán | Kategorie |
|---|---------|-----------|----------|-----------|
| M1 | `StatusReport.shadowed` vždy `[]` (hardcoded prázdný list, nepočítá se overlap mezi profily). | `__init__.py:951-960` | `PLAN-Release-1-Roadmap.md` (Profiles) | dokončení |
| M2 | `ConflictConfig.mode` deklarováno, ale nikde čteno — `view_builder` neaplikuje conflict resolution. | `models.py:1012`, `view_builder.py` | `PLAN-Release-1-Roadmap.md` (Profiles) | dokončení |
| M3 | `InventoryItem.active_in_uis = []` TODO (nikdy se neplní z `view_state.json`). | `inventory_service.py:377` | `PLAN-Model-Inventory.md` | dokončení |
| M4 | `ImpactAnalysis.active_in_uis = []` stejný TODO. | `inventory_service.py:613` | `PLAN-Model-Inventory.md` | dokončení |
| M5 | `base_model_aliases` default factories používají placeholder zero IDs (`model_id=0, version_id=0`). Komentář v kódu: "These are placeholder values". | `models.py:271-307` | `PLAN-Resolution.md` | data fix |
| M6 | `schema_*` versioning pole existují na 6 modelech, ale **žádný migration runner** — `grep schema_version` v `src/store/` = 0 hits. Při změně schématu starý data crashnou. | `models.py` (StoreConfig, UISets, Pack, PackLock, Profile, atd.) | `PLAN-Release-1-Roadmap.md` (cross-cutting) | infrastructure |
| M7 | `INSTALL` pack semantics nemodelované — žádný `script_manifest`, `install_dir`, `entrypoints` na `Pack`. PackCategory.INSTALL existuje, ale je to enum hodnota bez data. | `models.py:837 Pack`, `models.py PackCategory` | `PLAN-Install-Packs.md` | rozšíření |
| M8 | Žádný `WORKFLOW` PackCategory — workflow imports musí jít přes `CUSTOM` s nějakým facetem (`imported_workflow_ref`?). | `models.py PackCategory` | `PLAN-Workflow-Wizard.md` | rozšíření |
| M9 | `BaseModelHintResolver` swallowuje errory přes nested try/except — debugging je peklo. | `dependency_resolver.py:264` | `PLAN-Resolution.md` | code quality |
| M10 | `extra_model_paths` schema je YAML-string (ne modelovaný objekt) — žádná validace. | `ui_attach.py` | `PLAN-Workflow-Wizard.md` | rozšíření |

### LOW severity (kosmetika / dokumentace)

| # | Finding | File:Line | Cíl plán |
|---|---------|-----------|----------|
| L1 | `Pack` třída dělá příliš (provider origin, deps, gallery, generation meta, workflow meta, editability, update behavior, install). 9 polí by mohlo být discriminated union. | `models.py:837` | `PLAN-Release-1-Roadmap.md` (refactor) |
| L2 | `DependencySelector` má 6 Optional polí — mělo by být discriminated union per strategy (Civitai vs HF vs Local vs URL). | `models.py:438` | `PLAN-Dependencies.md` |
| L3 | `work__<pack>` ephemeral profile lifecycle není dokumentován ani testovaný — vznikne na export, někdy zůstane viset. | `profile_service.py` | `PLAN-Release-1-Roadmap.md` (Profiles) |

### Open Questions pro vlastníka (před jakýmkoliv rozšiřováním modelů)

Z auditu, čekají na rozhodnutí:

1. **`pack_dependencies`** — operational (expandovat do view) nebo informational (jen meta)?
2. **`apply_resolution()`** — má updatovat `lock.json`, invalidovat ho, nebo nechat stale state?
3. **`Pack.source`** — "creation source" (jen jak vznikl) nebo "all pack content source"?
4. **Workflow imports** → `PackCategory.WORKFLOW` (samostatný), nebo `CUSTOM` s `workflow` facetem?
5. **Install packs** — first-party only, nebo user-uploadable arbitrary install scripts?
6. **Custom packs** — backend-updatable když deps mají `FOLLOW_LATEST`?
7. **Optional dependencies** — affectují `PackLock.is_fully_resolved()`?
8. **Dependency IDs** — user-editable po vytvoření locku?
9. **ComfyUI custom nodes** — store assets, install packs, nebo separátní extension manager?
10. **Backup state sync** — push/pull only, nebo bidirectional merge s conflict resolution?
11. **UI roots** — store config, nebo zůstávají v application config?
12. **Migration policy** pro existující `synapse.pack.v2` soubory po canonical-source landingu?

→ **Zodpovědět tyto otázky PŘED implementací bodů 2 (Custom), 3 (Install), 4 (Workflow), 5 (Profiles).**

---

## 🚦 Prioritizace pro Release 1

**Návrh pořadí (dependency-driven, ne důležitost):**

1. **Bod 1 (Resolve)** — dotáhnout doma, je nejdál. Bez něj nefungují bod 2, 4, 5 v plné formě.
2. **Bod 5 (App Connector)** — CRITICAL feature, pravděpodobně největší díra. Audit první.
3. **Bod 2 (Custom Pack)** — bez něj nelze použít bod 4 (import workflow → custom pack).
4. **Bod 4 (Workflow Wizard)** — staví na 1, 2, 5.
5. **Bod 6 (AI)** — průřezově, mapuje se na všechny předchozí. Lze postupně doplňovat.
6. **Bod 3 (Install Pack)** — security-heavy, lze odložit za Release 1.1, pokud potřeba.

---

## 📐 Pravidla pro práci na bodech

Pro každý bod **v tomto pořadí**:

1. **Audit** podle pěti otázek z úvodu (specifikace / implementace / integrace / testy / UX)
2. **Revize plánu** — doplnit nálezy, dospecifikovat díry, odškrtnout, co opravdu funguje
3. **Review** — Claude + Gemini + Codex (z `CLAUDE.md` § Review po každé fázi)
4. **Implementace** — postupně po fázích, každá fáze končí review + testy
5. **Test pyramida** — unit + integration + smoke/E2E (povinné podle `CLAUDE.md`)
6. **Aktualizace tohoto roadmapu** — odškrtnout/přidat poznámku

**NIKDY:**
- ❌ Neimplementovat bez auditu
- ❌ Nevěřit "✅ DOKONČENO" v existujících plánech bez ověření kódu
- ❌ Nepřeskakovat integraci (= největší zdroj děr)
- ❌ Nevytvářet paralelní implementaci, pokud existuje napojitelná služba (viz MEMORY.md)

---

## 🔄 Stav roadmapu

| Datum | Co | Kdo |
|-------|-----|-----|
| 2026-05-02 | Vytvořen v0.1.0 (DRAFT) — 6 bodů, čeká na schválení a start auditu | raven2cz + Claude |
| 2026-05-02 | v0.4.0 — přidán Domain Audit Findings table (HIGH/MEDIUM/LOW + open questions), distribuováno do per-plan sekcí | raven2cz + Claude Opus 4.7 + Codex 5.5 |

---

*Tento dokument je living document. Aktualizujeme po každém auditu a fázi.*
