import type { PageContext, PageId } from '../../stores/pageContextStore'

// ─── Types ───────────────────────────────────────────────────────────

export interface AvatarPageContextPayload {
  page: PageId
  description: string
  entity?: string
  entityType?: string
  pathname: string
}

// ─── Page Descriptions ───────────────────────────────────────────────

const PAGE_DESCRIPTIONS: Record<PageId, string> = {
  'packs': 'Viewing pack list',
  'pack-detail': 'Viewing pack detail',
  'inventory': 'Viewing model inventory',
  'profiles': 'Viewing profiles',
  'downloads': 'Viewing downloads',
  'browse': 'Browsing Civitai models',
  'settings': 'Viewing settings',
  'avatar': 'In AI chat',
  'unknown': 'Unknown page',
}

// ─── Builders ────────────────────────────────────────────────────────

export function buildContextPayload(
  context: PageContext | null,
): AvatarPageContextPayload | null {
  if (!context) return null
  if (context.pageId === 'unknown' || context.pageId === 'avatar') return null

  const payload: AvatarPageContextPayload = {
    page: context.pageId,
    description: PAGE_DESCRIPTIONS[context.pageId],
    pathname: context.pathname,
  }

  if (context.pageId === 'pack-detail' && context.params.packName) {
    payload.entity = context.params.packName
    payload.entityType = 'pack'
  }

  return payload
}

export function formatContextForMessage(
  payload: AvatarPageContextPayload | null,
): string {
  if (!payload) return ''

  const parts = [payload.description]
  if (payload.entity && payload.entityType) {
    parts.push(`${payload.entityType}: ${payload.entity}`)
  }
  return `[Context: ${parts.join(', ')}]`
}
