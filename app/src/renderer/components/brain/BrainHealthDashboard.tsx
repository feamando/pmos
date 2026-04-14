import { FolderOpen } from 'lucide-react'
import MetricCard, { getIndicator } from './MetricCard'
import type { BrainHealthData } from '@shared/types'

interface BrainHealthDashboardProps {
  data: BrainHealthData
  onOpenFolder: () => void
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return 'Never'
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  if (diffHours < 1) return 'Less than 1 hour ago'
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

const barStyle = (pct: number, color: string): React.CSSProperties => ({
  height: 6,
  borderRadius: 3,
  background: color,
  width: `${Math.min(pct, 100)}%`,
  transition: 'width 0.3s ease',
})

export default function BrainHealthDashboard({ data, onOpenFolder }: BrainHealthDashboardProps) {
  const t = data.targets

  // Compute max for relationship type distribution bar widths
  const maxRelCount = data.relationshipTypes.length > 0
    ? Math.max(...data.relationshipTypes.map((r) => r.count))
    : 1

  // Max for orphan breakdown
  const maxOrphanCount = data.orphansByReason.length > 0
    ? Math.max(...data.orphansByReason.map((o) => o.count))
    : 1

  return (
    <div>
      {/* Core Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <MetricCard
          label="Connectivity Rate"
          value={data.connectivityRate}
          unit="%"
          target={t.connectivityRate}
          indicator={getIndicator(data.connectivityRate, t.connectivityRate, 'higher')}
        />
        <MetricCard
          label="Entity Count"
          value={data.entityCount}
          target={t.entityCount}
          indicator={getIndicator(data.entityCount, t.entityCount, 'higher')}
        />
        <MetricCard
          label="Median Relationships"
          value={data.medianRelationships}
          target={t.medianRelationships}
          indicator={getIndicator(data.medianRelationships, t.medianRelationships, 'higher')}
        />
      </div>

      {/* Graph & Orphan Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <MetricCard
          label="Connected Components"
          value={data.graphComponents}
          target={t.graphComponents}
          targetLabel={`${t.graphComponents} (fully connected)`}
          indicator={getIndicator(data.graphComponents, t.graphComponents, 'lower')}
        />
        <MetricCard
          label="Graph Diameter"
          value={data.graphDiameter ?? 'N/A'}
          indicator={data.graphDiameter === null ? 'yellow' : data.graphDiameter <= 10 ? 'green' : data.graphDiameter <= 20 ? 'yellow' : 'red'}
        />
        <MetricCard
          label="Density Score"
          value={data.densityScore}
          indicator={getIndicator(data.densityScore, 0.7, 'higher')}
        />
      </div>

      {/* Health Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        <MetricCard
          label="Orphan Rate"
          value={data.orphanRate}
          unit="%"
          target={t.orphanRate}
          targetLabel={`≤${t.orphanRate}`}
          indicator={getIndicator(data.orphanRate, t.orphanRate, 'lower')}
        />
        <MetricCard
          label="Stale Entities"
          value={data.staleEntityRate}
          unit="%"
          target={t.staleEntityRate}
          targetLabel={`≤${t.staleEntityRate}`}
          indicator={getIndicator(data.staleEntityRate, t.staleEntityRate, 'lower')}
        />
        <MetricCard
          label="Enrichment Velocity (7d)"
          value={data.enrichmentVelocity7d}
          unit="entities"
          target={t.enrichmentVelocity7d}
          indicator={getIndicator(data.enrichmentVelocity7d, t.enrichmentVelocity7d, 'higher')}
        />
      </div>

      {/* Last Enrichment */}
      <div style={{
        padding: '12px 16px', background: '#0a1929', border: '1px solid var(--border)', borderRadius: 8,
        marginBottom: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: "'Inter', sans-serif" }}>
          Last Enrichment
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>
          {formatTimestamp(data.lastEnrichmentTimestamp)}
        </span>
      </div>

      {/* Two-column: Relationship Distribution + Orphan Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* Relationship Type Distribution */}
        <div style={{ background: '#0a1929', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
          <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 12px', fontFamily: "'Krub', sans-serif" }}>
            Relationship Types
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.relationshipTypes.map((rt) => (
              <div key={rt.type}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 12, fontFamily: "'Inter', sans-serif", color: 'var(--text-secondary)' }}>
                    {rt.type.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>
                    {rt.count}
                  </span>
                </div>
                <div style={{ height: 6, background: '#0d2137', borderRadius: 3 }}>
                  <div style={barStyle((rt.count / maxRelCount) * 100, '#ff0088')} />
                </div>
              </div>
            ))}
            {data.relationshipTypes.length === 0 && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No relationships found</span>
            )}
          </div>
        </div>

        {/* Orphan Breakdown */}
        <div style={{ background: '#0a1929', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
          <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 12px', fontFamily: "'Krub', sans-serif" }}>
            Orphans by Reason
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.orphansByReason.map((ob) => (
              <div key={ob.reason}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 12, fontFamily: "'Inter', sans-serif", color: 'var(--text-secondary)' }}>
                    {ob.reason.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>
                    {ob.count}
                  </span>
                </div>
                <div style={{ height: 6, background: '#0d2137', borderRadius: 3 }}>
                  <div style={barStyle((ob.count / maxOrphanCount) * 100, '#ca8a04')} />
                </div>
              </div>
            ))}
            {data.orphansByReason.length === 0 && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No orphans found</span>
            )}
          </div>
        </div>
      </div>

      {/* Entity Type Distribution */}
      <div style={{ background: '#0a1929', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 12px', fontFamily: "'Krub', sans-serif" }}>
          Entities by Type
        </h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {Object.entries(data.entitiesByType)
            .sort(([, a], [, b]) => b - a)
            .map(([type, count]) => (
              <div key={type} style={{
                padding: '6px 12px', background: '#0d2137', borderRadius: 16,
                fontSize: 12, fontFamily: "'Inter', sans-serif",
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <span style={{ color: 'var(--text-secondary)' }}>{type}</span>
                <span style={{ fontWeight: 700 }}>{count}</span>
              </div>
            ))
          }
        </div>
      </div>

      {/* Explore CTA */}
      <button
        onClick={onOpenFolder}
        style={{
          width: '100%',
          padding: '14px 20px',
          background: 'var(--btn-primary-bg)',
          color: 'var(--btn-primary-text)',
          border: 'none',
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 600,
          cursor: 'pointer',
          fontFamily: "'Inter', sans-serif",
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
        }}
      >
        <FolderOpen size={16} />
        Explore your Knowledgebase
      </button>
    </div>
  )
}
