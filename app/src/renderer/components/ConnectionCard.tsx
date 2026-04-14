import { Pencil, Plus } from 'lucide-react'
import StatusLight from './StatusLight'
import type { ConnectionState } from '@shared/types'

interface ConnectionCardProps {
  connection: ConnectionState
  onClick: () => void
}

export default function ConnectionCard({ connection, onClick }: ConnectionCardProps) {
  const { active, name, brandColor, health, fields } = connection
  const subtitle = active
    ? (fields.JIRA_URL || fields.GITHUB_ORG || fields.FIGMA_ACCESS_TOKEN ? getSubtitle(connection) : 'Configured')
    : 'Not configured'

  return (
    <button
      onClick={onClick}
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: '#0a1929',
        cursor: 'pointer',
        opacity: active ? 1 : 0.6,
        transition: 'box-shadow 0.15s, opacity 0.15s',
        width: '100%',
        textAlign: 'left',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)' }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none' }}
    >
      <div style={{
        width: 36,
        height: 36,
        borderRadius: 'var(--radius)',
        background: active ? brandColor : '#9ca3af',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ color: 'white', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>
          {name.slice(0, 4)}
        </span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: active ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
          {name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {subtitle}
        </div>
      </div>

      <StatusLight status={health.status} />

      <div style={{ flexShrink: 0, width: 20, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {active ? <Pencil size={14} color="var(--text-muted)" /> : <Plus size={14} color="var(--text-muted)" />}
      </div>
    </button>
  )
}

function getSubtitle(connection: ConnectionState): string {
  const { id, fields } = connection
  if (id === 'jira' || id === 'confluence') return fields.JIRA_URL?.replace(/https?:\/\//, '').replace(/\/$/, '') || 'Configured'
  if (id === 'github') return fields.GITHUB_ORG || 'Configured'
  if (id === 'slack') return 'Connected'
  if (id === 'google') return 'OAuth configured'
  if (id === 'figma') return 'Connected'
  return 'Configured'
}
