import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { PacksPage } from './components/modules/PacksPage'
import { PackDetailPage } from './components/modules/PackDetailPage'
import { DownloadsPage } from './components/modules/DownloadsPage'
import { BrowsePage } from './components/modules/BrowsePage'
import { SettingsPage } from './components/modules/SettingsPage'
import { ProfilesPage } from './components/modules/ProfilesPage'
import { InventoryPage } from './components/modules/InventoryPage'
import { AvatarPage } from './components/modules/AvatarPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<PacksPage />} />
        <Route path="/packs/:packName" element={<PackDetailPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/profiles" element={<ProfilesPage />} />
        <Route path="/downloads" element={<DownloadsPage />} />
        <Route path="/browse" element={<BrowsePage />} />
        <Route path="/avatar" element={<AvatarPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}
