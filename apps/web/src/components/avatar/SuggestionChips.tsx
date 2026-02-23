import { useTranslation } from 'react-i18next'
import { useShallow } from 'zustand/react/shallow'
import { usePageContextStore } from '../../stores/pageContextStore'
import { resolveSuggestions } from '../../lib/avatar/suggestions'

interface SuggestionChipsProps {
  onSelect: (text: string) => void
}

export function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  const { t } = useTranslation()
  const { current, previous } = usePageContextStore(
    useShallow(s => ({ current: s.current, previous: s.previous })),
  )

  const { keys, params } = resolveSuggestions(current, previous)

  return (
    <div className="flex flex-wrap gap-2 mb-3">
      {keys.map(key => (
        <button
          key={key}
          onClick={() => onSelect(t(key, params))}
          className="px-3 py-1.5 rounded-lg bg-slate-mid/30 border border-slate-mid/50 text-xs text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary hover:border-synapse/30 transition-all duration-150"
        >
          {t(key, params)}
        </button>
      ))}
    </div>
  )
}
