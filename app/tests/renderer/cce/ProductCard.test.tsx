import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import ProductCard from '../../../src/renderer/components/cce/ProductCard'
import type { CCEProduct } from '../../../src/shared/types'

afterEach(cleanup)

const mockProduct: CCEProduct = {
  id: 'growth-platform',
  name: 'Growth Platform Context',
  org: 'platform',
  path: 'platform/growth-platform',
  meta: { status: 'ACTIVE', owner: 'Alex Johnson', type: 'brand', lastUpdated: '2026-03-27' },
  features: [
    {
      id: 'gp-shopify', name: 'Growth Shopify', path: 'platform/growth-platform/gp-shopify',
      meta: { title: 'Growth Shopify Context', status: 'In Progress', owner: 'Jordan Lee',
        priority: 'P0', deadline: null, lastUpdated: '2026-03-28', description: 'Shopify migration.',
        actionCount: 3, latestAction: { date: '2026-03-28', action: 'Updated specs', status: 'In Progress' } },
    },
    {
      id: 'gp-b2b', name: 'Growth Canada B2B', path: 'platform/growth-platform/gp-b2b',
      meta: { title: 'Growth Canada B2B Context', status: 'Planning', owner: 'Alex Johnson',
        priority: 'P0', deadline: null, lastUpdated: '2026-03-25', description: 'B2B channel strategy.',
        actionCount: 1, latestAction: null },
    },
  ],
  isWcrProduct: true,
  wcrMeta: { squad: 'Growth Squad', tribe: 'Platform', market: 'US' },
}

describe('ProductCard', () => {
  it('renders product name, org, and feature count', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} />)
    expect(screen.getAllByText('Growth Platform').length).toBeGreaterThan(0)
    expect(screen.getByText('2 features')).toBeDefined()
  })

  it('starts collapsed and expands on click', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} />)
    // Features should not be visible when collapsed
    expect(screen.queryByText('Growth Shopify')).toBeNull()
    // Click header to expand
    fireEvent.click(screen.getAllByText('Growth Platform')[0])
    expect(screen.getByText('Growth Shopify')).toBeDefined()
    expect(screen.getByText('Growth Canada B2B')).toBeDefined()
  })

  it('shows WCR badge for highlighted products', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('WCR')).toBeDefined()
  })

  it('shows WCR metadata when expanded', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} defaultExpanded />)
    expect(screen.getByText(/Tribe: Platform/)).toBeDefined()
    expect(screen.getByText(/Market: US/)).toBeDefined()
  })

  it('hides WCR badge for non-WCR products', () => {
    const nonWcr: CCEProduct = { ...mockProduct, isWcrProduct: false, wcrMeta: undefined }
    render(<ProductCard product={nonWcr} onOpenFolder={vi.fn()} />)
    expect(screen.queryByText('WCR')).toBeNull()
  })

  it('renders FeatureRow for each feature when expanded', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} defaultExpanded />)
    const ctaButtons = screen.getAllByText('Go to project folder')
    expect(ctaButtons).toHaveLength(2)
  })
})
