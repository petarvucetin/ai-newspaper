import { useState, useCallback } from "react"

const BOOKMARK_KEY = "ai-news-bookmarks"

function load(): Set<number> {
  try {
    return new Set(JSON.parse(localStorage.getItem(BOOKMARK_KEY) || "[]"))
  } catch {
    return new Set()
  }
}

function save(set: Set<number>) {
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify([...set]))
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState(load)

  const toggle = useCallback((id: number) => {
    setBookmarks((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      save(next)
      return next
    })
  }, [])

  const has = useCallback((id: number) => bookmarks.has(id), [bookmarks])

  return { bookmarks, toggle, has }
}
