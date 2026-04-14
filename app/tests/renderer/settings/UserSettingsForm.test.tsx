import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import UserSettingsForm from '../../../src/renderer/components/settings/UserSettingsForm'

describe('UserSettingsForm', () => {
  const baseData = {
    user: { name: 'Jane', email: 'jane@co.com', position: 'PM', tribe: 'NV', team: 'FF', function: 'Product Manager', career_step: 5 },
    personal: {
      learning_capture: { enabled: true, slack_channels: ['#general', '#pm'] },
      career: { current_level: 'Senior', target_level: 'Director', review_cycle: 'H1' },
    },
  }

  it('renders user profile fields with values', () => {
    render(<UserSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByDisplayValue('Jane')).toBeDefined()
    expect(screen.getByDisplayValue('jane@co.com')).toBeDefined()
    expect(screen.getByDisplayValue('PM')).toBeDefined()
  })

  it('renders personal development section', () => {
    render(<UserSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Personal Development')).toBeDefined()
    expect(screen.getByDisplayValue('#general, #pm')).toBeDefined()
    expect(screen.getByDisplayValue('Senior')).toBeDefined()
  })

  it('calls onChange when user field updated', () => {
    const onChange = vi.fn()
    render(<UserSettingsForm data={baseData} onChange={onChange} />)
    fireEvent.change(screen.getByDisplayValue('Jane'), { target: { value: 'Janet' } })
    expect(onChange).toHaveBeenCalledWith('user', expect.objectContaining({ name: 'Janet' }))
  })

  it('renders with empty data without crashing', () => {
    render(<UserSettingsForm data={{}} onChange={vi.fn()} />)
    expect(screen.getByText('User Profile')).toBeDefined()
    expect(screen.getByText('Personal Development')).toBeDefined()
  })
})
