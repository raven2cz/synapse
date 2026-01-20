import { NavLink } from 'react-router-dom'
import {
  Package,
  Download,
  Search,
  Settings,
  Layers,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useDownloadsStore } from '../../stores/downloadsStore'
import { Logo } from '../ui/Logo'

const navItems = [
  { to: '/', icon: Package, label: 'Packs' },
  { to: '/profiles', icon: Layers, label: 'Profiles' },
  { to: '/browse', icon: Search, label: 'Browse Civitai' },
  { to: '/downloads', icon: Download, label: 'Downloads', badge: true },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const activeDownloads = useDownloadsStore((s) =>
    s.downloads.filter(d => d.status === 'downloading').length
  )

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
    <aside className="w-64 h-full bg-slate-900/95 backdrop-blur-2xl backdrop-saturate-150 border-r border-slate-700/50 flex flex-col">
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium ${
                isActive
                  ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
              }`
            }
          >
            <Icon className="w-5 h-5" />
            <span className="flex-1">{label}</span>
            {badge && activeDownloads > 0 && (
              <span className="px-2 py-0.5 text-xs font-medium bg-indigo-500 text-white rounded-full">
                {activeDownloads}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer status */}
      <div className={`p-4 border-t ${
        isConnected
          ? 'border-slate-700/50 bg-gradient-to-br from-slate-900 to-slate-800/50'
          : 'border-red-900/30 bg-gradient-to-br from-slate-900 to-red-900/10'
      }`}>
        <div className="flex items-center gap-3 text-xs">
          <Logo size={28} className={`drop-shadow-lg ${!isConnected ? 'opacity-50' : ''}`} />
          <div className="flex-1">
            <div className={`font-semibold ${isConnected ? 'text-slate-300' : 'text-red-400'}`}>
              Synapse
            </div>
            <div className={`text-[10px] ${isConnected ? 'text-slate-500' : 'text-red-500/70'}`}>
              {isConnected ? 'All systems ready' : 'Disconnected'}
            </div>
          </div>
          <div className={`w-2 h-2 rounded-full ${
            isConnected
              ? 'bg-green-500 animate-pulse-glow'
              : 'bg-red-500 shadow-lg shadow-red-500/50'
          }`} />
        </div>
      </div>
    </aside>
  )
}
