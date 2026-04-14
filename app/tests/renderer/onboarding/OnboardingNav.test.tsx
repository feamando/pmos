import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import OnboardingNav from '../../../src/renderer/components/onboarding/OnboardingNav'

const defaultProps = {
  onContinue: vi.fn(),
  onSkip: vi.fn(),
  onBack: vi.fn(),
  isFirstStep: false,
  isLastStep: false,
  continueDisabled: false,
}

describe('OnboardingNav', () => {
  it('renders Continue, Skip, and Back buttons', () => {
    render(<OnboardingNav {...defaultProps} />)
    expect(screen.getAllByText('Continue').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Skip').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Back').length).toBeGreaterThan(0)
  })

  it('hides Back on first step', () => {
    const { container } = render(<OnboardingNav {...defaultProps} isFirstStep={true} />)
    const backButtons = container.querySelectorAll('button')
    const backTexts = Array.from(backButtons).filter(b => b.textContent === 'Back')
    expect(backTexts.length).toBe(0)
  })

  it('shows "Complete Setup" on last step with Skip still available', () => {
    render(<OnboardingNav {...defaultProps} isLastStep={true} />)
    expect(screen.getAllByText('Complete Setup').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Skip').length).toBeGreaterThan(0)
  })

  it('fires onContinue when clicked', () => {
    const onContinue = vi.fn()
    render(<OnboardingNav {...defaultProps} onContinue={onContinue} />)
    fireEvent.click(screen.getAllByText('Continue')[0])
    expect(onContinue).toHaveBeenCalledOnce()
  })

  it('fires onSkip when clicked', () => {
    const onSkip = vi.fn()
    render(<OnboardingNav {...defaultProps} onSkip={onSkip} />)
    fireEvent.click(screen.getAllByText('Skip')[0])
    expect(onSkip).toHaveBeenCalledOnce()
  })

  it('fires onBack when clicked', () => {
    const onBack = vi.fn()
    render(<OnboardingNav {...defaultProps} onBack={onBack} />)
    fireEvent.click(screen.getAllByText('Back')[0])
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('disables Continue when continueDisabled is true', () => {
    render(<OnboardingNav {...defaultProps} continueDisabled={true} />)
    const btn = screen.getAllByText('Continue')[0]
    expect(btn).toBeDisabled()
  })

  it('uses custom continueLabel', () => {
    render(<OnboardingNav {...defaultProps} continueLabel="Save & Next" />)
    expect(screen.getAllByText('Save & Next').length).toBeGreaterThan(0)
  })
})
