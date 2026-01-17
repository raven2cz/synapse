import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  ChevronDown, 
  ArrowLeft, 
  Home, 
  Layers,
  RefreshCw,
  AlertTriangle
} from 'lucide-react'
import { toast } from '../../stores/toastStore'

interface UIRuntimeStatus {
  ui: string
  active_profile: string
  stack: string[]
  stack_depth: number
}

interface ProfilesStatus {
  ui_statuses: UIRuntimeStatus[]
  shadowed_count: number
  updates_available: number
}

export function ProfileDropdown() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Fetch profiles status
  const { data: status, isLoading } = useQuery<ProfilesStatus>({
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
    mutationFn: async () => {
      const res = await fetch('/api/profiles/back', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sync: true }),
      })
      if (!res.ok) throw new Error('Failed to go back')
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
      setIsOpen(false)
      toast.success(`Switched to: ${data?.new_profile || 'previous profile'}`)
    },
    onError: (error: Error) => {
      toast.error(`Back failed: ${error.message}`)
    },
  })

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/profiles/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sync: true }),
      })
      if (!res.ok) throw new Error('Failed to reset')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
      setIsOpen(false)
      toast.success('Reset to global profile')
    },
    onError: (error: Error) => {
      toast.error(`Reset failed: ${error.message}`)
    },
  })

  // Get primary UI status (first one, or comfyui)
  const primaryStatus = status?.ui_statuses?.find(s => s.ui === 'comfyui') || status?.ui_statuses?.[0]
  const activeProfile = primaryStatus?.active_profile || 'global'
  const isAtGlobal = activeProfile === 'global'
  const stackDepth = primaryStatus?.stack_depth || 1

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded-lg">
        <RefreshCw className="w-4 h-4 animate-spin text-slate-400" />
        <span className="text-sm text-slate-400">Loading...</span>
      </div>
    )
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Dropdown Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
          isAtGlobal
            ? 'bg-slate-800/50 border-slate-700/50 text-slate-300 hover:bg-slate-800'
            : 'bg-indigo-500/20 border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/30'
        }`}
      >
        <Layers className="w-4 h-4" />
        <span className="font-medium">{activeProfile}</span>
        {stackDepth > 1 && (
          <span className="px-1.5 py-0.5 text-xs bg-indigo-500/30 rounded">
            +{stackDepth - 1}
          </span>
        )}
        {status?.shadowed_count ? (
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
        ) : null}
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-72 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-50 overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-slate-700 bg-slate-800/80">
            <p className="text-sm font-medium text-slate-200">Profile Stack</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {status?.ui_statuses?.length || 0} UI(s) configured
            </p>
          </div>

          {/* Stack Visualization */}
          <div className="px-4 py-3 border-b border-slate-700">
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Current Stack</p>
            <div className="space-y-1">
              {primaryStatus?.stack.map((profile, index) => (
                <div
                  key={index}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded ${
                    index === (primaryStatus?.stack.length || 0) - 1
                      ? 'bg-indigo-500/20 border border-indigo-500/30'
                      : 'bg-slate-700/30'
                  }`}
                >
                  <span className="text-xs text-slate-500 w-4">{index + 1}.</span>
                  <span className={`text-sm ${
                    index === (primaryStatus?.stack.length || 0) - 1
                      ? 'text-indigo-400 font-medium'
                      : 'text-slate-400'
                  }`}>
                    {profile}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Warnings */}
          {status?.shadowed_count ? (
            <div className="px-4 py-2 bg-amber-500/10 border-b border-amber-500/20">
              <div className="flex items-center gap-2 text-amber-400 text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>{status.shadowed_count} shadowed file(s)</span>
              </div>
            </div>
          ) : null}

          {/* Actions */}
          <div className="p-2 space-y-1">
            <button
              onClick={() => backMutation.mutate()}
              disabled={isAtGlobal || backMutation.isPending}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Previous</span>
              {backMutation.isPending && <RefreshCw className="w-3 h-3 animate-spin ml-auto" />}
            </button>
            
            <button
              onClick={() => resetMutation.mutate()}
              disabled={isAtGlobal || resetMutation.isPending}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Home className="w-4 h-4" />
              <span>Reset to Global</span>
              {resetMutation.isPending && <RefreshCw className="w-3 h-3 animate-spin ml-auto" />}
            </button>
          </div>

          {/* Footer Link */}
          <div className="px-4 py-2 border-t border-slate-700 bg-slate-800/50">
            <a
              href="/profiles"
              className="text-xs text-indigo-400 hover:text-indigo-300"
              onClick={() => setIsOpen(false)}
            >
              Manage all profiles →
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
