/**
 * BreathingOrb - Premium Loading Animation
 *
 * The PREMIUM loader from ui-loading-animations.html:
 * - Dýchající gradient koule (orb-breathe animation)
 * - Glowing aura effect that expands (glow-breathe animation)
 * - 6 floating particles orbiting around (particle-float animation)
 * - Optional status text
 *
 * Use for page/section loading states. For buttons, keep using Loader2.
 */

import { clsx } from 'clsx'

interface BreathingOrbProps {
  /** Size preset: 'sm' (modal), 'md' (section), 'lg' (page) */
  size?: 'sm' | 'md' | 'lg'
  /** Optional primary text */
  text?: string
  /** Optional secondary/subtitle text */
  subtext?: string
  /** Additional className for container */
  className?: string
}

// Size presets matching the HTML reference proportions
// Base: container 100px, glow 80px, orb 40px, particle 4px
const SIZES = {
  sm: {
    container: 60,
    glow: 48,
    orb: 24,
    particle: 3,
    text: 'text-sm',
    subtext: 'text-xs',
  },
  md: {
    container: 100,
    glow: 80,
    orb: 40,
    particle: 4,
    text: 'text-base',
    subtext: 'text-sm',
  },
  lg: {
    container: 150,
    glow: 120,
    orb: 60,
    particle: 5,
    text: 'text-lg',
    subtext: 'text-sm',
  },
}

// Particle positions exactly from HTML reference
// 6 particles arranged in a circle around the orb
const PARTICLE_CONFIGS = [
  { top: '10%', left: '50%', delay: 0 },
  { top: '30%', left: '85%', delay: 0.5 },
  { top: '70%', left: '90%', delay: 1 },
  { top: '90%', left: '50%', delay: 1.5 },
  { top: '70%', left: '10%', delay: 2 },
  { top: '30%', left: '15%', delay: 2.5 },
]

export function BreathingOrb({
  size = 'md',
  text,
  subtext,
  className,
}: BreathingOrbProps) {
  const s = SIZES[size]

  return (
    <div className={clsx('flex flex-col items-center justify-center gap-4', className)}>
      {/* Orb container - breathing-orb from HTML */}
      <div
        className="relative flex items-center justify-center"
        style={{
          width: s.container,
          height: s.container,
        }}
      >
        {/* Glow effect - expands and fades */}
        <div
          className="absolute rounded-full"
          style={{
            width: s.glow,
            height: s.glow,
            background: 'radial-gradient(circle, rgba(139, 92, 246, 0.3) 0%, transparent 70%)',
            animation: 'glow-breathe 2s ease-in-out infinite',
          }}
        />

        {/* Core orb - breathes with gradient */}
        <div
          className="relative rounded-full"
          style={{
            width: s.orb,
            height: s.orb,
            background: 'linear-gradient(135deg, #8B5CF6 0%, #EC4899 50%, #06B6D4 100%)',
            animation: 'orb-breathe 2s ease-in-out infinite',
            boxShadow:
              '0 0 30px rgba(139, 92, 246, 0.4), 0 0 60px rgba(236, 72, 153, 0.2), inset 0 0 20px rgba(255, 255, 255, 0.2)',
          }}
        />

        {/* Particles wrapper - exactly like HTML .particles */}
        <div
          className="absolute"
          style={{
            width: s.container,
            height: s.container,
          }}
        >
          {/* 6 floating particles around the orb */}
          {PARTICLE_CONFIGS.map((config, i) => (
            <div
              key={i}
              className="absolute rounded-full"
              style={{
                width: s.particle,
                height: s.particle,
                top: config.top,
                left: config.left,
                background: '#A78BFA', // synapse-light color
                animation: 'particle-float 3s ease-in-out infinite',
                animationDelay: `${config.delay}s`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Text */}
      {(text || subtext) && (
        <div className="text-center space-y-1">
          {text && (
            <p className={clsx('text-text-primary font-medium', s.text)}>{text}</p>
          )}
          {subtext && (
            <p className={clsx('text-text-muted', s.subtext)}>{subtext}</p>
          )}
        </div>
      )}
    </div>
  )
}
