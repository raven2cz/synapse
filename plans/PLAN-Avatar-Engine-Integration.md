# PLAN: Avatar Engine Integration into Synapse

**Version:** v1.0.0
**Status:** 🚧 PLÁNOVÁNÍ
**Created:** 2026-02-22
**Author:** raven2cz + Claude Opus 4.6
**Branch:** `feat/avatar-engine`
**Dependencies:** `avatar-engine` v1.0.0 (PyPI), `@avatar-engine/react` v1.0.0 (npm)

---

## Executive Summary

Plná integrace AI Avatar Engine do Synapse. Avatar Engine poskytuje runtime pro AI avatary
s podporou tří providerů (Gemini CLI, Claude Code, Codex CLI), WebSocket streamingem,
MCP tool orchestrací a kompletní React komponentovou knihovnou (23 komponent, 7 hooků).

**Klíčové cíle:**
- Interaktivní AI asistent přístupný z každé stránky (FAB → CompactChat → Fullscreen)
- MCP servery pro Synapse-specifické operace (inventory, packs, backup, import, dependencies)
- Skills systém s markdown konfigurací pro doménové znalosti
- Postupná integrace do všech částí Synapse (import, parameters, dependencies, workflow)
- Podpora custom avatarů a CSS přetížení
- Bezpečný upgrade path knihovny

**Propojení s existujícími plány:**
- **`PLAN-Resolution.md`** — Smart Resolution (extracted from Dependencies Phase 5).
  Avatar-engine AI recommendations jsou klíčová součást. Iterace 6.3 tohoto plánu
  implementuje přesně to, co PLAN-Resolution.md popisuje v sekci 2b.
- **`PLAN-Dependencies.md`** — Phase 1-4 DOKONČENO. Dependency resolver
  (`BaseModelResolverModal`) je **obecná komponenta** pro jakýkoliv typ závislosti.
  Avatar AI tab (Iterace 6.3) ji rozšiřuje.
- **`PLAN-Workflow-Wizard.md`** — Wizard pro generování workflow z parametrů.
  Avatar MCP workflow server (Iterace 6.2) bude backend intelligence pro tento wizard.
- **`PLAN-Install-Packs.md`** — Správa instalací UI prostředí (ComfyUI, Forge, atd.)
  přes skripty a terminál. Avatar může asistovat s troubleshootingem a konfigurací.
- **`PLAN-AI-Services.md`** — Phase 1 DOKONČENO (src/ai/). Iterace 7 tohoto plánu
  kompletně nahradí src/ai/ avatar-enginem.

**Zlaté pravidlo — AI je VOLITELNÁ:**
- **Kompletně vypínatelná** — master switch v Settings, Synapse funguje 100% bez AI
- **Žádné AI CLI ≠ žádný problém** — uživatel bez Gemini/Claude/Codex přijde jen o AI features
- **Každá AI-enhanced feature MÁ fallback** — manuální alternativa je VŽDY dostupná
- **UI nabízí obojí** — AI suggestion + ruční možnost vedle sebe, nikdy jen AI

**Architektura:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYNAPSE + AVATAR ENGINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────┐     ┌──────────────────────────────────────┐ │
│  │  React Frontend       │     │  FastAPI Backend                     │ │
│  │  ┌──────────────────┐ │     │  ┌──────────────────────────────┐   │ │
│  │  │ AvatarWidget     │ │     │  │ app.mount("/api/avatar",     │   │ │
│  │  │ (FAB + Compact   │ │ WS  │  │   create_api_app(...))       │   │ │
│  │  │  + Fullscreen)   │◄├─────┤► │                              │   │ │
│  │  │                  │ │     │  │ AvatarEngine ──► Provider     │   │ │
│  │  │ useAvatarChat()  │ │     │  │   │               Bridge     │   │ │
│  │  └──────────────────┘ │     │  │   ▼                          │   │ │
│  │                       │     │  │ MCP Servers:                  │   │ │
│  │  ┌──────────────────┐ │     │  │  ├─ synapse-store            │   │ │
│  │  │ Existing UI      │ │REST │  │  ├─ synapse-import           │   │ │
│  │  │ (Packs, Browse,  │◄├─────┤► │  ├─ synapse-inventory        │   │ │
│  │  │  Inventory, ...)│ │     │  │  └─ synapse-workflow          │   │ │
│  │  └──────────────────┘ │     │  └──────────────────────────────┘   │ │
│  └──────────────────────┘     └──────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Princip "avatar-engine jako knihovna":**
- Synapse NEFORKÁ avatar-engine, používá ji jako dependency
- Veškeré Synapse-specifické chování definováno přes:
  1. MCP servery (tools pro AI)
  2. Skills (markdown soubory s doménovou znalostí)
  3. System prompt (instrukce pro avatara)
  4. Konfigurace (`~/.synapse/avatar.yaml`)
- Upgrade knihovny = `pip install --upgrade avatar-engine` + `pnpm update @avatar-engine/react`

---

## Princip: AI je volitelná — Fallback & Settings strategie

### Master Switch & Disable Strategie

AI v Synapse je **kompletně vypínatelná**. Existují tři stavy:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AI Availability States                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  STATE 1: AI ENABLED + Provider available                            │
│  ├─ Avatar FAB viditelný, chat funkční                               │
│  ├─ AI-enhanced features aktivní (suggestions, auto-extract, ...)    │
│  ├─ MCP tools dostupné                                               │
│  └─ UI zobrazuje AI i manuální alternativy                          │
│                                                                      │
│  STATE 2: AI ENABLED + No provider (CLI not installed)               │
│  ├─ Avatar FAB viditelný ale s "Setup required" badge                │
│  ├─ Click → setup wizard (jak nainstalovat Gemini/Claude/Codex)      │
│  ├─ Batch operations fallback na rule_based                          │
│  └─ UI features fungují manuálně                                     │
│                                                                      │
│  STATE 3: AI DISABLED (master switch OFF)                            │
│  ├─ Avatar FAB SKRYTÝ, žádné AI komponenty v DOM                    │
│  ├─ Žádné WS spojení, žádné MCP servery                             │
│  ├─ Batch extraction → rule_based only                               │
│  ├─ UI nezobrazuje žádné AI suggestions                              │
│  └─ Synapse plně funkční — nic nechybí, jen extra AI features       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Fallback strategie pro každou AI feature

**Pravidlo:** Každé UI místo, kde avatar nabízí AI funkci, MUSÍ mít vedle
manuální alternativu. Uživatel nikdy není nucen používat AI.

| AI Feature | AI varianta | Manuální fallback (stávající UI) |
|------------|-------------|-----------------------------------|
| **Parameter extraction** | Automatická AI extrakce při importu | Rule-based extrakce + ruční editace v EditParametersModal |
| **Dependency resolution** | 4. tab "AI" v dependency resolveru — prohledá všechny zdroje, ranked list (jakýkoliv dep typ) | 3 stávající taby: Local, Civitai, HuggingFace (beze změny) |
| **Workflow generation** | AI navrhne default ComfyUI workflow pro pack | Ruční výběr z workflow šablon, import vlastního JSON |
| **Import analysis** | Collapsible "AI Analysis" v ImportWizardModal — typ, kvalita, dependencies | Wizard funguje přesně jako dnes (sekce se nezobrazí) |
| **Parameter explanation** | Klik → avatar vysvětlí parametr v chatu | Tooltip s krátkou definicí (statický text) |
| **Base model hint** | AI vylepší `extractBaseModelHint()` — přesnější detekce | Stávající regex pattern matching (funguje, jen méně přesně) |
| **Inventory help** | Avatar chat: "Find orphans", "Suggest cleanup" | Stávající BlobsTable filtry, cleanup wizard, CLI příkazy |
| **Install pack help** | Avatar asistuje s troubleshootingem skriptů, konfigurací, chybovými hláškami | Uživatel čte console output, řeší ručně dle dokumentace |
| **Proactive suggestions** | Suggestion chips v compact chatu dle stránky | Nic se nezobrazí — UI funguje normálně bez nich |

### Settings UI — Transformace stávající AI záložky

