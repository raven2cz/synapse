/**
 * DescriptionEditorModal
 *
 * Full-featured description editor supporting both Markdown and HTML.
 *
 * Features:
 * - Auto-detect content format (HTML vs Markdown)
 * - Markdown toolbar (bold, italic, headers, lists, links, code)
 * - HTML raw editor for Civitai imports
 * - Split view: edit | preview
 * - Full-screen editing option
 */

import { useState, useMemo, useCallback } from 'react'
import {
  X,
  Loader2,
  Bold,
  Italic,
  Heading1,
  Heading2,
  List,
  ListOrdered,
  Link,
  Code,
  Quote,
  Image,
  Maximize2,
  Minimize2,
  Eye,
  Edit3,
  FileText,
  Code2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export type ContentFormat = 'markdown' | 'html'

export interface DescriptionEditorModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Initial content
   */
  content: string

  /**
   * Callback when saving
   */
  onSave: (content: string, format: ContentFormat) => void

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Whether saving is in progress
   */
  isSaving?: boolean

  /**
   * Force a specific format (otherwise auto-detect)
   */
  forcedFormat?: ContentFormat
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Detect if content is HTML or Markdown
 */
function detectFormat(content: string): ContentFormat {
  if (!content) return 'markdown'

  // Check for common HTML patterns
  const htmlPatterns = [
    /<[a-z][\s\S]*>/i,           // HTML tags
    /&[a-z]+;/i,                  // HTML entities
    /<br\s*\/?>/i,                // Line breaks
    /<p>/i,                       // Paragraphs
    /<div>/i,                     // Divs
    /<span/i,                     // Spans
    /<a\s+href/i,                 // Links
    /<img\s+src/i,                // Images
    /<h[1-6]>/i,                  // Headers
    /<ul>|<ol>/i,                 // Lists
  ]

  const isHtml = htmlPatterns.some(pattern => pattern.test(content))
  return isHtml ? 'html' : 'markdown'
}

/**
 * Simple markdown preview renderer (basic implementation)
 */
function renderMarkdownPreview(markdown: string): string {
  if (!markdown) return ''

  let html = markdown
    // Headers
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^# (.*$)/gm, '<h1>$1</h1>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.*?)__/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
    // Code blocks
    .replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Images
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" />')
    // Blockquotes
    .replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>')
    // Unordered lists
    .replace(/^\* (.*$)/gm, '<li>$1</li>')
    .replace(/^- (.*$)/gm, '<li>$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.*$)/gm, '<li>$1</li>')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br />')

  // Wrap in paragraphs
  html = '<p>' + html + '</p>'

  // Cleanup
  html = html
    .replace(/<p><h/g, '<h')
    .replace(/<\/h(\d)><\/p>/g, '</h$1>')
    .replace(/<p><pre>/g, '<pre>')
    .replace(/<\/pre><\/p>/g, '</pre>')
    .replace(/<p><blockquote>/g, '<blockquote>')
    .replace(/<\/blockquote><\/p>/g, '</blockquote>')
    .replace(/<p><li>/g, '<ul><li>')
    .replace(/<\/li><\/p>/g, '</li></ul>')
    .replace(/<\/li><br \/><li>/g, '</li><li>')
    .replace(/<p><\/p>/g, '')

  return html
}

// =============================================================================
// Markdown Toolbar
// =============================================================================

interface ToolbarButtonProps {
  icon: React.ReactNode
  title: string
  onClick: () => void
  active?: boolean
}

function ToolbarButton({ icon, title, onClick, active }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={clsx(
        'p-2 rounded-lg transition-colors',
        active
          ? 'bg-synapse/20 text-synapse'
          : 'text-text-muted hover:text-text-primary hover:bg-slate-mid/50'
      )}
    >
      {icon}
    </button>
  )
}

interface MarkdownToolbarProps {
  onInsert: (before: string, after?: string, placeholder?: string) => void
}

