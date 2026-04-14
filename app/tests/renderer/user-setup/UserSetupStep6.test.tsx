import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import UserSetupStep6 from '../../../src/renderer/components/user-setup/UserSetupStep6'

afterEach(cleanup)

describe('UserSetupStep6', () => {
  it('renders WCR settings sections', () => {
    render(<UserSetupStep6 data={{}} onChange={vi.fn()} />)
    expect(screen.getByText('Organization')).toBeDefined()
    expect(screen.getByText('Products')).toBeDefined()
    expect(screen.getByText('Manager')).toBeDefined()
  })

  it('renders helper text', () => {
    render(<UserSetupStep6 data={{}} onChange={vi.fn()} />)
    expect(screen.getByText(/Configure your organization/)).toBeDefined()
  })

  it('calls onChange when section data changes', () => {
    const onChange = vi.fn()
    const { container } = render(<UserSetupStep6 data={{}} onChange={onChange} />)
    const inputs = container.querySelectorAll('input')
    // First input is Organization Name
    fireEvent.change(inputs[0], { target: { value: 'Test Org' } })
    expect(onChange).toHaveBeenCalled()
  })

  it('renders Add Product button', () => {
    render(<UserSetupStep6 data={{}} onChange={vi.fn()} />)
    expect(screen.getByText('Add Product')).toBeDefined()
  })
})
