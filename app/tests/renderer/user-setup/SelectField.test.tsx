import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SelectField from '../../../src/renderer/components/user-setup/SelectField'

const options = [
  { value: 'pm', label: 'Product Manager' },
  { value: 'eng', label: 'Engineer' },
  { value: 'design', label: 'Product Designer' },
]

describe('SelectField', () => {
  it('renders label and options', () => {
    render(<SelectField label="Function" value="" onChange={() => {}} options={options} placeholder="Select..." />)
    expect(screen.getAllByText('Function').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Product Manager').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Engineer').length).toBeGreaterThan(0)
  })

  it('shows required indicator', () => {
    const { container } = render(<SelectField label="Function" value="" onChange={() => {}} options={options} required />)
    const stars = Array.from(container.querySelectorAll('span')).filter(s => s.textContent === '*')
    expect(stars.length).toBeGreaterThan(0)
  })

  it('fires onChange with selected value', () => {
    const onChange = vi.fn()
    const { container } = render(<SelectField label="Function" value="" onChange={onChange} options={options} />)
    const select = container.querySelector('select')!
    fireEvent.change(select, { target: { value: 'eng' } })
    expect(onChange).toHaveBeenCalledWith('eng')
  })

  it('shows placeholder option', () => {
    render(<SelectField label="Function" value="" onChange={() => {}} options={options} placeholder="Choose one" />)
    expect(screen.getAllByText('Choose one').length).toBeGreaterThan(0)
  })
})
