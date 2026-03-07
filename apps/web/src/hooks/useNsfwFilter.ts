import { useState, useEffect } from 'react'
import { useNsfwStore, normalizeLevel } from '../stores/nsfwStore'

/**
 * Centralized NSFW filtering hook.
 * Replaces inline `nsfw && nsfwBlurEnabled && !isRevealed` patterns.
 *
 * @param nsfwLevel - Numeric Civitai level (1=PG, 2=PG13, 4=R, 8=X, 16=XXX)
 *                    or boolean (legacy: true=NSFW, false=safe)
 */
export function useNsfwFilter(nsfwLevel: number | boolean) {
  const shouldBlurFn = useNsfwStore((s) => s.shouldBlur)
  const shouldHideFn = useNsfwStore((s) => s.shouldHide)
  const filterMode = useNsfwStore((s) => s.filterMode)
  const maxLevel = useNsfwStore((s) => s.maxLevel)
  const [isRevealed, setIsRevealed] = useState(false)

  // Reset reveal state when filter mode or viewed item changes
  useEffect(() => {
    setIsRevealed(false)
  }, [filterMode, nsfwLevel])

  // Re-derive when maxLevel changes (maxLevel used to trigger recompute)
  const isHidden = shouldHideFn(nsfwLevel)
  // Mutually exclusive: hidden items are never blurred
  const isBlurred = !isHidden && shouldBlurFn(nsfwLevel) && !isRevealed
  const isNsfw = normalizeLevel(nsfwLevel).isNsfw

  // Silence TS — maxLevel is subscribed to trigger re-renders when it changes
  void maxLevel

  return {
    isBlurred,
    isHidden,
    isRevealed,
    isNsfw,
    reveal: () => setIsRevealed(true),
    hide: () => setIsRevealed(false),
    toggle: () => setIsRevealed((prev) => !prev),
    // Badge visible in show mode OR after manual reveal
    showBadge: isNsfw && (filterMode === 'show' || isRevealed),
  }
}