Stávající "AI Services" v Settings se postupně transformuje na "AI Assistant" (Avatar).
Klíčové: zachovat jednoduchost pro základní konfiguraci, pokročilé věci přes `avatar.yaml`.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⚙️ Settings                                                    [×] │
├─────────────────────────────────────────────────────────────────────┤
│  General │ Storage │ 🤖 AI Assistant │ Profiles │ ...               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  AI Assistant                                                        │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Enable AI features           [═══════════○] ON                      │
│  ⓘ When disabled, all AI features are hidden. Synapse works          │
│    fully without AI — only manual alternatives are available.        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Provider                                                     │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │                                                               │    │
│  │  Active provider: [Gemini CLI            ▼]                   │    │
│  │  Model:           [gemini-3-pro-preview  ▼]                   │    │
│  │  Status:          ● Connected (ACP warm session)              │    │
│  │                                                               │    │
│  │  Available providers on this system:                          │    │
│  │   ● Gemini CLI     gemini-3-pro-preview    ✅ Ready           │    │
│  │   ● Claude Code    claude-sonnet-4-5       ✅ Ready           │    │
│  │   ○ Codex CLI      —                       ❌ Not installed   │    │
│  │                                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Avatar                                                       │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │                                                               │    │
│  │  Avatar:   [🎭 Synapse (default)     ▼]   [Preview]          │    │
│  │  Safety:   [◉ Safe  ○ Ask  ○ Unrestricted]                    │    │
│  │  ⓘ Ask mode requires Gemini provider (only supported there)  │    │
│  │                                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Batch AI (Import extraction)                                 │    │
│  ├─────────────────────────────────────────────────────────────┤    │
│  │                                                               │    │
│  │  Auto-extract parameters on import: [✓]                       │    │
│  │  Provider for batch extraction:     [Same as above ▼]         │    │
│  │  Cache AI results:                  [✓]  TTL: [30 days]       │    │
│  │                                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  [Advanced ▼]                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Skills:          8 built-in, 0 custom    [Manage Skills]      │    │
│  │ Config file:     ~/.synapse/avatar.yaml  [Open in Editor]     │    │
│  │ MCP Servers:     3 active                [View Status]        │    │
│  │ Log level:       [INFO ▼]                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ⓘ Advanced configuration: edit ~/.synapse/avatar.yaml directly.     │
│    MCP servers, custom skills, and provider-specific settings         │
│    are configured in this file.                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Klíčové design principy Settings UI:**
1. **Jednoduché nahoře** — master switch, provider, model, avatar, safety = 80% uživatelů
2. **Batch AI samostatně** — extrakce parametrů je specifická, má vlastní sekci
3. **Advanced schované** — skills, MCP, config file, timeouts = pro pokročilé
4. **avatar.yaml je pravda** — Settings UI zapisuje do avatar.yaml, ne do separátního configu
5. **"Open in Editor"** — pro edge cases, které UI nepokrývá

### Jak AI vylepšuje stávající UI (ne nahrazuje)

**Pravidlo:** AI NENAHRAZUJE existující UI komponenty. Rozšiřuje je.
Stávající manuální flow (taby, formuláře, dropdowny) zůstává 100% funkční.
AI přidá chytrou vrstvu navíc — když je dostupná.

#### Dependency Resolver — obecná komponenta (klíčový případ)

Stávající `BaseModelResolverModal.tsx` je ve skutečnosti **obecný dependency resolver**.
Používá se pro **jakýkoliv typ závislosti** — base model, LoRA, VAE, embedding,
ControlNet, atd. Používá se:
- Při Civitai importu (base model assignment)
- Při custom packu (přidání libovolné dependency)
- Při manuální editaci závislostí (EditDependenciesModal → resolve)

Modal má 3 taby: **Local | Civitai | HuggingFace** — tři zdroje odkud
uživatel může ručně vyhledat a přiřadit fyzický model k závislosti.

**S AI integrací:**
- Přibude **4. tab: AI** — prohledá všechny tři zdroje najednou,
  zhodnotí kompatibilitu s packem, seřadí výsledky podle relevance
- **Smart hint** ve stávajících tabech — AI pre-fillne search query
  na základě analýzy dependency typu a popisu packu
- AI tab ví o typu dependency (base_model vs LoRA vs VAE...) a podle toho
  hledá jinak — pro base model hledá checkpointy, pro LoRA hledá LoRA, atd.
- Když AI není dostupná → 3 taby fungují přesně jako dnes, nic nechybí

```
Příklad: resolve base model pro LoRA pack

┌─────────────────────────────────────────────────────────┐
│ Resolve Dependency: MyLoRA v2.0                      [×] │
│ Type: Base Model (Checkpoint)    Hint: "SD 1.5"         │
├─────────────────────────────────────────────────────────┤
│  [🤖 AI] │ [Local] │ [Civitai] │ [HuggingFace]         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  AI searched Local + Civitai + HuggingFace:              │
│                                                          │
│  ⭐ dreamshaper_8.safetensors         LOCAL ✅  98%      │
│     In inventory (Pack: DreamShaper v8) · SD 1.5         │
│     [Use This]                                           │
│                                                          │
│     realisticVision_v51.safetensors   LOCAL ✅  95%      │
│     In inventory (Pack: Realistic Vision v5) · SD 1.5    │
│     [Use This]                                           │
│                                                          │
│     epicRealism_pureEvolution.saf...  Civitai 📥  92%   │
│     Available on Civitai — 2.1 GB · SD 1.5               │
│     [Import & Use]                                       │
│                                                          │
│  💬 [Ask AI for more options...]                         │
│                                                          │
└─────────────────────────────────────────────────────────┘

Příklad: resolve embedding dependency

┌─────────────────────────────────────────────────────────┐
│ Resolve Dependency: MyLoRA v2.0                      [×] │
│ Type: Embedding    Hint: "EasyNegative"                  │
├─────────────────────────────────────────────────────────┤
│  [🤖 AI] │ [Local] │ [Civitai] │ [HuggingFace]         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  AI searched Local + Civitai + HuggingFace:              │
│                                                          │
│  ⭐ EasyNegative.safetensors          LOCAL ✅  99%      │
│     In inventory (Pack: Negative Embeddings)             │
│     [Use This]                                           │
│                                                          │
│     easynegative.safetensors          HF 📥  97%        │
│     gsdf/EasyNegative · 24 KB                            │
│     [Import & Use]                                       │
│                                                          │
└─────────────────────────────────────────────────────────┘

Bez AI (vypnutá nebo nedostupná):

┌─────────────────────────────────────────────────────────┐
│ Resolve Dependency: MyLoRA v2.0                      [×] │
│ Type: Base Model (Checkpoint)    Hint: "SD 1.5"         │
├─────────────────────────────────────────────────────────┤
│  [Local] │ [Civitai] │ [HuggingFace]                    │
├─────────────────────────────────────────────────────────┤
│  🔍 [Search models...              ]                     │
│  (3 taby fungují přesně jako dnes — nic nechybí)        │
└─────────────────────────────────────────────────────────┘
```

**Důležité:** Komponenta se přejmenuje z `BaseModelResolverModal` na
`DependencyResolverModal` (nebo podobně), protože to není jen pro base model —
je to obecný resolver pro jakoukoliv dependency s přiřazením fyzického modelu.

#### ImportWizardModal — Civitai import

Stávající wizard: Pack Details → Version Selection → Download Options → Thumbnail → Import.
S AI přibude volitelný collapsible blok **AI Analysis** nahoře:

```
┌─────────────────────────────────────────────────────────┐
│ Import: GhostMix V2.0                               [×] │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌ 🤖 AI Analysis (optional, collapsible) ───────────┐  │
│  │ Type: SDXL Checkpoint                               │  │
│  │ Quality: High (based on 12k downloads)              │  │
│  │ Dependencies: Needs SDXL VAE (not in inventory)     │  │
│  │ Recommendation: Import v2.0 + v1.5 for comparison   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
│  ▶ Pack Details                                          │
│  ▶ Version Selection (2 selected)                        │
│  ▶ Download Options                                      │
│  ▶ Thumbnail Selection                                   │
│                                                          │
│                              [Cancel]  [Import]          │
└─────────────────────────────────────────────────────────┘
```

Bez AI — žádný "AI Analysis" blok, wizard funguje přesně jako dnes.

#### Obecné pravidlo pro všechny komponenty
1. Stávající UI zůstává funkční a kompletní
2. AI přidá nový tab / collapsible sekci / smart hint
3. Když AI disabled/unavailable → přidaný element se nezobrazí
4. Uživatel nikdy nemá pocit "tady mi něco chybí" bez AI

---

## Iterace 1: Foundation — Backend mount + Frontend widget

**Cíl:** Avatar Engine běží jako součást Synapse, uživatel vidí FAB tlačítko a může chatovat.

### 1.1 Backend: Python dependency + mount ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Přidat `avatar-engine[web]` do pyproject.toml | ❌ | `pyproject.toml` | Optional dependency group `[avatar]` |
| Vytvořit avatar config loader | ❌ | `src/avatar/__init__.py` | Načítá `~/.synapse/avatar.yaml`, fallback na defaults |
| Vytvořit default avatar.yaml | ❌ | `config/avatar.yaml.example` | Vzorová konfigurace s komentáři |
| Mount avatar API do FastAPI | ❌ | `apps/api/src/main.py` | `app.mount("/api/avatar", create_api_app(...))` |
| Přidat CORS pro WebSocket | ❌ | `apps/api/src/main.py` | WS origin povolení |
| Graceful degradation | ❌ | `apps/api/src/main.py` | Pokud avatar-engine není nainstalován → skip mount, log warning |
| Health check endpoint | ❌ | `src/store/api.py` | `GET /api/ai/avatar/status` — je avatar engine dostupný? |

**Detail mount:**
```python
# apps/api/src/main.py
try:
    from avatar_engine.web import create_api_app as create_avatar_app
    from src.avatar import load_avatar_config

    avatar_config = load_avatar_config()
    avatar_app = create_avatar_app(
        provider=avatar_config.get("provider", "gemini"),
        config_path=avatar_config.get("config_path"),
    )
    app.mount("/api/avatar", avatar_app)
    logger.info("Avatar Engine mounted at /api/avatar")
except ImportError:
    logger.info("Avatar Engine not installed — AI avatar features disabled")
```

