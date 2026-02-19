import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Settings, Save, RefreshCw, CheckCircle2, XCircle, AlertCircle, Key, FolderOpen, Eye, EyeOff, Database, Layers, Zap, Cloud, Link2, Unlink } from 'lucide-react'
import { Card, CardTitle, CardDescription } from '../ui/Card'
import { Button } from '../ui/Button'
import { useState, useEffect, useRef } from 'react'
import { useSettingsStore } from '../../stores/settingsStore'
import { toast } from '../../stores/toastStore'
import type { BackupStatus, BackupConfigRequest } from './inventory/types'
import { formatBytes } from '../../lib/utils/format'
import { AIServicesSettings, type AIServicesSettingsHandle } from './settings/AIServicesSettings'
import { LanguageSettings } from './settings/LanguageSettings'

interface SettingsResponse {
  comfyui_path: string
  synapse_data_path: string
  nsfw_blur_enabled: boolean
  civitai_token_set: boolean
  huggingface_token_set: boolean
  // Store v2 settings
  store_root: string
  store_ui_roots: Record<string, string>
  store_default_ui_set: string
  store_ui_sets: Record<string, string[]>
}

interface DiagnosticsResponse {
  comfyui_found: boolean
  comfyui_path: string
  models_found: Record<string, number>
  custom_nodes_count: number
  packs_registered: number
  packs_installed: number
  issues: Array<{
    level: string
    message: string
    suggestion: string | null
  }>
}

