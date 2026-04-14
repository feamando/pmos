import { X } from 'lucide-react'
import ConnectionForm from './ConnectionForm'
import StatusLight from './StatusLight'
import { getConnectionConfig } from '@shared/connection-configs'
import type { ConnectionState, HealthStatus } from '@shared/types'

interface ConnectionPanelProps {
  connectionId: string | null
  connections: ConnectionState[]
  onClose: () => void
  onSaved: () => void
}

export default function ConnectionPanel({ connectionId, connections, onClose, onSaved }: ConnectionPanelProps) {
  const isOpen = connectionId !== null
  const connection = connections.find((c) => c.id === connectionId)
  const config = connectionId ? getConnectionConfig(connectionId) : undefined

  const handleSave = async (values: Record<string, string>) => {
    if (!connectionId) return
    const result = await window.api.saveConnection(connectionId, values)
    if (result.success) {
      onSaved()
    }
  }

  const handleTest = async () => {
    if (!connectionId) return
    const result = await window.api.testConnection(connectionId)
    // Return result first so ConnectionForm can display it,
    // then refresh connections in background (don't block result display)
    setTimeout(() => onSaved(), 500)
    return result
  }

  const handleCopyFromJira = async (): Promise<Record<string, string>> => {
    return window.api.copyFromJira(connectionId!)
  }

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0,0,0,0.05)',
            zIndex: 10,
          }}
        />
      )}

      {/* Panel */}
      <div style={{
        position: 'absolute',
        right: 0,
        top: 0,
        bottom: 0,
        width: 380,
        background: '#0a1929',
        boxShadow: isOpen ? '-4px 0 24px rgba(0,0,0,0.12)' : 'none',
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.2s ease-out',
        zIndex: 20,
        overflowY: 'auto',
        padding: isOpen ? 28 : 0,
      }}>
        {config && connection && (
          <>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 'var(--radius-lg)',
                  background: connection.active ? config.brandColor : '#9ca3af',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <span style={{ color: 'white', fontWeight: 700, fontSize: 11, textTransform: 'uppercase' }}>
                    {config.name.slice(0, 4)}
                  </span>
                </div>
                <h3 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{config.name}</h3>
                <StatusLight status={connection.health.status} />
                <span style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: connection.health.status === 'healthy' ? 'var(--status-green)' : 'var(--status-red)',
                }}>
                  {connection.health.status === 'healthy' ? 'Connected' : 'Not connected'}
                </span>
              </div>
              <button
                onClick={onClose}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 'var(--radius)',
                  border: '1px solid var(--border)',
                  background: '#0a1929',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              >
                <X size={14} color="var(--text-secondary)" />
              </button>
            </div>

            <ConnectionForm
              config={config}
              initialValues={connection.fields}
              healthStatus={connection.health}
              onSave={handleSave}
              onTest={handleTest}
              onCopyFromJira={config.linkedTo ? handleCopyFromJira : undefined}
            />
          </>
        )}
      </div>
    </>
  )
}
