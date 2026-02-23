# PLAN: Avatar Engine Integration into Synapse

**Version:** v3.0.0 (DEFINITIVNÍ přepis — jediný zdroj pravdy)
**Status:** ✅ KROKY 1-5 DOKONČENY — Avatar chat funguje end-to-end
**Created:** 2026-02-22
**Rewritten:** 2026-02-23
**Author:** raven2cz + Claude Opus 4.6
**Branch:** `feat/avatar-engine`
**Dependencies:** `avatar-engine[web]` (PyPI), `@avatar-engine/react` + `@avatar-engine/core` (npm)

---

## ⚠️ CO SE POKAZILO v1.0.0 (NEOPAKOVAT!)

Frontend iterace 1-4 vytvořily CUSTOM stub komponenty místo použití reálné knihovny:

| Soubor | Bylo (ŠPATNĚ) | Má být (SPRÁVNĚ) |
|--------|---------------|-------------------|
| `AvatarPage.tsx` (589ř) | Custom chat UI, `setTimeout(1000)` fake odpovědi | SMAZAT — fullscreen je interní mód AvatarWidget |
| `AvatarProvider.tsx` (69ř) | REST-only status check, žádný WebSocket | Wrapper nad `useAvatarChat(wsUrl)` — reálný WS |
| `AvatarFab.tsx` (71ř) | Custom FAB s `useNavigate('/avatar')` | SMAZAT — AvatarWidget má vlastní FAB interně |
| `package.json` | Žádná `@avatar-engine/*` dependency | `pnpm link` obou balíčků |
| `tailwind.config.js` | Žádný avatar preset | `presets: [avatarPreset]` + content scan |
| `vite.config.ts` | Proxy na `/api/avatar/engine/ws` (špatný endpoint) | `/api/avatar` proxy s `ws: true` |

**PRAVIDLO: NIKDY nevytvářet custom komponenty pro něco, co knihovna poskytuje!**
**PRAVIDLO: ŽÁDNÉ setTimeout — uživatel řídí vše přes STOP tlačítko (`chat.stopResponse()`)!**

---

## 🔴 KRITICKÁ SEKCE: Jak avatar-engine funguje (PŘEČÍST PO KAŽDÉM COMPACTINGU!)

Tato sekce obsahuje VŠECHNY poznatky nutné pro správnou integraci. Avatar-engine je
kompletní knihovna s vlastním UI — Synapse ji pouze POUŽÍVÁ, NIKDY neimplementuje vlastní.

### Kde knihovna žije

```
~/git/github/avatar-engine/
├── packages/
│   ├── core/                          # @avatar-engine/core (npm)
│   │   ├── dist/                      # ✅ BUILDNUTÉ — index.es.js (32KB), index.cjs.js (25KB)
│   │   └── package.json               # name: "@avatar-engine/core", v1.0.0
│   └── react/                         # @avatar-engine/react (npm)
│       ├── dist/                      # ✅ BUILDNUTÉ — index.es.js (1.3MB), style.css (6KB)
│       ├── tailwind-preset.js         # Tailwind preset pro host app
│       └── package.json               # name: "@avatar-engine/react", v1.0.0
├── avatar_engine/                     # Python backend (pip: avatar-engine[web])
│   └── web/server.py                  # create_api_app() — FastAPI app factory
├── examples/
│   └── web-demo/                      # ← KANONICKÝ PŘÍKLAD INTEGRACE
│       ├── App.tsx                    # 199 řádků — useAvatarChat + AvatarWidget
│       ├── main.tsx                   # Import styles + initAvatarI18n
│       ├── vite.config.ts            # Proxy config
│       └── public/avatars/           # 8 avatarů (~860KB)
└── README.md
```

### Architektura: AvatarWidget je MASTER KONTEJNER

```
App Root
├── useAvatarChat(wsUrl, options)     ← JEDEN hook, JEDEN WebSocket, volat JEDNOU v kořenu
│   └── Vrací: messages, sendMessage, stopResponse, connected, provider, model,
│              engineState, thinking, cost, permissionRequest, sendPermissionResponse,
│              switchProvider, resumeSession, newSession, uploadFile, removeFile,
│              isStreaming, safetyMode, error, diagnostic, ...
│
├── PermissionDialog                  ← SOUROZENEC AvatarWidget (MIMO widget!)
│   ├── request={chat.permissionRequest}
│   └── onRespond={chat.sendPermissionResponse}
│
└── AvatarWidget                      ← MASTER KONTEJNER (řídí VŠE interně)
    ├── Props: {...chat} + avatars + avatarBasePath + renderBackground + children
    │
    ├── INTERNÍ useWidgetMode()
    │   ├── mode: 'fab' | 'compact' | 'fullscreen'
    │   ├── Přepínání: Escape (dolů), Ctrl+Shift+A (fab↔compact), Ctrl+Shift+F (compact↔fullscreen)
    │   └── Persistuje do localStorage
    │
    ├── Když mode === 'fab'
    │   └── AvatarFab (plovoucí tlačítko, pulsing)
    │       └── onClick → openCompact()
    │
    ├── Když mode === 'compact'
    │   └── Compact Drawer (slide-up, resizable)
    │       ├── AvatarBust (animovaný avatar, toggleable Ctrl+Shift+H)
    │       ├── CompactHeader (provider dropdown, expand button)
    │       ├── CompactMessages (historie zpráv)
    │       └── CompactInput (input, file upload, send)
    │
    ├── Když mode === 'fullscreen'
    │   └── Fixed overlay (z-[2000]) — renderuje {children}
    │       └── To co host app poskytne: StatusBar + ChatPanel + CostTracker
    │
    └── renderBackground() — VŽDY viditelné za všemi módy
        └── Landing page, hlavní obsah aplikace
```

