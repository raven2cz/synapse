import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Package,
  Download,
  Search,
  Settings,
  Layers,
  HardDrive,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useDownloadsStore } from '../../stores/downloadsStore'
import { Logo } from '../ui/Logo'
import { clsx } from 'clsx'

const navItems = [
  { to: '/', icon: Package, labelKey: 'nav.packs' },
  { to: '/inventory', icon: HardDrive, labelKey: 'nav.inventory' },
  { to: '/profiles', icon: Layers, labelKey: 'nav.profiles' },
  { to: '/browse', icon: Search, labelKey: 'nav.browse' },
  { to: '/downloads', icon: Download, labelKey: 'nav.downloads', badge: true },
  { to: '/settings', icon: Settings, labelKey: 'nav.settings' },
]

// Sidebar widths
const SIDEBAR_WIDTH = 256 // w-64
const SIDEBAR_COLLAPSED_WIDTH = 64 // w-16

// LocalStorage key for sidebar state
const SIDEBAR_COLLAPSED_KEY = 'synapse-sidebar-collapsed'

export function Sidebar() {
  const { t } = useTranslation()
  // Initialize from localStorage
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
    } catch {
      return false
    }
  })
  const [isHovering, setIsHovering] = useState(false)

  // Persist to localStorage when changed
  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed))
    } catch {
      // Ignore localStorage errors
    }
  }, [isCollapsed])

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
    <div
      className="relative"
      style={{
        width: isCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
        transition: 'width 200ms cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <aside
        className={clsx(
          "sticky top-14 self-start",
          "bg-slate-900/95 backdrop-blur-2xl backdrop-saturate-150",
          "border-r border-slate-700/50 rounded-br-xl",
          "flex flex-col overflow-hidden"
        )}
        style={{
          width: isCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
          transition: 'width 200ms cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        {/* Toggle button - appears on hover at the edge */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={clsx(
            "absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-20",
            "w-5 h-10 rounded-full",
            "bg-slate-800/90 backdrop-blur-sm",
            "border border-slate-600/50",
            "flex items-center justify-center",
            "text-slate-400 hover:text-white hover:bg-slate-700",
            "shadow-lg shadow-black/20",
            "transition-all duration-200",
            // Show on hover or when collapsed
            isHovering || isCollapsed ? "opacity-100" : "opacity-0 pointer-events-none"
          )}
          title={isCollapsed ? `${t('sidebar.expandSidebar')} (⌘ \\)` : `${t('sidebar.collapseSidebar')} (⌘ \\)`}
        >
          {isCollapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5" />
          )}
        </button>

        {/* Navigation */}
        <nav className={clsx(
          "flex-1 space-y-1 overflow-y-auto overflow-x-hidden",
          isCollapsed ? "p-2" : "p-4"
        )}>
          {navItems.map(({ to, icon: Icon, labelKey, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={isCollapsed ? t(labelKey) : undefined}
              className={({ isActive }) =>
                clsx(
                  "relative flex items-center rounded-xl font-medium",
                  "transition-all duration-150",
                  isCollapsed
                    ? "justify-center w-12 h-12 mx-auto"
                    : "gap-3 px-4 py-3",
                  isActive
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                )
              }
            >
              <Icon className="w-5 h-5 shrink-0" />
              {!isCollapsed && (
                <span className="flex-1 text-sm whitespace-nowrap overflow-hidden">
                  {t(labelKey)}
                </span>
              )}
              {badge && activeDownloads > 0 && (
                <span className={clsx(
                  "bg-indigo-500 text-white font-medium rounded-full",
                  isCollapsed
                    ? "absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center text-[10px]"
                    : "px-2 py-0.5 text-xs"
                )}>
                  {activeDownloads}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer status */}
        <div className={clsx(
          "border-t shrink-0",
          isCollapsed ? "p-2" : "p-4",
          isConnected
            ? 'border-slate-700/50 bg-gradient-to-br from-slate-900 to-slate-800/50'
            : 'border-red-900/30 bg-gradient-to-br from-slate-900 to-red-900/10'
        )}>
          <div className={clsx(
            "flex items-center",
            isCollapsed ? "flex-col gap-2 py-1" : "gap-3"
          )}>
            <Logo
              size={isCollapsed ? 24 : 28}
              className={clsx("drop-shadow-lg shrink-0", !isConnected && 'opacity-50')}
            />
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <div className={clsx(
                  "font-semibold text-xs truncate",
                  isConnected ? 'text-slate-300' : 'text-red-400'
                )}>
                  Synapse
                </div>
                <div className={clsx(
                  "text-[10px] truncate",
                  isConnected ? 'text-slate-500' : 'text-red-500/70'
                )}>
                  {isConnected ? t('sidebar.allSystemsReady') : t('sidebar.disconnected')}
                </div>
              </div>
            )}
            <div className={clsx(
              "w-2 h-2 rounded-full shrink-0",
              isConnected
                ? 'bg-green-500 animate-pulse-glow'
                : 'bg-red-500 shadow-lg shadow-red-500/50'
            )} />
          </div>
        </div>
      </aside>
    </div>
  )
}
