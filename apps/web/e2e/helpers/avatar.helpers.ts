/**
 * Shared Playwright helpers for avatar-engine E2E tests.
 *
 * IMPORTANT: @avatar-engine/react uses RAW i18n keys as aria-labels
 * (not translated strings). Selectors must match the raw key format.
 */

import type { Page } from '@playwright/test'

// ─── Selectors ──────────────────────────────────────────────────────

/** FAB button that opens the chat panel (raw i18n key) */
export const SEL_FAB = 'button[aria-label="fab.openChatPanel"]'

/** Expand to fullscreen button in compact header */
export const SEL_COMPACT_EXPAND = 'button[aria-label="compact.header.expandFullscreen"]'

/** Close button in compact header */
export const SEL_COMPACT_CLOSE = 'button[aria-label="compact.header.closePanel"]'

/**
 * Compact mode message list container.
 * Only rendered when WS is connected — use SEL_COMPACT_CLOSE to detect compact mode.
 */
export const SEL_COMPACT_MESSAGES = '.compact-messages'

/**
 * Individual message bubbles inside the compact message list.
 * Each message is a div.flex (user: flex-row-reverse, assistant: flex-row).
 * The last child of .compact-messages is an empty scroll-anchor div — excluded by .flex.
 */
export const SEL_COMPACT_MSG_BUBBLE = '.compact-messages > .flex'

/** Send button in compact mode */
export const SEL_COMPACT_SEND = 'button[title="compact.input.send"]'

/** Switch to compact mode button in fullscreen status bar */
export const SEL_FULLSCREEN_COMPACT = 'button[aria-label="fullscreen.statusBar.switchCompact"]'

/** Chat panel in fullscreen */
export const SEL_CHAT_PANEL = '[aria-label="chat.panel"]'

/** Suggestion chip buttons rendered by SuggestionChips.tsx (Synapse component) */
export const SEL_SUGGESTION_CHIP = '.flex.flex-wrap.gap-2.mb-3 button'

// ─── Helpers ────────────────────────────────────────────────────────

/**
 * Wait for the Synapse app to be fully loaded.
 * Checks that the sidebar navigation is present.
 */
export async function waitForAppReady(page: Page) {
  await page.waitForSelector('nav', { state: 'visible', timeout: 15_000 })
}

/**
 * Poll the avatar status endpoint until the expected state is returned.
 */
export async function waitForAvatarStatus(
  page: Page,
  expectedState: string,
  timeout = 10_000,
) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const resp = await page.request.get('/api/avatar/status')
    if (resp.ok()) {
      const data = await resp.json()
      if (data.state === expectedState) return data
    }
    await page.waitForTimeout(500)
  }
  throw new Error(`Avatar status did not reach "${expectedState}" within ${timeout}ms`)
}

/**
 * Click the FAB to open compact chat mode.
 * Waits for the compact header close button to appear (proves compact is open).
 * Note: .compact-messages only renders when WS is connected.
 */
export async function openCompactMode(page: Page) {
  const fab = page.locator(SEL_FAB)
  await fab.waitFor({ state: 'visible', timeout: 10_000 })
  await fab.click()
  // Compact mode is open when the close button in compact header is visible
  await page.waitForSelector(SEL_COMPACT_CLOSE, {
    state: 'visible',
    timeout: 5_000,
  })
}

/**
 * From compact mode, expand to fullscreen.
 * Waits for the StatusBar compact-mode switcher to appear.
 */
export async function openFullscreenMode(page: Page) {
  await page.click(SEL_COMPACT_EXPAND)
  await page.waitForSelector(SEL_FULLSCREEN_COMPACT, {
    state: 'visible',
    timeout: 5_000,
  })
}

/**
 * Type text into the compact chat textarea and press Enter to send.
 */
export async function sendCompactMessage(page: Page, text: string) {
  const textarea = page.locator('textarea').last()
  await textarea.waitFor({ state: 'visible', timeout: 5_000 })
  await textarea.fill(text)
  await textarea.press('Enter')
}

/**
 * Type text into the fullscreen chat textarea and press Enter to send.
 */
export async function sendFullscreenMessage(page: Page, text: string) {
  const textarea = page.locator('textarea').last()
  await textarea.waitFor({ state: 'visible', timeout: 5_000 })
  await textarea.fill(text)
  await textarea.press('Enter')
}

/**
 * Wait for at least one assistant message to appear in the compact chat.
 * Returns the text content of the last assistant message.
 */
export async function waitForAssistantMessage(
  page: Page,
  timeout = 30_000,
): Promise<string> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const compactMsgs = page.locator(SEL_COMPACT_MSG_BUBBLE)
    const count = await compactMsgs.count()
    if (count >= 2) {
      const lastMsg = compactMsgs.last()
      const text = await lastMsg.innerText()
      if (text.trim().length > 0) return text.trim()
    }
    await page.waitForTimeout(500)
  }
  throw new Error(`No assistant message appeared within ${timeout}ms`)
}

/**
 * Navigate to a specific path and wait for the app to be ready.
 */
export async function navigateTo(page: Page, path: string) {
  await page.goto(path)
  await waitForAppReady(page)
}

/**
 * Check if the chat shows a provider error (quota exceeded, rate limit, etc.)
 * and skip the test if so. Call after sending a message and waiting briefly.
 */
export async function skipOnProviderError(page: Page) {
  const body = await page.locator('body').innerText()
  const lower = body.toLowerCase()
  if (
    lower.includes('exhausted your capacity') ||
    lower.includes('quota') ||
    lower.includes('rate limit') ||
    lower.includes('429') ||
    lower.includes('resource_exhausted')
  ) {
    const { test } = await import('@playwright/test')
    test.skip(true, 'AI provider quota/rate limit exceeded')
  }
}

// ─── API helpers ─────────────────────────────────────────────────────

/** GET request to backend API, returns parsed JSON. */
export async function apiGet(page: Page, path: string): Promise<any> {
  const resp = await page.request.get(path)
  return resp.json()
}

/** POST request to backend API, returns parsed JSON. */
export async function apiPost(page: Page, path: string, body: any): Promise<any> {
  const resp = await page.request.post(path, { data: body })
  return resp.json()
}

/** DELETE request to backend API, returns parsed JSON. */
export async function apiDelete(page: Page, path: string): Promise<any> {
  const resp = await page.request.delete(path)
  return resp.json()
}

// ─── WebSocket interception ──────────────────────────────────────────

/**
 * Intercept outgoing WebSocket messages from the page.
 * Monkey-patches WebSocket.prototype.send in the browser context.
 * Returns a function that retrieves all captured messages when called.
 */
export async function interceptWsMessages(
  page: Page,
): Promise<() => Promise<string[]>> {
  await page.evaluate(() => {
    ;(window as any).__capturedWsMessages = [] as string[]
    const origSend = WebSocket.prototype.send
    WebSocket.prototype.send = function (data: string | ArrayBufferLike | Blob | ArrayBufferView) {
      if (typeof data === 'string') {
        ;(window as any).__capturedWsMessages.push(data)
      }
      return origSend.call(this, data)
    }
  })

  return async () => {
    return page.evaluate(() => {
      const msgs = (window as any).__capturedWsMessages as string[]
      return [...msgs]
    })
  }
}
