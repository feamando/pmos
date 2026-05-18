import { useState, useEffect } from 'react'
import { SettingsSection } from './SettingsField'
import type { SyncStatus, SyncConfig } from '../../../shared/types'

const GATHER_OPTIONS = [
  { value: 15, label: 'Every 15 minutes' },
  { value: 30, label: 'Every 30 minutes' },
  { value: 60, label: 'Every hour' },
  { value: 120, label: 'Every 2 hours' },
]

const SYNTHESIZE_OPTIONS = [
  { value: 60, label: 'Every hour' },
  { value: 120, label: 'Every 2 hours' },
  { value: 240, label: 'Every 4 hours' },
]

export default function SyncSettingsForm() {
  const [config, setConfig] = useState<SyncConfig | null>(null)
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    window.api.getSyncConfig().then(setConfig)
    window.api.getSyncStatus().then(setStatus)

    window.api.onSyncUpdate((s: SyncStatus) => {
      setStatus(s)
      setSyncing(s.running)
    })

    return () => {
      window.api.removeSyncUpdateListener()
    }
  }, [])

  const handleToggle = async (field: keyof SyncConfig, value: boolean) => {
    if (!config) return
    const updated = { ...config, [field]: value }
    setConfig(updated)
    setSaving(true)
    await window.api.saveSyncConfig(updated)
    setSaving(false)
  }

  const handleInterval = async (field: keyof SyncConfig, value: number) => {
    if (!config) return
    const updated = { ...config, [field]: value }
    setConfig(updated)
    setSaving(true)
    await window.api.saveSyncConfig(updated)
    setSaving(false)
  }

  const handleSyncNow = async () => {
    setSyncing(true)
    window.api.logTelemetryClick('sync_now')
    await window.api.triggerSyncNow()
    setSyncing(false)
  }

  const formatTimeAgo = (ts: number | null) => {
    if (!ts) return 'Never'
    const mins = Math.round((Date.now() - ts) / 60_000)
    if (mins < 1) return 'Just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.round(mins / 60)
    return `${hrs}h ago`
  }

  if (!config) return null

  return (
    <div style={{ paddingTop: 16 }}>
      <SettingsSection title="Background Sync">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '8px 0' }}>

          {/* Enable toggle */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Enable Background Sync</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                Automatically gather data from Jira, Slack, Google, and Brain
              </div>
            </div>
            <button
              onClick={() => handleToggle('enabled', !config.enabled)}
              style={{
                width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
                background: config.enabled ? 'var(--btn-primary-bg)' : '#d1d5db',
                position: 'relative', transition: 'background 0.2s',
              }}
            >
              <div style={{
                width: 18, height: 18, borderRadius: 9, background: 'white',
                position: 'absolute', top: 2,
                left: config.enabled ? 20 : 2, transition: 'left 0.2s',
                boxShadow: '0 1px 2px rgba(0,0,0,0.15)',
              }} />
            </button>
          </div>

          {/* Gather interval */}
          {config.enabled && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                Data Gathering Interval
              </div>
              <select
                value={config.gatherIntervalMinutes}
                onChange={(e) => handleInterval('gatherIntervalMinutes', Number(e.target.value))}
                style={{
                  width: '100%', padding: '8px 12px', fontSize: 13, borderRadius: 4,
                  border: '1px solid var(--border)', background: 'white',
                  fontFamily: "'Source Sans Pro', sans-serif",
                }}
              >
                {GATHER_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </SettingsSection>

      {config.enabled && (
        <SettingsSection title="Context Synthesis">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '8px 0' }}>

            {/* Synthesis toggle */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Enable LLM Synthesis</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  Generate context summaries via Claude API (~$0.02-0.05/run)
                </div>
              </div>
              <button
                onClick={() => handleToggle('enableSynthesis', !config.enableSynthesis)}
                style={{
                  width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
                  background: config.enableSynthesis ? 'var(--btn-primary-bg)' : '#d1d5db',
                  position: 'relative', transition: 'background 0.2s',
                }}
              >
                <div style={{
                  width: 18, height: 18, borderRadius: 9, background: 'white',
                  position: 'absolute', top: 2,
                  left: config.enableSynthesis ? 20 : 2, transition: 'left 0.2s',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.15)',
                }} />
              </button>
            </div>

            {/* Synthesis interval */}
            {config.enableSynthesis && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Synthesis Interval
                </div>
                <select
                  value={config.synthesizeIntervalMinutes}
                  onChange={(e) => handleInterval('synthesizeIntervalMinutes', Number(e.target.value))}
                  style={{
                    width: '100%', padding: '8px 12px', fontSize: 13, borderRadius: 4,
                    border: '1px solid var(--border)', background: 'white',
                    fontFamily: "'Source Sans Pro', sans-serif",
                  }}
                >
                  {SYNTHESIZE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </SettingsSection>
      )}

      <SettingsSection title="Status">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '8px 0' }}>

          {/* Last sync info */}
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
            <span style={{ color: 'var(--text-secondary)' }}>Last Sync</span>
            <span style={{
              fontWeight: 600,
              color: status?.lastSuccess ? '#16a34a' : status?.lastRun ? '#dc2626' : 'var(--text-muted)',
            }}>
              {status?.running ? 'Running...' : formatTimeAgo(status?.lastRun ?? null)}
            </span>
          </div>

          {status?.lastMessage && status.lastMessage !== 'Not started' && (
            <div style={{
              fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {status.lastMessage}
            </div>
          )}

          {/* Sync Now button */}
          <button
            onClick={handleSyncNow}
            disabled={syncing || saving}
            style={{
              padding: '10px 24px', width: '100%',
              background: syncing ? '#9ca3af' : 'var(--btn-primary-bg)',
              color: 'white', border: 'none', borderRadius: 4,
              fontSize: 13, fontWeight: 600,
              cursor: syncing ? 'not-allowed' : 'pointer',
              opacity: syncing ? 0.7 : 1,
              fontFamily: "'Source Sans Pro', sans-serif",
            }}
          >
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </SettingsSection>
    </div>
  )
}
