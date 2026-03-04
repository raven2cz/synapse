import { useState, useCallback } from 'react'
import { Loader2, AlertCircle, Search } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { toProxyUrl } from '@/lib/utils/civitaiTransformers'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ImageItem {
  id: number
  url: string
  nsfwLevel?: number
  width?: number
  height?: number
  postId?: number
  userId?: number
  stats?: { heartCount?: number; likeCount?: number; laughCount?: number; cryCount?: number }
}

interface GalleryConfig {
  endpoint: 'getImagesAsPostsInfinite' | 'getInfinite'
  sort: string
  period: string
  browsingLevel: number
  limit: number
}

// ---------------------------------------------------------------------------
// Civitai enums (from civitai/src/server/common/enums.ts + prisma/enums.ts)
// ---------------------------------------------------------------------------

// ImageSort — getImagesAsPostsInfinite sorts in-memory, all values work.
// getInfinite only respects Newest/Oldest (sort by ID), rest fall back to newest.
const IMAGE_SORT_OPTIONS = [
  'Most Reactions',
  'Most Comments',
  'Most Collected',
  'Newest',
  'Oldest',
] as const

// MetricTimeframe (prisma enum)
const PERIOD_OPTIONS = [
  { value: 'AllTime', label: 'All Time' },
  { value: 'Year', label: 'Year' },
  { value: 'Month', label: 'Month' },
  { value: 'Week', label: 'Week' },
  { value: 'Day', label: 'Day' },
] as const

// NsfwLevel flags: PG=1, PG13=2, R=4, X=8, XXX=16, Blocked=32
const BROWSING_LEVELS = [
  { value: 1, label: '1 — PG (SFW only)' },
  { value: 3, label: '3 — PG + PG13' },
  { value: 7, label: '7 — PG + PG13 + R' },
  { value: 15, label: '15 — PG..X (no XXX)' },
  { value: 31, label: '31 — All except Blocked' },
  { value: 63, label: '63 — Everything' },
] as const

const DEFAULT_CONFIG: GalleryConfig = {
  endpoint: 'getImagesAsPostsInfinite',
  sort: 'Most Reactions',
  period: 'AllTime',
  browsingLevel: 31,
  limit: 50,  // This is POSTS count for getImagesAsPostsInfinite, images will be more
}

// ---------------------------------------------------------------------------
// URL Parser — extract modelId + versionId from Civitai URL
// ---------------------------------------------------------------------------

function parseCivitaiUrl(input: string): { modelId: number | null; versionId: number | null } {
  const num = Number(input)
  if (!isNaN(num) && num > 0) return { modelId: num, versionId: null }

  const modelMatch = input.match(/\/models\/(\d+)/)
  const versionMatch = input.match(/modelVersionId=(\d+)/)
  return {
    modelId: modelMatch ? Number(modelMatch[1]) : null,
    versionId: versionMatch ? Number(versionMatch[1]) : null,
  }
}

// ---------------------------------------------------------------------------
// Image URL helpers
// ---------------------------------------------------------------------------

const CIVITAI_CDN = 'https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA'

/** Build full CDN URL from UUID (tRPC returns UUID, not full URL) */
function buildImageUrl(uuid: string, name?: string): string {
  if (!uuid) return ''
  if (uuid.startsWith('http')) return uuid
  const filename = name || 'image.jpeg'
  return `${CIVITAI_CDN}/${uuid}/anim=false,transcode=true,width=450/${filename}`
}

function thumbUrl(url: string): string {
  if (!url) return ''
  if (url.includes('image.civitai.com')) return url.replace(/width=\d+/, 'width=200')
  return url
}

// ---------------------------------------------------------------------------
// ResultsGrid
// ---------------------------------------------------------------------------

