/**
 * LocalResolveTab — Import local model files to resolve dependencies.
 *
 * Three scenarios:
 * A) Dep has known remote source → recommend matching files
 * B) Unknown file → hash → Civitai/HF lookup → enrich
 * C) No remote match → filename search → fallback
 *
 * UX states:
 * 1. Directory input (with recent paths from localStorage)
 * 2. File listing with recommendations
 * 3. Import progress (hash → copy → enrich → apply)
 * 4. Success / error result
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  FolderOpen,
  Loader2,
  Check,
  Star,
  FileBox,
  ArrowRight,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HardDrive,
  Sparkles,
  Link2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { formatSize } from '../utils'
import type {
  LocalFileInfo,
  FileRecommendation,
  LocalImportStatus,
} from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

interface LocalResolveTabProps {
  packName: string
  depId: string
  depName?: string
  kind?: string
  /** Known SHA256 (for Scenario A recommendations) */
  expectedSha256?: string
  /** Known filename (for Scenario A recommendations) */
  expectedFilename?: string
  /** Called when import completes successfully */
  onResolved: () => void
}

type TabState = 'browse' | 'importing' | 'success' | 'error'

const RECENT_PATHS_KEY = 'synapse:local-resolve:recent-paths'
const MAX_RECENT_PATHS = 5

const STAGE_LABELS: Record<string, string> = {
  hashing: 'Computing SHA256 hash...',
  copying: 'Copying to blob store...',
  enriching: 'Looking up metadata...',
  applying: 'Applying resolution...',
}

// =============================================================================
// Helpers
// =============================================================================

function getRecentPaths(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_PATHS_KEY) || '[]')
  } catch {
    return []
  }
}

function addRecentPath(path: string) {
  const paths = getRecentPaths().filter((p) => p !== path)
  paths.unshift(path)
  localStorage.setItem(
    RECENT_PATHS_KEY,
    JSON.stringify(paths.slice(0, MAX_RECENT_PATHS))
  )
}

