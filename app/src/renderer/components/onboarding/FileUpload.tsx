import { useState, useRef } from 'react'
import { Upload, CheckCircle, XCircle } from 'lucide-react'

interface FileUploadProps {
  label: string
  accept: string
  onUpload: (filePath: string) => Promise<{ success: boolean; error?: string }>
}

export default function FileUpload({ label, accept, onUpload }: FileUploadProps) {
  const [fileName, setFileName] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<{ success: boolean; error?: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setFileName(file.name)
    setUploading(true)
    setResult(null)

    try {
      // In Electron, file input gives us the path
      const filePath = (file as any).path || file.name
      const uploadResult = await onUpload(filePath)
      setResult(uploadResult)
    } catch (err: any) {
      setResult({ success: false, error: err.message })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{
        display: 'block',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--text-primary)',
        marginBottom: 6,
        fontFamily: "'Inter', sans-serif",
      }}>
        {label}
      </label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          style={{
            padding: '10px 20px',
            background: 'transparent',
            color: 'var(--text-primary)',
            border: '1px solid #ff008844',
            borderRadius: 4,
            fontSize: 14,
            cursor: uploading ? 'not-allowed' : 'pointer',
            fontFamily: "'Inter', sans-serif",
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Upload size={14} />
          {uploading ? 'Uploading...' : 'Browse...'}
        </button>
        {fileName && (
          <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontFamily: "'Inter', sans-serif" }}>
            {fileName}
          </span>
        )}
        {result && (
          result.success ? (
            <CheckCircle size={16} color="#22c55e" />
          ) : (
            <XCircle size={16} color="#ef4444" />
          )
        )}
      </div>
      {result && !result.success && result.error && (
        <div style={{ fontSize: 12, color: '#ef4444', marginTop: 4 }}>
          {result.error}
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />
    </div>
  )
}
