import type { PageId, PageContext } from '../../stores/pageContextStore'

// ─── Per-page suggestion i18n keys ───────────────────────────────────

export const PAGE_SUGGESTIONS: Partial<Record<PageId, string[]>> = {
  'packs': [
    'avatar.suggestions.packsPage.overview',
    'avatar.suggestions.packsPage.unresolved',
    'avatar.suggestions.packsPage.recommend',
  ],
  'pack-detail': [
    'avatar.suggestions.packDetail.explain',
    'avatar.suggestions.packDetail.dependencies',
    'avatar.suggestions.packDetail.workflow',
  ],
  'inventory': [
    'avatar.suggestions.inventoryPage.diskUsage',
    'avatar.suggestions.inventoryPage.orphans',
    'avatar.suggestions.inventoryPage.cleanup',
  ],
  'browse': [
    'avatar.suggestions.browsePage.recommend',
    'avatar.suggestions.browsePage.compare',
    'avatar.suggestions.browsePage.trending',
  ],
  'downloads': [
    'avatar.suggestions.downloadsPage.status',
    'avatar.suggestions.downloadsPage.queue',
  ],
  'profiles': [
    'avatar.suggestions.profilesPage.explain',
    'avatar.suggestions.profilesPage.conflicts',
  ],
  'settings': [
    'avatar.suggestions.settingsPage.optimize',
    'avatar.suggestions.settingsPage.providers',
  ],
}

export const FALLBACK_SUGGESTIONS = [
  'avatar.suggestions.inventory',
  'avatar.suggestions.parameters',
  'avatar.suggestions.dependencies',
]

// ─── Resolution Logic ────────────────────────────────────────────────

export interface SuggestionResult {
  keys: string[]
  params: Record<string, string>
}

/**
 * Resolve suggestion keys and interpolation params from page context.
 * When on /avatar, uses the previous (non-avatar) context.
 */
export function resolveSuggestions(
  current: PageContext | null,
  previous: PageContext | null,
): SuggestionResult {
  const context = current?.pageId === 'avatar' ? previous : current
  const pageId = context?.pageId
  const keys = (pageId && PAGE_SUGGESTIONS[pageId]) || FALLBACK_SUGGESTIONS

  const params: Record<string, string> = {}
  if (context?.params.packName) {
    params.packName = context.params.packName
  }

  return { keys, params }
}
