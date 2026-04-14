import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Sidebar from '../../src/renderer/components/Sidebar'

describe('Sidebar', () => {
  it('renders all navigation buttons including Plugins', () => {
    render(<Sidebar activePage="home" onNavigate={vi.fn()} />)
    expect(screen.getByTitle('Home')).toBeDefined()
    expect(screen.getByTitle('Connections')).toBeDefined()
    expect(screen.getByTitle('Brain')).toBeDefined()
    expect(screen.getByTitle('Context Engine')).toBeDefined()
    expect(screen.getByTitle('Plugins')).toBeDefined()
    expect(screen.getByTitle('Settings')).toBeDefined()
  })

  it('navigates to plugins page on click', () => {
    const onNavigate = vi.fn()
    render(<Sidebar activePage="home" onNavigate={onNavigate} />)
    fireEvent.click(screen.getByTitle('Plugins'))
    expect(onNavigate).toHaveBeenCalledWith('plugins')
  })

  it('highlights active page', () => {
    render(<Sidebar activePage="plugins" onNavigate={vi.fn()} />)
    const pluginsBtn = screen.getByTitle('Plugins')
    // Active buttons have rgba(255,255,255,0.15) background
    expect(pluginsBtn.style.background).toContain('rgba(255')
  })
})
