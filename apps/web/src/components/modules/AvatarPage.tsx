/**
 * AvatarPage — Fullscreen AI assistant interface.
 *
 * Two modes:
 * - Ready: Chat interface with message history, input, provider indicator
 * - Setup: Beautiful onboarding guide with provider detection
 */

import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  Sparkles,
  Bot,
  Send,
  Terminal,
  CheckCircle2,
  XCircle,
  Loader2,
  Zap,
  Shield,
  Brain,
  MessageSquare,
  Info,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAvatar } from '../avatar/AvatarProvider'
import { getAvatarConfig, avatarKeys, type AvatarProvider as ProviderInfo } from '../../lib/avatar/api'

// ─── Chat Message Type ───────────────────────────────────────────────
interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
}

// ─── Main Page Component ─────────────────────────────────────────────

export function AvatarPage() {
  const { available, state, status, isLoading } = useAvatar()

  if (isLoading) {
    return <LoadingState />
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {available ? (
        <ChatInterface status={status} />
      ) : (
        <SetupGuide state={state} providers={status?.providers ?? []} />
      )}
    </div>
  )
}

// ─── Loading State ───────────────────────────────────────────────────

function LoadingState() {
  const { t } = useTranslation()

  return (
    <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center">
      <div className="text-center">
        <div className="relative w-20 h-20 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full bg-gradient-to-br from-synapse/20 to-pulse/20 animate-pulse" />
          <div className="absolute inset-2 rounded-full bg-slate-deep flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-synapse animate-pulse" />
          </div>
        </div>
        <p className="text-text-secondary text-sm">{t('avatar.loading')}</p>
      </div>
    </div>
  )
}

// ─── Chat Interface (STATE 1: Ready) ─────────────────────────────────

