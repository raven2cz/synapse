# 🔍 Phase 5: Internal Civitai Search (tRPC)

**Branch:** `feature/internal-search-trpc`
**Verze:** v2.7.0
**Datum zahájení:** 2026-01-22
**Status:** 🚧 PLANNING

---

## 📊 Přehled

### Motivace
Aktuálně BrowsePage volá Civitai API přímo z frontendu. To má několik nevýhod:
1. **CORS problémy** - některé endpointy vyžadují proxy
2. **Rate limiting** - Civitai může omezit požadavky z různých IP
3. **API klíč exposure** - klíč musí být ve frontendu
4. **Nedostatečná kontrola** - nemůžeme cachovat ani transformovat odpovědi
5. **Offline podpora** - nelze implementovat offline vyhledávání

### Cíle
1. **tRPC backend** - Veškeré Civitai volání přes náš backend
2. **Search endpoint** - `/api/search/models` s cachováním
3. **Model detail endpoint** - `/api/search/model/{id}` s enrichmentem
4. **Metadata caching** - Redis/SQLite cache pro často hledané modely
5. **Offline fallback** - Vyhledávání v již stažených packách

---

## 📁 Struktura změn

```
synapse/
├── src/
│   ├── api/
│   │   └── search_router.py      # NOVÉ - tRPC-style search endpoints
│   ├── services/
│   │   └── search_service.py     # NOVÉ - Business logika pro search
│   └── cache/
│       └── search_cache.py       # NOVÉ - Cache layer (Redis/SQLite)
├── apps/web/src/
│   ├── lib/
│   │   └── api/
│   │       └── search.ts         # NOVÉ - Frontend API client
│   └── components/modules/
│       └── BrowsePage.tsx        # UPRAVIT - Použít interní API
└── tests/
    └── api/
        └── test_search_router.py # NOVÉ - Testy pro search API
```

---

## 🔧 Subfáze 5.1: Backend Search Router

### 5.1.1 Vytvořit search_router.py

**Status:** ❌ TODO

**Soubor:** `src/api/search_router.py`

```python
from fastapi import APIRouter, Query, Depends
from typing import Optional, List
from pydantic import BaseModel

search_router = APIRouter(prefix="/api/search", tags=["search"])

class SearchFilters(BaseModel):
    query: Optional[str] = None
    tag: Optional[str] = None
    types: Optional[List[str]] = None  # LORA, Checkpoint, etc.
    base_models: Optional[List[str]] = None  # SDXL, SD 1.5, etc.
    sort: str = "Highest Rated"
    nsfw: bool = True
    limit: int = 20
    cursor: Optional[str] = None  # For pagination

class SearchResult(BaseModel):
    items: List[dict]
    metadata: dict
    cached: bool = False

@search_router.get("/models")
async def search_models(
    query: Optional[str] = None,
    tag: Optional[str] = None,
    types: Optional[str] = None,  # Comma-separated
    base_models: Optional[str] = None,  # Comma-separated
    sort: str = "Highest Rated",
    nsfw: bool = True,
    limit: int = Query(20, le=100),
    cursor: Optional[str] = None,
) -> SearchResult:
    """
    Search Civitai models through our backend.

    Benefits:
    - API key stays on server
    - Response caching
    - Rate limit handling
    - Enrichment with local pack data
    """
    pass

@search_router.get("/model/{model_id}")
async def get_model_detail(model_id: int) -> dict:
    """
    Get model detail with enrichment.

    Enrichment:
    - Check if already imported as pack
    - Add local pack info if exists
    - Cache popular models
    """
    pass

@search_router.get("/model/{model_id}/images")
async def get_model_images(
    model_id: int,
    limit: int = Query(20, le=100),
    sort: str = "Most Reactions",
) -> dict:
    """
    Get model images/previews.
    """
    pass
```

---

### 5.1.2 Vytvořit search_service.py

**Status:** ❌ TODO

**Soubor:** `src/services/search_service.py`

```python
from src.clients.civitai_client import CivitaiClient
from src.cache.search_cache import SearchCache
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(
        self,
        civitai_client: CivitaiClient,
        cache: Optional[SearchCache] = None,
    ):
        self.civitai = civitai_client
        self.cache = cache

    async def search_models(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        types: Optional[List[str]] = None,
        base_models: Optional[List[str]] = None,
        sort: str = "Highest Rated",
        nsfw: bool = True,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> dict:
        """
        Search with caching and error handling.
        """
        # 1. Check cache
        cache_key = self._build_cache_key(query, tag, types, sort, nsfw, limit, cursor)
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key}")
                return {**cached, "cached": True}

        # 2. Call Civitai API
        try:
            result = self.civitai.search_models(
                query=query,
                tag=tag,
                types=types,
                base_models=base_models,
                sort=sort,
                nsfw=nsfw,
                limit=limit,
                cursor=cursor,
            )
        except Exception as e:
            logger.error(f"Civitai search failed: {e}")
            # Fallback to local search if available
            return await self._local_fallback(query, tag, types)

        # 3. Cache result
        if self.cache:
            await self.cache.set(cache_key, result, ttl=300)  # 5 min TTL

        return {**result, "cached": False}

    async def _local_fallback(self, query, tag, types) -> dict:
        """
        Search in local packs when Civitai is unavailable.
        """
        # TODO: Implement local pack search
        return {"items": [], "metadata": {"fallback": True}}
```

