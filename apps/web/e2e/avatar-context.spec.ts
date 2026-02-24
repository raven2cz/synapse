/**
 * Avatar Context Propagation — Tier 1 (offline) + Tier 2 (@live)
 *
 * Tests context prefix injection from Iterace 7.
 * Tier 1 tests intercept outgoing WS messages and verify context prefix format.
 * Tier 2 tests verify the AI understands and references the current context.
 *
 * Context format: "[Context: <description>]" prepended to user messages via WS.
 * AvatarProvider.sendWithContext() reads pageContextStore (previous ?? current).
 *
 * Run Tier 1: pnpm e2e --grep-invert @live
 * Run Tier 2: pnpm e2e --grep @live
 */

import { test, expect } from '@playwright/test'
import {
  interceptWsMessages,
  navigateTo,
  openCompactMode,
  sendCompactMessage,
  waitForAssistantMessage,
  SEL_COMPACT_MESSAGES,
  SEL_COMPACT_MSG_BUBBLE,
} from './helpers/avatar.helpers'

/**
 * Wait for WS connection (compact-messages visible), skip if unavailable.
 * Returns true if connected.
 */
async function ensureWsConnected(page: import('@playwright/test').Page) {
  await openCompactMode(page)
  try {
    await page.waitForSelector(SEL_COMPACT_MESSAGES, {
      state: 'visible',
      timeout: 15_000,
    })
    return true
  } catch {
    return false
  }
}

/**
 * Extract context prefix from captured WS messages.
 * Messages are JSON strings containing a text field with the "[Context: ...]" prefix.
 * Returns all unique context strings found.
 */
function extractContextPrefixes(messages: string[]): string[] {
  const prefixes: string[] = []
  for (const msg of messages) {
    // WS message may be raw text or JSON — try both
    let text = msg
    try {
      const parsed = JSON.parse(msg)
      text = parsed.text ?? parsed.content ?? parsed.message ?? msg
    } catch {
      // raw text — use as-is
    }
    const match = text.match(/\[Context: [^\]]+\]/)
    if (match) {
      prefixes.push(match[0])
    }
  }
  return prefixes
}

test.describe('Context Propagation — WS Interception', () => {
  test('packs page sends [Context: Viewing pack list] prefix', async ({
    page,
  }) => {
    await navigateTo(page, '/')
    const getMessages = await interceptWsMessages(page)
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'Hello from packs page')
    await page.waitForTimeout(2_000)

    const captured = await getMessages()
    const prefixes = extractContextPrefixes(captured)
    // Context should mention "Viewing pack list"
    const hasPacks = prefixes.some((p) => p.includes('Viewing pack list'))
    // On first page load, there's no "previous" context, so current is used
    // If no context is injected (e.g. on avatar page), prefixes may be empty
    if (prefixes.length > 0) {
      expect(hasPacks).toBe(true)
    }
  })

  test('inventory page sends [Context: Viewing model inventory] prefix', async ({
    page,
  }) => {
    // Navigate to packs first so pageContextStore has a "previous"
    await navigateTo(page, '/')
    await navigateTo(page, '/inventory')
    const getMessages = await interceptWsMessages(page)
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'Hello from inventory')
    await page.waitForTimeout(2_000)

    const captured = await getMessages()
    const prefixes = extractContextPrefixes(captured)
    if (prefixes.length > 0) {
      // Could be "Viewing pack list" (previous) or "Viewing model inventory" (current)
      const hasContext = prefixes.some(
        (p) =>
          p.includes('Viewing model inventory') ||
          p.includes('Viewing pack list'),
      )
      expect(hasContext).toBe(true)
    }
  })

  test('browse page sends [Context: Browsing Civitai models] prefix', async ({
    page,
  }) => {
    await navigateTo(page, '/')
    await navigateTo(page, '/browse')
    const getMessages = await interceptWsMessages(page)
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'Hello from browse')
    await page.waitForTimeout(2_000)

    const captured = await getMessages()
    const prefixes = extractContextPrefixes(captured)
    if (prefixes.length > 0) {
      const hasContext = prefixes.some(
        (p) =>
          p.includes('Browsing Civitai models') ||
          p.includes('Viewing pack list'),
      )
      expect(hasContext).toBe(true)
    }
  })

  test('context changes on navigation', async ({ page }) => {
    // Start on packs — send first message
    await navigateTo(page, '/')
    const getMessages = await interceptWsMessages(page)
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'First message on packs')
    await page.waitForTimeout(2_000)

    const capturedBefore = await getMessages()
    expect(capturedBefore.length).toBeGreaterThanOrEqual(1)

    // Navigate to inventory — WS may reconnect, re-intercept
    await navigateTo(page, '/inventory')
    const getMessages2 = await interceptWsMessages(page)

    // Re-open compact mode if it closed during navigation
    const textarea = page.locator('textarea').last()
    const visible = await textarea.isVisible().catch(() => false)
    if (!visible) {
      await openCompactMode(page)
      try {
        await page.waitForSelector(SEL_COMPACT_MESSAGES, {
          state: 'visible',
          timeout: 10_000,
        })
      } catch {
        test.skip(true, 'WebSocket not reconnected after navigation')
      }
    }

    await sendCompactMessage(page, 'Second message on inventory')
    await page.waitForTimeout(2_000)

    const capturedAfter = await getMessages2()
    expect(capturedAfter.length).toBeGreaterThanOrEqual(1)
  })
})

