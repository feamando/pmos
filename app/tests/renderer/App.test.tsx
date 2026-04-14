import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import App from '../../src/renderer/App'

const mockApi = {
  getAppMode: vi.fn().mockResolvedValue('connections'),
  getEnvPath: vi.fn().mockResolvedValue('/mock/path/.env'),
  detectPmosInstallation: vi.fn().mockResolvedValue([]),
  getConnections: vi.fn().mockResolvedValue([]),
  detectV4Installation: vi.fn().mockResolvedValue({ isV4: false }),
  onAppModeChanged: vi.fn(),
  removeAppModeChangedListener: vi.fn(),
  onHealthUpdate: vi.fn(),
  removeHealthUpdateListener: vi.fn(),
  logTelemetryClick: vi.fn(),
  // Plugin stubs
  getInstalledPlugins: vi.fn().mockResolvedValue([]),
  getAvailablePlugins: vi.fn().mockResolvedValue([]),
  getPluginHealth: vi.fn().mockResolvedValue({ status: 'unknown' }),
  // Migration stubs
  onMigrationProgress: vi.fn(),
  removeMigrationProgressListener: vi.fn(),
}

beforeEach(() => {
  ;(window as any).api = mockApi
  vi.clearAllMocks()
  mockApi.getAppMode.mockResolvedValue('connections')
  mockApi.getEnvPath.mockResolvedValue('/mock/path')
  mockApi.getConnections.mockResolvedValue([])
  mockApi.detectV4Installation.mockResolvedValue({ isV4: false })
})

describe('App', () => {
  it('renders home page by default in connections mode', async () => {
    render(<App />)
    await waitFor(() => {
      // App should render (not be stuck on loading)
      expect(mockApi.getAppMode).toHaveBeenCalled()
    })
  })

  it('navigates to plugins page', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByTitle('Plugins')).toBeDefined()
    })
    fireEvent.click(screen.getByTitle('Plugins'))
    await waitFor(() => {
      expect(screen.getByText('Plugins')).toBeDefined()
    })
  })

  it('shows migration dialog when v4 detected', async () => {
    mockApi.detectV4Installation.mockResolvedValue({ isV4: true, path: '/mock/pm-os' })
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('Upgrade to PM-OS v5.0')).toBeDefined()
    })
  })

  it('does not show migration dialog when no v4', async () => {
    mockApi.detectV4Installation.mockResolvedValue({ isV4: false })
    render(<App />)
    await waitFor(() => {
      expect(screen.getByTitle('Home')).toBeDefined()
    })
    expect(screen.queryByText('Upgrade to PM-OS v5.0')).toBeNull()
  })
})
