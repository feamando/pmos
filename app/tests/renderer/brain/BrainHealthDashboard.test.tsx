import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import BrainHealthDashboard from '../../../src/renderer/components/brain/BrainHealthDashboard'
import type { BrainHealthData } from '../../../src/shared/types'

const mockData: BrainHealthData = {
  connectivityRate: 72,
  entityCount: 347,
  medianRelationships: 2.3,
  graphComponents: 3,
  graphDiameter: 8,
  orphanCount: 28,
  orphanRate: 8.1,
  orphansByReason: [
    { reason: 'pending_enrichment', count: 15 },
    { reason: 'no_external_data', count: 8 },
  ],
  staleEntityRate: 22,
  enrichmentVelocity7d: 6,
  lastEnrichmentTimestamp: new Date().toISOString(),
  densityScore: 0.64,
  relationshipTypes: [
    { type: 'part_of', count: 89 },
    { type: 'owns', count: 67 },
  ],
  entitiesByType: { project: 142, person: 68, team: 34 },
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

describe('BrainHealthDashboard', () => {
  it('renders all core metric labels', () => {
    render(<BrainHealthDashboard data={mockData} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Connectivity Rate')).toBeDefined()
    expect(screen.getByText('Entity Count')).toBeDefined()
    expect(screen.getByText('Median Relationships')).toBeDefined()
  })

  it('renders graph and health metrics', () => {
    render(<BrainHealthDashboard data={mockData} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Connected Components')).toBeDefined()
    expect(screen.getByText('Graph Diameter')).toBeDefined()
    expect(screen.getByText('Orphan Rate')).toBeDefined()
    expect(screen.getByText('Stale Entities')).toBeDefined()
    expect(screen.getByText('Enrichment Velocity (7d)')).toBeDefined()
  })

  it('renders relationship type distribution', () => {
    render(<BrainHealthDashboard data={mockData} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Relationship Types')).toBeDefined()
    expect(screen.getByText('part of')).toBeDefined()
    expect(screen.getByText('89')).toBeDefined()
  })

  it('renders orphan breakdown by reason', () => {
    render(<BrainHealthDashboard data={mockData} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Orphans by Reason')).toBeDefined()
    expect(screen.getByText('pending enrichment')).toBeDefined()
    expect(screen.getByText('15')).toBeDefined()
  })

  it('renders entity type pills', () => {
    render(<BrainHealthDashboard data={mockData} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Entities by Type')).toBeDefined()
    expect(screen.getByText('project')).toBeDefined()
    expect(screen.getByText('142')).toBeDefined()
  })

  it('renders CTA button and calls onOpenFolder on click', () => {
    const onOpenFolder = vi.fn()
    render(<BrainHealthDashboard data={mockData} onOpenFolder={onOpenFolder} />)
    const cta = screen.getByText('Explore your Knowledgebase')
    expect(cta).toBeDefined()
    fireEvent.click(cta)
    expect(onOpenFolder).toHaveBeenCalledOnce()
  })

  it('renders last enrichment timestamp', () => {
    render(<BrainHealthDashboard data={mockData} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Last Enrichment')).toBeDefined()
    expect(screen.getByText('Less than 1 hour ago')).toBeDefined()
  })
})
