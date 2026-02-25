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
  skills?: AvatarSkills
  provider_configs: Record<string, { model: string; enabled: boolean }>
}

export interface AvatarSkillInfo {
  name: string
  path: string
  size: number
  category: 'builtin' | 'custom'
}

export interface AvatarSkills {
  builtin: AvatarSkillInfo[]
  custom: AvatarSkillInfo[]
}

export interface AvatarInfo {
  id: string
  name: string
  category: 'builtin' | 'custom'
}

export interface AvatarAvatars {
  builtin: AvatarInfo[]
  custom: AvatarInfo[]
}

// --- Query key factory ---

export const avatarKeys = {
  all: ['avatar'] as const,
  status: () => [...avatarKeys.all, 'status'] as const,
  providers: () => [...avatarKeys.all, 'providers'] as const,
  config: () => [...avatarKeys.all, 'config'] as const,
  skills: () => [...avatarKeys.all, 'skills'] as const,
  avatars: () => [...avatarKeys.all, 'avatars'] as const,
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

export async function getAvatarSkills(): Promise<AvatarSkills> {
  const res = await fetch(`${API_BASE}/skills`)
  if (!res.ok) throw new Error('Failed to fetch avatar skills')
  return res.json()
}

export async function getAvatarAvatars(): Promise<AvatarAvatars> {
  const res = await fetch(`${API_BASE}/avatars`)
  if (!res.ok) throw new Error('Failed to fetch avatar avatars')
  return res.json()
}

export async function patchAvatarConfig(updates: Partial<{
  enabled: boolean
  provider: string
  providers: Record<string, { enabled?: boolean; model?: string }>
}>): Promise<AvatarConfig> {
  const res = await fetch(`${API_BASE}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  if (!res.ok) throw new Error('Failed to update avatar config')
  return res.json()
}
