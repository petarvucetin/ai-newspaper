import type { ArticlesResponse, AdminData, FetchStatus } from "@/types"

const BASE = ""  // Vite proxy handles routing to FastAPI

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    credentials: "include",
    ...options,
  })
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
  return resp.json()
}

// --- Articles ---
export function fetchArticles(source = "all"): Promise<ArticlesResponse> {
  return request(`/api/articles?source=${encodeURIComponent(source)}`)
}

export function dismissArticle(articleId: number): Promise<void> {
  return request(`/dismiss/${articleId}`, { method: "DELETE" })
}

export function restoreArticle(articleId: number): Promise<void> {
  return request(`/restore/${articleId}`, { method: "POST" })
}

export function rateArticle(articleId: number, score: number): Promise<void> {
  return request(`/rate/${articleId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score }),
  })
}

export function removeSource(sourceId: number): Promise<void> {
  return request(`/source/${sourceId}`, { method: "DELETE" })
}

// --- Admin ---
export function fetchAdminData(): Promise<AdminData> {
  return request("/api/admin/data")
}

export function startFetch(): Promise<{ status: string }> {
  return request("/admin/fetch-now", { method: "POST" })
}

export function fetchFetchStatus(): Promise<FetchStatus> {
  return request("/admin/fetch-status")
}

export function saveSchedule(fetchTime: string, autoEnabled: boolean): Promise<void> {
  const form = new URLSearchParams()
  form.set("fetch_time", fetchTime)
  form.set("auto_enabled", autoEnabled ? "1" : "0")
  return request("/admin/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function uploadCookies(file: File): Promise<void> {
  const form = new FormData()
  form.append("cookies_file", file)
  return request("/admin/cookies/upload", { method: "POST", body: form })
}

export function deleteCookies(): Promise<void> {
  return request("/admin/cookies/delete", { method: "POST" })
}

export function addChannel(handle: string): Promise<void> {
  const form = new URLSearchParams()
  form.set("channel", handle)
  return request("/admin/channel/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function pinChannel(sourceId: number): Promise<void> {
  return request(`/admin/channel/${sourceId}/pin`, { method: "POST" })
}

export function unpinChannel(sourceId: number): Promise<void> {
  return request(`/admin/channel/${sourceId}/unpin`, { method: "POST" })
}

export async function deleteChannel(sourceId: number): Promise<void> {
  await request(`/admin/channel/${sourceId}/delete`, { method: "POST" })
  window.dispatchEvent(new Event("articles-invalidated"))
}

export function addSubreddit(name: string): Promise<void> {
  const form = new URLSearchParams()
  form.set("subreddit", name)
  return request("/admin/reddit/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function toggleReddit(sourceId: number): Promise<void> {
  return request(`/admin/reddit/${sourceId}/toggle`, { method: "POST" })
}

export async function deleteReddit(sourceId: number): Promise<void> {
  await request(`/admin/reddit/${sourceId}/delete`, { method: "POST" })
  window.dispatchEvent(new Event("articles-invalidated"))
}

export function addSource(name: string, sourceType: string, identifier: string, weight: number): Promise<void> {
  const form = new URLSearchParams()
  form.set("name", name)
  form.set("source_type", sourceType)
  form.set("identifier", identifier)
  form.set("weight", String(weight))
  return request("/admin/source/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function toggleSource(sourceId: number): Promise<void> {
  return request(`/admin/source/${sourceId}/toggle`, { method: "POST" })
}

export async function deleteSource(sourceId: number): Promise<void> {
  await request(`/admin/source/${sourceId}/delete`, { method: "POST" })
  window.dispatchEvent(new Event("articles-invalidated"))
}

export function addKeyword(keyword: string, weight: number): Promise<void> {
  const form = new URLSearchParams()
  form.set("keyword", keyword)
  form.set("weight", String(weight))
  return request("/admin/keyword/add", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  })
}

export function deleteKeyword(keywordId: number): Promise<void> {
  return request(`/admin/keyword/${keywordId}/delete`, { method: "POST" })
}

export function saveWeights(
  sources: { id: number; weight: number }[],
  keywords: { id: number; weight: number }[],
): Promise<{ ok: boolean; updated: number }> {
  return request("/admin/weights/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sources, keywords }),
  })
}
