import { checkAllConnections } from './health-checker'
import type { HealthStatus } from '../../shared/types'

const DEFAULT_INTERVAL = 30 * 60 * 1000 // 30 minutes

export function startHealthPolling(
  envPath: string,
  onUpdate: (statuses: HealthStatus[]) => void,
  intervalMs: number = DEFAULT_INTERVAL,
): () => void {
  let timer: ReturnType<typeof setInterval> | null = null

  async function poll() {
    try {
      const statuses = await checkAllConnections(envPath)
      onUpdate(statuses)
    } catch (err) {
      console.error('Health polling failed:', err)
    }
  }

  // Run immediately
  poll()

  // Then every interval
  timer = setInterval(poll, intervalMs)

  // Return stop function
  return () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }
}
