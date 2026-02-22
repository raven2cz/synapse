/**
 * Import Wizard Modal Component
 * 
 * A sophisticated multi-step modal for importing Civitai models into Synapse packs.
 * Features include:
 * - Multi-version selection with visual cards
 * - Preview thumbnail selection grid
 * - Configurable download options (images, videos, NSFW)
 * - Real-time summary with file sizes
 * - Professional glass morphism design with smooth animations
 * 
 * @module components/ui/ImportWizardModal
 * @version 2.6.0
 * @author Synapse Team
 */

import React, { useState, useCallback, useEffect, useMemo, memo } from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'
import {
    X,
    Download,
    Image as ImageIcon,
    Video,
    Eye,
    EyeOff,
    Check,
    ChevronDown,
    ChevronUp,
    Loader2,
    Package,
    HardDrive,
    FileImage,
    Film,
    AlertTriangle,
    Info,
    Sparkles,
    Pencil,
    RefreshCw,
} from 'lucide-react'
import { clsx } from 'clsx'
import { MediaPreview } from './MediaPreview'

// =============================================================================
// Types & Interfaces
// =============================================================================

/** Model version information from Civitai API */
export interface ModelVersion {
    /** Unique version identifier */
    id: number
    /** Version name/label */
    name: string
    /** Base model architecture (SD 1.5, SDXL, Pony, etc.) */
    baseModel?: string
    /** Total download count */
    downloadCount?: number
    /** Creation/publish date */
    createdAt?: string
    /** Files available for download */
    files: VersionFile[]
    /** Preview images/videos */
    images: VersionPreview[]
}

/** File information for a model version */
export interface VersionFile {
    /** Unique file identifier */
    id: number
    /** File name */
    name: string
    /** File size in bytes */
    sizeKB?: number
    /** File type (Model, VAE, Config, etc.) */
    type?: string
    /** Primary file flag */
    primary?: boolean
}

/** Preview media for a model version */
export interface VersionPreview {
    /** Preview URL */
    url: string
    /** NSFW flag */
    nsfw?: boolean
    /** NSFW level (1=safe, 2+=mature) */
    nsfwLevel?: number
    /** Width in pixels */
    width?: number
    /** Height in pixels */
    height?: number
    /** Media type */
    type?: 'image' | 'video'
    /** Generation metadata */
    meta?: Record<string, any>
}

/** Import options configuration */
export interface ImportOptions {
    /** Download preview images */
    downloadImages: boolean
    /** Download preview videos */
    downloadVideos: boolean
    /** Include NSFW content */
    includeNsfw: boolean
    /** Download previews from all versions, not just selected ones */
    downloadFromAllVersions: boolean
}

