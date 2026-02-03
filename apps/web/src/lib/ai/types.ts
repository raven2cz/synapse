/**
 * AI Services Types
 *
 * TypeScript types for AI services integration.
 * Uses string types instead of enums for flexibility.
 */

// Provider identifiers (extensible)
export type ProviderId = string // "ollama" | "gemini" | "claude" | "rule_based" | custom

// Task type identifiers (extensible)
export type TaskType = string // "parameter_extraction" | "description_translation" | custom

// Well-known providers (for UI hints)
export const KNOWN_PROVIDERS = ['ollama', 'gemini', 'claude', 'rule_based'] as const

// Well-known tasks
export const KNOWN_TASKS = [
  'parameter_extraction',
  'description_translation',
  'auto_tagging',
  'workflow_generation',
  'model_compatibility',
  'preview_analysis',
  'config_migration',
] as const

/**
 * Provider configuration
 */
export interface ProviderConfig {
  providerId: string
  enabled: boolean
  model: string
  availableModels: string[]
  endpoint?: string
  extraArgs?: Record<string, unknown>
}

/**
 * Provider runtime status
 */
export interface ProviderStatus {
  providerId: string
  available: boolean
  running: boolean
  version?: string
  models: string[]
  error?: string
}

/**
 * Task-specific priority configuration (snake_case from API)
 */
export interface TaskPriorityConfig {
  task_type: string
  provider_order: string[] // Provider IDs in order
  custom_timeout?: number
  custom_prompt?: string
}

/**
 * Complete AI services settings (snake_case from API)
 */
export interface AIServicesSettings {
  enabled: boolean
  providers: Record<string, ProviderConfig>
  task_priorities: Record<string, TaskPriorityConfig>
  cli_timeout_seconds: number
  max_retries: number
  retry_delay_seconds: number
  cache_enabled: boolean
  cache_ttl_days: number
  cache_directory: string
  always_fallback_to_rule_based: boolean
  show_provider_in_results: boolean
  log_requests: boolean
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  log_prompts: boolean
  log_responses: boolean
}

/**
 * Response for provider detection (snake_case from API)
 */
export interface AIDetectionResponse {
  providers: Record<string, ProviderStatus>
  available_count: number
  running_count: number
}

/**
 * Response for parameter extraction
 */
export interface AIExtractionResponse {
  success: boolean
  parameters?: Record<string, unknown>
  error?: string
  providerId?: string
  model?: string
  cached: boolean
  executionTimeMs: number
}

/**
 * Cache statistics (snake_case from API)
 */
export interface AICacheStats {
  cache_dir: string
  entry_count: number
  total_size_bytes: number
  total_size_mb: number
  ttl_days: number
}

/**
 * Provider display info for UI
 */
export interface ProviderDisplayInfo {
  id: string
  name: string
  type: 'local' | 'cloud'
  icon: string
  description: string
  installGuide?: string
}

/**
 * Provider display configurations
 */
export const PROVIDER_INFO: Record<string, ProviderDisplayInfo> = {
  ollama: {
    id: 'ollama',
    name: 'Ollama',
    type: 'local',
    icon: '🦙',
    description: 'Local GPU-accelerated inference (~2.9s)',
    installGuide: 'Install: yay -S ollama-cuda && ollama pull qwen2.5:14b',
  },
  gemini: {
    id: 'gemini',
    name: 'Gemini CLI',
    type: 'cloud',
    icon: '✨',
    description: 'Google AI with unlimited Pro subscription (~21s)',
    installGuide: 'Install from: https://github.com/google-gemini/gemini-cli',
  },
  claude: {
    id: 'claude',
    name: 'Claude Code',
    type: 'cloud',
    icon: '🤖',
    description: 'Highest quality extraction (~8s, limited quota)',
    installGuide: 'Install from: https://claude.ai/claude-code',
  },
  rule_based: {
    id: 'rule_based',
    name: 'Rule-based',
    type: 'local',
    icon: '📋',
    description: 'Pattern matching fallback (always available)',
  },
}

/**
 * Recommended models for each provider (defaults + common models)
 */
export const RECOMMENDED_MODELS: Record<string, string[]> = {
  ollama: [
    'qwen2.5:14b',
    'qwen2.5:7b',
    'qwen2.5:32b',
    'llama3.1:8b',
    'llama3.1:70b',
    'mistral:7b',
    'mixtral:8x7b',
    'codellama:13b',
    'deepseek-coder:6.7b',
    'phi3:14b',
  ],
  gemini: [
    'gemini-2.5-pro',
    'gemini-2.5-flash',
    'gemini-3-pro-preview',
    'gemini-3-flash-preview',
    'gemini-pro',
    'gemini-pro-vision',
  ],
  claude: [
    'claude-sonnet-4-20250514',
    'claude-opus-4-5-20251101',
    'claude-haiku-4-5-20251001',
    'claude-3-opus',
    'claude-3-sonnet',
    'claude-3-haiku',
  ],
}
