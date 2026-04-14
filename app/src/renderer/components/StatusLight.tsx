import type { HealthStatus } from '@shared/types'

interface StatusLightProps {
  status: HealthStatus['status']
}

export default function StatusLight({ status }: StatusLightProps) {
  const color = status === 'healthy' ? 'var(--status-green)' : 'var(--status-red)'
  const isChecking = status === 'checking'

  return (
    <div
      style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: isChecking ? 'var(--text-muted)' : color,
        flexShrink: 0,
        animation: isChecking ? 'pulse 1.5s ease-in-out infinite' : undefined,
      }}
    />
  )
}
