import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Link as LinkIcon, FileJson, Upload, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'
import { toast } from '@/stores/toastStore'

interface ImportModalProps {
  isOpen: boolean
  onClose: () => void
}

type ImportTab = 'url' | 'workflow'

export function ImportModal({ isOpen, onClose }: ImportModalProps) {
  const [tab, setTab] = useState<ImportTab>('url')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<{
    success: boolean
    packName?: string
    errors: string[]
    warnings: string[]
  } | null>(null)
  
  const queryClient = useQueryClient()
  
  const importUrlMutation = useMutation({
    mutationFn: async (civitaiUrl: string) => {
      // v2 API: POST /api/packs/import with {url: ...}
      const res = await fetch('/api/packs/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: civitaiUrl }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Import failed')
      }
      return res.json()
    },
    onSuccess: (data) => {
      // v2 returns {pack: {...}, message: "..."}
      setResult({
        success: true,
        packName: data.pack?.name || data.name,
        errors: [],
        warnings: data.warnings || [],
      })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success(`Pack "${data.pack?.name || data.name}" imported successfully`)
    },
    onError: (err: Error) => {
      setResult({ success: false, errors: [err.message], warnings: [] })
      toast.error(`Import failed: ${err.message}`)
    },
  })

  const importFileMutation = useMutation({
    mutationFn: async (workflowFile: File) => {
      // Read file content and send as JSON
      const content = await workflowFile.text()
      let workflowJson
      try {
        workflowJson = JSON.parse(content)
      } catch {
        throw new Error('Invalid JSON file')
      }
      
      // v2 API: POST /api/packs/import with {workflow_json: ...}
      const res = await fetch('/api/packs/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow_json: workflowJson }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Import failed')
      }
      return res.json()
    },
    onSuccess: (data) => {
      setResult({
        success: true,
        packName: data.pack?.name || data.name,
        errors: [],
        warnings: data.warnings || [],
      })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      toast.success(`Pack "${data.pack?.name || data.name}" imported from workflow`)
    },
    onError: (err: Error) => {
      setResult({ success: false, errors: [err.message], warnings: [] })
      toast.error(`Import failed: ${err.message}`)
    },
  })

  const handleImport = () => {
    setResult(null)
    if (tab === 'url' && url) {
      importUrlMutation.mutate(url)
    } else if (tab === 'workflow' && file) {
      importFileMutation.mutate(file)
    }
  }
  
  const handleClose = () => {
    setUrl('')
    setFile(null)
    setResult(null)
    onClose()
  }
  
  const isLoading = importUrlMutation.isPending || importFileMutation.isPending
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-obsidian/80 backdrop-blur-sm"
        onClick={handleClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-lg bg-slate-deep border border-slate-mid/50 rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-mid/50">
          <h2 className="text-lg font-semibold text-text-primary">Import Pack</h2>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-slate-mid/50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Tabs */}
        <div className="flex border-b border-slate-mid/50">
          <button
            onClick={() => setTab('url')}
            className={clsx(
              'flex-1 px-4 py-3 text-sm font-medium transition-colors',
              tab === 'url'
                ? 'text-synapse border-b-2 border-synapse'
                : 'text-text-secondary hover:text-text-primary'
            )}
          >
            <LinkIcon className="w-4 h-4 inline-block mr-2" />
            Civitai URL
          </button>
          <button
            onClick={() => setTab('workflow')}
            className={clsx(
              'flex-1 px-4 py-3 text-sm font-medium transition-colors',
              tab === 'workflow'
                ? 'text-synapse border-b-2 border-synapse'
                : 'text-text-secondary hover:text-text-primary'
            )}
          >
            <FileJson className="w-4 h-4 inline-block mr-2" />
            Workflow JSON
          </button>
        </div>
        
        {/* Content */}
        <div className="p-4 space-y-4">
          {tab === 'url' && (
            <div>
              <label className="block text-sm text-text-secondary mb-2">
                Civitai Model URL
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://civitai.com/models/..."
                className="w-full px-4 py-2.5 bg-slate-mid/50 border border-slate-mid rounded-xl text-text-primary placeholder:text-text-muted focus:outline-none focus:border-synapse/50"
              />
              <p className="text-xs text-text-muted mt-2">
                Paste a Civitai model URL to import the model with metadata and previews
              </p>
            </div>
          )}
          
          {tab === 'workflow' && (
            <div>
              <label className="block text-sm text-text-secondary mb-2">
                Workflow File
              </label>
              <div
                className={clsx(
                  'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors',
                  file
                    ? 'border-synapse/50 bg-synapse/5'
                    : 'border-slate-mid hover:border-synapse/30'
                )}
                onClick={() => document.getElementById('workflow-input')?.click()}
              >
                <input
                  id="workflow-input"
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                {file ? (
                  <div className="flex items-center justify-center gap-2 text-synapse">
                    <FileJson className="w-5 h-5" />
                    <span>{file.name}</span>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 text-text-muted mx-auto mb-2" />
                    <p className="text-text-secondary">
                      Click to select or drag & drop
                    </p>
                    <p className="text-xs text-text-muted mt-1">
                      ComfyUI workflow JSON file
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
          
          {/* Result */}
          {result && (
            <div className={clsx(
              'p-4 rounded-xl',
              result.success
                ? 'bg-success/10 border border-success/20'
                : 'bg-error/10 border border-error/20'
            )}>
              <div className="flex items-start gap-2">
                {result.success ? (
                  <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-error flex-shrink-0" />
                )}
                <div>
                  {result.success ? (
                    <p className="text-success font-medium">
                      Pack "{result.packName}" imported successfully!
                    </p>
                  ) : (
                    <>
                      <p className="text-error font-medium">Import failed</p>
                      {result.errors.map((err, i) => (
                        <p key={i} className="text-sm text-error/80 mt-1">{err}</p>
                      ))}
                    </>
                  )}
                  {result.warnings.map((warn, i) => (
                    <p key={i} className="text-sm text-warning mt-1">⚠ {warn}</p>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t border-slate-mid/50">
          <Button variant="ghost" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleImport}
            isLoading={isLoading}
            disabled={
              (tab === 'url' && !url) ||
              (tab === 'workflow' && !file)
            }
          >
            Import
          </Button>
        </div>
      </div>
    </div>
  )
}