**Detail konfigurace (`~/.synapse/avatar.yaml`):**
```yaml
# Default provider
provider: "gemini"

# Synapse-specific system prompt (injected into all providers)
system_prompt: |
  You are a Synapse AI assistant — an expert in AI model management,
  ComfyUI workflows, Stable Diffusion, and image generation.

  You have access to Synapse tools via MCP. Use them to help the user
  manage their model inventory, import packs, resolve dependencies,
  and optimize generation parameters.

  The user's model store is at ~/.synapse/store.
  Always be helpful, concise, and proactive.

# MCP servers (Synapse tools)
mcp_servers:
  synapse-store:
    command: "python"
    args: ["-m", "src.avatar.mcp.store_server"]
    env:
      SYNAPSE_ROOT: "~/.synapse"

# Provider configs (override avatar-engine defaults)
gemini:
  model: "gemini-3-pro-preview"
  approval_mode: "yolo"
  acp_enabled: true
  mcp_servers:
    synapse-store:
      command: "python"
      args: ["-m", "src.avatar.mcp.store_server"]

claude:
  model: "claude-sonnet-4-5"
  permission_mode: "acceptEdits"
  allowed_tools:
    - "Read"
    - "Grep"
    - "mcp__synapse-store__*"
  mcp_servers:
    synapse-store:
      command: "python"
      args: ["-m", "src.avatar.mcp.store_server"]

codex:
  model: ""
  auth_method: "chatgpt"
  mcp_servers:
    synapse-store:
      command: "python"
      args: ["-m", "src.avatar.mcp.store_server"]

engine:
  working_dir: "~/.synapse"
  max_history: 100
  auto_restart: true
  safety_instructions: "safe"  # safe (default) | ask (Gemini only) | unrestricted
```

### 1.2 Frontend: npm dependency + AvatarWidget ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Přidat `@avatar-engine/react` do package.json | ❌ | `apps/web/package.json` | `pnpm add @avatar-engine/react` |
| Update Tailwind config — preset | ❌ | `apps/web/tailwind.config.js` | `presets: [avatarPreset]` + content scan |
| Update Vite config — WS proxy | ❌ | `apps/web/vite.config.ts` | `/api/avatar` proxy s `ws: true` |
| Import avatar styles | ❌ | `apps/web/src/main.tsx` | `import '@avatar-engine/react/styles.css'` |
| Vytvořit AvatarProvider wrapper | ❌ | `apps/web/src/components/avatar/AvatarProvider.tsx` | Context provider s useAvatarChat |
| Přidat AvatarWidget do Layout | ❌ | `apps/web/src/components/layout/Layout.tsx` | FAB + CompactChat + Fullscreen |
| Přidat PermissionDialog | ❌ | `apps/web/src/components/layout/Layout.tsx` | Pro ACP permission requests |
| Avatar stránka (fullscreen) | ❌ | `apps/web/src/components/modules/AvatarPage.tsx` | Route `/avatar` — dedikovaná stránka |
| Navigace — přidat do Sidebar | ❌ | `apps/web/src/components/layout/Sidebar.tsx` | "AI Assistant" odkaz |
| Route `/avatar` | ❌ | `apps/web/src/App.tsx` | Nová route |

