import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import StepBar from '../../../src/renderer/components/cce/StepBar'

afterEach(cleanup)

describe('StepBar', () => {
  it('renders all 5 step labels', () => {
    render(<StepBar stepIndex={2} />)
    expect(screen.getByText('Discovery')).toBeDefined()
    expect(screen.getByText('Planning')).toBeDefined()
    expect(screen.getByText('Context v1')).toBeDefined()
    expect(screen.getByText('In Progress')).toBeDefined()
    expect(screen.getByText('Complete')).toBeDefined()
  })

  it('renders step labels for To Do (index -1)', () => {
    render(<StepBar stepIndex={-1} />)
    // All 5 labels should still render
    expect(screen.getByText('Discovery')).toBeDefined()
    expect(screen.getByText('Complete')).toBeDefined()
  })

  it('renders Deprioritized badge for index -2', () => {
    render(<StepBar stepIndex={-2} />)
    expect(screen.getByText('Deprioritized')).toBeDefined()
    // Should NOT render step labels
    expect(screen.queryByText('Discovery')).toBeNull()
  })

  it('renders in compact mode', () => {
    render(<StepBar stepIndex={3} compact />)
    expect(screen.getByText('Discovery')).toBeDefined()
    expect(screen.getByText('In Progress')).toBeDefined()
  })

  it('renders correctly for Complete (index 4)', () => {
    render(<StepBar stepIndex={4} />)
    expect(screen.getByText('Complete')).toBeDefined()
  })

  it('renders correctly for Discovery (index 0)', () => {
    render(<StepBar stepIndex={0} />)
    expect(screen.getByText('Discovery')).toBeDefined()
  })
})
