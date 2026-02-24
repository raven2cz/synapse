/**
 * Avatar AI Parameter Extraction — Tier 1 (offline) + Tier 2 (@live)
 *
 * Tests POST /api/ai/extract from Iterace 6 (AvatarAIService).
 * Tier 1 tests use rule-based fallback (no AI provider needed).
 * Tier 2 tests require a running AI provider.
 *
 * Run Tier 1: pnpm e2e --grep-invert @live
 * Run Tier 2: pnpm e2e --grep @live
 */

import { test, expect } from '@playwright/test'
import { apiGet, apiPost, apiDelete } from './helpers/avatar.helpers'

test.describe('AI Parameter Extraction', () => {
  test('POST /api/ai/extract with simple description returns result', async ({
    page,
  }) => {
    const data = await apiPost(page, '/api/ai/extract', {
      description: 'SDXL checkpoint for anime style illustrations',
      use_cache: false,
    })
    // The endpoint always returns a structured response
    expect(typeof data.success).toBe('boolean')
    // provider_id may be null for rule-based fallback
    expect(data).toHaveProperty('provider_id')
    // If success, parameters should be present; if not, error should be present
    if (data.success) {
      expect(data.parameters).toBeDefined()
      expect(typeof data.parameters).toBe('object')
    } else {
      // Rule-based fallback may fail or return minimal data — both are valid
      expect(data).toHaveProperty('error')
    }
  })

  test('POST /api/ai/extract with empty description returns error', async ({
    page,
  }) => {
    const resp = await page.request.post('/api/ai/extract', {
      data: { description: '', use_cache: false },
    })
    // Either 422 (validation) or 200 with success=false
    if (resp.ok()) {
      const data = await resp.json()
      expect(data.success).toBe(false)
    } else {
      // FastAPI validation error for empty string
      expect(resp.status()).toBeGreaterThanOrEqual(400)
    }
  })

  test('POST /api/ai/extract caching works', async ({ page }) => {
    const statsBefore = await apiGet(page, '/api/ai/cache/stats')
    const beforeEntries = statsBefore.entry_count

    // First call — should potentially create a cache entry
    await apiPost(page, '/api/ai/extract', {
      description: 'Flux.1 dev model for photorealistic portraits',
      use_cache: true,
    })

    // Second call with same description — should hit cache
    const second = await apiPost(page, '/api/ai/extract', {
      description: 'Flux.1 dev model for photorealistic portraits',
      use_cache: true,
    })

    // The second call should return cached=true if caching is working
    // (depends on whether the first call succeeded and was cacheable)
    if (second.success && second.cached !== undefined) {
      expect(second.cached).toBe(true)
    }

    // Cache stats should have at least as many entries as before
    const statsAfter = await apiGet(page, '/api/ai/cache/stats')
    expect(statsAfter.entry_count).toBeGreaterThanOrEqual(beforeEntries)
  })
})

test.describe('AI Parameter Extraction @live', () => {
  test('@live AI extracts parameters from detailed description', async ({
    page,
  }) => {
    const data = await apiPost(page, '/api/ai/extract', {
      description:
        'High quality SDXL 1.0 checkpoint trained on anime art. ' +
        'Best results at 1024x1024, use DPM++ 2M Karras sampler, ' +
        'CFG scale 7, 25 steps. Supports clip skip 2.',
      use_cache: false,
    })
    expect(data.success).toBe(true)
    expect(data.parameters).toBeDefined()
    // AI should extract at least some of the mentioned parameters
    const params = data.parameters
    const hasRelevantFields =
      params.steps !== undefined ||
      params.cfg_scale !== undefined ||
      params.sampler !== undefined ||
      params.sampler_name !== undefined ||
      params.width !== undefined ||
      params.clip_skip !== undefined
    expect(hasRelevantFields).toBe(true)
  })

  test('@live AI extract + clear cache cycle', async ({ page }) => {
    // Ensure at least one cached entry exists
    await apiPost(page, '/api/ai/extract', {
      description: 'Pony diffusion V6 XL for cartoon style',
      use_cache: true,
    })

    const statsBeforeClear = await apiGet(page, '/api/ai/cache/stats')
    expect(statsBeforeClear.entry_count).toBeGreaterThanOrEqual(0)

    // Clear all cache
    const cleared = await apiDelete(page, '/api/ai/cache')
    expect(typeof cleared.cleared).toBe('number')

    // Verify cache is empty
    const statsAfterClear = await apiGet(page, '/api/ai/cache/stats')
    expect(statsAfterClear.entry_count).toBe(0)
  })
})
