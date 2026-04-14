import { readdirSync, readFileSync, existsSync } from 'fs'
import path from 'path'
import yaml from 'js-yaml'
import type { DailyContextData, MeetingItem, ActionItem, AlertItem } from '../../shared/types'

/**
 * Find the most recent context file in the context directory.
 * Files follow naming: YYYY-MM-DD-context.md or YYYY-MM-DD-##-context.md
 */
export function findLatestContextFile(contextDir: string): string | null {
  if (!existsSync(contextDir)) return null

  const files = readdirSync(contextDir)
    .filter((f) => f.endsWith('-context.md') && /^\d{4}-\d{2}-\d{2}/.test(f))
    .sort()
    .reverse()

  return files.length > 0 ? path.join(contextDir, files[0]) : null
}

/**
 * Extract the content between two section headers (## markers).
 */
function extractSection(content: string, sectionName: string): string {
  const pattern = new RegExp(`^## ${sectionName}\\s*$`, 'm')
  const match = content.match(pattern)
  if (!match || match.index === undefined) return ''

  const start = match.index + match[0].length
  const nextSection = content.indexOf('\n## ', start)
  const sectionContent = nextSection === -1
    ? content.slice(start)
    : content.slice(start, nextSection)

  return sectionContent.trim()
}

/**
 * Parse the "Today's Schedule" section into MeetingItem[]
 */
export function parseMeetings(content: string): MeetingItem[] {
  const section = extractSection(content, 'Today\'s Schedule')
  if (!section) return []

  const items: MeetingItem[] = []
  const lines = section.split('\n')

  for (const line of lines) {
    // Table row: | Time | Event |
    const tableMatch = line.match(/^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$/)
    if (tableMatch) {
      const time = tableMatch[1].trim()
      const event = tableMatch[2].trim()
      // Skip header row and separator
      if (time === 'Time' || time.startsWith('-')) continue
      items.push({ time: time === '—' ? '' : time, event })
    }
  }

  return items
}

/**
 * Parse the "Action Items" section into ActionItem[]
 */
export function parseActionItems(content: string): ActionItem[] {
  const section = extractSection(content, 'Action Items')
  if (!section) return []

  const items: ActionItem[] = []
  let currentGroup = 'Today'

  for (const line of section.split('\n')) {
    // Group headers: ### Today, ### This Week, ### This Sprint (Sprint-7: ...)
    const groupMatch = line.match(/^###\s+(.+)/)
    if (groupMatch) {
      const raw = groupMatch[1].trim()
      if (raw.startsWith('Today')) currentGroup = 'Today'
      else if (raw.startsWith('This Week')) currentGroup = 'This Week'
      else if (raw.startsWith('This Sprint')) currentGroup = 'This Sprint'
      else currentGroup = raw
      continue
    }

    // Action item: - [ ] **Owner**: Text
    const itemMatch = line.match(/^-\s*\[[ x]?\]\s*\*\*(.+?)\*\*[:\s]*(.+)/)
    if (itemMatch) {
      items.push({
        owner: itemMatch[1].trim(),
        text: itemMatch[2].trim(),
        group: currentGroup,
      })
    }
  }

  return items
}

/**
 * Parse the "Critical Alerts" section into AlertItem[]
 */
export function parseAlerts(content: string): AlertItem[] {
  const section = extractSection(content, 'Critical Alerts')
  if (!section) return []

  const items: AlertItem[] = []

  for (const line of section.split('\n')) {
    // Alert: - **(P0) Title — Description** — More text...
    // or: - **(P0) Title** — Description text
    const alertMatch = line.match(/^-\s*\*\*\((P[0-9])\)\s*(.+?)(?:\s*—|$)\*\*\s*(?:—\s*)?(.*)/)
    if (alertMatch) {
      items.push({
        priority: alertMatch[1],
        title: alertMatch[2].trim(),
        description: alertMatch[3]?.trim() || '',
      })
      continue
    }

    // Simpler format: - **(P0/P1) Title — Description
    const simpleMatch = line.match(/^-\s*\*\*\((P[0-9])\)\s*(.+?)—\s*(.+)/)
    if (simpleMatch) {
      items.push({
        priority: simpleMatch[1],
        title: simpleMatch[2].replace(/\*\*/g, '').trim(),
        description: simpleMatch[3].trim(),
      })
    }
  }

  return items
}

/**
 * Parse the generated timestamp from context file header.
 */
function parseGeneratedAt(content: string): string {
  const match = content.match(/\*\*Generated:\*\*\s*(.+)/)
  return match ? match[1].trim() : ''
}

/**
 * Parse the date from the context file header.
 */
function parseDate(content: string): string {
  const match = content.match(/^# Daily Context:\s*(\d{4}-\d{2}-\d{2})/m)
  return match ? match[1] : ''
}

/**
 * Read user name from config.yaml
 */
export function readUserName(pmosPath: string): string {
  try {
    const configPath = path.join(pmosPath, 'user', 'config.yaml')
    if (!existsSync(configPath)) return ''
    const content = readFileSync(configPath, 'utf-8')
    const config = yaml.load(content) as Record<string, any>
    return config?.user?.name || ''
  } catch {
    return ''
  }
}

/**
 * Parse a full context file into DailyContextData.
 */
export function parseContextFile(filePath: string, userName: string): DailyContextData {
  const content = readFileSync(filePath, 'utf-8')

  return {
    date: parseDate(content),
    generatedAt: parseGeneratedAt(content),
    userName,
    meetings: parseMeetings(content),
    actionItems: parseActionItems(content),
    alerts: parseAlerts(content),
  }
}

/**
 * Synthetic context data for dev mode.
 */
export function getSyntheticContext(): DailyContextData {
  const today = new Date().toISOString().split('T')[0]
  return {
    date: today,
    generatedAt: `${today} 09:00 CET`,
    userName: 'Developer',
    meetings: [
      { time: '09:30–10:00', event: 'Daily Standup — Engineering sync' },
      { time: '11:00–12:00', event: 'Sprint Planning — Sprint-8 kickoff' },
      { time: '14:00–14:30', event: '1:1 with Manager — Weekly check-in' },
      { time: '16:00–17:00', event: 'Product Review — Q1 retrospective' },
    ],
    actionItems: [
      { owner: 'You', text: 'Review PR #142 for API integration', group: 'Today' },
      { owner: 'You', text: 'Finalize spec for new onboarding flow', group: 'Today' },
      { owner: 'Sarah', text: 'Update design mockups for settings panel', group: 'This Week' },
      { owner: 'Mike', text: 'Deploy staging build for QA testing', group: 'This Week' },
      { owner: 'Team', text: 'Complete sprint retrospective action items', group: 'This Sprint' },
    ],
    alerts: [
      { priority: 'P0', title: 'API Rate Limiting — Production Impact', description: 'Third-party API returning 429s; fallback cache enabled but degraded experience for 12% of users.' },
      { priority: 'P1', title: 'Sprint Velocity Declining — Capacity Review', description: 'Last 3 sprints trending below target; PTO + context switching identified as root causes.' },
      { priority: 'P1', title: 'Security Audit Findings — 2 Medium Issues', description: 'Audit completed; XSS in admin panel + missing rate limiting on auth endpoint. Fix deadline: next sprint.' },
    ],
  }
}
