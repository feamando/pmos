import { useState, useEffect, useCallback } from 'react'
import { Calendar, CheckSquare, AlertTriangle, XCircle } from 'lucide-react'
import ContextSection from '../components/homepage/ContextSection'
import type { DailyContextData } from '@shared/types'

function formatDate(dateStr?: string): string {
  const d = dateStr ? new Date(dateStr + 'T00:00:00') : new Date()
  return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
}

const priorityStyle = (priority: string): React.CSSProperties => ({
  display: 'inline-block',
  padding: '1px 6px',
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 700,
  fontFamily: "'Inter', sans-serif",
  background: priority === 'P0' ? '#2a0a0a' : '#2a2200',
  color: priority === 'P0' ? '#dc2626' : '#ca8a04',
  marginRight: 8,
  flexShrink: 0,
})

export default function HomePage() {
  const [contextData, setContextData] = useState<DailyContextData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [devMode, setDevMode] = useState(false)

  const loadContext = useCallback(async () => {
    setError(null)
    try {
      const result = await window.api.getDailyContext()
      if (result.success && result.data) {
        setContextData(result.data)
        setDevMode(result.devMode ?? false)
      } else {
        setError(result.error || 'Failed to load daily context')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadContext() }, [loadContext])

  useEffect(() => {
    if (error) window.api.logTelemetryClick('error:homepage_context_failed')
  }, [error])

  const userName = contextData?.userName || 'there'

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg-onboarding)', overflow: 'auto' }}>
      <div style={{ padding: '32px 32px 24px' }}>
        {/* Welcome header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, fontFamily: "'Krub', sans-serif" }}>
            Welcome {userName}
          </h2>
          {devMode && (
            <span style={{
              fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
              background: '#fef3c7', color: '#92400e', fontFamily: "'Inter', sans-serif",
            }}>
              DEV MODE
            </span>
          )}
        </div>
        <p style={{
          color: 'var(--text-secondary)', fontSize: 14, marginBottom: 0,
          fontFamily: "'Inter', sans-serif", lineHeight: 1.5,
        }}>
          Today is {formatDate()}{contextData ? ', your last daily context is below.' : '.'}
        </p>
      </div>

      <div style={{ padding: '0 32px 32px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13 }}>
            Loading daily context...
          </div>
        ) : error ? (
          <div style={{
            padding: 20, background: '#2a0a0a', border: '1px solid #fecaca', borderRadius: 8,
            fontSize: 13, color: '#dc2626', lineHeight: 1.6,
          }}>
            No daily context available. Run a context update from PM-OS to generate one.
            <div style={{ marginTop: 8, fontSize: 12, color: '#778899' }}>{error}</div>
          </div>
        ) : contextData ? (
          <>
            {/* Context date badge */}
            {contextData.generatedAt && (
              <div style={{
                fontSize: 12, color: 'var(--text-muted)', marginBottom: 16,
                fontFamily: "'Inter', sans-serif",
              }}>
                Context from {contextData.date} ({contextData.generatedAt})
              </div>
            )}

            {/* Alerts */}
            <ContextSection
              title="Alerts"
              icon={<AlertTriangle size={16} color="#ca8a04" />}
              empty={contextData.alerts.length === 0}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {contextData.alerts.map((alert, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
                    <span style={priorityStyle(alert.priority)}>{alert.priority}</span>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "'Inter', sans-serif", color: 'var(--text-primary)' }}>
                        {alert.title}
                      </div>
                      {alert.description && (
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2, lineHeight: 1.5, fontFamily: "'Inter', sans-serif" }}>
                          {alert.description}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ContextSection>

            {/* Meetings */}
            <ContextSection
              title="Meetings"
              icon={<Calendar size={16} color="var(--text-secondary)" />}
              empty={contextData.meetings.length === 0}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {contextData.meetings.map((m, i) => (
                  <div key={i} style={{
                    display: 'flex', gap: 12, padding: '8px 0',
                    borderBottom: i < contextData.meetings.length - 1 ? '1px solid #0d2137' : 'none',
                  }}>
                    <span style={{
                      fontSize: 12, color: 'var(--text-muted)', fontFamily: "'Inter', sans-serif",
                      minWidth: 90, flexShrink: 0, fontWeight: 500,
                    }}>
                      {m.time || '—'}
                    </span>
                    <span style={{ fontSize: 13, fontFamily: "'Inter', sans-serif", color: 'var(--text-primary)' }}>
                      {m.event}
                    </span>
                  </div>
                ))}
              </div>
            </ContextSection>

            {/* Action Items */}
            <ContextSection
              title="Open Action Items"
              icon={<CheckSquare size={16} color="var(--text-secondary)" />}
              empty={contextData.actionItems.length === 0}
            >
              {(() => {
                const groups = ['Today', 'This Week', 'This Sprint']
                return groups.map((group) => {
                  const items = contextData.actionItems.filter((a) => a.group === group)
                  if (items.length === 0) return null
                  return (
                    <div key={group} style={{ marginBottom: 14 }}>
                      <div style={{
                        fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)',
                        fontFamily: "'Inter', sans-serif", marginBottom: 6,
                        textTransform: 'uppercase', letterSpacing: 0.5,
                      }}>
                        {group}
                      </div>
                      {items.map((item, i) => (
                        <div key={i} style={{
                          display: 'flex', alignItems: 'flex-start', gap: 8, padding: '5px 0',
                          fontSize: 13, fontFamily: "'Inter', sans-serif",
                        }}>
                          <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
                            <XCircle size={14} style={{ opacity: 0.3, marginTop: 2 }} />
                          </span>
                          <span>
                            <span style={{ fontWeight: 600 }}>{item.owner}:</span>{' '}
                            <span style={{ color: 'var(--text-primary)' }}>{item.text}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  )
                })
              })()}
            </ContextSection>
          </>
        ) : null}
      </div>
    </div>
  )
}
