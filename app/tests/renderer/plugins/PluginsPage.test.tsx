import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import PluginsPage from '../../../src/renderer/pages/PluginsPage'

const mockInstalledPlugin = {
  id: 'pm-os-base',
  name: 'pm-os-base',
  version: '5.0.0',
  description: 'Core configuration and shared utilities',
  author: 'PM-OS',
  dependencies: [],
  status: 'installed' as const,
  commands: ['commands/base.md'],
  skills: [],
  mcpServers: [],
}

const mockAvailablePlugin = {
  id: 'pm-os-brain',
  name: 'pm-os-brain',
  version: '5.0.0',
  description: 'Knowledge graph and entity management',
  author: 'PM-OS',
  dependencies: ['pm-os-base'],
  status: 'available' as const,
  commands: ['commands/brain.md'],
  skills: ['skills/entity-resolution.md'],
  mcpServers: [],
}

const mockApi = {
  getInstalledPlugins: vi.fn().mockResolvedValue([mockInstalledPlugin]),
  getAvailablePlugins: vi.fn().mockResolvedValue([mockAvailablePlugin]),
  getPluginHealth: vi.fn().mockResolvedValue({ status: 'healthy', message: 'Config valid' }),
  installPlugin: vi.fn().mockResolvedValue({ success: true, pluginId: 'pm-os-brain', action: 'install' }),
  disablePlugin: vi.fn().mockResolvedValue({ success: true, pluginId: 'pm-os-brain', action: 'disable' }),
  logTelemetryClick: vi.fn(),
}

beforeEach(() => {
  ;(window as any).api = mockApi
  vi.clearAllMocks()
  mockApi.getInstalledPlugins.mockResolvedValue([mockInstalledPlugin])
  mockApi.getAvailablePlugins.mockResolvedValue([mockAvailablePlugin])
  mockApi.getPluginHealth.mockResolvedValue({ status: 'healthy', message: 'Config valid' })
})

describe('PluginsPage', () => {
  it('shows loading state initially', () => {
    mockApi.getInstalledPlugins.mockReturnValue(new Promise(() => {}))
    mockApi.getAvailablePlugins.mockReturnValue(new Promise(() => {}))
    render(<PluginsPage />)
    expect(screen.getByText('Loading plugins...')).toBeDefined()
  })

  it('renders installed and available sections', async () => {
    render(<PluginsPage />)
    await waitFor(() => {
      // "Installed" appears as section header and as badge — use getAllByText
      expect(screen.getAllByText('Installed').length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText('Available').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('pm-os-base')).toBeDefined()
    expect(screen.getByText('pm-os-brain')).toBeDefined()
  })

  it('shows the page header', async () => {
    render(<PluginsPage />)
    await waitFor(() => {
      expect(screen.getByText('Plugins')).toBeDefined()
    })
    expect(screen.getByText('Manage PM-OS v5.0 plugins')).toBeDefined()
  })

  it('shows cowork note', async () => {
    render(<PluginsPage />)
    await waitFor(() => {
      expect(screen.getByText('Plugins also work in Claude Cowork.')).toBeDefined()
    })
  })

  it('shows empty state when no plugins found', async () => {
    mockApi.getInstalledPlugins.mockResolvedValue([])
    mockApi.getAvailablePlugins.mockResolvedValue([])
    render(<PluginsPage />)
    await waitFor(() => {
      expect(screen.getByText(/No plugins found/)).toBeDefined()
    })
  })
})
