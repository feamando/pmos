import DynamicList from './DynamicList'

interface GDriveLinksFieldProps {
  urls: string[]
  onChange: (urls: string[]) => void
}

function isValidGDriveUrl(url: string): boolean {
  if (!url.trim()) return true // empty is ok
  return url.startsWith('https://docs.google.com/') || url.startsWith('https://drive.google.com/')
}

export default function GDriveLinksField({ urls, onChange }: GDriveLinksFieldProps) {
  return (
    <div>
      <label style={{
        display: 'block',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--text-primary)',
        marginBottom: 8,
        fontFamily: "'Inter', sans-serif",
      }}>
        Google Drive File Links
      </label>
      <DynamicList
        items={urls}
        maxItems={5}
        minItems={0}
        addLabel="Add Link"
        onAdd={() => onChange([...urls, ''])}
        onRemove={(index) => onChange(urls.filter((_, i) => i !== index))}
        onUpdate={(index, value) => {
          const updated = [...urls]
          updated[index] = value
          onChange(updated)
        }}
        renderItem={(url, index, onUpdate) => {
          const invalid = url.trim() !== '' && !isValidGDriveUrl(url)
          return (
            <div>
              <input
                type="text"
                value={url}
                onChange={(e) => onUpdate(e.target.value)}
                placeholder="https://docs.google.com/document/d/..."
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: '#0a1929',
                  border: `1px solid ${invalid ? '#ef4444' : '#ff008844'}`,
                  color: '#ffffff',
                  borderRadius: 4,
                  fontSize: 14,
                  fontFamily: "'Inter', sans-serif",
                  boxSizing: 'border-box' as const,
                  outline: 'none',
                }}
              />
              {invalid && (
                <p style={{ fontSize: 11, color: '#ef4444', marginTop: 2, marginBottom: 0 }}>
                  Must be a Google Drive or Google Docs URL
                </p>
              )}
            </div>
          )
        }}
      />
    </div>
  )
}
