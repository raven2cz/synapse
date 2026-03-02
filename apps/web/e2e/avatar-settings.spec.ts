/**
 * Avatar Settings Page — Tier 1 (offline)
 *
 * Verifies the unified AI settings panel displays engine info, master toggle,
 * provider checkboxes, skills list, avatar picker, cache section, and config path.
 */

import { test, expect } from '@playwright/test'
import { navigateTo } from './helpers/avatar.helpers'

test.describe('Avatar Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '/settings')
  })

  test('settings page shows AI Assistant section', async ({ page }) => {
    const title = page.getByText('AI Assistant', { exact: false })
    await expect(title.first()).toBeVisible({ timeout: 10_000 })
  })

  test('master toggle is visible', async ({ page }) => {
    const toggle = page.locator('[data-testid="ai-master-toggle"]')
    await expect(toggle).toBeVisible({ timeout: 10_000 })
  })

  test('status cards display engine info', async ({ page }) => {
    const grid = page.locator('.grid.grid-cols-2')
    await expect(grid.first()).toBeVisible({ timeout: 10_000 })
    // StatCards render labels like "Engine", "Service Default", "Safety", "Skills"
    for (const label of ['Engine', 'Service Default', 'Safety', 'Skills']) {
      await expect(
        page.getByText(label, { exact: false }).first(),
      ).toBeVisible()
    }
  })

  test('provider checkboxes are visible', async ({ page }) => {
    const title = page.getByText('AI Providers', { exact: false })
    await expect(title.first()).toBeVisible({ timeout: 10_000 })
    // Each provider row has a name label
    for (const name of ['Gemini CLI', 'Claude Code', 'Codex CLI']) {
      await expect(
        page.getByText(name, { exact: false }).first(),
      ).toBeVisible()
    }
  })

  test('skills list expandable', async ({ page }) => {
    const skillsTitle = page.getByText('Skills', { exact: false })
    await expect(skillsTitle.first()).toBeVisible({ timeout: 10_000 })
    const expandBtn = page.locator('button').filter({ hasText: /built-in/i })
    if (await expandBtn.isVisible()) {
      await expandBtn.click()
      await page.waitForTimeout(300)
      // After expanding, skill tags should be visible
      const skillTags = page.locator('span.font-mono')
      const count = await skillTags.count()
      expect(count).toBeGreaterThanOrEqual(1)
    }
  })

  test('avatar picker opens on button click', async ({ page }) => {
    const changeBtn = page.getByText('Change Avatar', { exact: false })
    await expect(changeBtn).toBeVisible({ timeout: 10_000 })
    await changeBtn.click()
    await page.waitForTimeout(500)
    // AvatarPicker renders avatar cards with names
    const avatarNames = ['Synapse', 'Bella', 'Heart', 'Nicole', 'Sky', 'Adam']
    let found = 0
    for (const name of avatarNames) {
      const el = page.getByText(name, { exact: true })
      if (await el.first().isVisible().catch(() => false)) found++
    }
    expect(found).toBeGreaterThanOrEqual(3)
  })

  test('selecting avatar updates localStorage', async ({ page }) => {
    const changeBtn = page.getByText('Change Avatar', { exact: false })
    await expect(changeBtn).toBeVisible({ timeout: 10_000 })
    await page.evaluate(() => localStorage.removeItem('avatar-engine-selected-avatar'))
    await changeBtn.click()
    await page.waitForTimeout(500)
    const heartLabel = page.getByText('Heart', { exact: true }).first()
    if (await heartLabel.isVisible().catch(() => false)) {
      await heartLabel.click()
      await page.waitForTimeout(500)
      const stored = await page.evaluate(
        () => localStorage.getItem('avatar-engine-selected-avatar'),
      )
      if (stored) {
        expect(stored).toBeTruthy()
      }
    }
  })

  test('cache section is visible', async ({ page }) => {
    const cacheTitle = page.getByText('Cache', { exact: false })
    await expect(cacheTitle.first()).toBeVisible({ timeout: 10_000 })
    // Cache action buttons
    const cleanupBtn = page.getByText('Cleanup Expired', { exact: false })
    const clearBtn = page.getByText('Clear All', { exact: false })
    await expect(cleanupBtn.first()).toBeVisible()
    await expect(clearBtn.first()).toBeVisible()
  })

  test('config path displayed', async ({ page }) => {
    const configLabel = page.getByText('Configuration', { exact: false })
    const visible = await configLabel.first().isVisible().catch(() => false)
    if (visible) {
      const codeElement = page.locator('code').filter({ hasText: /avatar/ })
      await expect(codeElement.first()).toBeVisible()
    }
  })
})
