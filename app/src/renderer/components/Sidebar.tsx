import { Home, Link, Brain, Cog, Puzzle, Settings } from 'lucide-react'

export type SidebarPage = 'home' | 'connections' | 'brain' | 'cce' | 'plugins' | 'settings'

interface SidebarProps {
  activePage: SidebarPage
  onNavigate: (page: SidebarPage) => void
}

const navBtnStyle = (active: boolean): React.CSSProperties => ({
  width: 36,
  height: 36,
  borderRadius: 'var(--radius-lg)',
  background: active ? 'rgba(255,255,255,0.15)' : 'transparent',
  border: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  transition: 'background 0.15s',
})

export default function Sidebar({ activePage, onNavigate }: SidebarProps) {
  const hoverOn = (page: SidebarPage) => (e: React.MouseEvent<HTMLButtonElement>) => {
    if (activePage !== page) e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
  }
  const hoverOff = (page: SidebarPage) => (e: React.MouseEvent<HTMLButtonElement>) => {
    if (activePage !== page) e.currentTarget.style.background = 'transparent'
  }

  return (
    <nav style={{
      width: 56,
      minWidth: 56,
      height: '100vh',
      background: 'var(--hf-green)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 0',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
        <button onClick={() => onNavigate('home')} title="Home" style={navBtnStyle(activePage === 'home')} onMouseEnter={hoverOn('home')} onMouseLeave={hoverOff('home')}>
          <Home size={20} color="white" />
        </button>
        <button onClick={() => onNavigate('connections')} title="Connections" style={navBtnStyle(activePage === 'connections')} onMouseEnter={hoverOn('connections')} onMouseLeave={hoverOff('connections')}>
          <Link size={20} color="white" />
        </button>
        <button onClick={() => onNavigate('brain')} title="Brain" style={navBtnStyle(activePage === 'brain')} onMouseEnter={hoverOn('brain')} onMouseLeave={hoverOff('brain')}>
          <Brain size={20} color="white" />
        </button>
        <button onClick={() => onNavigate('cce')} title="Context Engine" style={navBtnStyle(activePage === 'cce')} onMouseEnter={hoverOn('cce')} onMouseLeave={hoverOff('cce')}>
          <Cog size={20} color="white" />
        </button>
        <button onClick={() => onNavigate('plugins')} title="Plugins" style={navBtnStyle(activePage === 'plugins')} onMouseEnter={hoverOn('plugins')} onMouseLeave={hoverOff('plugins')}>
          <Puzzle size={20} color="white" />
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
        <button
          onClick={() => onNavigate('settings')}
          title="Settings"
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: activePage === 'settings' ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.2)',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.3)' }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = activePage === 'settings' ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.2)'
          }}
        >
          <Settings size={18} color="white" />
        </button>
      </div>
    </nav>
  )
}
