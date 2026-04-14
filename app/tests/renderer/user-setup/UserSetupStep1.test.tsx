import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import UserSetupStep1 from '../../../src/renderer/components/user-setup/UserSetupStep1'

// Mock window.api
vi.stubGlobal('window', {
  ...window,
  api: {
    getEnvValues: vi.fn().mockResolvedValue({}),
  },
})

describe('UserSetupStep1', () => {
  it('renders all form fields', () => {
    render(<UserSetupStep1 data={{}} onChange={vi.fn()} />)
    expect(screen.getAllByText('Name').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Email').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Function').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Career Step').length).toBeGreaterThan(0)
  })

  it('renders function dropdown with correct options', () => {
    const { container } = render(<UserSetupStep1 data={{}} onChange={vi.fn()} />)
    const selects = container.querySelectorAll('select')
    expect(selects.length).toBe(2) // function + career step
    const functionSelect = selects[0]
    const optionTexts = Array.from(functionSelect.querySelectorAll('option')).map(o => o.textContent)
    expect(optionTexts).toContain('Product Manager')
    expect(optionTexts).toContain('Engineer')
  })

  it('renders career step dropdown with 1-10', () => {
    const { container } = render(<UserSetupStep1 data={{}} onChange={vi.fn()} />)
    const selects = container.querySelectorAll('select')
    const careerSelect = selects[1]
    const values = Array.from(careerSelect.querySelectorAll('option')).map(o => o.getAttribute('value')).filter(Boolean)
    expect(values).toContain('1')
    expect(values).toContain('10')
    expect(values.length).toBe(10)
  })
})
