import { NavLink } from 'react-router-dom'
import { 
  Package, 
  Download, 
  Search, 
  Settings,
  Activity,
  Layers,
} from 'lucide-react'
import { useDownloadsStore } from '../../stores/downloadsStore'

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
      <div className="p-4 border-t border-slate-700/50">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Activity className="w-4 h-4" />
          <span>Synapse ready</span>
        </div>
      </div>
    </aside>
  )
}
