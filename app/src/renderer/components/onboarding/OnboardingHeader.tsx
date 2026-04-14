interface OnboardingHeaderProps {
  stepTitle: string
  currentStep: number
  totalSteps: number
}

export default function OnboardingHeader({ stepTitle, currentStep, totalSteps }: OnboardingHeaderProps) {
  const pct = ((currentStep + 1) / totalSteps) * 100

  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
        <h2 style={{ fontFamily: "'Krub', sans-serif", fontWeight: 700, fontSize: 28, color: 'var(--text-primary)' }}>
          {stepTitle}
        </h2>
        <span style={{ fontSize: 14, color: 'var(--text-muted)', fontFamily: "'Inter', sans-serif" }}>
          Step {currentStep + 1} of {totalSteps}
        </span>
      </div>
      <div style={{ width: '100%', height: 4, background: '#0d2137', borderRadius: 2 }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: 'var(--btn-primary-bg)',
            borderRadius: 2,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
