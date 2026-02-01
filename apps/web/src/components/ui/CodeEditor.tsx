/**
 * CodeEditor - Reusable code editor component powered by CodeMirror 6
 *
 * Features:
 * - Syntax highlighting for HTML, Markdown, JavaScript
 * - Dark theme matching Synapse design
 * - Line numbers, code folding, search (Ctrl+F)
 * - Autocompletion support
 * - Controlled component (value + onChange)
 */

import { useEffect, useRef, useCallback } from 'react'
import { clsx } from 'clsx'

// CodeMirror core
import { EditorState, Extension } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, dropCursor, rectangularSelection, crosshairCursor, highlightSpecialChars } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { indentOnInput, bracketMatching, foldGutter, foldKeymap, syntaxHighlighting, defaultHighlightStyle, HighlightStyle } from '@codemirror/language'
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search'
import { autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'

// Language support
import { html } from '@codemirror/lang-html'
import { markdown } from '@codemirror/lang-markdown'
import { javascript } from '@codemirror/lang-javascript'

// Theme
import { tags } from '@lezer/highlight'

export type CodeEditorLanguage = 'html' | 'markdown' | 'javascript' | 'json' | 'plaintext'

export interface CodeEditorProps {
  value: string
  onChange?: (value: string) => void
  language?: CodeEditorLanguage
  placeholder?: string
  readOnly?: boolean
  lineWrapping?: boolean
  minHeight?: string
  maxHeight?: string
  className?: string
  autoFocus?: boolean
}

/**
 * Custom Synapse dark theme for CodeMirror
 */
const synapseTheme = EditorView.theme({
  '&': {
    color: '#e2e8f0',
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    borderRadius: '0.75rem',
    fontSize: '14px',
    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace',
    height: '100%',
  },
  '.cm-scroller': {
    overflow: 'auto',
    fontFamily: 'inherit',
  },
  '.cm-content': {
    caretColor: '#8b5cf6',
    padding: '12px 0',
  },
  '.cm-cursor, .cm-dropCursor': {
    borderLeftColor: '#8b5cf6',
    borderLeftWidth: '2px',
  },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
    backgroundColor: 'rgba(139, 92, 246, 0.3)',
  },
  '.cm-activeLine': {
    backgroundColor: 'rgba(139, 92, 246, 0.08)',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'rgba(139, 92, 246, 0.08)',
  },
  '.cm-gutters': {
    backgroundColor: 'rgba(15, 23, 42, 0.4)',
    color: '#64748b',
    border: 'none',
    borderRight: '1px solid rgba(148, 163, 184, 0.1)',
    borderRadius: '0.75rem 0 0 0.75rem',
  },
  '.cm-lineNumbers .cm-gutterElement': {
    padding: '0 12px 0 8px',
    minWidth: '40px',
  },
  '.cm-foldPlaceholder': {
    backgroundColor: 'rgba(139, 92, 246, 0.2)',
    border: 'none',
    color: '#8b5cf6',
    borderRadius: '4px',
    padding: '0 4px',
  },
  '.cm-tooltip': {
    backgroundColor: '#1e293b',
    border: '1px solid rgba(148, 163, 184, 0.2)',
    borderRadius: '8px',
    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.5)',
  },
  '.cm-tooltip.cm-tooltip-autocomplete': {
    '& > ul': {
      fontFamily: 'inherit',
      maxHeight: '200px',
    },
    '& > ul > li': {
      padding: '4px 8px',
    },
    '& > ul > li[aria-selected]': {
      backgroundColor: 'rgba(139, 92, 246, 0.3)',
      color: '#e2e8f0',
    },
  },
  '.cm-panels': {
    backgroundColor: 'rgba(30, 41, 59, 0.95)',
    color: '#e2e8f0',
    borderTop: '1px solid rgba(148, 163, 184, 0.1)',
  },
  '.cm-panels.cm-panels-top': {
    borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
    borderTop: 'none',
  },
  '.cm-search': {
    fontSize: '14px',
  },
  '.cm-search input': {
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    border: '1px solid rgba(148, 163, 184, 0.2)',
    borderRadius: '6px',
    color: '#e2e8f0',
    padding: '4px 8px',
  },
  '.cm-search input:focus': {
    borderColor: '#8b5cf6',
    outline: 'none',
  },
  '.cm-search button': {
    backgroundColor: 'rgba(139, 92, 246, 0.2)',
    border: 'none',
    borderRadius: '6px',
    color: '#e2e8f0',
    padding: '4px 12px',
    cursor: 'pointer',
  },
  '.cm-search button:hover': {
    backgroundColor: 'rgba(139, 92, 246, 0.3)',
  },
  '.cm-selectionMatch': {
    backgroundColor: 'rgba(139, 92, 246, 0.2)',
  },
  '.cm-matchingBracket': {
    backgroundColor: 'rgba(139, 92, 246, 0.3)',
    outline: '1px solid rgba(139, 92, 246, 0.5)',
  },
  '.cm-placeholder': {
    color: '#64748b',
    fontStyle: 'italic',
  },
  // Scrollbar styling
  '.cm-scroller::-webkit-scrollbar': {
    width: '8px',
    height: '8px',
  },
  '.cm-scroller::-webkit-scrollbar-track': {
    backgroundColor: 'rgba(15, 23, 42, 0.3)',
    borderRadius: '4px',
  },
  '.cm-scroller::-webkit-scrollbar-thumb': {
    backgroundColor: 'rgba(139, 92, 246, 0.4)',
    borderRadius: '4px',
  },
  '.cm-scroller::-webkit-scrollbar-thumb:hover': {
    backgroundColor: 'rgba(139, 92, 246, 0.6)',
  },
}, { dark: true })

