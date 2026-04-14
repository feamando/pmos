import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AppSettingsForm from '../../../src/renderer/components/settings/AppSettingsForm'

const mockApi = {
  getAppVersion: vi.fn().mockResolvedValue({ version: '0.8.0-20260331', electronVersion: '41.1.0' }),
  getPmosPath: vi.fn().mockResolvedValue('/Users/test/pm-os'),
  startUpdate: vi.fn().mockResolvedValue(undefined),
  checkForUpdates: vi.fn().mockResolvedValue({ available: false, currentVersion: '0.8.0', latestVersion: '0.8.0' }),
  onUpdateProgress: vi.fn(),
  removeUpdateProgressListener: vi.fn(),
  openBrainFolder: vi.fn(),
  logTelemetryClick: vi.fn(),
}

Object.defineProperty(window, 'api', { value: mockApi, writable: true })

describe('AppSettingsForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.getAppVersion.mockResolvedValue({ version: '0.8.0-20260331', electronVersion: '41.1.0' })
    mockApi.getPmosPath.mockResolvedValue('/Users/test/pm-os')
  })

  it('renders version info', async () => {
    render(<AppSettingsForm />)
    await waitFor(() => {
      expect(screen.getByText('0.8.0-20260331')).toBeDefined()
    })
  })

  it('renders electron version', async () => {
    render(<AppSettingsForm />)
    await waitFor(() => {
      expect(screen.getByText('41.1.0')).toBeDefined()
    })
  })

  it('renders credits', async () => {
    render(<AppSettingsForm />)
    expect(screen.getByText('Nikita Gorshkov')).toBeDefined()
  })

  it('renders Update App button in idle state', async () => {
    render(<AppSettingsForm />)
    expect(screen.getByText('Update App')).toBeDefined()
  })

  it('calls startUpdate when Update App clicked', async () => {
    render(<AppSettingsForm />)
    fireEvent.click(screen.getByText('Update App'))
    expect(mockApi.startUpdate).toHaveBeenCalled()
  })

  it('shows PM-OS path when available', async () => {
    render(<AppSettingsForm />)
    await waitFor(() => {
      expect(screen.getByText('/Users/test/pm-os')).toBeDefined()
    })
  })

  it('registers update progress listener on mount', () => {
    render(<AppSettingsForm />)
    expect(mockApi.onUpdateProgress).toHaveBeenCalled()
  })

  it('removes update progress listener on unmount', () => {
    const { unmount } = render(<AppSettingsForm />)
    unmount()
    expect(mockApi.removeUpdateProgressListener).toHaveBeenCalled()
  })
})
