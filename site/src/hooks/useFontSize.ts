import { useState, useEffect, useCallback } from "react"

const FONT_KEY = "ai-news-font-size"
const FONT_MIN = 11
const FONT_MAX = 22
const FONT_DEFAULT = 16

export function useFontSize() {
  const [size, setSize] = useState(() => {
    const saved = parseInt(localStorage.getItem(FONT_KEY) || "", 10)
    return saved || FONT_DEFAULT
  })

  useEffect(() => {
    document.documentElement.style.setProperty("--article-font-size", `${size}px`)
    localStorage.setItem(FONT_KEY, String(size))
  }, [size])

  const inc = useCallback(() => setSize((s) => Math.min(FONT_MAX, s + 1)), [])
  const dec = useCallback(() => setSize((s) => Math.max(FONT_MIN, s - 1)), [])
  return { size, inc, dec }
}
