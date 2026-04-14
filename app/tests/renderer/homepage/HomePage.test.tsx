import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import HomePage from '../../../src/renderer/pages/HomePage'

const mockContext = {
  date: '2026-03-30',
  generatedAt: '2026-03-30 10:31 CET',
  userName: 'Nikita',
  meetings: [
    { time: '09:30–10:00', event: 'Daily Standup' },
    { time: '14:00–15:00', event: 'Sprint Review' },
  ],
  actionItems: [
    { owner: 'Alice', text: 'Review PR #42', group: 'Today' },
    { owner: 'Bob', text: 'Deploy to staging', group: 'This Week' },
  ],
  alerts: [
    { priority: 'P0', title: 'API Outage', description: 'Service returning 500 errors' },
  ],
}

const mockApi = {
  getDailyContext: vi.fn().mockResolvedValue({ success: true, data: mockContext, devMode: false }),
  logTelemetryClick: vi.fn(),
}

beforeEach(() => {
  ;(window as any).api = mockApi
  mockApi.getDailyContext.mockResolvedValue({ success: true, data: mockContext, devMode: false })
})

describe('HomePage', () => {
  it('shows loading state initially', () => {
    mockApi.getDailyContext.mockReturnValue(new Promise(() => {}))
    render(<HomePage />)
    expect(screen.getByText('Loading daily context...')).toBeDefined()
  })

  it('renders welcome message with user name', async () => {
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText('Welcome Nikita')).toBeDefined()
    })
  })

  it('renders meetings section', async () => {
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText('Meetings')).toBeDefined()
      expect(screen.getByText('Daily Standup')).toBeDefined()
      expect(screen.getByText('Sprint Review')).toBeDefined()
    })
  })

  it('renders action items grouped', async () => {
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText('Open Action Items')).toBeDefined()
      expect(screen.getByText(/Review PR #42/)).toBeDefined()
    })
  })

  it('renders alerts with priority badge', async () => {
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText('Alerts')).toBeDefined()
      expect(screen.getByText('P0')).toBeDefined()
      expect(screen.getByText('API Outage')).toBeDefined()
    })
  })

  it('shows error state on failure', async () => {
    mockApi.getDailyContext.mockResolvedValue({ success: false, data: null, error: 'No files found' })
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText(/No daily context available/)).toBeDefined()
    })
  })

  it('shows DEV MODE badge', async () => {
    mockApi.getDailyContext.mockResolvedValue({ success: true, data: mockContext, devMode: true })
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText('DEV MODE')).toBeDefined()
    })
  })
})
