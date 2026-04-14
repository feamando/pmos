import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import BugReportButton from '../../src/renderer/components/BugReportButton'

const mockApi = {
  logTelemetryClick: vi.fn(),
  getDiagnosticBundle: vi.fn().mockResolvedValue({ success: true, data: 'test diagnostic data' }),
}

Object.defineProperty(window, 'api', { value: mockApi, writable: true })

// Mock clipboard
Object.defineProperty(navigator, 'clipboard', {
  value: { writeText: vi.fn().mockResolvedValue(undefined) },
  writable: true,
})

describe('BugReportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders bug icon button', () => {
    render(<BugReportButton />)
    expect(screen.getByTitle('Report a Bug')).toBeDefined()
  })

  it('opens popup on click', async () => {
    render(<BugReportButton />)
    fireEvent.click(screen.getByTitle('Report a Bug'))
    expect(await screen.findByText('Report a Bug')).toBeDefined()
  })

  it('logs telemetry on click', () => {
    render(<BugReportButton />)
    fireEvent.click(screen.getByTitle('Report a Bug'))
    expect(mockApi.logTelemetryClick).toHaveBeenCalledWith('bug_report_opened')
  })
})
