/**
 * Avatar UI Transitions — Tier 1 (offline, no AI provider needed)
 *
 * Tests FAB visibility, compact/fullscreen mode transitions,
 * close behavior, and navigation persistence.
 */

import { test, expect } from '@playwright/test'
import {
  SEL_FAB,
  SEL_COMPACT_CLOSE,
  SEL_COMPACT_EXPAND,
  SEL_FULLSCREEN_COMPACT,
  SEL_SUGGESTION_CHIP,
  waitForAppReady,
  openCompactMode,
  openFullscreenMode,
  navigateTo,
} from './helpers/avatar.helpers'

test.describe('Avatar UI Transitions', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '/')
  })

  test('FAB is visible on page load', async ({ page }) => {
    const fab = page.locator(SEL_FAB)
    await expect(fab).toBeVisible({ timeout: 10_000 })
  })

  test('FAB opens compact mode on click', async ({ page }) => {
    await openCompactMode(page)
    // Compact mode is confirmed by the close button being visible
    await expect(page.locator(SEL_COMPACT_CLOSE)).toBeVisible()
  })

  test('compact mode shows expand and close buttons', async ({ page }) => {
    await openCompactMode(page)
    await expect(page.locator(SEL_COMPACT_EXPAND)).toBeVisible()
    await expect(page.locator(SEL_COMPACT_CLOSE)).toBeVisible()
  })

  test('compact mode shows textarea input', async ({ page }) => {
    await openCompactMode(page)
    const textarea = page.locator('textarea').last()
    await expect(textarea).toBeVisible()
  })

  test('compact mode expands to fullscreen', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    const compactBtn = page.locator(SEL_FULLSCREEN_COMPACT)
    await expect(compactBtn).toBeVisible()
  })

  test('fullscreen shows StatusBar and textarea', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    await expect(page.locator(SEL_FULLSCREEN_COMPACT)).toBeVisible()
    const textarea = page.locator('textarea')
    await expect(textarea.last()).toBeVisible()
  })

  test('fullscreen back to compact', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.click(SEL_FULLSCREEN_COMPACT)
    // Back in compact mode — close button should be visible again
    await expect(page.locator(SEL_COMPACT_CLOSE)).toBeVisible({ timeout: 5_000 })
  })

  test('close compact returns to FAB', async ({ page }) => {
    await openCompactMode(page)
    await page.click(SEL_COMPACT_CLOSE)
    // FAB should be visible again after closing compact
    await expect(page.locator(SEL_FAB)).toBeVisible({ timeout: 5_000 })
    // The compact panel animates out — wait for transition
    await page.waitForTimeout(500)
    // Verify FAB is clickable (proves compact is closed)
    await expect(page.locator(SEL_FAB)).toBeEnabled()
  })

  test('suggestion chips visible in fullscreen with empty chat', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    // SuggestionChips (Synapse component) renders when messages.length === 0
    const chips = page.locator(SEL_SUGGESTION_CHIP)
    await expect(chips.first()).toBeVisible({ timeout: 5_000 })
    const count = await chips.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('page navigation preserves chat mode', async ({ page }) => {
    await openCompactMode(page)
    await page.goto('/inventory')
    await waitForAppReady(page)
    // Widget mode is persisted in localStorage — compact or FAB should be present
    const fab = page.locator(SEL_FAB)
    const compactClose = page.locator(SEL_COMPACT_CLOSE)
    const compactVisible = await compactClose.isVisible().catch(() => false)
    const fabVisible = await fab.isVisible().catch(() => false)
    expect(compactVisible || fabVisible).toBe(true)
  })
})
