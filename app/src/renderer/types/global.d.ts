import type { HelloAIAPI } from '../../shared/types'

declare global {
  interface Window {
    api: HelloAIAPI
  }
}
