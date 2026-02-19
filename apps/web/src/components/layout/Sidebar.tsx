import { useState, useEffect, useCallback } from 'react'
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
import { useUpdatesStore } from '../../stores/updatesStore'
import { useSettingsStore } from '../../stores/settingsStore'
import { Logo } from '../ui/Logo'
import { toast } from '../../stores/toastStore'
import { clsx } from 'clsx'

const navItems = [
  { to: '/', icon: Package, labelKey: 'nav.packs', badgeType: 'updates' as const },
  { to: '/inventory', icon: HardDrive, labelKey: 'nav.inventory' },
  { to: '/profiles', icon: Layers, labelKey: 'nav.profiles' },
  { to: '/browse', icon: Search, labelKey: 'nav.browse' },
  { to: '/downloads', icon: Download, labelKey: 'nav.downloads', badgeType: 'downloads' as const },
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
  const availableUpdates = useUpdatesStore((s) => s.updatesCount)
  const autoCheckUpdates = useSettingsStore((s) => s.autoCheckUpdates)

  // Keyboard shortcut: Ctrl/Cmd+U to check updates
  const handleCheckUpdates = useCallback(async (showDesktopNotification = false) => {
    const store = useUpdatesStore.getState()
    if (store.isChecking) return
    await store.checkAll()
    const after = useUpdatesStore.getState()
    if (after.updatesCount > 0) {
      toast.info(t('updates.autoCheck.found', { count: after.updatesCount }))
      // Desktop notification for background auto-check
      if (showDesktopNotification && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('Synapse', {
          body: t('updates.autoCheck.found', { count: after.updatesCount }),
          icon: '/favicon.ico',
        })
      }
    } else {
      toast.success(t('updates.panel.allUpToDate'))
    }
  }, [t])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
        e.preventDefault()
        handleCheckUpdates(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleCheckUpdates])

  // Auto-check updates on interval
  useEffect(() => {
    if (autoCheckUpdates === 'off') return

    const intervalMs: Record<string, number> = {
      '1h': 3_600_000,
      '6h': 21_600_000,
      '24h': 86_400_000,
    }
    const ms = intervalMs[autoCheckUpdates]
    if (!ms) return

    // Request notification permission when auto-check is enabled
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }

    // Debounce: 5s delay after mount to avoid hammering on rapid reloads
    const debounceTimer = setTimeout(() => {
      const { lastChecked, isChecking } = useUpdatesStore.getState()
      const now = Date.now()
      if (!isChecking && (!lastChecked || now - lastChecked >= ms)) {
        handleCheckUpdates(true)
      }
    }, 5000)

    // Recurring interval for long-lived sessions
    const interval = setInterval(() => {
      const { lastChecked, isChecking } = useUpdatesStore.getState()
      const now = Date.now()
      if (!isChecking && (!lastChecked || now - lastChecked >= ms)) {
        handleCheckUpdates(true)
      }
    }, ms)

    return () => {
      clearTimeout(debounceTimer)
      clearInterval(interval)
    }
  }, [autoCheckUpdates, handleCheckUpdates])

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
      {/* Invisible hover zone extending right to cover the toggle tab */}
      <div className="absolute top-0 -right-4 w-4 h-full" />
      <aside
        className={clsx(
          "sticky top-14 self-start",
          "bg-slate-900/95 backdrop-blur-2xl backdrop-saturate-150",
          "border-r border-slate-700/50 rounded-br-xl",
          "flex flex-col"
        )}
        style={{
          width: isCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
          transition: 'width 200ms cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        {/* Toggle tab - subtle handle protruding from the right edge */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={clsx(
            "absolute top-1/2 -translate-y-1/2 -right-3.5 z-20",
            "w-3.5 h-7 rounded-r-md",
            "bg-slate-800/50 hover:bg-slate-700/80",
            "border border-l-0 border-slate-600/30 hover:border-slate-500/50",
            "flex items-center justify-center",
            "text-slate-500 hover:text-slate-200",
            "transition-all duration-200",
            // Show only on hover
            isHovering ? "opacity-70 hover:opacity-100" : "opacity-0 pointer-events-none"
          )}
          title={isCollapsed ? `${t('sidebar.expandSidebar')} (⌘ \\)` : `${t('sidebar.collapseSidebar')} (⌘ \\)`}
        >
          {isCollapsed ? (
            <ChevronRight className="w-3 h-3" />
          ) : (
            <ChevronLeft className="w-3 h-3" />
          )}
        </button>

        {/* Navigation */}
        <nav className={clsx(
          "flex-1 space-y-1 overflow-y-auto overflow-x-hidden",
          isCollapsed ? "p-2" : "p-4"
        )}>
          {navItems.map(({ to, icon: Icon, labelKey, badgeType }) => {
            const badgeCount = badgeType === 'downloads' ? activeDownloads
              : badgeType === 'updates' ? availableUpdates : 0
            const badgeColor = badgeType === 'updates' ? 'bg-amber-500' : 'bg-indigo-500'

            return (
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
                {badgeType && badgeCount > 0 && (
                  <span className={clsx(
                    badgeColor, "text-white font-medium rounded-full",
                    isCollapsed
                      ? "absolute -top-1 -right-1 w-5 h-5 flex items-center justify-center text-[10px]"
                      : "px-2 py-0.5 text-xs"
                  )}>
                    {badgeCount}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Footer status */}
        <div className={clsx(
          "border-t shrink-0 overflow-hidden",
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
