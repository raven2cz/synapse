/**
 * Shared helpers and mock data for resolve E2E tests.
 *
 * All API responses are intercepted via page.route() — no real backend needed.
 */

import type { Page, Route } from '@playwright/test'

// ─── Mock Data ──────────────────────────────────────────────────────

export const MOCK_PACK_NAME = 'test-lora-pack'

export const MOCK_PACK_DETAIL = {
  name: MOCK_PACK_NAME,
  version: '1.0',
  description: 'Test LoRA pack with unresolved deps',
  author: 'test-author',
  tags: ['lora', 'anime'],
  user_tags: [],
  installed: false,
  has_unresolved: true,
  all_installed: false,
  can_generate: false,
  assets: [
    {
      name: 'base-checkpoint',
      asset_type: 'checkpoint',
      source: 'civitai',
      size: 6_800_000_000,
      installed: false,
      status: 'unresolved',
      filename: 'illustriousXL_v060.safetensors',
      required: true,
      is_base_model: true,
      strategy: 'base_model_hint',
    },
    {
      name: 'main-lora',
      asset_type: 'lora',
      source: 'civitai',
      size: 150_000_000,
      installed: true,
      status: 'installed',
      filename: 'my_lora_v1.safetensors',
      required: true,
      url: 'https://civitai.com/api/download/models/12345',
    },
  ],
  previews: [
    {
      filename: '001.png',
      url: '/previews/test-lora-pack/001.png',
      nsfw: false,
      width: 1024,
      height: 1536,
      media_type: 'image',
    },
  ],
  workflows: [],
  custom_nodes: [],
  docs: {},
  pack: {
    schema: '2.0',
    name: MOCK_PACK_NAME,
    pack_type: 'lora',
    pack_category: 'external',
    source: { provider: 'civitai', model_id: 99999 },
    base_model: 'Illustrious XL',
  },
}

export const MOCK_SUGGEST_RESULT = {
  request_id: 'req-001',
  candidates: [
    {
      candidate_id: 'cand-001',
      display_name: 'Illustrious XL v0.6',
      provider: 'civitai',
      confidence: 0.88,
      tier: 2,
      evidence_groups: [
        {
          provenance: 'preview:001.png',
          items: [
            {
              source: 'preview_api_meta',
              description: 'Preview metadata references Illustrious XL',
              confidence: 0.85,
            },
          ],
        },
      ],
      selector_strategy: 'civitai_file',
      base_model: 'SDXL 1.0',
      compatibility_warnings: [],
    },
    {
      candidate_id: 'cand-002',
      display_name: 'Animagine XL 3.1',
      provider: 'civitai',
      confidence: 0.55,
      tier: 3,
      evidence_groups: [
        {
          provenance: 'file:illustriousXL_v060.safetensors',
          items: [
            {
              source: 'file_metadata',
              description: 'Filename pattern match',
              confidence: 0.55,
            },
          ],
        },
      ],
      selector_strategy: 'civitai_file',
      base_model: 'SDXL 1.0',
      compatibility_warnings: [],
    },
  ],
  pack_fingerprint: 'abc123',
  warnings: [],
}

export const MOCK_SUGGEST_EMPTY = {
  request_id: 'req-002',
  candidates: [],
  pack_fingerprint: 'abc123',
  warnings: [],
}

export const MOCK_APPLY_RESULT = {
  success: true,
  message: 'Applied Illustrious XL v0.6',
  compatibility_warnings: [],
}

export const MOCK_PREVIEW_ANALYSIS = {
  pack_name: MOCK_PACK_NAME,
  previews: [
    {
      filename: '001.png',
      url: '/previews/test-lora-pack/001.png',
      thumbnail_url: '/previews/test-lora-pack/001.png',
      media_type: 'image',
      width: 1024,
      height: 1536,
      nsfw: false,
      hints: [
        {
          filename: 'illustriousXL_v060.safetensors',
          kind: 'checkpoint',
          source_type: 'api_meta',
          raw_value: 'Illustrious XL v0.6',
          resolvable: true,
          hash: 'abcd1234',
          weight: null,
        },
        {
          filename: 'my_lora_v1.safetensors',
          kind: 'lora',
          source_type: 'api_meta',
          raw_value: 'My LoRA v1',
          resolvable: true,
          hash: null,
          weight: 0.8,
        },
      ],
      generation_params: {
        sampler: 'Euler a',
        steps: 25,
        cfg_scale: 7.5,
        seed: 123456,
        width: 1024,
        height: 1536,
      },
    },
  ],
  total_hints: 2,
}

export const MOCK_LOCAL_BROWSE = {
  directory: '/home/user/models/checkpoints',
  files: [
    {
      name: 'illustriousXL_v060.safetensors',
      path: '/home/user/models/checkpoints/illustriousXL_v060.safetensors',
      size: 6_800_000_000,
      mtime: 1709900000,
      extension: '.safetensors',
      cached_hash: null,
    },
    {
      name: 'sdxl_base_1.0.safetensors',
      path: '/home/user/models/checkpoints/sdxl_base_1.0.safetensors',
      size: 6_900_000_000,
      mtime: 1709800000,
      extension: '.safetensors',
      cached_hash: null,
    },
  ],
  total_count: 2,
  error: null,
}

