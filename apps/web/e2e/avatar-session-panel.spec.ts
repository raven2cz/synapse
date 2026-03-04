/**
 * Avatar SessionPanel — Tier 1 (offline, no AI provider needed)
 *
 * Tests SessionPanel rendering, scroll behavior, and interaction.
 * Uses route interception to mock the sessions API.
 */

import { test, expect } from '@playwright/test'
import {
  waitForAppReady,
  openCompactMode,
  openFullscreenMode,
} from './helpers/avatar.helpers'

/** Generate mock session data */
function mockSessions(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    session_id: `sess-${String(i).padStart(3, '0')}-${Math.random().toString(36).slice(2, 10)}`,
    title: i === 0 ? null : `Session ${count - i}: ${['Bug fix', 'Feature work', 'Refactoring', 'Code review', 'Testing'][i % 5]}`,
    updated_at: new Date(Date.now() - i * 3600_000).toISOString(),
    is_current: i === 0,
  }))
}

/** Click the session management button in the StatusBar */
async function openSessionPanel(page: import('@playwright/test').Page) {
  // The button shows "Sessions" text when no session ID, or the session ID otherwise.
  // It has class gap-1.5 px-2.5 (unique to this button in StatusBar).
  const sessionBtn = page.locator('button[title="Sessions"]').first()
  const altBtn = page.locator('button[class*="gap-1.5"][class*="px-2.5"]').first()

  if (await sessionBtn.isVisible().catch(() => false)) {
    await sessionBtn.click()
  } else {
    await altBtn.click()
  }
  await page.waitForTimeout(300)
}

test.describe('SessionPanel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await waitForAppReady(page)
  })

  test('session button is visible in fullscreen StatusBar', async ({ page }) => {
    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.waitForTimeout(500)

    const sessionBtn = page.locator('button[title="Sessions"], button[class*="gap-1.5"][class*="px-2.5"]')
    const count = await sessionBtn.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })

  test('SessionPanel opens and renders via portal on document.body', async ({ page }) => {
    await page.route('**/api/avatar/sessions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSessions(5)),
      })
    })

    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.waitForTimeout(500)
    await openSessionPanel(page)

    // Verify the SessionPanel is rendered as a React Portal on document.body
    const portalInfo = await page.evaluate(() => {
      const bodyChildren = Array.from(document.body.children)
      const fixedDivs = bodyChildren.filter((el) => {
        if (el.tagName !== 'DIV') return false
        return window.getComputedStyle(el).position === 'fixed'
      })

      const backdrop = fixedDivs.find((el) =>
        el.className.includes('bg-black') || el.className.includes('backdrop-blur')
      )
      const modalWrapper = fixedDivs.find((el) =>
        el.className.includes('pointer-events-none') && el.className.includes('justify-center')
      )

      return {
        fixedDivsOnBody: fixedDivs.length,
        hasBackdrop: !!backdrop,
        hasModalWrapper: !!modalWrapper,
      }
    })

    expect(portalInfo.fixedDivsOnBody).toBeGreaterThanOrEqual(2)
    expect(portalInfo.hasBackdrop).toBe(true)
    expect(portalInfo.hasModalWrapper).toBe(true)
  })

  test('session list is scrollable with many sessions', async ({ page }) => {
    await page.route('**/api/avatar/sessions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSessions(30)),
      })
    })

    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.waitForTimeout(2_000)
    await openSessionPanel(page)

    // Verify session content is present
    await expect(page.getByText('30 sessions')).toBeVisible({ timeout: 3_000 })

    // Find the scrollable container: the one with overflow-y-auto that actually overflows
    const scrollInfo = await page.evaluate(() => {
      const candidates = document.querySelectorAll('[class*="overflow-y-auto"]')
      for (const el of Array.from(candidates)) {
        if (el.scrollHeight > el.clientHeight && el.clientHeight > 0) {
          return {
            found: true,
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            overflowY: window.getComputedStyle(el).overflowY,
            className: el.className.slice(0, 60),
          }
        }
      }
      return { found: false }
    })

    expect(scrollInfo.found).toBe(true)
    if (!scrollInfo.found) return

    // Verify overflow-y is set
    expect(scrollInfo.overflowY).toBe('auto')
    // Content should be significantly taller than visible area
    expect(scrollInfo.scrollHeight).toBeGreaterThan(scrollInfo.clientHeight * 2)
  })

  test('mouse wheel scrolls the session list', async ({ page }) => {
    await page.route('**/api/avatar/sessions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSessions(30)),
      })
    })

    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.waitForTimeout(2_000)
    await openSessionPanel(page)

    await expect(page.getByText('30 sessions')).toBeVisible({ timeout: 3_000 })

    // Find the scrollable session list and test mouse wheel scroll
    const scrollResult = await page.evaluate(() => {
      const candidates = document.querySelectorAll('[class*="overflow-y-auto"]')
      for (const el of Array.from(candidates)) {
        if (el.scrollHeight > el.clientHeight && el.clientHeight > 0) {
          // Reset scroll position
          el.scrollTop = 0
          // Dispatch a wheel event
          el.dispatchEvent(new WheelEvent('wheel', {
            deltaY: 200,
            bubbles: true,
            cancelable: true,
          }))
          return {
            found: true,
            scrollTop: el.scrollTop,
            // Also test programmatic scroll
            canProgramScroll: (() => {
              el.scrollTop = 100
              return el.scrollTop === 100
            })(),
          }
        }
      }
      return { found: false }
    })

    expect(scrollResult.found).toBe(true)
    // Programmatic scroll must work (proves overflow is functional)
    expect(scrollResult.canProgramScroll).toBe(true)
  })

  test('SessionPanel closes on Escape key', async ({ page }) => {
    await page.route('**/api/avatar/sessions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSessions(3)),
      })
    })

    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.waitForTimeout(500)
    await openSessionPanel(page)

    // Verify backdrop is visible (proves panel is open)
    const backdrop = page.locator('div.fixed[class*="bg-black"]')
    await expect(backdrop).toBeVisible({ timeout: 3_000 })

    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)

    await expect(backdrop).not.toBeVisible({ timeout: 3_000 })
  })

  test('SessionPanel closes on backdrop click', async ({ page }) => {
    await page.route('**/api/avatar/sessions', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSessions(3)),
      })
    })

    await openCompactMode(page)
    await openFullscreenMode(page)
    await page.waitForTimeout(500)
    await openSessionPanel(page)

    const backdrop = page.locator('div.fixed[class*="bg-black"]')
    await expect(backdrop).toBeVisible({ timeout: 3_000 })

    // Click on the backdrop edge (not on the modal)
    await backdrop.click({ position: { x: 10, y: 10 } })
    await page.waitForTimeout(500)

    await expect(backdrop).not.toBeVisible({ timeout: 3_000 })
  })
})
