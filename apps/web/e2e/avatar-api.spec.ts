/**
 * Avatar API Endpoints — Tier 1 (offline, no AI provider needed)
 *
 * Tests backend API endpoints from Iterace 1-2 (feature flag, config, routes)
 * and AI service endpoints from Iterace 3-4, 6.
 * Uses page.request (Playwright API context) — no UI interaction needed.
 *
 * Run with: pnpm e2e --grep-invert @live
 */

import { test, expect } from '@playwright/test'
import { apiGet } from './helpers/avatar.helpers'

test.describe('Avatar API Endpoints', () => {
  test('GET /api/avatar/status returns valid state', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/status')
    expect(data.state).toBeTruthy()
    expect([
      'ready',
      'no_provider',
      'no_engine',
      'setup_required',
      'disabled',
      'incompatible',
    ]).toContain(data.state)
    expect(typeof data.engine_installed).toBe('boolean')
    // engine_version is string or null
    expect(
      data.engine_version === null || typeof data.engine_version === 'string',
    ).toBe(true)
    expect(typeof data.available).toBe('boolean')
    expect(typeof data.enabled).toBe('boolean')
  })

  test('GET /api/avatar/config returns config', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/config')
    expect(typeof data.enabled).toBe('boolean')
    expect(data.provider).toBeTruthy()
    expect(data.skills_count).toBeDefined()
    expect(typeof data.skills_count.builtin).toBe('number')
    expect(data.skills_count.builtin).toBeGreaterThanOrEqual(1)
    // Skills object has builtin/custom arrays
    expect(Array.isArray(data.skills.builtin)).toBe(true)
    expect(Array.isArray(data.skills.custom)).toBe(true)
  })

  test('GET /api/avatar/providers returns list', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/providers')
    expect(Array.isArray(data)).toBe(true)
    expect(data.length).toBeGreaterThanOrEqual(1)
    for (const provider of data) {
      expect(provider).toHaveProperty('name')
      expect(typeof provider.installed).toBe('boolean')
      expect(provider).toHaveProperty('command')
    }
  })

  test('GET /api/avatar/skills returns skills', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/skills')
    expect(Array.isArray(data.builtin)).toBe(true)
    for (const skill of data.builtin) {
      expect(skill).toHaveProperty('name')
      expect(skill).toHaveProperty('path')
      expect(typeof skill.size).toBe('number')
      expect(skill).toHaveProperty('category')
    }
  })

  test('GET /api/avatar/avatars returns avatars', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/avatars')
    expect(Array.isArray(data.builtin)).toBe(true)
    expect(data.builtin.length).toBe(8)
    const ids = data.builtin.map((a: any) => a.id)
    for (const expected of [
      'bella',
      'heart',
      'nicole',
      'sky',
      'adam',
      'michael',
      'george',
      'astronautka',
    ]) {
      expect(ids).toContain(expected)
    }
    // Custom array is optional but should be an array if present
    if (data.custom !== undefined) {
      expect(Array.isArray(data.custom)).toBe(true)
    }
  })

  test('GET /api/ai/providers detects providers', async ({ page }) => {
    const data = await apiGet(page, '/api/ai/providers')
    expect(data.providers).toBeDefined()
    expect(typeof data.providers).toBe('object')
    expect(typeof data.available_count).toBe('number')
    expect(typeof data.running_count).toBe('number')
    // Each provider has expected fields
    for (const [, status] of Object.entries(data.providers) as [string, any][]) {
      expect(typeof status.available).toBe('boolean')
      expect(typeof status.running).toBe('boolean')
      expect(Array.isArray(status.models)).toBe(true)
    }
  })

  test('GET /api/ai/settings returns config', async ({ page }) => {
    const data = await apiGet(page, '/api/ai/settings')
    expect(typeof data.enabled).toBe('boolean')
    expect(typeof data.providers).toBe('object')
    expect(typeof data.task_priorities).toBe('object')
    expect(typeof data.cache_enabled).toBe('boolean')
  })

  test('GET /api/ai/cache/stats returns stats', async ({ page }) => {
    const data = await apiGet(page, '/api/ai/cache/stats')
    expect(typeof data.entry_count).toBe('number')
    expect(typeof data.total_size_bytes).toBe('number')
    expect(typeof data.total_size_mb).toBe('number')
    expect(typeof data.ttl_days).toBe('number')
  })

  test('GET /api/ai/tasks returns registered task types', async ({ page }) => {
    const data = await apiGet(page, '/api/ai/tasks')
    expect(Array.isArray(data.tasks)).toBe(true)
    expect(data.tasks.length).toBeGreaterThanOrEqual(1)
    // parameter_extraction must be registered
    const paramTask = data.tasks.find(
      (t: any) => t.task_type === 'parameter_extraction',
    )
    expect(paramTask).toBeDefined()
    expect(Array.isArray(paramTask.skill_names)).toBe(true)
    expect(paramTask.skill_names).toContain('generation-params')
    expect(typeof paramTask.has_fallback).toBe('boolean')
    expect(paramTask.has_fallback).toBe(true)
  })

  test('status endpoint remains consistent after sequential calls', async ({
    page,
  }) => {
    const first = await apiGet(page, '/api/avatar/status')
    expect(first.state).toBeTruthy()

    // Second call should return the same state (cached or consistent)
    const second = await apiGet(page, '/api/avatar/status')
    expect(second.state).toBe(first.state)
    expect(second.engine_installed).toBe(first.engine_installed)
  })
})
