import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SettingsCategoryList from '../../../src/renderer/components/settings/SettingsCategoryList'

describe('SettingsCategoryList', () => {
  it('renders all 5 categories', () => {
    render(<SettingsCategoryList active="user" onChange={vi.fn()} />)
    expect(screen.getByText('User')).toBeDefined()
    expect(screen.getByText('Integrations')).toBeDefined()
    expect(screen.getByText('PM-OS')).toBeDefined()
    expect(screen.getByText('WCR')).toBeDefined()
    expect(screen.getByText('App')).toBeDefined()
  })

  it('calls onChange when category clicked', () => {
    const onChange = vi.fn()
    render(<SettingsCategoryList active="user" onChange={onChange} />)
    fireEvent.click(screen.getByText('PM-OS'))
    expect(onChange).toHaveBeenCalledWith('pmos')
  })
})
