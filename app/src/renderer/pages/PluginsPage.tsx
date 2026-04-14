import { useState, useEffect, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import PluginCard from '../components/plugins/PluginCard'
import type { PluginInfo } from '@shared/types'

export default function PluginsPage() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [busy, setBusy] = useState(false)

  const loadPlugins = useCallback(async () => {
    setError(null)
    try {
      const [installed, available] = await Promise.all([
        window.api.getInstalledPlugins(),
        window.api.getAvailablePlugins(),
      ])

      // Load health for installed plugins
      const withHealth = await Promise.all(
        installed.map(async (p) => {
          try {
            const health = await window.api.getPluginHealth(p.id)
            return { ...p, health }
          } catch {
            return p
          }
        })
      )

      setPlugins([...withHealth, ...available])
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { loadPlugins() }, [loadPlugins])

  const handleRefresh = () => {
    setRefreshing(true)
    loadPlugins()
  }

  const handleInstall = async (pluginId: string) => {
    setBusy(true)
    window.api.logTelemetryClick(`plugin_install=${pluginId}`)
    try {
      const result = await window.api.installPlugin(pluginId)
      if (!result.success) {
        setError(result.error || 'Install failed')
      }
      await loadPlugins()
    } finally {
      setBusy(false)
    }
  }

  const handleDisable = async (pluginId: string) => {
    setBusy(true)
    window.api.logTelemetryClick(`plugin_disable=${pluginId}`)
    try {
      const result = await window.api.disablePlugin(pluginId)
      if (!result.success) {
        setError(result.error || 'Disable failed')
      }
      await loadPlugins()
    } finally {
      setBusy(false)
    }
  }

  const installed = plugins.filter((p) => p.status === 'installed')
  const available = plugins.filter((p) => p.status === 'available')

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg-onboarding)', overflow: 'auto' }}>
      <div style={{ padding: '32px 32px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, fontFamily: "'Krub', sans-serif" }}>
            Plugins
          </h2>
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
          Manage PM-OS v5.0 plugins
        </p>
      </div>

      <div style={{ padding: '0 32px 32px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13 }}>
            Loading plugins...
          </div>
        ) : error ? (
          <div style={{
            padding: 16, marginBottom: 16, background: '#2a0a0a', border: '1px solid #fecaca',
            borderRadius: 8, fontSize: 13, color: '#dc2626', lineHeight: 1.6,
          }}>
            {error}
          </div>
        ) : null}

        {!loading && (
          <>
            {installed.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <h3 style={{
                  fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: 'var(--text-muted)', marginBottom: 10, fontFamily: "'Inter', sans-serif",
                }}>
                  Installed
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {installed.map((plugin) => (
                    <PluginCard
                      key={plugin.id}
                      plugin={plugin}
                      onDisable={handleDisable}
                      busy={busy}
                    />
                  ))}
                </div>
              </div>
            )}

            {available.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <h3 style={{
                  fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: 'var(--text-muted)', marginBottom: 10, fontFamily: "'Inter', sans-serif",
                }}>
                  Available
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {available.map((plugin) => (
                    <PluginCard
                      key={plugin.id}
                      plugin={plugin}
                      onInstall={handleInstall}
                      busy={busy}
                    />
                  ))}
                </div>
              </div>
            )}

            {installed.length === 0 && available.length === 0 && (
              <div style={{
                textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13,
                fontFamily: "'Inter', sans-serif",
              }}>
                No plugins found. Ensure PM-OS v5.0 is properly installed.
              </div>
            )}

            <div style={{
              marginTop: 8,
              fontSize: 12,
              color: 'var(--text-muted)',
              fontFamily: "'Inter', sans-serif",
              textAlign: 'center',
            }}>
              Plugins also work in Claude Cowork.
            </div>
          </>
        )}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
