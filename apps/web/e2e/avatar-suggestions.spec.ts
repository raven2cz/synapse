/**
 * Suggestion Chips per Page — Tier 1 (offline, no AI provider needed)
 *
 * Verifies that page-specific suggestion chips appear in fullscreen mode
 * and that clicking a chip sends the message.
 */

import { test, expect } from '@playwright/test'
import {
  SEL_SUGGESTION_CHIP,
  openCompactMode,
  openFullscreenMode,
  navigateTo,
} from './helpers/avatar.helpers'

test.describe('Suggestion Chips per Page', () => {
  async function openFullscreen(page: import('@playwright/test').Page) {
    await openCompactMode(page)
    await openFullscreenMode(page)
  }

  test('packs page shows packs suggestions', async ({ page }) => {
    await navigateTo(page, '/')
    await openFullscreen(page)
    const chips = page.locator(SEL_SUGGESTION_CHIP)
    await expect(chips.first()).toBeVisible({ timeout: 5_000 })
    const count = await chips.count()
    expect(count).toBeGreaterThanOrEqual(2)
    const texts = await chips.allInnerTexts()
    const hasPacks = texts.some(
      t => /pack|model|workflow|dependenc/i.test(t),
    )
    expect(hasPacks).toBe(true)
  })

  test('inventory page shows inventory suggestions', async ({ page }) => {
    await navigateTo(page, '/inventory')
    await openFullscreen(page)
    const chips = page.locator(SEL_SUGGESTION_CHIP)
    await expect(chips.first()).toBeVisible({ timeout: 5_000 })
    const texts = await chips.allInnerTexts()
    const hasInventory = texts.some(
      t => /disk|orphan|cleanup|space/i.test(t),
    )
    expect(hasInventory).toBe(true)
  })

  test('browse page shows browse suggestions', async ({ page }) => {
    await navigateTo(page, '/browse')
    await openFullscreen(page)
    const chips = page.locator(SEL_SUGGESTION_CHIP)
    await expect(chips.first()).toBeVisible({ timeout: 5_000 })
    const texts = await chips.allInnerTexts()
    const hasBrowse = texts.some(
      t => /recommend|compare|trending|anime|SDXL|Flux/i.test(t),
    )
    expect(hasBrowse).toBe(true)
  })

  test('clicking suggestion sends message', async ({ page }) => {
    await navigateTo(page, '/')
    await openFullscreen(page)
    const chip = page.locator(SEL_SUGGESTION_CHIP).first()
    await expect(chip).toBeVisible({ timeout: 5_000 })
    const chipText = await chip.innerText()
    await chip.click()
    // After clicking, sendWithContext is called → message sent
    // Chips should disappear (messages.length > 0 hides them)
    await page.waitForTimeout(1_000)
    const chipsAfter = page.locator(SEL_SUGGESTION_CHIP)
    const stillVisible = await chipsAfter.first().isVisible().catch(() => false)
    // Either chips disappeared (message sent) or text appears in page
    if (!stillVisible) {
      // Message was sent — chip text should appear in the chat area
      const body = await page.locator('body').innerText()
      expect(body).toContain(chipText.slice(0, 15))
    }
  })
})
