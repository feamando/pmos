import { useState, useEffect, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import ProductCard from '../components/cce/ProductCard'
import type { CCEHubData } from '@shared/types'

export default function CCEPage() {
  const [data, setData] = useState<CCEHubData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [devMode, setDevMode] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const loadProjects = useCallback(async () => {
    setError(null)
    try {
      const result = await window.api.getCCEProjects()
      if (result.success && result.data) {
        // Sort: WCR products first, then alphabetical
        const sorted = [...result.data.products].sort((a, b) => {
          if (a.isWcrProduct !== b.isWcrProduct) return a.isWcrProduct ? -1 : 1
          return a.name.localeCompare(b.name)
        })
        setData({ ...result.data, products: sorted })
        setDevMode(result.devMode ?? false)
      } else {
        setError(result.error || 'Failed to load projects')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { loadProjects() }, [loadProjects])

  useEffect(() => {
    if (error) window.api.logTelemetryClick('error:cce_load_failed')
  }, [error])

  const handleRefresh = () => {
    setRefreshing(true)
    loadProjects()
  }

  const handleOpenFolder = async (featurePath: string) => {
    await window.api.openFeatureFolder(featurePath)
  }

  return (
    <div style={{ position: 'relative', height: '100%', background: 'var(--bg-onboarding)', overflow: 'auto' }}>
      <div style={{ padding: '32px 32px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ fontSize: 22, fontWeight: 700, margin: 0, fontFamily: "'Krub', sans-serif" }}>
              Context Creation Engine
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

        {data && (
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 0, fontFamily: "'Inter', sans-serif" }}>
            {data.summary.products} products &middot; {data.summary.features} features &middot; {data.summary.active} active
          </p>
        )}
      </div>

      <div style={{ padding: '0 32px 32px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13 }}>
            Loading projects...
          </div>
        ) : error ? (
          <div style={{
            padding: 20, background: '#2a0a0a', border: '1px solid #fecaca', borderRadius: 8,
            fontSize: 13, color: '#dc2626', lineHeight: 1.6,
          }}>
            Unable to load CCE projects. Ensure PM-OS is properly configured and feature index generator is available.
            <div style={{ marginTop: 8, fontSize: 12, color: '#778899' }}>{error}</div>
          </div>
        ) : data && data.products.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13,
            fontFamily: "'Inter', sans-serif",
          }}>
            No projects found. Add feature context files to user/products/ to get started.
          </div>
        ) : data ? (
          data.products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onOpenFolder={handleOpenFolder}
              defaultExpanded={product.isWcrProduct}
            />
          ))
        ) : null}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
