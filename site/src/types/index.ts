export interface Article {
  id: number
  source_id: number
  external_id: string
  title: string
  url: string
  summary: string | null
  author: string | null
  published_at: string | null
  fetched_at: string
  relevancy_score: number
  display_score: number
  thumbnail_url: string | null
  num_comments: number
  upvotes: number
  source_name: string
  source_type: string
  user_rating: number | null
  dismissed: number
  dismissed_at: string | null
  auto_dismissed: number
}

export interface Comment {
  article_id: number
  author: string
  body: string
  score: number
  comment_url: string
}

export interface ArticleItem {
  article: Article
  old: boolean
  comments?: Comment[]
}

export interface ArticlesResponse {
  fresh: ArticleItem[]
  archive: ArticleItem[]
  active_filter: string
  last_fetched_utc: string | null
  source_counts: Record<string, number>
}

export interface Source {
  id: number
  name: string
  source_type: string
  identifier: string
  weight: number
  enabled: number
  created_at: string
}

export interface KeywordWeight {
  id: number
  keyword: string
  weight: number
  hits: number
}

export interface CookiesStatus {
  exists: boolean
  age_days: number | null
  warning: boolean
}

export interface ApiUsageRow {
  model: string
  purpose: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  calls: number
}

export interface ApiUsageSummary {
  totals: ApiUsageRow[]
  overall: {
    total_cost: number | null
    total_input: number | null
    total_output: number | null
    total_calls: number | null
  }
  daily: { day: string; cost_usd: number; calls: number }[]
}

export interface AdminData {
  sources: Source[]
  channels: Source[]
  reddit_sources: Source[]
  keywords: KeywordWeight[]
  last_fetched: string | null
  schedule_time: string
  auto_enabled: boolean
  cookies_status: CookiesStatus
  api_usage: ApiUsageSummary
}

export interface FetchStatus {
  status: "idle" | "running" | "done" | "error"
  log: string[]
  inserted: number
  skipped: number
  total: number
  error: string
  elapsed: number
}
