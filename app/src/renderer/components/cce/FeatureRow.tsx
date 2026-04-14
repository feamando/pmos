import { FolderOpen } from 'lucide-react'
import StepBar from './StepBar'
import { mapStatusToStep, cleanDisplayName } from './status-utils'
import type { CCEFeature } from '@shared/types'

interface FeatureRowProps {
  feature: CCEFeature
  onOpenFolder: (path: string) => void
}

const priorityColors: Record<string, string> = {
  P0: '#dc2626',
  P1: '#f59e0b',
  P2: '#6b7280',
}

export default function FeatureRow({ feature, onOpenFolder }: FeatureRowProps) {
  const { meta } = feature
  const stepIndex = mapStatusToStep(meta.status)

  return (
    <div style={{
      padding: '14px 16px',
      borderBottom: '1px solid var(--border)',
    }}>
      {/* Header: name + meta */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: 13, fontFamily: "'Inter', sans-serif", color: '#ffffff' }}>
            {cleanDisplayName(meta.title || feature.name)}
          </span>
          {meta.priority && (
            <span style={{
              fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
              background: `${priorityColors[meta.priority] || '#6b7280'}15`,
              color: priorityColors[meta.priority] || '#6b7280',
              fontFamily: "'Inter', sans-serif",
            }}>
              {meta.priority}
            </span>
          )}
          {meta.owner && (
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: "'Inter', sans-serif" }}>
              {meta.owner}
            </span>
          )}
        </div>
        {meta.lastUpdated && (
          <span style={{ fontSize: 10, color: '#9ca3af', fontFamily: "'Inter', sans-serif", whiteSpace: 'nowrap' }}>
            {meta.lastUpdated}
          </span>
        )}
      </div>

      {/* Step bar */}
      <div style={{ marginBottom: 8 }}>
        <StepBar stepIndex={stepIndex} compact />
      </div>

      {/* Description */}
      {meta.description && (
        <p style={{
          fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 6px',
          fontFamily: "'Inter', sans-serif", lineHeight: 1.4,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {meta.description}
        </p>
      )}

      {/* Next step + CTA */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {meta.latestAction ? (
          <span style={{ fontSize: 11, color: '#6b7280', fontFamily: "'Inter', sans-serif" }}>
            <strong>Next:</strong> {meta.latestAction.action}
          </span>
        ) : (
          <span />
        )}
        <button
          onClick={() => onOpenFolder(feature.path)}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            fontSize: 11, fontWeight: 500, color: 'var(--hf-green)',
            background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0',
            fontFamily: "'Inter', sans-serif",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
          onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
        >
          <FolderOpen size={12} />
          Go to project folder
        </button>
      </div>
    </div>
  )
}
