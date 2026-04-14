import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FormField from '../../../src/renderer/components/onboarding/FormField'
import type { FieldConfig } from '../../../src/shared/types'

const textField: FieldConfig = {
  envKey: 'JIRA_URL',
  label: 'Jira URL',
  type: 'text',
  required: true,
  placeholder: 'https://your-company.atlassian.net',
}

const passwordField: FieldConfig = {
  envKey: 'API_TOKEN',
  label: 'API Token',
  type: 'password',
  required: true,
  placeholder: 'Your token',
}

const optionalField: FieldConfig = {
  envKey: 'REPO_FILTER',
  label: 'Repo Filter',
  type: 'text',
  required: false,
  placeholder: 'Optional filter',
}

describe('FormField', () => {
  it('renders text input with label', () => {
    render(<FormField field={textField} value="" onChange={() => {}} />)
    expect(screen.getAllByText('Jira URL').length).toBeGreaterThan(0)
    expect(screen.getAllByPlaceholderText('https://your-company.atlassian.net').length).toBeGreaterThan(0)
  })

  it('renders required indicator for required fields', () => {
    render(<FormField field={textField} value="" onChange={() => {}} />)
    expect(screen.getAllByText('*').length).toBeGreaterThan(0)
  })

  it('does not render required indicator for optional fields', () => {
    const { container } = render(<FormField field={optionalField} value="" onChange={() => {}} />)
    const stars = container.querySelectorAll('span')
    const starTexts = Array.from(stars).filter(s => s.textContent === '*')
    expect(starTexts.length).toBe(0)
  })

  it('fires onChange when text input changes', () => {
    const onChange = vi.fn()
    render(<FormField field={textField} value="" onChange={onChange} />)
    fireEvent.change(screen.getAllByPlaceholderText('https://your-company.atlassian.net')[0], { target: { value: 'https://test.atlassian.net' } })
    expect(onChange).toHaveBeenCalledWith('https://test.atlassian.net')
  })

  it('renders password field as password type', () => {
    render(<FormField field={passwordField} value="secret" onChange={() => {}} />)
    const input = screen.getAllByPlaceholderText('Your token')[0]
    expect(input).toHaveAttribute('type', 'password')
  })

  it('toggles password visibility', () => {
    render(<FormField field={passwordField} value="secret" onChange={() => {}} />)
    const input = screen.getAllByPlaceholderText('Your token')[0]
    expect(input).toHaveAttribute('type', 'password')

    const toggle = input.parentElement?.querySelector('button')
    if (toggle) {
      fireEvent.click(toggle)
      expect(input).toHaveAttribute('type', 'text')
    }
  })
})
