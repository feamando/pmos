import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import FeatureRow from './FeatureRow'
import { cleanDisplayName } from './status-utils'
import type { CCEProduct } from '@shared/types'

interface ProductCardProps {
  product: CCEProduct
  onOpenFolder: (path: string) => void
  defaultExpanded?: boolean
}

export default function ProductCard({ product, onOpenFolder, defaultExpanded = false }: ProductCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const featureCount = product.features.length

  return (
    <div style={{
      background: '#0a1929',
      border: '1px solid var(--border)',
      borderRadius: 8,
      overflow: 'hidden',
    }}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = '#0d2137' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'none' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {expanded
            ? <ChevronDown size={16} color="#6b7280" />
            : <ChevronRight size={16} color="#6b7280" />
          }
          <span style={{ fontWeight: 600, fontSize: 14, fontFamily: "'Krub', sans-serif", color: '#ffffff' }}>
            {cleanDisplayName(product.name)}
          </span>
          {product.isWcrProduct && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 4,
              background: '#0a2a1a', color: '#4ade80',
              fontFamily: "'Inter', sans-serif",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
              WCR
            </span>
          )}
          {product.meta.status && (
            <span style={{
              fontSize: 10, color: '#6b7280', fontFamily: "'Inter', sans-serif",
              textTransform: 'capitalize',
            }}>
              {product.meta.status.toLowerCase()}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {product.wcrMeta?.squad && (
            <span style={{ fontSize: 10, color: '#9ca3af', fontFamily: "'Inter', sans-serif" }}>
              {product.wcrMeta.squad}
            </span>
          )}
          <span style={{
            fontSize: 11, color: '#6b7280', fontFamily: "'Inter', sans-serif",
          }}>
            {featureCount} {featureCount === 1 ? 'feature' : 'features'}
          </span>
        </div>
      </button>

      {/* Expanded: product meta + features */}
      {expanded && (
        <div>
          {/* Product meta line */}
          <div style={{
            padding: '0 16px 8px',
            display: 'flex', gap: 12, flexWrap: 'wrap',
            fontSize: 11, color: '#9ca3af', fontFamily: "'Inter', sans-serif",
          }}>
            <span>Org: {product.org}</span>
            {product.wcrMeta?.tribe && <span>Tribe: {product.wcrMeta.tribe}</span>}
            {product.wcrMeta?.market && <span>Market: {product.wcrMeta.market}</span>}
            {product.meta.owner && <span>Owner: {product.meta.owner}</span>}
          </div>

          {/* Feature list */}
          {featureCount === 0 ? (
            <div style={{
              padding: '16px',
              fontSize: 12, color: '#9ca3af',
              fontFamily: "'Inter', sans-serif",
              borderTop: '1px solid var(--border)',
            }}>
              No tracked features
            </div>
          ) : (
            <div style={{ borderTop: '1px solid var(--border)' }}>
              {product.features.map((f) => (
                <FeatureRow key={f.id} feature={f} onOpenFolder={onOpenFolder} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
