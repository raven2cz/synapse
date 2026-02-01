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
import { CodeEditor } from '@/components/ui/CodeEditor'
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

/**
 * Format/prettify HTML for readability
 * Adds proper indentation and newlines
 */
function prettifyHtml(html: string): string {
  if (!html) return ''

  // Block-level elements that should start on new line
  const blockElements = [
    'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'table', 'tr', 'td', 'th', 'thead', 'tbody',
    'blockquote', 'pre', 'hr', 'br', 'section', 'article', 'header', 'footer',
    'nav', 'aside', 'main', 'figure', 'figcaption'
  ]

  let result = html
    // Remove existing whitespace between tags
    .replace(/>\s+</g, '><')
    // Trim
    .trim()

  // Add newlines before and after block elements
  blockElements.forEach(tag => {
    // Opening tags (not self-closing)
    result = result.replace(new RegExp(`<${tag}([^>]*)>`, 'gi'), `\n<${tag}$1>\n`)
    // Closing tags
    result = result.replace(new RegExp(`</${tag}>`, 'gi'), `\n</${tag}>\n`)
  })

  // Handle self-closing tags
  result = result
    .replace(/<br\s*\/?>/gi, '<br />\n')
    .replace(/<hr\s*\/?>/gi, '\n<hr />\n')
    .replace(/<img([^>]*)\/?\s*>/gi, '\n<img$1 />\n')

  // Clean up multiple newlines
  result = result
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  // Add indentation
  const lines = result.split('\n')
  let indent = 0
  const indentStr = '  '
  const formattedLines: string[] = []

  for (const line of lines) {
    const trimmedLine = line.trim()
    if (!trimmedLine) continue

    // Decrease indent for closing tags
    if (trimmedLine.match(/^<\/[^>]+>$/)) {
      indent = Math.max(0, indent - 1)
    }

    formattedLines.push(indentStr.repeat(indent) + trimmedLine)

    // Increase indent for opening tags (not self-closing, not void elements)
    if (
      trimmedLine.match(/^<[a-z][^>]*>$/i) &&
      !trimmedLine.match(/\/>$/) &&
      !trimmedLine.match(/^<(br|hr|img|input|meta|link|area|base|col|embed|param|source|track|wbr)/i)
    ) {
      indent++
    }

    // Handle tags that open and close on same line like <p>text</p>
    if (trimmedLine.match(/^<[a-z][^>]*>.*<\/[a-z]+>$/i)) {
      // Don't change indent
    }
  }

  return formattedLines.join('\n')
}

/**
 * Minify HTML (remove unnecessary whitespace)
 */
function minifyHtml(html: string): string {
  return html
    .replace(/\s+/g, ' ')
    .replace(/>\s+</g, '><')
    .replace(/\s+>/g, '>')
    .replace(/<\s+/g, '<')
    .trim()
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
// HTML Toolbar
// =============================================================================

interface HtmlToolbarProps {
  onFormat: () => void
  onMinify: () => void
}

function HtmlToolbar({ onFormat, onMinify }: HtmlToolbarProps) {
  return (
    <div className="flex items-center gap-1 flex-wrap">
      <ToolbarButton
        icon={<Code className="w-4 h-4" />}
        title="Format HTML (prettify)"
        onClick={onFormat}
      />
      <ToolbarButton
        icon={<Minimize2 className="w-4 h-4" />}
        title="Minify HTML"
        onClick={onMinify}
      />
      <div className="w-px h-6 bg-slate-mid mx-2" />
      <span className="text-xs text-text-muted">
        Format: Add indentation | Minify: Remove whitespace
      </span>
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

  // Handle toolbar insert (appends at end since CodeMirror handles cursor internally)
  const handleInsert = useCallback((before: string, after = '', placeholder = '') => {
    // With CodeMirror, we append formatting at the end
    // User can then position it as needed
    const insertion = before + placeholder + after
    setContent(prev => prev + (prev.endsWith('\n') || prev === '' ? '' : '\n') + insertion)
  }, [])

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
        "bg-slate-deep rounded-2xl w-[90vw] max-w-[1600px] h-[85vh]",
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

        {/* Toolbar */}
        {viewMode !== 'preview' && (
          <div className="px-4 py-2 border-b border-slate-mid/30 bg-slate-dark/50">
            {format === 'markdown' ? (
              <MarkdownToolbar onInsert={handleInsert} />
            ) : (
              <HtmlToolbar
                onFormat={() => setContent(prettifyHtml(content))}
                onMinify={() => setContent(minifyHtml(content))}
              />
            )}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 flex min-h-0">
          {/* Editor */}
          {viewMode !== 'preview' && (
            <div className={clsx(
              'flex-1 flex flex-col min-h-0',
              viewMode === 'split' && 'border-r border-slate-mid/50'
            )}>
              <div className="flex-1 p-2 min-h-0">
                <CodeEditor
                  value={content}
                  onChange={setContent}
                  language={format === 'markdown' ? 'markdown' : 'html'}
                  placeholder={format === 'markdown' ? 'Write your description in Markdown...' : 'Write or paste HTML...'}
                  lineWrapping={true}
                  minHeight="200px"
                  maxHeight="100%"
                  autoFocus
                  className="h-full"
                />
              </div>
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