**KLÍČOVÉ FAKTY:**
1. **AvatarWidget řídí FAB/Compact/Fullscreen INTERNĚ** — žádná custom logika, žádný routing
2. **useAvatarChat se volá JEDNOU** v kořenu — jeden WebSocket přežívá přepínání módů
3. **PermissionDialog je MIMO AvatarWidget** — sourozenec na úrovni app root
4. **Fullscreen NENÍ route** — je to mód, `fixed inset-0 z-[2000]` overlay, children vždy v DOM
5. **Route `/avatar` NENÍ potřeba** — ale můžeme ji nechat jako alternativní vstupní bod
6. **Custom avatary** — prop `avatars={[...]}` + `avatarBasePath="/avatars"`
7. **Přepínání módů NIKDY nerestartuje WebSocket** — persistent connection

### Minimální integrace (CELÝ kód!)

```tsx
// ═══════════════════════════════════════════════════════════════════════
// TOTO JE KOMPLETNÍ INTEGRACE. Nic víc není potřeba.
// Převzato z examples/web-demo/App.tsx (kanonický příklad)
// ═══════════════════════════════════════════════════════════════════════

import { useRef } from 'react'
import {
  AvatarWidget, PermissionDialog, StatusBar, ChatPanel, CostTracker,
  useAvatarChat, useAvailableProviders,
} from '@avatar-engine/react'
import '@avatar-engine/react/styles.css'

function App() {
  const wsUrl = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/avatar/ws`

  // JEDEN hook, JEDEN WebSocket — volat JEDNOU
  const chat = useAvatarChat(wsUrl, { apiBase: '/api/avatar' })
  const providers = useAvailableProviders()
  const compactRef = useRef<(() => void) | null>(null)

  return (
    <>
      {/* 1. PermissionDialog — MIMO AvatarWidget */}
      <PermissionDialog
        request={chat.permissionRequest}
        onRespond={chat.sendPermissionResponse}
      />

      {/* 2. AvatarWidget — řídí FAB/Compact/Fullscreen interně */}
      <AvatarWidget
        messages={chat.messages}
        sendMessage={chat.sendMessage}
        stopResponse={chat.stopResponse}
        isStreaming={chat.isStreaming}
        connected={chat.connected}
        wasConnected={chat.wasConnected}
        initDetail={chat.initDetail}
        error={chat.error}
        diagnostic={chat.diagnostic}
        provider={chat.provider}
        model={chat.model}
        version={chat.version}
        engineState={chat.engineState}
        thinkingSubject={chat.thinking.active ? chat.thinking.subject : ''}
        toolName={chat.toolName}
        pendingFiles={chat.pendingFiles}
        uploading={chat.uploading}
        uploadFile={chat.uploadFile}
        removeFile={chat.removeFile}
        switching={chat.switching}
        activeOptions={chat.activeOptions}
        availableProviders={providers}
        switchProvider={chat.switchProvider}
        onCompactModeRef={compactRef}
        avatarBasePath="/avatars"
        renderBackground={({ showFabHint }) => (
          <div>{/* Hlavní obsah aplikace */}</div>
        )}
      >
        {/* 3. Fullscreen children — StatusBar + ChatPanel */}
        <StatusBar
          connected={chat.connected}
          provider={chat.provider}
          model={chat.model}
          version={chat.version}
          cwd={chat.cwd}
          engineState={chat.engineState as any}
          capabilities={chat.capabilities}
          sessionId={chat.sessionId}
          sessionTitle={chat.sessionTitle}
          cost={chat.cost}
          switching={chat.switching}
          activeOptions={chat.activeOptions}
          availableProviders={providers}
          onSwitch={chat.switchProvider}
          onResume={chat.resumeSession}
          onNewSession={chat.newSession}
          onCompactMode={() => compactRef.current?.()}
        />
        <ChatPanel
          messages={chat.messages}
          onSend={chat.sendMessage}
          onStop={chat.stopResponse}
          onClear={chat.clearHistory}
          isStreaming={chat.isStreaming}
          connected={chat.connected}
          pendingFiles={chat.pendingFiles}
          uploading={chat.uploading}
          onUpload={chat.uploadFile}
          onRemoveFile={chat.removeFile}
        />
      </AvatarWidget>
    </>
  )
}
```

### useAvatarChat — kompletní return type

```typescript
interface UseAvatarChatReturn {
  // Chat
  messages: ChatMessage[]
  sendMessage: (text: string, attachments?: UploadedFile[]) => void
  stopResponse: () => void
  clearHistory: () => void
  isStreaming: boolean

