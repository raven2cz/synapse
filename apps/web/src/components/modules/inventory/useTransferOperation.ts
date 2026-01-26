/**
 * useTransferOperation - Unified hook for tracking transfer operations
 *
 * Provides consistent progress tracking for:
 * - Backup operations (local → backup)
 * - Restore operations (backup → local)
 * - Delete operations
 * - Sync operations
 * - Verify operations
 *
 * Features:
 * - Sequential processing with per-item progress
 * - Real-time UI updates
 * - Error handling with retry capability
 * - Cancel support
 * - Speed and ETA calculation
 */
import { useState, useCallback, useRef } from 'react'
import type { TransferProgress, TransferOperation, TransferStatus, TransferItem } from './types'

export interface TransferOperationItem {
  sha256: string
  display_name: string
  size_bytes: number
}

export interface UseTransferOperationOptions {
  operation: TransferOperation
  onItemComplete?: (item: TransferOperationItem, success: boolean) => void
  onComplete?: (progress: TransferProgress) => void
}

export interface UseTransferOperationReturn {
  // State
  progress: TransferProgress | null
  isRunning: boolean
  isCompleted: boolean
  isFailed: boolean
  hasFailed: boolean

  // Actions
  start: (
    items: TransferOperationItem[],
    executeFn: (sha256: string) => Promise<void>
  ) => Promise<TransferProgress>
  cancel: () => void
  retryFailed: (executeFn: (sha256: string) => Promise<void>) => Promise<void>
  reset: () => void
}