function ResultsGrid({ items }: { items: ImageItem[] }) {
  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const hovered = items.find((i) => i.id === hoveredId)

  return (
    <div>
      <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-1 max-h-[600px] overflow-y-auto">
        {items.map((item) => (
          <div
            key={item.id}
            className="relative aspect-[3/4] rounded overflow-hidden cursor-pointer border border-white/5 hover:border-white/20"
            onMouseEnter={() => setHoveredId(item.id)}
            onMouseLeave={() => setHoveredId(null)}
          >
            <img
              src={thumbUrl(item.url)}
              alt={`#${item.id}`}
              className="absolute inset-0 w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        ))}
      </div>
      {hovered && (
        <div className="mt-2 text-xs text-white/60 font-mono">
          id={hovered.id} nsfw={hovered.nsfwLevel} post={hovered.postId} user={hovered.userId}
          {hovered.stats?.heartCount ? ` hearts=${hovered.stats.heartCount}` : ''}
          {hovered.width && hovered.height ? ` ${hovered.width}x${hovered.height}` : ''}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function CommunityGalleryDebug() {
  const [modelInput, setModelInput] = useState('')
  const [versionIdInput, setVersionIdInput] = useState('')
  const [resolvedVersionId, setResolvedVersionId] = useState<number | null>(null)
  const [resolvingVersion, setResolvingVersion] = useState(false)
  const [config, setConfig] = useState<GalleryConfig>({ ...DEFAULT_CONFIG })
  const [items, setItems] = useState<ImageItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fetchInfo, setFetchInfo] = useState<string | null>(null)
  const [showRawJson, setShowRawJson] = useState(false)

  const bridge = typeof window !== 'undefined' ? window.SynapseSearchBridge : undefined

  // Resolve modelId → first versionId
  const resolveVersionId = useCallback(async (): Promise<number | null> => {
    if (versionIdInput) {
      const v = Number(versionIdInput)
      setResolvedVersionId(v)
      return v
    }

    const parsed = parseCivitaiUrl(modelInput)
    if (parsed.versionId) {
      setResolvedVersionId(parsed.versionId)
      return parsed.versionId
    }

    if (!parsed.modelId || !bridge?.getModel) return null

    setResolvingVersion(true)
    try {
      // Try tRPC model.getById first
      const result = await bridge.getModel(parsed.modelId)
      const data = result.data as Record<string, unknown> | undefined
      const versions = data?.modelVersions as Array<Record<string, unknown>> | undefined
      if (result.ok && versions?.[0]?.id) {
        const vid = versions[0].id as number
        setResolvedVersionId(vid)
        setVersionIdInput(String(vid))
        return vid
      }
      // Fallback: REST API (tRPC sometimes returns empty modelVersions)
      try {
        const restRes = await fetch(`/api/browse/model/${parsed.modelId}`)
        if (restRes.ok) {
          const restData = await restRes.json()
          const restVid = restData?.versions?.[0]?.id
          if (restVid) {
            setResolvedVersionId(restVid)
            setVersionIdInput(String(restVid))
            return restVid
          }
        }
      } catch { /* REST fallback failed, user can enter manually */ }
      return null
    } catch {
      return null
    } finally {
      setResolvingVersion(false)
    }
  }, [modelInput, versionIdInput, bridge])

  // Parse raw tRPC image item → ImageItem
  const parseImageItem = (r: Record<string, unknown>): ImageItem => {
    const rawUrl = (r.url as string) || ''
    const filename = r.name as string | undefined
    return {
      id: r.id as number,
      url: toProxyUrl(buildImageUrl(rawUrl, filename)),
      nsfwLevel: r.nsfwLevel as number | undefined,
      width: r.width as number | undefined,
      height: r.height as number | undefined,
      postId: r.postId as number | undefined,
      userId: (r.user as Record<string, unknown>)?.id as number | undefined,
      stats: r.stats as ImageItem['stats'],
    }
  }

  // Fetch images
  const handleFetch = useCallback(async () => {
    if (!bridge?.getModelImages && !bridge?.getModelImagesAsPosts) {
      setError('Bridge not available')
      return
    }

    const vid = await resolveVersionId()
    if (!vid) {
      setError('Could not resolve versionId — enter Version ID manually')
      return
    }

    setLoading(true)
    setError(null)
    setItems([])

    try {
      const bridgeOpts = {
        limit: config.limit,
        sort: config.sort,
        period: config.period,
        browsingLevel: config.browsingLevel,
        timeout: 60_000,
      }

      let parsed: ImageItem[]

      if (config.endpoint === 'getImagesAsPostsInfinite' && bridge?.getModelImagesAsPosts) {
        const result = await bridge.getModelImagesAsPosts(vid, bridgeOpts)
        if (!result.ok) {
          setError(result.error?.message || 'Fetch failed')
          setLoading(false)
          return
        }
        const posts = (result.data?.items as unknown[] || []) as Record<string, unknown>[]
        parsed = []
        for (const post of posts) {
          const images = (post.images as Record<string, unknown>[]) || []
          for (const img of images) parsed.push(parseImageItem(img))
        }
        setFetchInfo(`${posts.length} posts \u2192 ${parsed.length} images`)
      } else {
        const result = await bridge.getModelImages!(vid, bridgeOpts)
        if (!result.ok) {
          setError(result.error?.message || 'Fetch failed')
          setLoading(false)
          return
        }
        parsed = ((result.data?.items as unknown[]) || []).map((raw) =>
          parseImageItem(raw as Record<string, unknown>)
        )
        setFetchInfo(`${parsed.length} images (flat)`)
      }

      setItems(parsed)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [bridge, resolveVersionId, config])

  if (!bridge) {
    return (
      <div className="p-8 text-center text-white/60">
        <AlertCircle className="mx-auto mb-2 h-8 w-8 text-yellow-400" />
        <p>Synapse Bridge not detected. Install the Tampermonkey userscript and open Civitai in another tab.</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 p-4 space-y-4">
      <h1 className="text-lg font-semibold text-white">Community Gallery Debug</h1>

      {/* Model input */}
      <div className="flex gap-2 items-end">
        <label className="flex-1 text-xs text-white/50">
          Model URL or ID
          <input
            className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-3 py-1.5 text-white"
            placeholder="https://civitai.com/models/1949537/cherry-gig or 1949537"
            value={modelInput}
            onChange={(e) => setModelInput(e.target.value)}
          />
        </label>
        <label className="w-32 text-xs text-white/50">
          Version ID
          <input
            className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-3 py-1.5 text-white"
            placeholder="auto"
            value={versionIdInput}
            onChange={(e) => setVersionIdInput(e.target.value)}
          />
        </label>
        {resolvingVersion && <Loader2 className="h-5 w-5 animate-spin text-white/40 mb-1" />}
        {resolvedVersionId && (
          <span className="text-xs text-green-400 mb-1">v{resolvedVersionId}</span>
        )}
      </div>

      {/* Config + Fetch */}
      <div className="rounded-lg border border-white/10 bg-slate-900/50 p-3 space-y-3">
        <div className="mb-1">
          <label className="text-xs text-white/50">
            Endpoint
            <select
              className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-2 py-1 text-white"
              value={config.endpoint}
              onChange={(e) => setConfig({ ...config, endpoint: e.target.value as GalleryConfig['endpoint'] })}
            >
              <option value="getImagesAsPostsInfinite">getImagesAsPostsInfinite (Civitai web — grouped by post, real sort)</option>
              <option value="getInfinite">getInfinite (flat list, sort only Newest/Oldest)</option>
            </select>
          </label>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <label className="text-xs text-white/50">
            Sort
            <select
              className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-2 py-1 text-white"
              value={config.sort}
              onChange={(e) => setConfig({ ...config, sort: e.target.value })}
            >
              {IMAGE_SORT_OPTIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-white/50">
            Period
            <select
              className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-2 py-1 text-white"
              value={config.period}
              onChange={(e) => setConfig({ ...config, period: e.target.value })}
            >
              {PERIOD_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-white/50">
            Browsing Level
            <select
              className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-2 py-1 text-white"
              value={config.browsingLevel}
              onChange={(e) => setConfig({ ...config, browsingLevel: Number(e.target.value) })}
            >
              {BROWSING_LEVELS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-white/50">
            Limit {config.endpoint === 'getImagesAsPostsInfinite' ? '(posts)' : '(images)'}
            <input
              type="number"
              className="mt-0.5 block w-full rounded bg-slate-800 border border-white/10 text-sm px-2 py-1 text-white"
              value={config.limit}
              min={1}
              max={200}
              onChange={(e) => setConfig({ ...config, limit: Number(e.target.value) || 50 })}
            />
          </label>
        </div>
        <Button
          size="sm"
          onClick={handleFetch}
          disabled={loading || !modelInput}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Search className="h-4 w-4 mr-1" />}
          Fetch
        </Button>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-red-400"><AlertCircle className="inline h-3 w-3 mr-1" />{error}</p>
      )}

      {/* Results */}
      {items.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-white/60">{fetchInfo}</p>
          <ResultsGrid items={items} />

          <button
            className="text-xs text-white/40 hover:text-white/60 underline"
            onClick={() => setShowRawJson(!showRawJson)}
          >
            {showRawJson ? 'Hide' : 'Show'} raw JSON (first 3)
          </button>
          {showRawJson && (
            <pre className="text-[10px] text-white/50 bg-slate-900 rounded p-2 overflow-auto max-h-60 border border-white/5">
              {JSON.stringify(items.slice(0, 3), null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
