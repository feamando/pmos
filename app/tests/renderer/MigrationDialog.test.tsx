import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MigrationDialog from '../../src/renderer/components/MigrationDialog'

const mockApi = {
  startMigration: vi.fn().mockResolvedValue(undefined),
  onMigrationProgress: vi.fn(),
  removeMigrationProgressListener: vi.fn(),
  rollbackMigration: vi.fn().mockResolvedValue({ success: true }),
  logTelemetryClick: vi.fn(),
}

beforeEach(() => {
  ;(window as any).api = mockApi
  vi.clearAllMocks()
})

describe('MigrationDialog', () => {
  it('does not render when isOpen is false', () => {
    render(<MigrationDialog isOpen={false} onClose={vi.fn()} />)
    expect(screen.queryByText('Upgrade to PM-OS v5.0')).toBeNull()
  })

  it('renders when isOpen is true', () => {
    render(<MigrationDialog isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText('Upgrade to PM-OS v5.0')).toBeDefined()
  })

  it('shows v5.0 benefits', () => {
    render(<MigrationDialog isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText(/7 modular plugins/)).toBeDefined()
    expect(screen.getByText(/Claude Cowork compatible/)).toBeDefined()
  })

  it('shows Later and Upgrade buttons', () => {
    render(<MigrationDialog isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText('Later')).toBeDefined()
    expect(screen.getByText('Upgrade to v5.0')).toBeDefined()
  })

  it('calls onClose when Later is clicked', () => {
    const onClose = vi.fn()
    render(<MigrationDialog isOpen={true} onClose={onClose} />)
    fireEvent.click(screen.getByText('Later'))
    expect(onClose).toHaveBeenCalled()
  })

  it('starts migration on Upgrade click', () => {
    render(<MigrationDialog isOpen={true} onClose={vi.fn()} />)
    fireEvent.click(screen.getByText('Upgrade to v5.0'))
    expect(mockApi.startMigration).toHaveBeenCalled()
  })

  it('shows step labels during migration', () => {
    render(<MigrationDialog isOpen={true} onClose={vi.fn()} />)
    fireEvent.click(screen.getByText('Upgrade to v5.0'))
    // Step labels are always rendered once started
    expect(screen.getByText('Analyzing installation...')).toBeDefined()
    expect(screen.getByText('Creating backup...')).toBeDefined()
    expect(screen.getByText('Migrating to v5.0...')).toBeDefined()
    expect(screen.getByText('Validating migration...')).toBeDefined()
    expect(screen.getByText('Migration complete!')).toBeDefined()
  })

  it('shows description about v4.x detection', () => {
    render(<MigrationDialog isOpen={true} onClose={vi.fn()} />)
    expect(screen.getByText(/v4.x PM-OS installation was detected/)).toBeDefined()
  })
})
