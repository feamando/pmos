import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import GDriveLinksField from '../../../src/renderer/components/user-setup/GDriveLinksField'

describe('GDriveLinksField', () => {
  it('renders URL inputs for each link', () => {
    const { container } = render(
      <GDriveLinksField urls={['https://docs.google.com/doc1', 'https://docs.google.com/doc2']} onChange={vi.fn()} />
    )
    const inputs = container.querySelectorAll('input')
    expect(inputs.length).toBe(2)
    expect(inputs[0]).toHaveValue('https://docs.google.com/doc1')
  })

  it('calls onChange when adding a new link', () => {
    const onChange = vi.fn()
    const { container } = render(<GDriveLinksField urls={['url1']} onChange={onChange} />)
    const addBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.includes('Add Link'))
    fireEvent.click(addBtn!)
    expect(onChange).toHaveBeenCalledWith(['url1', ''])
  })

  it('shows error for invalid non-GDrive URL', () => {
    const { container } = render(
      <GDriveLinksField urls={['https://example.com/file']} onChange={vi.fn()} />
    )
    expect(container.textContent).toContain('Must be a Google Drive')
  })

  it('does not show error for valid GDrive URL', () => {
    const { container } = render(
      <GDriveLinksField urls={['https://docs.google.com/document/d/abc']} onChange={vi.fn()} />
    )
    expect(container.textContent).not.toContain('Must be a Google Drive')
  })
})
