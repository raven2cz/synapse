# PLAN: Fullscreen Media Viewer - Metadata Panel Redesign

**Version:** v1.0.0
**Status:** ✅ DOKONČENO
**Created:** 2026-01-30
**Completed:** 2026-01-30

---

## Problem Statement

The current metadata panel in FullscreenMediaViewer has several UX/design issues:
1. Covers top toolbar and bottom thumbnails
2. Solid opaque background doesn't fit the premium aesthetic
3. No fade in/out animation
4. Clicking outside doesn't close the panel
5. Nested objects (like `resources`) displayed as raw JSON instead of formatted fields

---

## Design Requirements

### Layout & Positioning
- [x] Panel must NOT cover top toolbar
- [x] Panel must NOT cover bottom thumbnails strip
- [x] Position: right side, between top bar and thumbnail strip
- [x] Click outside panel closes it

### Visual Design
- [x] Semi-transparent background with blur effect (glassmorphism)
- [x] Must remain readable - sufficient contrast
- [x] Smooth fade in/out animation (300ms)
- [x] Premium feel for designers

### Data Display
- [x] Use structured display like existing `GenerationDataPanel.tsx`
- [x] Parse nested objects (resources, hashes) into readable fields
- [x] Support 1-2 levels of nesting
- [x] Fallback to elegant JSON for deeply nested or unknown structures
- [x] Keep copy-to-clipboard functionality

---

## Technical Approach

### Option A: Inline Enhancement (SELECTED)
Modify the existing panel code in `FullscreenMediaViewer.tsx` directly.

**Pros:**
- No new component
- Self-contained
- Simple

**Cons:**
- Larger file

### Option B: Extract to Component
Create `FullscreenMetaPanel.tsx` component.

**Pros:**
- Cleaner separation
- Reusable

**Cons:**
- Another file to maintain

**Decision:** Option A - keep it inline but improve the code structure.

---

## Implementation Plan

### Iteration 1: Layout & Close-on-Click-Outside ✅

**Files modified:**
- `apps/web/src/components/ui/FullscreenMediaViewer.tsx`

**Tasks:**
- [x] Adjust panel position to respect top bar (64px) and bottom thumbnails (160px)
- [x] Add click handler on backdrop to close panel
- [x] Prevent event propagation from panel content

**Implementation:** Panel uses `style={{ top: '64px', bottom: '160px' }}` positioning. Invisible backdrop div added for click-outside behavior.

### Iteration 2: Glassmorphism Design ✅

**Tasks:**
- [x] Replace solid `bg-slate-900/95` with semi-transparent + blur
- [x] Use `bg-black/50 backdrop-blur-2xl`
- [x] Ensure text remains readable with proper contrast
- [x] Add subtle border for definition (`border-l border-white/10`)

### Iteration 3: Fade Animation ✅

**Tasks:**
- [x] Add opacity transition for panel show/hide
- [x] Use `animate-in slide-in-from-right-4 fade-in` Tailwind animation
- [x] Animate both opacity and slight translateX

### Iteration 4: Smart Data Rendering ✅

**Tasks:**
- [x] Extract known fields (prompt, negativePrompt, resources, etc.)
- [x] Render `resources` array as formatted cards (type badge + name)
- [x] Render `hashes` object as key-value pairs
- [x] Grid layout for simple fields (Model, Sampler, Steps, CFG, Seed, etc.)
- [x] Fallback: elegantly formatted JSON for unknown nested structures
- [x] Copy button for each field

---

## Field Mapping (from Civitai API)

| Field | Type | Display |
|-------|------|---------|
| `prompt` | string | Monospace text block with copy |
| `negativePrompt` | string | Red-tinted text block with copy |
| `resources` | array | Cards with type badge + name |
| `Model` / `model_name` | string | Grid item |
| `sampler` | string | Grid item |
| `steps` | number | Grid item |
| `cfgScale` / `cfg_scale` | number | Grid item |
| `seed` | number | Grid item |
| `clipSkip` / `clip_skip` | number | Grid item |
| `Size` / computed | string | Grid item |
| `hashes` | object | Key-value pairs |
| `*other*` | any | Fallback JSON or simple display |

---

## UI Mockup (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│  [1/10]                              [i] [↓] [⤴] [⛶] [X]  ← TOP BAR │
├─────────────────────────────────────────────────────────────────┬───┤
│                                                                 │   │
│                                                                 │ G │
│                                                                 │ e │
│                     IMAGE/VIDEO                                 │ n │
│                                                                 │   │
│                                                                 │ D │
│                                                                 │ a │
│                                                                 │ t │
│                                                                 │ a │
│  ← CLICK HERE CLOSES PANEL                                      │   │
│                                                                 │ P │
│                                                                 │ a │
│                                                                 │ n │
│                                                                 │ e │
│                                                                 │ l │
├─────────────────────────────────────────────────────────────────┴───┤
│  [1] [2] [3] [4] [5] [6] [7] [8] [9] [10]           ← THUMBNAILS    │
└─────────────────────────────────────────────────────────────────────┘
```

Panel width: ~340px (slightly narrower than current 380px)
Background: `bg-black/50 backdrop-blur-2xl`

---

## Testing

- [x] Visual test: panel doesn't overlap toolbars
- [x] Click outside closes panel
- [x] Fade animation smooth
- [x] All field types render correctly
- [x] Copy to clipboard works
- [x] Keyboard shortcut (I) still works
- [x] TypeScript type check passes
- [x] Frontend tests pass (`verify.sh --frontend`)

---

## Notes

- Keep existing `GenerationDataPanel.tsx` unchanged (used elsewhere)
- This is fullscreen-viewer-specific implementation
- Don't touch other parts of FullscreenMediaViewer (stability!)
