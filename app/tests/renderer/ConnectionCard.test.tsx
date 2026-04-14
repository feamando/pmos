import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ConnectionCard from '../../src/renderer/components/ConnectionCard'
import type { ConnectionState } from '../../src/shared/types'

const activeConnection: ConnectionState = {
  id: 'jira',
  name: 'Jira',
  icon: 'jira.svg',
  brandColor: '#0052CC',
  active: true,
  fields: { JIRA_URL: 'https://test.atlassian.net', JIRA_USERNAME: 'user@test.com', JIRA_API_TOKEN: 'token' },
  health: { connectionId: 'jira', status: 'healthy' },
}

const inactiveConnection: ConnectionState = {
  id: 'figma',
  name: 'Figma',
  icon: 'figma.svg',
  brandColor: '#F24E1E',
  active: false,
  fields: {},
  health: { connectionId: 'figma', status: 'unknown' },
}

describe('ConnectionCard', () => {
  it('renders active card with service name', () => {
    render(<ConnectionCard connection={activeConnection} onClick={() => {}} />)
    expect(screen.getAllByText('Jira').length).toBeGreaterThan(0)
  })

  it('renders inactive card with "Not configured" subtitle', () => {
    render(<ConnectionCard connection={inactiveConnection} onClick={() => {}} />)
    expect(screen.getByText('Not configured')).toBeInTheDocument()
  })

  it('calls onClick when card is clicked', () => {
    const onClick = vi.fn()
    const { container } = render(<ConnectionCard connection={activeConnection} onClick={onClick} />)
    fireEvent.click(container.querySelector('button')!)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders with reduced opacity when inactive', () => {
    const { container } = render(<ConnectionCard connection={inactiveConnection} onClick={() => {}} />)
    const button = container.querySelector('button')
    expect(button?.style.opacity).toBe('0.6')
  })
})
