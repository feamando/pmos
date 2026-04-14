import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import type { SidebarPage } from './components/Sidebar'
import HomePage from './pages/HomePage'
import ConnectionsPage from './pages/ConnectionsPage'
import BrainPage from './pages/BrainPage'
import CCEPage from './pages/CCEPage'
import PluginsPage from './pages/PluginsPage'
import SettingsPanel from './components/settings/SettingsPanel'
import OnboardingPage from './pages/OnboardingPage'
import UserSetupPage from './pages/UserSetupPage'
import BugReportButton from './components/BugReportButton'
import MigrationDialog from './components/MigrationDialog'
import type { ConnectionState, AppMode } from '@shared/types'

type ContentPage = 'home' | 'connections' | 'brain' | 'cce' | 'plugins'

export default function App() {
  const [appMode, setAppMode] = useState<AppMode | null>(null)
  const [activePage, setActivePage] = useState<ContentPage>('home')
  const [connections, setConnections] = useState<ConnectionState[]>([])
  const [loading, setLoading] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [migrationOpen, setMigrationOpen] = useState(false)

  const loadConnections = useCallback(async () => {
    try {
      const conns = await window.api.getConnections()
      setConnections(conns)
    } catch (err) {
      console.error('Failed to load connections:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    async function init() {
      const mode = await window.api.getAppMode()
      setAppMode(mode)

      if (mode === 'connections') {
        const envPath = await window.api.getEnvPath()
        if (!envPath) {
          const candidates = await window.api.detectPmosInstallation()
          if (candidates.length > 0) {
            await window.api.setEnvPath(candidates[0])
          }
        }
        loadConnections()

        // Check for v4.x installation
        try {
          const v4Check = await window.api.detectV4Installation()
          if (v4Check.isV4) setMigrationOpen(true)
        } catch {
          // Migration detection is non-blocking
        }
      } else {
        setLoading(false)
      }
    }
    init()
  }, [loadConnections])

  useEffect(() => {
    window.api.onAppModeChanged((mode) => {
      setAppMode(mode as AppMode)
      if (mode === 'connections') {
        loadConnections()
      }
    })
    return () => {
      window.api.removeAppModeChangedListener()
    }
  }, [loadConnections])

  useEffect(() => {
    window.api.onHealthUpdate((statuses) => {
      setConnections((prev) =>
        prev.map((conn) => {
          const updated = statuses.find((s) => s.connectionId === conn.id)
          return updated ? { ...conn, health: updated } : conn
        })
      )
    })
    return () => {
      window.api.removeHealthUpdateListener()
    }
  }, [])

  const handleNavigate = (page: SidebarPage) => {
    window.api.logTelemetryClick(`page=${page}`)
    if (page === 'settings') {
      setSettingsOpen(true)
    } else {
      setActivePage(page)
      setSettingsOpen(false)
    }
  }

  if (appMode === null) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--text-muted)' }}>
        Loading...
      </div>
    )
  }

  if (appMode === 'onboarding') {
    return <OnboardingPage />
  }

  if (appMode === 'user-setup') {
    return <UserSetupPage />
  }

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar activePage={settingsOpen ? 'settings' : activePage} onNavigate={handleNavigate} />
      <main style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
            Loading...
          </div>
        ) : (
          <>
            {activePage === 'home' && <HomePage />}
            {activePage === 'connections' && <ConnectionsPage connections={connections} onRefresh={loadConnections} />}
            {activePage === 'brain' && <BrainPage />}
            {activePage === 'cce' && <CCEPage />}
            {activePage === 'plugins' && <PluginsPage />}
          </>
        )}

        <BugReportButton />

        <SettingsPanel
          isOpen={settingsOpen}
          onClose={() => setSettingsOpen(false)}
        />

        <MigrationDialog
          isOpen={migrationOpen}
          onClose={() => setMigrationOpen(false)}
        />
      </main>
    </div>
  )
}
