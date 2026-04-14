import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import type { HealthIndicator } from '@shared/types'

interface MetricCardProps {
  label: string
  value: number | string
  unit?: string
  target?: number
  targetLabel?: string
  indicator: HealthIndicator
  compact?: boolean
}

const INDICATOR_CONFIG = {
  green: { icon: CheckCircle, color: '#16a34a' },
  yellow: { icon: AlertTriangle, color: '#ca8a04' },
  red: { icon: XCircle, color: '#dc2626' },
} as const

export function getIndicator(value: number, target: number, direction: 'higher' | 'lower'): HealthIndicator {
  if (direction === 'higher') {
    const ratio = value / target
    if (ratio >= 0.75) return 'green'
    if (ratio >= 0.50) return 'yellow'
    return 'red'
  }
  // Lower is better: invert — green when value <= target, red when value >= 2x target
  if (value <= target) return 'green'
  if (value <= target * 2) return 'yellow'
  return 'red'
}

export default function MetricCard({ label, value, unit, target, targetLabel, indicator, compact }: MetricCardProps) {
  const { icon: Icon, color } = INDICATOR_CONFIG[indicator]

  return (
    <div style={{
      padding: compact ? '12px 14px' : '16px 18px',
      background: '#0a1929',
      border: '1px solid var(--border)',
      borderRadius: 8,
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: "'Inter', sans-serif", fontWeight: 500 }}>
          {label}
        </span>
        <Icon size={14} color={color} />
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontSize: compact ? 20 : 24, fontWeight: 700, fontFamily: "'Krub', sans-serif", color: 'var(--text-primary)' }}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </span>
        {unit && <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: "'Inter', sans-serif" }}>{unit}</span>}
      </div>
      {target !== undefined && (
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: "'Inter', sans-serif" }}>
          Target: {targetLabel || target.toLocaleString()}{unit ? ` ${unit}` : ''}
        </span>
      )}
    </div>
  )
}
