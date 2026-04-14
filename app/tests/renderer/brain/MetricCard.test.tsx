import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import MetricCard, { getIndicator } from '../../../src/renderer/components/brain/MetricCard'

describe('MetricCard', () => {
  it('renders label, value, and unit', () => {
    render(<MetricCard label="Connectivity" value={85} unit="%" indicator="green" />)
    expect(screen.getByText('Connectivity')).toBeDefined()
    expect(screen.getByText('85')).toBeDefined()
    expect(screen.getByText('%')).toBeDefined()
  })

  it('renders target when provided', () => {
    render(<MetricCard label="Entities" value={347} target={500} indicator="yellow" />)
    expect(screen.getByText(/Target.*500/)).toBeDefined()
  })

  it('renders custom target label', () => {
    render(<MetricCard label="Components" value={3} target={1} targetLabel="1 (fully connected)" indicator="red" />)
    expect(screen.getByText(/1 \(fully connected\)/)).toBeDefined()
  })

  it('renders string value', () => {
    render(<MetricCard label="Diameter" value="N/A" indicator="yellow" />)
    expect(screen.getByText('N/A')).toBeDefined()
  })

  it('does not render target when not provided', () => {
    const { container } = render(<MetricCard label="Test" value={42} indicator="green" />)
    expect(container.textContent).not.toContain('Target')
  })
})

describe('getIndicator', () => {
  it('returns green when value >= 75% of target (higher)', () => {
    expect(getIndicator(80, 100, 'higher')).toBe('green')
    expect(getIndicator(75, 100, 'higher')).toBe('green')
  })

  it('returns yellow when value 50-75% of target (higher)', () => {
    expect(getIndicator(60, 100, 'higher')).toBe('yellow')
    expect(getIndicator(50, 100, 'higher')).toBe('yellow')
  })

  it('returns red when value < 50% of target (higher)', () => {
    expect(getIndicator(40, 100, 'higher')).toBe('red')
  })

  it('returns green when value <= target (lower)', () => {
    expect(getIndicator(5, 10, 'lower')).toBe('green')
    expect(getIndicator(10, 10, 'lower')).toBe('green')
  })

  it('returns yellow when value <= 2x target (lower)', () => {
    expect(getIndicator(15, 10, 'lower')).toBe('yellow')
  })

  it('returns red when value > 2x target (lower)', () => {
    expect(getIndicator(25, 10, 'lower')).toBe('red')
  })
})
