import * as fs from 'fs'
import * as path from 'path'
import * as crypto from 'crypto'
import { logInfo, logError, logOk } from './logger'
import type { StepResult } from './dep-installer'

function copyRecursive(src: string, dest: string, onFile?: (rel: string) => void, baseDir?: string): number {
  let count = 0
  const base = baseDir || src

  fs.mkdirSync(dest, { recursive: true })

  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name)
    const destPath = path.join(dest, entry.name)

    if (entry.isDirectory()) {
      count += copyRecursive(srcPath, destPath, onFile, base)
    } else {
      // Skip if destination is newer
      if (fs.existsSync(destPath)) {
        const srcStat = fs.statSync(srcPath)
        const destStat = fs.statSync(destPath)
        if (destStat.mtimeMs > srcStat.mtimeMs) {
          continue
        }
      }

      fs.copyFileSync(srcPath, destPath)

      // Set executable on Python scripts
      if (entry.name.endsWith('.py') || entry.name.endsWith('.sh')) {
        try { fs.chmodSync(destPath, 0o755) } catch { /* ignore */ }
      }

      const rel = path.relative(base, srcPath)
      onFile?.(rel)
      count++
    }
  }

  return count
}

function checksumFile(filePath: string): string {
  const content = fs.readFileSync(filePath)
  return crypto.createHash('sha256').update(content).digest('hex')
}

export async function distributePmos(
  bundlePath: string,
  targetPath: string,
  onProgress?: (copied: number, total: number) => void,
): Promise<StepResult> {
  const start = Date.now()
  const bundleCommon = path.join(bundlePath, 'common')
  const targetCommon = path.join(targetPath, 'common')

  logInfo('installer', `Distributing PM-OS from ${bundleCommon} to ${targetCommon}`)

  if (!fs.existsSync(bundleCommon)) {
    logError('installer', `Bundle common/ not found at ${bundleCommon}`)
    return { success: false, message: 'Bundle common/ directory not found', duration: 0 }
  }

  try {
    // Count files first for progress reporting
    let totalFiles = 0
    const countDir = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory()) countDir(path.join(dir, entry.name))
        else totalFiles++
      }
    }
    countDir(bundleCommon)

    let copied = 0
    const fileCount = copyRecursive(bundleCommon, targetCommon, (rel) => {
      copied++
      onProgress?.(copied, totalFiles)
    })

    // Verify manifest checksums (sample 10%)
    const manifestPath = path.join(bundleCommon, 'MANIFEST.json')
    let verifyOk = true
    if (fs.existsSync(manifestPath)) {
      try {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'))
        const entries = Object.entries(manifest) as [string, string][]
        const sampleSize = Math.max(1, Math.ceil(entries.length * 0.1))
        const sample = entries.sort(() => Math.random() - 0.5).slice(0, sampleSize)

        for (const [file, expectedHash] of sample) {
          const targetFile = path.join(targetCommon, file)
          if (fs.existsSync(targetFile)) {
            const actualHash = checksumFile(targetFile)
            if (actualHash !== expectedHash) {
              logError('installer', `Checksum mismatch: ${file}`)
              verifyOk = false
            }
          }
        }
      } catch {
        logInfo('installer', 'Manifest verification skipped (parse error)')
      }
    }

    const duration = (Date.now() - start) / 1000
    logOk('installer', `Distributed ${fileCount} files (${duration.toFixed(1)}s)`)
    return {
      success: true,
      message: `${fileCount} files distributed${verifyOk ? '' : ' (checksum warnings)'}`,
      duration,
    }
  } catch (err: any) {
    logError('installer', `Distribution failed: ${err.message}`)
    return { success: false, message: err.message, duration: (Date.now() - start) / 1000 }
  }
}
