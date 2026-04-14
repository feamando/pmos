import { Settings, Power, Download } from 'lucide-react'
import type { PluginInfo } from '@shared/types'

interface PluginCardProps {
  plugin: PluginInfo
  onInstall?: (pluginId: string) => void
  onDisable?: (pluginId: string) => void
  busy?: boolean
}

const statusColors: Record<string, { bg: string; text: string; label: string }> = {
  installed: { bg: '#0a2a1a', text: '#4ade80', label: 'Installed' },
  available: { bg: '#0a1a2e', text: '#60a5fa', label: 'Available' },
  disabled: { bg: '#2a0a0a', text: '#f87171', label: 'Disabled' },
}

export default function PluginCard({ plugin, onInstall, onDisable, busy }: PluginCardProps) {
  const statusStyle = statusColors[plugin.status] || statusColors.available
  const isBase = plugin.id === 'pm-os-base'

  return (
    <div style={{
      background: '#0a1929',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: 16,
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 16,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{
            fontFamily: "'Inter', sans-serif",
            fontWeight: 600,
            fontSize: 14,
            color: '#ffffff',
          }}>
            {plugin.name}
          </span>
          <span style={{
            fontSize: 11,
            color: 'var(--text-muted)',
            fontFamily: "'Inter', sans-serif",
          }}>
            v{plugin.version}
          </span>
          <span style={{
            fontSize: 10,
            fontWeight: 600,
            padding: '1px 6px',
            borderRadius: 4,
            background: statusStyle.bg,
            color: statusStyle.text,
            fontFamily: "'Inter', sans-serif",
          }}>
            {statusStyle.label}
          </span>
        </div>

        <p style={{
          margin: '4px 0 8px',
          fontSize: 13,
          color: 'var(--text-secondary)',
          fontFamily: "'Inter', sans-serif",
          lineHeight: 1.4,
        }}>
          {plugin.description}
        </p>

        <div style={{
          display: 'flex',
          gap: 12,
          fontSize: 11,
          color: 'var(--text-muted)',
          fontFamily: "'Inter', sans-serif",
        }}>
          {plugin.commands.length > 0 && (
            <span>{plugin.commands.length} command{plugin.commands.length !== 1 ? 's' : ''}</span>
          )}
          {plugin.skills.length > 0 && (
            <span>{plugin.skills.length} skill{plugin.skills.length !== 1 ? 's' : ''}</span>
          )}
          {plugin.dependencies.length > 0 && (
            <span>Depends on: {plugin.dependencies.join(', ')}</span>
          )}
        </div>

        {plugin.health && plugin.health.message && (
          <div style={{
            marginTop: 6,
            fontSize: 11,
            color: plugin.health.status === 'healthy' ? '#166534' : plugin.health.status === 'degraded' ? '#92400e' : '#dc2626',
            fontFamily: "'Inter', sans-serif",
          }}>
            {plugin.health.message}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        {plugin.status === 'installed' && !isBase && (
          <button
            onClick={() => onDisable?.(plugin.id)}
            disabled={busy}
            title="Disable"
            style={{
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 500,
              border: '1px solid var(--border)',
              borderRadius: 4,
              background: '#0a1929',
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontFamily: "'Inter', sans-serif",
              color: '#aabbcc',
            }}
          >
            <Power size={12} />
            Disable
          </button>
        )}
        {plugin.status === 'available' && (
          <button
            onClick={() => onInstall?.(plugin.id)}
            disabled={busy}
            title="Install"
            style={{
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 600,
              border: 'none',
              borderRadius: 4,
              background: 'black',
              color: 'white',
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontFamily: "'Inter', sans-serif",
            }}
          >
            <Download size={12} />
            Install
          </button>
        )}
      </div>
    </div>
  )
}
