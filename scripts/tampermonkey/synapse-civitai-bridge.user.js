// ==UserScript==
// @name         Synapse Civitai Bridge
// @namespace    synapse.civitai.bridge
// @version      10.0.0
// @description  Bridge for Synapse - Civitai API access via Meilisearch + tRPC
// @author       SynapseTeam
// @match        http://localhost:*/*
// @match        http://127.0.0.1:*/*
// @match        https://localhost:*/*
// @connect      civitai.com
// @connect      search-new.civitai.com
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        unsafeWindow
// @run-at       document-start
// ==/UserScript==

(function () {
  'use strict';

  // ==========================================================================
  // Configuration
  // ==========================================================================

  const VERSION = '10.0.0';
  const TRPC_BASE = 'https://civitai.com/api/trpc';
  const MEILISEARCH_BASE = 'https://search-new.civitai.com';
  const MEILISEARCH_TOKEN = '8c46eb2508e21db1e9828a97968d91ab1ca1caa5f70a00e88a2ba1e286603b61';
  const MEILISEARCH_INDEX = 'models_v9';
  const CACHE_TTL = 30000; // 30 seconds
  const CACHE_MAX_SIZE = 200;
  const DEFAULT_TIMEOUT = 15000; // 15 seconds (faster for Meilisearch)
  const TRPC_TIMEOUT = 30000; // 30 seconds for tRPC
  const IMAGE_FETCH_TIMEOUT = 60000; // 60 seconds for image.getInfinite which is VERY slow

  // Target window (Firefox needs unsafeWindow)
  const target = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;

  // LRU Cache
  const cache = new Map();

  // ==========================================================================
  // Configuration Storage
  // ==========================================================================

  function getConfig() {
    return {
      enabled: GM_getValue('synapse_bridge_enabled', true),
      nsfw: GM_getValue('synapse_bridge_nsfw', true),
    };
  }

  function saveConfig(updates) {
    if (updates.enabled !== undefined) {
      GM_setValue('synapse_bridge_enabled', updates.enabled);
    }
    if (updates.nsfw !== undefined) {
      GM_setValue('synapse_bridge_nsfw', updates.nsfw);
    }
  }

  // ==========================================================================
  // LRU Cache
  // ==========================================================================

  function cacheGet(key) {
    const item = cache.get(key);
    if (!item) return null;

    // Check TTL
    if (Date.now() - item.ts > CACHE_TTL) {
      cache.delete(key);
      return null;
    }

    // LRU: move to end
    cache.delete(key);
    cache.set(key, item);
    return item.data;
  }

  function cacheSet(key, data) {
    // Evict oldest if full
    if (cache.size >= CACHE_MAX_SIZE) {
      const oldest = cache.keys().next().value;
      cache.delete(oldest);
    }
    cache.set(key, { ts: Date.now(), data });
  }

  function cacheClear() {
    cache.clear();
  }

  // ==========================================================================
  // Meilisearch Request Builder (FAST search with query)
  // ==========================================================================

  function buildMeilisearchRequest(params, config) {
    // Build NSFW filter based on config
    // nsfwLevel: 1=None, 2=Soft, 4=Mature, 8=X, 16=Blocked, 32=???
    let nsfwFilter = '';
    if (config.nsfw) {
      // All content
      nsfwFilter = '(nsfwLevel=1 OR nsfwLevel=2 OR nsfwLevel=4 OR nsfwLevel=8 OR nsfwLevel=16)';
    } else {
      // SFW only
      nsfwFilter = '(nsfwLevel=1 OR nsfwLevel=2)';
    }

    // Build additional filters
    const filters = [nsfwFilter];

    // Type filter
    if (params.filters?.types) {
      const types = Array.isArray(params.filters.types)
        ? params.filters.types
        : [params.filters.types];
      if (types.length > 0) {
        filters.push(`(type IN [${types.map((t) => `'${t}'`).join(', ')}])`);
      }
    }

    // Base model filter
    if (params.filters?.baseModel) {
      const baseModels = Array.isArray(params.filters.baseModel)
        ? params.filters.baseModel
        : [params.filters.baseModel];
      if (baseModels.length > 0) {
        filters.push(
          `(version.baseModel IN [${baseModels.map((b) => `'${b}'`).join(', ')}])`
        );
      }
    }

    // Sort mapping: Meilisearch uses different sort syntax
    // For now, we'll use default relevance sort when searching
    // tRPC is better for sorted browsing without query

    return {
      queries: [
        {
          q: params.q || '',
          indexUid: MEILISEARCH_INDEX,
          facets: [
            'category.name',
            'checkpointType',
            'fileFormats',
            'tags.name',
            'type',
            'user.username',
            'version.baseModel',
          ],
          attributesToHighlight: [],
          highlightPreTag: '__ais-highlight__',
          highlightPostTag: '__/ais-highlight__',
          limit: params.limit || 20,
          offset: params.offset || 0,
          filter: filters,
        },
      ],
    };
  }

  // ==========================================================================
  // tRPC URL Builders (for browse without query, model detail)
  // ==========================================================================

  function buildSearchUrl(params, config) {
    const input = {
      json: {
        query: params.q || undefined,
        limit: params.limit || 20,
        cursor: params.cursor || undefined,
        sort: params.sort || 'Most Downloaded',
        period: params.period || 'AllTime',
        // browsingLevel: 31 = all content, 1 = SFW only
        browsingLevel: config.nsfw ? 31 : 1,
        // Optional filters
        types: params.filters?.types ? [params.filters.types] : undefined,
        baseModels: params.filters?.baseModel
          ? [params.filters.baseModel]
          : undefined,
      },
    };

    // Clean undefined values
    Object.keys(input.json).forEach((k) => {
      if (input.json[k] === undefined) delete input.json[k];
    });

    return `${TRPC_BASE}/model.getAll?input=${encodeURIComponent(
      JSON.stringify(input)
    )}`;
  }

  function buildModelUrl(modelId) {
    const input = { json: { id: modelId } };
    return `${TRPC_BASE}/model.getById?input=${encodeURIComponent(
      JSON.stringify(input)
    )}`;
  }

  function buildModelImagesUrl(modelId, config, limit = 50) {
    const input = {
      json: {
        modelId: modelId,
        limit: limit,
        sort: 'Most Reactions',
        period: 'AllTime',
        // browsingLevel: 31 = all content, 1 = SFW only
        browsingLevel: config.nsfw ? 31 : 1,
      },
    };
    return `${TRPC_BASE}/image.getInfinite?input=${encodeURIComponent(
      JSON.stringify(input)
    )}`;
  }

  // ==========================================================================
  // Meilisearch Request Handler (POST with JSON body)
  // ==========================================================================

  async function meilisearchRequest(body, opts = {}) {
    const cacheKey = `meili:${JSON.stringify(body)}`;

    // Check cache first (unless noCache)
    if (!opts.noCache) {
      const cached = cacheGet(cacheKey);
      if (cached) {
        return {
          ok: true,
          data: cached,
          meta: { cached: true, durationMs: 0, source: 'meilisearch' },
        };
      }
    }

    const startTime = Date.now();

    return new Promise((resolve) => {
      let resolved = false;

      const finish = (result) => {
        if (!resolved) {
          resolved = true;
          resolve(result);
        }
      };

      const request = GM_xmlhttpRequest({
        method: 'POST',
        url: `${MEILISEARCH_BASE}/multi-search`,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          Authorization: `Bearer ${MEILISEARCH_TOKEN}`,
          'X-Meilisearch-Client':
            'Meilisearch instant-meilisearch (v0.13.5) ; Meilisearch JavaScript (v0.34.0)',
        },
        data: JSON.stringify(body),
        timeout: opts.timeout || DEFAULT_TIMEOUT,
        responseType: 'json',

        onload: (response) => {
          if (response.status >= 200 && response.status < 300) {
            try {
              let data = response.response;

              // Parse if string
              if (!data && response.responseText) {
                data = JSON.parse(response.responseText);
              }

              // Meilisearch returns { results: [{ hits: [...], ... }] }
              const result = data?.results?.[0] || data;

              cacheSet(cacheKey, result);

              finish({
                ok: true,
                data: result,
                meta: {
                  cached: false,
                  durationMs: Date.now() - startTime,
                  source: 'meilisearch',
                },
              });
            } catch (e) {
              finish({
                ok: false,
                error: {
                  code: 'PARSE_ERROR',
                  message: e.message,
                },
              });
            }
          } else {
            const isRetryable =
              response.status === 429 || response.status >= 500;

            finish({
              ok: false,
              error: {
                code: response.status === 429 ? 'RATE_LIMIT' : 'HTTP_ERROR',
                message: `HTTP ${response.status}`,
                httpStatus: response.status,
                retryable: isRetryable,
              },
            });
          }
        },

        onerror: () => {
          finish({
            ok: false,
            error: {
              code: 'NETWORK',
              message: 'Network error - check connection',
            },
          });
        },

        ontimeout: () => {
          finish({
            ok: false,
            error: {
              code: 'TIMEOUT',
              message: 'Request timed out',
              retryable: true,
            },
          });
        },
      });

      // Abort signal support
      if (opts.signal) {
        opts.signal.addEventListener('abort', () => {
          try {
            request.abort?.();
          } catch (e) {
            // Ignore abort errors
          }
          finish({
            ok: false,
            error: {
              code: 'ABORTED',
              message: 'Request cancelled',
            },
          });
        });
      }
    });
  }

  // ==========================================================================
  // tRPC Request Handler (GET requests)
  // ==========================================================================

  async function trpcRequest(url, opts = {}) {
    const cacheKey = url;

    // Check cache first (unless noCache)
    if (!opts.noCache) {
      const cached = cacheGet(cacheKey);
      if (cached) {
        return {
          ok: true,
          data: cached,
          meta: { cached: true, durationMs: 0, source: 'trpc' },
        };
      }
    }

    const startTime = Date.now();

    return new Promise((resolve) => {
      let resolved = false;

      const finish = (result) => {
        if (!resolved) {
          resolved = true;
          resolve(result);
        }
      };

      const request = GM_xmlhttpRequest({
        method: 'GET',
        url,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        timeout: opts.timeout || TRPC_TIMEOUT,
        responseType: 'json',

        onload: (response) => {
          if (response.status >= 200 && response.status < 300) {
            try {
              let data = response.response;

              // Parse if string
              if (!data && response.responseText) {
                data = JSON.parse(response.responseText);
              }

              // tRPC wraps response in result.data.json
              const result = data?.result?.data?.json || data;

              cacheSet(cacheKey, result);

              finish({
                ok: true,
                data: result,
                meta: {
                  cached: false,
                  durationMs: Date.now() - startTime,
                  source: 'trpc',
                },
              });
            } catch (e) {
              finish({
                ok: false,
                error: {
                  code: 'PARSE_ERROR',
                  message: e.message,
                },
              });
            }
          } else {
            const isRetryable =
              response.status === 429 || response.status >= 500;

            finish({
              ok: false,
              error: {
                code: response.status === 429 ? 'RATE_LIMIT' : 'HTTP_ERROR',
                message: `HTTP ${response.status}`,
                httpStatus: response.status,
                retryable: isRetryable,
              },
            });
          }
        },

        onerror: () => {
          finish({
            ok: false,
            error: {
              code: 'NETWORK',
              message: 'Network error - check connection',
            },
          });
        },

        ontimeout: () => {
          finish({
            ok: false,
            error: {
              code: 'TIMEOUT',
              message: 'Request timed out',
              retryable: true,
            },
          });
        },
      });

      // Abort signal support
      if (opts.signal) {
        opts.signal.addEventListener('abort', () => {
          try {
            request.abort?.();
          } catch (e) {
            // Ignore abort errors
          }
          finish({
            ok: false,
            error: {
              code: 'ABORTED',
              message: 'Request cancelled',
            },
          });
        });
      }
    });
  }

  // ==========================================================================
  // Bridge API
  // ==========================================================================

  const bridge = {
    version: VERSION,

    /**
     * Check if bridge is enabled
     */
    isEnabled: () => getConfig().enabled,

    /**
     * Get current status
     */
    getStatus: () => {
      const config = getConfig();
      return {
        enabled: config.enabled,
        nsfw: config.nsfw,
        version: VERSION,
        cacheSize: cache.size,
        features: ['meilisearch', 'trpc', 'hybrid'],
      };
    },

    /**
     * Update configuration
     */
    configure: (updates) => {
      saveConfig(updates);
      return bridge.getStatus();
    },

    /**
     * Clear cache
     */
    clearCache: () => {
      const prevSize = cache.size;
      cacheClear();
      return { cleared: true, previousSize: prevSize };
    },

    /**
     * HYBRID SEARCH - Uses Meilisearch for queries, tRPC for browse
     *
     * Strategy:
     * - If query provided (q) → Use Meilisearch (FAST full-text search)
     * - If no query (browse) → Use tRPC model.getAll (better sorting/filtering)
     *
     * @param {Object} params - Search parameters
     * @param {string} params.q - Search query (triggers Meilisearch)
     * @param {number} params.limit - Results limit (default: 20)
     * @param {string} params.sort - Sort order (tRPC only)
     * @param {string} params.period - Time period filter (tRPC only)
     * @param {string} params.cursor - Pagination cursor (tRPC only)
     * @param {number} params.offset - Pagination offset (Meilisearch only)
     * @param {Object} params.filters - Additional filters
     * @param {Object} opts - Request options
     * @param {AbortSignal} opts.signal - Abort signal
     * @param {boolean} opts.noCache - Skip cache
     * @param {boolean} opts.forceTrpc - Force tRPC even with query
     */
    search: async (params, opts = {}) => {
      const config = getConfig();

      if (!config.enabled) {
        return {
          ok: false,
          error: {
            code: 'DISABLED',
            message: 'Bridge is disabled',
          },
        };
      }

      // HYBRID STRATEGY:
      // - Query search → Meilisearch (fast full-text)
      // - Browse (no query) → tRPC (sorting, pagination)
      const hasQuery = params.q && params.q.trim().length > 0;
      const useMeilisearch = hasQuery && !opts.forceTrpc;

      if (useMeilisearch) {
        // Use Meilisearch for query search
        const body = buildMeilisearchRequest(params, config);
        const result = await meilisearchRequest(body, opts);

        if (!result.ok) return result;

        // Transform Meilisearch response to match expected format
        const hits = result.data?.hits || [];
        return {
          ok: true,
          data: {
            items: hits,
            // Meilisearch uses offset/limit, not cursor
            nextCursor: undefined,
            // Estimate if more results
            hasMore: hits.length >= (params.limit || 20),
            totalHits: result.data?.estimatedTotalHits || hits.length,
          },
          meta: {
            ...result.meta,
            source: 'meilisearch',
            query: params.q,
          },
        };
      } else {
        // Use tRPC for browse without query
        const url = buildSearchUrl(params, config);
        const result = await trpcRequest(url, opts);

        if (!result.ok) return result;

        return {
          ok: true,
          data: {
            items: result.data?.items || [],
            nextCursor: result.data?.nextCursor,
            hasMore: !!result.data?.nextCursor,
          },
          meta: {
            ...result.meta,
            source: 'trpc',
          },
        };
      }
    },

    /**
     * Direct Meilisearch search (bypass hybrid logic)
     *
     * @param {Object} params - Search parameters
     * @param {Object} opts - Request options
     */
    searchMeilisearch: async (params, opts = {}) => {
      const config = getConfig();

      if (!config.enabled) {
        return {
          ok: false,
          error: {
            code: 'DISABLED',
            message: 'Bridge is disabled',
          },
        };
      }

      const body = buildMeilisearchRequest(params, config);
      return meilisearchRequest(body, opts);
    },

    /**
     * Direct tRPC search (bypass hybrid logic)
     *
     * @param {Object} params - Search parameters
     * @param {Object} opts - Request options
     */
    searchTrpc: async (params, opts = {}) => {
      const config = getConfig();

      if (!config.enabled) {
        return {
          ok: false,
          error: {
            code: 'DISABLED',
            message: 'Bridge is disabled',
          },
        };
      }

      const url = buildSearchUrl(params, config);
      return trpcRequest(url, opts);
    },

    /**
     * Get model details via tRPC
     *
     * @param {number} modelId - Model ID
     * @param {Object} opts - Request options
     */
    getModel: async (modelId, opts = {}) => {
      const config = getConfig();

      if (!config.enabled) {
        return {
          ok: false,
          error: {
            code: 'DISABLED',
            message: 'Bridge is disabled',
          },
        };
      }

      const url = buildModelUrl(modelId);
      return trpcRequest(url, opts);
    },

    /**
     * Get images for a model via tRPC image.getInfinite
     *
     * NOTE: model.getById only returns post IDs, not actual images!
     * This method fetches the images separately.
     *
     * @param {number} modelId - Model ID
     * @param {Object} opts - Request options
     * @param {number} opts.limit - Max images to fetch (default: 50)
     */
    getModelImages: async (modelId, opts = {}) => {
      const config = getConfig();

      if (!config.enabled) {
        return {
          ok: false,
          error: {
            code: 'DISABLED',
            message: 'Bridge is disabled',
          },
        };
      }

      const url = buildModelImagesUrl(modelId, config, opts.limit || 50);
      return trpcRequest(url, opts);
    },

    /**
     * Test connection to both APIs
     */
    test: async () => {
      const results = {
        meilisearch: null,
        trpc: null,
      };

      // Test Meilisearch
      try {
        const meiliResult = await bridge.searchMeilisearch(
          { q: 'test', limit: 1 },
          { noCache: true }
        );
        results.meilisearch = {
          ok: meiliResult.ok,
          durationMs: meiliResult.meta?.durationMs,
        };
      } catch (e) {
        results.meilisearch = { ok: false, error: e.message };
      }

      // Test tRPC
      try {
        const trpcResult = await bridge.searchTrpc(
          { q: '', limit: 1 },
          { noCache: true }
        );
        results.trpc = {
          ok: trpcResult.ok,
          durationMs: trpcResult.meta?.durationMs,
        };
      } catch (e) {
        results.trpc = { ok: false, error: e.message };
      }

      return {
        ok: results.meilisearch?.ok || results.trpc?.ok,
        results,
      };
    },
  };

  // ==========================================================================
  // Export to Window
  // ==========================================================================

  // Firefox requires cloneInto for security
  if (typeof cloneInto === 'function') {
    target.SynapseSearchBridge = cloneInto(bridge, target, {
      cloneFunctions: true,
    });
  } else {
    target.SynapseSearchBridge = bridge;
  }

  // Dispatch ready events
  const dispatchReady = () => {
    target.dispatchEvent(new Event('synapse-bridge-ready'));
  };

  // Dispatch immediately and after small delay (for late listeners)
  dispatchReady();
  setTimeout(dispatchReady, 100);
  setTimeout(dispatchReady, 500);

  // Log success
  console.log(
    `%c[Synapse] Bridge v${VERSION} loaded (Meilisearch + tRPC hybrid)`,
    'color: #8B5CF6; font-weight: bold;'
  );
})();
