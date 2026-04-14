export const STEP_LABELS = ['Discovery', 'Planning', 'Context v1', 'In Progress', 'Complete'] as const

/**
 * Clean up display names: remove "Context" suffix, normalize casing.
 */
export function cleanDisplayName(name: string): string {
  return name
    .replace(/\s*Context$/i, '')
    .replace(/\s*context$/i, '')
    .trim()
}

/**
 * Map a raw feature status string to a step bar index.
 * Returns 0-4 for pipeline steps, -1 for "To Do", -2 for "Deprioritized".
 */
export function mapStatusToStep(rawStatus: string): number {
  const s = rawStatus.toLowerCase().trim()

  // Special cases
  if (s === 'to do' || s === '') return -1
  if (s === 'deprioritized') return -2

  // Step 4: Complete
  if (s === 'complete' || s === 'completed' || s === 'archived') return 4

  // Step 3: In Progress / Active
  if (s.startsWith('in progress') || s.startsWith('active')) return 3

  // Step 2: Context creation
  if (s.includes('context v1') || s.includes('context v2') || s.includes('context creation') || s.includes('initialization')) return 2

  // Step 1: Planning
  if (s === 'planning' || s === 'draft') return 1

  // Step 0: Discovery
  if (s.includes('discovery') || s.includes('research')) return 0

  // Unknown → treat as To Do
  console.warn(`[CCE] Unknown feature status: "${rawStatus}", defaulting to To Do`)
  return -1
}