  // Connection
  connected: boolean
  wasConnected: boolean
  initDetail: string
  switching: boolean

  // Session
  sessionId: string | null
  sessionTitle: string | null
  provider: string
  model: string | null
  version: string
  cwd: string

  // Engine state
  engineState: string              // 'idle' | 'thinking' | 'responding' | 'tool_executing' | 'waiting_approval' | 'error'
  thinking: { active: boolean; phase: string; subject: string; startedAt: number }
  cost: { totalCostUsd: number; totalInputTokens: number; totalOutputTokens: number }
  capabilities: ProviderCapabilities
  toolName: string | undefined
  safetyMode: SafetyMode           // 'safe' | 'ask' | 'unrestricted'

  // Errors
  error: string | null
  diagnostic: string | null

  // ACP (Approval Control Protocol)
  permissionRequest: PermissionRequest | null
  sendPermissionResponse: (requestId: string, optionId: string, cancelled: boolean) => void

  // Provider switching
  switchProvider: (provider: string, model?: string, options?: Record<string, string | number>) => void
  resumeSession: (sessionId: string) => void
  newSession: () => void
  activeOptions: Record<string, string | number>

  // File upload
  pendingFiles: UploadedFile[]
  uploading: boolean
  uploadFile: (file: File) => Promise<UploadedFile | null>
  removeFile: (fileId: string) => void
}

interface AvatarChatOptions {
  apiBase?: string                    // Default: '/api/avatar'
  initialProvider?: string            // Auto-switch on connect
  initialModel?: string
  initialOptions?: Record<string, string | number>
  onResponse?: (message: ChatMessage) => void
}
```

### Instalace do Synapse

```bash
# 1. Link balíčky (lokální dev — buildnuté dist/ jsou ready)
cd /home/box/git/github/synapse/apps/web
pnpm link ~/git/github/avatar-engine/packages/react
pnpm link ~/git/github/avatar-engine/packages/core

# 2. Peer dependencies (react-markdown, syntax highlighter)
pnpm add react-markdown react-syntax-highlighter remark-gfm
pnpm add -D @types/react-syntax-highlighter

# 3. Avatar obrázky (8 avatarů, ~860KB)
cp -r ~/git/github/avatar-engine/examples/web-demo/public/avatars apps/web/public/
```

### Konfigurace souborů

**tailwind.config.js:**
```javascript
import avatarPreset from '@avatar-engine/react/tailwind-preset'

