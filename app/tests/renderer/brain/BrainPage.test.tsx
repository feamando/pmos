import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import BrainPage from '../../../src/renderer/pages/BrainPage'

const mockHealthData = {
  connectivityRate: 72,
  entityCount: 347,
  medianRelationships: 2.3,
  graphComponents: 3,
  graphDiameter: 8,
  orphanCount: 28,
  orphanRate: 8.1,
  orphansByReason: [],
  staleEntityRate: 22,
  enrichmentVelocity7d: 6,
  lastEnrichmentTimestamp: null,
  densityScore: 0.64,
  relationshipTypes: [],
  entitiesByType: {},
  targets: {
    connectivityRate: 85,
    entityCount: 500,
    medianRelationships: 3,
    graphComponents: 1,
    orphanRate: 10,
    staleEntityRate: 15,
    enrichmentVelocity7d: 10,
  },
}

const mockApi = {
  getBrainHealth: vi.fn().mockResolvedValue({ success: true, data: mockHealthData, devMode: false }),
  openBrainFolder: vi.fn().mockResolvedValue({ success: true }),
  logTelemetryClick: vi.fn(),
}

beforeEach(() => {
  ;(window as any).api = mockApi
  mockApi.getBrainHealth.mockResolvedValue({ success: true, data: mockHealthData, devMode: false })
  mockApi.openBrainFolder.mockResolvedValue({ success: true })
})

describe('BrainPage', () => {
  it('shows loading state initially', () => {
    // Override to never resolve
    mockApi.getBrainHealth.mockReturnValue(new Promise(() => {}))
    render(<BrainPage />)
    expect(screen.getByText('Analyzing brain health...')).toBeDefined()
  })

  it('renders dashboard after data loads', async () => {
    render(<BrainPage />)
    await waitFor(() => {
      expect(screen.getByText('Connectivity Rate')).toBeDefined()
    })
    expect(screen.getByText('Brain')).toBeDefined()
  })

  it('shows error state on failure', async () => {
    mockApi.getBrainHealth.mockResolvedValue({ success: false, data: null, error: 'Python not found' })
    render(<BrainPage />)
    await waitFor(() => {
      expect(screen.getByText(/Unable to load brain health/)).toBeDefined()
    })
    expect(screen.getByText('Python not found')).toBeDefined()
  })

  it('shows DEV MODE badge when devMode is true', async () => {
    mockApi.getBrainHealth.mockResolvedValue({ success: true, data: mockHealthData, devMode: true })
    render(<BrainPage />)
    await waitFor(() => {
      expect(screen.getByText('DEV MODE')).toBeDefined()
    })
  })
})