function ChatInterface({ status }: { status: ReturnType<typeof useAvatar>['status'] }) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: t('avatar.chat.welcomeMessage'),
      timestamp: Date.now(),
    },
  ])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const { data: config } = useQuery({
    queryKey: avatarKeys.config(),
    queryFn: getAvatarConfig,
    staleTime: 60_000,
  })

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || isSending) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsSending(true)

    // Placeholder: avatar-engine WebSocket chat will replace this
    setTimeout(() => {
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: t('avatar.chat.placeholder'),
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, assistantMsg])
      setIsSending(false)
    }, 1000)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const providerLabel = status?.active_provider
    ? status.active_provider.charAt(0).toUpperCase() + status.active_provider.slice(1)
    : '—'

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="shrink-0 px-6 py-3 border-b border-slate-mid/50 bg-slate-deep/80 backdrop-blur-sm">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-synapse to-pulse flex items-center justify-center shadow-lg shadow-synapse/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-text-primary">
                {t('avatar.title')}
              </h1>
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                <span>{providerLabel}</span>
                {config?.skills_count && (
                  <>
                    <span className="text-slate-600">·</span>
                    <span>
                      {t('avatar.chat.skillsCount', {
                        count: config.skills_count.builtin + config.skills_count.custom,
                      })}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={clsx(
              'px-2 py-1 rounded-lg text-xs font-medium border',
              status?.safety === 'safe'
                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                : status?.safety === 'ask'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  : 'bg-red-500/10 text-red-400 border-red-500/20'
            )}>
              <Shield className="w-3 h-3 inline-block mr-1" />
              {status?.safety ?? 'safe'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-4 space-y-4">
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isSending && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-synapse/30 to-pulse/30 flex items-center justify-center shrink-0">
                <Sparkles className="w-4 h-4 text-synapse" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-tl-md bg-slate-deep/80 border border-slate-mid/30">
                <div className="flex items-center gap-2 text-text-muted text-sm">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{t('avatar.chat.thinking')}</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-slate-mid/50 bg-slate-deep/80 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          {/* Suggestion chips */}
          {messages.length <= 1 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {[
                'avatar.suggestions.inventory',
                'avatar.suggestions.parameters',
                'avatar.suggestions.dependencies',
              ].map(key => (
                <button
                  key={key}
                  onClick={() => setInput(t(key))}
                  className="px-3 py-1.5 rounded-lg bg-slate-mid/30 border border-slate-mid/50 text-xs text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary hover:border-synapse/30 transition-all duration-150"
                >
                  {t(key)}
                </button>
              ))}
            </div>
          )}
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('avatar.chat.inputPlaceholder')}
              rows={1}
              className={clsx(
                'flex-1 px-4 py-3 rounded-xl resize-none',
                'bg-slate-800/50 border border-slate-700 text-text-primary',
                'placeholder:text-slate-500 text-sm leading-relaxed',
                'focus:outline-none focus:border-synapse/50 focus:ring-1 focus:ring-synapse/20',
                'transition-colors duration-150',
              )}
              style={{ maxHeight: '120px' }}
              onInput={e => {
                const el = e.target as HTMLTextAreaElement
                el.style.height = 'auto'
                el.style.height = Math.min(el.scrollHeight, 120) + 'px'
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className={clsx(
                'w-11 h-11 rounded-xl flex items-center justify-center shrink-0',
                'transition-all duration-150',
                input.trim() && !isSending
                  ? 'bg-gradient-to-r from-synapse to-pulse text-white shadow-lg shadow-synapse/25 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]'
                  : 'bg-slate-800/50 text-slate-600 cursor-not-allowed',
              )}
            >
              <Send className="w-4.5 h-4.5" />
            </button>
          </div>
          <p className="text-[10px] text-text-muted mt-2 text-center">
            {t('avatar.chat.enterHint')}
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Message Bubble ──────────────────────────────────────────────────

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={clsx('flex items-start gap-3', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div className={clsx(
        'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
        isUser
          ? 'bg-slate-mid/50'
          : 'bg-gradient-to-br from-synapse/30 to-pulse/30',
      )}>
        {isUser ? (
          <MessageSquare className="w-4 h-4 text-text-secondary" />
        ) : (
          <Sparkles className="w-4 h-4 text-synapse" />
        )}
      </div>

      {/* Bubble */}
      <div className={clsx(
        'max-w-[75%] px-4 py-3 text-sm leading-relaxed',
        isUser
          ? 'rounded-2xl rounded-tr-md bg-synapse/15 border border-synapse/20 text-text-primary'
          : 'rounded-2xl rounded-tl-md bg-slate-deep/80 border border-slate-mid/30 text-text-primary',
      )}>
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  )
}

// ─── Setup Guide (STATE 2/3: Not Ready) ──────────────────────────────

function SetupGuide({
  state,
  providers,
}: {
  state: string
  providers: ProviderInfo[]
}) {
  const { t } = useTranslation()

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Hero */}
        <div className="text-center mb-10">
          <div className="relative w-24 h-24 mx-auto mb-6">
            {/* Outer glow ring */}
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-synapse/20 to-pulse/20 animate-pulse-slow" />
            {/* Inner ring */}
            <div className="absolute inset-1 rounded-full border border-synapse/30" />
            {/* Core */}
            <div className="absolute inset-3 rounded-full bg-gradient-to-br from-slate-deep to-slate-dark flex items-center justify-center border border-slate-mid/50">
              <Bot className="w-10 h-10 text-synapse/70" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-text-primary mb-2">
            {t('avatar.setup.title')}
          </h1>
          <p className="text-text-secondary max-w-lg mx-auto leading-relaxed">
            {t('avatar.setup.description')}
          </p>
        </div>

        {/* Status card */}
        {state !== 'disabled' && (
          <div className="mb-8 p-4 rounded-2xl bg-slate-deep/50 border border-slate-mid/50">
            <div className="flex items-center gap-3 mb-3">
              <Info className="w-5 h-5 text-synapse" />
              <span className="text-sm font-medium text-text-primary">
                {t('avatar.setup.statusTitle')}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <StatusItem
                label={t('avatar.setup.engineLabel')}
                ok={state !== 'no_engine' && state !== 'setup_required'}
              />
              <StatusItem
                label={t('avatar.setup.providerLabel')}
                ok={state !== 'no_provider' && state !== 'setup_required'}
              />
            </div>
          </div>
        )}

        {/* Provider cards */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4">
            {t('avatar.setup.providersTitle')}
          </h2>
          <div className="space-y-3">
            {providers.map(provider => (
              <ProviderCard key={provider.name} provider={provider} />
            ))}
            {providers.length === 0 && (
              <div className="space-y-3">
                <ProviderCardStatic name="gemini" displayName="Gemini CLI" installed={false} />
                <ProviderCardStatic name="claude" displayName="Claude Code" installed={false} />
                <ProviderCardStatic name="codex" displayName="Codex CLI" installed={false} />
              </div>
            )}
          </div>
        </div>

        {/* Setup steps */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4">
            {t('avatar.setup.stepsTitle')}
          </h2>
          <div className="space-y-3">
            <SetupStep
              number={1}
              title={t('avatar.setup.step1Title')}
              description={t('avatar.setup.step1Desc')}
              done={state !== 'setup_required' && state !== 'no_engine'}
            />
            <SetupStep
              number={2}
              title={t('avatar.setup.step2Title')}
              description={t('avatar.setup.step2Desc')}
              done={state !== 'setup_required' && state !== 'no_provider'}
            />
            <SetupStep
              number={3}
              title={t('avatar.setup.step3Title')}
              description={t('avatar.setup.step3Desc')}
              done={false}
            />
          </div>
        </div>

        {/* Features preview */}
        <div>
          <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-4">
            {t('avatar.setup.featuresTitle')}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <FeatureCard
              icon={Brain}
              title={t('avatar.setup.feature1')}
              description={t('avatar.setup.feature1Desc')}
              color="synapse"
            />
            <FeatureCard
              icon={Zap}
              title={t('avatar.setup.feature2')}
              description={t('avatar.setup.feature2Desc')}
              color="neural"
            />
            <FeatureCard
              icon={Terminal}
              title={t('avatar.setup.feature3')}
              description={t('avatar.setup.feature3Desc')}
              color="pulse"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────

function StatusItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {ok ? (
        <CheckCircle2 className="w-4 h-4 text-green-400" />
      ) : (
        <XCircle className="w-4 h-4 text-red-400" />
      )}
      <span className={ok ? 'text-text-primary' : 'text-text-muted'}>{label}</span>
    </div>
  )
}

function ProviderCard({ provider }: { provider: ProviderInfo }) {
  return (
    <ProviderCardStatic
      name={provider.name}
      displayName={provider.display_name}
      installed={provider.installed}
    />
  )
}

function ProviderCardStatic({
  name,
  displayName,
  installed,
}: {
  name: string
  displayName: string
  installed: boolean
}) {
  const { t } = useTranslation()

  const gradients: Record<string, string> = {
    gemini: 'from-blue-500/20 to-cyan-500/20',
    claude: 'from-amber-500/20 to-orange-500/20',
    codex: 'from-green-500/20 to-emerald-500/20',
  }

  const iconColors: Record<string, string> = {
    gemini: 'text-blue-400',
    claude: 'text-amber-400',
    codex: 'text-green-400',
  }

  return (
    <div className={clsx(
      'flex items-center gap-4 p-4 rounded-xl border transition-all duration-200',
      installed
        ? 'bg-slate-deep/80 border-green-500/20'
        : 'bg-slate-deep/50 border-slate-mid/30 opacity-80',
    )}>
      <div className={clsx(
        'w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center',
        gradients[name] || 'from-slate-mid/50 to-slate-mid/30',
      )}>
        <Terminal className={clsx('w-5 h-5', iconColors[name] || 'text-text-secondary')} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text-primary">{displayName}</div>
        <div className="text-xs text-text-muted">
          <code className="bg-slate-mid/30 px-1.5 py-0.5 rounded">{name}</code>
        </div>
      </div>
      {installed ? (
        <span className="flex items-center gap-1.5 text-xs text-green-400 font-medium">
          <CheckCircle2 className="w-3.5 h-3.5" />
          {t('avatar.setup.installed')}
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-xs text-text-muted">
          <XCircle className="w-3.5 h-3.5" />
          {t('avatar.setup.notInstalled')}
        </span>
      )}
    </div>
  )
}

function SetupStep({
  number,
  title,
  description,
  done,
}: {
  number: number
  title: string
  description: string
  done: boolean
}) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-deep/50 border border-slate-mid/30">
      <div className={clsx(
        'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-sm font-bold',
        done
          ? 'bg-green-500/20 text-green-400'
          : 'bg-slate-mid/30 text-text-muted',
      )}>
        {done ? <CheckCircle2 className="w-4 h-4" /> : number}
      </div>
      <div>
        <div className={clsx(
          'text-sm font-medium',
          done ? 'text-text-secondary line-through' : 'text-text-primary',
        )}>
          {title}
        </div>
        <div className="text-xs text-text-muted mt-0.5">{description}</div>
      </div>
    </div>
  )
}

function FeatureCard({
  icon: Icon,
  title,
  description,
  color,
}: {
  icon: typeof Brain
  title: string
  description: string
  color: 'synapse' | 'neural' | 'pulse'
}) {
  const colorMap = {
    synapse: { bg: 'from-synapse/10 to-synapse/5', border: 'border-synapse/20', text: 'text-synapse' },
    neural: { bg: 'from-neural/10 to-neural/5', border: 'border-neural/20', text: 'text-neural' },
    pulse: { bg: 'from-pulse/10 to-pulse/5', border: 'border-pulse/20', text: 'text-pulse' },
  }
  const c = colorMap[color]

  return (
    <div className={clsx(
      'p-4 rounded-xl border bg-gradient-to-br',
      c.bg, c.border,
    )}>
      <Icon className={clsx('w-5 h-5 mb-2', c.text)} />
      <div className="text-sm font-medium text-text-primary">{title}</div>
      <div className="text-xs text-text-muted mt-1">{description}</div>
    </div>
  )
}
