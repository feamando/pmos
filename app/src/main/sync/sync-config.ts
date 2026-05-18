import { readConfigYaml, writeConfigYaml } from '../config-yaml-manager'
import type { SyncConfig } from '../../shared/types'

const DEFAULTS: SyncConfig = {
  enabled: true,
  gatherIntervalMinutes: 30,
  synthesizeIntervalMinutes: 120,
  enableSynthesis: true,
}

export function readSyncConfig(pmosPath: string): SyncConfig {
  try {
    const config = readConfigYaml(pmosPath)
    const bg = config?.background_sync || {}
    return {
      enabled: bg.enabled ?? DEFAULTS.enabled,
      gatherIntervalMinutes: bg.gather_interval_minutes ?? DEFAULTS.gatherIntervalMinutes,
      synthesizeIntervalMinutes: bg.synthesize_interval_minutes ?? DEFAULTS.synthesizeIntervalMinutes,
      enableSynthesis: bg.enable_synthesis ?? DEFAULTS.enableSynthesis,
    }
  } catch {
    return { ...DEFAULTS }
  }
}

export function writeSyncConfig(pmosPath: string, syncConfig: SyncConfig): void {
  const config = readConfigYaml(pmosPath)
  config.background_sync = {
    enabled: syncConfig.enabled,
    gather_interval_minutes: syncConfig.gatherIntervalMinutes,
    synthesize_interval_minutes: syncConfig.synthesizeIntervalMinutes,
    enable_synthesis: syncConfig.enableSynthesis,
  }
  writeConfigYaml(pmosPath, config)
}
