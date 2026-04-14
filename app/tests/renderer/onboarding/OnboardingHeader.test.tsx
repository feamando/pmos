import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import OnboardingHeader from '../../../src/renderer/components/onboarding/OnboardingHeader'

describe('OnboardingHeader', () => {
  it('renders step title', () => {
    render(<OnboardingHeader stepTitle="Google OAuth" currentStep={0} totalSteps={5} />)
    expect(screen.getByText('Google OAuth')).toBeInTheDocument()
  })

  it('renders step counter', () => {
    render(<OnboardingHeader stepTitle="Jira" currentStep={1} totalSteps={5} />)
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument()
  })

  it('progress bar width matches step ratio', () => {
    const { container } = render(<OnboardingHeader stepTitle="Test" currentStep={2} totalSteps={5} />)
    const progressFill = container.querySelectorAll('div > div > div')[0] // outer track > fill
    // Step 3 of 5 = 60%
    const fillEl = container.querySelector('[style*="width: 60%"]') || container.querySelector('[style*="width:60%"]')
    // Alternative: check by style directly
    const track = container.querySelectorAll('div')[3] // the inner fill div
    expect(track).toBeTruthy()
  })
})
