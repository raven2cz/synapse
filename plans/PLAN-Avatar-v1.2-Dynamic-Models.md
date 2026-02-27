# Plan: Integrace Avatar Engine v1.2 — Dynamic Models + Claude additional_dirs

**Status:** 🚧 IMPLEMENTACE
**Datum:** 2026-02-26
**Závislost:** avatar-engine branch `feature/v1.2-stability` (lokální npm link)

---

## Motivace

Avatar Engine v1.2 přináší dvě klíčové funkce:

1. **Dynamické modely** — Modely se mění rychle (Gemini je už na 3.1). Avatar Engine scrapuje dokumentační stránky providerů a vrací aktuální seznamy modelů. Model dropdown v Synapse se aktualizuje automaticky — hardcodované modely v YAML example jsou jen initial fallback, reálně se modely vždy načítají dynamicky z backendu.
2. **Claude additional_dirs** — Claude Code nemůže přistupovat k `~/.synapse`, protože working_dir je jinde. Nový parametr `additional_dirs` řeší přístup k datům Synapse.

### Jak dynamické modely fungují (3-tier fallback)

1. **Okamžitě:** Statické `PROVIDERS` z `@avatar-engine/core` (hardcoded fallback)
2. **< 1ms:** `localStorage` cache z posledního úspěšného fetch (24h TTL)
3. **Pozadí:** `GET /api/avatar/models` — backend scrapuje provider docs, vrátí aktuální modely

Frontend hook `useDynamicModels(apiBase)` vrací `ProviderConfig[]` — okamžitě s fallback, pak se asynchronně aktualizuje po fetch. Při chybě scrapingu emituje `CustomEvent`, hook `useModelDiscoveryErrors()` ho zachytí pro toast.

---

## Krok 0: Lokální napojení na avatar-engine

Avatar Engine ještě NENÍ publikován jako v1.2. Napojíme se lokálně přes npm link + pip install -e.

### 0.1: Python backend

```bash
# V avatar-engine repo:
cd ~/git/github/avatar-engine
uv pip install -e ".[web]"
```

Tím se nainstaluje lokální verze včetně nového `model_discovery` modulu.

### 0.2: Frontend (npm link)

```bash
# V avatar-engine repo — build + link:
cd ~/git/github/avatar-engine
pnpm build --filter @avatar-engine/core --filter @avatar-engine/react
cd packages/core && pnpm link --global && cd ../..
cd packages/react && pnpm link --global && cd ../..

# V synapse repo — připojit:
cd ~/git/github/synapse/apps/web
pnpm link --global @avatar-engine/core @avatar-engine/react
```

### 0.3: Ověření

```bash
# Python:
python -c "from avatar_engine.web.model_discovery import fetch_models; print('OK')"

# Frontend:
ls -la node_modules/@avatar-engine/core  # → symlink na avatar-engine/packages/core
ls -la node_modules/@avatar-engine/react  # → symlink na avatar-engine/packages/react
```

---

## Krok 1: Aktualizovat avatar.yaml.example

**Soubor:** `config/avatar.yaml.example`

- Přidat `additional_dirs` do claude sekce
- Přidat komentář, že `model:` je jen initial default — dropdown se aktualizuje dynamicky
- Odebrat hardcoded model u codex (prázdný = provider default, dynamicky se doplní)

---

## Krok 2: Ověřit průchod `additional_dirs` v config.py

**Soubor:** `src/avatar/config.py`

Avatar-engine čte `additional_dirs` přímo z YAML přes `config_path` (celý YAML se předá engine).
Synapse `config.py` nefiltruje provider kwargs — **NENÍ TŘEBA MĚNIT**.

Ověřeno: `load_avatar_config()` ukládá `_raw` (celý YAML dict) a `config_path`. Při mountu
se předá `config_path` do `create_avatar_app()` → engine parsuje YAML sám včetně
`claude.additional_dirs`.

---

## Krok 3: Přidat `useDynamicModels` do Layout

**Soubor:** `apps/web/src/components/avatar/AvatarProvider.tsx`

Přidat import a hook:

```typescript
import {
  useAvatarChat,
  useAvailableProviders,
  useDynamicModels,        // NOVÝ
  useModelDiscoveryErrors, // NOVÝ
  AVATARS,
} from '@avatar-engine/react'
```

V `AvatarProvider` komponentě přidat:

```typescript
export function AvatarProvider({ children }: { children: ReactNode }) {
  // ... existující kód ...

  const chat = useAvatarChat(wsUrl, { apiBase: '/api/avatar' })
  const providers = useAvailableProviders()
  const dynamicProviders = useDynamicModels('/api/avatar')  // NOVÝ
  const modelErrors = useModelDiscoveryErrors()              // NOVÝ

  // Zobrazit warning toast při chybě parseru
  useEffect(() => {
    for (const err of modelErrors) {
      toast.warning(err.message)
    }
  }, [modelErrors])

  // ... zbytek ...
}
```

Přidat `dynamicProviders` do kontextu:

