/**
 * DependencyResolverModal
 *
 * Generic modal for resolving ANY dependency type (checkpoint, LoRA, VAE, etc.).
 * Replaces BaseModelResolverModal for all non-base-model dependencies.
 *
 * Tabs:
 * 1. Candidates — auto-suggested results from evidence providers
 * 2. Preview Analysis — metadata from preview images (if available)
 * 3. AI Resolve — AI-powered search (if avatar available)
 * 4. Civitai — manual Civitai search
 * 5. HuggingFace — manual HF search (only for eligible kinds)
 *
 * Design follows BaseModelResolverModal aesthetic:
 * - Dark theme with synapse accent
 * - Rounded cards with selection state
 * - Loading spinners, empty states
 */

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  X,
  Loader2,
  Check,
  Search,
  Sparkles,
  Image,
  Globe,
  Database,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Shield,
  ShieldCheck,
  ShieldQuestion,
  ShieldAlert,
  Download,
  Info,
  HardDrive,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import type {
  AssetType,
  ResolutionCandidate,
  SuggestResult,
  SuggestOptions,
  EvidenceGroupInfo,
  ConfidenceLevel,
} from '../types'
import { HF_ELIGIBLE_KINDS } from '../types'
import { ANIMATION_PRESETS } from '../constants'
import { PreviewAnalysisTab } from './PreviewAnalysisTab'
import { LocalResolveTab } from './LocalResolveTab'

// =============================================================================
// Types
// =============================================================================

type ResolverTab = 'candidates' | 'preview' | 'local' | 'ai-resolve' | 'civitai' | 'huggingface'

export interface DependencyResolverModalProps {
  isOpen: boolean
  onClose: () => void
  packName: string
  depId: string
  depName: string
  kind: AssetType
  baseModelHint?: string

  // Candidates from suggest
  candidates: ResolutionCandidate[]
  isSuggesting: boolean
  requestId?: string

  // Actions
  onSuggest: (options?: SuggestOptions) => Promise<SuggestResult>
  onApply: (candidateId: string) => void
  onApplyAndDownload: (candidateId: string) => void
  isApplying: boolean

  // Avatar
  avatarAvailable: boolean
}

// =============================================================================
// Helpers
// =============================================================================

function getConfidenceLevel(candidate: ResolutionCandidate): ConfidenceLevel {
  if (candidate.tier === 1) return 'exact'
  if (candidate.tier === 2) return 'high'
  if (candidate.tier === 3) return 'possible'
  return 'hint'
}

const CONFIDENCE_DISPLAY: Record<
  ConfidenceLevel,
  { icon: typeof ShieldCheck; label: string; color: string; bg: string }
> = {
  exact: {
    icon: ShieldCheck,
    label: 'Exact match',
    color: 'text-green-400',
    bg: 'bg-green-500/15',
  },
  high: {
    icon: Shield,
    label: 'High confidence',
    color: 'text-blue-400',
    bg: 'bg-blue-500/15',
  },
  possible: {
    icon: ShieldQuestion,
    label: 'Possible match',
    color: 'text-amber-400',
    bg: 'bg-amber-500/15',
  },
  hint: {
    icon: ShieldAlert,
    label: 'Hint — verify',
    color: 'text-text-muted',
    bg: 'bg-slate-mid/30',
  },
}

function getDefaultTab(
  candidates: ResolutionCandidate[],
  avatarAvailable: boolean,
): ResolverTab {
  if (candidates.some((c) => c.tier <= 2)) return 'candidates'
  if (candidates.length === 0) return 'candidates'
  if (avatarAvailable) return 'ai-resolve'
  return 'candidates'
}

// =============================================================================
// Sub-components
// =============================================================================

interface TabDef {
  id: ResolverTab
  label: string
  icon: React.ReactNode
  visible: boolean
}