export default {
  presets: [avatarPreset],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './node_modules/@avatar-engine/react/dist/**/*.js',  // ← KRITICKÉ!
  ],
  // ... zbytek Synapse configu
}
```

**vite.config.ts — proxy:**
```typescript
server: {
  proxy: {
    '/api/avatar/ws': {          // WebSocket MUSÍ být první (specifičtější match)
      target: 'ws://localhost:8000',
      ws: true,
    },
    '/api': {                     // REST (včetně /api/avatar/*)
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

**main.tsx — import stylů:**
```typescript
import '@avatar-engine/react/styles.css'  // ← PŘED vlastními styly!
import './index.css'
```

**i18n — inicializace:**
```typescript
import { initAvatarI18n } from '@avatar-engine/core'
initAvatarI18n()  // Standalone — avatar má vlastní i18n instance s en+cs
```

### CSS bridge — avatar-overrides.css

```css
:root {
  /* Synapse a avatar-engine sdílí STEJNOU paletu — tyto hodnoty jsou kompatibilní */
  --ae-accent-rgb: 99 102 241;         /* synapse #6366f1 */
  --ae-pulse-rgb: 139 92 246;          /* pulse #8b5cf6 */
  --ae-neural-rgb: 6 182 212;          /* neural #06b6d4 */
  --ae-bg-obsidian-rgb: 10 10 15;
  --ae-bg-darker-rgb: 15 15 23;
  --ae-bg-deep-rgb: 18 18 26;
  --ae-bg-base-rgb: 19 19 27;
  --ae-bg-dark-rgb: 22 22 31;
  --ae-bg-mid-rgb: 26 26 46;
  --ae-bg-light-rgb: 42 42 66;
  --ae-text-primary-rgb: 248 250 252;
  --ae-text-secondary-rgb: 148 163 184;
  --ae-text-muted-rgb: 100 116 139;
}
```

### Custom avatary pro Synapse

```typescript
import { AVATARS } from '@avatar-engine/core'
import type { AvatarConfig } from '@avatar-engine/core'

// Vlastní Synapse avatar (pokud budeme mít bust obrázky)
const synapseAvatar: AvatarConfig = {
  id: 'synapse',
  name: 'Synapse',
  fullName: 'Synapse AI Assistant',
  busts: {
    idle: 'idle.webp',
    thinking: 'thinking.webp',
    speaking: 'speaking.webp',
  },
}

// Použít knihovní avatary + vlastní
const avatars = [synapseAvatar, ...AVATARS]
// AvatarWidget: avatars={avatars} avatarBasePath="/avatars"
// Obrázky v: apps/web/public/avatars/synapse/idle.webp, thinking.webp, speaking.webp
// Knihovní obrázky v: apps/web/public/avatars/af_bella/speaking.webp, atd.
```

### Knihovní exporty — kompletní seznam

**@avatar-engine/react — 22 komponent:**
`AvatarWidget`, `ChatPanel`, `CompactChat`, `CompactHeader`, `CompactInput`, `CompactMessages`,
`StatusBar`, `ProviderModelSelector`, `SessionPanel`, `MessageBubble`, `MarkdownContent`,
`ThinkingIndicator`, `ToolActivity`, `PermissionDialog`, `SafetyModeSelector`, `SafetyModal`,
`AvatarBust`, `AvatarFab`, `AvatarPicker`, `AvatarLogo`, `CostTracker`, `BreathingOrb`, `OptionControl`

**@avatar-engine/react — 7 hooků:**
`useAvatarChat`, `useAvatarWebSocket`, `useWidgetMode`, `useAvatarBust`,
`useFileUpload`, `useAvailableProviders`, `useAvatarThumb`

**@avatar-engine/core — typy a utility:**
`avatarReducer`, `parseServerMessage`, `initialAvatarState`, `AvatarClient`,
`createChatMessage`, `createStopMessage`, `createSwitchMessage`, `createPermissionResponse`,
`PROVIDERS`, `AVATARS`, `DEFAULT_AVATAR_ID`, `getAvatarById`, `getAvatarBasePath`,
`initAvatarI18n`, `changeLanguage`, `getCurrentLanguage`,
`SafetyMode`, `EngineState`, `BridgeState`, `ThinkingPhase`, `ActivityStatus`,
`ChatMessage`, `CostInfo`, `ThinkingInfo`, `ToolInfo`, `PermissionRequest`,
`ProviderCapabilities`, `ChatAttachment`, `UploadedFile`, `AvatarConfig`, `WidgetMode`,
`LS_BUST_VISIBLE`, `LS_WIDGET_MODE`, `LS_COMPACT_HEIGHT`, `LS_COMPACT_WIDTH`,
`LS_SELECTED_AVATAR`, `LS_HINTS_SHOWN`, `LS_DEFAULT_MODE`, `LS_LANGUAGE`

### Python backend — embedding

```python
# src/avatar/routes.py — try_mount_avatar_engine()
from avatar_engine.web.server import create_api_app

avatar_app = create_api_app(
    provider=config.provider,          # "gemini" | "claude" | "codex"
    config_path=str(config.config_path),
    working_dir=str(config.working_dir),
    system_prompt=build_system_prompt(config),
)
app.mount("/api/avatar", avatar_app)
# Poskytuje: REST endpointy + WebSocket na /api/avatar/ws
```

---

## Iterace 1: Foundation — Backend mount + Frontend widget

**Cíl:** Avatar Engine běží jako součást Synapse, uživatel vidí FAB a může reálně chatovat.

### 1.1 Backend ✅ HOTOVO (31 testů, 3 review)

| Soubor | Řádků | Stav | Popis |
|--------|-------|------|-------|
| `src/avatar/__init__.py` | 26 | ✅ | Feature flag: `AVATAR_ENGINE_AVAILABLE`, `AVATAR_ENGINE_VERSION` |
| `src/avatar/config.py` | 208 | ✅ | YAML config loader, provider validace, path resolution |
| `src/avatar/routes.py` | 226 | ✅ | 6 REST endpointů + `try_mount_avatar_engine()` |
| `config/avatar.yaml.example` | 58 | ✅ | Vzorová konfigurace |

**Reviews:** Claude ✅ Gemini ✅ Codex ✅

### 1.2 Frontend ✅ PŘEDĚLÁNO (KROK 1)

**Soubory ke SMAZÁNÍ:**
- ~~`AvatarFab.tsx`~~ (71ř) — knihovna má vlastní FAB v AvatarWidget
- ~~`AvatarPage.tsx`~~ (589ř) — custom chat s setTimeout fake — SMAZAT CELÝ

**Soubory k PŘEPSÁNÍ:**
- `AvatarProvider.tsx` — z REST-only stubu na wrapper nad `useAvatarChat(wsUrl)`
- `Layout.tsx` — přidat `<AvatarWidget>` + `<PermissionDialog>`

**Nové soubory:**
- `apps/web/src/styles/avatar-overrides.css` — CSS bridge

**Soubory k ÚPRAVĚ:**
- `package.json` — pnpm link @avatar-engine/react + @avatar-engine/core
- `tailwind.config.js` — přidat avatarPreset + content scan
- `vite.config.ts` — opravit WS proxy
- `main.tsx` — import `@avatar-engine/react/styles.css`
- `i18n/index.ts` — `initAvatarI18n()`
- `App.tsx` — ~~smazat route `/avatar`~~ nebo zachovat jako redirect/landing

**Assets:**
- `apps/web/public/avatars/` — zkopírovat z `~/git/github/avatar-engine/examples/web-demo/public/avatars/`

| Krok | Úkol | Detail |
|------|------|--------|
| 1 | Instalace balíčků | `pnpm link` react + core, `pnpm add react-markdown react-syntax-highlighter remark-gfm` |
| 2 | Tailwind preset | `presets: [avatarPreset]`, content scan `node_modules/@avatar-engine/react/dist/**/*.js` |
| 3 | Vite proxy | `/api/avatar/ws` → `ws://localhost:8000` (ws:true), `/api` → `http://localhost:8000` |
| 4 | CSS import | `import '@avatar-engine/react/styles.css'` v main.tsx PŘED vlastními styly |
| 5 | CSS bridge | Vytvořit `avatar-overrides.css` s `--ae-*` variables (viz kritická sekce) |
| 6 | i18n | `initAvatarI18n()` v i18n/index.ts |
| 7 | Avatar obrázky | `cp -r ~/git/github/avatar-engine/examples/web-demo/public/avatars apps/web/public/` |
| 8 | SMAZAT AvatarFab.tsx | Celý soubor — knihovna řídí FAB interně |
| 9 | SMAZAT AvatarPage.tsx | Celý soubor — fullscreen je interní mód AvatarWidget |
| 10 | PŘEPSAT AvatarProvider.tsx | `useAvatarChat(wsUrl, {apiBase: '/api/avatar'})` + context |
| 11 | PŘEPSAT Layout.tsx | `<AvatarWidget {...chat}>` children `</AvatarWidget>` + `<PermissionDialog>` |
| 12 | Upravit App.tsx | Smazat import AvatarPage, ~~route `/avatar`~~ nebo nechat jako fallback |
| 13 | Upravit Sidebar.tsx | Odkaz na avatar → buď smazat (FAB stačí) nebo nechat jako fullscreen trigger |

**Detail AvatarProvider.tsx (NOVÝ):**
```tsx
import { createContext, useContext, useMemo, useRef } from 'react'
import { useAvatarChat, useAvailableProviders } from '@avatar-engine/react'
import type { UseAvatarChatReturn } from '@avatar-engine/react'

interface AvatarContextValue {
  chat: UseAvatarChatReturn
  providers: Set<string> | null
  compactRef: React.MutableRefObject<(() => void) | null>
}

const AvatarContext = createContext<AvatarContextValue | null>(null)

export function AvatarProvider({ children }: { children: React.ReactNode }) {
  const wsUrl = useMemo(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${location.host}/api/avatar/ws`
  }, [])

  const chat = useAvatarChat(wsUrl, { apiBase: '/api/avatar' })
  const providers = useAvailableProviders()
  const compactRef = useRef<(() => void) | null>(null)

  return (
    <AvatarContext.Provider value={{ chat, providers, compactRef }}>
      {children}
    </AvatarContext.Provider>
  )
}

