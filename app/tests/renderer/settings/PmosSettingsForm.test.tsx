import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PmosSettingsForm from '../../../src/renderer/components/settings/PmosSettingsForm'

const mockApi = {
  getPmosPath: vi.fn().mockResolvedValue('/Users/test/pm-os'),
  setPmosPath: vi.fn().mockResolvedValue({ success: true }),
}

beforeEach(() => {
  ;(window as any).api = mockApi
})

describe('PmosSettingsForm', () => {
  const baseData = {
    pm_os: { fpf_enabled: true, confucius_enabled: true, ralph_enabled: false, auto_update: true },
    brain: { entity_types: ['person', 'team'], hot_topics_limit: 10, workers: 5 },
    context: { retention_days: 30, include: { jira: true, github: false, slack: true, calendar: true } },
    sessions: { auto_save_interval: 5, max_sessions: 50 },
    meeting_prep: { prep_hours: 24, default_depth: 'standard', preferred_model: 'bedrock' },
    spec_machine: { enabled: true, default_repo: 'my-repo' },
  }

  it('renders core feature toggles', () => {
    render(<PmosSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Core Features')).toBeDefined()
    expect(screen.getByText('FPF (First Principles Framework)')).toBeDefined()
    expect(screen.getByText('Confucius (Session Notes)')).toBeDefined()
    expect(screen.getByText('Ralph (Workflow Engine)')).toBeDefined()
  })

  it('renders brain section with CSV entity types', () => {
    render(<PmosSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Brain')).toBeDefined()
    expect(screen.getByDisplayValue('person, team')).toBeDefined()
  })

  it('renders context include toggles', () => {
    render(<PmosSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Include Jira')).toBeDefined()
    expect(screen.getByText('Include GitHub')).toBeDefined()
  })

  it('renders meeting prep settings', () => {
    render(<PmosSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Meeting Prep')).toBeDefined()
    expect(screen.getByText('Task Inference')).toBeDefined()
    expect(screen.getByText('Section Defaults')).toBeDefined()
    expect(screen.getByText('Meeting Type Max Words')).toBeDefined()
  })

  it('renders spec machine section', () => {
    render(<PmosSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Spec Machine')).toBeDefined()
    expect(screen.getByDisplayValue('my-repo')).toBeDefined()
  })

  it('calls onChange for brain entity_types CSV update', () => {
    const onChange = vi.fn()
    render(<PmosSettingsForm data={baseData} onChange={onChange} />)
    fireEvent.change(screen.getByDisplayValue('person, team'), { target: { value: 'person, project' } })
    expect(onChange).toHaveBeenCalledWith('brain', expect.objectContaining({
      entity_types: ['person', 'project'],
    }))
  })

  it('renders with empty data without crashing', () => {
    render(<PmosSettingsForm data={{}} onChange={vi.fn()} />)
    expect(screen.getByText('Core Features')).toBeDefined()
    expect(screen.getByText('Brain')).toBeDefined()
  })
})
