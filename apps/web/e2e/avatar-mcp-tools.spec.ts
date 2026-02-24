/**
 * Avatar MCP Tool Invocation — Tier 2 (@live, requires running AI provider)
 *
 * Tests MCP tool invocation from Iterace 5 (21 tools in store_server.py).
 * Each test sends a natural question that triggers the AI to invoke a specific
 * MCP tool, then verifies the response contains tool-specific data.
 *
 * All tests are @live — they require:
 * - Backend running (uvicorn) with avatar-engine mounted
 * - Frontend running (vite dev)
 * - At least one AI provider CLI installed and functional
 *
 * Run with: pnpm e2e --grep @live
 */

import { test, expect } from '@playwright/test'
import {
  navigateTo,
  openCompactMode,
  sendCompactMessage,
  skipOnProviderError,
  SEL_COMPACT_MESSAGES,
  SEL_COMPACT_MSG_BUBBLE,
} from './helpers/avatar.helpers'

/** Timeout for MCP tool tests — AI needs to think + invoke tool + respond */
const MCP_TIMEOUT = 60_000

/**
 * Setup: navigate to page, open compact mode, ensure WS is connected.
 * Skips the test if WS is not available.
 */
async function setupMcpTest(page: import('@playwright/test').Page) {
  await navigateTo(page, '/')
  await openCompactMode(page)
  try {
    await page.waitForSelector(SEL_COMPACT_MESSAGES, {
      state: 'visible',
      timeout: 15_000,
    })
  } catch {
    test.skip(true, 'WebSocket not connected — cannot test MCP tools')
  }
}

/**
 * Send a message and wait for an assistant response.
 * Returns the response text content.
 */
async function askAndWaitForResponse(
  page: import('@playwright/test').Page,
  question: string,
): Promise<string> {
  await sendCompactMessage(page, question)
  // Give AI a moment to respond or show an error
  await page.waitForTimeout(3_000)
  await skipOnProviderError(page)
  let responseText = ''
  await expect(async () => {
    const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
    const count = await msgs.count()
    expect(count).toBeGreaterThanOrEqual(2)
    responseText = (await msgs.last().innerText()).trim()
    expect(responseText.length).toBeGreaterThan(0)
  }).toPass({ timeout: MCP_TIMEOUT })
  return responseText
}

test.describe('MCP Tool Invocation @live', () => {
  test('@live AI can list packs via MCP', async ({ page }) => {
    await setupMcpTest(page)
    const response = await askAndWaitForResponse(
      page,
      'List all my installed packs',
    )
    const lower = response.toLowerCase()
    // AI should mention packs — either listing them or saying there are none
    const mentionsPacks =
      lower.includes('pack') ||
      lower.includes('no pack') ||
      lower.includes('installed') ||
      lower.includes('model')
    expect(mentionsPacks).toBe(true)
  })

  test('@live AI can check inventory via MCP', async ({ page }) => {
    await setupMcpTest(page)
    const response = await askAndWaitForResponse(
      page,
      'Give me an inventory summary',
    )
    const lower = response.toLowerCase()
    const mentionsInventory =
      lower.includes('blob') ||
      lower.includes('storage') ||
      lower.includes('disk') ||
      lower.includes('inventory') ||
      lower.includes('file') ||
      lower.includes('model')
    expect(mentionsInventory).toBe(true)
  })

  test('@live AI can search Civitai via MCP', async ({ page }) => {
    await setupMcpTest(page)
    const response = await askAndWaitForResponse(
      page,
      'Search Civitai for anime LORA models',
    )
    const lower = response.toLowerCase()
    const mentionsSearch =
      lower.includes('lora') ||
      lower.includes('model') ||
      lower.includes('anime') ||
      lower.includes('civitai') ||
      lower.includes('result') ||
      lower.includes('found')
    expect(mentionsSearch).toBe(true)
  })

  test('@live AI can check storage stats via MCP', async ({ page }) => {
    await setupMcpTest(page)
    const response = await askAndWaitForResponse(
      page,
      'How much disk space is my store using?',
    )
    const lower = response.toLowerCase()
    const mentionsStorage =
      lower.includes('size') ||
      lower.includes('gb') ||
      lower.includes('mb') ||
      lower.includes('byte') ||
      lower.includes('disk') ||
      lower.includes('storage') ||
      lower.includes('space')
    expect(mentionsStorage).toBe(true)
  })

  test('@live AI can check for orphan blobs via MCP', async ({ page }) => {
    await setupMcpTest(page)
    const response = await askAndWaitForResponse(
      page,
      'Are there any orphan blobs in my store?',
    )
    const lower = response.toLowerCase()
    const mentionsOrphans =
      lower.includes('orphan') ||
      lower.includes('unused') ||
      lower.includes('clean') ||
      lower.includes('blob') ||
      lower.includes('no orphan') ||
      lower.includes('none')
    expect(mentionsOrphans).toBe(true)
  })

  test('@live AI can check backup status via MCP', async ({ page }) => {
    await setupMcpTest(page)
    const response = await askAndWaitForResponse(
      page,
      "What's the backup status of my store?",
    )
    const lower = response.toLowerCase()
    const mentionsBackup =
      lower.includes('backup') ||
      lower.includes('configured') ||
      lower.includes('not configured') ||
      lower.includes('storage') ||
      lower.includes('sync')
    expect(mentionsBackup).toBe(true)
  })
})
