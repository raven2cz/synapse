# Theming

Avatar-engine's UI components use CSS custom properties for styling. Synapse provides a bridge layer that maps its own color palette to avatar-engine's variables, ensuring visual consistency.

## How It Works

The CSS loading order in `main.tsx`:

1. `@avatar-engine/react/styles.css` — Base component styles with default theme
2. `src/styles/avatar-overrides.css` — Synapse's bridge (maps Synapse colors to `--ae-*` variables)
3. Synapse's own styles — Application styles

This means avatar-engine components automatically use Synapse's exact color palette.

## Built-in Bridge Variables

Synapse maps its design tokens to avatar-engine's CSS custom properties using RGB triples (for `rgba()` compositing):

```css
:root {
  /* Accent colors */
  --ae-accent-rgb: 99 102 241;        /* Synapse indigo (#6366f1) */
  --ae-pulse-rgb: 139 92 246;         /* Purple (#8b5cf6) */
  --ae-neural-rgb: 6 182 212;         /* Cyan (#06b6d4) */

  /* Background surfaces */
  --ae-bg-obsidian-rgb: 10 10 15;
  --ae-bg-darker-rgb: 15 15 23;
  --ae-bg-deep-rgb: 18 18 26;
  --ae-bg-base-rgb: 19 19 27;
  --ae-bg-dark-rgb: 22 22 31;
  --ae-bg-mid-rgb: 26 26 46;
  --ae-bg-light-rgb: 42 42 66;

  /* Text */
  --ae-text-primary-rgb: 248 250 252;
  --ae-text-secondary-rgb: 148 163 184;
  --ae-text-muted-rgb: 100 116 139;
}
```

Source: `apps/web/src/styles/avatar-overrides.css`

## Custom Theme Override

For users who want to customize the avatar UI beyond Synapse's defaults, copy the example file:

```bash
cp config/avatar/theme-override.css.example ~/.synapse/avatar/theme-override.css
```

This file uses higher-level semantic variables:

```css
:root {
  /* Primary accent */
  --avatar-primary: #6366f1;
  --avatar-primary-hover: #4f46e5;
  --avatar-primary-light: rgba(99, 102, 241, 0.1);

  /* Backgrounds */
  --avatar-bg: #0f1729;
  --avatar-bg-secondary: #1a2332;
  --avatar-bg-input: #1e293b;
  --avatar-bg-message-user: #1e293b;
  --avatar-bg-message-ai: #0f172a;

  /* Text */
  --avatar-text-primary: #e2e8f0;
  --avatar-text-secondary: #94a3b8;
  --avatar-text-placeholder: #475569;

  /* Borders */
  --avatar-border: rgba(148, 163, 184, 0.15);
  --avatar-border-focus: rgba(99, 102, 241, 0.5);

  /* Layout */
  --avatar-radius: 0.75rem;
  --avatar-radius-lg: 1rem;
  --avatar-font-size: 0.875rem;
  --avatar-font-family: inherit;

  /* Chat layout */
  --avatar-chat-max-width: 48rem;
  --avatar-chat-gap: 1rem;
  --avatar-input-height: 2.75rem;

  /* Status colors */
  --avatar-success: #22c55e;
  --avatar-warning: #f59e0b;
  --avatar-error: #ef4444;

  /* Shadows */
  --avatar-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
  --avatar-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
}
```

## Tailwind Integration

Synapse's `tailwind.config.js` includes the avatar-engine preset:

```javascript
import avatarPreset from '@avatar-engine/react/tailwind-preset'

export default {
  presets: [avatarPreset],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './node_modules/@avatar-engine/react/dist/**/*.js',  // Scan avatar-engine classes
  ],
}
```

The preset adds avatar-specific Tailwind utilities. The `content` entry ensures Tailwind doesn't purge classes used by avatar-engine components.

## See Also

- [Architecture](architecture.md) — Frontend component structure
- [Getting Started](getting-started.md) — Initial setup