export function SettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { nsfwBlurEnabled, setNsfwBlur, autoCheckUpdates, setAutoCheckUpdates } = useSettingsStore()
  const aiSettingsRef = useRef<AIServicesSettingsHandle>(null)
  const [comfyuiPath, setComfyuiPath] = useState('~/ComfyUI')
  const [civitaiToken, setCivitaiToken] = useState('')
  const [hfToken, setHfToken] = useState('')
  const [showCivitaiToken, setShowCivitaiToken] = useState(false)
  const [showHfToken, setShowHfToken] = useState(false)

  // Store v2 settings
  const [storeRoot, setStoreRoot] = useState('~/.synapse/store')
  const [storeUiRoots, setStoreUiRoots] = useState({
    comfyui: '~/ComfyUI',
    forge: '~/stable-diffusion-webui-forge',
    a1111: '~/stable-diffusion-webui',
    sdnext: '~/sdnext',
  })
  const [storeDefaultUiSet, setStoreDefaultUiSet] = useState('local')

  // Backup storage settings
  const [backupEnabled, setBackupEnabled] = useState(false)
  const [backupPath, setBackupPath] = useState('')
  const [autoBackupNew, setAutoBackupNew] = useState(false)
  const [warnBeforeDeleteLastCopy, setWarnBeforeDeleteLastCopy] = useState(true)

  const { data: settings } = useQuery<SettingsResponse>({
    queryKey: ['settings'],
    queryFn: async () => {
      const res = await fetch('/api/system/settings')
      if (!res.ok) throw new Error('Failed to fetch settings')
      return res.json()
    },
  })

  useEffect(() => {
    if (settings) {
      setComfyuiPath(settings.comfyui_path || '~/ComfyUI')
      // Store v2 settings
      if (settings.store_root) setStoreRoot(settings.store_root)
      if (settings.store_ui_roots) setStoreUiRoots(settings.store_ui_roots as any)
      if (settings.store_default_ui_set) setStoreDefaultUiSet(settings.store_default_ui_set)
    }
  }, [settings])

  const { data: diagnostics, refetch: runDiagnostics, isFetching: isRunningDiagnostics } = useQuery<DiagnosticsResponse>({
    queryKey: ['diagnostics'],
    queryFn: async () => {
      const res = await fetch('/api/system/diagnostics')
      if (!res.ok) throw new Error('Failed to run diagnostics')
      return res.json()
    },
  })

  // Backup status query - also tells us if store is initialized
  const { data: backupStatus, error: backupError } = useQuery<BackupStatus>({
    queryKey: ['backup-status'],
    queryFn: async () => {
      const res = await fetch('/api/store/backup/status')
      if (!res.ok) {
        if (res.status === 400) {
          // Store not initialized
          throw new Error('STORE_NOT_INITIALIZED')
        }
        throw new Error('Failed to fetch backup status')
      }
      return res.json()
    },
    retry: false, // Don't retry if store is not initialized
  })

  // Store is initialized if backup status query succeeded
  const isStoreInitialized = !!backupStatus && !backupError

  // Sync backup state from backend
  useEffect(() => {
    if (backupStatus) {
      setBackupEnabled(backupStatus.enabled)
      setBackupPath(backupStatus.path || '')
      setAutoBackupNew(backupStatus.auto_backup_new || false)
      setWarnBeforeDeleteLastCopy(backupStatus.warn_before_delete_last_copy ?? true)
    }
  }, [backupStatus])

  // Backup config mutation
  const updateBackupConfigMutation = useMutation({
    mutationFn: async (config: BackupConfigRequest) => {
      const res = await fetch('/api/store/backup/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Failed to update backup config' }))
        throw new Error(error.detail || 'Failed to update backup config')
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backup-status'] })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
    },
  })

  const updateSettingsMutation = useMutation({
    mutationFn: async (updates: Partial<SettingsResponse> & { civitai_token?: string; huggingface_token?: string }) => {
      const res = await fetch('/api/system/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      if (!res.ok) throw new Error('Failed to update settings')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['diagnostics'] })
      // Clear token inputs after save
      setCivitaiToken('')
      setHfToken('')
    },
  })

  const handleSave = async () => {
    try {
      // Save general settings
      const updates: any = {
        comfyui_path: storeUiRoots.comfyui || comfyuiPath,
        nsfw_blur_enabled: nsfwBlurEnabled,
        store_root: storeRoot,
        store_ui_roots: storeUiRoots,
        store_default_ui_set: storeDefaultUiSet,
      }
      if (civitaiToken) updates.civitai_token = civitaiToken
      if (hfToken) updates.huggingface_token = hfToken

      // Save backup config
      const backupConfig: BackupConfigRequest = {
        enabled: backupEnabled,
        path: backupPath || undefined,
        auto_backup_new: autoBackupNew,
        warn_before_delete_last_copy: warnBeforeDeleteLastCopy,
      }

      // Build promises array - only include AI settings if there are changes
      const savePromises: Promise<unknown>[] = [
        updateSettingsMutation.mutateAsync(updates),
        updateBackupConfigMutation.mutateAsync(backupConfig),
      ]

      // Include AI settings save if there are unsaved changes
      if (aiSettingsRef.current?.hasChanges()) {
        savePromises.push(aiSettingsRef.current.save())
      }

      // Execute all saves
      await Promise.all(savePromises)

      toast.success(t('settings.saved'))
    } catch (error) {
      toast.error(t('settings.saveFailed'))
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
          <Zap className="w-7 h-7 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-100">{t('settings.title')}</h1>
          <p className="text-slate-400">
            {t('settings.subtitle')}
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {/* 1. Display Settings - Language first so user understands the rest */}
        <Card>
          <CardTitle>
            <Eye className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            {t('settings.display.title')}
          </CardTitle>
          <CardDescription>{t('settings.display.subtitle')}</CardDescription>

          <div className="mt-4 space-y-6">
            {/* Language Settings - first */}
            <LanguageSettings />

            {/* Divider */}
            <div className="border-t border-slate-700/50" />

            {/* NSFW Blur toggle */}
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
              <div>
                <span className="text-slate-100">{t('settings.display.nsfwBlur')}</span>
                <p className="text-xs text-slate-500 mt-0.5">
                  {t('settings.display.nsfwBlurDesc')}
                </p>
              </div>
              <button
                onClick={() => setNsfwBlur(!nsfwBlurEnabled)}
                className={`relative w-12 h-6 rounded-full transition-all duration-200 ${
                  nsfwBlurEnabled ? 'bg-indigo-500 shadow-lg shadow-indigo-500/40' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200 ${
                    nsfwBlurEnabled ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* Divider */}
            <div className="border-t border-slate-700/50" />

            {/* Auto-check updates */}
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
              <div>
                <span className="text-slate-100">{t('settings.display.autoCheckUpdates')}</span>
                <p className="text-xs text-slate-500 mt-0.5">
                  {t('settings.display.autoCheckUpdatesDesc')}
                </p>
              </div>
              <select
                value={autoCheckUpdates}
                onChange={(e) => setAutoCheckUpdates(e.target.value as 'off' | '1h' | '6h' | '24h')}
                className="px-3 py-1.5 bg-slate-800/50 border border-slate-700 rounded-lg text-slate-100 text-sm focus:outline-none focus:border-indigo-500/50"
              >
                <option value="off">{t('settings.display.autoCheckOff')}</option>
                <option value="1h">{t('settings.display.autoCheck1h')}</option>
                <option value="6h">{t('settings.display.autoCheck6h')}</option>
                <option value="24h">{t('settings.display.autoCheck24h')}</option>
              </select>
            </div>
          </div>
        </Card>

        {/* 2. Paths */}
        <Card>
          <CardTitle>
            <FolderOpen className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            {t('settings.paths.title')}
          </CardTitle>
          <CardDescription>{t('settings.paths.subtitle')}</CardDescription>

          <div className="mt-4 space-y-4">


            <div>
              <label className="block text-sm text-slate-400 mb-2">
                {t('settings.paths.synapseData')}
              </label>
              <input
                type="text"
                value={settings?.synapse_data_path || '~/.synapse'}
                disabled
                className="w-full px-4 py-2.5 bg-slate-800/30 border border-slate-700/50 rounded-xl text-slate-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                {t('settings.paths.synapseDataDesc')}
              </p>
            </div>
          </div>
        </Card>

        {/* 3. Store v2 Configuration */}
        <Card>
          <CardTitle>
            <Database className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            {t('settings.store.title')}
          </CardTitle>
          <CardDescription>{t('settings.store.subtitle')}</CardDescription>

          <div className="mt-4 space-y-4">
            {/* Store Root */}
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                {t('settings.store.root')}
              </label>
              <input
                type="text"
                value={storeRoot}
                onChange={(e) => setStoreRoot(e.target.value)}
                placeholder="~/.synapse/store"
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
              />
              <p className="text-xs text-slate-500 mt-1">
                {t('settings.store.rootDesc')}
              </p>
            </div>

            {/* Default UI Set */}
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                {t('settings.store.defaultUiSet')}
              </label>
              <select
                value={storeDefaultUiSet}
                onChange={(e) => setStoreDefaultUiSet(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-indigo-500/50"
              >
                {settings?.store_ui_sets && Object.keys(settings.store_ui_sets).map((setName) => (
                  <option key={setName} value={setName}>
                    {setName} ({settings.store_ui_sets[setName].join(', ')})
                  </option>
                ))}
              </select>
            </div>

            {/* UI Roots */}
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                <Layers className="w-4 h-4 inline-block mr-1" />
                {t('settings.store.uiPaths')}
              </label>
              <div className="space-y-2">
                {Object.entries(storeUiRoots).map(([ui, path]) => (
                  <div key={ui} className="flex items-center gap-2">
                    <span className="w-24 text-sm text-slate-500 capitalize">{ui}</span>
                    <input
                      type="text"
                      value={path}
                      onChange={(e) => setStoreUiRoots(prev => ({ ...prev, [ui]: e.target.value }))}
                      placeholder={`~/${ui}`}
                      className="flex-1 px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-slate-100 text-sm placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Store Actions */}
            <div className="flex gap-2 pt-2">
              <Button
                variant={isStoreInitialized ? 'secondary' : 'primary'}
                size="sm"
                leftIcon={<Zap className="w-4 h-4" />}
                onClick={async () => {
                  try {
                    const res = await fetch('/api/store/init', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ force: false })
                    })
                    if (res.ok) {
                      toast.success(t('settings.store.initSuccess'))
                      // Refresh all store-dependent queries
                      queryClient.invalidateQueries({ queryKey: ['backup-status'] })
                      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
                      queryClient.invalidateQueries({ queryKey: ['inventory'] })
                    } else {
                      const err = await res.text()
                      toast.error(t('settings.store.initFailed', { error: err }))
                    }
                  } catch (e) {
                    console.error('Init failed:', e)
                    toast.error(t('settings.store.initFailedGeneric'))
                  }
                }}
              >
                {isStoreInitialized ? t('settings.store.reInitStore') : t('settings.store.initStore')}
              </Button>
            </div>
          </div>
        </Card>

        {/* 4. Backup Storage */}
        <div id="backup-config">
        <Card>
          <CardTitle>
            <Cloud className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            {t('settings.backup.title')}
          </CardTitle>
          <CardDescription>{t('settings.backup.subtitle')}</CardDescription>

          <div className="mt-4 space-y-4">
            {/* Enable/Disable toggle */}
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
              <div>
                <span className="text-slate-100">{t('settings.backup.enable')}</span>
                <p className="text-xs text-slate-500 mt-0.5">
                  {t('settings.backup.enableDesc')}
                </p>
              </div>
              <button
                onClick={() => setBackupEnabled(!backupEnabled)}
                className={`relative w-12 h-6 rounded-full transition-all duration-200 ${
                  backupEnabled ? 'bg-indigo-500 shadow-lg shadow-indigo-500/40' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200 ${
                    backupEnabled ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* Backup Path */}
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                {t('settings.backup.path')}
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={backupPath}
                  onChange={(e) => setBackupPath(e.target.value)}
                  placeholder={t('settings.backup.pathPlaceholder')}
                  disabled={!backupEnabled}
                  className={`flex-1 px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50 ${
                    !backupEnabled ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                />
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {t('settings.backup.pathDesc')}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                💡 {t('settings.backup.gitHint')}
              </p>
            </div>

            {/* Connection Status */}
            {backupEnabled && (
              <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
                <div className="flex items-center gap-2">
                  {backupStatus?.connected ? (
                    <>
                      <Link2 className="w-4 h-4 text-green-400" />
                      <span className="text-green-400">{t('settings.backup.connected')}</span>
                    </>
                  ) : (
                    <>
                      <Unlink className="w-4 h-4 text-amber-400" />
                      <span className="text-amber-400">
                        {backupStatus?.error || t('settings.backup.disconnected')}
                      </span>
                    </>
                  )}
                </div>
                {backupStatus?.connected && backupStatus.total_bytes !== undefined && (
                  <div className="text-sm text-slate-400">
                    {t('settings.backup.usedSize', { size: formatBytes(backupStatus.total_bytes) })}
                    {backupStatus.free_space !== undefined && (
                      <span className="text-slate-500 ml-2">
                        {t('settings.backup.freeSpace', { size: formatBytes(backupStatus.free_space) })}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Auto-backup new blobs */}
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
              <div>
                <span className={`${!backupEnabled ? 'text-slate-500' : 'text-slate-100'}`}>
                  {t('settings.backup.autoBackup')}
                </span>
                <p className="text-xs text-slate-500 mt-0.5">
                  {t('settings.backup.autoBackupDesc')}
                </p>
              </div>
              <button
                onClick={() => setAutoBackupNew(!autoBackupNew)}
                disabled={!backupEnabled}
                className={`relative w-12 h-6 rounded-full transition-all duration-200 ${
                  autoBackupNew && backupEnabled ? 'bg-indigo-500 shadow-lg shadow-indigo-500/40' : 'bg-slate-700'
                } ${!backupEnabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200 ${
                    autoBackupNew ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>

            {/* Warn before delete last copy */}
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
              <div>
                <span className={`${!backupEnabled ? 'text-slate-500' : 'text-slate-100'}`}>
                  {t('settings.backup.warnLastCopy')}
                </span>
                <p className="text-xs text-slate-500 mt-0.5">
                  {t('settings.backup.warnLastCopyDesc')}
                </p>
              </div>
              <button
                onClick={() => setWarnBeforeDeleteLastCopy(!warnBeforeDeleteLastCopy)}
                disabled={!backupEnabled}
                className={`relative w-12 h-6 rounded-full transition-all duration-200 ${
                  warnBeforeDeleteLastCopy && backupEnabled ? 'bg-indigo-500 shadow-lg shadow-indigo-500/40' : 'bg-slate-700'
                } ${!backupEnabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200 ${
                    warnBeforeDeleteLastCopy ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </Card>
        </div>

        {/* 5. API Tokens */}
        <Card>
          <CardTitle>
            <Key className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            {t('settings.tokens.title')}
          </CardTitle>
          <CardDescription>{t('settings.tokens.subtitle')}</CardDescription>

          <div className="mt-4 space-y-4">
            {/* Civitai Token */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-slate-400">{t('settings.tokens.civitai')}</label>
                <span className={`flex items-center gap-1.5 text-xs ${settings?.civitai_token_set ? 'text-green-400' : 'text-amber-400'}`}>
                  {settings?.civitai_token_set ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {t('settings.tokens.configured')}
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3.5 h-3.5" />
                      {t('settings.tokens.notSet')}
                    </>
                  )}
                </span>
              </div>
              <div className="relative">
                <input
                  type={showCivitaiToken ? 'text' : 'password'}
                  value={civitaiToken}
                  onChange={(e) => setCivitaiToken(e.target.value)}
                  placeholder={settings?.civitai_token_set ? '••••••••••••••••' : t('settings.tokens.civitaiPlaceholder')}
                  className="w-full px-4 py-2.5 pr-12 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
                />
                <button
                  type="button"
                  onClick={() => setShowCivitaiToken(!showCivitaiToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showCivitaiToken ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {t('settings.tokens.civitaiLink').split('civitai.com')[0]}<a href="https://civitai.com/user/account" target="_blank" rel="noopener" className="text-indigo-400 hover:underline">civitai.com/user/account</a>
              </p>
            </div>

            {/* HuggingFace Token */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-slate-400">{t('settings.tokens.huggingface')}</label>
                <span className={`flex items-center gap-1.5 text-xs ${settings?.huggingface_token_set ? 'text-green-400' : 'text-amber-400'}`}>
                  {settings?.huggingface_token_set ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {t('settings.tokens.configured')}
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3.5 h-3.5" />
                      {t('settings.tokens.notSet')}
                    </>
                  )}
                </span>
              </div>
              <div className="relative">
                <input
                  type={showHfToken ? 'text' : 'password'}
                  value={hfToken}
                  onChange={(e) => setHfToken(e.target.value)}
                  placeholder={settings?.huggingface_token_set ? '••••••••••••••••' : t('settings.tokens.huggingfacePlaceholder')}
                  className="w-full px-4 py-2.5 pr-12 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
                />
                <button
                  type="button"
                  onClick={() => setShowHfToken(!showHfToken)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showHfToken ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {t('settings.tokens.huggingfaceLink').split('huggingface.co')[0]}<a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener" className="text-indigo-400 hover:underline">huggingface.co/settings/tokens</a>
              </p>
            </div>
          </div>
        </Card>

        {/* 6. AI Services Settings */}
        <AIServicesSettings ref={aiSettingsRef} />

        {/* 7. Diagnostics */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>
                <Settings className="w-5 h-5 inline-block mr-2 text-indigo-400" />
                {t('settings.diagnostics.title')}
              </CardTitle>
              <CardDescription>{t('settings.diagnostics.subtitle')}</CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<RefreshCw className="w-4 h-4" />}
              onClick={() => runDiagnostics()}
              isLoading={isRunningDiagnostics}
            >
              {t('settings.diagnostics.run')}
            </Button>
          </div>

          {diagnostics && (
            <div className="mt-4 space-y-3">
              {/* ComfyUI status */}
              <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
                <span className="text-slate-400">{t('settings.diagnostics.comfyui')}</span>
                <span className={`flex items-center gap-2 text-sm ${diagnostics.comfyui_found ? 'text-green-400' : 'text-red-400'}`}>
                  {diagnostics.comfyui_found ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      {t('settings.diagnostics.found')}
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4" />
                      {t('settings.diagnostics.notFound')}
                    </>
                  )}
                </span>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 bg-slate-800/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-indigo-400">
                    {diagnostics.packs_registered}
                  </p>
                  <p className="text-xs text-slate-500">{t('settings.diagnostics.packs')}</p>
                </div>
                <div className="p-3 bg-slate-800/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-400">
                    {diagnostics.packs_installed}
                  </p>
                  <p className="text-xs text-slate-500">{t('settings.diagnostics.installed')}</p>
                </div>
                <div className="p-3 bg-slate-800/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-cyan-400">
                    {diagnostics.custom_nodes_count}
                  </p>
                  <p className="text-xs text-slate-500">{t('settings.diagnostics.customNodes')}</p>
                </div>
              </div>

              {/* Issues */}
              {diagnostics.issues.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-slate-100">{t('settings.diagnostics.issues')}</h4>
                  {diagnostics.issues.map((issue, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-lg ${issue.level === 'error' || issue.level === 'critical'
                        ? 'bg-red-500/10 border border-red-500/20'
                        : 'bg-amber-500/10 border border-amber-500/20'
                        }`}
                    >
                      <p className={`text-sm ${issue.level === 'error' || issue.level === 'critical'
                        ? 'text-red-400'
                        : 'text-amber-400'
                        }`}>
                        {issue.message}
                      </p>
                      {issue.suggestion && (
                        <p className="text-xs text-slate-500 mt-1">
                          → {issue.suggestion}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Save button */}
        <div className="flex justify-end">
          <Button
            variant="primary"
            leftIcon={<Save className="w-4 h-4" />}
            onClick={handleSave}
            isLoading={updateSettingsMutation.isPending || updateBackupConfigMutation.isPending}
          >
            {t('settings.save')}
          </Button>
        </div>
      </div>
    </div>
  )
}
