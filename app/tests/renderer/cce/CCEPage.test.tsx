import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import CCEPage from '../../../src/renderer/pages/CCEPage'
import { getSyntheticCCEData } from '../../../src/main/cce/cce-data'

afterEach(cleanup)

const mockCCEData = getSyntheticCCEData()

const mockApi = {
  getCCEProjects: vi.fn().mockResolvedValue({ success: true, data: mockCCEData, devMode: false }),
  openFeatureFolder: vi.fn().mockResolvedValue({ success: true }),
  logTelemetryClick: vi.fn(),
}

beforeEach(() => {
  ;(window as any).api = mockApi
  mockApi.getCCEProjects.mockResolvedValue({ success: true, data: mockCCEData, devMode: false })
  mockApi.openFeatureFolder.mockResolvedValue({ success: true })
})

describe('CCEPage', () => {
  it('shows loading state initially', () => {
    mockApi.getCCEProjects.mockReturnValue(new Promise(() => {}))
    render(<CCEPage />)
    expect(screen.getByText('Loading projects...')).toBeDefined()
  })

  it('renders summary header with counts after load', async () => {
    render(<CCEPage />)
    await waitFor(() => {
      expect(screen.getByText(/4 products/)).toBeDefined()
    })
    expect(screen.getByText(/12 features/)).toBeDefined()
  })

  it('renders ProductCard for each product', async () => {
    render(<CCEPage />)
    await waitFor(() => {
      expect(screen.getAllByText('Growth Platform').length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText('Analytics Suite').length).toBeGreaterThan(0)
  })

  it('shows error state on failure', async () => {
    mockApi.getCCEProjects.mockResolvedValue({ success: false, data: null, error: 'Generator failed' })
    render(<CCEPage />)
    await waitFor(() => {
      expect(screen.getByText(/Unable to load CCE projects/)).toBeDefined()
    })
    expect(screen.getByText('Generator failed')).toBeDefined()
  })

  it('shows DEV MODE badge when devMode is true', async () => {
    mockApi.getCCEProjects.mockResolvedValue({ success: true, data: mockCCEData, devMode: true })
    render(<CCEPage />)
    await waitFor(() => {
      expect(screen.getByText('DEV MODE')).toBeDefined()
    })
  })
})
