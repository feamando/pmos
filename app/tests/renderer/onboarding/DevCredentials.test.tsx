import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DevCredentials from '../../../src/renderer/components/onboarding/DevCredentials'

describe('DevCredentials', () => {
  it('renders nothing when not in dev mode', () => {
    const { container } = render(
      <DevCredentials isDevMode={false} onLoadCredentials={vi.fn()} onApplyCredentials={vi.fn()} />
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders Test Credentials button in dev mode', () => {
    render(
      <DevCredentials isDevMode={true} onLoadCredentials={vi.fn()} onApplyCredentials={vi.fn()} />
    )
    expect(screen.getAllByText('Test Credentials').length).toBeGreaterThan(0)
  })

  it('calls onLoadCredentials and onApplyCredentials when clicked', async () => {
    const creds = { JIRA_URL: 'https://test.atlassian.net' }
    const onLoad = vi.fn().mockResolvedValue(creds)
    const onApply = vi.fn()

    render(<DevCredentials isDevMode={true} onLoadCredentials={onLoad} onApplyCredentials={onApply} />)
    fireEvent.click(screen.getAllByText('Test Credentials')[0])

    await waitFor(() => {
      expect(onLoad).toHaveBeenCalledOnce()
      expect(onApply).toHaveBeenCalledWith(creds)
    })
  })
})