---

### 5.1.3 Implementovat cache layer

**Status:** ❌ TODO

**Soubor:** `src/cache/search_cache.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, Any
import json
import hashlib
from pathlib import Path

class SearchCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def set(self, key: str, value: dict, ttl: int = 300) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

class FileSearchCache(SearchCache):
    """
    Simple file-based cache for development.
    """
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.json"

    async def get(self, key: str) -> Optional[dict]:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        # TODO: Check TTL
        with open(path) as f:
            return json.load(f)

    async def set(self, key: str, value: dict, ttl: int = 300) -> None:
        path = self._key_to_path(key)
        with open(path, "w") as f:
            json.dump({"value": value, "ttl": ttl}, f)

    async def delete(self, key: str) -> None:
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
```

---

## 🔧 Subfáze 5.2: Frontend Integration

### 5.2.1 Vytvořit search API client

**Status:** ❌ TODO

**Soubor:** `apps/web/src/lib/api/search.ts`

```typescript
import { API_BASE } from '../constants'

export interface SearchFilters {
  query?: string
  tag?: string
  types?: string[]
  baseModels?: string[]
  sort?: string
  nsfw?: boolean
  limit?: number
  cursor?: string
}

export interface SearchResult {
  items: ModelSummary[]
  metadata: {
    totalItems?: number
    currentPage?: number
    pageSize?: number
    nextCursor?: string
  }
  cached: boolean
}

export async function searchModels(filters: SearchFilters): Promise<SearchResult> {
  const params = new URLSearchParams()

  if (filters.query) params.set('query', filters.query)
  if (filters.tag) params.set('tag', filters.tag)
  if (filters.types?.length) params.set('types', filters.types.join(','))
  if (filters.baseModels?.length) params.set('base_models', filters.baseModels.join(','))
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.nsfw !== undefined) params.set('nsfw', String(filters.nsfw))
  if (filters.limit) params.set('limit', String(filters.limit))
  if (filters.cursor) params.set('cursor', filters.cursor)

  const response = await fetch(`${API_BASE}/search/models?${params}`)
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`)
  }

  return response.json()
}

export async function getModelDetail(modelId: number): Promise<ModelDetail> {
  const response = await fetch(`${API_BASE}/search/model/${modelId}`)
  if (!response.ok) {
    throw new Error(`Get model failed: ${response.status}`)
  }

  return response.json()
}
```

---

### 5.2.2 Aktualizovat BrowsePage.tsx

**Status:** ❌ TODO

**Soubor:** `apps/web/src/components/modules/BrowsePage.tsx`

**Změny:**
1. Nahradit přímá Civitai volání za `searchModels()` z `lib/api/search`
2. Přidat indikátor cached/live dat
3. Zachovat stávající UI a UX

---

## 🔧 Subfáze 5.3: Enrichment a Local Fallback

### 5.3.1 Enrichment - přidat local pack info

**Status:** ❌ TODO

Když vracíme search results, enrichovat o:
- `isImported: boolean` - Je model již importován?
- `localPackName?: string` - Jméno lokálního packu
- `localPackVersion?: string` - Verze lokálního packu

### 5.3.2 Local fallback search

**Status:** ❌ TODO

Když Civitai není dostupné:
- Vyhledat v lokálních packách podle jména
- Vyhledat podle tagů
- Zobrazit upozornění že data jsou pouze lokální

---

## 📋 Celkový checklist

### Fáze 5.1: Backend Search Router
- [ ] 5.1.1 search_router.py - základní endpointy
- [ ] 5.1.2 search_service.py - business logika
- [ ] 5.1.3 search_cache.py - cache layer

### Fáze 5.2: Frontend Integration
- [ ] 5.2.1 search.ts - API client
- [ ] 5.2.2 BrowsePage.tsx - integrace

### Fáze 5.3: Enrichment
- [ ] 5.3.1 Local pack enrichment
- [ ] 5.3.2 Offline fallback

### Testy
- [ ] Backend testy pro search router
- [ ] Frontend testy pro search API
- [ ] Integration testy

---

## 📝 Implementační log

*(Doplňovat průběžně)*

---

## 🚨 Známé problémy a rizika

1. **Civitai API změny** - API může změnit strukturu bez varování
2. **Rate limiting** - Potřeba implementovat retry logic
3. **Cache invalidace** - Jak dlouho cachovat? Jak invalidovat?
4. **Velké responses** - Některé modely mají stovky verzí

---

## 📚 Reference

- [Civitai API Docs](https://github.com/civitai/civitai/wiki/REST-API-Reference)
- `src/clients/civitai_client.py` - Stávající Civitai client
- `apps/web/src/components/modules/BrowsePage.tsx` - Stávající frontend implementace

---

*Vytvořeno: 2026-01-22*
*Status: PLANNING*
