import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import DynamicList from '../../../src/renderer/components/user-setup/DynamicList'

describe('DynamicList', () => {
  it('renders all items', () => {
    const { container } = render(
      <DynamicList
        items={['a', 'b', 'c']}
        maxItems={5}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
        onUpdate={vi.fn()}
        renderItem={(item) => <span>{item}</span>}
      />
    )
    expect(container.textContent).toContain('a')
    expect(container.textContent).toContain('b')
    expect(container.textContent).toContain('c')
  })

  it('calls onAdd when + button clicked', () => {
    const onAdd = vi.fn()
    const { container } = render(
      <DynamicList
        items={['a']}
        maxItems={5}
        onAdd={onAdd}
        onRemove={vi.fn()}
        onUpdate={vi.fn()}
        renderItem={(item) => <span>{item}</span>}
        addLabel="Add Item"
      />
    )
    const addBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.includes('Add Item'))
    expect(addBtn).toBeTruthy()
    fireEvent.click(addBtn!)
    expect(onAdd).toHaveBeenCalledOnce()
  })

  it('hides add button when at maxItems', () => {
    const { container } = render(
      <DynamicList
        items={['a', 'b', 'c']}
        maxItems={3}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
        onUpdate={vi.fn()}
        renderItem={(item) => <span>{item}</span>}
        addLabel="Add"
      />
    )
    const addBtn = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.includes('Add'))
    expect(addBtn).toBeUndefined()
  })

  it('calls onRemove when X button clicked', () => {
    const onRemove = vi.fn()
    const { container } = render(
      <DynamicList
        items={['a', 'b']}
        maxItems={5}
        onAdd={vi.fn()}
        onRemove={onRemove}
        onUpdate={vi.fn()}
        renderItem={(item) => <span>{item}</span>}
      />
    )
    // X buttons are the ones with the lucide X icon (svg inside button)
    const removeButtons = Array.from(container.querySelectorAll('button')).filter(
      b => b.querySelector('svg') && !b.textContent?.includes('Add')
    )
    expect(removeButtons.length).toBe(2)
    fireEvent.click(removeButtons[0])
    expect(onRemove).toHaveBeenCalledWith(0)
  })

  it('hides remove buttons when at minItems', () => {
    const { container } = render(
      <DynamicList
        items={['a']}
        maxItems={5}
        minItems={1}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
        onUpdate={vi.fn()}
        renderItem={(item) => <span>{item}</span>}
      />
    )
    const removeButtons = Array.from(container.querySelectorAll('button')).filter(
      b => b.querySelector('svg') && !b.textContent?.includes('Add')
    )
    expect(removeButtons.length).toBe(0)
  })
})
