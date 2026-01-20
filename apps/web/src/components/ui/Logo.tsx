interface LogoProps {
  size?: number
  className?: string
}

export function Logo({ size = 36, className = '' }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="18 18 84 84"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="hex-star-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="1" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="1" />
        </linearGradient>
      </defs>
      {/* Hexagon outline */}
      <polygon
        points="60,20 85,35 85,65 60,80 35,65 35,35"
        stroke="url(#hex-star-gradient)"
        strokeWidth="3"
        fill="none"
      />
      {/* Star connections */}
      <line x1="60" y1="20" x2="60" y2="50" stroke="url(#hex-star-gradient)" strokeWidth="2.5" />
      <line x1="85" y1="35" x2="65" y2="50" stroke="url(#hex-star-gradient)" strokeWidth="2.5" />
      <line x1="85" y1="65" x2="65" y2="55" stroke="url(#hex-star-gradient)" strokeWidth="2.5" />
      <line x1="60" y1="80" x2="60" y2="55" stroke="url(#hex-star-gradient)" strokeWidth="2.5" />
      <line x1="35" y1="65" x2="55" y2="55" stroke="url(#hex-star-gradient)" strokeWidth="2.5" />
      <line x1="35" y1="35" x2="55" y2="50" stroke="url(#hex-star-gradient)" strokeWidth="2.5" />
      {/* Center hub */}
      <circle cx="60" cy="52.5" r="8" fill="url(#hex-star-gradient)" />
    </svg>
  )
}