```typescript
interface AvatarContextValue {
  chat: UseAvatarChatReturn
  sendWithContext: (text: string) => void
  providers: Set<string> | null
  dynamicProviders: ProviderConfig[]  // NOVÝ
  compactRef: React.MutableRefObject<(() => void) | null>
}
```

### 3.1: Předat dynamicProviders do Layout

**Soubor:** `apps/web/src/components/layout/Layout.tsx`

Změnit `customProviders` na AvatarWidget:

```typescript
function LayoutInner({ children }: LayoutProps) {
  const { chat, sendWithContext, providers, dynamicProviders, compactRef } = useAvatar()

  // ...

  <AvatarWidget
    initialMode="fab"
    customProviders={E2E_PROVIDERS ?? dynamicProviders}  // ZMĚNA
    // ... zbytek props beze změny ...
  >
```

Logika: pokud existuje E2E override (testy), použít ho. Jinak dynamické modely.

**Totéž pro StatusBar** (má taky `availableProviders` prop — ten je pro filtrování providerů,
ne pro modely. Ten zůstává beze změny).

---

## Krok 4: Aktualizovat dokumentaci

### 4.1: `docs/avatar/configuration.md`

Přidat sekci o `additional_dirs`:

```markdown
### Additional Directories (Claude only)

When using Claude provider, the AI can only access files in the `working_dir`.
To grant access to additional directories (e.g., Synapse data store):

```yaml
claude:
  additional_dirs:
    - "~/.synapse"
    - "~/projects/shared-data"
```

### 4.2: `docs/avatar/configuration.md`

Přidat poznámku o dynamických modelech:

```markdown
### Dynamic Model Discovery

Avatar Engine automatically fetches current model lists from provider
documentation pages. The model dropdown shows the latest available models
without manual configuration updates.

If model discovery fails (page structure changed), a warning toast appears.
Static model lists are used as fallback.
```

---

## Krok 5: Verze — NEMĚNIT TEĎ

Verze se bumpe **AŽ PO OTESTOVÁNÍ** spolu s uživatelem:

1. Společné manuální testování (dynamické modely, additional_dirs, provider switch)
2. Pokud vše funguje → release avatar-engine v1.2.0
3. Pak Synapse bump: `AE_MIN_VERSION = '1.2.0'`, `AVATAR_ENGINE_MIN_VERSION = "1.2.0"`
4. Pak `package.json` / `pyproject.toml` constrainty

**TEĎ:**
- `AE_MIN_VERSION` zůstává `'1.0.0'`
- `AVATAR_ENGINE_MIN_VERSION` zůstává `"1.0.0"`
- `package.json` zůstává `^1.1.0` (npm link přepisuje)

---

## Krok 6: Ověření

```bash
# 1. Backend testy (žádný avatar-engine runtime nepotřeba)
./scripts/verify.sh --quick

# 2. Frontend build
cd apps/web && pnpm build

# 3. Manuální test (vyžaduje npm link + pip install -e z Kroku 0):
#    - Spustit backend: uv run uvicorn src.store.api:app --reload --port 8000
#    - Spustit frontend: cd apps/web && pnpm dev
#    - curl http://localhost:8000/api/avatar/models | python -m json.tool
#    - Otevřít Synapse → model dropdown by měl ukazovat dynamické modely
#    - Přepnout na Claude → ověřit, že AI vidí ~/.synapse
#    - Zkusit refresh: curl "http://localhost:8000/api/avatar/models?refresh=true"
```

---

## Soubory k úpravě

| Soubor | Změna | Stav |
|--------|-------|------|
| `config/avatar.yaml.example` | Přidat `additional_dirs`, komentář o dynamických modelech | ✅ |
| `src/avatar/config.py` | BEZ ZMĚNY — additional_dirs projde transparentně | ✅ ověřeno |
| `apps/web/src/components/avatar/AvatarProvider.tsx` | Přidat `useDynamicModels`, `useModelDiscoveryErrors`, context | ✅ |
| `apps/web/src/components/layout/Layout.tsx` | `customProviders={E2E_PROVIDERS ?? dynamicProviders}` | ✅ |
| `docs/avatar/configuration.md` | Dokumentace additional_dirs + dynamic models | ✅ |
| `src/avatar/__init__.py` | BEZ ZMĚNY TEĎ — verze po otestování | ✅ zatím |

---

## Co NEDĚLAT

- **NEPUBLIKOVAT** avatar-engine v1.2.0 — jedeme přes npm link + pip install -e
- **NEMĚNIT** `package.json` závislosti — zůstává `^1.1.0`, npm link přepíše
- **NEMĚNIT** `pyproject.toml` verzi constraintu — pip install -e přepíše
- **NEODSTRAŇOVAT** E2E_PROVIDERS logiku — stále potřebujeme pro testy
- **NEBUMPOVAT** verze (`AE_MIN_VERSION`, `AVATAR_ENGINE_MIN_VERSION`) — až po společném testování a release
