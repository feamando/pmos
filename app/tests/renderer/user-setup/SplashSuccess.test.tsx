import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import UserSetupStep7 from '../../../src/renderer/components/user-setup/UserSetupStep7'

vi.stubGlobal('window', {
  ...window,
  api: {
    validateConfig: vi.fn().mockResolvedValue({ valid: true, errors: [], warnings: [] }),
    completeUserSetup: vi.fn(),
  },
})

describe('UserSetupStep7 (SplashSuccess)', () => {
  it('renders success message', async () => {
    render(<UserSetupStep7 />)
    expect(screen.getAllByText('Your settings are stored').length).toBeGreaterThan(0)
  })

  it('renders the /session boot command', () => {
    render(<UserSetupStep7 />)
    expect(screen.getAllByText('/session boot').length).toBeGreaterThan(0)
  })

  it('shows countdown text', () => {
    render(<UserSetupStep7 />)
    expect(screen.getAllByText(/Continuing in/).length).toBeGreaterThan(0)
  })
})
