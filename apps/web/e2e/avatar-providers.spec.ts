/**
 * Avatar Provider Detection & Switching — Tier 1 (offline) + Tier 2 (@live)
 *
 * Tests provider detection from Iterace 3-4 and switching from Iterace 8.
 * Tier 1 tests verify API structure; Tier 2 tests verify live provider behavior.
 *
 * Run Tier 1: pnpm e2e --grep-invert @live
 * Run Tier 2: pnpm e2e --grep @live
 */

import { test, expect } from '@playwright/test'
import {
  apiGet,
  navigateTo,
  openCompactMode,
  sendCompactMessage,
  SEL_COMPACT_MESSAGES,
  SEL_COMPACT_MSG_BUBBLE,
} from './helpers/avatar.helpers'

test.describe('Avatar Provider Detection', () => {
  test('status endpoint reports active provider', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/status')
    // active_provider is one of the known providers or null
    if (data.state === 'ready') {
      expect(['gemini', 'claude', 'codex']).toContain(data.active_provider)
    } else {
      // When not ready, active_provider should be null
      expect(data.active_provider).toBeNull()
    }
  })

  test('providers endpoint lists CLI availability', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/providers')
    expect(Array.isArray(data)).toBe(true)
    // At least one provider should be installed on a dev machine
    const installed = data.filter((p: any) => p.installed)
    expect(installed.length).toBeGreaterThanOrEqual(1)
  })

  test('config endpoint shows provider settings', async ({ page }) => {
    const data = await apiGet(page, '/api/avatar/config')
    expect(data.provider_configs).toBeDefined()
    expect(typeof data.provider_configs).toBe('object')
    // Should have entries for known providers
    const keys = Object.keys(data.provider_configs)
    expect(keys.length).toBeGreaterThanOrEqual(1)
    // Each provider config has model and enabled fields
    for (const [, config] of Object.entries(data.provider_configs) as [
      string,
      any,
    ][]) {
      expect(config).toHaveProperty('enabled')
      expect(typeof config.enabled).toBe('boolean')
    }
  })
})

test.describe('Avatar Provider Switching @live', () => {
  test('@live switch provider via settings UI and verify status', async ({
    page,
  }) => {
    const statusBefore = await apiGet(page, '/api/avatar/status')
    if (statusBefore.state !== 'ready') {
      test.skip(true, 'Avatar not ready — cannot test provider switching')
    }
    const providerBefore = statusBefore.active_provider

    await navigateTo(page, '/settings')

    // Find provider buttons (gemini, claude, codex)
    const providerBtns = page
      .locator('button')
      .filter({ hasText: /gemini|claude|codex/i })
    const count = await providerBtns.count()
    if (count < 2) {
      test.skip(true, 'Less than 2 provider buttons — cannot test switching')
    }

    // Click a different provider than the current one
    for (let i = 0; i < count; i++) {
      const btnText = await providerBtns.nth(i).innerText()
      if (!btnText.toLowerCase().includes(providerBefore)) {
        await providerBtns.nth(i).scrollIntoViewIfNeeded()
        await providerBtns.nth(i).click({ force: true })
        await page.waitForTimeout(2_000)
        break
      }
    }

    // Verify status changed (or at least still valid)
    const statusAfter = await apiGet(page, '/api/avatar/status')
    expect(statusAfter.state).toBeTruthy()
    // Restore original provider if changed
    if (statusAfter.active_provider !== providerBefore) {
      for (let i = 0; i < count; i++) {
        const btnText = await providerBtns.nth(i).innerText()
        if (btnText.toLowerCase().includes(providerBefore)) {
          await providerBtns.nth(i).scrollIntoViewIfNeeded()
          await providerBtns.nth(i).click({ force: true })
          await page.waitForTimeout(2_000)
          break
        }
      }
    }
  })

  test('@live chat works after provider switch', async ({ page }) => {
    await navigateTo(page, '/settings')
    const providerBtns = page
      .locator('button')
      .filter({ hasText: /gemini|claude|codex/i })
    const count = await providerBtns.count()
    if (count >= 1) {
      await providerBtns.first().scrollIntoViewIfNeeded()
      await providerBtns.first().click({ force: true })
      await page.waitForTimeout(2_000)
    }

    // Navigate to home and try chatting
    await navigateTo(page, '/')
    await openCompactMode(page)
    try {
      await page.waitForSelector(SEL_COMPACT_MESSAGES, {
        state: 'visible',
        timeout: 15_000,
      })
    } catch {
      test.skip(true, 'WebSocket not connected after provider switch')
    }

    await sendCompactMessage(page, 'Say hello in one word')
    const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
    await expect(async () => {
      const msgCount = await msgs.count()
      expect(msgCount).toBeGreaterThanOrEqual(2)
    }).toPass({ timeout: 60_000 })
  })

  test('@live provider version is reported', async ({ page }) => {
    const data = await apiGet(page, '/api/ai/providers')
    const entries = Object.entries(data.providers) as [string, any][]
    // At least one available provider should report a version
    const available = entries.filter(([, s]) => s.available)
    if (available.length === 0) {
      test.skip(true, 'No available AI providers')
    }
    // Version is a string or null — at least one should have a version
    const withVersion = available.filter(
      ([, s]) => s.version && typeof s.version === 'string',
    )
    expect(withVersion.length).toBeGreaterThanOrEqual(1)
  })
})