function TabButton({
  tab,
  currentTab,
  onClick,
  icon,
  label,
  badge,
}: {
  tab: ResolverTab
  currentTab: ResolverTab
  onClick: () => void
  icon: React.ReactNode
  label: string
  badge?: number
}) {
  const isActive = tab === currentTab

  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex items-center justify-center gap-2 py-3 px-3',
        'transition-all duration-200 font-medium text-sm whitespace-nowrap',
        isActive
          ? 'text-synapse border-b-2 border-synapse bg-synapse/10'
          : 'text-text-muted hover:text-text-primary hover:bg-slate-mid/30'
      )}
    >
      {icon}
      {label}
      {badge !== undefined && badge > 0 && (
        <span
          className={clsx(
            'ml-1 px-1.5 py-0.5 rounded-full text-xs font-bold',
            isActive ? 'bg-synapse/20 text-synapse' : 'bg-slate-mid text-text-muted'
          )}
        >
          {badge}
        </span>
      )}
    </button>
  )
}

function CandidateCard({
  candidate,
  isSelected,
  onSelect,
  isExpanded,
  onToggleExpand,
}: {
  candidate: ResolutionCandidate
  isSelected: boolean
  onSelect: () => void
  isExpanded: boolean
  onToggleExpand: () => void
}) {
  const level = getConfidenceLevel(candidate)
  const display = CONFIDENCE_DISPLAY[level]
  const IconComponent = display.icon

  return (
    <div
      className={clsx(
        'rounded-xl overflow-hidden transition-all duration-200',
        isSelected
          ? 'bg-synapse/20 border-2 border-synapse'
          : 'bg-slate-dark border border-slate-mid hover:border-slate-mid/80'
      )}
    >
      <div role="button" tabIndex={0} onClick={onSelect} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect() }} className="w-full text-left p-4 cursor-pointer">
        <div className="flex items-start gap-3">
          {/* Confidence indicator */}
          <div className={clsx('p-2 rounded-lg flex-shrink-0', display.bg)}>
            <IconComponent className={clsx('w-5 h-5', display.color)} />
          </div>

          {/* Content */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="text-text-primary font-medium truncate">
                {candidate.display_name}
              </p>
              {isSelected && <Check className="w-4 h-4 text-synapse flex-shrink-0" />}
            </div>

            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className={clsx('px-2 py-0.5 rounded text-xs font-medium', display.bg, display.color)}>
                {display.label}
              </span>
              {candidate.provider && (
                <span className="px-2 py-0.5 bg-slate-mid/50 text-text-muted text-xs rounded">
                  {candidate.provider}
                </span>
              )}
              {candidate.base_model && (
                <span className="px-2 py-0.5 bg-pulse/20 text-pulse text-xs rounded">
                  {candidate.base_model}
                </span>
              )}
            </div>

            {/* Compatibility warnings */}
            {candidate.compatibility_warnings.length > 0 && (
              <div className="mt-2 flex items-start gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-400">
                  {candidate.compatibility_warnings[0]}
                </p>
              </div>
            )}
          </div>

          {/* Expand toggle */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleExpand()
            }}
            className="p-1 hover:bg-slate-mid/30 rounded transition-colors flex-shrink-0"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-text-muted" />
            ) : (
              <ChevronRight className="w-4 h-4 text-text-muted" />
            )}
          </button>
        </div>
      </div>

      {/* Evidence details */}
      {isExpanded && candidate.evidence_groups.length > 0 && (
        <div className="border-t border-slate-mid px-4 py-3 space-y-2">
          <p className="text-xs text-text-muted font-medium uppercase tracking-wider">
            Evidence
          </p>
          {candidate.evidence_groups.map((group, gi) => (
            <EvidenceGroupCard key={gi} group={group} />
          ))}
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-mid/50">
            <Info className="w-3.5 h-3.5 text-text-muted" />
            <p className="text-xs text-text-muted">
              Score: {(candidate.confidence * 100).toFixed(0)}% (Tier {candidate.tier})
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function EvidenceGroupCard({ group }: { group: EvidenceGroupInfo }) {
  return (
    <div className="pl-3 border-l-2 border-slate-mid/50">
      <p className="text-xs text-text-muted font-mono">{group.provenance}</p>
      {group.items.map((item, i) => (
        <div key={i} className="mt-1">
          <p className="text-xs text-text-primary">{item.description}</p>
          <p className="text-xs text-text-muted">
            {item.source} &mdash; {(item.confidence * 100).toFixed(0)}%
          </p>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function DependencyResolverModal({
  isOpen,
  onClose,
  packName,
  depId,
  depName,
  kind,
  baseModelHint,
  candidates,
  isSuggesting,
  requestId: _requestId,
  onSuggest,
  onApply,
  onApplyAndDownload,
  isApplying,
  avatarAvailable,
}: DependencyResolverModalProps) {
  const { t } = useTranslation()

  // Tab state
  const [tab, setTab] = useState<ResolverTab>('candidates')
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
  const [expandedCandidateId, setExpandedCandidateId] = useState<string | null>(null)
  const [isAiSearching, setIsAiSearching] = useState(false)

  // Build tabs list
  const tabs: TabDef[] = [
    { id: 'candidates', label: 'Candidates', icon: <Search className="w-4 h-4" />, visible: true },
    { id: 'preview', label: 'Preview', icon: <Image className="w-4 h-4" />, visible: true },
    { id: 'local', label: 'Local File', icon: <HardDrive className="w-4 h-4" />, visible: true },
    { id: 'ai-resolve', label: 'AI Resolve', icon: <Sparkles className="w-4 h-4" />, visible: avatarAvailable },
    { id: 'civitai', label: 'Civitai', icon: <Globe className="w-4 h-4" />, visible: true },
    { id: 'huggingface', label: 'HuggingFace', icon: <Database className="w-4 h-4" />, visible: HF_ELIGIBLE_KINDS.has(kind) },
  ]
  const visibleTabs = tabs.filter((t) => t.visible)

  // Reset when modal opens
  useEffect(() => {
    if (isOpen) {
      setTab(getDefaultTab(candidates, avatarAvailable))
      setSelectedCandidateId(null)
      setExpandedCandidateId(null)
      setIsAiSearching(false)
    }
  }, [isOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-select top candidate if TIER-1/2
  useEffect(() => {
    if (candidates.length > 0 && candidates[0].tier <= 2) {
      setSelectedCandidateId(candidates[0].candidate_id)
    }
  }, [candidates])

  const handleAiResolve = useCallback(async () => {
    setIsAiSearching(true)
    try {
      const result = await onSuggest({ include_ai: true })
      if (result.candidates.length > 0) {
        setTab('candidates')
      }
    } catch {
      // Error toast handled by mutation onError
    } finally {
      setIsAiSearching(false)
    }
  }, [onSuggest])

  const selectedCandidate = candidates.find((c) => c.candidate_id === selectedCandidateId)

  if (!isOpen) return null

  return (
    <div
      className={clsx(
        'fixed inset-0 bg-black/80 backdrop-blur-sm z-50',
        'flex items-center justify-center p-4',
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          'bg-slate-deep border border-slate-mid rounded-2xl',
          'max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col',
          'shadow-2xl',
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="border-b border-slate-mid p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-synapse/15">
                <Search className="w-5 h-5 text-synapse" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-primary">
                  {t('pack.resolve.title', 'Resolve Dependency')}
                </h2>
                <p className="text-sm text-text-muted">
                  {depName}
                  {baseModelHint && (
                    <span className="ml-2 text-synapse font-mono text-xs">
                      {baseModelHint}
                    </span>
                  )}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-dark/50 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-text-muted" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-mid overflow-x-auto">
          {visibleTabs.map((tabDef) => (
            <TabButton
              key={tabDef.id}
              tab={tabDef.id}
              currentTab={tab}
              onClick={() => setTab(tabDef.id)}
              icon={tabDef.icon}
              label={tabDef.label}
              badge={tabDef.id === 'candidates' ? candidates.length : undefined}
            />
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Candidates Tab */}
          {tab === 'candidates' && (
            <div className="space-y-2">
              {isSuggesting ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-synapse" />
                  <p className="text-sm text-text-muted">
                    {t('pack.resolve.searching', 'Searching for matches...')}
                  </p>
                </div>
              ) : candidates.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <Search className="w-10 h-10 text-text-muted/50" />
                  <p className="text-text-muted text-center">
                    {t('pack.resolve.noCandidates', 'No candidates found.')}
                  </p>
                  {avatarAvailable && (
                    <Button onClick={handleAiResolve} disabled={isAiSearching}>
                      {isAiSearching ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Sparkles className="w-4 h-4" />
                      )}
                      {t('pack.resolve.tryAi', 'Try AI Search')}
                    </Button>
                  )}
                </div>
              ) : (
                candidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.candidate_id}
                    candidate={candidate}
                    isSelected={selectedCandidateId === candidate.candidate_id}
                    onSelect={() => setSelectedCandidateId(candidate.candidate_id)}
                    isExpanded={expandedCandidateId === candidate.candidate_id}
                    onToggleExpand={() =>
                      setExpandedCandidateId(
                        expandedCandidateId === candidate.candidate_id
                          ? null
                          : candidate.candidate_id
                      )
                    }
                  />
                ))
              )}
            </div>
          )}

          {/* Preview Analysis Tab */}
          {tab === 'preview' && (
            <PreviewAnalysisTab
              packName={packName}
              depKind={kind}
              candidates={candidates}
              onSelectCandidate={(candidateId) => {
                setSelectedCandidateId(candidateId)
                setTab('candidates')
              }}
            />
          )}

          {/* Local File Tab */}
          {tab === 'local' && (
            <LocalResolveTab
              packName={packName}
              depId={depId}
              depName={depName}
              kind={kind}
              onResolved={onClose}
            />
          )}

          {/* AI Resolve Tab */}
          {tab === 'ai-resolve' && (
            <div className="flex flex-col items-center justify-center py-12 gap-4">
              <div className="p-4 rounded-2xl bg-gradient-to-br from-synapse/20 to-pulse/10 border border-synapse/30">
                <Sparkles className="w-10 h-10 text-synapse" />
              </div>
              <div className="text-center max-w-md">
                <h3 className="text-text-primary font-semibold mb-2">
                  {t('pack.resolve.aiTitle', 'AI-Powered Search')}
                </h3>
                <p className="text-sm text-text-muted">
                  {t(
                    'pack.resolve.aiDescription',
                    'AI will search Civitai and HuggingFace to find the best matching model for this dependency.'
                  )}
                </p>
              </div>
              <Button
                onClick={handleAiResolve}
                disabled={isAiSearching || isSuggesting}
                className="px-8"
              >
                {isAiSearching ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('pack.resolve.aiSearching', 'Searching...')}
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    {t('pack.resolve.aiSearch', 'Search with AI')}
                  </>
                )}
              </Button>
              {isAiSearching && (
                <p className="text-xs text-text-muted">
                  {t('pack.resolve.aiNote', 'This may take up to 30 seconds...')}
                </p>
              )}
            </div>
          )}

          {/* Civitai Tab */}
          {tab === 'civitai' && (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Globe className="w-10 h-10 text-text-muted/50" />
              <p className="text-text-muted text-center">
                {t(
                  'pack.resolve.civitaiPlaceholder',
                  'Manual Civitai search coming in Phase 4.'
                )}
              </p>
              <p className="text-xs text-text-muted">
                {t(
                  'pack.resolve.useAiInstead',
                  'Use AI Resolve for automated Civitai search.'
                )}
              </p>
            </div>
          )}

          {/* HuggingFace Tab */}
          {tab === 'huggingface' && (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Database className="w-10 h-10 text-text-muted/50" />
              <p className="text-text-muted text-center">
                {t(
                  'pack.resolve.hfPlaceholder',
                  'Manual HuggingFace search coming in Phase 4.'
                )}
              </p>
              <p className="text-xs text-text-muted">
                {t(
                  'pack.resolve.useAiInstead',
                  'Use AI Resolve for automated HuggingFace search.'
                )}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-mid bg-slate-dark/50 flex gap-3">
          <Button variant="secondary" onClick={onClose} className="flex-1">
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button
            onClick={() => selectedCandidate && onApply(selectedCandidate.candidate_id)}
            disabled={!selectedCandidate || isApplying}
            variant="secondary"
            className="flex-1"
          >
            {isApplying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Check className="w-4 h-4" />
                {t('pack.resolve.apply', 'Apply')}
              </>
            )}
          </Button>
          <Button
            onClick={() =>
              selectedCandidate && onApplyAndDownload(selectedCandidate.candidate_id)
            }
            disabled={!selectedCandidate || isApplying}
            className="flex-1"
          >
            {isApplying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Download className="w-4 h-4" />
                {t('pack.resolve.applyDownload', 'Apply & Download')}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default DependencyResolverModal
