import yaml from 'js-yaml'
import { readFileSync, writeFileSync, existsSync } from 'fs'
import path from 'path'
import type { ConfigValidationResult } from '../shared/types'

function getConfigPath(pmosPath: string): string {
  return path.join(pmosPath, 'user', 'config.yaml')
}

export function readConfigYaml(pmosPath: string): Record<string, any> {
  const configPath = getConfigPath(pmosPath)
  if (!existsSync(configPath)) return {}
  const content = readFileSync(configPath, 'utf-8')
  return (yaml.load(content) as Record<string, any>) || {}
}

function deepMerge(target: Record<string, any>, source: Record<string, any>): Record<string, any> {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    if (
      source[key] !== null &&
      typeof source[key] === 'object' &&
      !Array.isArray(source[key]) &&
      typeof result[key] === 'object' &&
      result[key] !== null &&
      !Array.isArray(result[key])
    ) {
      result[key] = deepMerge(result[key], source[key])
    } else {
      result[key] = source[key]
    }
  }
  return result
}

export function writeConfigYaml(pmosPath: string, data: Record<string, any>): void {
  const configPath = getConfigPath(pmosPath)
  const existing = readConfigYaml(pmosPath)
  const merged = deepMerge(existing, data)
  if (!merged.version) merged.version = '3.0.0'
  const output = yaml.dump(merged, { lineWidth: 120, noRefs: true, sortKeys: false })
  writeFileSync(configPath, output, 'utf-8')
}

export function validateConfigYaml(data: Record<string, any>): ConfigValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  if (!data.user?.name) errors.push('Missing user.name')
  if (!data.user?.email || !data.user.email.includes('@')) errors.push('Missing or invalid user.email')

  if (!data.brain) warnings.push('Brain settings not configured')
  if (!data.meeting_prep) warnings.push('Meeting prep settings not configured')
  if (!data.team) warnings.push('Team structure not configured')

  return { valid: errors.length === 0, errors, warnings }
}
