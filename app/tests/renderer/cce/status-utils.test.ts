import { describe, it, expect, vi } from 'vitest'
import { mapStatusToStep, STEP_LABELS } from '../../../src/renderer/components/cce/status-utils'

describe('status-utils', () => {
  it('exports 5 step labels', () => {
    expect(STEP_LABELS).toHaveLength(5)
    expect(STEP_LABELS[0]).toBe('Discovery')
    expect(STEP_LABELS[4]).toBe('Complete')
  })

  it('maps Discovery statuses to step 0', () => {
    expect(mapStatusToStep('In Discovery')).toBe(0)
    expect(mapStatusToStep('In Research')).toBe(0)
    expect(mapStatusToStep('discovery')).toBe(0)
  })

  it('maps Planning statuses to step 1', () => {
    expect(mapStatusToStep('Planning')).toBe(1)
    expect(mapStatusToStep('Draft')).toBe(1)
  })

  it('maps Context creation statuses to step 2', () => {
    expect(mapStatusToStep('Context v1 Complete')).toBe(2)
    expect(mapStatusToStep('Context v2 — Deep Research Complete')).toBe(2)
    expect(mapStatusToStep('Active — Initialization')).toBe(2)
  })

  it('maps In Progress statuses to step 3', () => {
    expect(mapStatusToStep('In Progress')).toBe(3)
    expect(mapStatusToStep('Active')).toBe(3)
    expect(mapStatusToStep('In Progress — Parallel Tracks (Read-Only Phase 1)')).toBe(3)
    expect(mapStatusToStep('Active — mandated baseline')).toBe(3)
  })

  it('maps Complete statuses to step 4', () => {
    expect(mapStatusToStep('Complete')).toBe(4)
    expect(mapStatusToStep('Completed')).toBe(4)
    expect(mapStatusToStep('Archived')).toBe(4)
  })

  it('maps To Do to -1', () => {
    expect(mapStatusToStep('To Do')).toBe(-1)
    expect(mapStatusToStep('')).toBe(-1)
  })

  it('maps Deprioritized to -2', () => {
    expect(mapStatusToStep('Deprioritized')).toBe(-2)
  })

  it('maps unknown status to -1 with console warning', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(mapStatusToStep('Some Unknown Status')).toBe(-1)
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('Unknown feature status'))
    warnSpy.mockRestore()
  })
})
