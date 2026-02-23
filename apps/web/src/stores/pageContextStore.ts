import { create } from 'zustand'

// ─── Types ───────────────────────────────────────────────────────────

export type PageId =
  | 'packs'
  | 'pack-detail'
  | 'inventory'
  | 'profiles'
  | 'downloads'
  | 'browse'
  | 'avatar'
  | 'settings'
  | 'unknown'

/** Pages that carry meaningful context for the avatar assistant */
const CONTEXT_BEARING_PAGES: ReadonlySet<PageId> = new Set([
  'packs', 'pack-detail', 'inventory', 'profiles',
  'downloads', 'browse', 'settings',
])

export interface PageContext {
  pageId: PageId
  pathname: string
  params: Record<string, string>
  updatedAt: number
}

interface PageContextState {
  current: PageContext | null
  previous: PageContext | null
  setContext: (pathname: string) => void
}

// ─── Route Resolution ────────────────────────────────────────────────

export function resolveContext(pathname: string): PageContext {
  // Normalize: strip trailing slash (keep "/" as-is)
  const p = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname

  const ctx: PageContext = {
    pageId: 'unknown',
    pathname,
    params: {},
    updatedAt: Date.now(),
  }

  if (p === '/' || p === '/packs') {
    ctx.pageId = 'packs'
  } else if (p.startsWith('/packs/')) {
    const raw = p.slice('/packs/'.length)
    if (raw) {
      ctx.pageId = 'pack-detail'
      try {
        ctx.params.packName = decodeURIComponent(raw)
      } catch {
        // Malformed URI encoding — use raw segment
        ctx.params.packName = raw
      }
    } else {
      ctx.pageId = 'packs'
    }
  } else if (p === '/inventory') {
    ctx.pageId = 'inventory'
  } else if (p === '/profiles') {
    ctx.pageId = 'profiles'
  } else if (p === '/downloads') {
    ctx.pageId = 'downloads'
  } else if (p === '/browse') {
    ctx.pageId = 'browse'
  } else if (p === '/avatar') {
    ctx.pageId = 'avatar'
  } else if (p === '/settings') {
    ctx.pageId = 'settings'
  }

  return ctx
}

// ─── Store ───────────────────────────────────────────────────────────

export const usePageContextStore = create<PageContextState>((set, get) => ({
  current: null,
  previous: null,

  setContext: (pathname: string) => {
    const { current } = get()

    // Deduplicate: skip if pathname unchanged
    if (current?.pathname === pathname) return

    const next = resolveContext(pathname)

    // Only persist previous for context-bearing pages (not avatar, not unknown)
    const newPrevious = current && CONTEXT_BEARING_PAGES.has(current.pageId)
      ? current
      : get().previous

    set({ current: next, previous: newPrevious })
  },
}))
