import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AuthMethodTabs from '../../../src/renderer/components/onboarding/AuthMethodTabs'

const options = [
  { id: 'direct', label: 'Direct API', enabled: true },
  { id: 'sso', label: 'SSO / OAuth', enabled: false },
]

describe('AuthMethodTabs', () => {
  it('renders all tab labels', () => {
    render(<AuthMethodTabs options={options} activeTab="direct" onTabChange={() => {}} />)
    expect(screen.getAllByText('Direct API').length).toBeGreaterThan(0)
    expect(screen.getAllByText('SSO / OAuth').length).toBeGreaterThan(0)
  })

  it('shows "Coming soon" for disabled tabs', () => {
    render(<AuthMethodTabs options={options} activeTab="direct" onTabChange={() => {}} />)
    expect(screen.getAllByText('Coming soon').length).toBeGreaterThan(0)
  })

  it('calls onTabChange when enabled tab is clicked', () => {
    const onTabChange = vi.fn()
    render(<AuthMethodTabs options={options} activeTab="sso" onTabChange={onTabChange} />)
    fireEvent.click(screen.getAllByText('Direct API')[0])
    expect(onTabChange).toHaveBeenCalledWith('direct')
  })

  it('does NOT call onTabChange when disabled tab is clicked', () => {
    const onTabChange = vi.fn()
    render(<AuthMethodTabs options={options} activeTab="direct" onTabChange={onTabChange} />)
    fireEvent.click(screen.getAllByText('SSO / OAuth')[0])
    expect(onTabChange).not.toHaveBeenCalled()
  })
})