export const MOCK_LOCAL_RECOMMEND = {
  recommendations: [
    {
      file: MOCK_LOCAL_BROWSE.files[0],
      match_type: 'filename_exact',
      confidence: 0.85,
      reason: 'Filename matches dependency exactly',
    },
  ],
}

export const MOCK_IMPORT_PENDING = {
  import_id: 'imp-001',
  pack_name: MOCK_PACK_NAME,
  dep_id: 'base-checkpoint',
  filename: 'illustriousXL_v060.safetensors',
  file_size: 6_800_000_000,
  status: 'importing',
  stage: 'hashing',
  progress: 0.3,
  result: null,
}

export const MOCK_IMPORT_COMPLETED = {
  ...MOCK_IMPORT_PENDING,
  status: 'completed',
  stage: 'done',
  progress: 1.0,
  result: {
    success: true,
    sha256: 'abcdef1234567890abcdef1234567890',
    file_size: 6_800_000_000,
    display_name: 'Illustrious XL v0.6',
    enrichment_source: 'civitai_hash',
    message: 'Successfully imported and enriched from Civitai',
  },
}

// ─── Route Setup ────────────────────────────────────────────────────

/**
 * Setup all API route intercepts for the resolve test pack.
 * Call in beforeEach to mock the backend completely.
 */
export async function setupResolveRoutes(page: Page, overrides?: {
  packDetail?: object
  suggestResult?: object
  applyResult?: object
  previewAnalysis?: object
}) {
  const packDetail = overrides?.packDetail ?? MOCK_PACK_DETAIL
  const suggestResult = overrides?.suggestResult ?? MOCK_SUGGEST_RESULT
  const applyResult = overrides?.applyResult ?? MOCK_APPLY_RESULT
  const previewAnalysis = overrides?.previewAnalysis ?? MOCK_PREVIEW_ANALYSIS

  // Pack list (sidebar/navigation)
  await page.route('**/api/packs', (route: Route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { name: MOCK_PACK_NAME, pack_type: 'lora', installed: false, has_unresolved: true },
        ]),
      })
    } else {
      route.continue()
    }
  })

  // Pack detail
  await page.route(`**/api/packs/${MOCK_PACK_NAME}`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(packDetail),
    })
  })

  // Suggest resolution (pack-level: POST /api/packs/{pack}/suggest-resolution)
  await page.route(`**/api/packs/${MOCK_PACK_NAME}/suggest-resolution`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(suggestResult),
    })
  })

  // Apply resolution (pack-level: POST /api/packs/{pack}/apply-resolution)
  await page.route(`**/api/packs/${MOCK_PACK_NAME}/apply-resolution`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(applyResult),
    })
  })

  // Preview analysis
  await page.route(`**/api/packs/${MOCK_PACK_NAME}/preview-analysis**`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(previewAnalysis),
    })
  })

  // Avatar status (AI not available by default)
  await page.route('**/api/avatar/status', (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ state: 'stopped', available: false, enabled: false }),
    })
  })

  // Downloads (none active)
  await page.route('**/api/store/downloads', (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ downloads: {} }),
    })
  })

  // Backup status (not configured)
  const backupResponse = {
    pack: MOCK_PACK_NAME,
    backup_enabled: false,
    backup_connected: false,
    blobs: [],
    summary: { total: 0, local_only: 0, backup_only: 0, both: 0, nowhere: 0, total_bytes: 0 },
  }
  await page.route(`**/api/store/backup/pack-status/${MOCK_PACK_NAME}`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(backupResponse),
    })
  })

  // Preview images — return 1x1 transparent PNG
  await page.route('**/previews/**', (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        'base64'
      ),
    })
  })
}

/**
 * Setup local file browsing routes for Local Resolve tab tests.
 */
export async function setupLocalFileRoutes(page: Page) {
  // Browse local directory
  await page.route('**/api/store/browse-local**', (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_LOCAL_BROWSE),
    })
  })

  // Recommend local file
  await page.route(`**/api/packs/${MOCK_PACK_NAME}/recommend-local**`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_LOCAL_RECOMMEND),
    })
  })

  // Import local file — returns import ID
  await page.route(`**/api/packs/${MOCK_PACK_NAME}/import-local`, (route: Route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ import_id: 'imp-001', status: 'pending' }),
    })
  })

  // Import status polling — first call: importing, second: completed
  let pollCount = 0
  await page.route('**/api/store/imports/imp-001', (route: Route) => {
    pollCount++
    const data = pollCount >= 2 ? MOCK_IMPORT_COMPLETED : MOCK_IMPORT_PENDING
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(data),
    })
  })
}

// ─── Navigation Helpers ─────────────────────────────────────────────

/** Wait for the app shell to be ready (sidebar nav visible) */
export async function waitForApp(page: Page) {
  await page.waitForSelector('nav', { state: 'visible', timeout: 15_000 })
}

/** Navigate to the mock pack detail page */
export async function navigateToPackDetail(page: Page) {
  await page.goto(`/packs/${MOCK_PACK_NAME}`)
  await waitForApp(page)
  // Wait for pack content to load
  await page.waitForSelector('text=base-checkpoint', { state: 'visible', timeout: 10_000 })
}
