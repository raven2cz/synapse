import { useQuery } from '@tanstack/react-query'
import { Download, CheckCircle2, XCircle, Clock, Trash2, RefreshCw, HardDrive, Gauge, Timer } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { clsx } from 'clsx'

interface DownloadInfo {
  download_id: string
  pack_name: string
  asset_name: string
  filename: string
  status: string
  progress: number
  downloaded_bytes: number
  total_bytes: number
  speed_bps: number
  eta_seconds: number | null
  error: string | null
  started_at: string
  completed_at: string | null
  target_path: string | null
}

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * Format speed (bytes per second) to human readable
 */
function formatSpeed(bps: number): string {
  if (bps === 0) return '0 B/s'
  return formatBytes(bps) + '/s'
}

/**
 * Format seconds to human readable time
 */
function formatEta(seconds: number | null): string {
  if (seconds === null || seconds <= 0) return '--'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

export function DownloadsPage() {
  const { data: downloads, isLoading, refetch } = useQuery<DownloadInfo[]>({
    queryKey: ['downloads-active'],
    queryFn: async () => {
      // v2 API: /api/packs/downloads/active
      const res = await fetch('/api/packs/downloads/active')
      if (!res.ok) {
        console.error('[DownloadsPage] Failed to fetch downloads')
        return []
      }
      return res.json()
    },
    // Poll only when there are active (non-completed) downloads
    refetchInterval: (query) => {
      const data = query.state.data as DownloadInfo[] | undefined
      const hasActive = data?.some((d: DownloadInfo) => d.status === 'downloading' || d.status === 'pending')
      return hasActive ? 2000 : false
    },
  })
  
  const clearCompleted = async () => {
    await fetch('/api/packs/downloads/completed', { method: 'DELETE' })
    refetch()
  }
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />
      case 'failed':
      case 'cancelled':
        return <XCircle className="w-5 h-5 text-red-400" />
      case 'downloading':
        return <Download className="w-5 h-5 text-synapse animate-pulse" />
      default:
        return <Clock className="w-5 h-5 text-amber-400" />
    }
  }
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-400'
      case 'failed':
      case 'cancelled':
        return 'text-red-400'
      case 'downloading':
        return 'text-synapse'
      default:
        return 'text-amber-400'
    }
  }
  
  // Count active downloads
  const activeCount = downloads?.filter(d => ['pending', 'downloading'].includes(d.status)).length || 0
  
  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
            Downloads
            {activeCount > 0 && (
              <span className="px-2 py-0.5 bg-synapse/20 text-synapse text-sm rounded-full">
                {activeCount} active
              </span>
            )}
          </h1>
          <p className="text-text-secondary mt-1">
            Track your asset downloads
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => refetch()}
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
          {downloads && downloads.some(d => ['completed', 'failed', 'cancelled'].includes(d.status)) && (
            <Button
              variant="secondary"
              size="sm"
              onClick={clearCompleted}
            >
              <Trash2 className="w-4 h-4" />
              Clear Completed
            </Button>
          )}
        </div>
      </div>
      
      {/* Loading */}
      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-24 skeleton" />
          ))}
        </div>
      )}
      
      {/* Empty state */}
      {!isLoading && (!downloads || downloads.length === 0) && (
        <Card className="p-12 text-center">
          <Download className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No downloads
          </h3>
          <p className="text-text-secondary">
            Install a pack to start downloading assets
          </p>
        </Card>
      )}
      
      {/* Downloads list */}
      {downloads && downloads.length > 0 && (
        <div className="space-y-4">
          {downloads.map((download) => (
            <Card 
              key={download.download_id} 
              className={clsx(
                "space-y-4",
                download.status === 'downloading' && "border-synapse/50",
                download.status === 'completed' && "border-green-500/50",
                download.status === 'failed' && "border-red-500/50"
              )}
            >
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(download.status)}
                  <div>
                    <h3 className="font-semibold text-text-primary">
                      {download.asset_name}
                    </h3>
                    <p className="text-xs text-text-muted">
                      {download.pack_name} • {download.filename}
                    </p>
                  </div>
                </div>
                <span className={clsx(
                  'text-sm font-medium capitalize',
                  getStatusColor(download.status)
                )}>
                  {download.status}
                </span>
              </div>
              
              {/* Progress for downloading */}
              {download.status === 'downloading' && (
                <div className="space-y-3">
                  <ProgressBar 
                    progress={download.progress} 
                    showLabel={true}
                  />
                  <div className="flex items-center justify-between text-xs text-text-muted">
                    <div className="flex items-center gap-4">
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3 h-3" />
                        {formatBytes(download.downloaded_bytes)} / {formatBytes(download.total_bytes)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Gauge className="w-3 h-3" />
                        {formatSpeed(download.speed_bps)}
                      </span>
                    </div>
                    <span className="flex items-center gap-1">
                      <Timer className="w-3 h-3" />
                      ETA: {formatEta(download.eta_seconds)}
                    </span>
                  </div>
                </div>
              )}
              
              {/* Pending state */}
              {download.status === 'pending' && (
                <div className="flex items-center gap-2 text-sm text-amber-400">
                  <Clock className="w-4 h-4 animate-pulse" />
                  <span>Waiting to start...</span>
                </div>
              )}
              
              {/* Completed info */}
              {download.status === 'completed' && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-green-400 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" />
                      Download complete
                    </span>
                    <span className="text-text-muted">
                      {formatBytes(download.total_bytes)}
                    </span>
                  </div>
                  {download.target_path && (
                    <div className="text-xs text-text-muted truncate" title={download.target_path}>
                      Saved to: {download.target_path}
                    </div>
                  )}
                </div>
              )}
              
              {/* Error */}
              {download.error && (
                <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                  <p className="text-sm text-red-400">{download.error}</p>
                </div>
              )}
              
              {/* Timestamps */}
              <div className="text-xs text-text-muted pt-2 border-t border-white/5">
                Started: {new Date(download.started_at).toLocaleString()}
                {download.completed_at && (
                  <> • Completed: {new Date(download.completed_at).toLocaleString()}</>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
