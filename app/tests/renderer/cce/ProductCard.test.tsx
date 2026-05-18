import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import ProductCard from '../../../src/renderer/components/cce/ProductCard'
import type { CCEProduct } from '../../../src/shared/types'

afterEach(cleanup)

const mockProduct: CCEProduct = {
  id: 'factor-form',
  name: 'Factor Form Context',
  org: 'new-ventures',
  path: 'new-ventures/factor-form',
  meta: { status: 'ACTIVE', owner: 'Alison Ryan', type: 'brand', lastUpdated: '2026-03-27' },
  features: [
    {
      id: 'ff-shopify', name: 'Factor Form Shopify', path: 'new-ventures/factor-form/ff-shopify',
      meta: { title: 'Factor Form Shopify Context', status: 'In Progress', owner: 'Nikita Gorshkov',
        priority: 'P0', deadline: null, lastUpdated: '2026-03-28', description: 'Shopify migration.',
        actionCount: 3, latestAction: { date: '2026-03-28', action: 'Updated specs', status: 'In Progress' } },
    },
    {
      id: 'ff-b2b', name: 'Factor Canada B2B', path: 'new-ventures/factor-form/ff-b2b',
      meta: { title: 'Factor Canada B2B Context', status: 'Planning', owner: 'Alison Ryan',
        priority: 'P0', deadline: null, lastUpdated: '2026-03-25', description: 'B2B channel strategy.',
        actionCount: 1, latestAction: null },
    },
  ],
  isWcrProduct: true,
  wcrMeta: { squad: 'Factor Form', tribe: 'New Ventures', market: 'US' },
}

describe('ProductCard', () => {
  it('renders product name, org, and feature count', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} />)
    expect(screen.getAllByText('Factor Form').length).toBeGreaterThan(0)
    expect(screen.getByText('2 features')).toBeDefined()
  })

  it('starts collapsed and expands on click', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} />)
    // Features should not be visible when collapsed
    expect(screen.queryByText('Factor Form Shopify')).toBeNull()
    // Click header to expand
    fireEvent.click(screen.getAllByText('Factor Form')[0])
    expect(screen.getByText('Factor Form Shopify')).toBeDefined()
    expect(screen.getByText('Factor Canada B2B')).toBeDefined()
  })

  it('shows WCR badge for highlighted products', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('WCR')).toBeDefined()
  })

  it('shows WCR metadata when expanded', () => {
    render(<ProductCard product={mockProduct} onOpenFolder={vi.fn()} defaultExpanded />)
    expect(screen.getByText(/Tribe: New Ventures/)).toBeDefined()
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
