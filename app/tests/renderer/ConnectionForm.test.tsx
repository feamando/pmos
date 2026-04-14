import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ConnectionForm from '../../src/renderer/components/ConnectionForm'
import type { ConnectionConfig, HealthStatus } from '../../src/shared/types'

const jiraConfig: ConnectionConfig = {
  id: 'jira',
  name: 'Jira',
  icon: 'jira.svg',
  brandColor: '#0052CC',
  fields: [
    { envKey: 'JIRA_URL', label: 'Jira URL', type: 'text', required: true, placeholder: 'https://your-company.atlassian.net' },
    { envKey: 'JIRA_USERNAME', label: 'Username', type: 'text', required: true, placeholder: 'you@company.com' },
    { envKey: 'JIRA_API_TOKEN', label: 'API Token', type: 'password', required: true, placeholder: 'Your token' },
  ],
  helpText: 'Create an API token at id.atlassian.com',
  testEndpoint: { method: 'GET', urlTemplate: '', headers: {}, authType: 'basic' },
}

const healthyStatus: HealthStatus = { connectionId: 'jira', status: 'healthy' }
const unhealthyStatus: HealthStatus = { connectionId: 'jira', status: 'unhealthy', message: '401 Unauthorized' }

describe('ConnectionForm', () => {
  it('renders correct number of fields for Jira', () => {
    render(
      <ConnectionForm config={jiraConfig} initialValues={{}} healthStatus={healthyStatus} onSave={() => {}} onTest={() => {}} />
    )
    expect(screen.getByText('JIRA_URL')).toBeInTheDocument()
    expect(screen.getByText('JIRA_USERNAME')).toBeInTheDocument()
    expect(screen.getByText('JIRA_API_TOKEN')).toBeInTheDocument()
  })

  it('renders help text', () => {
    render(
      <ConnectionForm config={jiraConfig} initialValues={{}} healthStatus={healthyStatus} onSave={() => {}} onTest={() => {}} />
    )
    expect(screen.getAllByText(/Create an API token/).length).toBeGreaterThan(0)
  })

  it('calls onSave with field values when Save clicked', async () => {
    const onSave = vi.fn()
    const { container } = render(
      <ConnectionForm config={jiraConfig} initialValues={{ JIRA_URL: 'https://test.atlassian.net' }} healthStatus={healthyStatus} onSave={onSave} onTest={() => {}} />
    )
    const buttons = container.querySelectorAll('button')
    // Find the Save button (not Test Connection, not eye toggles)
    const saveButton = Array.from(buttons).find((b) => b.textContent === 'Save')!
    fireEvent.click(saveButton)
    // handleSave is async, wait for it
    await vi.waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ JIRA_URL: 'https://test.atlassian.net' }))
    })
  })

  it('shows error message when health is unhealthy', () => {
    render(
      <ConnectionForm config={jiraConfig} initialValues={{}} healthStatus={unhealthyStatus} onSave={() => {}} onTest={() => {}} />
    )
    expect(screen.getByText('401 Unauthorized')).toBeInTheDocument()
  })

  it('shows Save and Test Connection buttons', () => {
    render(
      <ConnectionForm config={jiraConfig} initialValues={{}} healthStatus={healthyStatus} onSave={() => {}} onTest={() => {}} />
    )
    expect(screen.getAllByText('Save').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Test Connection').length).toBeGreaterThan(0)
  })

  it('shows Copy from Jira button for linked connections', () => {
    const confluenceConfig = { ...jiraConfig, id: 'confluence', linkedTo: 'jira' }
    const onCopy = vi.fn().mockResolvedValue({})
    render(
      <ConnectionForm config={confluenceConfig} initialValues={{}} healthStatus={healthyStatus} onSave={() => {}} onTest={() => {}} onCopyFromJira={onCopy} />
    )
    expect(screen.getByText('Copy from Jira')).toBeInTheDocument()
  })
})