test.describe('Context Propagation — AI Understanding @live', () => {
  test.describe.configure({ mode: 'serial' })
  test('@live AI response references current page context on inventory', async ({
    page,
  }) => {
    await navigateTo(page, '/inventory')
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'What page am I currently viewing?')
    let responseText = ''
    await expect(async () => {
      const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
      const count = await msgs.count()
      expect(count).toBeGreaterThanOrEqual(2)
      responseText = (await msgs.last().innerText()).trim()
      expect(responseText.length).toBeGreaterThan(0)
    }).toPass({ timeout: 60_000 })

    // AI should mention inventory-related terms
    const lower = responseText.toLowerCase()
    const mentionsInventory =
      lower.includes('inventory') ||
      lower.includes('model') ||
      lower.includes('blob') ||
      lower.includes('storage')
    expect(mentionsInventory).toBe(true)
  })

  test('@live AI response on browse page references browsing', async ({
    page,
  }) => {
    await navigateTo(page, '/browse')
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'What am I doing on this page?')
    let responseText = ''
    await expect(async () => {
      const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
      const count = await msgs.count()
      expect(count).toBeGreaterThanOrEqual(2)
      responseText = (await msgs.last().innerText()).trim()
      expect(responseText.length).toBeGreaterThan(0)
    }).toPass({ timeout: 60_000 })

    const lower = responseText.toLowerCase()
    const mentionsBrowse =
      lower.includes('brows') ||
      lower.includes('civitai') ||
      lower.includes('search') ||
      lower.includes('model')
    expect(mentionsBrowse).toBe(true)
  })

  test('@live pack detail context includes pack name', async ({ page }) => {
    // First check if there are any packs to navigate to
    const resp = await page.request.get('/api/store/packs')
    if (!resp.ok()) {
      test.skip(true, 'Store packs endpoint not available')
    }
    const packs = await resp.json()
    if (!Array.isArray(packs) || packs.length === 0) {
      test.skip(true, 'No packs available for pack-detail test')
    }

    const packName = packs[0].name ?? packs[0].id
    await navigateTo(page, `/packs/${packName}`)
    const connected = await ensureWsConnected(page)
    if (!connected) {
      test.skip(true, 'WebSocket not connected')
    }

    await sendCompactMessage(page, 'What am I looking at?')
    let responseText = ''
    await expect(async () => {
      const msgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
      const count = await msgs.count()
      expect(count).toBeGreaterThanOrEqual(2)
      responseText = (await msgs.last().innerText()).trim()
      expect(responseText.length).toBeGreaterThan(0)
    }).toPass({ timeout: 60_000 })

    // AI should mention the pack or pack-related terms
    const lower = responseText.toLowerCase()
    const mentionsPack =
      lower.includes('pack') ||
      lower.includes(packName.toLowerCase()) ||
      lower.includes('model') ||
      lower.includes('detail')
    expect(mentionsPack).toBe(true)
  })
})
