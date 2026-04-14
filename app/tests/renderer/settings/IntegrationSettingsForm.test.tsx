import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import IntegrationSettingsForm from '../../../src/renderer/components/settings/IntegrationSettingsForm'

describe('IntegrationSettingsForm', () => {
  const baseData = {
    integrations: {
      jira: { enabled: true, url: 'https://co.atlassian.net', username: 'me@co.com', tracked_projects: ['GOC', 'TPT'] },
      github: { enabled: false },
    },
  }

  it('renders all 7 integrations', () => {
    render(<IntegrationSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Jira')).toBeDefined()
    expect(screen.getByText('Confluence')).toBeDefined()
    expect(screen.getByText('GitHub')).toBeDefined()
    expect(screen.getByText('Slack')).toBeDefined()
    expect(screen.getByText('Google')).toBeDefined()
    expect(screen.getByText('Statsig')).toBeDefined()
    expect(screen.getByText('Sprint Tracker')).toBeDefined()
  })

  it('shows Jira expanded by default with fields', () => {
    render(<IntegrationSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByDisplayValue('https://co.atlassian.net')).toBeDefined()
    expect(screen.getByDisplayValue('GOC, TPT')).toBeDefined()
  })

  it('shows enabled/disabled status', () => {
    render(<IntegrationSettingsForm data={baseData} onChange={vi.fn()} />)
    const statuses = screen.getAllByText('Enabled')
    expect(statuses.length).toBeGreaterThanOrEqual(1) // Jira enabled
    const disabled = screen.getAllByText('Disabled')
    expect(disabled.length).toBeGreaterThanOrEqual(1) // Others disabled
  })

  it('expands a different integration on click', () => {
    render(<IntegrationSettingsForm data={baseData} onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('GitHub'))
    expect(screen.getByText('Organization')).toBeDefined()
  })

  it('calls onChange with CSV split for tracked_projects', () => {
    const onChange = vi.fn()
    render(<IntegrationSettingsForm data={baseData} onChange={onChange} />)
    const csvInput = screen.getByDisplayValue('GOC, TPT')
    fireEvent.change(csvInput, { target: { value: 'A, B, C' } })
    expect(onChange).toHaveBeenCalledWith('integrations', expect.objectContaining({
      jira: expect.objectContaining({ tracked_projects: ['A', 'B', 'C'] }),
    }))
  })

  it('renders with empty data without crashing', () => {
    render(<IntegrationSettingsForm data={{}} onChange={vi.fn()} />)
    expect(screen.getByText('Jira')).toBeDefined()
  })
})
