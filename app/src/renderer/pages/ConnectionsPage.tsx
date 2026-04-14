import { useState } from 'react'
import ConnectionGrid from '../components/ConnectionGrid'
import ConnectionPanel from '../components/ConnectionPanel'
import type { ConnectionState } from '@shared/types'

interface ConnectionsPageProps {
  connections: ConnectionState[]
  onRefresh: () => void
}

export default function ConnectionsPage({ connections, onRefresh }: ConnectionsPageProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg-onboarding)' }}>
      <div style={{ padding: 32 }}>
        <h2 style={{ fontSize: 22, marginBottom: 6 }}>Connections</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 24 }}>
          Manage your service integrations
        </p>
        <ConnectionGrid
          connections={connections}
          onCardClick={(id) => setSelectedId(id)}
          dimmed={selectedId !== null}
        />
      </div>

      <ConnectionPanel
        connectionId={selectedId}
        connections={connections}
        onClose={() => setSelectedId(null)}
        onSaved={() => {
          onRefresh()
        }}
      />
    </div>
  )
}
