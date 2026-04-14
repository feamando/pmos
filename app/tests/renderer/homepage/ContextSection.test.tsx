import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ContextSection from '../../../src/renderer/components/homepage/ContextSection'

describe('ContextSection', () => {
  it('renders title and children', () => {
    render(<ContextSection title="Meetings"><div>Meeting content</div></ContextSection>)
    expect(screen.getByText('Meetings')).toBeDefined()
    expect(screen.getByText('Meeting content')).toBeDefined()
  })

  it('renders empty state when empty prop is true', () => {
    render(<ContextSection title="Alerts" empty><div>ignored</div></ContextSection>)
    expect(screen.getByText('Alerts')).toBeDefined()
    expect(screen.getByText('No items found')).toBeDefined()
  })

  it('renders icon when provided', () => {
    render(<ContextSection title="Test" icon={<span data-testid="icon">IC</span>}><p>Body</p></ContextSection>)
    expect(screen.getByTestId('icon')).toBeDefined()
  })
})
