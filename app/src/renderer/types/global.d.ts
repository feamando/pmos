import type { PmosAPI } from '../../shared/types'

declare global {
  interface Window {
    api: PmosAPI
  }
}