function formatDate(mtime: number): string {
  return new Date(mtime * 1000).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function matchTypeIcon(type: string) {
  switch (type) {
    case 'sha256_exact':
      return <CheckCircle2 className="w-4 h-4 text-green-400" />
    case 'filename_exact':
      return <Check className="w-4 h-4 text-blue-400" />
    case 'filename_stem':
      return <Star className="w-4 h-4 text-amber-400" />
    default:
      return <FileBox className="w-4 h-4 text-text-muted" />
  }
}

function matchTypeBadge(type: string): { label: string; color: string } | null {
  switch (type) {
    case 'sha256_exact':
      return { label: 'Hash match', color: 'bg-green-500/15 text-green-400 border-green-500/30' }
    case 'filename_exact':
      return { label: 'Name match', color: 'bg-blue-500/15 text-blue-400 border-blue-500/30' }
    case 'filename_stem':
      return { label: 'Similar', color: 'bg-amber-500/15 text-amber-400 border-amber-500/30' }
    default:
      return null
  }
}

// =============================================================================
// Component
// =============================================================================

export function LocalResolveTab(props: LocalResolveTabProps) {
  const { packName, depId, onResolved } = props
  const [tabState, setTabState] = useState<TabState>('browse')
  const [directoryPath, setDirectoryPath] = useState('')
  const [recommendations, setRecommendations] = useState<FileRecommendation[]>([])
  const [selectedFile, setSelectedFile] = useState<LocalFileInfo | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [browseError, setBrowseError] = useState<string | null>(null)
  const [importStatus, setImportStatus] = useState<LocalImportStatus | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // --- Browse directory ---
  const handleBrowse = useCallback(async (path?: string) => {
    const dirPath = path || directoryPath.trim()
    if (!dirPath) return

    setIsLoading(true)
    setBrowseError(null)
    setRecommendations([])
    setSelectedFile(null)

    try {
      // Use recommend endpoint if we have dep context
      const url = `/api/packs/${encodeURIComponent(packName)}/recommend-local?dep_id=${encodeURIComponent(depId)}&directory=${encodeURIComponent(dirPath)}`
      const res = await fetch(url)

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Failed to browse directory')
      }

      const data = await res.json()
      const recs: FileRecommendation[] = data.recommendations || []
      setRecommendations(recs)

      if (recs.length === 0) {
        setBrowseError('No model files found in this directory.')
      }

      // Auto-select top recommendation if high confidence
      if (recs.length > 0 && recs[0].confidence >= 0.85) {
        setSelectedFile(recs[0].file)
      }

      // Save to recent paths
      addRecentPath(dirPath)
      if (!path) setDirectoryPath(dirPath)
    } catch (e) {
      setBrowseError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [directoryPath, packName, depId])

  // --- Import file ---
  const handleImport = useCallback(async () => {
    if (!selectedFile) return

    // Clear any stale polling interval (e.g., double-click)
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    setTabState('importing')
    setImportStatus(null)

    try {
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/import-local`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dep_id: depId,
            file_path: selectedFile.path,
          }),
        }
      )

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Failed to start import')
      }

      const data = await res.json()
      const importId = data.import_id

      // Start polling for progress
      setImportStatus({
        ...data,
        status: 'pending',
        stage: '',
        progress: 0,
        result: null,
      })

      pollRef.current = setInterval(async () => {  // 1s interval — large file ops take minutes
        try {
          const statusRes = await fetch(`/api/store/imports/${importId}`)
          if (statusRes.status === 404) {
            // Import lost (e.g., server restart) — stop polling
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
            setTabState('error')
            setImportStatus((prev) => prev ? {
              ...prev,
              status: 'failed',
              result: { success: false, message: 'Import session lost. Please try again.' },
            } : null)
            return
          }
          if (!statusRes.ok) return

          const status: LocalImportStatus = await statusRes.json()
          setImportStatus(status)

          if (status.status === 'completed' || status.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null

            if (status.status === 'completed' && status.result?.success) {
              setTabState('success')
              onResolved()
            } else {
              setTabState('error')
            }
          }
        } catch {
          // Silent retry
        }
      }, 1000)
    } catch (e) {
      setTabState('error')
      setImportStatus({
        import_id: '',
        pack_name: packName,
        dep_id: depId,
        filename: selectedFile.name,
        file_size: selectedFile.size,
        status: 'failed',
        stage: '',
        progress: 0,
        result: {
          success: false,
          message: e instanceof Error ? e.message : 'Unknown error',
        },
      })
    }
  }, [selectedFile, packName, depId, onResolved])

  const handleReset = useCallback(() => {
    setTabState('browse')
    setImportStatus(null)
    setSelectedFile(null)
  }, [])

  // --- Render ---

  // State: Importing
  if (tabState === 'importing' && importStatus) {
    return (
      <div className={clsx('flex flex-col items-center py-10 gap-6', ANIMATION_PRESETS.fadeIn)}>
        <div className="p-4 rounded-2xl bg-synapse/10 border border-synapse/20">
          <HardDrive className="w-10 h-10 text-synapse animate-pulse" />
        </div>

        <div className="text-center w-full max-w-sm">
          <h3 className="text-text-primary font-semibold mb-1">
            Importing {importStatus.filename}
          </h3>
          <p className="text-xs text-text-muted mb-4">
            {formatSize(importStatus.file_size)}
          </p>

          {/* Progress bar */}
          <div className="w-full bg-slate-dark rounded-full h-2.5 mb-2 overflow-hidden border border-slate-mid/30">
            <div
              className="h-full rounded-full bg-gradient-to-r from-synapse to-pulse transition-all duration-300 ease-out"
              style={{ width: `${Math.round(importStatus.progress * 100)}%` }}
            />
          </div>

          <div className="flex justify-between text-xs">
            <span className="text-text-muted">
              {STAGE_LABELS[importStatus.stage] || 'Preparing...'}
            </span>
            <span className="text-synapse font-mono">
              {Math.round(importStatus.progress * 100)}%
            </span>
          </div>

          {/* Stage indicators */}
          <div className="mt-6 space-y-2">
            {['hashing', 'copying', 'enriching', 'applying'].map((stage) => {
              const current = importStatus.stage
              const stages = ['hashing', 'copying', 'enriching', 'applying']
              const currentIdx = stages.indexOf(current)
              const stageIdx = stages.indexOf(stage)
              const isDone = stageIdx < currentIdx
              const isCurrent = stage === current
              const isPending = stageIdx > currentIdx

              return (
                <div key={stage} className="flex items-center gap-3 text-sm">
                  {isDone ? (
                    <Check className="w-4 h-4 text-green-400 flex-shrink-0" />
                  ) : isCurrent ? (
                    <Loader2 className="w-4 h-4 text-synapse animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-slate-mid flex-shrink-0" />
                  )}
                  <span
                    className={clsx(
                      isDone && 'text-text-muted line-through',
                      isCurrent && 'text-text-primary font-medium',
                      isPending && 'text-text-muted/50'
                    )}
                  >
                    {STAGE_LABELS[stage]}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  // State: Success
  if (tabState === 'success' && importStatus?.result) {
    const result = importStatus.result
    return (
      <div className={clsx('flex flex-col items-center py-10 gap-5', ANIMATION_PRESETS.fadeIn)}>
        <div className="p-4 rounded-2xl bg-green-500/10 border border-green-500/20">
          <CheckCircle2 className="w-10 h-10 text-green-400" />
        </div>

        <div className="text-center max-w-sm">
          <h3 className="text-text-primary font-semibold mb-1">
            Successfully imported!
          </h3>
          <p className="text-sm text-text-muted">
            {result.display_name || importStatus.filename}
          </p>
        </div>

        {/* Details card */}
        <div className="w-full max-w-sm bg-slate-dark/80 rounded-xl border border-slate-mid/50 p-4 space-y-3">
          {result.sha256 && (
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">SHA256</span>
              <span className="text-text-primary font-mono">{result.sha256.slice(0, 16)}...</span>
            </div>
          )}
          {result.file_size && (
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Size</span>
              <span className="text-text-primary">{formatSize(result.file_size)}</span>
            </div>
          )}

          {/* Enrichment info */}
          {result.enrichment_source && result.enrichment_source !== 'filename_only' && (
            <div className="pt-2 border-t border-slate-mid/30">
              <div className="flex items-center gap-2 mb-2">
                <Link2 className="w-3.5 h-3.5 text-synapse" />
                <span className="text-xs font-medium text-synapse">Enrichment</span>
              </div>
              <p className="text-xs text-text-muted">
                {result.enrichment_source === 'civitai_hash' && (
                  <>Found on Civitai via hash match. Canonical source saved for updates.</>
                )}
                {result.enrichment_source === 'civitai_name' && (
                  <>Found on Civitai via name search. Canonical source saved for updates.</>
                )}
                {result.enrichment_source === 'huggingface' && (
                  <>Found on HuggingFace. Canonical source saved for updates.</>
                )}
              </p>
            </div>
          )}

          {result.enrichment_source === 'filename_only' && (
            <div className="pt-2 border-t border-slate-mid/30">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-xs text-amber-400">
                  No remote source found — updates won't be tracked
                </span>
              </div>
            </div>
          )}
        </div>

        <Button variant="secondary" onClick={handleReset} size="sm">
          Import another file
        </Button>
      </div>
    )
  }

  // State: Error
  if (tabState === 'error') {
    const errorMsg = importStatus?.result?.message || 'Import failed'
    return (
      <div className={clsx('flex flex-col items-center py-10 gap-5', ANIMATION_PRESETS.fadeIn)}>
        <div className="p-4 rounded-2xl bg-error/10 border border-error/20">
          <XCircle className="w-10 h-10 text-error" />
        </div>

        <div className="text-center max-w-sm">
          <h3 className="text-text-primary font-semibold mb-1">Import failed</h3>
          <p className="text-sm text-error/80">{errorMsg}</p>
        </div>

        <Button variant="secondary" onClick={handleReset} size="sm">
          Try again
        </Button>
      </div>
    )
  }

  // State: Browse (default)
  const recentPaths = getRecentPaths()
  const hasRecommendations = recommendations.length > 0
  const topMatch = hasRecommendations ? recommendations[0] : null
  const hasTopMatch = topMatch && topMatch.confidence >= 0.6

  return (
    <div className={clsx('space-y-4', ANIMATION_PRESETS.fadeIn)}>
      {/* Directory input */}
      <div>
        <label className="block text-xs font-medium text-text-muted mb-2">
          Model directory
        </label>
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={directoryPath}
            onChange={(e) => setDirectoryPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleBrowse()
            }}
            placeholder="/home/user/models/checkpoints"
            className={clsx(
              'flex-1 px-4 py-2.5 rounded-xl text-sm',
              'bg-slate-dark border border-slate-mid/50',
              'text-text-primary placeholder:text-text-muted/40',
              'focus:outline-none focus:border-synapse/50 focus:ring-1 focus:ring-synapse/30',
              'transition-all duration-200'
            )}
          />
          <Button
            onClick={() => handleBrowse()}
            disabled={!directoryPath.trim() || isLoading}
            isLoading={isLoading}
            variant="secondary"
          >
            <FolderOpen className="w-4 h-4" />
            Browse
          </Button>
        </div>
      </div>

      {/* Recent paths */}
      {!hasRecommendations && recentPaths.length > 0 && (
        <div>
          <p className="text-xs text-text-muted mb-2 flex items-center gap-1.5">
            <Clock className="w-3 h-3" />
            Recent
          </p>
          <div className="flex flex-wrap gap-1.5">
            {recentPaths.map((path) => (
              <button
                key={path}
                onClick={() => {
                  setDirectoryPath(path)
                  handleBrowse(path)
                }}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs',
                  'bg-slate-dark/60 border border-slate-mid/30',
                  'text-text-muted hover:text-text-primary hover:border-synapse/30',
                  'transition-all duration-150 truncate max-w-[280px]'
                )}
                title={path}
              >
                {path}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {browseError && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-error/5 border border-error/20">
          <AlertTriangle className="w-4 h-4 text-error flex-shrink-0 mt-0.5" />
          <p className="text-sm text-error/80">{browseError}</p>
        </div>
      )}

      {/* Recommended badge */}
      {hasTopMatch && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-green-500/5 border border-green-500/20">
          <Sparkles className="w-4 h-4 text-green-400" />
          <p className="text-xs text-green-400">
            <span className="font-medium">Recommended match found!</span>
            {' '}
            {topMatch!.reason}
          </p>
        </div>
      )}

      {/* File list */}
      {hasRecommendations && (
        <div className="space-y-1.5 max-h-[320px] overflow-y-auto pr-1">
          {recommendations.map((rec) => {
            const isSelected = selectedFile?.path === rec.file.path
            const badge = matchTypeBadge(rec.match_type)

            return (
              <button
                key={rec.file.path}
                onClick={() => setSelectedFile(rec.file)}
                className={clsx(
                  'w-full text-left p-3 rounded-xl',
                  'transition-all duration-200',
                  'flex items-center gap-3',
                  isSelected
                    ? 'bg-synapse/15 border-2 border-synapse shadow-sm shadow-synapse/10'
                    : rec.confidence >= 0.6
                      ? 'bg-slate-dark/80 border border-green-500/20 hover:border-synapse/30'
                      : 'bg-slate-dark/50 border border-slate-mid/30 hover:border-slate-mid/50'
                )}
              >
                {/* Match icon */}
                <div className="flex-shrink-0">
                  {matchTypeIcon(rec.match_type)}
                </div>

                {/* File info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p
                      className={clsx(
                        'font-medium truncate text-sm',
                        isSelected ? 'text-synapse' : 'text-text-primary'
                      )}
                    >
                      {rec.file.name}
                    </p>
                    {badge && (
                      <span
                        className={clsx(
                          'px-1.5 py-0.5 rounded text-[10px] font-semibold border whitespace-nowrap',
                          badge.color
                        )}
                      >
                        {badge.label}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-text-muted">
                      {formatSize(rec.file.size)}
                    </span>
                    <span className="text-xs text-text-muted/50">
                      {formatDate(rec.file.mtime)}
                    </span>
                    {rec.reason && rec.match_type !== 'none' && (
                      <span className="text-xs text-text-muted/60 truncate">
                        {rec.reason}
                      </span>
                    )}
                  </div>
                </div>

                {/* Selection indicator */}
                {isSelected && (
                  <Check className="w-5 h-5 text-synapse flex-shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Import button */}
      {hasRecommendations && (
        <div className="flex justify-end pt-2">
          <Button
            onClick={handleImport}
            disabled={!selectedFile}
            className="min-w-[160px]"
          >
            <HardDrive className="w-4 h-4" />
            Use This File
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Empty state hint */}
      {!hasRecommendations && !isLoading && !browseError && (
        <div className="flex flex-col items-center py-8 gap-3">
          <div className="p-3 rounded-2xl bg-slate-dark/60 border border-slate-mid/30">
            <FolderOpen className="w-8 h-8 text-text-muted/40" />
          </div>
          <p className="text-sm text-text-muted text-center max-w-xs">
            Enter a directory path where your model files are stored
          </p>
          <p className="text-xs text-text-muted/60 text-center">
            Supports .safetensors, .ckpt, .pt, .bin, .onnx
          </p>
        </div>
      )}
    </div>
  )
}
