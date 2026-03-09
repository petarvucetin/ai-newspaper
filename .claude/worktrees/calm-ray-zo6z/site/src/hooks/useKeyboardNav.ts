import { useState, useEffect, useCallback, useRef } from "react"

interface UseKeyboardNavOptions {
  onDismiss?: (id: number) => void
  onBookmark?: (id: number) => void
  onOpen?: (url: string) => void
}

export function useKeyboardNav(
  articleIds: number[],
  options: UseKeyboardNavOptions,
) {
  const [focusIdx, setFocusIdx] = useState(-1)
  const [hintVisible, setHintVisible] = useState(false)
  const idsRef = useRef(articleIds)
  idsRef.current = articleIds

  const focus = useCallback((idx: number) => {
    const ids = idsRef.current
    if (ids.length === 0) return
    setFocusIdx(Math.max(0, Math.min(idx, ids.length - 1)))
  }, [])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) return

      if (e.key === "?") {
        setHintVisible((v) => !v)
        return
      }
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault()
        setFocusIdx((i) => {
          const next = i < 0 ? 0 : Math.min(i + 1, idsRef.current.length - 1)
          return next
        })
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault()
        setFocusIdx((i) => Math.max(0, i - 1))
      } else if (e.key === "Enter") {
        setFocusIdx((i) => {
          if (i >= 0) {
            const el = document.querySelector(`[data-article-id="${idsRef.current[i]}"] .article-title a`) as HTMLAnchorElement
            if (el) window.open(el.href, "_blank", "noopener")
          }
          return i
        })
      } else if (e.key === "d") {
        setFocusIdx((i) => {
          if (i >= 0 && options.onDismiss) options.onDismiss(idsRef.current[i])
          return i
        })
      } else if (e.key === "b") {
        setFocusIdx((i) => {
          if (i >= 0 && options.onBookmark) options.onBookmark(idsRef.current[i])
          return i
        })
      }
    }

    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [options, focus])

  return { focusIdx, hintVisible }
}
