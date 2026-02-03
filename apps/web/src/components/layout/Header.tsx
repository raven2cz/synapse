import { Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useSettingsStore } from '../../stores/settingsStore'
import { ProfileDropdown } from './ProfileDropdown'
import { Logo } from '../ui/Logo'
import { APP_VERSION } from '../../config'

export function Header() {
  const { nsfwBlurEnabled, toggleNsfwBlur } = useSettingsStore()

  return (
    <header className="h-14 px-6 flex items-center justify-between border-b border-slate-700/50 bg-slate-900/95 backdrop-blur-2xl backdrop-saturate-150 sticky top-0 z-50">
      {/* Logo */}
      <Link
        to="/"
        className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        onClick={() => {
          // Reset packs filters when clicking logo
          import('../../stores/packsStore').then(({ usePacksStore }) => {
            usePacksStore.getState().resetFilters()
          })
        }}
      >
        <Logo size={42} className="drop-shadow-lg flex-shrink-0" />
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-0.5">
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent leading-tight">
              Synapse
            </h1>
            <span className="text-[10px] font-mono px-1.5 py-0.5 bg-violet-500/20 text-violet-300 rounded border border-violet-500/30">
              v{APP_VERSION}
            </span>
          </div>
          <span className="text-xs font-semibold text-slate-200">The Pack-First Model Manager</span>
        </div>
      </Link>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Profile Dropdown */}
        <ProfileDropdown />

        {/* NSFW Toggle - Compact Design */}
        <button
          onClick={toggleNsfwBlur}
          className={`group flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border transition-all duration-200 ${
            nsfwBlurEnabled
              ? 'bg-indigo-500/10 border-indigo-500/30 hover:bg-indigo-500/20'
              : 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20'
          }`}
        >
          {nsfwBlurEnabled ? (
            <EyeOff className="w-4 h-4 text-indigo-400" />
          ) : (
            <Eye className="w-4 h-4 text-red-400" />
          )}
          <span className={`text-xs font-medium ${nsfwBlurEnabled ? 'text-indigo-300' : 'text-red-300'}`}>
            NSFW
          </span>
          {/* Compact toggle indicator */}
          <div className={`w-8 h-4 rounded-full relative transition-colors duration-200 ${
            nsfwBlurEnabled ? 'bg-indigo-500/30' : 'bg-red-500/30'
          }`}>
            <div className={`absolute top-0.5 w-3 h-3 rounded-full transition-all duration-200 ${
              nsfwBlurEnabled
                ? 'left-[1.125rem] bg-indigo-400 shadow-lg shadow-indigo-400/50'
                : 'left-0.5 bg-red-400 shadow-lg shadow-red-400/50'
            }`} />
          </div>
        </button>

      </div>
    </header>
  )
}
