import { useState, useEffect, useCallback } from "react"
import { fetchArticles } from "@/api/client"
import type { ArticlesResponse } from "@/types"

export function useArticles(source: string) {
  const [data, setData] = useState<ArticlesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetchArticles(source)
      setData(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load articles")
    } finally {
      setLoading(false)
    }
  }, [source])

  useEffect(() => { load() }, [load])

  // Reload when a source is deleted (event fired from admin actions)
  useEffect(() => {
    const handler = () => { load() }
    window.addEventListener("articles-invalidated", handler)
    return () => window.removeEventListener("articles-invalidated", handler)
  }, [load])

  return { data, loading, error, reload: load }
}