export function useTransferOperation({
  operation,
  onItemComplete,
  onComplete,
}: UseTransferOperationOptions): UseTransferOperationReturn {
  const [progress, setProgress] = useState<TransferProgress | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const abortRef = useRef(false)
  const startTimeRef = useRef<number>(0)
  const itemsRef = useRef<TransferOperationItem[]>([])

  // Calculate derived state
  const isCompleted = progress?.status === 'completed'
  const isFailed = progress?.status === 'failed'
  const hasFailed = (progress?.failed_items || 0) > 0

  // Create initial progress state
  const createInitialProgress = useCallback(
    (items: TransferOperationItem[]): TransferProgress => ({
      operation,
      status: 'in_progress',
      total_items: items.length,
      completed_items: 0,
      failed_items: 0,
      total_bytes: items.reduce((sum, i) => sum + i.size_bytes, 0),
      transferred_bytes: 0,
      items: items.map((item) => ({
        sha256: item.sha256,
        display_name: item.display_name,
        size_bytes: item.size_bytes,
        status: 'pending' as TransferStatus,
      })),
      errors: [],
      can_resume: true,
    }),
    [operation]
  )

  // Update progress with timing info
  const updateProgress = useCallback((updater: (prev: TransferProgress) => TransferProgress) => {
    setProgress((prev) => {
      if (!prev) return prev
      const updated = updater(prev)

      // Calculate timing
      const elapsed = (Date.now() - startTimeRef.current) / 1000
      const bytesPerSecond = elapsed > 0 ? updated.transferred_bytes / elapsed : 0
      const remainingBytes = updated.total_bytes - updated.transferred_bytes
      const etaSeconds = bytesPerSecond > 0 ? remainingBytes / bytesPerSecond : undefined

      return {
        ...updated,
        elapsed_seconds: elapsed,
        bytes_per_second: bytesPerSecond,
        eta_seconds: etaSeconds,
      }
    })
  }, [])

  // Start operation
  const start = useCallback(
    async (
      items: TransferOperationItem[],
      executeFn: (sha256: string) => Promise<void>
    ): Promise<TransferProgress> => {
      if (items.length === 0) {
        const emptyResult: TransferProgress = {
          operation,
          status: 'completed',
          total_items: 0,
          completed_items: 0,
          failed_items: 0,
          total_bytes: 0,
          transferred_bytes: 0,
          items: [],
          errors: [],
          can_resume: false,
        }
        setProgress(emptyResult)
        return emptyResult
      }

      // Initialize
      setIsRunning(true)
      abortRef.current = false
      startTimeRef.current = Date.now()
      itemsRef.current = items

      const initialProgress = createInitialProgress(items)
      setProgress(initialProgress)

      let completedItems = 0
      let failedItems = 0
      let transferredBytes = 0
      const errors: string[] = []
      const resultItems: TransferItem[] = [...initialProgress.items]

      // Process items sequentially
      for (let i = 0; i < items.length; i++) {
        if (abortRef.current) break

        const item = items[i]

        // Update current item
        updateProgress((prev) => ({
          ...prev,
          current_item: {
            sha256: item.sha256,
            display_name: item.display_name,
            size_bytes: item.size_bytes,
            status: 'in_progress',
          },
        }))

        // Mark as in progress
        resultItems[i] = { ...resultItems[i], status: 'in_progress' }
        updateProgress((prev) => ({
          ...prev,
          items: [...resultItems],
        }))

        try {
          await executeFn(item.sha256)

          // Success
          completedItems++
          transferredBytes += item.size_bytes
          resultItems[i] = {
            ...resultItems[i],
            status: 'completed',
            bytes_transferred: item.size_bytes,
          }

          onItemComplete?.(item, true)
        } catch (error) {
          // Failure
          failedItems++
          const errorMsg = error instanceof Error ? error.message : 'Unknown error'
          errors.push(`${item.display_name}: ${errorMsg}`)
          resultItems[i] = {
            ...resultItems[i],
            status: 'failed',
            error: errorMsg,
          }

          onItemComplete?.(item, false)
        }

        // Update progress
        updateProgress((prev) => ({
          ...prev,
          completed_items: completedItems,
          failed_items: failedItems,
          transferred_bytes: transferredBytes,
          items: [...resultItems],
          errors: [...errors],
        }))
      }

      // Final status
      const finalStatus: TransferStatus = abortRef.current
        ? 'cancelled'
        : failedItems > 0
          ? 'failed'
          : 'completed'

      const finalProgress: TransferProgress = {
        operation,
        status: finalStatus,
        total_items: items.length,
        completed_items: completedItems,
        failed_items: failedItems,
        total_bytes: items.reduce((sum, i) => sum + i.size_bytes, 0),
        transferred_bytes: transferredBytes,
        elapsed_seconds: (Date.now() - startTimeRef.current) / 1000,
        items: resultItems,
        errors,
        can_resume: failedItems > 0,
      }

      setProgress(finalProgress)
      setIsRunning(false)
      onComplete?.(finalProgress)

      return finalProgress
    },
    [operation, createInitialProgress, updateProgress, onItemComplete, onComplete]
  )

  // Cancel operation
  const cancel = useCallback(() => {
    abortRef.current = true
    setProgress((prev) =>
      prev
        ? {
            ...prev,
            status: 'cancelled',
          }
        : null
    )
    setIsRunning(false)
  }, [])

  // Retry failed items
  const retryFailed = useCallback(
    async (executeFn: (sha256: string) => Promise<void>) => {
      if (!progress) return

      const failedItemsData = itemsRef.current.filter((item) =>
        progress.items.find((i) => i.sha256 === item.sha256 && i.status === 'failed')
      )

      if (failedItemsData.length === 0) return

      // Reset failed items to pending
      setProgress((prev) =>
        prev
          ? {
              ...prev,
              status: 'in_progress',
              failed_items: 0,
              items: prev.items.map((item) =>
                item.status === 'failed'
                  ? { ...item, status: 'pending' as TransferStatus, error: undefined }
                  : item
              ),
              errors: [],
            }
          : null
      )

      setIsRunning(true)
      abortRef.current = false
      startTimeRef.current = Date.now()

      let newCompleted = 0
      let newFailed = 0
      const newErrors: string[] = []

      for (const item of failedItemsData) {
        if (abortRef.current) break

        // Update current item
        updateProgress((prev) => ({
          ...prev,
          current_item: {
            sha256: item.sha256,
            display_name: item.display_name,
            size_bytes: item.size_bytes,
            status: 'in_progress',
          },
        }))

        try {
          await executeFn(item.sha256)
          newCompleted++

          // Update item status
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  completed_items: prev.completed_items + 1,
                  transferred_bytes: prev.transferred_bytes + item.size_bytes,
                  items: prev.items.map((i) =>
                    i.sha256 === item.sha256
                      ? { ...i, status: 'completed' as TransferStatus, bytes_transferred: item.size_bytes }
                      : i
                  ),
                }
              : null
          )
        } catch (error) {
          newFailed++
          const errorMsg = error instanceof Error ? error.message : 'Unknown error'
          newErrors.push(`${item.display_name}: ${errorMsg}`)

          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  failed_items: prev.failed_items + 1,
                  items: prev.items.map((i) =>
                    i.sha256 === item.sha256 ? { ...i, status: 'failed' as TransferStatus, error: errorMsg } : i
                  ),
                  errors: [...prev.errors, `${item.display_name}: ${errorMsg}`],
                }
              : null
          )
        }
      }

      // Final status
      setProgress((prev) =>
        prev
          ? {
              ...prev,
              status: newFailed > 0 ? 'failed' : 'completed',
              current_item: undefined,
              can_resume: newFailed > 0,
            }
          : null
      )

      setIsRunning(false)
    },
    [progress, updateProgress]
  )

  // Reset state
  const reset = useCallback(() => {
    setProgress(null)
    setIsRunning(false)
    abortRef.current = false
    itemsRef.current = []
  }, [])

  return {
    progress,
    isRunning,
    isCompleted,
    isFailed,
    hasFailed,
    start,
    cancel,
    retryFailed,
    reset,
  }
}
