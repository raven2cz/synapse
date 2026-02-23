/**
 * Tests for Avatar Context Utilities
 *
 * Tests cover:
 * - buildContextPayload: PageContext → AvatarPageContextPayload
 * - formatContextForMessage: payload → [Context: ...] prefix
 * - Edge cases: null, unknown, avatar pages
 */

import { describe, it, expect } from 'vitest'
import {
  buildContextPayload,
  formatContextForMessage,
  type AvatarPageContextPayload,
} from '../lib/avatar/context'
import type { PageContext } from '../stores/pageContextStore'

// ============================================================================
// buildContextPayload
// ============================================================================

describe('buildContextPayload', () => {
  it('should return null for null context', () => {
    expect(buildContextPayload(null)).toBeNull()
  })

  it('should return null for unknown page', () => {
    const ctx: PageContext = {
      pageId: 'unknown',
      pathname: '/some/random',
      params: {},
      updatedAt: Date.now(),
    }
    expect(buildContextPayload(ctx)).toBeNull()
  })

  it('should return null for avatar page', () => {
    const ctx: PageContext = {
      pageId: 'avatar',
      pathname: '/avatar',
      params: {},
      updatedAt: Date.now(),
    }
    expect(buildContextPayload(ctx)).toBeNull()
  })

  it('should build payload for packs page', () => {
    const ctx: PageContext = {
      pageId: 'packs',
      pathname: '/',
      params: {},
      updatedAt: Date.now(),
    }
    const payload = buildContextPayload(ctx)
    expect(payload).not.toBeNull()
    expect(payload!.page).toBe('packs')
    expect(payload!.description).toBe('Viewing pack list')
    expect(payload!.pathname).toBe('/')
    expect(payload!.entity).toBeUndefined()
    expect(payload!.entityType).toBeUndefined()
  })

  it('should build payload for inventory page', () => {
    const payload = buildContextPayload({
      pageId: 'inventory',
      pathname: '/inventory',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('inventory')
    expect(payload!.description).toBe('Viewing model inventory')
  })

  it('should build payload for pack-detail with entity', () => {
    const payload = buildContextPayload({
      pageId: 'pack-detail',
      pathname: '/packs/my-lora',
      params: { packName: 'my-lora' },
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('pack-detail')
    expect(payload!.description).toBe('Viewing pack detail')
    expect(payload!.entity).toBe('my-lora')
    expect(payload!.entityType).toBe('pack')
  })

  it('should build payload for pack-detail without packName param', () => {
    const payload = buildContextPayload({
      pageId: 'pack-detail',
      pathname: '/packs/',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('pack-detail')
    expect(payload!.entity).toBeUndefined()
    expect(payload!.entityType).toBeUndefined()
  })

  it('should build payload for browse page', () => {
    const payload = buildContextPayload({
      pageId: 'browse',
      pathname: '/browse',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('browse')
    expect(payload!.description).toBe('Browsing Civitai models')
  })

  it('should build payload for settings page', () => {
    const payload = buildContextPayload({
      pageId: 'settings',
      pathname: '/settings',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('settings')
    expect(payload!.description).toBe('Viewing settings')
  })

  it('should include pathname in all payloads', () => {
    const payload = buildContextPayload({
      pageId: 'downloads',
      pathname: '/downloads',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.pathname).toBe('/downloads')
  })

  it('should build payload for profiles page', () => {
    const payload = buildContextPayload({
      pageId: 'profiles',
      pathname: '/profiles',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('profiles')
    expect(payload!.description).toBe('Viewing profiles')
  })

  it('should build payload for downloads page', () => {
    const payload = buildContextPayload({
      pageId: 'downloads',
      pathname: '/downloads',
      params: {},
      updatedAt: Date.now(),
    })
    expect(payload!.page).toBe('downloads')
    expect(payload!.description).toBe('Viewing downloads')
  })
})

// ============================================================================
// formatContextForMessage
// ============================================================================

describe('formatContextForMessage', () => {
  it('should return empty string for null payload', () => {
    expect(formatContextForMessage(null)).toBe('')
  })

  it('should format simple page context', () => {
    const payload: AvatarPageContextPayload = {
      page: 'inventory',
      description: 'Viewing model inventory',
      pathname: '/inventory',
    }
    expect(formatContextForMessage(payload)).toBe('[Context: Viewing model inventory]')
  })

  it('should include entity in format', () => {
    const payload: AvatarPageContextPayload = {
      page: 'pack-detail',
      description: 'Viewing pack detail',
      entity: 'my-lora',
      entityType: 'pack',
      pathname: '/packs/my-lora',
    }
    expect(formatContextForMessage(payload)).toBe(
      '[Context: Viewing pack detail, pack: my-lora]',
    )
  })

  it('should not include entity when missing', () => {
    const payload: AvatarPageContextPayload = {
      page: 'browse',
      description: 'Browsing Civitai models',
      pathname: '/browse',
    }
    const result = formatContextForMessage(payload)
    expect(result).toBe('[Context: Browsing Civitai models]')
    expect(result).not.toContain('undefined')
  })

  it('should not include entity when only entity is set (no entityType)', () => {
    const payload: AvatarPageContextPayload = {
      page: 'pack-detail',
      description: 'Viewing pack detail',
      entity: 'my-lora',
      pathname: '/packs/my-lora',
    }
    const result = formatContextForMessage(payload)
    expect(result).toBe('[Context: Viewing pack detail]')
    expect(result).not.toContain('my-lora')
  })

  it('should not include entity when only entityType is set (no entity)', () => {
    const payload: AvatarPageContextPayload = {
      page: 'pack-detail',
      description: 'Viewing pack detail',
      entityType: 'pack',
      pathname: '/packs/x',
    }
    const result = formatContextForMessage(payload)
    expect(result).toBe('[Context: Viewing pack detail]')
    expect(result).not.toContain('pack:')
  })
})
