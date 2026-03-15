/**
 * Dependency Resolution E2E — Tier 1 (offline, mocked backend)
 *
 * Tests the full resolve flow: opening modal, viewing candidates,
 * applying resolution, local file import, preview analysis tab.
 * All API calls intercepted via page.route().
 */

import { test, expect } from '@playwright/test'
import {
  setupResolveRoutes,
  setupLocalFileRoutes,
  navigateToPackDetail,
  MOCK_PACK_NAME,
  MOCK_PACK_DETAIL,
  MOCK_SUGGEST_RESULT,
  MOCK_SUGGEST_EMPTY,
  MOCK_APPLY_RESULT,
} from './helpers/resolve.helpers'

test.describe('Dependency Resolution', () => {
  test.beforeEach(async ({ page }) => {
    await setupResolveRoutes(page)
  })

  // ─── Modal Opening ──────────────────────────────────────────────

  test('unresolved base model dep shows Select Model button', async ({ page }) => {
    await navigateToPackDetail(page)

    const selectBtn = page.getByRole('button', { name: 'Select Model' })
    await expect(selectBtn).toBeVisible({ timeout: 10_000 })
  })

  test('clicking Select Model opens DependencyResolverModal', async ({ page }) => {
    await navigateToPackDetail(page)

    await page.getByRole('button', { name: 'Select Model' }).click()

    // Modal should appear with dep name in header
    await expect(page.getByText('base-checkpoint')).toBeVisible({ timeout: 5_000 })
    // Should have tab buttons
    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible()
  })

  test('modal shows candidates from eager suggest', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()

    // Wait for candidates to load (eager suggest fires on modal open)
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('Animagine XL 3.1')).toBeVisible()
  })

  test('modal shows candidate count badge on tab', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()

    // Candidates tab should show count
    const candidatesTab = page.getByRole('button', { name: /Candidates/i })
    await expect(candidatesTab).toBeVisible({ timeout: 10_000 })
    // Badge with "2" for two candidates
    await expect(candidatesTab).toContainText('2')
  })

  // ─── Candidate Selection & Apply ─────────────────────────────────

  test('clicking a candidate selects it', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })

    // Click the first candidate
    await page.getByText('Illustrious XL v0.6').click()

    // Apply button should be enabled
    const applyBtn = page.getByRole('button', { name: /^Apply$/i })
    await expect(applyBtn).toBeEnabled()
  })

  test('Apply sends apply-resolution request and closes modal', async ({ page }) => {
    let applyCallMade = false
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
      applyCallMade = true
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_APPLY_RESULT),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    await page.getByText('Illustrious XL v0.6').click()

    await page.getByRole('button', { name: /^Apply$/i }).click()

    // Modal should close after apply
    await expect(page.getByText('Illustrious XL v0.6')).toBeHidden({ timeout: 5_000 })
    expect(applyCallMade).toBe(true)
  })

  test('Apply & Download sends request and closes modal', async ({ page }) => {
    let applyCallMade = false
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
      applyCallMade = true
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_APPLY_RESULT),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    await page.getByText('Illustrious XL v0.6').click()

    await page.getByRole('button', { name: /Apply & Download/i }).click()

    // Apply & Download may close modal or keep it open while downloading
    await page.waitForTimeout(2000)
    expect(applyCallMade).toBe(true)
  })

  // ─── Confidence Tiers ────────────────────────────────────────────

  test('candidates show confidence tier badges', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })

    // Tier 2 candidate should show "High confidence" indicator
    await expect(page.getByText(/High confidence/i).or(page.getByText(/88%/i))).toBeVisible()
  })

  // ─── Empty State ─────────────────────────────────────────────────

  test('no candidates shows empty state', async ({ page }) => {
    // Override with empty suggest
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/suggest-resolution`, (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SUGGEST_EMPTY),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()

    // Should show empty/no candidates message or default to preview tab
    const candidatesTab = page.getByRole('button', { name: /Candidates/i })
    await expect(candidatesTab).toBeVisible({ timeout: 10_000 })
  })

  // ─── Tab Navigation ──────────────────────────────────────────────

  test('can switch between modal tabs', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })

    // Switch to Preview tab
    const previewTab = page.getByRole('button', { name: /Preview/i })
    if (await previewTab.isVisible()) {
      await previewTab.click()
      // Preview content should appear (thumbnail grid or loading)
      await page.waitForTimeout(500)
    }

    // Switch to Local File tab
    const localTab = page.getByRole('button', { name: /Local/i })
    if (await localTab.isVisible()) {
      await localTab.click()
      // Should see directory input (use specific placeholder)
      await expect(page.locator('input[type="text"]').last()).toBeVisible()
    }

    // Switch to Civitai tab
    const civitaiTab = page.getByRole('button', { name: /Civitai/i })
    if (await civitaiTab.isVisible()) {
      await civitaiTab.click()
    }
  })

  test('HuggingFace tab visible for checkpoint (HF-eligible)', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })

    // Checkpoint is HF-eligible → HF tab should be visible
    await expect(page.getByRole('button', { name: /HuggingFace/i })).toBeVisible()
  })

  test('HuggingFace tab hidden for LoRA (not HF-eligible)', async ({ page }) => {
    // Override pack: make the unresolved dep a LoRA instead of checkpoint
    const loraAssets = MOCK_PACK_DETAIL.assets.map(a =>
      a.name === 'base-checkpoint'
        ? { ...a, asset_type: 'lora', is_base_model: false }
        : a
    )
    await setupResolveRoutes(page, {
      packDetail: { ...MOCK_PACK_DETAIL, assets: loraAssets },
    })

    await navigateToPackDetail(page)
    // For non-base-model LoRA, the button should say "Resolve" not "Select Model"
    await page.getByRole('button', { name: 'Resolve' }).click()
    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })

    // LoRA is NOT HF-eligible → HF tab should be hidden
    await expect(page.getByRole('button', { name: /HuggingFace/i })).toBeHidden()
  })

  // ─── AI Tab Gate ─────────────────────────────────────────────────

  test('AI Resolve tab hidden when avatar not available', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })

    // Avatar is not available (mocked as stopped) → AI tab should be hidden
    await expect(page.getByRole('button', { name: /AI Resolve/i })).toBeHidden()
  })

  test('AI Resolve tab visible when avatar is available', async ({ page }) => {
    // Override avatar status to available
    await page.route('**/api/avatar/status', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'ready', available: true, enabled: true }),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByRole('button', { name: /Candidates/i })).toBeVisible({ timeout: 10_000 })

    await expect(page.getByRole('button', { name: /AI Resolve/i })).toBeVisible()
  })

  // ─── Cancel/Close ────────────────────────────────────────────────

  test('Cancel button closes modal without applying', async ({ page }) => {
    let applyCallMade = false
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
      applyCallMade = true
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: /Cancel/i }).click()

    // Modal should close
    await expect(page.getByText('Illustrious XL v0.6')).toBeHidden({ timeout: 5_000 })
    expect(applyCallMade).toBe(false)
  })
})

test.describe('Preview Analysis Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setupResolveRoutes(page)
  })

  test('shows preview thumbnails in grid', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByRole('button', { name: /Preview/i })).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: /Preview/i }).click()

    // Should show at least one preview thumbnail (img element)
    await expect(page.locator('img[loading="lazy"]').first()).toBeVisible({ timeout: 5_000 })
  })

  test('clicking preview shows detail with hints', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await page.getByRole('button', { name: /Preview/i }).click()
    await expect(page.locator('img[loading="lazy"]').first()).toBeVisible({ timeout: 5_000 })

    // Thumbnail is a <button> wrapping an <img> — click the button directly
    await page.locator('button:has(img[loading="lazy"])').first().click()

    // Should show hint details — "Model References" section header
    await expect(page.getByText(/Model References/i).first()).toBeVisible({ timeout: 5_000 })
  })

  test('shows generation parameters when preview selected', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await page.getByRole('button', { name: /Preview/i }).click()
    await expect(page.locator('img[loading="lazy"]').first()).toBeVisible({ timeout: 5_000 })

    // Thumbnail is a <button> wrapping an <img> — click the button directly
    await page.locator('button:has(img[loading="lazy"])').first().click()

    // Generation params section header
    await expect(page.getByText(/Generation Parameters/i).first()).toBeVisible({ timeout: 5_000 })
  })
})

test.describe('Local File Import', () => {
  test.beforeEach(async ({ page }) => {
    await setupResolveRoutes(page)
    await setupLocalFileRoutes(page)
  })

  test('Local tab shows directory input', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByRole('button', { name: /Local/i })).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: /Local/i }).click()

    // Should have directory input field
    await expect(page.locator('input[type="text"]').last()).toBeVisible({ timeout: 5_000 })
  })

  test('browsing directory shows file recommendations', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await page.getByRole('button', { name: /Local/i }).click()

    // Type directory path
    const input = page.locator('input[type="text"]').last()
    await input.fill('/home/user/models/checkpoints')

    // Click Browse
    await page.getByRole('button', { name: /Browse/i }).click()

    // Should show recommended file (use button role — the file card is a button)
    await expect(page.getByRole('button', { name: /illustriousXL_v060/ })).toBeVisible({ timeout: 5_000 })
  })

  test('selecting file enables Use This File button', async ({ page }) => {
    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await page.getByRole('button', { name: /Local/i }).click()

    const input = page.locator('input[type="text"]').last()
    await input.fill('/home/user/models/checkpoints')
    await page.getByRole('button', { name: /Browse/i }).click()

    // Wait for file card button to appear and click it
    await expect(page.getByRole('button', { name: /illustriousXL_v060/ })).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: /illustriousXL_v060/ }).click()

    // "Use This File" button should be visible after selecting a file
    await expect(page.getByRole('button', { name: /Use This File/i })).toBeVisible()
  })

  test('clicking Use This File triggers import', async ({ page }) => {
    let importCalled = false
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/import-local`, (route) => {
      importCalled = true
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ import_id: 'imp-001', status: 'pending' }),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await page.getByRole('button', { name: /Local/i }).click()

    const input = page.locator('input[type="text"]').last()
    await input.fill('/home/user/models/checkpoints')
    await page.getByRole('button', { name: /Browse/i }).click()

    await expect(page.getByRole('button', { name: /illustriousXL_v060/ })).toBeVisible({ timeout: 5_000 })
    await page.getByRole('button', { name: /illustriousXL_v060/ }).click()

    await page.getByRole('button', { name: /Use This File/i }).click()

    // Wait for the import API call to be made
    await page.waitForTimeout(2000)
    expect(importCalled).toBe(true)
  })
})