export function useAvatar() {
  const ctx = useContext(AvatarContext)
  if (!ctx) throw new Error('useAvatar must be used within AvatarProvider')
  return ctx
}
```

**Detail Layout.tsx (NOVÝ):**
```tsx
import { useEffect } from 'react'
import { useLocation, Outlet } from 'react-router-dom'
import { AvatarWidget, PermissionDialog, StatusBar, ChatPanel } from '@avatar-engine/react'
import { AvatarProvider, useAvatar } from '../avatar/AvatarProvider'
import { usePageContextStore } from '../../stores/pageContextStore'

function LayoutInner() {
  const { chat, providers, compactRef } = useAvatar()
  const { pathname } = useLocation()

  // Track page context for suggestions (Iterace 5)
  useEffect(() => {
    usePageContextStore.getState().setContext(pathname)
  }, [pathname])

  return (
    <div className="min-h-screen bg-obsidian">
      {/* PermissionDialog — MIMO AvatarWidget */}
      <PermissionDialog
        request={chat.permissionRequest}
        onRespond={chat.sendPermissionResponse}
      />

      {/* AvatarWidget — řídí FAB/Compact/Fullscreen INTERNĚ */}
      <AvatarWidget
        messages={chat.messages}
        sendMessage={chat.sendMessage}
        stopResponse={chat.stopResponse}
        isStreaming={chat.isStreaming}
        connected={chat.connected}
        wasConnected={chat.wasConnected}
        initDetail={chat.initDetail}
        error={chat.error}
        diagnostic={chat.diagnostic}
        provider={chat.provider}
        model={chat.model}
        version={chat.version}
        engineState={chat.engineState}
        thinkingSubject={chat.thinking.active ? chat.thinking.subject : ''}
        toolName={chat.toolName}
        pendingFiles={chat.pendingFiles}
        uploading={chat.uploading}
        uploadFile={chat.uploadFile}
        removeFile={chat.removeFile}
        switching={chat.switching}
        activeOptions={chat.activeOptions}
        availableProviders={providers}
        switchProvider={chat.switchProvider}
        onCompactModeRef={compactRef}
        avatarBasePath="/avatars"
        renderBackground={() => (
          <div className="min-h-screen bg-obsidian flex flex-col">
            <Header />
            <div className="flex flex-1">
              <Sidebar />
              <main className="flex-1 p-6"><Outlet /></main>
            </div>
            <ToastContainer />
          </div>
        )}
      >
        {/* Fullscreen children */}
        <StatusBar
          connected={chat.connected}
          provider={chat.provider}
          model={chat.model}
          version={chat.version}
          cwd={chat.cwd}
          engineState={chat.engineState as any}
          capabilities={chat.capabilities}
          sessionId={chat.sessionId}
          sessionTitle={chat.sessionTitle}
          cost={chat.cost}
          switching={chat.switching}
          activeOptions={chat.activeOptions}
          availableProviders={providers}
          onSwitch={chat.switchProvider}
          onResume={chat.resumeSession}
          onNewSession={chat.newSession}
          onCompactMode={() => compactRef.current?.()}
        />
        <ChatPanel
          messages={chat.messages}
          onSend={chat.sendMessage}
          onStop={chat.stopResponse}
          onClear={chat.clearHistory}
          isStreaming={chat.isStreaming}
          connected={chat.connected}
          pendingFiles={chat.pendingFiles}
          uploading={chat.uploading}
          onUpload={chat.uploadFile}
          onRemoveFile={chat.removeFile}
        />
      </AvatarWidget>
    </div>
  )
}

