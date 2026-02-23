/**
 * AvatarFab — Floating Action Button for AI assistant.
 *
 * Shows a small FAB in the bottom-right corner that opens the avatar chat.
 * Renders different states based on avatar availability:
 *
 * - STATE 1 (ready): Pulsing purple FAB → click opens chat
 * - STATE 2 (setup_required/no_provider/no_engine): FAB with setup badge → click navigates to settings
 * - STATE 3 (disabled): Not rendered at all
 * - Loading: Not rendered (avoid flash)
 */

import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Bot, Sparkles } from 'lucide-react'
import { clsx } from 'clsx'
import { useAvatar } from './AvatarProvider'

export function AvatarFab() {
  const { available, state, isLoading } = useAvatar()
  const navigate = useNavigate()
  const { t } = useTranslation()

  // Don't render when disabled or loading
  if (state === 'disabled' || isLoading || state === 'error') return null

  const handleClick = () => {
    if (available) {
      // STATE 1: Open avatar chat page
      navigate('/avatar')
    } else {
      // STATE 2: Navigate to settings for setup
      navigate('/settings')
    }
  }

  const needsSetup = !available

  return (
    <button
      onClick={handleClick}
      title={
        available
          ? t('avatar.fab.openChat')
          : t('avatar.fab.setupRequired')
      }
      className={clsx(
        'fixed bottom-6 right-6 z-40',
        'w-14 h-14 rounded-full',
        'flex items-center justify-center',
        'shadow-lg shadow-black/30',
        'transition-all duration-200',
        'hover:scale-110 active:scale-95',
        available
          ? 'bg-gradient-to-br from-indigo-500 to-violet-600 hover:from-indigo-400 hover:to-violet-500'
          : 'bg-slate-700 hover:bg-slate-600',
      )}
    >
      {available ? (
        <Sparkles className="w-6 h-6 text-white" />
      ) : (
        <Bot className="w-6 h-6 text-slate-300" />
      )}

      {/* Setup badge */}
      {needsSetup && (
        <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 border-2 border-obsidian" />
      )}
    </button>
  )
}
