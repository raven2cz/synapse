/**
 * InstallPlugin (PROTOTYPE)
 *
 * Plugin for installation packs (ComfyUI, Forge, etc.)
 *
 * CURRENT STATUS: PROTOTYPE
 * Full implementation will be done in a separate plan.
 *
 * PLANNED FEATURES:
 * - Script management (install.sh, start.sh, stop.sh)
 * - Console output viewer
 * - Environment status monitoring
 * - Install/Start/Stop buttons
 *
 * IDENTIFICATION:
 * Packs with user_tags including 'install-pack' are considered install packs.
 */

import { useState } from 'react'
import {
  Terminal,
  Play,
  Square,
  Download,
  Settings,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import type { PackDetail } from '../types'
import type {
  PackPlugin,
  PluginContext,
  PluginBadge,
} from './types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

type ScriptStatus = 'idle' | 'running' | 'success' | 'error'

interface Script {
  name: string
  description: string
  status: ScriptStatus
  lastRun?: string
}

// =============================================================================
// Scripts Section (Prototype)
// =============================================================================

interface ScriptsSectionProps {
  context: PluginContext
}

function ScriptsSection({ context }: ScriptsSectionProps) {
  const { toast } = context
  const [runningScript, setRunningScript] = useState<string | null>(null)

  // Mock scripts - in full implementation, these would come from pack data
  const scripts: Script[] = [
    { name: 'install.sh', description: 'Install the environment', status: 'idle' },
    { name: 'start.sh', description: 'Start the server', status: 'idle' },
    { name: 'stop.sh', description: 'Stop the server', status: 'idle' },
    { name: 'update.sh', description: 'Update to latest version', status: 'idle' },
  ]

  const handleRunScript = async (scriptName: string) => {
    setRunningScript(scriptName)
    toast.info(`Running ${scriptName}...`)

    // Simulate script execution
    await new Promise(resolve => setTimeout(resolve, 2000))

    setRunningScript(null)
    toast.success(`${scriptName} completed`)
  }

  return (
    <Card className={clsx('overflow-hidden', ANIMATION_PRESETS.fadeIn)}>
      <div className="p-4 border-b border-slate-mid">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/20 rounded-lg">
            <Terminal className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-medium text-text-primary">Scripts</h3>
            <p className="text-sm text-text-muted">
              Manage installation and runtime
            </p>
          </div>
        </div>
      </div>

      <div className="divide-y divide-slate-mid">
        {scripts.map(script => (
          <div
            key={script.name}
            className="p-4 flex items-center justify-between hover:bg-slate-mid/20 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className={clsx(
                'p-1.5 rounded',
                script.status === 'running' ? 'bg-synapse/20' :
                script.status === 'success' ? 'bg-green-500/20' :
                script.status === 'error' ? 'bg-red-500/20' :
                'bg-slate-mid/50'
              )}>
                {script.status === 'running' ? (
                  <Loader2 className="w-4 h-4 text-synapse animate-spin" />
                ) : script.status === 'success' ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : script.status === 'error' ? (
                  <XCircle className="w-4 h-4 text-red-400" />
                ) : (
                  <Terminal className="w-4 h-4 text-text-muted" />
                )}
              </div>
              <div>
                <p className="font-mono text-sm text-text-primary">{script.name}</p>
                <p className="text-xs text-text-muted">{script.description}</p>
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleRunScript(script.name)}
              disabled={runningScript !== null}
            >
              {runningScript === script.name ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Run
            </Button>
          </div>
        ))}
      </div>
    </Card>
  )
}

// =============================================================================
// Environment Status (Prototype)
// =============================================================================

interface EnvironmentStatusProps {
  context: PluginContext
}

function EnvironmentStatus(_props: EnvironmentStatusProps) {
  // Mock status - in full implementation, this would be fetched from backend
  const status = {
    installed: true,
    running: false,
    version: '1.0.0',
    lastStarted: '2 hours ago',
  }

  return (
    <Card className={clsx('p-4', ANIMATION_PRESETS.fadeIn)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-lg',
            status.running ? 'bg-green-500/20' : 'bg-slate-mid/50'
          )}>
            <Settings className={clsx(
              'w-5 h-5',
              status.running ? 'text-green-400' : 'text-text-muted'
            )} />
          </div>
          <div>
            <h3 className="font-medium text-text-primary">Environment Status</h3>
            <p className="text-sm text-text-muted">
              {status.running ? (
                <span className="text-green-400">Running</span>
              ) : status.installed ? (
                <span className="text-text-muted">Stopped</span>
              ) : (
                <span className="text-amber-400">Not installed</span>
              )}
              {status.version && (
                <span className="ml-2">• v{status.version}</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {status.running ? (
            <Button variant="secondary" size="sm">
              <Square className="w-4 h-4" />
              Stop
            </Button>
          ) : status.installed ? (
            <Button variant="primary" size="sm">
              <Play className="w-4 h-4" />
              Start
            </Button>
          ) : (
            <Button variant="primary" size="sm">
              <Download className="w-4 h-4" />
              Install
            </Button>
          )}
        </div>
      </div>
    </Card>
  )
}

// =============================================================================
// Prototype Notice
// =============================================================================

function PrototypeNotice() {
  return (
    <Card className={clsx(
      'p-4 bg-amber-500/10 border-amber-500/30',
      ANIMATION_PRESETS.fadeIn
    )}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-medium text-amber-400">Install Pack (Prototype)</h3>
          <p className="text-sm text-text-muted mt-1">
            This is a prototype implementation. Full install pack functionality
            (script execution, console output, environment management) will be
            implemented in a future update.
          </p>
        </div>
      </div>
    </Card>
  )
}

// =============================================================================
// Plugin Definition
// =============================================================================

export const InstallPlugin: PackPlugin = {
  id: 'install',
  name: 'Install Pack',
  priority: 100, // Highest - most specific match

  appliesTo: (pack: PackDetail) => {
    // Check for install-pack tag
    return pack.user_tags?.includes('install-pack') ?? false
  },

  getBadge: (): PluginBadge => ({
    label: 'Install',
    variant: 'warning',
    icon: 'Terminal',
    tooltip: 'Installation pack for UI environment',
  }),

  features: {
    canEditMetadata: true,
    canEditPreviews: false,
    canEditDependencies: false,
    canEditWorkflows: false,
    canEditParameters: false,
    canCheckUpdates: false,
    canManagePackDependencies: false,
    canRunScripts: true,
    canDelete: true,
  },

  renderHeaderActions: (context: PluginContext) => {
    // Quick actions for install packs
    return (
      <>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => context.toast.info('Console feature coming soon')}
        >
          <Terminal className="w-4 h-4" />
          Console
        </Button>
      </>
    )
  },

  renderExtraSections: (context: PluginContext) => {
    return (
      <div className="space-y-4">
        <PrototypeNotice />
        <EnvironmentStatus context={context} />
        <ScriptsSection context={context} />
      </div>
    )
  },

  onPackLoad: (pack: PackDetail) => {
    console.log('[InstallPlugin] Loaded install pack:', pack.name)
  },

  validateChanges: (_pack, changes) => {
    // Install packs have limited editability
    const errors: Record<string, string> = {}

    if (changes.description !== undefined && changes.description.length > 5000) {
      errors.description = 'Description is too long'
    }

    return {
      valid: Object.keys(errors).length === 0,
      errors,
    }
  },
}

export default InstallPlugin
