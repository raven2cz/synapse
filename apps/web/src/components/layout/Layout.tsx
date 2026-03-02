/**
 * Layout — Main app shell with @avatar-engine/react AvatarWidget.
 *
 * AvatarWidget handles FAB / CompactChat / Fullscreen internally.
 * The existing Synapse UI (Header, Sidebar, page content) is rendered
 * via renderBackground — always visible behind all avatar modes.
 *
 * PermissionDialog (ACP) is a sibling OUTSIDE AvatarWidget.
 */

import { useEffect, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AvatarWidget,
  PermissionDialog,
  StatusBar,
  ChatPanel,
  createProviders,
} from '@avatar-engine/react'
import type { EngineState } from '@avatar-engine/react'

/**
 * E2E test model override — when VITE_E2E_MODEL is set (via Playwright webServer),
 * override the provider dropdown to show the cheap test model.
 * The backend model is switched separately via run-e2e.sh.
 */
const E2E_PROVIDERS = import.meta.env.VITE_E2E_MODEL
  ? createProviders({ gemini: { defaultModel: import.meta.env.VITE_E2E_MODEL } })
  : undefined
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { ToastContainer } from '../ui/Toast'
import { AvatarProvider, useAvatar, ALL_AVATARS } from '../avatar/AvatarProvider'
import { SuggestionChips } from '../avatar/SuggestionChips'
import { usePageContextStore } from '../../stores/pageContextStore'
import { getAvatarStatus, avatarKeys } from '../../lib/avatar/api'

interface LayoutProps {
  children: ReactNode
}

function LayoutInner({ children }: LayoutProps) {
  const { chat, sendWithContext, providers, dynamicProviders, compactRef } = useAvatar()
  const { pathname } = useLocation()

  // Track page context for suggestions (Iterace 5)
  useEffect(() => {
    usePageContextStore.getState().setContext(pathname)
  }, [pathname])

  // Check if AI is enabled (master toggle)
  const { data: avatarStatus } = useQuery({
    queryKey: avatarKeys.status(),
    queryFn: getAvatarStatus,
    staleTime: 60_000,
  })

  const aiEnabled = avatarStatus?.enabled !== false

  // When AI is disabled, render layout without AvatarWidget
  if (!aiEnabled) {
    return (
      <div className="min-h-screen bg-obsidian flex flex-col">
        <Header />
        <div className="flex flex-1">
          <Sidebar />
          <main className="flex-1 p-6">{children}</main>
        </div>
        <ToastContainer />
      </div>
    )
  }

  return (
    <>
      {/* ACP Permission Dialog — OUTSIDE AvatarWidget (sibling) */}
      <PermissionDialog
        request={chat.permissionRequest}
        onRespond={chat.sendPermissionResponse}
      />

      {/* AvatarWidget — handles FAB/Compact/Fullscreen INTERNALLY */}
      <AvatarWidget
        initialMode="fab"
        customProviders={E2E_PROVIDERS ?? dynamicProviders}
        messages={chat.messages}
        sendMessage={sendWithContext}
        stopResponse={chat.stopResponse}
        isStreaming={chat.isStreaming}
        connected={chat.connected}
        wasConnected={chat.wasConnected}
        initDetail={chat.initDetail}
        error={chat.error}
        diagnostic={chat.diagnostic}
        provider={chat.provider}
        model={chat.model}
        version={chat.version}
        engineState={chat.engineState}
        thinkingSubject={chat.thinking.active ? chat.thinking.subject : ''}
        toolName={chat.toolName}
        pendingFiles={chat.pendingFiles}
        uploading={chat.uploading}
        uploadFile={chat.uploadFile}
        removeFile={chat.removeFile}
        switching={chat.switching}
        activeOptions={chat.activeOptions}
        availableProviders={providers}
        switchProvider={chat.switchProvider}
        onCompactModeRef={compactRef}
        avatars={ALL_AVATARS}
        avatarBasePath="/avatars"
        renderBackground={() => (
          <div className="min-h-screen bg-obsidian flex flex-col">
            <Header />
            <div className="flex flex-1">
              <Sidebar />
              <main className="flex-1 p-6">
                {children}
              </main>
            </div>
            <ToastContainer />
          </div>
        )}
      >
        {/* Fullscreen children — rendered when mode === 'fullscreen' */}
        <div className="h-full flex flex-col overflow-hidden">
          <StatusBar
            connected={chat.connected}
            provider={chat.provider}
            model={chat.model}
            version={chat.version}
            cwd={chat.cwd}
            engineState={chat.engineState as EngineState}
            capabilities={chat.capabilities}
            sessionId={chat.sessionId}
            sessionTitle={chat.sessionTitle}
            cost={chat.cost}
            switching={chat.switching}
            activeOptions={chat.activeOptions}
            availableProviders={providers}
            onSwitch={chat.switchProvider}
            onResume={chat.resumeSession}
            onNewSession={chat.newSession}
            onCompactMode={() => compactRef.current?.()}
          />
          <main className="flex-1 flex flex-col min-h-0">
            {chat.messages.length === 0 && (
              <div className="px-4 pt-3">
                <SuggestionChips onSelect={sendWithContext} />
              </div>
            )}
            <ChatPanel
              messages={chat.messages}
              onSend={sendWithContext}
              onStop={chat.stopResponse}
              onClear={chat.clearHistory}
              isStreaming={chat.isStreaming}
              connected={chat.connected}
              pendingFiles={chat.pendingFiles}
              uploading={chat.uploading}
              onUpload={chat.uploadFile}
              onRemoveFile={chat.removeFile}
            />
          </main>
        </div>
      </AvatarWidget>
    </>
  )
}

export function Layout({ children }: LayoutProps) {
  return (
    <AvatarProvider>
      <LayoutInner>{children}</LayoutInner>
    </AvatarProvider>
  )
}
