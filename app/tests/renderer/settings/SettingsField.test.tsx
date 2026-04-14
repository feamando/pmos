import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SettingsField, SettingsToggle, SettingsSelect, SettingsSection } from '../../../src/renderer/components/settings/SettingsField'

describe('SettingsField', () => {
  it('renders label and input with value', () => {
    render(<SettingsField label="Username" value="john" onChange={vi.fn()} />)
    expect(screen.getByText('Username')).toBeDefined()
    expect(screen.getByDisplayValue('john')).toBeDefined()
  })

  it('calls onChange when input changes', () => {
    const onChange = vi.fn()
    render(<SettingsField label="Name" value="" onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } })
    expect(onChange).toHaveBeenCalledWith('test')
  })

  it('renders placeholder and note', () => {
    render(<SettingsField label="URL" value="" onChange={vi.fn()} placeholder="https://..." note="Enter full URL" />)
    expect(screen.getByPlaceholderText('https://...')).toBeDefined()
    expect(screen.getByText('Enter full URL')).toBeDefined()
  })
})

describe('SettingsToggle', () => {
  it('renders label and checkbox state', () => {
    render(<SettingsToggle label="Enabled" checked={true} onChange={vi.fn()} />)
    expect(screen.getByText('Enabled')).toBeDefined()
    const checkbox = screen.getByRole('checkbox') as HTMLInputElement
    expect(checkbox.checked).toBe(true)
  })

  it('calls onChange on toggle', () => {
    const onChange = vi.fn()
    render(<SettingsToggle label="Active" checked={false} onChange={onChange} />)
    fireEvent.click(screen.getByRole('checkbox'))
    expect(onChange).toHaveBeenCalledWith(true)
  })
})

describe('SettingsSelect', () => {
  const options = [
    { value: 'a', label: 'Alpha' },
    { value: 'b', label: 'Beta' },
  ]

  it('renders options', () => {
    render(<SettingsSelect label="Choice" value="a" onChange={vi.fn()} options={options} />)
    expect(screen.getByText('Alpha')).toBeDefined()
    expect(screen.getByText('Beta')).toBeDefined()
  })

  it('calls onChange on selection', () => {
    const onChange = vi.fn()
    render(<SettingsSelect label="Choice" value="a" onChange={onChange} options={options} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'b' } })
    expect(onChange).toHaveBeenCalledWith('b')
  })
})

describe('SettingsSection', () => {
  it('renders title and children', () => {
    render(<SettingsSection title="My Section"><div>child content</div></SettingsSection>)
    expect(screen.getByText('My Section')).toBeDefined()
    expect(screen.getByText('child content')).toBeDefined()
  })
})
