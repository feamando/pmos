import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PluginCard from '../../../src/renderer/components/plugins/PluginCard'
import type { PluginInfo } from '../../../src/shared/types'

const basePlugin: PluginInfo = {
  id: 'pm-os-base',
  name: 'pm-os-base',
  version: '5.0.0',
  description: 'Core configuration and shared utilities',
  author: 'PM-OS',
  dependencies: [],
  status: 'installed',
  commands: ['commands/base.md'],
  skills: ['skills/base-skill.md'],
  mcpServers: [],
}

describe('PluginCard', () => {
  it('renders plugin name and version', () => {
    render(<PluginCard plugin={basePlugin} />)
    expect(screen.getByText('pm-os-base')).toBeDefined()
    expect(screen.getByText('v5.0.0')).toBeDefined()
  })

  it('renders description', () => {
    render(<PluginCard plugin={basePlugin} />)
    expect(screen.getByText('Core configuration and shared utilities')).toBeDefined()
  })

  it('shows command and skill counts', () => {
    render(<PluginCard plugin={basePlugin} />)
    expect(screen.getByText('1 command')).toBeDefined()
    expect(screen.getByText('1 skill')).toBeDefined()
  })

  it('shows Install button for available plugins', () => {
    const available = { ...basePlugin, id: 'pm-os-brain', status: 'available' as const }
    const onInstall = vi.fn()
    render(<PluginCard plugin={available} onInstall={onInstall} />)
    const btn = screen.getByText('Install')
    fireEvent.click(btn)
    expect(onInstall).toHaveBeenCalledWith('pm-os-brain')
  })

  it('does NOT show Disable button for pm-os-base', () => {
    render(<PluginCard plugin={basePlugin} />)
    expect(screen.queryByText('Disable')).toBeNull()
  })

  it('shows Disable button for non-base installed plugins', () => {
    const brain = { ...basePlugin, id: 'pm-os-brain', name: 'pm-os-brain' }
    const onDisable = vi.fn()
    render(<PluginCard plugin={brain} onDisable={onDisable} />)
    const btn = screen.getByText('Disable')
    fireEvent.click(btn)
    expect(onDisable).toHaveBeenCalledWith('pm-os-brain')
  })

  it('shows Installed badge', () => {
    render(<PluginCard plugin={basePlugin} />)
    expect(screen.getByText('Installed')).toBeDefined()
  })

  it('shows Available badge for available plugin', () => {
    const available = { ...basePlugin, status: 'available' as const }
    render(<PluginCard plugin={available} />)
    expect(screen.getByText('Available')).toBeDefined()
  })

  it('shows health message when present', () => {
    const withHealth = {
      ...basePlugin,
      health: { status: 'healthy' as const, message: 'Config valid' },
    }
    render(<PluginCard plugin={withHealth} />)
    expect(screen.getByText('Config valid')).toBeDefined()
  })

  it('shows dependency info', () => {
    const withDeps = { ...basePlugin, dependencies: ['pm-os-base'] }
    render(<PluginCard plugin={withDeps} />)
    expect(screen.getByText('Depends on: pm-os-base')).toBeDefined()
  })
})