/**
 * Synapse syntax highlighting
 */
const synapseHighlightStyle = HighlightStyle.define([
  // Comments
  { tag: tags.comment, color: '#64748b', fontStyle: 'italic' },
  { tag: tags.lineComment, color: '#64748b', fontStyle: 'italic' },
  { tag: tags.blockComment, color: '#64748b', fontStyle: 'italic' },

  // Strings
  { tag: tags.string, color: '#34d399' },
  { tag: tags.special(tags.string), color: '#34d399' },
  { tag: tags.character, color: '#34d399' },

  // Numbers
  { tag: tags.number, color: '#f472b6' },
  { tag: tags.integer, color: '#f472b6' },
  { tag: tags.float, color: '#f472b6' },

  // Keywords
  { tag: tags.keyword, color: '#c084fc' },
  { tag: tags.controlKeyword, color: '#c084fc', fontWeight: 'bold' },
  { tag: tags.operatorKeyword, color: '#c084fc' },

  // Operators
  { tag: tags.operator, color: '#94a3b8' },
  { tag: tags.compareOperator, color: '#94a3b8' },
  { tag: tags.arithmeticOperator, color: '#94a3b8' },
  { tag: tags.logicOperator, color: '#94a3b8' },

  // Names
  { tag: tags.variableName, color: '#e2e8f0' },
  { tag: tags.propertyName, color: '#60a5fa' },
  { tag: tags.function(tags.variableName), color: '#facc15' },
  { tag: tags.definition(tags.variableName), color: '#facc15' },
  { tag: tags.className, color: '#f97316' },
  { tag: tags.typeName, color: '#2dd4bf' },

  // HTML/XML
  { tag: tags.tagName, color: '#f87171' },
  { tag: tags.attributeName, color: '#fbbf24' },
  { tag: tags.attributeValue, color: '#34d399' },
  { tag: tags.angleBracket, color: '#64748b' },

  // Markdown
  { tag: tags.heading, color: '#c084fc', fontWeight: 'bold' },
  { tag: tags.heading1, color: '#c084fc', fontWeight: 'bold', fontSize: '1.3em' },
  { tag: tags.heading2, color: '#a78bfa', fontWeight: 'bold', fontSize: '1.2em' },
  { tag: tags.heading3, color: '#8b5cf6', fontWeight: 'bold', fontSize: '1.1em' },
  { tag: tags.link, color: '#60a5fa', textDecoration: 'underline' },
  { tag: tags.url, color: '#60a5fa' },
  { tag: tags.emphasis, fontStyle: 'italic', color: '#fcd34d' },
  { tag: tags.strong, fontWeight: 'bold', color: '#fb923c' },
  { tag: tags.strikethrough, textDecoration: 'line-through', color: '#64748b' },
  { tag: tags.quote, color: '#94a3b8', fontStyle: 'italic' },
  { tag: tags.monospace, color: '#34d399', fontFamily: 'monospace' },

  // Misc
  { tag: tags.bool, color: '#f472b6' },
  { tag: tags.null, color: '#f472b6' },
  { tag: tags.self, color: '#c084fc' },
  { tag: tags.punctuation, color: '#94a3b8' },
  { tag: tags.bracket, color: '#94a3b8' },
  { tag: tags.meta, color: '#64748b' },
  { tag: tags.invalid, color: '#ef4444', textDecoration: 'underline wavy' },
])

