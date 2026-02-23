import { ReactNode } from 'react'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { ToastContainer } from '../ui/Toast'
import { AvatarProvider } from '../avatar/AvatarProvider'
import { AvatarFab } from '../avatar/AvatarFab'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <AvatarProvider>
      <div className="min-h-screen bg-obsidian flex flex-col">
        <Header />
        <div className="flex flex-1">
          <Sidebar />
          <main className="flex-1 p-6">
            {children}
          </main>
        </div>
        <ToastContainer />
        <AvatarFab />
      </div>
    </AvatarProvider>
  )
}
