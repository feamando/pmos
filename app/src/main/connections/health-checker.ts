import { parseEnvFile, readAllEnvValues } from '../env/env-manager'
import { getAllEnvKeys, CONNECTION_CONFIGS } from '../../shared/connection-configs'
import { validateJira, validateConfluence, validateGoogle, validateSlack, validateGithub, validateFigma } from './validators'
import type { HealthStatus, TestResult } from '../../shared/types'
import path from 'path'

const VALIDATORS: Record<string, (fields: Record<string, string>, basePath: string) => Promise<TestResult>> = {
  jira: (f) => validateJira(f),
  confluence: (f) => validateConfluence(f),
  google: (f, basePath) => validateGoogle(f, basePath),
  slack: (f) => validateSlack(f),
  github: (f) => validateGithub(f),
  figma: (f) => validateFigma(f),
}

export async function checkConnection(id: string, fields: Record<string, string>, basePath: string): Promise<HealthStatus> {
  const validator = VALIDATORS[id]
  if (!validator) return { connectionId: id, status: 'unknown', message: 'No validator' }

  // Skip if no required fields have values
  const config = CONNECTION_CONFIGS.find((c) => c.id === id)
  if (!config) return { connectionId: id, status: 'unknown' }

  const hasRequired = config.fields.some((f) => f.required && fields[f.envKey])
  if (!hasRequired) return { connectionId: id, status: 'unknown', message: 'Not configured' }

  try {
    const result = await validator(fields, basePath)
    return {
      connectionId: id,
      status: result.success ? 'healthy' : 'unhealthy',
      message: result.message,
      lastChecked: Date.now(),
    }
  } catch (err: any) {
    return {
      connectionId: id,
      status: 'unhealthy',
      message: err.message,
      lastChecked: Date.now(),
    }
  }
}

export async function checkAllConnections(envPath: string): Promise<HealthStatus[]> {
  const envFile = await parseEnvFile(envPath)
  const allValues = readAllEnvValues(envFile, getAllEnvKeys())
  const basePath = path.dirname(envPath) // .env is in user/, basePath should be user/ for relative paths

  const results = await Promise.allSettled(
    CONNECTION_CONFIGS.map((config) => {
      const fields: Record<string, string> = {}
      for (const field of config.fields) {
        fields[field.envKey] = allValues[field.envKey] || ''
      }
      return checkConnection(config.id, fields, basePath)
    })
  )

  return results.map((r, i) =>
    r.status === 'fulfilled'
      ? r.value
      : { connectionId: CONNECTION_CONFIGS[i].id, status: 'unhealthy' as const, message: 'Check failed', lastChecked: Date.now() }
  )
}
