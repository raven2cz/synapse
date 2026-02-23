/**
 * Avatar Engine API client.
 *
 * Calls /api/avatar/* endpoints for AI assistant status,
 * provider detection, and configuration.
 */

const API_BASE = '/api/avatar'

// --- Types ---

export interface AvatarProvider {
  name: string
  display_name: string
  command: string
  installed: boolean
}

export interface AvatarStatus {
  available: boolean
  state: 'ready' | 'no_provider' | 'no_engine' | 'setup_required' | 'disabled'
  enabled: boolean
  engine_installed: boolean
  engine_version: string | null
  active_provider: string | null
  safety: string
  providers: AvatarProvider[]
}

export interface AvatarConfig {
  enabled: boolean
  provider: string
  safety: string
  max_history: number
  has_config_file: boolean
  config_path: string | null
  skills_count: { builtin: number; custom: number }
  provider_configs: Record<string, { model: string; enabled: boolean }>
}

// --- Query key factory ---

export const avatarKeys = {
  all: ['avatar'] as const,
  status: () => [...avatarKeys.all, 'status'] as const,
  providers: () => [...avatarKeys.all, 'providers'] as const,
  config: () => [...avatarKeys.all, 'config'] as const,
}

// --- API functions ---

export async function getAvatarStatus(): Promise<AvatarStatus> {
  const res = await fetch(`${API_BASE}/status`)
  if (!res.ok) throw new Error('Failed to fetch avatar status')
  return res.json()
}

export async function getAvatarProviders(): Promise<AvatarProvider[]> {
  const res = await fetch(`${API_BASE}/providers`)
  if (!res.ok) throw new Error('Failed to fetch avatar providers')
  return res.json()
}

export async function getAvatarConfig(): Promise<AvatarConfig> {
  const res = await fetch(`${API_BASE}/config`)
  if (!res.ok) throw new Error('Failed to fetch avatar config')
  return res.json()
}