export function Layout() {
  return (
    <AvatarProvider>
      <LayoutInner />
    </AvatarProvider>
  )
}
```

### 1.3 Testy — Iterace 1 Frontend ✅ HOTOVO (59 testů: 24 unit + 22 integration + 13 smoke)

| Typ | Soubor | Co testuje |
|-----|--------|------------|
| Unit | `AvatarProvider.test.ts` | WS URL construction, context creation |
| Unit | `AvatarLayout.test.ts` | Widget rendering, PermissionDialog přítomnost |
| Integration | `avatar-widget-integration.test.ts` | Provider → Widget → Layout wiring |
| Smoke | `avatar-widget-smoke.test.ts` | Full lifecycle: render → connect check → fallback |

---

## Iterace 2: MCP Server — Synapse Store Tools ✅ HOTOVO (84 testů, 3 review)

| Soubor | Řádků | Popis |
|--------|-------|-------|
| `src/avatar/mcp/store_server.py` | 598 | 10 MCP tools s FastMCP |
| `src/avatar/mcp/__main__.py` | — | Entry point |
| `src/avatar/mcp/__init__.py` | — | Package init |

**10 tools:** list_packs, get_pack_details, search_packs, get_pack_parameters,
get_inventory_summary, find_orphan_blobs, find_missing_blobs, get_backup_status,
check_pack_updates, get_storage_stats

**Reviews:** Claude ✅ Gemini ✅ Codex ✅

---

## Iterace 3: Skills System ✅ HOTOVO (45 testů, 3 review)

| Soubor | Řádků | Popis |
|--------|-------|-------|
| `src/avatar/skills.py` | 132 | Loader + build_system_prompt() |
| `config/avatar/skills/*.md` | 9 souborů | synapse-basics, pack-management, model-types, generation-params, dependency-resolution, workflow-creation, install-packs, inventory-management, civitai-integration |

**Reviews:** Claude ✅ Gemini ✅ Codex ✅

---

## Iterace 4: Custom Avatars & Settings UI

### 4.1 Backend ✅ HOTOVO

| Soubor | Stav | Popis |
|--------|------|-------|
| `routes.py /avatars` | ✅ | 8 built-in + custom avatary, symlink protection, 1MB guard |

### 4.2 Settings UI (REST) ✅ HOTOVO

| Soubor | Stav | Popis |
|--------|------|-------|
| `AvatarSettings.tsx` | ✅ | ~520ř, provider list, safety mode, skills info |
| `SettingsPage.tsx` | ✅ | "AI Assistant" tab |
| i18n klíče | ✅ | en.json + cs.json |

### 4.3 Knihovní komponenty v Settings ✅ HOTOVO (KROK 2)

| Úkol | Stav | Detail |
|------|------|--------|
| `<AvatarPicker>` | ✅ | Nahradit hardcoded avatar list v Settings → `<AvatarPicker avatars={...} />` z knihovny |
| `<SafetyModeSelector>` | ✅ | Nahradit custom radio buttons → knihovní selector |
| `<AvatarBust>` preview | ✅ | Přidat animated bust preview do Settings |
| `<ProviderModelSelector>` | ❌ | Nahradit custom select pro provider/model → knihovní dropdown |
| Synapse avatar bust obrázky | ❌ | Vytvořit/získat idle.webp, thinking.webp, speaking.webp pro Synapse avatar |

**Testy:** 72 testů ✅ (27 FE unit + 27 BE unit + 10 integration + 8 smoke)
**Reviews:** Claude ✅ Gemini ✅ Codex ✅

---

## Iterace 5: Context-Aware Integration

### 5.1 Logika ✅ HOTOVO (88 testů, 3 review)

| Soubor | Řádků | Stav | Popis |
|--------|-------|------|-------|
| `pageContextStore.ts` | 101 | ✅ | Zustand store, URL → PageId, trailing slash, decodeURI safety |
| `context.ts` | 59 | ✅ | buildContextPayload, formatContextForMessage |
| `suggestions.ts` | 71 | ✅ | PAGE_SUGGESTIONS, resolveSuggestions, FALLBACK_SUGGESTIONS |
| `SuggestionChips.tsx` | 31 | ✅ | Per-page chips s useShallow |
| 5 test souborů | 88 testů | ✅ | Unit + integration + smoke |

### 5.2 Context → sendMessage ✅ HOTOVO

Po předělání frontendu se kontext pošle jako prefix ve zprávě:

```typescript
// V Layout.tsx nebo AvatarProvider — wrapper nad chat.sendMessage
function sendWithContext(text: string) {
  const { previous } = usePageContextStore.getState()
  const payload = buildContextPayload(previous)
  const prefix = formatContextForMessage(payload)
  chat.sendMessage(prefix ? `${prefix}\n\n${text}` : text)
}
```

### 5.3 SuggestionChips integrace ✅ HOTOVO (KROK 3) — chips v fullscreen children, viditelné při prázdné konverzaci

SuggestionChips.tsx je hotový, ale musí se integrovat do AvatarWidget:
- Buď jako součást `renderBackground` (chips viditelné na stránce)
- Nebo přes custom wrapper nad `ChatPanel` (chips v chatu)
- Detail závisí na tom, jak AvatarWidget renderuje compact vs fullscreen

**Reviews:** Claude ✅ Gemini ✅ Codex ✅

---

## IMPLEMENTAČNÍ POŘADÍ

```
KROK 1: Iterace 1.2 REDO — Frontend foundation                    ✅ HOTOVO
         • pnpm link, tailwind, vite, css, i18n, avatar images
         • Smazat AvatarFab.tsx, AvatarPage.tsx
         • Přepsat AvatarProvider.tsx, Layout.tsx
         • Upravit App.tsx, Sidebar.tsx, main.tsx

KROK 2: Iterace 4.3 — Knihovní komponenty v Settings              ✅ HOTOVO
         • AvatarPicker, SafetyModeSelector, AvatarBust v AvatarSettings.tsx

KROK 3: Iterace 5.2+5.3 — Context → sendMessage + SuggestionChips ✅ HOTOVO
         • Wrapper sendWithContext()
         • SuggestionChips integrace do chatu

KROK 4: Testy (Iterace 1.3)                                       ✅ HOTOVO (59 testů)
         • Unit + integration + smoke pro frontend widget

KROK 5: Review (Claude + Gemini + Codex)                           ✅ HOTOVO (Claude + Gemini)

── MILESTONE: Avatar chat funguje end-to-end ──────────────────────

KROK 6+: Iterace 6 — Advanced MCP (workflow, dependencies, import)
KROK 7+: Iterace 7 — Migrace src/ai/ → avatar-engine
KROK 8+: Iterace 8-9 — Library upgrade, polish, docs
```

---

## Iterace 6-9 (BUDOUCÍ — beze změny oproti v1.0.0)

### Iterace 6: Advanced MCP Tools ✅ HOTOVO (57 testů, 3 review)

Rozšíření store_server.py o 11 nových tools (celkem 21). Čistě backendová změna.

| Skupina | Tools | Popis |
|---------|-------|-------|
| Civitai (4) | search_civitai, analyze_civitai_model, compare_model_versions, import_civitai_model | Hledání, analýza, porovnání verzí, import (WRITE) |
| Workflow (4) | scan_workflow, scan_workflow_file, check_workflow_availability, list_custom_nodes | Analýza ComfyUI workflow, cross-ref s inventářem |
| Dependencies (3) | resolve_workflow_dependencies, find_model_by_hash, suggest_asset_sources | Resoluce zdrojů, hash lookup, source suggestions |

| Soubor | Řádků | Popis |
|--------|-------|-------|
| `src/avatar/mcp/store_server.py` | 1290 | 21 MCP tools (10 store + 11 nových) |
| `src/avatar/mcp/__init__.py` | 26 | Docstring update |
| `tests/helpers/fixtures.py` | 330 | +search_models, +get_model_by_hash, +parse_civitai_url, +_FakeVersionResult |

**Security:** `scan_workflow_file` omezeno na `.json` extension (Gemini+Codex review nález).
**Reviews:** Claude ✅ (1 fix: dead code), Gemini ✅ (1 fix: path traversal), Codex ✅ (2 fixes: path security + unresolved node logic)

### Iterace 7: Migrace src/ai/ → Avatar Engine ❌
- AvatarAIService (batch operace přes engine.chat_sync)
- Zachovat _ai_fields + _extracted_by kompatibilitu
- Feature flag pro přepínání old/new
- Rule-based fallback zůstává
- Smazat src/ai/ po ověření parity

### Iterace 8: Library Upgrade Management ❌
- Version pinning, compatibility matrix, migration guide

### Iterace 9: Production Polish & Documentation ❌
- User guide, dev guide, theming guide, MCP reference
- E2E testy, performance monitoring

---

## Souhrn testů

| Iterace | Backend | Frontend | Celkem | Stav |
|---------|---------|----------|--------|------|
| 1 Backend | 31 | — | 31 | ✅ |
| 1 Frontend | — | 59 | 59 | ✅ |
| 2 MCP | 84 | — | 84 | ✅ |
| 3 Skills | 45 | — | 45 | ✅ |
| 4 Avatars | 45 | 27 | 72 | ✅ |
| 5 Context | — | 88 | 88 | ✅ |
| 6 MCP Advanced | 57 | — | 57 | ✅ |
| **CELKEM** | **262** | **174** | **436** | ✅ |

---

## Soubory — akce

### SMAZAT
| Soubor | Důvod |
|--------|-------|
| `apps/web/src/components/avatar/AvatarFab.tsx` | Knihovna má vlastní FAB v AvatarWidget |
| `apps/web/src/components/modules/AvatarPage.tsx` | Fullscreen je interní mód AvatarWidget |

### PŘEPSAT
| Soubor | Důvod |
|--------|-------|
| `apps/web/src/components/avatar/AvatarProvider.tsx` | REST stub → useAvatarChat wrapper |
| `apps/web/src/components/layout/Layout.tsx` | Přidat AvatarWidget + PermissionDialog + renderBackground |

### UPRAVIT
| Soubor | Co změnit |
|--------|-----------|
| `apps/web/package.json` | pnpm link + peer deps |
| `apps/web/tailwind.config.js` | avatarPreset + content scan |
| `apps/web/vite.config.ts` | WS proxy fix |
| `apps/web/src/main.tsx` | import styles.css |
| `apps/web/src/i18n/index.ts` | initAvatarI18n() |
| `apps/web/src/App.tsx` | Smazat AvatarPage import + route |
| `apps/web/src/components/layout/Sidebar.tsx` | Upravit AI Assistant link |

### NOVÉ
| Soubor | Účel |
|--------|------|
| `apps/web/src/styles/avatar-overrides.css` | CSS bridge --ae-* variables |
| `apps/web/public/avatars/*` | Avatar bust obrázky (kopie z avatar-engine) |

### ZACHOVAT (beze změny)
| Soubor | Důvod |
|--------|-------|
| `pageContextStore.ts` | Čistá logika ✅ |
| `context.ts` | Čistá logika ✅ |
| `suggestions.ts` | Čistá logika ✅ |
| `SuggestionChips.tsx` | Čistá logika ✅ |
| `src/avatar/config.py` | Backend ✅ |
| `src/avatar/routes.py` | Backend ✅ |
| `src/avatar/skills.py` | Backend ✅ |
| `src/avatar/mcp/store_server.py` | Backend ✅ |
| `AvatarSettings.tsx` | REST settings ✅ |
| Všech 320 existujících testů | ✅ |

---

## MANDATORY: Post-Iteration Review & Test Pyramid

**Platí pro KAŽDOU iteraci. NESMÍ se přeskočit.**

1. **Claude review** — přečíst KAŽDÝ nový/změněný soubor
2. **Gemini review** — `gemini -p "Review files <seznam> for bugs, security, error handling" --yolo`
3. **Codex review** — `codex review --commit <SHA>` nebo `codex exec "Review these files: <seznam>"`
4. **Test pyramid:**
   - Unit (30-60): error paths, edge cases, all branches
   - Integration (8-15): reálné komponenty, mockovaný HTTP
   - Smoke (3-7): celý lifecycle
5. **Verifikace:** `./scripts/verify.sh`

---

*Last Updated: 2026-02-23 (KROKY 1-5 + Iterace 6 dokončeny)*
*Status: Iterace 1-6 ✅. 21 MCP tools, 436 testů. Frontend PŘEDĚLÁNO s @avatar-engine/react.*