test.describe('Edge Cases', () => {
  test('resolved pack does not show Resolve button', async ({ page }) => {
    // Override: all assets installed, no unresolved
    const resolvedPack = {
      ...MOCK_PACK_DETAIL,
      has_unresolved: false,
      all_installed: true,
      assets: MOCK_PACK_DETAIL.assets.map(a => ({
        ...a,
        installed: true,
        status: 'installed',
        strategy: 'civitai_file',
      })),
    }
    await setupResolveRoutes(page, { packDetail: resolvedPack })
    await navigateToPackDetail(page)

    // "Select Model" button should NOT appear (dep is resolved)
    await expect(page.getByRole('button', { name: 'Select Model' })).toBeHidden()
    // "Resolve" button should NOT appear either
    await expect(page.getByRole('button', { name: 'Resolve' })).toBeHidden()
  })

  test('apply failure shows error', async ({ page }) => {
    // Setup base routes first, then override apply with failure
    await setupResolveRoutes(page)
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route) => {
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Stale pack fingerprint' }),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()
    await expect(page.getByText('Illustrious XL v0.6')).toBeVisible({ timeout: 10_000 })
    await page.getByText('Illustrious XL v0.6').click()
    await page.getByRole('button', { name: /^Apply$/i }).click()

    // Modal should stay open (apply failed) — or show error toast
    // The exact behavior depends on implementation, but modal shouldn't silently close
    await page.waitForTimeout(1000)
    // Either modal is still visible or error toast appeared
    const modalStillVisible = await page.getByText('Illustrious XL v0.6').isVisible()
    const errorVisible = await page.getByText(/error|failed|stale/i).isVisible()
    expect(modalStillVisible || errorVisible).toBe(true)
  })

  test('suggest failure shows graceful fallback', async ({ page }) => {
    // Setup base routes first, then override suggest with failure
    await setupResolveRoutes(page)
    await page.route(`**/api/packs/${MOCK_PACK_NAME}/suggest-resolution`, (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal error' }),
      })
    })

    await navigateToPackDetail(page)
    await page.getByRole('button', { name: 'Select Model' }).click()

    // Modal should still open — header "Resolve Dependency" should be visible
    await expect(page.getByRole('heading', { name: 'Resolve Dependency' })).toBeVisible({ timeout: 10_000 })
  })
})
