/**
 * Unit Tests: Avatar Engine Version Check
 *
 * Tests the semverLessThan utility and version check logic
 * from AvatarProvider.tsx.
 */

import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from 'vitest'

// ============================================================================
// semverLessThan — extracted logic mirror
// ============================================================================

/** Compare two semver strings. Returns true if a < b. */
function semverLessThan(a: string, b: string): boolean {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    if ((pa[i] ?? 0) < (pb[i] ?? 0)) return true
    if ((pa[i] ?? 0) > (pb[i] ?? 0)) return false
  }
  return false
}

describe('semverLessThan', () => {
  it('should return false for equal versions', () => {
    expect(semverLessThan('1.0.0', '1.0.0')).toBe(false)
  })

  it('should return true when major is less', () => {
    expect(semverLessThan('0.9.0', '1.0.0')).toBe(true)
  })

  it('should return false when major is greater', () => {
    expect(semverLessThan('2.0.0', '1.0.0')).toBe(false)
  })

  it('should return true when minor is less', () => {
    expect(semverLessThan('1.0.0', '1.1.0')).toBe(true)
  })

  it('should return false when minor is greater', () => {
    expect(semverLessThan('1.2.0', '1.1.0')).toBe(false)
  })

  it('should return true when patch is less', () => {
    expect(semverLessThan('1.0.0', '1.0.1')).toBe(true)
  })

  it('should return false when patch is greater', () => {
    expect(semverLessThan('1.0.2', '1.0.1')).toBe(false)
  })

  it('should handle two-segment versions', () => {
    // Missing patch treated as 0
    expect(semverLessThan('1.0', '1.0.1')).toBe(true)
  })

  it('should handle single-segment versions', () => {
    expect(semverLessThan('1', '2.0.0')).toBe(true)
  })
})

// ============================================================================
// Version Check Logic (mirrors AvatarProvider useEffect)
// ============================================================================

const AE_MIN_VERSION = '1.0.0'

describe('AvatarProvider version check logic', () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let warnSpy: MockInstance<any[], any>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let fetchSpy: MockInstance<any[], any>

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {}) as MockInstance<any[], any>
    fetchSpy = vi.spyOn(globalThis, 'fetch') as MockInstance<any[], any>
  })

  afterEach(() => {
    warnSpy.mockRestore()
    fetchSpy.mockRestore()
  })

  /** Simulate the version check logic from AvatarProvider */
  async function simulateVersionCheck(statusResponse: Record<string, unknown> | null) {
    fetchSpy.mockResolvedValueOnce({
      ok: statusResponse !== null,
      json: async () => statusResponse,
    } as Response)

    const response = await fetch('/api/avatar/status')
    const data = response.ok ? await response.json() : null

    if (data?.engine_version && data.engine_version !== 'unknown') {
      if (semverLessThan(data.engine_version as string, AE_MIN_VERSION)) {
        console.warn(
          `[Synapse] Backend avatar-engine ${data.engine_version} is below minimum ${AE_MIN_VERSION} — upgrade recommended`
        )
      }
    }
  }

  it('should not warn when version meets minimum', async () => {
    await simulateVersionCheck({ engine_version: '1.0.0' })
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('should not warn when version exceeds minimum', async () => {
    await simulateVersionCheck({ engine_version: '2.1.0' })
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('should warn when version is below minimum', async () => {
    await simulateVersionCheck({ engine_version: '0.9.0' })
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('below minimum')
    )
  })

  it('should not warn when version is unknown', async () => {
    await simulateVersionCheck({ engine_version: 'unknown' })
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('should not warn when engine_version is missing', async () => {
    await simulateVersionCheck({ state: 'setup_required' })
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('should not warn when status endpoint fails', async () => {
    await simulateVersionCheck(null)
    expect(warnSpy).not.toHaveBeenCalled()
  })

  it('should not crash when fetch throws', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('Network error'))

    try {
      const response = await fetch('/api/avatar/status')
      const data = response.ok ? await response.json() : null
      if (data?.engine_version && data.engine_version !== 'unknown') {
        if (semverLessThan(data.engine_version as string, AE_MIN_VERSION)) {
          console.warn('below minimum')
        }
      }
    } catch {
      // Non-critical — should not crash
    }

    expect(warnSpy).not.toHaveBeenCalled()
  })
})
