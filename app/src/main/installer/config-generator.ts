import * as fs from 'fs'
import * as path from 'path'
import { logInfo, logError, logOk } from './logger'
import type { StepResult } from './dep-installer'

interface TemplateFile {
  templateName: string
  targetPath: string // relative to basePath
}

const TEMPLATE_MAP: TemplateFile[] = [
  { templateName: 'env.template', targetPath: 'user/.env' },
  { templateName: 'config.yaml.template', targetPath: 'user/config.yaml' },
  { templateName: 'claude.md.template', targetPath: 'CLAUDE.md' },
  { templateName: 'agent.md.template', targetPath: 'common/AGENT.md' },
  { templateName: 'user.md.template', targetPath: 'user/USER.md' },
  { templateName: 'mcp.json.template', targetPath: '.mcp.json' },
]

export async function generateConfigFiles(basePath: string, bundlePath: string): Promise<StepResult> {
  const start = Date.now()
  const templateDir = path.join(bundlePath, 'data', 'templates')
  logInfo('installer', `Generating config files from ${templateDir}`)

  if (!fs.existsSync(templateDir)) {
    logError('installer', `Template directory not found: ${templateDir}`)
    return { success: false, message: 'Template directory not found', duration: 0 }
  }

  const errors: string[] = []

  for (const { templateName, targetPath } of TEMPLATE_MAP) {
    const src = path.join(templateDir, templateName)
    const dest = path.join(basePath, targetPath)

    // Skip if target already exists (idempotent — don't overwrite)
    if (fs.existsSync(dest)) {
      logInfo('installer', `Skipping ${targetPath} — already exists`)
      continue
    }

    if (!fs.existsSync(src)) {
      logInfo('installer', `Template not found: ${templateName} — skipping`)
      continue
    }

    try {
      const destDir = path.dirname(dest)
      fs.mkdirSync(destDir, { recursive: true })

      let content = fs.readFileSync(src, 'utf-8')

      // Replace any template variables
      content = content.replace(/\{\{DATE\}\}/g, new Date().toISOString().split('T')[0])
      content = content.replace(/\{\{PMOS_PATH\}\}/g, basePath)

      fs.writeFileSync(dest, content, 'utf-8')
      logInfo('installer', `Generated: ${targetPath}`)
    } catch (err: any) {
      errors.push(`${targetPath}: ${err.message}`)
      logError('installer', `Failed to generate ${targetPath}: ${err.message}`)
    }
  }

  const duration = (Date.now() - start) / 1000
  if (errors.length > 0) {
    return { success: false, message: errors.join('; '), duration }
  }

  logOk('installer', `Config files generated (${duration.toFixed(1)}s)`)
  return { success: true, message: 'All config files generated', duration }
}