**Detail Layout integrace:**
```tsx
// Layout.tsx
import { useAvatarChat, AvatarWidget, PermissionDialog } from '@avatar-engine/react'
import '@avatar-engine/react/styles.css'

export function Layout({ children }: LayoutProps) {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/avatar/ws`
  const chat = useAvatarChat(wsUrl, {
    apiBase: '/api/avatar',
    initialProvider: 'gemini',
  })

  return (
    <div className="min-h-screen bg-obsidian flex flex-col">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-6">{children}</main>
      </div>
      <ToastContainer />

      {/* AI Avatar — accessible from every page */}
      <AvatarWidget {...chat} />
      <PermissionDialog
        request={chat.permissionRequest}
        onRespond={chat.sendPermissionResponse}
      />
    </div>
  )
}
```

### 1.3 Tailwind & CSS kompatibilita ❌ CHYBÍ

| Úkol | Stav | Popis |
|------|------|-------|
| Ověřit color compatibility | ❌ | Synapse a avatar-engine sdílí barvy (synapse, pulse, neural, obsidian, slate-*) |
| Ověřit animation compatibility | ❌ | Obě knihovny mají `breathe`, `slide-in`, `fade-in` |
| Resolvenout konflikty | ❌ | Avatar preset by měl rozšířit, ne přepsat Synapse barvy |
| CSS custom properties bridge | ❌ | Mapovat Synapse barvy na `--ae-*` CSS variables |
| Vytvořit `synapse-avatar-overrides.css` | ❌ | Pro případné přetížení avatar stylů |

**Detail CSS bridge:**
```css
/* apps/web/src/styles/avatar-overrides.css */
:root {
  /* Map Synapse colors to Avatar Engine CSS custom properties */
  --ae-accent-rgb: 99 102 241;       /* synapse (#6366f1) */
  --ae-pulse-rgb: 139 92 246;        /* pulse (#8b5cf6) */
  --ae-neural-rgb: 6 182 212;        /* neural (#06b6d4) */

  --ae-bg-obsidian-rgb: 10 10 15;    /* obsidian (#0a0a0f) */
  --ae-bg-darker-rgb: 15 15 23;      /* slate-darker (#0f0f17) */
  --ae-bg-deep-rgb: 18 18 26;        /* slate-deep (#12121a) */
  --ae-bg-base-rgb: 19 19 27;        /* slate-base (#13131b) */
  --ae-bg-dark-rgb: 22 22 31;        /* slate-dark (#16161f) */
  --ae-bg-mid-rgb: 26 26 46;         /* slate-mid (#1a1a2e) */
  --ae-bg-light-rgb: 42 42 66;       /* slate-light (#2a2a42) */

  --ae-text-primary-rgb: 248 250 252;
  --ae-text-secondary-rgb: 148 163 184;
  --ae-text-muted-rgb: 100 116 139;
}
```

### 1.4 Install skript (`scripts/install.sh`) ❌ CHYBÍ

Stávající `scripts/install.sh` řeší: Python deps (uv/pip), Node.js deps (npm), inicializaci
`~/.synapse/store/`. Pro avatar-engine je potřeba rozšířit:

| Úkol | Stav | Popis |
|------|------|-------|
| Avatar jako optional install | ❌ | Nová sekce v install.sh s `--with-avatar` flag (nebo interaktivní prompt) |
| Python: `avatar-engine[web]` | ❌ | `uv pip install avatar-engine[web]` (skip pokud `--no-avatar`) |
| Node.js: `@avatar-engine/react` | ❌ | `pnpm add @avatar-engine/react` v `apps/web/` |
| Vytvořit avatar adresáře | ❌ | `~/.synapse/avatar/skills/`, `~/.synapse/avatar/custom-skills/`, `~/.synapse/avatar/avatars/` |
| Zkopírovat default avatar.yaml | ❌ | `config/avatar.yaml.example` → `~/.synapse/avatar.yaml` (jen pokud neexistuje) |
| Zkopírovat built-in skills | ❌ | `config/avatar/skills/*.md` → `~/.synapse/avatar/skills/` (vždy přepsat — built-in) |
| Detekce AI CLI providerů | ❌ | Check `gemini`/`claude`/`codex` v PATH, informovat uživatele o dostupnosti |
| Graceful skip | ❌ | Pokud avatar-engine install selže → warn + pokračovat (Synapse funguje bez AI) |

**Detail v install.sh:**
```bash
# ============================================================================
# Avatar Engine (Optional AI Features)
# ============================================================================

echo -e "${BOLD_MAGENTA}${HEX_ICON}${NC} ${CYAN}Setting up AI Avatar (optional)...${NC}"
echo ""

# Install avatar-engine Python package
if [ "$USE_UV" = true ]; then
    uv pip install --python .venv/bin/python avatar-engine[web] 2>/dev/null && \
        echo -e "${GREEN}  ✓ avatar-engine installed${NC}" || \
        echo -e "${YELLOW}  ! avatar-engine not available (AI features disabled)${NC}"
else
    .venv/bin/pip install avatar-engine[web] 2>/dev/null && \
        echo -e "${GREEN}  ✓ avatar-engine installed${NC}" || \
        echo -e "${YELLOW}  ! avatar-engine not available (AI features disabled)${NC}"
fi

# Create avatar directories
mkdir -p ~/.synapse/avatar/skills
mkdir -p ~/.synapse/avatar/custom-skills
mkdir -p ~/.synapse/avatar/avatars

# Copy default config (don't overwrite user config)
if [ ! -f ~/.synapse/avatar.yaml ]; then
    cp config/avatar.yaml.example ~/.synapse/avatar.yaml
    echo -e "${GREEN}  ✓ Default avatar.yaml created${NC}"
fi

# Always update built-in skills (user customizations go to custom-skills/)
if [ -d "config/avatar/skills" ]; then
    cp config/avatar/skills/*.md ~/.synapse/avatar/skills/ 2>/dev/null
    SKILL_COUNT=$(ls -1 ~/.synapse/avatar/skills/*.md 2>/dev/null | wc -l)
    echo -e "${GREEN}  ✓ ${SKILL_COUNT} built-in skills installed${NC}"
fi

# Detect available AI CLI providers
echo ""
echo -e "${CYAN}  AI CLI providers:${NC}"
command -v gemini &>/dev/null && echo -e "${GREEN}    ✓ Gemini CLI${NC}" || echo -e "${YELLOW}    ○ Gemini CLI (not installed)${NC}"
command -v claude &>/dev/null && echo -e "${GREEN}    ✓ Claude Code${NC}" || echo -e "${YELLOW}    ○ Claude Code (not installed)${NC}"
command -v codex &>/dev/null && echo -e "${GREEN}    ✓ Codex CLI${NC}" || echo -e "${YELLOW}    ○ Codex CLI (not installed)${NC}"
echo ""
```

**Klíčový princip:** Avatar instalace NESMÍ být blokující. Pokud cokoliv selže,
skript pokračuje. Synapse funguje 100% bez avatar-engine.

### 1.5 Testy — Iterace 1 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_config.py` | Načítání avatar.yaml, defaults, merge |
| Unit | `tests/unit/avatar/test_mount.py` | Graceful degradation (ImportError) |
| Integration | `tests/integration/test_avatar_mount.py` | Avatar API mount + health check |
| Frontend | `apps/web/src/__tests__/AvatarProvider.test.tsx` | Hook initialization, WS URL construction |
| Frontend | `apps/web/src/__tests__/AvatarLayout.test.tsx` | FAB rendering, fallback when unavailable |

---

## Iterace 2: MCP Server — Synapse Store Tools

**Cíl:** AI avatar má přístup k Synapse datům a může vykonávat operace.

### 2.1 MCP Server: synapse-store ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Vytvořit MCP server modul | ❌ | `src/avatar/mcp/__init__.py` | Package init |
| Store server | ❌ | `src/avatar/mcp/store_server.py` | Hlavní MCP server pro Synapse Store |
| Pack tools | ❌ | (v store_server) | list_packs, get_pack, search_packs |
| Blob/Inventory tools | ❌ | (v store_server) | list_blobs, get_blob_status, find_orphans |
| Backup tools | ❌ | (v store_server) | backup_status, sync_status |
| Model info tools | ❌ | (v store_server) | get_model_info, check_dependencies |
| Import tools | ❌ | (v store_server) | import_from_civitai, check_updates |
| Statistics tools | ❌ | (v store_server) | storage_stats, pack_stats |

**Detail MCP Tools (store_server.py):**

```python
#!/usr/bin/env python3
"""
MCP server providing Synapse Store tools for the AI avatar.

Tools are organized by domain:
- Packs: list, search, details, parameters
- Inventory: blobs, orphans, missing, cleanup impacts
- Backup: status, sync status, restore suggestions
- Import: import from Civitai, check for updates
- Statistics: storage usage, pack counts, health
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("synapse-store")

@server.list_tools()
async def list_tools():
    return [
        # === Pack Tools ===
        Tool(
            name="list_packs",
            description="List all packs in the Synapse store with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Name filter (substring match)"},
                    "sort_by": {"type": "string", "enum": ["name", "date", "size"], "default": "name"},
                    "limit": {"type": "integer", "default": 20, "description": "Max results"},
                },
            },
        ),
        Tool(
            name="get_pack_details",
            description="Get detailed information about a specific pack including versions, parameters, and preview images",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_name": {"type": "string", "description": "Pack name"},
                },
                "required": ["pack_name"],
            },
        ),
        Tool(
            name="get_pack_parameters",
            description="Get generation parameters for a pack (CFG, steps, sampler, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_name": {"type": "string", "description": "Pack name"},
                },
                "required": ["pack_name"],
            },
        ),
        Tool(
            name="search_packs",
            description="Full-text search across pack names, descriptions, and metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        ),

        # === Inventory Tools ===
        Tool(
            name="get_inventory_summary",
            description="Get a summary of the model inventory: total blobs, disk usage, backup status, orphans",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="find_orphan_blobs",
            description="Find blobs not referenced by any pack",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="find_missing_blobs",
            description="Find blobs referenced by packs but not present on disk",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_cleanup_impacts",
            description="Preview what would happen if orphan blobs are cleaned up (size freed, safety check)",
            inputSchema={"type": "object", "properties": {}},
        ),

        # === Backup Tools ===
        Tool(
            name="get_backup_status",
            description="Check backup storage status: connected, sync state, last sync time",
            inputSchema={"type": "object", "properties": {}},
        ),

        # === Import Tools ===
        Tool(
            name="check_pack_updates",
            description="Check if any imported packs have newer versions on Civitai",
            inputSchema={
                "type": "object",
                "properties": {
                    "pack_name": {"type": "string", "description": "Specific pack to check (optional, checks all if omitted)"},
                },
            },
        ),

        # === Statistics ===
        Tool(
            name="get_storage_stats",
            description="Get storage statistics: total disk usage, per-type breakdown (checkpoints, LoRAs, etc.), largest packs",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]
```

### 2.2 MCP Server registrace ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Entry point pro MCP server | ❌ | `src/avatar/mcp/__main__.py` | `python -m src.avatar.mcp.store_server` |
| Registrace do avatar.yaml | ❌ | `config/avatar.yaml.example` | MCP server config per provider |
| Environment variables | ❌ | (v config) | `SYNAPSE_ROOT` pro MCP server |
| Store initialization v MCP | ❌ | `src/avatar/mcp/store_server.py` | Inicializovat Store z SYNAPSE_ROOT |

### 2.3 Testy — Iterace 2 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_mcp_tools.py` | Každý tool izolovaně s mock Store |
| Integration | `tests/integration/test_mcp_store.py` | MCP server s reálným Store (tmp_path) |
| Smoke | `tests/integration/test_mcp_smoke.py` | Full lifecycle: start server → call tools → verify |

---

## Iterace 3: Skills System — Domain Knowledge

**Cíl:** Avatar má hlubokou znalost Synapse domény přes markdown skill soubory.

### 3.1 Skills architektura ❌ CHYBÍ

Skills jsou markdown soubory, které avatar načte jako kontextové instrukce.
Definují doménové znalosti, best practices a specifické workflow pro Synapse.

```
~/.synapse/avatar/
├── skills/                      # Synapse-provided skills
│   ├── synapse-basics.md        # What is Synapse, architecture, pack types
│   ├── pack-management.md       # Civitai import, custom packs, pack lifecycle
│   ├── model-types.md           # Checkpoints, LoRAs, VAE, embeddings, ControlNet, upscalers
│   ├── generation-params.md     # CFG, steps, samplers, schedulers, etc.
│   ├── dependency-resolution.md # Asset deps, pack deps, resolver (Local/Civitai/HF)
│   ├── workflow-creation.md     # Workflow wizard, UI targets (ComfyUI, Forge, A1111, SDnext)
│   ├── install-packs.md         # UI installations (ComfyUI, Forge), scripts, terminal, process mgmt
│   ├── inventory-management.md  # Blob storage, backup, cleanup
│   └── civitai-integration.md   # Civitai API, import flow, CDN, HuggingFace
├── custom-skills/               # User-created skills
│   └── (user adds .md files)
└── avatars/                     # Custom avatar images
    └── (user adds avatar dirs)
```

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Vytvořit skills directory structure | ❌ | `~/.synapse/avatar/skills/` | Automaticky vytvořit při prvním spuštění |
| Skill: synapse-basics.md | ❌ | `config/avatar/skills/synapse-basics.md` | Co je Synapse, architektura, typy packů (Civitai, custom, install) |
| Skill: pack-management.md | ❌ | `config/avatar/skills/pack-management.md` | Civitai import, custom pack tvorba, pack lifecycle |
| Skill: model-types.md | ❌ | `config/avatar/skills/model-types.md` | Checkpoints, LoRAs, VAE, embeddings, ControlNet, upscalers, architektury (SD1.5, SDXL, Flux, Pony, Illustrious) |
| Skill: generation-params.md | ❌ | `config/avatar/skills/generation-params.md` | Param explanations + best practices |
| Skill: dependency-resolution.md | ❌ | `config/avatar/skills/dependency-resolution.md` | Asset deps, pack deps, resolver (3 zdroje), strategie, selektory |
| Skill: workflow-creation.md | ❌ | `config/avatar/skills/workflow-creation.md` | Workflow formáty pro ComfyUI, Forge, A1111, SDnext — node system, JSON struktura |
| Skill: install-packs.md | ❌ | `config/avatar/skills/install-packs.md` | Instalace UI prostředí (ComfyUI, Forge, atd.), skripty, terminál, process management, troubleshooting |
| Skill: inventory-management.md | ❌ | `config/avatar/skills/inventory-management.md` | Blob storage, backup/restore, cleanup, orphan detection |
| Skill: civitai-integration.md | ❌ | `config/avatar/skills/civitai-integration.md` | Civitai API, HuggingFace, CDN, import flow |
| Skill loader v system prompt | ❌ | `src/avatar/skills.py` | Čte skills/*.md a appenduje do system prompt |
| Custom skills support | ❌ | `src/avatar/skills.py` | Čte i custom-skills/*.md |
| Skills management API | ❌ | `src/store/api.py` | List/add/remove skills |

### 3.2 System prompt construction ❌ CHYBÍ

```python
# src/avatar/skills.py

def build_system_prompt(
    base_prompt: str,
    skills_dir: Path,
    custom_skills_dir: Path | None = None,
) -> str:
    """
    Build complete system prompt by combining:
    1. Base prompt (from avatar.yaml)
    2. Built-in skills (synapse-provided)
    3. Custom skills (user-provided)
    """
    parts = [base_prompt, "\n\n# Domain Knowledge\n"]

    # Load built-in skills
    for skill_file in sorted(skills_dir.glob("*.md")):
        content = skill_file.read_text()
        parts.append(f"\n## {skill_file.stem.replace('-', ' ').title()}\n{content}\n")

    # Load custom skills
    if custom_skills_dir and custom_skills_dir.exists():
        for skill_file in sorted(custom_skills_dir.glob("*.md")):
            content = skill_file.read_text()
            parts.append(f"\n## Custom: {skill_file.stem}\n{content}\n")

    return "\n".join(parts)
```

### 3.3 Testy — Iterace 3 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_skills.py` | Skill loading, merging, custom override |
| Unit | `tests/unit/avatar/test_system_prompt.py` | System prompt construction |

---

## Iterace 4: Custom Avatars & Theming

**Cíl:** Uživatel může vybrat jiného avatara, přizpůsobit CSS.

### 4.1 Avatar management ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Ship default Synapse avatar | ❌ | `apps/web/public/avatars/synapse/` | idle, thinking, speaking, happy, neutral, surprised, sad |
| Avatar config v avatar.yaml | ❌ | `config/avatar.yaml.example` | `avatar_id: "synapse"` |
| Custom avatar directory | ❌ | `~/.synapse/avatar/avatars/` | Uživatel sem přidá vlastní avatary |
| Avatar picker v Settings | ❌ | `apps/web/src/components/modules/settings/AvatarSettings.tsx` | Výběr avatara + preview |
| Serve avatar images | ❌ | `apps/api/src/main.py` | Static mount pro avatar images |
| AvatarPicker integrace | ❌ | `apps/web/src/components/avatar/AvatarProvider.tsx` | Použít `<AvatarPicker>` z knihovny |

**Detail avatar config:**
```typescript
// Frontend: custom Synapse avatar
const synapseAvatar: AvatarConfig = {
  id: 'synapse',
  name: 'Synapse',
  description: 'The default Synapse AI assistant',
  fullName: 'Synapse AI Assistant',
  busts: {
    idle: '/avatars/synapse/idle.webp',
    thinking: '/avatars/synapse/thinking.webp',
    speaking: '/avatars/synapse/speaking.webp',
    happy: '/avatars/synapse/happy.webp',
    neutral: '/avatars/synapse/neutral.webp',
    surprised: '/avatars/synapse/surprised.webp',
    sad: '/avatars/synapse/sad.webp',
  },
}
```

### 4.2 CSS customization ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| CSS override systém | ❌ | `apps/web/src/styles/avatar-overrides.css` | User-overridable CSS |
| Custom theme support | ❌ | `~/.synapse/avatar/theme.css` | User CSS loaded at runtime |
| Theme selector v Settings | ❌ | `apps/web/src/components/modules/settings/AvatarSettings.tsx` | Light/dark/custom theme |
| Dokumentace CSS variables | ❌ | `docs/AVATAR-THEMING.md` | Which CSS vars can be overridden |

### 4.3 Testy — Iterace 4 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_avatar_config.py` | Avatar loading, custom avatars |
| Frontend | `apps/web/src/__tests__/AvatarSettings.test.tsx` | Avatar picker, theme selector |

---

## Iterace 5: Context-Aware Integration

**Cíl:** Avatar ví, na jaké stránce uživatel je a nabízí kontextovou pomoc.

### 5.1 Page context ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| usePageContext hook | ❌ | `apps/web/src/hooks/usePageContext.ts` | Detekuje aktuální stránku + data |
| Context injection do chatu | ❌ | `apps/web/src/components/avatar/AvatarProvider.tsx` | Při odeslání zprávy přidá kontext |
| PackDetail context | ❌ | (v usePageContext) | Aktuální pack, verze, parametry |
| Browse context | ❌ | (v usePageContext) | Civitai model, preview, description |
| Inventory context | ❌ | (v usePageContext) | Blob stats, orphans count |
| Downloads context | ❌ | (v usePageContext) | Aktivní stahování, progress |

**Detail context injection:**
```typescript
// usePageContext.ts
export function usePageContext() {
  const location = useLocation()
  const params = useParams()

  return useMemo(() => {
    const path = location.pathname

    if (path === '/') return { page: 'packs', description: 'Pack list overview' }
    if (path.startsWith('/packs/') && params.packName) {
      return {
        page: 'pack-detail',
        packName: params.packName,
        description: `Viewing pack: ${params.packName}`,
      }
    }
    if (path === '/inventory') return { page: 'inventory', description: 'Model inventory' }
    if (path === '/browse') return { page: 'browse', description: 'Browsing Civitai models' }
    if (path === '/downloads') return { page: 'downloads', description: 'Active downloads' }
    if (path === '/settings') return { page: 'settings', description: 'Application settings' }

    return { page: 'unknown', description: path }
  }, [location.pathname, params])
}
```

### 5.2 Proactive suggestions ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Suggestion system | ❌ | `apps/web/src/components/avatar/SuggestionChips.tsx` | Quick action chips pod chatem |
| Pack detail suggestions | ❌ | (v SuggestionChips) | "Explain parameters", "Check dependencies", "Suggest workflow" |
| Inventory suggestions | ❌ | (v SuggestionChips) | "Find orphans", "Suggest cleanup", "Check backup" |
| Import suggestions | ❌ | (v SuggestionChips) | "Analyze this model", "Compare versions" |

### 5.3 Testy — Iterace 5 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_page_context.py` | Context detection per page |
| Frontend | `apps/web/src/__tests__/SuggestionChips.test.tsx` | Correct suggestions per page |

---

## Iterace 6: Advanced MCP Tools — Workflow, Dependencies, Import

**Cíl:** Rozšířit MCP servery o pokročilé operace. Toto jsou "mozky" Synapse —
avatar přes tyto tools aktivně pomáhá s tvorbou workflow, dohledáváním správných
modelů pro dependency resolution a analýzou Civitai modelů před importem.

### 6.1 Import MCP Server ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Import MCP server | ❌ | `src/avatar/mcp/import_server.py` | Civitai import operace |
| Tool: import_from_url | ❌ | (v import_server) | Import pack z Civitai URL |
| Tool: analyze_civitai_model | ❌ | (v import_server) | Analyzovat model před importem — typ, kompatibilita, kvalita |
| Tool: compare_versions | ❌ | (v import_server) | Porovnat verze modelu — co se změnilo, doporučení |
| Tool: suggest_import_config | ❌ | (v import_server) | Navrhnout konfiguraci importu na základě analýzy |
| Tool: extract_parameters | ❌ | (v import_server) | AI extrakce generačních parametrů z description (náhrada src/ai/) |

### 6.2 Workflow MCP Server ❌ CHYBÍ

**Viz:** `PLAN-Workflow-Wizard.md` — detailní plán workflow wizard UI.
Avatar MCP server je **backend intelligence** pro tento wizard.

**Klíčová zodpovědnost:** Pomáhá uživateli vytvářet workflow pro různá UI prostředí
(ComfyUI, Forge, A1111, SDnext) z pack parametrů. Wizard UI (z PLAN-Workflow-Wizard.md)
umožňuje vizuální výběr source obrázku a cílového UI, AI server generuje samotný workflow —
správné propojení nodů, doporučené parametry, na základě typu modelu a jeho architektury.

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Workflow MCP server | ❌ | `src/avatar/mcp/workflow_server.py` | ComfyUI workflow operace |
| Tool: generate_default_workflow | ❌ | (v workflow_server) | **HLAVNÍ** — vygenerovat default workflow pro pack |
| Tool: suggest_workflow | ❌ | (v workflow_server) | Navrhnout workflow z parametrů a stylu |
| Tool: analyze_workflow | ❌ | (v workflow_server) | Analyzovat existující workflow JSON |
| Tool: list_comfyui_nodes | ❌ | (v workflow_server) | Dostupné ComfyUI nody na uživatelově systému |
| Tool: validate_workflow | ❌ | (v workflow_server) | Ověřit workflow JSON — chybějící nody, propojení |
| Workflow templates | ❌ | `config/avatar/workflows/` | Šablony pro různé typy modelů (txt2img, img2img, LoRA, ControlNet) |

**Detail generate_default_workflow:**
```python
Tool(
    name="generate_default_workflow",
    description=(
        "Generate a default ComfyUI workflow for a pack. "
        "Considers the model type (checkpoint, LoRA, VAE, ControlNet, embedding), "
        "base model architecture (SD 1.5, SDXL, Flux, etc.), "
        "recommended generation parameters, and available dependencies. "
        "Returns a complete ComfyUI workflow JSON ready for use."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "pack_name": {"type": "string", "description": "Pack to generate workflow for"},
            "style": {"type": "string", "description": "Generation style hint (portrait, landscape, anime, etc.)"},
            "include_loras": {"type": "array", "items": {"type": "string"}, "description": "Additional LoRA packs to include"},
        },
        "required": ["pack_name"],
    },
)
```

### 6.3 Dependency MCP Server ❌ CHYBÍ

**Viz:** `PLAN-Resolution.md` — Smart Resolution (extracted from PLAN-Dependencies Phase 5).
Tento MCP server implementuje sekci 2b ("Avatar-Engine AI Recommendations") z toho plánu.

**Klíčová zodpovědnost:** Pomáhá **dohledat správný konkrétní model** pro jakoukoliv
závislost — base model, LoRA, VAE, embedding, ControlNet, upscaler, cokoliv.

Dependency resolver (`BaseModelResolverModal.tsx`, 765 řádků) je **obecná komponenta**
se 3 taby (Local | Civitai | HuggingFace), používaná ve všech kontextech:
- Civitai importu (přiřazení base modelu k LoRA/checkpoint packu)
- Custom packu (přidání libovolné dependency ručně)
- EditDependenciesModal (resolve existující neresolvené dependency)
- Budoucí bulk resolution (PLAN-Resolution.md sekce 2e)

AI prohledá lokální inventář, Civitai i HuggingFace, zhodnotí kompatibilitu a nabídne
ranked list kandidátů. **Toto je 4. tab "AI"** v dependency resolveru.
Stávající 3 taby zůstávají kompletní a beze změny.

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Dependency MCP server | ❌ | `src/avatar/mcp/dependency_server.py` | Model dependency operace |
| Tool: resolve_dependencies | ❌ | (v dependency_server) | Najít chybějící závislosti packu |
| Tool: find_matching_model | ❌ | (v dependency_server) | **HLAVNÍ** — dohledat konkrétní model pro závislost |
| Tool: search_civitai_for_dependency | ❌ | (v dependency_server) | Prohledat Civitai pro matching model |
| Tool: search_local_inventory | ❌ | (v dependency_server) | Prohledat lokální inventory pro matching blob |
| Tool: suggest_compatible_models | ❌ | (v dependency_server) | Navrhnout kompatibilní modely (ranked list) |
| Tool: check_compatibility | ❌ | (v dependency_server) | Zkontrolovat kompatibilitu LoRA + Checkpoint |
| Tool: assign_dependency | ❌ | (v dependency_server) | Přiřadit konkrétní model/blob k závislosti v packu |

**Detail find_matching_model:**
```python
Tool(
    name="find_matching_model",
    description=(
        "Find the correct specific model file for ANY type of dependency. "
        "Works for base models, LoRAs, VAEs, embeddings, ControlNets — "
        "any asset type a pack can depend on. "
        "Searches: 1) local inventory (already downloaded blobs), "
        "2) other packs in store, 3) Civitai API, 4) HuggingFace. "
        "Returns a ranked list of candidates with download URLs, "
        "compatibility scores, source (local/civitai/huggingface), "
        "and local availability status. "
        "Used by the DependencyResolverModal AI tab in the frontend."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "pack_name": {"type": "string", "description": "Pack that needs the dependency"},
            "dependency_type": {
                "type": "string",
                "enum": ["base_model", "lora", "vae", "embedding", "controlnet", "upscaler", "other"],
                "description": "Type of dependency — determines search strategy"
            },
            "dependency_hint": {
                "type": "string",
                "description": "What the pack says it needs (e.g., 'SD 1.5', 'EasyNegative', model name)"
            },
            "architecture": {
                "type": "string",
                "description": "Model architecture if known (sd15, sdxl, flux, pony, illustrious, etc.)"
            },
        },
        "required": ["pack_name", "dependency_type", "dependency_hint"],
    },
)
```

**UI integrace — 4. tab "AI" v DependencyResolverModal:**

Viz kompletní mockupy v sekci "Dependency Resolver — obecná komponenta" výše.
Stávající 3 taby (Local, Civitai, HuggingFace) zůstávají beze změny.
AI tab prohledá všechny zdroje najednou, ví o typu dependency (base_model/LoRA/VAE/embedding/...)
a podle toho hledá jinak — pro base model hledá checkpointy, pro embedding hledá embeddingy, atd.

Bez AI → tab "AI" se nezobrazí, modal začíná na Local tabu (jako dnes).

### 6.4 Testy — Iterace 6 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_mcp_import.py` | Import tools izolovaně |
| Unit | `tests/unit/avatar/test_mcp_workflow.py` | Workflow tools: generate, validate, templates |
| Unit | `tests/unit/avatar/test_mcp_dependency.py` | Dependency tools: find_matching, search local/civitai |
| Integration | `tests/integration/test_mcp_workflow.py` | Workflow generation s reálnými pack daty |
| Integration | `tests/integration/test_mcp_dependency.py` | Dependency resolution end-to-end |
| Integration | `tests/integration/test_mcp_advanced.py` | Multi-server orchestrace |

---

## Iterace 7: Migrace src/ai/ → Avatar Engine (FULL REPLACEMENT)

**Cíl:** Kompletně nahradit stávající `src/ai/` modul (72 testů, Ollama/Gemini/Claude CLI wrappers)
avatar-engine providerem. Stávající implementace byla "Phase 1" — přímé CLI volání s fallback
chainem. Nová implementace jde přes avatar-engine, který má robustnější bridge systém
(ACP warm sessions, persistent streaming, WebSocket), a používá stejné CLI nástroje
(Gemini CLI, Claude Code, Codex CLI), ale přes profesionálnější runtime.

**Klíčové rozdíly:**
- **Odpadá Ollama** — avatar-engine nepodporuje Ollama (a není potřeba — Gemini/Claude/Codex stačí)
- **Rule-based fallback zůstává** — `src/utils/parameter_extractor.py` je stále fallback
- **Caching se zachovává** — přepoužijeme existující cache mechanismus nebo nový přes avatar-engine
- **_ai_fields tracking** — MUSÍ zůstat funkční (kritické pro UI oddělení AI Insights vs Custom params)
- **Batch operace** — Avatar-engine umí `chat_sync()` pro non-interactive batch volání

### 7.1 Backend: Migrace AI Service ❌ CHYBÍ

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MIGRACE src/ai/ → avatar-engine                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PŘED (src/ai/):                      PO (src/avatar/):              │
│  ├─ providers/ollama.py  ──────────► ODSTRANĚNO (nepotřeba)          │
│  ├─ providers/gemini.py  ──────────► avatar-engine GeminiBridge      │
│  ├─ providers/claude.py  ──────────► avatar-engine ClaudeBridge      │
│  ├─ providers/rule_based.py ───────► ZACHOVÁN (fallback)             │
│  ├─ providers/registry.py ─────────► Nahrazeno avatar-engine config  │
│  ├─ service.py (orchestrator) ─────► src/avatar/ai_service.py (NEW)  │
│  ├─ cache.py ──────────────────────► ZACHOVÁN nebo přepoužit         │
│  ├─ detection.py ──────────────────► avatar-engine /api/providers     │
│  ├─ settings.py ───────────────────► Součást avatar.yaml              │
│  ├─ tasks/parameter_extraction.py ─► MCP tool: extract_parameters    │
│  └─ prompts/parameter_extraction.py► Skills MD + MCP tool prompt     │
│                                                                      │
│  src/ai/ se ODSTRANÍ po dokončení migrace a ověření parity.          │
│  Přechodné období: oba systémy existují paralelně, feature flag.     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Vytvořit nový AI service wrapper | ❌ | `src/avatar/ai_service.py` | Wrapper nad avatar-engine pro batch operace |
| Implementovat extract_parameters | ❌ | `src/avatar/ai_service.py` | Použít `engine.chat_sync()` s extraction promptem |
| Zachovat _ai_fields tracking | ❌ | `src/avatar/ai_service.py` | Výstup MUSÍ obsahovat `_ai_fields` + `_extracted_by` |
| Zachovat cache mechanismus | ❌ | `src/avatar/ai_service.py` | SHA-256[:16] cache s TTL (přepoužít src/ai/cache.py) |
| Rule-based fallback | ❌ | `src/avatar/ai_service.py` | Pokud avatar-engine selže → rule_based z src/utils/ |
| Feature flag pro přepínání | ❌ | `src/avatar/ai_service.py` | `use_avatar_engine: bool` v settings pro postupný rollout |
| Přepojit pack_service.py | ❌ | `src/store/pack_service.py` | Import flow: volat nový ai_service místo starého |
| Aktualizovat AI API endpointy | ❌ | `src/store/api.py` | `/api/ai/*` endpointy → volat nový service |
| Migrace AI Settings UI | ❌ | `AIServicesSettings.tsx` | Přepojit na avatar-engine providers (Gemini/Claude/Codex) |
| Odstranit Ollama z Settings UI | ❌ | `AIServicesSettings.tsx` | Ollama provider card → nahradit avatar-engine providers |
| Parita testů | ❌ | `tests/unit/avatar/test_ai_service.py` | Replika všech 72 testů src/ai/ pro nový service |
| Smoke test: import flow | ❌ | `tests/integration/test_ai_migration_smoke.py` | Import → extract → verify _ai_fields → verify cache |
| Odstranit src/ai/ | ❌ | `src/ai/` | **POSLEDNÍ KROK** — po ověření plné parity + all tests green |

**Detail nového AI service:**
```python
# src/avatar/ai_service.py
"""
AI service backed by avatar-engine.

Replaces src/ai/service.py with avatar-engine as the provider runtime.
Maintains identical output format (_ai_fields, _extracted_by, cache)
for backward compatibility with frontend.
"""

from avatar_engine import AvatarEngine

class AvatarAIService:
    """
    Non-interactive AI service using avatar-engine for batch operations.

    Uses engine.chat_sync() — no WebSocket, no streaming, just prompt → response.
    Providers: Gemini CLI, Claude Code, Codex CLI (configured in avatar.yaml).
    Fallback: rule-based parameter_extractor.py (always available).
    """

    def __init__(self, config_path: Path | None = None, cache: AICache | None = None):
        self.engine = AvatarEngine.from_config(str(config_path)) if config_path else AvatarEngine()
        self.cache = cache or AICache(...)
        self._rule_based = RuleBasedExtractor()  # Always-available fallback

    def extract_parameters(self, description: str, use_cache: bool = True) -> dict:
        """
        Extract generation parameters from model description.

        Returns dict with:
        - Extracted parameters (cfg_scale, steps, sampler, etc.)
        - _extracted_by: provider ID ("gemini", "claude", "codex")
        - _ai_fields: list of field names extracted by AI
        """
        # 1. Check cache
        cache_key = self._cache_key(description)
        if use_cache and (cached := self.cache.get("parameter_extraction", cache_key)):
            return cached

        # 2. Try avatar-engine
        try:
            prompt = self._build_extraction_prompt(description)
            self.engine.start_sync()
            response = self.engine.chat_sync(prompt)
            self.engine.stop_sync()

            parsed = self._parse_json_response(response.content)
            parsed["_extracted_by"] = self.engine.current_provider
            parsed["_ai_fields"] = [k for k in parsed if not k.startswith("_")]

            self.cache.set("parameter_extraction", cache_key, parsed)
            return parsed

        except Exception as e:
            logger.warning(f"Avatar engine extraction failed: {e}")

        # 3. Fallback to rule-based
        result = self._rule_based.extract(description)
        result["_extracted_by"] = "rule_based"
        result["_ai_fields"] = []
        return result
```

### 7.2 Import wizard enhancement ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| AI analysis step | ❌ | `ImportWizardModal.tsx` | Před importem → avatar analyzuje model (přes MCP) |
| Recommendation chips | ❌ | `ImportWizardModal.tsx` | Avatar doporučení pro import config |
| Post-import summary | ❌ | `ImportWizardModal.tsx` | Po importu → avatar shrne co se stalo |
| "Re-extract" akce v PackDetail | ❌ | `PackParametersSection.tsx` | Tlačítko → volá nový AI service |
| Explanation mode | ❌ | `PackParametersSection.tsx` | Klik na parametr → avatar vysvětlí co to je |
| Batch re-extract | ❌ | `PacksPage.tsx` | Multi-select → avatar re-extrahuje parametry |

### 7.3 Settings UI transformace ❌ CHYBÍ

Stávající "AI Services" tab v Settings se přetransformuje na "AI Assistant".
Viz kompletní mockup v sekci "Settings UI — Transformace stávající AI záložky" výše.

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Přejmenovat tab "AI Services" → "AI Assistant" | ❌ | `SettingsPage.tsx` | Tab rename |
| Refactor `AIServicesSettings.tsx` → `AvatarSettings.tsx` | ❌ | `apps/web/src/components/modules/settings/` | Kompletní redesign dle mockupu |
| Master switch (enable/disable ALL AI) | ❌ | (v AvatarSettings) | Skryje FAB + všechny AI features |
| Provider section (active + available list) | ❌ | (v AvatarSettings) | Nahrazuje starý ProviderCard s Ollama |
| Avatar section (picker + safety mode) | ❌ | (v AvatarSettings) | AvatarPicker + SafetyModeSelector z knihovny |
| Batch AI section (extraction config) | ❌ | (v AvatarSettings) | Auto-extract toggle, cache, rule-based fallback |
| Advanced accordion (skills, MCP, config file) | ❌ | (v AvatarSettings) | Pro pokročilé — skills management, avatar.yaml editor link |
| Odstranit staré AI komponenty | ❌ | `ProviderCard.tsx`, `TaskPriorityConfig.tsx`, `AdvancedAISettings.tsx` | Nahrazeno novými v AvatarSettings |
| Avatar.yaml writer | ❌ | `apps/web/src/lib/avatar/settings.ts` | Settings UI → zapisuje do avatar.yaml přes API |
| Migrační wizard | ❌ | (v AvatarSettings) | Detekce starého settings.json AI configu → nabídnout migraci na avatar.yaml |

**Odstranění stávajících komponent (po migraci):**
- ~~`ProviderCard.tsx`~~ → nahrazeno provider list v AvatarSettings
- ~~`TaskPriorityConfig.tsx`~~ → odpadá (avatar-engine řeší provider selection sám)
- ~~`AdvancedAISettings.tsx`~~ → sloučeno do Advanced accordion
- ~~`ProviderStatusBadge.tsx`~~ → nahrazeno inline statusem z avatar-engine /api/avatar/providers
- ~~`ProviderInstallGuide.tsx`~~ → zachováno, přesunuto do AvatarSettings setup wizard

### 7.4 Testy — Iterace 7 ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Unit | `tests/unit/avatar/test_ai_service.py` | Parita s 72 testy z src/ai/ |
| Unit | `tests/unit/avatar/test_ai_cache_compat.py` | Cache backward compatibility |
| Unit | `tests/unit/avatar/test_ai_fields_compat.py` | _ai_fields + _extracted_by output |
| Integration | `tests/integration/test_ai_migration_smoke.py` | Full import flow s novým service |
| Integration | `tests/integration/test_ai_migration_parity.py` | Stejný input → srovnatelný output |
| Frontend | `apps/web/src/__tests__/AvatarSettings.test.tsx` | Settings UI |

---

## Iterace 8: Library Upgrade Management

**Cíl:** Bezpečný upgrade path pro avatar-engine.

### 8.1 Version management ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Version pinning | ❌ | `pyproject.toml`, `package.json` | Semver ranges: `^1.0.0` |
| Compatibility matrix | ❌ | `docs/AVATAR-COMPATIBILITY.md` | Které verze avatar-engine fungují s kterou verzí Synapse |
| Migration guide template | ❌ | `docs/AVATAR-UPGRADE.md` | Postup pro upgrade |
| Version check na startu | ❌ | `src/avatar/__init__.py` | Ověřit kompatibilní verzi, log warning |
| Frontend version check | ❌ | `apps/web/src/components/avatar/AvatarProvider.tsx` | Check `/api/avatar/version` |

### 8.2 Graceful degradation ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Backend: avatar-engine missing | ❌ | `apps/api/src/main.py` | Skip mount, warn, disable features |
| Backend: no CLI providers | ❌ | `src/avatar/ai_service.py` | Fallback to rule_based, log warning |
| Frontend: AI disabled (master switch) | ❌ | `AvatarProvider.tsx` | No FAB, no WS, no AI suggestions — zero footprint |
| Frontend: avatar API unavailable | ❌ | `AvatarProvider.tsx` | Hide FAB, show "AI unavailable" tooltip |
| Frontend: dual-mode audit | ❌ | Všechny AI-enhanced komponenty | Ověřit že KAŽDÁ má manuální alternativu |
| Partial functionality | ❌ | Oba | MCP server down → avatar works without tools |
| Provider unavailable | ❌ | Oba | No providers → show setup instructions |
| Rule-based always works | ❌ | `src/utils/parameter_extractor.py` | NESMÍ mít dependency na avatar-engine |

---

## Iterace 9: Production Polish & Documentation

**Cíl:** Production-ready, plná dokumentace.

### 9.1 Documentation ❌ CHYBÍ

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| User guide | ❌ | `docs/AVATAR-USER-GUIDE.md` | Jak používat AI avatara v Synapse |
| Developer guide | ❌ | `docs/AVATAR-DEV-GUIDE.md` | Jak přidávat MCP tools, skills |
| Theming guide | ❌ | `docs/AVATAR-THEMING.md` | CSS customization |
| MCP reference | ❌ | `docs/AVATAR-MCP-TOOLS.md` | Kompletní reference všech tools |
| Configuration reference | ❌ | `docs/AVATAR-CONFIG.md` | avatar.yaml reference |

### 9.2 E2E testy ❌ CHYBÍ

| Typ | Soubor | Popis |
|-----|--------|-------|
| Smoke | `tests/integration/test_avatar_e2e.py` | Full avatar lifecycle |
| E2E | `apps/web/src/__tests__/avatar-e2e.test.tsx` | Frontend E2E |

### 9.3 Performance & Monitoring ❌ CHYBÍ

| Úkol | Stav | Popis |
|------|------|-------|
| WebSocket reconnection | ❌ | Auto-reconnect s exponential backoff |
| Memory management | ❌ | Limity na message history, chat cleanup |
| Health monitoring | ❌ | Dashboard widget s avatar health |
| Metrics collection | ❌ | Response times, token usage, cost tracking display |

---

## Souhrnná struktura souborů (po dokončení)

```
synapse/
├── src/
│   ├── avatar/                           # NEW: Avatar Engine integration
│   │   ├── __init__.py                   # Config loader, version check
│   │   ├── skills.py                     # Skill loading, system prompt builder
│   │   └── mcp/                          # MCP servers for Synapse tools
│   │       ├── __init__.py
│   │       ├── __main__.py               # MCP server entry point
│   │       ├── store_server.py           # Pack, Inventory, Backup, Stats tools
│   │       ├── import_server.py          # Civitai import tools
│   │       ├── workflow_server.py        # ComfyUI workflow tools
│   │       └── dependency_server.py      # Model dependency tools
│   │   ├── ai_service.py                 # NEW: Batch AI via avatar-engine (replaces src/ai/)
│   └── ~~ai/~~                           # REMOVED in Iter 7 (migrated to src/avatar/)
│
├── apps/web/src/
│   ├── components/
│   │   ├── avatar/                       # NEW: Avatar UI components
│   │   │   ├── AvatarProvider.tsx        # Context + useAvatarChat wrapper
│   │   │   └── SuggestionChips.tsx       # Context-aware quick actions
│   │   ├── layout/
│   │   │   └── Layout.tsx                # MODIFIED: AvatarWidget + PermissionDialog
│   │   └── modules/
│   │       ├── AvatarPage.tsx            # NEW: Fullscreen chat page
│   │       └── settings/
│   │           └── AvatarSettings.tsx    # NEW: Avatar configuration UI
│   ├── hooks/
│   │   └── usePageContext.ts             # NEW: Page context detection
│   └── styles/
│       └── avatar-overrides.css          # NEW: CSS bridge/overrides
│
├── config/
│   ├── avatar.yaml.example               # NEW: Default avatar configuration
│   └── avatar/
│       └── skills/                       # NEW: Built-in skill files
│           ├── synapse-basics.md
│           ├── pack-management.md
│           ├── model-types.md
│           ├── generation-params.md
│           ├── dependency-resolution.md
│           ├── workflow-creation.md
│           ├── install-packs.md
│           ├── inventory-management.md
│           └── civitai-integration.md
│       └── workflows/                    # NEW: Workflow templates for MCP
│           ├── txt2img-sd15.json         # Default txt2img for SD 1.5
│           ├── txt2img-sdxl.json         # Default txt2img for SDXL
│           ├── txt2img-flux.json         # Default txt2img for Flux
│           ├── lora-sd15.json            # LoRA workflow for SD 1.5
│           ├── lora-sdxl.json            # LoRA workflow for SDXL
│           ├── controlnet-sd15.json      # ControlNet workflow
│           └── img2img-basic.json        # Basic img2img
│
├── tests/
│   ├── unit/avatar/                      # NEW: Avatar unit tests
│   │   ├── test_config.py
│   │   ├── test_skills.py
│   │   ├── test_mcp_tools.py
│   │   ├── test_mcp_import.py
│   │   ├── test_mcp_workflow.py
│   │   ├── test_mcp_dependency.py
│   │   ├── test_ai_service.py            # NEW: Parity tests (replaces src/ai/ tests)
│   │   ├── test_ai_cache_compat.py       # NEW: Cache backward compat
│   │   └── test_ai_fields_compat.py      # NEW: _ai_fields output compat
│   └── integration/
│       ├── test_avatar_mount.py          # NEW: Backend mount test
│       ├── test_mcp_store.py             # NEW: MCP store integration
│       ├── test_mcp_workflow.py          # NEW: Workflow generation integration
│       ├── test_mcp_dependency.py        # NEW: Dependency resolution integration
│       ├── test_mcp_advanced.py          # NEW: Multi-server orchestration
│       ├── test_ai_migration_smoke.py    # NEW: Import flow parity check
│       ├── test_ai_migration_parity.py   # NEW: Same input → comparable output
│       └── test_avatar_e2e.py            # NEW: E2E smoke test
│
└── docs/
    ├── AVATAR-USER-GUIDE.md              # NEW
    ├── AVATAR-DEV-GUIDE.md               # NEW
    ├── AVATAR-THEMING.md                 # NEW
    ├── AVATAR-MCP-TOOLS.md               # NEW
    ├── AVATAR-CONFIG.md                  # NEW
    ├── AVATAR-COMPATIBILITY.md           # NEW
    └── AVATAR-UPGRADE.md                 # NEW
```

---

## Implementační pravidla

### Pořadí iterací
1. **Iterace 1** (Foundation) → MUSÍ být první — bez ní nic nefunguje
2. **Iterace 2** (MCP Store) → MUSÍ být druhá — avatar bez tools je jen chatbot
3. **Iterace 3** (Skills) → Třetí — doménové znalosti zásadně zlepší kvalitu
4. **Iterace 4-7** → Mohou být v libovolném pořadí, ale doporučené je zachovat
5. **Iterace 8-9** → Polish — na konci

### Klíčové principy
- **Avatar-engine je READ-ONLY dependency** — nikdy nemodifikujeme zdrojáky knihovny
- **Vše Synapse-specifické** je v `src/avatar/` a konfiguracích
- **Graceful degradation** — Synapse MUSÍ fungovat bez avatar-engine (rule-based fallback)
- **src/ai/ bude NAHRAZENO** — Iterace 7 kompletně migruje na avatar-engine + odstraní src/ai/
- **_ai_fields kompatibilita** — výstupní formát pro frontend se NESMÍ změnit
- **Test coverage** — každá iterace má vlastní testy, parita s původními 72 testy
- **Verify before commit** — `./scripts/verify.sh` jako vždy

### Životní cyklus AI v Synapse
```
┌─────────────────────────────────────────────────────────────────────┐
│              AI in Synapse — Evolution Plan                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  FÁZE A (Iterace 1-6): Koexistence                                  │
│  ┌────────────────────────┐  ┌────────────────────────────────────┐ │
│  │ src/ai/ (STÁVAJÍCÍ)    │  │ src/avatar/ (NOVÉ)                 │ │
│  │ • Batch extraction     │  │ • Interactive chat (AvatarWidget)  │ │
│  │ • Ollama → Gemini →    │  │ • MCP tools (store, workflow, dep) │ │
│  │   Claude → rule_based  │  │ • Skills system                    │ │
│  │ • Cache + _ai_fields   │  │ • Context-aware UI                 │ │
│  └────────────────────────┘  └────────────────────────────────────┘ │
│        ↑ Import flow uses this        ↑ User-facing features        │
│                                                                      │
│  FÁZE B (Iterace 7): Plná migrace                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ src/avatar/ (JEDINÝ AI SYSTÉM)                               │   │
│  │ • AvatarAIService — batch operace přes engine.chat_sync()    │   │
│  │   Providers: Gemini CLI, Claude Code, Codex CLI              │   │
│  │   Fallback: rule_based (src/utils/parameter_extractor.py)    │   │
│  │   Cache: zachován (SHA-256[:16], TTL)                        │   │
│  │   Output: _ai_fields + _extracted_by (beze změny formátu!)   │   │
│  │ • Interactive chat (AvatarWidget) — beze změny               │   │
│  │ • MCP tools — nově včetně extract_parameters                 │   │
│  │ • Skills + Context — beze změny                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ~~src/ai/~~ ODSTRANĚNO po ověření parity                           │
│                                                                      │
│  CO ZMIZÍ: Ollama provider (avatar-engine ho nemá, není potřeba)    │
│  CO ZŮSTANE: rule_based fallback, cache, _ai_fields, _extracted_by  │
│  CO SE ZLEPŠÍ: robustnější runtime (ACP warm sessions, streaming)   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| avatar-engine breaking change | High | Semver pinning `^1.0.0`, compatibility matrix |
| Provider CLI not installed | Medium | Graceful degradation, setup wizard |
| WebSocket connection issues | Medium | Auto-reconnect, health checks, error boundary |
| MCP server crash | Low | Restart policy, isolated process, error events |
| CSS conflicts | Low | CSS custom properties bridge, isolated scope |
| Performance (WS overhead) | Low | Lazy connection, disconnect on idle |
| Large system prompt (too many skills) | Medium | Skill size limits, lazy loading, relevance filtering |
| **src/ai/ migrace — regrese** | **High** | Feature flag, paralelní běh, 72+ parity testů, smoke testy |
| **Ztráta Ollama provideru** | **Medium** | Gemini/Claude/Codex pokryjí vše; rule-based fallback pro offline |
| **_ai_fields output format change** | **High** | Strict output tests, frontend regression tests |
| **Dependency resolution quality** | Medium | Ranked candidates, user confirmation, manual override vždy dostupný |

---

## Success Criteria

### Iterace 1 (Foundation)
- [ ] Avatar FAB visible on every page
- [ ] CompactChat opens and connects via WebSocket
- [ ] Chat messages sent and received
- [ ] Graceful degradation when avatar-engine not installed
- [ ] All existing tests pass + new tests

### Iterace 2 (MCP Tools)
- [ ] Avatar can answer "How many packs do I have?"
- [ ] Avatar can list packs and show details
- [ ] Avatar can check inventory status
- [ ] MCP tools tested with mock Store

### Iterace 3 (Skills)
- [ ] Avatar knows what CFG Scale is
- [ ] Avatar can explain LoRA vs Checkpoint
- [ ] Avatar gives Synapse-specific advice
- [ ] Custom skills loaded from user directory

### Iterace 5 (Context)
- [ ] On PackDetail page, avatar knows which pack user is viewing
- [ ] Suggestion chips change per page
- [ ] Avatar can perform actions in context

### Iterace 6 (Advanced MCP)
- [ ] Avatar can generate a default ComfyUI workflow for a pack
- [ ] Avatar can find correct model for a dependency ("I need an SD 1.5 checkpoint")
- [ ] Dependency resolution dialog shows AI-ranked candidates with local/Civitai source
- [ ] User can assign dependency from AI suggestion with one click
- [ ] Workflow templates exist for SD 1.5, SDXL, Flux, LoRA, ControlNet

### Iterace 7 (src/ai/ Migration)
- [ ] AvatarAIService produces identical _ai_fields + _extracted_by output
- [ ] Cache backward compatible (existing cached results still work)
- [ ] Import flow uses new service — parameters extracted correctly
- [ ] 72+ parity tests all green
- [ ] Feature flag allows switching between old/new service
- [ ] src/ai/ directory removed after parity confirmed
- [ ] Settings UI shows Gemini/Claude/Codex (no Ollama)
- [ ] Rule-based fallback works when avatar-engine unavailable

---

*Last Updated: 2026-02-22*
*Status: PLANNING — čeká na schválení*
