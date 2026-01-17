import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings, Save, RefreshCw, CheckCircle2, XCircle, AlertCircle, Key, FolderOpen, Eye, EyeOff, Database, Layers, Wrench, Trash2, Zap } from 'lucide-react'
import { Card, CardTitle, CardDescription } from '../ui/Card'
import { Button } from '../ui/Button'
import { useState, useEffect } from 'react'
import { useSettingsStore } from '../../stores/settingsStore'
import { toast } from '../../stores/toastStore'

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
  const queryClient = useQueryClient()
  const { nsfwBlurEnabled, setNsfwBlur } = useSettingsStore()
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
  
  const handleSave = () => {
    const updates: any = {
      comfyui_path: comfyuiPath,
      nsfw_blur_enabled: nsfwBlurEnabled,
      // Store v2 settings
      store_root: storeRoot,
      store_ui_roots: storeUiRoots,
      store_default_ui_set: storeDefaultUiSet,
    }
    if (civitaiToken) updates.civitai_token = civitaiToken
    if (hfToken) updates.huggingface_token = hfToken
    updateSettingsMutation.mutate(updates)
  }
  
  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
        <p className="text-slate-400 mt-1">
          Configure Synapse settings and run diagnostics
        </p>
      </div>
      
      <div className="space-y-6">
        {/* Paths */}
        <Card>
          <CardTitle>
            <FolderOpen className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            Paths
          </CardTitle>
          <CardDescription>Configure ComfyUI and data paths</CardDescription>
          
          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                ComfyUI Path
              </label>
              <input
                type="text"
                value={comfyuiPath}
                onChange={(e) => setComfyuiPath(e.target.value)}
                placeholder="~/ComfyUI"
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
              />
            </div>
            
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                Synapse Data Path
              </label>
              <input
                type="text"
                value={settings?.synapse_data_path || '~/.synapse'}
                disabled
                className="w-full px-4 py-2.5 bg-slate-800/30 border border-slate-700/50 rounded-xl text-slate-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                Read-only. Packs and registry are stored here.
              </p>
            </div>
          </div>
        </Card>
        
        {/* API Tokens */}
        <Card>
          <CardTitle>
            <Key className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            API Tokens
          </CardTitle>
          <CardDescription>Configure API tokens for model downloads</CardDescription>
          
          <div className="mt-4 space-y-4">
            {/* Civitai Token */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-slate-400">Civitai API Token</label>
                <span className={`flex items-center gap-1.5 text-xs ${settings?.civitai_token_set ? 'text-green-400' : 'text-amber-400'}`}>
                  {settings?.civitai_token_set ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Configured
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3.5 h-3.5" />
                      Not set
                    </>
                  )}
                </span>
              </div>
              <div className="relative">
                <input
                  type={showCivitaiToken ? 'text' : 'password'}
                  value={civitaiToken}
                  onChange={(e) => setCivitaiToken(e.target.value)}
                  placeholder={settings?.civitai_token_set ? '••••••••••••••••' : 'Enter Civitai API token'}
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
                Get your token from <a href="https://civitai.com/user/account" target="_blank" rel="noopener" className="text-indigo-400 hover:underline">civitai.com/user/account</a>
              </p>
            </div>
            
            {/* HuggingFace Token */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-slate-400">HuggingFace Token</label>
                <span className={`flex items-center gap-1.5 text-xs ${settings?.huggingface_token_set ? 'text-green-400' : 'text-amber-400'}`}>
                  {settings?.huggingface_token_set ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Configured
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3.5 h-3.5" />
                      Not set
                    </>
                  )}
                </span>
              </div>
              <div className="relative">
                <input
                  type={showHfToken ? 'text' : 'password'}
                  value={hfToken}
                  onChange={(e) => setHfToken(e.target.value)}
                  placeholder={settings?.huggingface_token_set ? '••••••••••••••••' : 'Enter HuggingFace token'}
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
                Get your token from <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener" className="text-indigo-400 hover:underline">huggingface.co/settings/tokens</a>
              </p>
            </div>
          </div>
        </Card>
        
        {/* UI Settings */}
        <Card>
          <CardTitle>
            <Eye className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            Display
          </CardTitle>
          <CardDescription>UI preferences</CardDescription>
          
          <div className="mt-4">
            <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
              <div>
                <span className="text-slate-100">NSFW Blur</span>
                <p className="text-xs text-slate-500 mt-0.5">
                  Blur NSFW preview images by default
                </p>
              </div>
              <button
                onClick={() => setNsfwBlur(!nsfwBlurEnabled)}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  nsfwBlurEnabled ? 'bg-indigo-500' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-200 ${
                    nsfwBlurEnabled ? 'left-7' : 'left-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </Card>
        
        {/* Store v2 Configuration */}
        <Card>
          <CardTitle>
            <Database className="w-5 h-5 inline-block mr-2 text-indigo-400" />
            Store Configuration
          </CardTitle>
          <CardDescription>Configure Store v2 paths and UI targets</CardDescription>
          
          <div className="mt-4 space-y-4">
            {/* Store Root */}
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                Store Root
              </label>
              <input
                type="text"
                value={storeRoot}
                onChange={(e) => setStoreRoot(e.target.value)}
                placeholder="~/.synapse/store"
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
              />
              <p className="text-xs text-slate-500 mt-1">
                Location for pack state and blob data
              </p>
            </div>
            
            {/* Default UI Set */}
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                Default UI Set
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
                UI Installation Paths
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
                variant="primary"
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
                      toast.success('Store initialized successfully')
                      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
                    } else {
                      const err = await res.text()
                      toast.error(`Init failed: ${err}`)
                    }
                  } catch (e) {
                    console.error('Init failed:', e)
                    toast.error('Failed to initialize store')
                  }
                }}
              >
                Init Store
              </Button>
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Wrench className="w-4 h-4" />}
                onClick={async () => {
                  try {
                    const res = await fetch('/api/store/doctor', { 
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ rebuild_views: true })
                    })
                    if (res.ok) {
                      toast.success('Doctor completed successfully')
                      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
                    } else {
                      toast.error('Doctor failed')
                    }
                  } catch (e) {
                    console.error('Doctor failed:', e)
                    toast.error('Doctor failed')
                  }
                }}
              >
                Doctor
              </Button>
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Trash2 className="w-4 h-4" />}
                onClick={async () => {
                  try {
                    const res = await fetch('/api/store/clean', { 
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ tmp: true, partial: true })
                    })
                    if (res.ok) {
                      toast.success('Cleanup completed')
                    } else {
                      toast.error('Cleanup failed')
                    }
                  } catch (e) {
                    console.error('Clean failed:', e)
                    toast.error('Cleanup failed')
                  }
                }}
              >
                Clean
              </Button>
            </div>
          </div>
        </Card>
        
        {/* Diagnostics */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>
                <Settings className="w-5 h-5 inline-block mr-2 text-indigo-400" />
                Diagnostics
              </CardTitle>
              <CardDescription>System health check</CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<RefreshCw className="w-4 h-4" />}
              onClick={() => runDiagnostics()}
              isLoading={isRunningDiagnostics}
            >
              Run
            </Button>
          </div>
          
          {diagnostics && (
            <div className="mt-4 space-y-3">
              {/* ComfyUI status */}
              <div className="flex items-center justify-between p-3 bg-slate-800/30 rounded-lg">
                <span className="text-slate-400">ComfyUI</span>
                <span className={`flex items-center gap-2 text-sm ${diagnostics.comfyui_found ? 'text-green-400' : 'text-red-400'}`}>
                  {diagnostics.comfyui_found ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      Found
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4" />
                      Not found
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
                  <p className="text-xs text-slate-500">Packs</p>
                </div>
                <div className="p-3 bg-slate-800/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-400">
                    {diagnostics.packs_installed}
                  </p>
                  <p className="text-xs text-slate-500">Installed</p>
                </div>
                <div className="p-3 bg-slate-800/30 rounded-lg text-center">
                  <p className="text-2xl font-bold text-cyan-400">
                    {diagnostics.custom_nodes_count}
                  </p>
                  <p className="text-xs text-slate-500">Custom Nodes</p>
                </div>
              </div>
              
              {/* Issues */}
              {diagnostics.issues.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-slate-100">Issues</h4>
                  {diagnostics.issues.map((issue, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-lg ${
                        issue.level === 'error' || issue.level === 'critical'
                          ? 'bg-red-500/10 border border-red-500/20'
                          : 'bg-amber-500/10 border border-amber-500/20'
                      }`}
                    >
                      <p className={`text-sm ${
                        issue.level === 'error' || issue.level === 'critical'
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
            isLoading={updateSettingsMutation.isPending}
          >
            Save Settings
          </Button>
        </div>
      </div>
    </div>
  )
}
