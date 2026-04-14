import { useState, useEffect, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import BrainHealthDashboard from '../components/brain/BrainHealthDashboard'
import type { BrainHealthData } from '@shared/types'

export default function BrainPage() {
  const [healthData, setHealthData] = useState<BrainHealthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [devMode, setDevMode] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const loadHealth = useCallback(async () => {
    setError(null)
    try {
      const result = await window.api.getBrainHealth()
      if (result.success && result.data) {
        setHealthData(result.data)
        setDevMode(result.devMode ?? false)
      } else {
        setError(result.error || 'Failed to load brain health')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { loadHealth() }, [loadHealth])

  useEffect(() => {
    if (error) window.api.logTelemetryClick('error:brain_health_failed')
  }, [error])

  const handleRefresh = () => {
    setRefreshing(true)
    loadHealth()
  }

  const handleOpenFolder = async () => {
    await window.api.openBrainFolder()
  }

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg-onboarding)', overflow: 'auto' }}>
      <div style={{ padding: '32px 32px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, fontFamily: "'Krub', sans-serif" }}>Brain</h2>
            {devMode && (
              <span style={{
                fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                background: '#fef3c7', color: '#92400e', fontFamily: "'Inter', sans-serif",
              }}>
                DEV MODE
              </span>
            )}
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh"
            style={{
              width: 32, height: 32, borderRadius: 6, border: '1px solid var(--border)',
              background: '#0a1929', display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: refreshing ? 'not-allowed' : 'pointer', opacity: refreshing ? 0.5 : 1,
            }}
          >
            <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          </button>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 0, fontFamily: "'Inter', sans-serif" }}>
          Knowledge graph health and metrics
        </p>
      </div>

      <div style={{ padding: '0 32px 32px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13 }}>
            Analyzing brain health...
          </div>
        ) : error ? (
          <div style={{
            padding: 20, background: '#2a0a0a', border: '1px solid #fecaca', borderRadius: 8,
            fontSize: 13, color: '#dc2626', lineHeight: 1.6,
          }}>
            Unable to load brain health metrics. Ensure PM-OS is properly configured and Python tools are available.
            <div style={{ marginTop: 8, fontSize: 12, color: '#778899' }}>{error}</div>
          </div>
        ) : healthData ? (
          <BrainHealthDashboard data={healthData} onOpenFolder={handleOpenFolder} />
        ) : null}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
