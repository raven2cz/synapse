/**
 * Pack Data Query Invalidation Tests
 *
 * Verifies that mutations in usePackData.ts which modify pack state
 * visible on PacksPage correctly invalidate the ['packs'] query key.
 *
 * Background: PacksPage uses `useQuery({ queryKey: ['packs'] })` with
 * a global staleTime of 60s. If a mutation on PackDetailPage changes
 * pack state (e.g. resolves a dependency → has_unresolved changes)
 * but doesn't invalidate ['packs'], the PacksPage will show stale
 * data (e.g. "Needs Setup" badge) until the staleTime expires.
 *
 * This is a static analysis test — it reads the source file and
 * verifies the invariant without React rendering.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// Read the source file
const SOURCE_PATH = resolve(
  __dirname,
  '../components/modules/pack-detail/hooks/usePackData.ts'
)
const source = readFileSync(SOURCE_PATH, 'utf-8')

/**
 * Extract mutation blocks from usePackData.ts source.
 *
 * Each mutation follows this pattern:
 *   const fooMutation = useMutation({
 *     mutationFn: async (...) => { ... },
 *     onSuccess: () => { ... },
 *     onError: ...
 *   })
 *
 * Returns a map of mutationName → onSuccess body text.
 */
function extractMutations(src: string): Map<string, string> {
  const mutations = new Map<string, string>()

  // Match: const <name>Mutation = useMutation({
  const mutationStarts = [...src.matchAll(/const (\w+Mutation) = useMutation\(\{/g)]

  for (let i = 0; i < mutationStarts.length; i++) {
    const name = mutationStarts[i][1]
    const startIdx = mutationStarts[i].index!

    // Find the onSuccess block within this mutation
    // We look from the mutation start to the next mutation (or EOF)
    const endIdx = i + 1 < mutationStarts.length
      ? mutationStarts[i + 1].index!
      : src.length

    const mutationBlock = src.slice(startIdx, endIdx)

    // Extract onSuccess body
    const successMatch = mutationBlock.match(/onSuccess:\s*\([^)]*\)\s*=>\s*\{([\s\S]*?)\},\s*onError/)
    if (successMatch) {
      mutations.set(name, successMatch[1])
    }
  }

  return mutations
}

const mutations = extractMutations(source)

// ============================================================================
// Mutations that MUST invalidate ['packs'] because they change state
// visible on PacksPage (has_unresolved, tags, thumbnail, pack existence)
// ============================================================================

const MUST_INVALIDATE_PACKS = [
  // Changes pack existence on list
  'deleteMutation',
  // Changes user_tags shown on list cards
  'updatePackMutation',
  // Resolves base model → changes has_unresolved
  'resolveBaseModelMutation',
  // Resolves all deps → changes has_unresolved
  'resolvePackMutation',
  // Deletes resource → can change has_unresolved
  'deleteResourceMutation',
  // Changes dependency strategy → can affect resolution status
  'setAsBaseModelMutation',
  // Changes previews/thumbnail shown on list
  'batchUpdatePreviewsMutation',
  // Changes cover image shown on list
  'setCoverPreviewMutation',
]

// ============================================================================
// Mutations that DON'T need ['packs'] invalidation because they only
// affect pack detail view, not the list
// ============================================================================

const NO_PACKS_INVALIDATION_NEEDED = [
  // Only affects profile status, not pack list
  'usePackMutation',
  // Only affects parameters (not shown on list)
  'updateParametersMutation',
  // Workflow mutations — not visible on pack list
  'generateWorkflowMutation',
  'createSymlinkMutation',
  'removeSymlinkMutation',
  'deleteWorkflowMutation',
  'uploadWorkflowMutation',
  // Description not shown on list cards
  'updateDescriptionMutation',
  // Backup operations — not visible on list
  'pullPackMutation',
  'pushPackMutation',
  // Individual preview upload — batchUpdate handles list invalidation
  'uploadPreviewMutation',
  // Individual preview delete — minor, batch handles it
  'deletePreviewMutation',
  // Reorder — doesn't change which preview is cover
  'reorderPreviewsMutation',
]

// ============================================================================
// Tests
// ============================================================================

describe('usePackData Query Invalidation', () => {
  it('should find all expected mutations in source', () => {
    const allExpected = [...MUST_INVALIDATE_PACKS, ...NO_PACKS_INVALIDATION_NEEDED]
    const found = [...mutations.keys()]

    for (const name of allExpected) {
      expect(found, `Mutation "${name}" not found in usePackData.ts`).toContain(name)
    }
  })

  it('should account for all mutations in source (no uncategorized)', () => {
    const allCategorized = new Set([
      ...MUST_INVALIDATE_PACKS,
      ...NO_PACKS_INVALIDATION_NEEDED,
    ])

    for (const name of mutations.keys()) {
      expect(
        allCategorized.has(name),
        `Mutation "${name}" exists in usePackData.ts but is not categorized ` +
        `in the test. Add it to MUST_INVALIDATE_PACKS or NO_PACKS_INVALIDATION_NEEDED.`
      ).toBe(true)
    }
  })

  describe('mutations affecting PacksPage MUST invalidate [\'packs\']', () => {
    for (const name of MUST_INVALIDATE_PACKS) {
      it(`${name} should invalidate ['packs'] query`, () => {
        const body = mutations.get(name)
        expect(body, `Could not find onSuccess for ${name}`).toBeDefined()
        expect(
          body,
          `${name}.onSuccess does NOT invalidate ['packs']. ` +
          `PacksPage will show stale data (e.g. "Needs Setup" badge) after this mutation. ` +
          `Add: queryClient.invalidateQueries({ queryKey: ['packs'] })`
        ).toContain("['packs']")
      })
    }
  })

  describe('mutations NOT affecting PacksPage should not over-invalidate', () => {
    // This is a softer check — it's OK if they DO invalidate,
    // but we document which ones currently don't need to.
    for (const name of NO_PACKS_INVALIDATION_NEEDED) {
      it(`${name} is categorized as not needing ['packs'] invalidation`, () => {
        // Just verify the mutation exists and is parseable
        const body = mutations.get(name)
        expect(body, `Could not find onSuccess for ${name}`).toBeDefined()
      })
    }
  })
})
