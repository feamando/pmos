import { STEP_LABELS } from './status-utils'

interface StepBarProps {
  stepIndex: number  // 0-4 for steps, -1 for To Do, -2 for Deprioritized
  compact?: boolean
}

const COLORS = {
  completed: '#16a34a',
  active: '#16a34a',
  pending: '#d1d5db',
  deprioritized: '#dc2626',
  deprioritizedBg: '#2a0a0a',
}

export default function StepBar({ stepIndex, compact }: StepBarProps) {
  if (stepIndex === -2) {
    return (
      <span style={{
        display: 'inline-block',
        fontSize: compact ? 10 : 11,
        fontWeight: 600,
        padding: compact ? '1px 6px' : '2px 8px',
        borderRadius: 4,
        background: COLORS.deprioritizedBg,
        color: COLORS.deprioritized,
        fontFamily: "'Inter', sans-serif",
      }}>
        Deprioritized
      </span>
    )
  }

  const circleSize = compact ? 10 : 12
  const connectorHeight = compact ? 2 : 2
  const fontSize = compact ? 9 : 10
  const gap = compact ? 2 : 4

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
      {STEP_LABELS.map((label, i) => {
        const isCompleted = stepIndex >= 0 && i < stepIndex
        const isActive = stepIndex >= 0 && i === stepIndex
        const isPending = stepIndex < 0 || i > stepIndex

        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap }}>
              {/* Circle */}
              <div style={{
                width: circleSize,
                height: circleSize,
                borderRadius: '50%',
                background: isCompleted ? COLORS.completed : isActive ? COLORS.completed : '#0a1929',
                border: `2px solid ${isCompleted || isActive ? COLORS.completed : COLORS.pending}`,
                boxSizing: 'border-box',
                position: 'relative',
              }}>
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    top: '50%', left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: circleSize - 6,
                    height: circleSize - 6,
                    borderRadius: '50%',
                    background: 'white',
                  }} />
                )}
              </div>
              {/* Label */}
              <span style={{
                fontSize,
                color: isCompleted || isActive ? '#ffffff' : '#778899',
                fontFamily: "'Inter', sans-serif",
                whiteSpace: 'nowrap',
                fontWeight: isActive ? 600 : 400,
              }}>
                {label}
              </span>
            </div>
            {/* Connector */}
            {i < STEP_LABELS.length - 1 && (
              <div style={{
                width: compact ? 16 : 24,
                height: connectorHeight,
                background: isCompleted ? COLORS.completed : COLORS.pending,
                marginTop: circleSize / 2 - connectorHeight / 2,
                alignSelf: 'flex-start',
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
