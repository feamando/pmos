import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import UserSetupStep5 from '../../../src/renderer/components/user-setup/UserSetupStep5'

vi.stubGlobal('window', {
  ...window,
  api: {
    getEnvValues: vi.fn().mockResolvedValue({}),
  },
})

describe('UserSetupStep5', () => {
  it('renders brain enrichment header', () => {
    render(<UserSetupStep5 data={{}} onChange={vi.fn()} />)
    expect(screen.getAllByText('Enrich PM-OS Brain with your Context').length).toBeGreaterThan(0)
  })

  it('renders all settings fields', () => {
    render(<UserSetupStep5 data={{ _initialized: true }} onChange={vi.fn()} />)
    expect(screen.getAllByText('Target Entity Count').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Hot Topic Limits').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Retention Days').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Meeting Prep Hours').length).toBeGreaterThan(0)
  })

  it('shows helper notes', () => {
    render(<UserSetupStep5 data={{ _initialized: true }} onChange={vi.fn()} />)
    expect(screen.getAllByText('500 minimum recommended').length).toBeGreaterThan(0)
    expect(screen.getAllByText('quick is possible for optimization').length).toBeGreaterThan(0)
  })
})
