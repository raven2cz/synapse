/**
 * Parameter Key Normalizer
 *
 * Normalizes parameter keys from various formats (camelCase, kebab-case)
 * to canonical snake_case format for consistent storage and display.
 */

/**
 * Maps various parameter key formats to canonical snake_case.
 * Mirrors backend PARAM_KEY_ALIASES for consistency.
 */
export const PARAM_KEY_ALIASES: Record<string, string> = {
  // CFG Scale variants
  cfg: 'cfg_scale',
  cfgscale: 'cfg_scale',
  cfg_scale: 'cfg_scale',
  cfgScale: 'cfg_scale',
  guidance: 'cfg_scale',
  guidance_scale: 'cfg_scale',

  // Clip Skip variants
  clipskip: 'clip_skip',
  clip_skip: 'clip_skip',
  clipSkip: 'clip_skip',
  clip: 'clip_skip',

  // Steps variants
  steps: 'steps',
  num_steps: 'steps',
  numSteps: 'steps',
  sampling_steps: 'steps',

  // Sampler variants
  sampler: 'sampler',
  sampler_name: 'sampler',
  samplerName: 'sampler',
  sampling_method: 'sampler',

  // Scheduler variants
  scheduler: 'scheduler',
  schedule: 'scheduler',
  schedule_type: 'scheduler',

  // Seed variants
  seed: 'seed',
  noise_seed: 'seed',

  // Denoise/Strength variants
  denoise: 'denoise',
  denoising: 'denoise',
  denoising_strength: 'denoise',
  strength: 'strength',
  lora_strength: 'strength',
  loraStrength: 'strength',

  // Resolution variants
  width: 'width',
  w: 'width',
  height: 'height',
  h: 'height',
  size: 'size',

  // HiRes variants
  hires_fix: 'hires_fix',
  hiresFix: 'hires_fix',
  hiresfix: 'hires_fix',
  highres_fix: 'hires_fix',
  hires_upscaler: 'hires_upscaler',
  hiresUpscaler: 'hires_upscaler',
  hires_upscale: 'hires_scale',
  hiresUpscale: 'hires_scale',
  hires_scale: 'hires_scale',
  hires_steps: 'hires_steps',
  hiresSteps: 'hires_steps',
  hires_denoise: 'hires_denoise',
  hiresDenoise: 'hires_denoise',

  // VAE variants
  vae: 'vae',
  vae_name: 'vae',
  vaeName: 'vae',

  // Model variants
  model: 'base_model',
  model_name: 'base_model',
  modelName: 'base_model',
  base_model: 'base_model',
  checkpoint: 'base_model',
}

/**
 * Parameters that should be numeric (int or float)
 */
export const NUMERIC_PARAMS = new Set([
  'cfg_scale', 'clip_skip', 'steps', 'seed', 'denoise', 'strength',
  'width', 'height', 'hires_scale', 'hires_steps', 'hires_denoise',
])

/**
 * Parameters that should be integers
 */
export const INTEGER_PARAMS = new Set([
  'clip_skip', 'steps', 'seed', 'width', 'height', 'hires_steps',
])

/**
 * Parameters that should be booleans
 */
export const BOOLEAN_PARAMS = new Set([
  'hires_fix',
])

/**
 * Normalize parameter key to canonical snake_case format.
 *
 * @param key - Parameter key in any format (camelCase, kebab-case, etc.)
 * @returns Normalized snake_case key
 *
 * @example
 * normalizeParamKey('cfgScale')    // 'cfg_scale'
 * normalizeParamKey('clip-skip')   // 'clip_skip'
 */
export function normalizeParamKey(key: string): string {
  if (!key) return key

  // Check direct alias match first
  const lowerKey = key.toLowerCase().replace(/-/g, '_').replace(/ /g, '_')
  if (PARAM_KEY_ALIASES[lowerKey]) {
    return PARAM_KEY_ALIASES[lowerKey]
  }

  // Check original key
  if (PARAM_KEY_ALIASES[key]) {
    return PARAM_KEY_ALIASES[key]
  }

  // Convert camelCase to snake_case
  const snake = key
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/-/g, '_')
    .replace(/ /g, '_')

  // Check if converted key has alias
  if (PARAM_KEY_ALIASES[snake]) {
    return PARAM_KEY_ALIASES[snake]
  }

  return snake
}

/**
 * Convert parameter value to appropriate type.
 *
 * @param key - Normalized parameter key
 * @param value - Raw value (usually string from metadata)
 * @returns Value converted to appropriate type (number, boolean, string)
 *
 * @example
 * convertParamValue('steps', '25')      // 25
 * convertParamValue('cfg_scale', '7.5') // 7.5
 * convertParamValue('hires_fix', 'true') // true
 */
export function convertParamValue(key: string, value: unknown): unknown {
  if (value === null || value === undefined) {
    return null
  }

  // Already correct type (not string)
  if (typeof value !== 'string') {
    return value
  }

  const strValue = value.trim().toLowerCase()

  // Boolean conversion
  if (BOOLEAN_PARAMS.has(key)) {
    return ['true', 'yes', 'enabled', 'enable', '1', 'on'].includes(strValue)
  }

  // Integer conversion
  if (INTEGER_PARAMS.has(key)) {
    const num = parseInt(strValue, 10)
    return isNaN(num) ? null : num
  }

  // Float conversion for other numeric params
  if (NUMERIC_PARAMS.has(key)) {
    const num = parseFloat(strValue)
    return isNaN(num) ? null : num
  }

  // String - preserve original value for non-numeric params
  return value.trim() || null
}

/**
 * Normalize all parameter keys and convert values.
 *
 * @param params - Dictionary with parameter key-value pairs
 * @returns Dictionary with normalized keys and converted values
 *
 * @example
 * normalizeParams({ cfgScale: '7', clipSkip: '2' })
 * // { cfg_scale: 7, clip_skip: 2 }
 */
export function normalizeParams(params: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(params)) {
    const normalizedKey = normalizeParamKey(key)
    const convertedValue = convertParamValue(normalizedKey, value)

    if (convertedValue !== null) {
      result[normalizedKey] = convertedValue
    }
  }

  return result
}
