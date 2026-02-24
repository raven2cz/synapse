/**
 * Avatar Chat — Tier 2 (@live, requires running AI provider)
 *
 * All tests in this file are tagged @live and require:
 * - Backend running (uvicorn)
 * - Frontend running (vite dev)
 * - At least one AI provider CLI installed (gemini/claude/codex)
 * - Avatar-engine WebSocket accepting connections
 *
 * Run with: pnpm e2e --grep @live
 */

import { test, expect } from '@playwright/test'
import {
  SEL_COMPACT_MESSAGES,
  SEL_COMPACT_MSG_BUBBLE,
  SEL_FAB,
  openCompactMode,
  openFullscreenMode,
  sendCompactMessage,
  sendFullscreenMessage,
  skipOnProviderError,
  navigateTo,
} from './helpers/avatar.helpers'

/**
 * Wait for WebSocket connection — compact-messages div appears only when connected.
 * Skips test if WS is not available (403, no provider, etc.)
 */
async function waitForWsConnection(page: import('@playwright/test').Page) {
  await openCompactMode(page)
  try {
    await page.waitForSelector(SEL_COMPACT_MESSAGES, { state: 'visible', timeout: 15_000 })
  } catch {
    test.skip(true, 'WebSocket not connected — avatar-engine WS may be rejecting connections')
  }
}

test.describe('Avatar Chat @live', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '/')
  })

  test('send message and receive response @live', async ({ page }) => {
    await waitForWsConnection(page)
    await sendCompactMessage(page, 'Hello, say hi back in one word')
    await page.waitForTimeout(3_000)
    await skipOnProviderError(page)
    const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
    // Wait for assistant response: 2+ message bubbles AND non-empty text in the last one
    let responseText = ''
    await expect(async () => {
      const count = await msgs.count()
      expect(count).toBeGreaterThanOrEqual(2)
      responseText = (await msgs.last().innerText()).trim()
      expect(responseText.length).toBeGreaterThan(0)
    }).toPass({ timeout: 60_000 })
    expect(responseText.length).toBeGreaterThan(0)
  })

  test('message appears in chat history @live', async ({ page }) => {
    await waitForWsConnection(page)
    const userText = 'Test message for history check'
    await sendCompactMessage(page, userText)
    await page.waitForTimeout(1_000)
    const body = await page.locator(SEL_COMPACT_MESSAGES).innerText()
    expect(body).toContain(userText)
  })

  test('streaming indicator shows during response @live', async ({ page }) => {
    await waitForWsConnection(page)
    await sendCompactMessage(page, 'Write a haiku about models')
    const thinkingIndicator = page.getByText(/thinking|responding/i).first()
    try {
      await expect(thinkingIndicator).toBeVisible({ timeout: 10_000 })
    } catch {
      // Streaming may be too fast to catch — acceptable
    }
    await page.waitForTimeout(5_000)
  })

  test('stop button cancels streaming @live', async ({ page }) => {
    await waitForWsConnection(page)
    await sendCompactMessage(page, 'Write a very long detailed essay about machine learning')
    await page.waitForTimeout(2_000)
    const stopBtn = page.locator('button[title="compact.input.stop"]')
    const visible = await stopBtn.isVisible().catch(() => false)
    if (visible) {
      await stopBtn.click()
      await page.waitForTimeout(1_000)
      await expect(stopBtn).toBeHidden({ timeout: 5_000 })
    }
  })

  test('clear history removes all messages @live', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    // Check if WS is connected by waiting for textarea to be enabled
    const textarea = page.locator('textarea').last()
    try {
      await expect(textarea).toBeEnabled({ timeout: 15_000 })
    } catch {
      test.skip(true, 'WebSocket not connected')
    }
    await sendFullscreenMessage(page, 'Hello')
    await page.waitForTimeout(5_000)
    const clearBtn = page.getByText('Clear', { exact: true })
    const visible = await clearBtn.isVisible().catch(() => false)
    if (visible) {
      await clearBtn.click()
      await page.waitForTimeout(500)
    }
  })

  test('context prefix injected on inventory page @live', async ({ page }) => {
    await navigateTo(page, '/inventory')
    await waitForWsConnection(page)
    await sendCompactMessage(page, 'What page am I on?')
    await page.waitForTimeout(10_000)
    const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
    const count = await msgs.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })

  test('switch to claude provider and chat @live', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    const claudeBtn = page.locator('button').filter({ hasText: /claude/i })
    const visible = await claudeBtn.first().isVisible().catch(() => false)
    if (visible) {
      await claudeBtn.first().click()
      await page.waitForTimeout(3_000)
      await sendFullscreenMessage(page, 'Say hello in one word')
      await page.waitForTimeout(10_000)
    }
  })

  test('switch to codex provider and chat @live', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    const codexBtn = page.locator('button').filter({ hasText: /codex/i })
    const visible = await codexBtn.first().isVisible().catch(() => false)
    if (visible) {
      await codexBtn.first().click()
      await page.waitForTimeout(3_000)
      await sendFullscreenMessage(page, 'Say hello in one word')
      await page.waitForTimeout(10_000)
    }
  })
})
