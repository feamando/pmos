import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import WcrSettingsForm from '../../../src/renderer/components/settings/WcrSettingsForm'

describe('WcrSettingsForm', () => {
  const baseData = {
    products: {
      organization: { name: 'Acme Corp', jira_project: 'AC' },
      items: [
        { id: 'p1', name: 'Factor', type: 'brand', market: 'US', status: 'active' },
        { id: 'p2', name: 'EveryPlate', type: 'brand', market: 'Global', status: 'active' },
      ],
    },
    team: {
      manager: { name: 'Boss', email: 'boss@co.com', role: 'VP' },
      reports: [{ id: 'r1', name: 'Alice', email: 'alice@co.com', role: 'PM' }],
      stakeholders: [{ id: 's1', name: 'Bob', email: 'bob@co.com', role: 'Eng Lead', relationship: 'peer' }],
    },
    workspace: { auto_create_folders: true, context_sync: { enabled: true } },
    master_sheet: { enabled: true, spreadsheet_id: 'abc123' },
  }

  it('renders organization fields', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Organization')).toBeDefined()
    expect(screen.getByDisplayValue('Acme Corp')).toBeDefined()
  })

  it('renders products as collapsible items', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Factor')).toBeDefined()
    expect(screen.getByText('EveryPlate')).toBeDefined()
  })

  it('expands product to show details', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    fireEvent.click(screen.getByText('Factor'))
    expect(screen.getByDisplayValue('US')).toBeDefined()
  })

  it('renders manager section', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Manager')).toBeDefined()
    expect(screen.getByDisplayValue('Boss')).toBeDefined()
    expect(screen.getByDisplayValue('boss@co.com')).toBeDefined()
  })

  it('renders direct reports with count', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Direct Reports (1/15)')).toBeDefined()
    expect(screen.getByDisplayValue('Alice')).toBeDefined()
  })

  it('renders stakeholders', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Stakeholders')).toBeDefined()
    expect(screen.getByDisplayValue('Bob')).toBeDefined()
  })

  it('renders workspace and master sheet', () => {
    render(<WcrSettingsForm data={baseData} onChange={vi.fn()} />)
    expect(screen.getByText('Workspace')).toBeDefined()
    expect(screen.getByText('Master Sheet')).toBeDefined()
    expect(screen.getByDisplayValue('abc123')).toBeDefined()
  })

  it('adds a product on click', () => {
    const onChange = vi.fn()
    render(<WcrSettingsForm data={baseData} onChange={onChange} />)
    fireEvent.click(screen.getByText('Add Product'))
    expect(onChange).toHaveBeenCalledWith('products', expect.objectContaining({
      items: expect.arrayContaining([
        expect.objectContaining({ name: '' }),
      ]),
    }))
  })

  it('renders with empty data without crashing', () => {
    render(<WcrSettingsForm data={{}} onChange={vi.fn()} />)
    expect(screen.getByText('Organization')).toBeDefined()
    expect(screen.getByText('Manager')).toBeDefined()
  })
})
