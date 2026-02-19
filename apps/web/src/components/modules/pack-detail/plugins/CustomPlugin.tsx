/**
 * CustomPlugin
 *
 * Plugin for custom (locally created) packs.
 *
 * FEATURES:
 * - Full editability of all fields
 * - Pack dependencies management (via PackDepsSection)
 * - Support for 7+ asset dependencies
 * - Markdown description editor
 * - Preview management
 *
 * This is the DEFAULT plugin - used as fallback when no other plugin matches.
 */

import { useTranslation } from 'react-i18next'
import {
  Check,
  Edit3,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import type { PackDetail } from '../types'
import type {
  PackPlugin,
  PluginContext,
  PluginBadge,
} from './types'
import { PackDepsSection } from '../sections/PackDepsSection'
import i18n from '@/i18n'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Edit Capabilities Info
// =============================================================================

interface EditCapabilitiesInfoProps {
  context: PluginContext
}

function EditCapabilitiesInfo({ context }: EditCapabilitiesInfoProps) {
  const { t } = useTranslation()
  const { isEditing } = context

  if (!isEditing) return null

  return (
    <Card className={clsx('p-4 bg-synapse/10 border-synapse/30', ANIMATION_PRESETS.fadeIn)}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-synapse/20 rounded-lg">
          <Edit3 className="w-5 h-5 text-synapse" />
        </div>
        <div>
          <h3 className="font-medium text-text-primary">{t('pack.plugins.custom.fullEditMode')}</h3>
          <p className="text-sm text-text-muted mt-1">
            {t('pack.plugins.custom.fullEditDesc')}
          </p>
          <ul className="text-sm text-text-muted mt-2 space-y-1">
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              {t('pack.plugins.custom.editName')}
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              {t('pack.plugins.custom.editPreviews')}
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              {t('pack.plugins.custom.editDeps')}
            </li>
            <li className="flex items-center gap-2">
              <Check className="w-3 h-3 text-synapse" />
              {t('pack.plugins.custom.editWorkflows')}
            </li>
          </ul>
        </div>
      </div>
    </Card>
  )
}

// =============================================================================
// Plugin Definition
// =============================================================================

export const CustomPlugin: PackPlugin = {
  id: 'custom',
  get name() { return i18n.t('pack.plugins.custom.title') },
  priority: 0, // Lowest - fallback

  appliesTo: (pack: PackDetail) => {
    // Match custom packs or use as fallback
    return pack.pack?.pack_category === 'custom' || true
  },

  getBadge: (pack: PackDetail): PluginBadge | null => {
    // Only show badge for explicitly custom packs
    if (pack.pack?.pack_category === 'custom') {
      return {
        label: i18n.t('pack.plugins.custom.title'),
        variant: 'success',
        icon: 'Package',
        tooltip: i18n.t('pack.plugins.custom.localPack'),
      }
    }
    return null
  },

  features: {
    canEditMetadata: true,
    canEditPreviews: true,
    canEditDependencies: true,
    canEditWorkflows: true,
    canEditParameters: true,
    canCheckUpdates: false,
    canManagePackDependencies: true,
    canRunScripts: false,
    canDelete: true,
  },

  renderHeaderActions: (_context: PluginContext) => {
    // Custom packs don't need extra header actions
    // Edit button is already provided by the main header
    return null
  },

  renderExtraSections: (context: PluginContext) => {
    return (
      <div className="space-y-4">
        <EditCapabilitiesInfo context={context} />
        <PackDepsSection context={context} />
      </div>
    )
  },

  onPackLoad: (pack: PackDetail) => {
    console.log('[CustomPlugin] Loaded pack:', pack.name, 'category:', pack.pack?.pack_category)
  },

  validateChanges: (_pack, changes) => {
    const errors: Record<string, string> = {}

    // Validate name if changed
    if (changes.name !== undefined) {
      if (!changes.name || changes.name.trim() === '') {
        errors.name = i18n.t('pack.plugins.custom.nameRequired')
      } else if (changes.name.length > 100) {
        errors.name = i18n.t('pack.plugins.custom.nameTooLong')
      }
    }

    // Validate version if changed
    if (changes.version !== undefined) {
      const versionRegex = /^\d+\.\d+\.\d+$/
      if (changes.version && !versionRegex.test(changes.version)) {
        errors.version = i18n.t('pack.plugins.custom.invalidVersion')
      }
    }

    return {
      valid: Object.keys(errors).length === 0,
      errors,
    }
  },

  onBeforeSave: (_pack, changes) => {
    // Clean up changes before save
    const cleanedChanges = { ...changes }

    // Trim strings
    if (cleanedChanges.name) {
      cleanedChanges.name = cleanedChanges.name.trim()
    }
    if (cleanedChanges.description) {
      cleanedChanges.description = cleanedChanges.description.trim()
    }

    return { changes: cleanedChanges }
  },
}

export default CustomPlugin
