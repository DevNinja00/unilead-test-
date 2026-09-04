import { describe, it, expect } from 'vitest'

function computeOverallProgress(items: { progress: number }[]): number {
  if (items.length === 0) return 0
  const sum = items.reduce((acc, item) => acc + item.progress, 0)
  return Math.round(sum / items.length)
}

describe('computeOverallProgress', () => {
  it('returns 0 for empty array', () => {
    expect(computeOverallProgress([])).toBe(0)
  })

  it('averages progress values', () => {
    const items = [
      { progress: 50 },
      { progress: 100 },
      { progress: 0 },
    ]
    expect(computeOverallProgress(items)).toBe(50)
  })

  it('handles single item', () => {
    expect(computeOverallProgress([{ progress: 75 }])).toBe(75)
  })

  it('handles all at 100', () => {
    const items = [
      { progress: 100 },
      { progress: 100 },
      { progress: 100 },
    ]
    expect(computeOverallProgress(items)).toBe(100)
  })
})
