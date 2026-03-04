# Independent E2E Smoke Tests: Civitai CDN/Proxy/Search Pipeline

**Status:** ✅ DOKONČENO (2026-03-01)
**Původní plán:** `.claude/plans/twinkling-humming-allen.md` (2026-02-22)

## Context

Mnohonásobné neúspěšné pokusy o opravu rozbily Browse a Pack Detail stránky:
1. `optimized=true` v URL způsobovalo CDN 500 errory
2. B2 redirect headers způsobovaly 401
3. Nucený `anim=false` na VŠECHNY .mp4 zabil přehrávání videa
4. 24 souběžných video autoPlay zamrzlo aplikaci

**Řešení:** Vytvořit samostatné smoke testy, které ověří každý CDN/proxy/search předpoklad PŘED integrací.

---

## Implementace ✅

### Struktura testů

```
tests/smoke/
├── conftest.py                     # Fixtures, markers, httpx clients
├── fixtures/
│   └── known_urls.py               # Stable CDN URLs, UUIDs, model IDs
├── utils/
│   ├── http_logger.py              # Redirect chain tracer
│   └── cdn_prober.py               # URL construction helpers
├── test_01_url_construction.py     # ~20 offline tests — URL building, optimized=true audit
├── test_02_cdn_direct.py           # ~14 live CDN tests — direct Civitai CDN HTTP
├── test_03_proxy_endpoint.py       # ~12 proxy tests — /api/browse/image-proxy via TestClient
├── test_04_search_pipeline.py      # ~12 pipeline tests — transformer output validation
├── test_05_juggernaut_e2e.py       # ~13 E2E tests — Juggernaut XL golden path
└── run_smoke_tests.sh              # Runner script
```

### Test Groups

| Group | File | Typ | Počet | Popis |
|-------|------|-----|-------|-------|
| 1 | `test_01_url_construction.py` | Offline | ~20 | URL building, `optimized=true` audit |
| 2 | `test_02_cdn_direct.py` | Live CDN | ~14 | Direct Civitai CDN HTTP testy |
| 3 | `test_03_proxy_endpoint.py` | Proxy | ~12 | Image proxy via TestClient |
| 4 | `test_04_search_pipeline.py` | Pipeline | ~12 | Transformer output validace |
| 5 | `test_05_juggernaut_e2e.py` | E2E | ~13 | Juggernaut XL golden path |

### Markers

- `@pytest.mark.smoke` — auto-applied to all tests/smoke/
- `@pytest.mark.live` — requires live Civitai CDN network access
- `@pytest.mark.proxy` — requires proxy server or TestClient

### Spuštění

```bash
# Offline only (fast, <1s)
uv run pytest tests/smoke/test_01_url_construction.py -v

# Live CDN (needs network)
uv run pytest tests/smoke/ -v -m live

# Full suite
uv run pytest tests/smoke/ -v

# Runner script
./tests/smoke/run_smoke_tests.sh
```

### Integrace

- `tests/conftest.py` — přidány `smoke`, `live`, `proxy` markery
- `scripts/verify.sh` — přidány `--smoke` / `--smoke-live` options

---

## Klíčové ověření

1. **URL audit:** Žádné `optimized=true` v produkčním kódu
2. **CDN behavior:** B2 redirect chain dokumentován a ověřen
3. **Proxy:** Správné header stripping, fast-fail pro videa
4. **Pipeline:** Transformery produkují validní URL bez `optimized=true`
5. **E2E:** Juggernaut XL golden path kompletní

---

*Souvisí s: `PLAN-CDN-Video-Fix.md`*
