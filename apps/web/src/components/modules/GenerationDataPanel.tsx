import { Copy, Info, X, Zap, Hash, Sliders, Layers, Box, Cpu, Ruler, Activity } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'

interface GenerationDataPanelProps {
    meta: Record<string, any>
    onClose?: () => void
    className?: string
}

export function GenerationDataPanel({
    meta,
    onClose,
    className,
}: GenerationDataPanelProps) {
    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text)
        // Ideally we would show a toast here
    }

    // Extract known fields
    const prompt = meta.prompt as string
    const negativePrompt = meta.negativePrompt as string
    const resources = meta.resources as Array<{ name: string; type: string; weight?: number; hash?: string }>

    // Helper for size
    const sizeValue = meta.size
        ? undefined
        : (meta.width && meta.height ? `${meta.width}x${meta.height}` : undefined)

    // Other metadata mapping
    const otherMeta = [
        { label: 'Model', value: meta.Model || meta.model_name, icon: Box },
        { label: 'Sampler', value: meta.sampler, icon: Activity },
        { label: 'Steps', value: meta.steps, icon: Layers },
        { label: 'CFG Scale', value: meta.cfgScale || meta.cfg_scale, icon: Sliders },
        { label: 'Seed', value: meta.seed ? String(meta.seed) : undefined, icon: Hash },
        { label: 'Clip Skip', value: meta.clipSkip || meta.clip_skip, icon: Zap },
        { label: 'Size', value: sizeValue, icon: Ruler },
    ].filter(item => item.value !== undefined && item.value !== null)

    return (
        <div className={clsx("flex flex-col h-full bg-[#1a1b1e] text-text-primary overflow-hidden border-l border-white/5", className)}>
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-white/5 shrink-0 bg-[#1a1b1e]">
                <h3 className="font-bold text-lg flex items-center gap-2 text-white">
                    <Info className="w-5 h-5 text-synapse" />
                    Generation Data
                </h3>
                {onClose && (
                    <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full transition-colors text-text-muted hover:text-white">
                        <X className="w-5 h-5" />
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-5 space-y-8 custom-scrollbar bg-[#141517]">

                {/* Process / Resources Section */}
                {resources && resources.length > 0 && (
                    <section className="space-y-3">
                        <h4 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                            <Cpu className="w-3 h-3" />
                            Resources Used
                        </h4>
                        <div className="space-y-2">
                            {resources.map((res, i) => (
                                <div key={i} className="flex items-center justify-between bg-[#1a1b1e] p-3 rounded-lg border border-white/5 hover:border-white/10 transition-colors group">
                                    <div className="flex items-center gap-3 overflow-hidden">
                                        <span className={clsx(
                                            "text-[10px] px-2 py-0.5 rounded-md font-bold uppercase shrink-0 tracking-wider",
                                            res.type === 'model' ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" : "bg-synapse/10 text-synapse border border-synapse/20"
                                        )}>
                                            {res.type}
                                        </span>
                                        <span className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors" title={res.name}>
                                            {res.name}
                                        </span>
                                    </div>
                                    {res.weight && (
                                        <span className="text-xs font-mono text-text-muted bg-black/20 px-2 py-1 rounded border border-white/5">
                                            {res.weight}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Prompt Section */}
                {prompt && (
                    <section className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h4 className="text-xs font-bold text-text-muted uppercase tracking-widest">Prompt</h4>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-xs text-text-muted hover:text-white hover:bg-white/5"
                                onClick={() => copyToClipboard(prompt)}
                            >
                                <Copy className="w-3 h-3 mr-1.5" /> Copy
                            </Button>
                        </div>
                        <div className="bg-[#1a1b1e] p-4 rounded-xl text-sm leading-relaxed border border-white/5 break-words whitespace-pre-wrap font-mono text-gray-300 selection:bg-synapse/20 selection:text-synapse-light shadow-inner">
                            {prompt}
                        </div>
                    </section>
                )}

                {/* Negative Prompt Section */}
                {negativePrompt && (
                    <section className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h4 className="text-xs font-bold text-red-400/80 uppercase tracking-widest">Negative Prompt</h4>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-xs text-text-muted hover:text-red-400 hover:bg-red-500/10"
                                onClick={() => copyToClipboard(negativePrompt)}
                            >
                                <Copy className="w-3 h-3 mr-1.5" /> Copy
                            </Button>
                        </div>
                        <div className="bg-[#1a1b1e] p-4 rounded-xl text-sm leading-relaxed border border-white/5 break-words whitespace-pre-wrap font-mono text-red-200/90 selection:bg-red-500/20 selection:text-red-200 shadow-inner">
                            {negativePrompt}
                        </div>
                    </section>
                )}

                {/* Other Metadata Grid */}
                {otherMeta.length > 0 && (
                    <section className="space-y-3">
                        <h4 className="text-xs font-bold text-text-muted uppercase tracking-widest">Generation Params</h4>
                        <div className="grid grid-cols-2 gap-2">
                            {otherMeta.map((item, i) => (
                                <div key={i} className="bg-[#1a1b1e] border border-white/5 px-3 py-2 rounded-lg flex flex-col group hover:border-white/10 transition-colors">
                                    <span className="text-[10px] text-text-muted uppercase font-bold tracking-wider mb-1 flex items-center gap-1.5">
                                        <item.icon className="w-3 h-3 opacity-50" />
                                        {item.label}
                                    </span>
                                    <span className="text-sm font-mono text-gray-200 font-medium" title={String(item.value)}>
                                        {item.value}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

            </div>
        </div>
    )
}
