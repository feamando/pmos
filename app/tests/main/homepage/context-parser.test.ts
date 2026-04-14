import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import path from 'path'
import os from 'os'
import yaml from 'js-yaml'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
  shell: { openPath: vi.fn() },
}))

vi.mock('electron-store', () => ({
  default: class MockStore {
    constructor() {}
    get(_key: string, fallback?: any) { return fallback }
    set() {}
    clear() {}
  },
}))

import { findLatestContextFile, parseMeetings, parseActionItems, parseAlerts, readUserName, getSyntheticContext } from '../../../src/main/homepage/context-parser'

const SAMPLE_CONTEXT = `# Daily Context: 2026-03-30

**Generated:** 2026-03-30 10:31 CET

---

## Critical Alerts

- **(P0) API Outage — Production Impact** — Third-party service returning 500 errors. (Team Lead / DevOps)
- **(P1) Sprint Velocity — Below Target** — Last 3 sprints below 80% target velocity. (Scrum Master)

---

## Today's Schedule

| Time | Event |
|------|-------|
| 09:30–10:00 | Daily Standup |
| 14:00–15:00 | Sprint Review |
| — | No other events |

---

## Key Updates & Decisions

### Some Topic
- Detail here

---

## Action Items

### Today
- [ ] **Alice**: Review PR #42
- [ ] **Bob**: Deploy to staging

### This Week
- [ ] **Charlie**: Update design docs

### This Sprint (Sprint-7: 2026-03-30 to 2026-04-10)
- [ ] **Team**: Complete retrospective items

---

## Key Dates

| Date | Event |
|------|-------|
| 2026-04-01 | Holiday |
`

describe('context-parser', () => {
  let tmpDir: string

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'context-parser-test-'))
  })

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true })
  })

  describe('findLatestContextFile', () => {
    it('returns null for non-existent directory', () => {
      expect(findLatestContextFile('/nonexistent')).toBeNull()
    })

    it('returns null for empty directory', () => {
      expect(findLatestContextFile(tmpDir)).toBeNull()
    })

    it('returns the most recent context file', () => {
      fs.writeFileSync(path.join(tmpDir, '2026-03-28-context.md'), 'old')
      fs.writeFileSync(path.join(tmpDir, '2026-03-30-context.md'), 'new')
      fs.writeFileSync(path.join(tmpDir, '2026-03-29-context.md'), 'mid')

      const result = findLatestContextFile(tmpDir)
      expect(result).toBe(path.join(tmpDir, '2026-03-30-context.md'))
    })

    it('ignores non-context files', () => {
      fs.writeFileSync(path.join(tmpDir, 'notes.md'), 'ignore')
      fs.writeFileSync(path.join(tmpDir, '2026-03-30-context.md'), 'pick')

      const result = findLatestContextFile(tmpDir)
      expect(result).toContain('2026-03-30-context.md')
    })
  })

  describe('parseMeetings', () => {
    it('extracts meeting items from schedule table', () => {
      const meetings = parseMeetings(SAMPLE_CONTEXT)
      expect(meetings).toHaveLength(3)
      expect(meetings[0]).toEqual({ time: '09:30–10:00', event: 'Daily Standup' })
      expect(meetings[1]).toEqual({ time: '14:00–15:00', event: 'Sprint Review' })
    })

    it('handles dash time as empty string', () => {
      const meetings = parseMeetings(SAMPLE_CONTEXT)
      expect(meetings[2].time).toBe('')
    })

    it('returns empty for missing section', () => {
      expect(parseMeetings('# No schedule here')).toEqual([])
    })
  })

  describe('parseActionItems', () => {
    it('extracts action items with correct groups', () => {
      const items = parseActionItems(SAMPLE_CONTEXT)
      expect(items).toHaveLength(4)
      expect(items[0]).toEqual({ owner: 'Alice', text: 'Review PR #42', group: 'Today' })
      expect(items[2]).toEqual({ owner: 'Charlie', text: 'Update design docs', group: 'This Week' })
      expect(items[3].group).toBe('This Sprint')
    })

    it('returns empty for missing section', () => {
      expect(parseActionItems('# No actions')).toEqual([])
    })
  })

  describe('parseAlerts', () => {
    it('extracts alert items with priority', () => {
      const alerts = parseAlerts(SAMPLE_CONTEXT)
      expect(alerts).toHaveLength(2)
      expect(alerts[0].priority).toBe('P0')
      expect(alerts[0].title).toContain('API Outage')
      expect(alerts[1].priority).toBe('P1')
    })

    it('returns empty for missing section', () => {
      expect(parseAlerts('# No alerts')).toEqual([])
    })
  })

  describe('readUserName', () => {
    it('reads user name from config.yaml', () => {
      const userDir = path.join(tmpDir, 'user')
      fs.mkdirSync(userDir, { recursive: true })
      fs.writeFileSync(path.join(userDir, 'config.yaml'), yaml.dump({ user: { name: 'Jane Doe' } }))

      expect(readUserName(tmpDir)).toBe('Jane Doe')
    })

    it('returns empty for missing config', () => {
      expect(readUserName(tmpDir)).toBe('')
    })
  })

  describe('getSyntheticContext', () => {
    it('returns complete synthetic data', () => {
      const data = getSyntheticContext()
      expect(data.userName).toBe('Developer')
      expect(data.meetings.length).toBeGreaterThan(0)
      expect(data.actionItems.length).toBeGreaterThan(0)
      expect(data.alerts.length).toBeGreaterThan(0)
    })
  })
})