/**
 * Get language extension based on language type
 */
function getLanguageExtension(lang: CodeEditorLanguage): Extension[] {
  switch (lang) {
    case 'html':
      return [html()]
    case 'markdown':
      return [markdown()]
    case 'javascript':
    case 'json':
      return [javascript()]
    case 'plaintext':
    default:
      return []
  }
}

/**
 * CodeEditor component
 */
export function CodeEditor({
  value,
  onChange,
  language = 'plaintext',
  placeholder,
  readOnly = false,
  lineWrapping = true,
  minHeight = '200px',
  maxHeight = '500px',
  className,
  autoFocus = false,
}: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeRef = useRef(onChange)

  // Keep onChange ref updated
  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  // Create editor
  useEffect(() => {
    if (!containerRef.current) return

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged && onChangeRef.current) {
        onChangeRef.current(update.state.doc.toString())
      }
    })

    const extensions: Extension[] = [
      // Theme
      synapseTheme,
      syntaxHighlighting(synapseHighlightStyle),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),

      // Basic features
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      highlightSpecialChars(),
      history(),
      foldGutter(),
      drawSelection(),
      dropCursor(),
      rectangularSelection(),
      crosshairCursor(),
      indentOnInput(),
      bracketMatching(),
      closeBrackets(),
      highlightSelectionMatches(),
      autocompletion(),

      // Keymaps
      keymap.of([
        ...defaultKeymap,
        ...historyKeymap,
        ...foldKeymap,
        ...searchKeymap,
        ...completionKeymap,
        ...closeBracketsKeymap,
        indentWithTab,
      ]),

      // Update listener
      updateListener,

      // Language
      ...getLanguageExtension(language),

      // Optional features
      ...(lineWrapping ? [EditorView.lineWrapping] : []),
      ...(readOnly ? [EditorState.readOnly.of(true)] : []),
      ...(placeholder ? [EditorView.contentAttributes.of({ 'aria-placeholder': placeholder })] : []),
    ]

    const state = EditorState.create({
      doc: value,
      extensions,
    })

    const view = new EditorView({
      state,
      parent: containerRef.current,
    })

    viewRef.current = view

    if (autoFocus) {
      view.focus()
    }

    return () => {
      view.destroy()
      viewRef.current = null
    }
  }, [language, readOnly, lineWrapping, placeholder, autoFocus])

  // Update value externally
  const updateValue = useCallback((newValue: string) => {
    const view = viewRef.current
    if (!view) return

    const currentValue = view.state.doc.toString()
    if (currentValue !== newValue) {
      view.dispatch({
        changes: {
          from: 0,
          to: currentValue.length,
          insert: newValue,
        },
      })
    }
  }, [])

  // Sync external value changes
  useEffect(() => {
    updateValue(value)
  }, [value, updateValue])

  // Check if we should use full height from parent
  const useFullHeight = className?.includes('h-full')

  return (
    <div
      ref={containerRef}
      className={clsx(
        'rounded-xl',
        'border border-slate-mid/30',
        'focus-within:border-synapse/50',
        'transition-colors duration-200',
        className
      )}
      style={{
        minHeight: useFullHeight ? undefined : minHeight,
        maxHeight: useFullHeight ? undefined : maxHeight,
        height: useFullHeight ? '100%' : undefined,
        overflow: 'hidden', // Container clips rounded corners, CodeMirror handles internal scroll
      }}
    />
  )
}

export default CodeEditor
