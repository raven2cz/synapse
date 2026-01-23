// ==UserScript==
// @name         Synapse Civitai Bridge
// @namespace    synapse.civitai.bridge
// @version      9.0.1
// @description  Bridge for Synapse - direct Civitai tRPC API access bypassing CORS
// @author       SynapseTeam
// @match        http://localhost:*/*
// @match        http://127.0.0.1:*/*
// @match        https://localhost:*/*
// @connect      civitai.com
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

  const VERSION = '9.0.1';
  const TRPC_BASE = 'https://civitai.com/api/trpc';
  const CACHE_TTL = 30000; // 30 seconds
  const CACHE_MAX_SIZE = 200;
  const DEFAULT_TIMEOUT = 30000;
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
  // tRPC URL Builders
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
  // tRPC Request Handler
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
          meta: { cached: true, durationMs: 0 },
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

              // tRPC wraps response in result.data.json
              const result = data?.result?.data?.json || data;

              cacheSet(cacheKey, result);

              finish({
                ok: true,
                data: result,
                meta: {
                  cached: false,
                  durationMs: Date.now() - startTime,
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
      cacheClear();
      return { cleared: true, previousSize: cache.size };
    },

    /**
     * Search models via tRPC
     *
     * @param {Object} params - Search parameters
     * @param {string} params.q - Search query
     * @param {number} params.limit - Results limit (default: 20)
     * @param {string} params.sort - Sort order
     * @param {string} params.period - Time period filter
     * @param {string} params.cursor - Pagination cursor
     * @param {Object} params.filters - Additional filters
     * @param {Object} opts - Request options
     * @param {AbortSignal} opts.signal - Abort signal
     * @param {boolean} opts.noCache - Skip cache
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
     * Test connection to Civitai
     */
    test: async () => {
      return bridge.search({ q: '', limit: 1 }, { noCache: true });
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
    `%c[Synapse] Bridge v${VERSION} loaded`,
    'color: #8B5CF6; font-weight: bold;'
  );
})();
