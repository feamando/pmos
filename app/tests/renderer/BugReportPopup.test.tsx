import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import BugReportPopup from '../../src/renderer/components/BugReportPopup'

const mockApi = {
  logTelemetryClick: vi.fn(),
  getDiagnosticBundle: vi.fn().mockResolvedValue({ success: true, data: '--- PM-OS Diagnostic ---\nApp Version: 0.10.0' }),
}

Object.defineProperty(window, 'api', { value: mockApi, writable: true })

Object.defineProperty(navigator, 'clipboard', {
  value: { writeText: vi.fn().mockResolvedValue(undefined) },
  writable: true,
})

describe('BugReportPopup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.getDiagnosticBundle.mockResolvedValue({ success: true, data: '--- PM-OS Diagnostic ---\nApp Version: 0.10.0' })
  })

  it('renders nothing when closed', () => {
    const { container } = render(<BugReportPopup isOpen={false} onClose={vi.fn()} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders title "Report a Bug" when open', async () => {
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText('Report a Bug')).toBeDefined()
  })

  it('renders description mentioning #pm-os-support', async () => {
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText(/pm-os-support/)).toBeDefined()
  })

  it('shows diagnostic data in log snippet', async () => {
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/PM-OS Diagnostic/)).toBeDefined()
    })
  })

  it('Copy to Clipboard button triggers clipboard write', async () => {
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText('Copy to Clipboard')).toBeDefined()
    })
    fireEvent.click(screen.getByText('Copy to Clipboard'))
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('PM-OS Diagnostic'))
    })
  })

  it('logs telemetry on copy', async () => {
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    await waitFor(() => screen.getByText('Copy to Clipboard'))
    fireEvent.click(screen.getByText('Copy to Clipboard'))
    await waitFor(() => {
      expect(mockApi.logTelemetryClick).toHaveBeenCalledWith('bug_report_copied')
    })
  })

  it('ESC key closes popup', async () => {
    const onClose = vi.fn()
    render(<BugReportPopup isOpen={true} onClose={onClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('backdrop click closes popup', async () => {
    const onClose = vi.fn()
    const { container } = render(<BugReportPopup isOpen={true} onClose={onClose} />)
    // First child div is the backdrop
    const backdrop = container.firstChild as HTMLElement
    fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalled()
  })

  it('shows loading state while fetching', () => {
    mockApi.getDiagnosticBundle.mockReturnValue(new Promise(() => {})) // Never resolves
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText('Loading diagnostic data...')).toBeDefined()
  })

  it('shows error state on fetch failure', async () => {
    mockApi.getDiagnosticBundle.mockResolvedValue({ success: false, data: '', error: 'Network error' })
    render(<BugReportPopup isOpen={true} onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeDefined()
    })
  })
})
