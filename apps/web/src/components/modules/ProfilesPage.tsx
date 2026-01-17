import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Layers, 
  ArrowLeft, 
  AlertTriangle, 
  RefreshCw,
  CheckCircle,
  ChevronRight,
  Home,
  Package
} from 'lucide-react'
import { toast } from '../../stores/toastStore'

interface UIRuntimeStatus {
  ui: string
  active_profile: string
  stack: string[]
  stack_depth: number
}

interface ShadowedEntry {
  ui: string
  dst_relpath: string
  winner_pack: string
  loser_pack: string
}

interface ProfilesStatus {
  ui_statuses: UIRuntimeStatus[]
  shadowed: ShadowedEntry[]
  shadowed_count: number
  updates_available: number
}

export function ProfilesPage() {
  const queryClient = useQueryClient()

  // Fetch profiles status
  const { data: status, isLoading, error, refetch } = useQuery<ProfilesStatus>({
    queryKey: ['profiles-status'],
    queryFn: async () => {
      const res = await fetch('/api/profiles/status')
      if (!res.ok) throw new Error('Failed to fetch profiles status')
      return res.json()
    },
    refetchInterval: 5000,
  })

  // Back mutation
  const backMutation = useMutation({
    mutationFn: async (ui: string) => {
      const res = await fetch('/api/profiles/back', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ui_set: ui, sync: true }),
      })
      if (!res.ok) throw new Error('Failed to go back')
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
      toast.success(`Switched to: ${data?.new_profile || 'previous profile'}`)
    },
    onError: (error: Error) => {
      toast.error(`Back failed: ${error.message}`)
    },
  })

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: async (ui: string) => {
      const res = await fetch('/api/profiles/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ui_set: ui, sync: true }),
      })
      if (!res.ok) throw new Error('Failed to reset')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
      toast.success('Reset to global profile')
    },
    onError: (error: Error) => {
      toast.error(`Reset failed: ${error.message}`)
    },
  })

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-200 mb-2">Error Loading Profiles</h2>
          <p className="text-slate-400 mb-4">{(error as Error).message}</p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-8 overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
            <Layers className="w-7 h-7 text-indigo-400" />
            Profiles
          </h1>
          <p className="text-slate-400 mt-1">
            Manage active profiles and view stack state per UI
          </p>
        </div>
        
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:bg-slate-700"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Active Profiles Grid */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <Package className="w-5 h-5 text-indigo-400" />
          Active Profiles per UI
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {status?.ui_statuses.map((uiStatus) => (
            <div
              key={uiStatus.ui}
              className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5"
            >
              {/* UI Name and Active Profile */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-medium text-slate-200 capitalize">
                    {uiStatus.ui}
                  </h3>
                  <p className="text-sm text-slate-400">
                    Active: <span className="text-indigo-400 font-medium">{uiStatus.active_profile}</span>
                  </p>
                </div>
                
                {/* Actions */}
                <div className="flex gap-2">
                  {uiStatus.active_profile !== 'global' && (
                    <>
                      <button
                        onClick={() => backMutation.mutate(uiStatus.ui)}
                        disabled={backMutation.isPending}
                        className="flex items-center gap-1 px-3 py-1.5 text-sm bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 disabled:opacity-50"
                      >
                        <ArrowLeft className="w-4 h-4" />
                        Back
                      </button>
                      <button
                        onClick={() => resetMutation.mutate(uiStatus.ui)}
                        disabled={resetMutation.isPending}
                        className="flex items-center gap-1 px-3 py-1.5 text-sm bg-indigo-500/20 text-indigo-400 rounded-lg hover:bg-indigo-500/30 disabled:opacity-50"
                      >
                        <Home className="w-4 h-4" />
                        Reset
                      </button>
                    </>
                  )}
                  {uiStatus.active_profile === 'global' && (
                    <span className="flex items-center gap-1 px-3 py-1.5 text-sm text-green-400">
                      <CheckCircle className="w-4 h-4" />
                      At Global
                    </span>
                  )}
                </div>
              </div>
              
              {/* Stack Visualization */}
              <div className="bg-slate-900/50 rounded-lg p-3">
                <p className="text-xs text-slate-500 mb-2 uppercase tracking-wide">Stack ({uiStatus.stack_depth})</p>
                <div className="flex flex-wrap gap-2">
                  {uiStatus.stack.map((profile, index) => (
                    <div key={index} className="flex items-center">
                      {index > 0 && <ChevronRight className="w-4 h-4 text-slate-600 mx-1" />}
                      <span
                        className={`px-2 py-1 rounded text-sm ${
                          index === uiStatus.stack.length - 1
                            ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                            : 'bg-slate-700/50 text-slate-400'
                        }`}
                      >
                        {profile}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {(!status?.ui_statuses || status.ui_statuses.length === 0) && (
          <div className="bg-slate-800/30 border border-slate-700/30 rounded-xl p-8 text-center">
            <p className="text-slate-400">No UI configurations found. Check Store settings.</p>
          </div>
        )}
      </section>

      {/* Shadowed Files Warning */}
      {status && status.shadowed_count > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            Shadowed Files ({status.shadowed_count})
          </h2>
          
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-amber-500/10">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">UI</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">File Path</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">Winner</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-amber-400">Shadowed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-amber-500/20">
                {status.shadowed.map((entry, index) => (
                  <tr key={index} className="hover:bg-amber-500/5">
                    <td className="px-4 py-3 text-sm text-slate-300 capitalize">{entry.ui}</td>
                    <td className="px-4 py-3 text-sm text-slate-400 font-mono">{entry.dst_relpath}</td>
                    <td className="px-4 py-3 text-sm text-green-400">{entry.winner_pack}</td>
                    <td className="px-4 py-3 text-sm text-red-400">{entry.loser_pack}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <p className="text-sm text-slate-500 mt-3">
            Shadowed files occur when multiple packs expose files to the same path. 
            The "winner" pack's file is used, while the "shadowed" pack's file is hidden.
          </p>
        </section>
      )}

      {/* Updates Available Badge */}
      {status && status.updates_available > 0 && (
        <div className="mt-8 p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-indigo-400" />
            <span className="text-slate-200">
              {status.updates_available} pack{status.updates_available > 1 ? 's' : ''} with updates available
            </span>
          </div>
          <a
            href="/"
            className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
          >
            View Packs
          </a>
        </div>
      )}
    </div>
  )
}
