import { createWriteStream, existsSync, mkdirSync } from 'fs'
import { createHash } from 'crypto'
import { readFile } from 'fs/promises'
import { tmpdir } from 'os'
import path from 'path'
import https from 'https'
import http from 'http'
import { logInfo, logError } from '../installer/logger'

const UPDATE_DIR = path.join(tmpdir(), 'pmos-update')

export function getUpdateDir(): string {
  if (!existsSync(UPDATE_DIR)) {
    mkdirSync(UPDATE_DIR, { recursive: true })
  }
  return UPDATE_DIR
}

export async function downloadBinary(
  url: string,
  destPath: string,
  onProgress?: (downloaded: number, total: number) => void
): Promise<void> {
  logInfo('updater', `Downloading from: ${url}`)

  const dir = path.dirname(destPath)
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })

  return new Promise((resolve, reject) => {
    const doRequest = (requestUrl: string, redirectCount = 0) => {
      if (redirectCount > 5) {
        reject(new Error('Too many redirects'))
        return
      }

      const client = requestUrl.startsWith('https') ? https : http
      client.get(requestUrl, (res) => {
        // Handle redirects
        if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          doRequest(res.headers.location, redirectCount + 1)
          return
        }

        // Handle GDrive virus scan interstitial (HTML with confirm token)
        const contentType = res.headers['content-type'] || ''
        if (contentType.includes('text/html')) {
          let body = ''
          res.on('data', (chunk: Buffer) => { body += chunk.toString() })
          res.on('end', () => {
            const confirmMatch = body.match(/confirm=([0-9A-Za-z_-]+)/)
            if (confirmMatch) {
              const confirmUrl = `${requestUrl}&confirm=${confirmMatch[1]}`
              logInfo('updater', 'GDrive confirmation required, retrying with token')
              doRequest(confirmUrl, redirectCount + 1)
            } else {
              reject(new Error('GDrive returned HTML but no confirm token found'))
            }
          })
          return
        }

        if (res.statusCode !== 200) {
          reject(new Error(`Download failed with status ${res.statusCode}`))
          return
        }

        const totalBytes = parseInt(res.headers['content-length'] || '0', 10)
        let downloadedBytes = 0

        const file = createWriteStream(destPath)
        res.on('data', (chunk: Buffer) => {
          downloadedBytes += chunk.length
          if (onProgress && totalBytes > 0) {
            onProgress(downloadedBytes, totalBytes)
          }
        })
        res.pipe(file)
        file.on('finish', () => {
          file.close()
          logInfo('updater', `Download complete: ${downloadedBytes} bytes`)
          resolve()
        })
        file.on('error', (err) => {
          reject(err)
        })
      }).on('error', (err) => {
        reject(new Error(`Download request failed: ${err.message}`))
      })
    }

    doRequest(url)
  })
}

export async function verifyChecksum(filePath: string, expectedSha256: string): Promise<{ valid: boolean; actual: string }> {
  if (!existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`)
  }

  const fileBuffer = await readFile(filePath)
  const hash = createHash('sha256')
  hash.update(fileBuffer)
  const actual = hash.digest('hex')

  const valid = actual === expectedSha256
  if (!valid) {
    logError('updater', `Checksum mismatch: expected ${expectedSha256}, got ${actual}`)
  } else {
    logInfo('updater', 'Checksum verified OK')
  }

  return { valid, actual }
}