/** Props for ImportWizardModal */
export interface ImportWizardModalProps {
    /** Whether modal is open */
    isOpen: boolean
    /** Close modal callback */
    onClose: () => void
    /** Confirm import callback with selected versions, options, and custom pack name */
    onImport: (
        selectedVersionIds: number[],
        options: ImportOptions,
        thumbnailUrl?: string,
        customPackName?: string
    ) => Promise<void>
    /** Model name for display */
    modelName: string
    /** Model description for display */
    modelDescription?: string
    /** Available versions to choose from */
    versions: ModelVersion[]
    /** Whether import is in progress */
    isLoading?: boolean
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Formats file size in human-readable format.
 * @param sizeKB - Size in kilobytes
 * @returns Formatted size string
 */
function formatFileSize(sizeKB?: number): string {
    if (!sizeKB) return 'Unknown'
    if (sizeKB < 1024) return `${sizeKB.toFixed(0)} KB`
    if (sizeKB < 1024 * 1024) return `${(sizeKB / 1024).toFixed(1)} MB`
    return `${(sizeKB / (1024 * 1024)).toFixed(2)} GB`
}

/**
 * Formats large numbers with K/M suffix.
 * @param num - Number to format
 * @returns Formatted number string
 */
function formatNumber(num?: number): string {
    if (!num) return '0'
    if (num < 1000) return num.toString()
    if (num < 1000000) return `${(num / 1000).toFixed(1)}K`
    return `${(num / 1000000).toFixed(1)}M`
}

/**
 * Calculates total size of selected versions.
 * @param versions - Array of model versions
 * @param selectedIds - Set of selected version IDs
 * @returns Total size in KB
 */
function getTotalSize(versions: ModelVersion[], selectedIds: Set<number>): number {
    return versions
        .filter(v => selectedIds.has(v.id))
        .reduce((total, v) => {
            const primaryFile = v.files.find(f => f.primary) || v.files[0]
            return total + (primaryFile?.sizeKB || 0)
        }, 0)
}

/**
 * Collects all unique previews from selected versions.
 * Deduplicates by URL and limits to maxPreviews.
 * @param versions - Array of model versions
 * @param selectedIds - Set of selected version IDs
 * @param maxPreviews - Maximum number of previews to return
 * @returns Array of unique preview objects
 */
function collectPreviews(
    versions: ModelVersion[],
    selectedIds: Set<number>,
    maxPreviews: number = 16
): VersionPreview[] {
    const seenUrls = new Set<string>()
    const previews: VersionPreview[] = []

    for (const version of versions) {
        if (!selectedIds.has(version.id)) continue

        for (const preview of version.images || []) {
            if (seenUrls.has(preview.url)) continue
            seenUrls.add(preview.url)
            previews.push(preview)

            if (previews.length >= maxPreviews) break
        }

        if (previews.length >= maxPreviews) break
    }

    return previews
}

/**
 * Collects all unique previews from ALL versions.
 * Deduplicates by URL.
 * @param versions - Array of model versions
 * @returns Array of unique preview objects
 */
function collectAllPreviews(versions: ModelVersion[]): VersionPreview[] {
    const seenUrls = new Set<string>()
    const previews: VersionPreview[] = []

    for (const version of versions) {
        for (const preview of version.images || []) {
            if (seenUrls.has(preview.url)) continue
            seenUrls.add(preview.url)
            previews.push(preview)
        }
    }

    return previews
}

/**
 * Generates static thumbnail URL from Civitai video/image URL.
 * @param url - Original URL
 * @returns Static thumbnail URL
 */
function getCivitaiThumbnailUrl(url: string): string {
    if (!url || url.includes('/api/browse/image-proxy') || !url.includes('civitai.com')) return url
    const separator = url.includes('?') ? '&' : '?'
    return `${url}${separator}anim=false`
}

/**
 * Determines if a preview is NSFW based on flags.
 * @param preview - Preview object
 * @returns True if NSFW
 */
function isPreviewNsfw(preview: VersionPreview): boolean {
    return preview.nsfw === true || (preview.nsfwLevel || 1) >= 4
}

// =============================================================================
// Sub-Components
// =============================================================================

/** Version card for selection grid */
const VersionCard = memo<{
    version: ModelVersion
    isSelected: boolean
    onToggle: () => void
}>(function VersionCard({ version, isSelected, onToggle }) {
    const primaryFile = version.files.find(f => f.primary) || version.files[0]
    const imageCount = version.images?.filter(i => i.type !== 'video').length || 0
    const videoCount = version.images?.filter(i => i.type === 'video').length || 0

    return (
        <button
            onClick={onToggle}
            className={clsx(
                'relative p-4 rounded-xl border-2 text-left transition-all duration-200',
                'hover:bg-white/5 hover:scale-[1.02]',
                isSelected
                    ? 'border-synapse bg-synapse/10'
                    : 'border-slate-mid/50 bg-slate-dark/50'
            )}
        >
            {/* Selection indicator */}
            <div className={clsx(
                'absolute top-3 right-3 w-6 h-6 rounded-full border-2 flex items-center justify-center',
                'transition-all duration-200',
                isSelected
                    ? 'bg-synapse border-synapse'
                    : 'border-slate-mid/70 bg-transparent'
            )}>
                {isSelected && <Check className="w-4 h-4 text-white" />}
            </div>

            {/* Version info */}
            <div className="pr-8">
                <h4 className="font-semibold text-text-primary truncate">
                    {version.name}
                </h4>

                {version.baseModel && (
                    <span className="inline-block mt-1 px-2 py-0.5 bg-pulse/20 text-pulse text-xs rounded-full">
                        {version.baseModel}
                    </span>
                )}

                <div className="mt-3 space-y-1.5 text-sm text-text-muted">
                    {/* File size */}
                    <div className="flex items-center gap-2">
                        <HardDrive className="w-4 h-4 text-text-muted/70" />
                        <span>{formatFileSize(primaryFile?.sizeKB)}</span>
                    </div>

                    {/* Downloads */}
                    {version.downloadCount && (
                        <div className="flex items-center gap-2">
                            <Download className="w-4 h-4 text-text-muted/70" />
                            <span>{formatNumber(version.downloadCount)} downloads</span>
                        </div>
                    )}

                    {/* Preview counts */}
                    <div className="flex items-center gap-3">
                        {imageCount > 0 && (
                            <div className="flex items-center gap-1">
                                <FileImage className="w-4 h-4 text-blue-400" />
                                <span>{imageCount}</span>
                            </div>
                        )}
                        {videoCount > 0 && (
                            <div className="flex items-center gap-1">
                                <Film className="w-4 h-4 text-purple-400" />
                                <span>{videoCount}</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </button>
    )
})

/** Collapsible section wrapper */
const CollapsibleSection = memo<{
    title: string
    icon: React.ReactNode
    isOpen: boolean
    onToggle: () => void
    badge?: string | number
    children: React.ReactNode
}>(function CollapsibleSection({ title, icon, isOpen, onToggle, badge, children }) {
    return (
        <div className="border border-slate-mid/50 rounded-xl overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <span className="text-synapse">{icon}</span>
                    <span className="font-medium text-text-primary">{title}</span>
                    {badge !== undefined && (
                        <span className="px-2 py-0.5 bg-synapse/20 text-synapse text-xs rounded-full">
                            {badge}
                        </span>
                    )}
                </div>
                {isOpen ? (
                    <ChevronUp className="w-5 h-5 text-text-muted" />
                ) : (
                    <ChevronDown className="w-5 h-5 text-text-muted" />
                )}
            </button>

            {isOpen && (
                <div className="px-4 pb-4 border-t border-slate-mid/30">
                    <div className="pt-4">{children}</div>
                </div>
            )}
        </div>
    )
})

// =============================================================================
// Main Component
// =============================================================================

/**
 * Import Wizard Modal - Multi-step modal for importing Civitai models.
 * 
 * Provides version selection, import options configuration, and
 * thumbnail selection with real-time summary display.
 */
export const ImportWizardModal = memo<ImportWizardModalProps>(function ImportWizardModal({
    isOpen,
    onClose,
    onImport,
    modelName,
    modelDescription,
    versions,
    isLoading = false,
}) {
    const { t } = useTranslation()

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    const [selectedVersionIds, setSelectedVersionIds] = useState<Set<number>>(
        () => new Set(versions.slice(0, 1).map(v => v.id))
    )

    const [options, setOptions] = useState<ImportOptions>({
        downloadImages: true,
        downloadVideos: true,
        includeNsfw: true,
        downloadFromAllVersions: true,
    })

    const [selectedThumbnail, setSelectedThumbnail] = useState<string | undefined>()

    // Pack name editing
    const [packName, setPackName] = useState(modelName)
    const [isEditingName, setIsEditingName] = useState(false)

    const [sectionsOpen, setSectionsOpen] = useState({
        packDetails: true,
        versions: true,
        options: true,
        thumbnail: false,
    })

    // -------------------------------------------------------------------------
    // Computed Values
    // -------------------------------------------------------------------------

    const totalSize = useMemo(
        () => getTotalSize(versions, selectedVersionIds),
        [versions, selectedVersionIds]
    )

    // Previews from selected versions only (for thumbnail selection)
    const selectedVersionPreviews = useMemo(
        () => collectPreviews(versions, selectedVersionIds, 16),
        [versions, selectedVersionIds]
    )

    // All previews from all versions
    const allVersionPreviews = useMemo(
        () => collectAllPreviews(versions),
        [versions]
    )

    const safePreviews = useMemo(
        () => selectedVersionPreviews.filter(p => !isPreviewNsfw(p)),
        [selectedVersionPreviews]
    )

    // Calculate preview counts based on selected options
    // This now correctly reflects what WILL be downloaded
    const previewStats = useMemo(() => {
        let imageCount = 0
        let videoCount = 0
        let estimatedSize = 0

        // Use the previews that will actually be downloaded
        const previewsToCount = options.downloadFromAllVersions
            ? allVersionPreviews
            : selectedVersionPreviews

        for (const preview of previewsToCount) {
            const isNsfw = isPreviewNsfw(preview)
            if (isNsfw && !options.includeNsfw) continue

            const isVideo = preview.type === 'video'

            if (isVideo) {
                if (options.downloadVideos) {
                    videoCount++
                    // Estimate ~10MB per video
                    estimatedSize += 10 * 1024
                }
            } else {
                if (options.downloadImages) {
                    imageCount++
                    // Estimate ~500KB per image
                    estimatedSize += 500
                }
            }
        }

        return { imageCount, videoCount, estimatedSize }
    }, [allVersionPreviews, selectedVersionPreviews, options])

    // -------------------------------------------------------------------------
    // Effects
    // -------------------------------------------------------------------------

    // Auto-select first safe preview as thumbnail
    useEffect(() => {
        if (!selectedThumbnail && safePreviews.length > 0) {
            setSelectedThumbnail(safePreviews[0].url)
        }
    }, [safePreviews, selectedThumbnail])

    // Handle escape key
    useEffect(() => {
        if (!isOpen) return

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && !isLoading) {
                onClose()
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, isLoading, onClose])

    // -------------------------------------------------------------------------
    // Handlers
    // -------------------------------------------------------------------------

    const toggleVersion = useCallback((versionId: number) => {
        setSelectedVersionIds(prev => {
            const next = new Set(prev)
            if (next.has(versionId)) {
                next.delete(versionId)
            } else {
                next.add(versionId)
            }
            return next
        })
    }, [])

    const toggleAllVersions = useCallback(() => {
        setSelectedVersionIds(prev => {
            if (prev.size === versions.length) {
                return new Set()
            }
            return new Set(versions.map(v => v.id))
        })
    }, [versions])

    const toggleSection = useCallback((section: keyof typeof sectionsOpen) => {
        setSectionsOpen(prev => ({
            ...prev,
            [section]: !prev[section],
        }))
    }, [])

    const handleImport = useCallback(async () => {
        if (selectedVersionIds.size === 0) return

        // Pass custom pack name if it differs from original
        const customName = packName !== modelName ? packName : undefined

        await onImport(
            Array.from(selectedVersionIds),
            options,
            selectedThumbnail,
            customName
        )
    }, [selectedVersionIds, options, selectedThumbnail, onImport, packName, modelName])

    // -------------------------------------------------------------------------
    // Render
    // -------------------------------------------------------------------------

    if (!isOpen) return null

    const modalContent = (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                onClick={!isLoading ? onClose : undefined}
            />

            {/* Modal */}
            <div className={clsx(
                'relative w-full max-w-3xl max-h-[90vh] m-4',
                'bg-slate-dark/95 backdrop-blur-xl',
                'border border-slate-mid/50 rounded-2xl shadow-2xl',
                'flex flex-col overflow-hidden',
                'animate-in fade-in zoom-in-95 duration-200'
            )}>
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-slate-mid/30">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-synapse/20 rounded-xl">
                            <Package className="w-6 h-6 text-synapse" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-text-primary">
                                {t('import.title')}
                            </h2>
                            <p className="text-sm text-text-muted truncate max-w-md">
                                {modelName}
                            </p>
                        </div>
                    </div>

                    <button
                        onClick={onClose}
                        disabled={isLoading}
                        className={clsx(
                            'p-2 rounded-xl transition-colors',
                            'hover:bg-white/10',
                            isLoading && 'opacity-50 cursor-not-allowed'
                        )}
                    >
                        <X className="w-6 h-6 text-text-muted" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    {/* Pack Details Section */}
                    <CollapsibleSection
                        title={t('import.packDetails')}
                        icon={<Package className="w-5 h-5" />}
                        isOpen={sectionsOpen.packDetails}
                        onToggle={() => toggleSection('packDetails')}
                    >
                        <div className="space-y-4">
                            {/* Editable Pack Name */}
                            <div>
                                <label className="text-sm text-text-muted mb-2 block">{t('import.packName')}</label>
                                <div className="flex items-center gap-2">
                                    {isEditingName ? (
                                        <input
                                            type="text"
                                            value={packName}
                                            onChange={(e) => setPackName(e.target.value)}
                                            onBlur={() => setIsEditingName(false)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') setIsEditingName(false)
                                                if (e.key === 'Escape') {
                                                    setPackName(modelName)
                                                    setIsEditingName(false)
                                                }
                                            }}
                                            autoFocus
                                            className={clsx(
                                                'flex-1 px-4 py-2 rounded-xl',
                                                'bg-slate-mid/50 border border-synapse',
                                                'text-text-primary font-medium',
                                                'focus:outline-none focus:ring-2 focus:ring-synapse/50'
                                            )}
                                        />
                                    ) : (
                                        <>
                                            <span className="flex-1 px-4 py-2 rounded-xl bg-white/5 text-text-primary font-medium truncate">
                                                {packName}
                                            </span>
                                            <button
                                                onClick={() => setIsEditingName(true)}
                                                className="p-2 rounded-lg hover:bg-white/10 text-text-muted hover:text-synapse transition-colors"
                                                title={t('importModal.editPackName')}
                                            >
                                                <Pencil className="w-4 h-4" />
                                            </button>
                                        </>
                                    )}
                                </div>
                                {packName !== modelName && (
                                    <p className="text-xs text-synapse mt-1 flex items-center gap-1">
                                        <Info className="w-3 h-3" />
                                        {t('import.customNameHint')}
                                    </p>
                                )}
                            </div>

                            {/* Description */}
                            {modelDescription && (
                                <div>
                                    <label className="text-sm text-text-muted mb-2 block">{t('import.description')}</label>
                                    <div
                                        className="px-4 py-3 rounded-xl bg-white/5 text-text-muted text-sm max-h-24 overflow-y-auto"
                                        dangerouslySetInnerHTML={{
                                            __html: modelDescription.length > 300
                                                ? modelDescription.substring(0, 300) + '...'
                                                : modelDescription
                                        }}
                                    />
                                </div>
                            )}
                        </div>
                    </CollapsibleSection>

                    {/* Version Selection */}
                    <CollapsibleSection
                        title={t('import.selectVersions')}
                        icon={<Sparkles className="w-5 h-5" />}
                        isOpen={sectionsOpen.versions}
                        onToggle={() => toggleSection('versions')}
                        badge={`${selectedVersionIds.size}/${versions.length}`}
                    >
                        {/* Select all toggle */}
                        <div className="flex justify-end mb-3">
                            <button
                                onClick={toggleAllVersions}
                                className="text-sm text-synapse hover:underline"
                            >
                                {selectedVersionIds.size === versions.length ? t('import.deselectAll') : t('import.selectAll')}
                            </button>
                        </div>

                        {/* Version grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {versions.map(version => (
                                <VersionCard
                                    key={version.id}
                                    version={version}
                                    isSelected={selectedVersionIds.has(version.id)}
                                    onToggle={() => toggleVersion(version.id)}
                                />
                            ))}
                        </div>
                    </CollapsibleSection>

                    {/* Import Options */}
                    <CollapsibleSection
                        title={t('import.downloadOptions')}
                        icon={<Download className="w-5 h-5" />}
                        isOpen={sectionsOpen.options}
                        onToggle={() => toggleSection('options')}
                    >
                        <div className="space-y-3">
                            {/* Download Images */}
                            <label className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                                <input
                                    type="checkbox"
                                    checked={options.downloadImages}
                                    onChange={e => setOptions(prev => ({
                                        ...prev,
                                        downloadImages: e.target.checked
                                    }))}
                                    className="w-5 h-5 rounded accent-synapse"
                                />
                                <ImageIcon className="w-5 h-5 text-blue-400" />
                                <div className="flex-1">
                                    <span className="font-medium text-text-primary">{t('import.downloadImages')}</span>
                                    <p className="text-sm text-text-muted">{t('import.downloadImagesDesc')}</p>
                                </div>
                            </label>

                            {/* Download Videos */}
                            <label className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                                <input
                                    type="checkbox"
                                    checked={options.downloadVideos}
                                    onChange={e => setOptions(prev => ({
                                        ...prev,
                                        downloadVideos: e.target.checked
                                    }))}
                                    className="w-5 h-5 rounded accent-synapse"
                                />
                                <Video className="w-5 h-5 text-purple-400" />
                                <div className="flex-1">
                                    <span className="font-medium text-text-primary">{t('import.downloadVideos')}</span>
                                    <p className="text-sm text-text-muted">{t('import.downloadVideosDesc')}</p>
                                </div>
                            </label>

                            {/* Include NSFW */}
                            <label className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                                <input
                                    type="checkbox"
                                    checked={options.includeNsfw}
                                    onChange={e => setOptions(prev => ({
                                        ...prev,
                                        includeNsfw: e.target.checked
                                    }))}
                                    className="w-5 h-5 rounded accent-synapse"
                                />
                                {options.includeNsfw ? (
                                    <Eye className="w-5 h-5 text-rose-400" />
                                ) : (
                                    <EyeOff className="w-5 h-5 text-text-muted" />
                                )}
                                <div className="flex-1">
                                    <span className="font-medium text-text-primary">{t('import.includeNsfw')}</span>
                                    <p className="text-sm text-text-muted">{t('import.includeNsfwDesc')}</p>
                                </div>
                            </label>

                            {/* Download from all versions */}
                            <label className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                                <input
                                    type="checkbox"
                                    checked={options.downloadFromAllVersions}
                                    onChange={e => setOptions(prev => ({
                                        ...prev,
                                        downloadFromAllVersions: e.target.checked
                                    }))}
                                    className="w-5 h-5 rounded accent-synapse"
                                />
                                <Sparkles className="w-5 h-5 text-amber-400" />
                                <div className="flex-1">
                                    <span className="font-medium text-text-primary">{t('import.downloadAllVersions')}</span>
                                    <p className="text-sm text-text-muted">
                                        {options.downloadFromAllVersions
                                            ? t('import.downloadAllVersionsDesc', { count: versions.length })
                                            : t('import.downloadSelectedVersionsDesc', { count: selectedVersionIds.size })}
                                    </p>
                                </div>
                            </label>
                        </div>

                        {/* Dependencies Preview - shows what will be downloaded */}
                        <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-synapse/10 to-pulse/10 border border-synapse/30">
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="font-medium text-text-primary flex items-center gap-2">
                                    <Info className="w-4 h-4 text-synapse" />
                                    {t('import.downloadSummary')}
                                </h4>
                                <button
                                    onClick={() => {
                                        // Refresh - recalculate (already reactive via useMemo)
                                    }}
                                    className="p-1.5 rounded-lg hover:bg-white/10 text-text-muted hover:text-synapse transition-colors"
                                    title={t('importModal.refreshPreview')}
                                >
                                    <RefreshCw className="w-4 h-4" />
                                </button>
                            </div>

                            <div className="grid grid-cols-3 gap-4 text-center">
                                {/* Total Size */}
                                <div className="p-3 rounded-lg bg-white/5">
                                    <HardDrive className="w-5 h-5 mx-auto mb-1 text-text-muted" />
                                    <div className="text-lg font-bold text-text-primary">
                                        {formatFileSize(totalSize + previewStats.estimatedSize)}
                                    </div>
                                    <div className="text-xs text-text-muted">{t('import.estimatedTotal')}</div>
                                </div>

                                {/* Images */}
                                <div className="p-3 rounded-lg bg-white/5">
                                    <FileImage className="w-5 h-5 mx-auto mb-1 text-blue-400" />
                                    <div className="text-lg font-bold text-text-primary">
                                        {previewStats.imageCount}
                                    </div>
                                    <div className="text-xs text-text-muted">{t('import.images')}</div>
                                </div>

                                {/* Videos */}
                                <div className="p-3 rounded-lg bg-white/5">
                                    <Film className="w-5 h-5 mx-auto mb-1 text-purple-400" />
                                    <div className="text-lg font-bold text-text-primary">
                                        {previewStats.videoCount}
                                    </div>
                                    <div className="text-xs text-text-muted">{t('import.videos')}</div>
                                </div>
                            </div>

                            {previewStats.imageCount === 0 && previewStats.videoCount === 0 && (
                                <p className="text-sm text-amber-400 mt-3 flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4" />
                                    {t('import.noPreviewsWarning')}
                                </p>
                            )}
                        </div>
                    </CollapsibleSection>

                    {/* Thumbnail Selection */}
                    {selectedVersionPreviews.length > 0 && (
                        <CollapsibleSection
                            title={t('import.packThumbnail')}
                            icon={<FileImage className="w-5 h-5" />}
                            isOpen={sectionsOpen.thumbnail}
                            onToggle={() => toggleSection('thumbnail')}
                        >
                            <p className="text-sm text-text-muted mb-3">
                                {t('import.selectThumbnail')}
                            </p>

                            <div className="grid grid-cols-4 gap-2">
                                {selectedVersionPreviews.map((preview) => {
                                    const isNsfw = isPreviewNsfw(preview)
                                    const isSelected = selectedThumbnail === preview.url

                                    return (
                                        <button
                                            key={preview.url}
                                            onClick={() => setSelectedThumbnail(preview.url)}
                                            className={clsx(
                                                'relative aspect-[3/4] rounded-lg overflow-hidden',
                                                'border-2 transition-all duration-200',
                                                'hover:scale-105',
                                                isSelected
                                                    ? 'border-synapse ring-2 ring-synapse/50'
                                                    : 'border-transparent hover:border-slate-mid'
                                            )}
                                        >
                                            <MediaPreview
                                                src={preview.url}
                                                type={preview.type || 'image'}
                                                thumbnailSrc={getCivitaiThumbnailUrl(preview.url)}
                                                nsfw={isNsfw}
                                                aspectRatio="portrait"
                                                className="w-full h-full"
                                                autoPlay={false}
                                            />

                                            {/* Selected indicator */}
                                            {isSelected && (
                                                <div className="absolute inset-0 bg-synapse/20 flex items-center justify-center">
                                                    <div className="p-2 bg-synapse rounded-full">
                                                        <Check className="w-4 h-4 text-white" />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Video badge */}
                                            {preview.type === 'video' && (
                                                <div className="absolute top-1 right-1 p-1 bg-black/70 rounded">
                                                    <Film className="w-3 h-3 text-purple-400" />
                                                </div>
                                            )}

                                            {/* NSFW badge */}
                                            {isNsfw && (
                                                <div className="absolute top-1 left-1 px-1.5 py-0.5 bg-rose-500/90 rounded text-[10px] text-white font-bold">
                                                    18+
                                                </div>
                                            )}
                                        </button>
                                    )
                                })}
                            </div>
                        </CollapsibleSection>
                    )}
                </div>

                {/* Footer with Summary */}
                <div className="p-6 border-t border-slate-mid/30 bg-slate-dark/50">
                    {/* Summary */}
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-6 text-sm">
                            <div className="flex items-center gap-2">
                                <Package className="w-4 h-4 text-synapse" />
                                <span className="text-text-muted">
                                    {selectedVersionIds.size} version{selectedVersionIds.size !== 1 ? 's' : ''}
                                </span>
                            </div>

                            <div className="flex items-center gap-2">
                                <HardDrive className="w-4 h-4 text-text-muted" />
                                <span className="text-text-muted">{formatFileSize(totalSize)}</span>
                            </div>

                            {(previewStats.imageCount > 0 || previewStats.videoCount > 0) && (
                                <div className="flex items-center gap-2">
                                    <FileImage className="w-4 h-4 text-blue-400" />
                                    <span className="text-text-muted">
                                        {previewStats.imageCount + previewStats.videoCount} previews
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Warning if no versions selected */}
                    {selectedVersionIds.size === 0 && (
                        <div className="flex items-center gap-2 mb-4 p-3 bg-amber-500/20 border border-amber-500/50 rounded-lg text-amber-400">
                            <AlertTriangle className="w-5 h-5" />
                            <span className="text-sm">{t('import.selectVersionWarning')}</span>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-3 justify-end">
                        <button
                            onClick={onClose}
                            disabled={isLoading}
                            className={clsx(
                                'px-6 py-2.5 rounded-xl font-medium transition-colors',
                                'bg-slate-mid/50 hover:bg-slate-mid text-text-primary',
                                isLoading && 'opacity-50 cursor-not-allowed'
                            )}
                        >
                            {t('import.cancel')}
                        </button>

                        <button
                            onClick={handleImport}
                            disabled={isLoading || selectedVersionIds.size === 0}
                            className={clsx(
                                'px-6 py-2.5 rounded-xl font-medium transition-all duration-200',
                                'bg-gradient-to-r from-synapse to-pulse',
                                'hover:shadow-lg hover:shadow-synapse/25 hover:scale-105',
                                'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100',
                                'flex items-center gap-2 text-white'
                            )}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    <span>{t('import.importing')}</span>
                                </>
                            ) : (
                                <>
                                    <Download className="w-5 h-5" />
                                    <span>{t('import.importPack')}</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )

    return createPortal(modalContent, document.body)
})

export default ImportWizardModal
