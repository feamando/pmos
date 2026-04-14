interface OnboardingNavProps {
  onContinue: () => void
  onSkip: () => void
  onBack: () => void
  isFirstStep: boolean
  isLastStep: boolean
  continueDisabled: boolean
  continueLabel?: string
}

export default function OnboardingNav({
  onContinue,
  onSkip,
  onBack,
  isFirstStep,
  isLastStep,
  continueDisabled,
  continueLabel,
}: OnboardingNavProps) {
  const label = continueLabel || (isLastStep ? 'Complete Setup' : 'Continue')

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 0',
      borderTop: '1px solid #ff008844',
      position: 'sticky',
      bottom: 0,
      background: 'var(--bg-onboarding, #FEF9EF)',
      zIndex: 10,
      marginTop: 'auto',
    }}>
      <div>
        {!isFirstStep && (
          <button
            onClick={onBack}
            style={{
              padding: '10px 24px',
              background: 'transparent',
              color: 'var(--text-primary)',
              border: '1px solid var(--btn-secondary-border)',
              borderRadius: 4,
              fontSize: 14,
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Back
          </button>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button
          onClick={onContinue}
          disabled={continueDisabled}
          style={{
            padding: '10px 28px',
            background: 'var(--btn-primary-bg)',
            color: 'var(--btn-primary-text)',
            border: 'none',
            borderRadius: 4,
            fontSize: 14,
            fontWeight: 600,
            cursor: continueDisabled ? 'not-allowed' : 'pointer',
            opacity: continueDisabled ? 0.5 : 1,
            fontFamily: "'Inter', sans-serif",
          }}
        >
          {label}
        </button>
        <button
          onClick={onSkip}
          style={{
            padding: '10px 4px',
            background: 'none',
            border: 'none',
            color: 'var(--btn-tertiary-text)',
            fontSize: 14,
            cursor: 'pointer',
            fontFamily: "'Inter', sans-serif",
          }}
        >
          Skip
        </button>
      </div>
    </div>
  )
}
