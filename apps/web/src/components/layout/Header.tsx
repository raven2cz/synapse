import { useQuery } from '@tanstack/react-query'
import { Zap, Wifi, WifiOff, Eye, EyeOff } from 'lucide-react'
import { useSettingsStore } from '../../stores/settingsStore'
import { ProfileDropdown } from './ProfileDropdown'

export function Header() {
  const { nsfwBlurEnabled, toggleNsfwBlur } = useSettingsStore()
  
  const { data: status, isError } = useQuery({
    queryKey: ['system-status'],
    queryFn: async () => {
      const res = await fetch('/api/system/status')
      if (!res.ok) throw new Error('Failed to fetch status')
      return res.json()
    },
    refetchInterval: 5000,
  })
  
  const isConnected = status && !isError
  
  return (
    <header className="h-14 px-6 flex items-center justify-between border-b border-slate-700/50 bg-slate-900/95 backdrop-blur-2xl backdrop-saturate-150 sticky top-0 z-50">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
          <Zap className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Synapse</h1>
          <span className="text-xs text-slate-500">v{status?.version || '1.0.0'}</span>
        </div>
      </div>
      
      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Profile Dropdown */}
        <ProfileDropdown />
        
        {/* NSFW Toggle */}
        <button
          onClick={toggleNsfwBlur}
          className="flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800"
        >
          {nsfwBlurEnabled ? (
            <EyeOff className="w-4 h-4 text-indigo-400" />
          ) : (
            <Eye className="w-4 h-4 text-red-400" />
          )}
          <span className={nsfwBlurEnabled ? 'text-indigo-400' : 'text-red-400'}>
            {nsfwBlurEnabled ? 'NSFW Blur ON' : 'NSFW Blur OFF'}
          </span>
          {/* Toggle switch */}
          <div className={`w-10 h-5 rounded-full relative ${nsfwBlurEnabled ? 'bg-indigo-500/30' : 'bg-red-500/30'}`}>
            <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all duration-200 ${
              nsfwBlurEnabled 
                ? 'left-5 bg-indigo-400' 
                : 'left-0.5 bg-red-400'
            }`} />
          </div>
        </button>
        
        {/* Packs count */}
        {status?.packs_count !== undefined && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span className="text-indigo-400 font-medium">{status.packs_count}</span>
            <span>packs</span>
          </div>
        )}
        
        {/* Connection status */}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4 text-green-400" />
              <span className="text-sm text-slate-500">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-400">Disconnected</span>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
