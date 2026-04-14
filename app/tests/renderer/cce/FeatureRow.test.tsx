import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import FeatureRow from '../../../src/renderer/components/cce/FeatureRow'
import type { CCEFeature } from '../../../src/shared/types'

afterEach(cleanup)

const mockFeature: CCEFeature = {
  id: 'test-feature',
  name: 'Test Feature',
  path: 'new-ventures/test-product/test-feature',
  meta: {
    title: 'Test Feature Context',
    status: 'In Progress',
    owner: 'Test User',
    priority: 'P0',
    deadline: '2026-04-15',
    lastUpdated: '2026-03-28',
    description: 'A test feature description for unit testing.',
    actionCount: 3,
    latestAction: { date: '2026-03-28', action: 'Updated specs', status: 'In Progress' },
  },
}

describe('FeatureRow', () => {
  it('renders feature name, owner, and priority badge', () => {
    render(<FeatureRow feature={mockFeature} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Test Feature')).toBeDefined()
    expect(screen.getByText('Test User')).toBeDefined()
    expect(screen.getByText('P0')).toBeDefined()
  })

  it('renders description text', () => {
    render(<FeatureRow feature={mockFeature} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('A test feature description for unit testing.')).toBeDefined()
  })

  it('renders next step from latest action', () => {
    render(<FeatureRow feature={mockFeature} onOpenFolder={vi.fn()} />)
    expect(screen.getByText(/Updated specs/)).toBeDefined()
  })

  it('CTA button calls onOpenFolder with correct path', () => {
    const onOpenFolder = vi.fn()
    render(<FeatureRow feature={mockFeature} onOpenFolder={onOpenFolder} />)
    fireEvent.click(screen.getByText('Go to project folder'))
    expect(onOpenFolder).toHaveBeenCalledWith('new-ventures/test-product/test-feature')
  })

  it('handles missing optional fields gracefully', () => {
    const minimal: CCEFeature = {
      id: 'minimal',
      name: 'Minimal Feature',
      path: 'org/product/minimal',
      meta: {
        title: 'Minimal', status: 'To Do', owner: null, priority: null,
        deadline: null, lastUpdated: null, description: null, actionCount: 0, latestAction: null,
      },
    }
    render(<FeatureRow feature={minimal} onOpenFolder={vi.fn()} />)
    expect(screen.getByText('Minimal')).toBeDefined()
    expect(screen.getByText('Go to project folder')).toBeDefined()
  })

  it('renders step bar with correct status', () => {
    render(<FeatureRow feature={mockFeature} onOpenFolder={vi.fn()} />)
    // In Progress maps to step 3, so Discovery/Planning/Context v1 should show as labels
    expect(screen.getByText('Discovery')).toBeDefined()
    expect(screen.getByText('In Progress')).toBeDefined()
  })
})