function MarkdownToolbar({ onInsert }: MarkdownToolbarProps) {
  return (
    <div className="flex items-center gap-1 flex-wrap">
      <ToolbarButton
        icon={<Bold className="w-4 h-4" />}
        title="Bold (Ctrl+B)"
        onClick={() => onInsert('**', '**', 'bold text')}
      />
      <ToolbarButton
        icon={<Italic className="w-4 h-4" />}
        title="Italic (Ctrl+I)"
        onClick={() => onInsert('*', '*', 'italic text')}
      />
      <div className="w-px h-6 bg-slate-mid mx-1" />
      <ToolbarButton
        icon={<Heading1 className="w-4 h-4" />}
        title="Heading 1"
        onClick={() => onInsert('# ', '', 'Heading')}
      />
      <ToolbarButton
        icon={<Heading2 className="w-4 h-4" />}
        title="Heading 2"
        onClick={() => onInsert('## ', '', 'Heading')}
      />
      <div className="w-px h-6 bg-slate-mid mx-1" />
      <ToolbarButton
        icon={<List className="w-4 h-4" />}
        title="Unordered List"
        onClick={() => onInsert('- ', '', 'list item')}
      />
      <ToolbarButton
        icon={<ListOrdered className="w-4 h-4" />}
        title="Ordered List"
        onClick={() => onInsert('1. ', '', 'list item')}
      />
      <div className="w-px h-6 bg-slate-mid mx-1" />
      <ToolbarButton
        icon={<Link className="w-4 h-4" />}
        title="Link"
        onClick={() => onInsert('[', '](url)', 'link text')}
      />
      <ToolbarButton
        icon={<Image className="w-4 h-4" />}
        title="Image"
        onClick={() => onInsert('![', '](url)', 'alt text')}
      />
      <ToolbarButton
        icon={<Code className="w-4 h-4" />}
        title="Inline Code"
        onClick={() => onInsert('`', '`', 'code')}
      />
      <ToolbarButton
        icon={<Quote className="w-4 h-4" />}
        title="Blockquote"
        onClick={() => onInsert('> ', '', 'quote')}
      />
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function DescriptionEditorModal({
  isOpen,
  content: initialContent,
  onSave,
  onClose,
  isSaving = false,
  forcedFormat,
}: DescriptionEditorModalProps) {
  const [content, setContent] = useState(initialContent)
  const [format, setFormat] = useState<ContentFormat>(
    forcedFormat || detectFormat(initialContent)
  )
  const [viewMode, setViewMode] = useState<'edit' | 'preview' | 'split'>('split')
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Detect format from content
  const detectedFormat = useMemo(() => detectFormat(content), [content])

  // Preview HTML
  const previewHtml = useMemo(() => {
    if (format === 'html') {
      return content
    }
    return renderMarkdownPreview(content)
  }, [content, format])

  // Handle toolbar insert
  const handleInsert = useCallback((before: string, after = '', placeholder = '') => {
    const textarea = document.querySelector('textarea[data-editor]') as HTMLTextAreaElement
    if (!textarea) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const selectedText = content.substring(start, end) || placeholder

    const newContent =
      content.substring(0, start) +
      before +
      selectedText +
      after +
      content.substring(end)

    setContent(newContent)

    // Restore focus and selection
    setTimeout(() => {
      textarea.focus()
      const newStart = start + before.length
      const newEnd = newStart + selectedText.length
      textarea.setSelectionRange(newStart, newEnd)
    }, 0)
  }, [content])

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey) {
      if (e.key === 'b') {
        e.preventDefault()
        handleInsert('**', '**', 'bold')
      } else if (e.key === 'i') {
        e.preventDefault()
        handleInsert('*', '*', 'italic')
      } else if (e.key === 'k') {
        e.preventDefault()
        handleInsert('[', '](url)', 'link')
      }
    }
  }

  // Handle save
  const handleSave = () => {
    onSave(content, format)
  }

  // Check for changes
  const hasChanges = content !== initialContent

  if (!isOpen) return null

  const containerClasses = isFullscreen
    ? 'fixed inset-0 bg-slate-deep z-50'
    : clsx(
        "fixed inset-0 bg-black/70 z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )

  const modalClasses = isFullscreen
    ? 'w-full h-full flex flex-col'
    : clsx(
        "bg-slate-deep rounded-2xl max-w-5xl w-full max-h-[90vh]",
        "border border-slate-mid/50",
        "shadow-2xl flex flex-col",
        ANIMATION_PRESETS.scaleIn
      )

  return (
    <div
      className={containerClasses}
      onClick={(e) => {
        if (!isFullscreen && e.target === e.currentTarget) onClose()
      }}
    >
      <div className={modalClasses} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-mid/50">
          <div className="flex items-center gap-4">
            <h3 className="text-lg font-semibold text-text-primary">
              Edit Description
            </h3>

            {/* Format toggle */}
            <div className="flex items-center gap-1 p-1 bg-slate-dark rounded-lg">
              <button
                onClick={() => setFormat('markdown')}
                className={clsx(
                  'px-3 py-1 rounded text-sm font-medium transition-colors',
                  format === 'markdown'
                    ? 'bg-synapse/20 text-synapse'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                <FileText className="w-4 h-4 inline-block mr-1" />
                Markdown
              </button>
              <button
                onClick={() => setFormat('html')}
                className={clsx(
                  'px-3 py-1 rounded text-sm font-medium transition-colors',
                  format === 'html'
                    ? 'bg-synapse/20 text-synapse'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                <Code2 className="w-4 h-4 inline-block mr-1" />
                HTML
              </button>
            </div>

            {/* Detected format indicator */}
            {detectedFormat !== format && (
              <span className="text-xs text-amber-400">
                (Detected: {detectedFormat})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* View mode toggle */}
            <div className="flex items-center gap-1 p-1 bg-slate-dark rounded-lg">
              <button
                onClick={() => setViewMode('edit')}
                className={clsx(
                  'p-1.5 rounded transition-colors',
                  viewMode === 'edit'
                    ? 'bg-synapse/20 text-synapse'
                    : 'text-text-muted hover:text-text-secondary'
                )}
                title="Edit only"
              >
                <Edit3 className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('split')}
                className={clsx(
                  'p-1.5 rounded transition-colors',
                  viewMode === 'split'
                    ? 'bg-synapse/20 text-synapse'
                    : 'text-text-muted hover:text-text-secondary'
                )}
                title="Split view"
              >
                <div className="w-4 h-4 flex">
                  <div className="w-2 h-4 border-r border-current" />
                  <div className="w-2 h-4" />
                </div>
              </button>
              <button
                onClick={() => setViewMode('preview')}
                className={clsx(
                  'p-1.5 rounded transition-colors',
                  viewMode === 'preview'
                    ? 'bg-synapse/20 text-synapse'
                    : 'text-text-muted hover:text-text-secondary'
                )}
                title="Preview only"
              >
                <Eye className="w-4 h-4" />
              </button>
            </div>

            {/* Fullscreen toggle */}
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-slate-mid transition-colors"
              title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? (
                <Minimize2 className="w-5 h-5" />
              ) : (
                <Maximize2 className="w-5 h-5" />
              )}
            </button>

            {/* Close button */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-slate-mid transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Toolbar (Markdown only) */}
        {format === 'markdown' && viewMode !== 'preview' && (
          <div className="px-4 py-2 border-b border-slate-mid/30 bg-slate-dark/50">
            <MarkdownToolbar onInsert={handleInsert} />
          </div>
        )}

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Editor */}
          {viewMode !== 'preview' && (
            <div className={clsx(
              'flex-1 flex flex-col',
              viewMode === 'split' && 'border-r border-slate-mid/50'
            )}>
              <textarea
                data-editor
                value={content}
                onChange={(e) => setContent(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={format === 'markdown' ? 'Write your description in Markdown...' : 'Write or paste HTML...'}
                className={clsx(
                  'flex-1 w-full p-4 resize-none',
                  'bg-transparent text-text-primary',
                  'placeholder:text-text-muted',
                  'focus:outline-none',
                  'font-mono text-sm'
                )}
              />
            </div>
          )}

          {/* Preview */}
          {viewMode !== 'edit' && (
            <div className={clsx(
              'flex-1 overflow-auto p-4',
              'bg-slate-dark/30'
            )}>
              <div className="text-xs text-text-muted mb-2 uppercase tracking-wider">
                Preview
              </div>
              <div
                className="prose prose-invert prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-mid/50">
          <div className="text-sm text-text-muted">
            {content.length} characters
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={!hasChanges || isSaving}
              onClick={handleSave}
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : null}
              Save Description
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DescriptionEditorModal
