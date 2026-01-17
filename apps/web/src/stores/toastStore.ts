import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
}

interface ToastState {
  toasts: Toast[]
  addToast: (type: ToastType, message: string, duration?: number) => void
  removeToast: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  
  addToast: (type, message, duration = 4000) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    
    set((state) => ({
      toasts: [...state.toasts, { id, type, message, duration }]
    }))
    
    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id)
        }))
      }, duration)
    }
  },
  
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id)
    }))
  },
}))

// Helper functions for easy usage
export const toast = {
  success: (message: string, duration?: number) => 
    useToastStore.getState().addToast('success', message, duration),
  error: (message: string, duration?: number) => 
    useToastStore.getState().addToast('error', message, duration),
  info: (message: string, duration?: number) => 
    useToastStore.getState().addToast('info', message, duration),
  warning: (message: string, duration?: number) => 
    useToastStore.getState().addToast('warning', message, duration),
}
