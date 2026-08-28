/**
 * `docs/api.md` の4エンドポイントが返す JSON の型。
 *
 * 正本は `docs/api.md` と、実際に返している
 * `backend/src/gapatlas/api/handlers.py` の `country_payload` / `ApiService`。
 * ここで推測して項目を足さない。バックエンドが返さない値は UI にも出せない。
 */

export type CountryCode = 'JP' | 'US' | 'GB' | 'DE' | 'IN';

export type TopicId = 'elder_care';

/** スキャン全体の状態。`completed` / `partially_failed` が終端。 */
export type ScanStatus = 'processing' | 'completed' | 'partially_failed';

/** 国単位の処理状態。`insufficient_evidence` はエラーではない。 */
export type CountryStatus =
  'pending' | 'processing' | 'completed' | 'insufficient_evidence' | 'failed';

export type SourceName = 'trends' | 'related_queries' | 'search' | 'news' | 'maps';

export type SourceStatus = 'ok' | 'missing' | 'not_requested';

/** 再現可能性のため結果に必ず含まれるバージョン識別子。 */
export interface Versions {
  query_profile_version: string;
  score_version: string;
  classifier_version: string;
  prompt_version: string;
}

// --- GET /api/v1/topics ---------------------------------------------------------------

export interface CountryOption {
  country: CountryCode;
  label: string;
}

export interface Topic {
  topic_id: TopicId;
  label: string;
  countries: CountryOption[];
}

export interface TopicsResponse {
  topics: Topic[];
}

// --- POST /api/v1/scans ---------------------------------------------------------------

export interface CreateScanRequest {
  topic_id: TopicId;
  countries?: CountryCode[];
}

export interface CreateScanResponse {
  scan_id: string;
  status: ScanStatus;
}

// --- GET /api/v1/scans/{scan_id} ------------------------------------------------------

export interface ScanProgress {
  total: number;
  completed: number;
}

/** ランキング1行。`need_gap_score` が `null` の国は末尾へ回る。 */
export interface RankingEntry {
  country: CountryCode;
  status: CountryStatus;
  need_gap_score: number | null;
  confidence: number;
  demand: number | null;
  pain: number | null;
  solution_gap: number | null;
  news_urgency: number | null;
}

export interface OpportunityBrief {
  why_now: string;
  what_people_are_struggling_with: string;
  visible_solutions: string;
  what_this_does_not_prove: string;
  next_validation: string;
  /** 本文が引用した Evidence の id(`E1` 形式)。 */
  cited_evidence_ids: string[];
}

export interface ScanSummary {
  scan_id: string;
  topic_id: TopicId;
  status: ScanStatus;
  progress: ScanProgress;
  completed_countries: CountryCode[];
  ranking: RankingEntry[];
  opportunity_brief: OpportunityBrief | null;
  versions: Versions;
}

// --- GET /api/v1/scans/{scan_id}/countries/{country} -----------------------------------

export interface Evidence {
  id: string;
  source: SourceName;
  summary: string;
  /** SerpApi のレスポンスに含まれていた URL のみ。無い場合は `null`。 */
  url: string | null;
}

export interface TrendPoint {
  /** ISO8601 UTC。 */
  timestamp: string;
  value: number;
}

export interface TrendsSeries {
  query: string;
  /** 古い順(timestamp 昇順)。 */
  points: TrendPoint[];
}

export interface TrendsTimeseries {
  series: TrendsSeries[];
}

export type PainCategory =
  'ACCESS' | 'SHORTAGE' | 'WAIT_TIME' | 'COST' | 'QUALITY' | 'WORKFORCE' | 'NEUTRAL';

export type SolutionCategory =
  'DIRECT_PROVIDER' | 'MARKETPLACE' | 'GOVERNMENT' | 'INFORMATION' | 'NEWS' | 'OTHER';

export type NewsRelevance = 'DIRECTLY_RELEVANT' | 'RELATED' | 'UNRELATED';

/** LLM の分類結果。分類のみで、スコアは算出しない。 */
export interface Classification<TCategory extends string> {
  classification: TCategory;
  /** 0.0〜1.0。 */
  confidence: number;
}

/** 元データと分類結果の組。UI が「この結果は◯◯と分類された」を示せる。 */
export interface Classified<TItem, TCategory extends string> {
  item: TItem;
  classification: Classification<TCategory>;
}

export interface RisingQuery {
  query: string;
  growth_percent: number;
  /** 数値化できず上限値で代替した場合 `true`。 */
  is_breakout: boolean;
  raw_value: string | null;
  link: string | null;
}

export interface SearchResultItem {
  position: number;
  title: string;
  link: string;
  snippet: string | null;
  displayed_link: string | null;
  source: string | null;
}

export interface NewsArticle {
  position: number;
  title: string;
  link: string;
  source_name: string | null;
  /** ISO8601 UTC。パースできなかった場合は `null`。 */
  published_at: string | null;
  raw_date: string | null;
}

export interface MapsPlace {
  position: number;
  title: string;
  place_id: string | null;
  rating: number | null;
  reviews: number | null;
  place_type: string | null;
  address: string | null;
  link: string | null;
}

export type ClassifiedRisingQuery = Classified<RisingQuery, PainCategory>;
export type ClassifiedSearchResult = Classified<SearchResultItem, SolutionCategory>;
export type ClassifiedNewsArticle = Classified<NewsArticle, NewsRelevance>;

export interface ScoreComponents {
  demand: number | null;
  pain: number | null;
  solution_gap: number | null;
  news_urgency: number | null;
}

export interface ConfidenceBreakdown {
  data_completeness: number | null;
  sample_sufficiency: number | null;
  localization_quality: number | null;
  source_agreement: number | null;
  freshness: number | null;
}

export interface CountryDetail {
  scan_id: string;
  topic_id: TopicId;
  country: CountryCode;
  status: CountryStatus;
  /** `insufficient_evidence` / `failed` の場合は `null`。 */
  need_gap_score: number | null;
  /** `need_gap_score` が `null` でも必ず返る。 */
  confidence: number;
  components: ScoreComponents;
  confidence_breakdown: ConfidenceBreakdown;
  source_status: Partial<Record<SourceName, SourceStatus>>;
  evidence: Evidence[];
  trends: TrendsTimeseries | null;
  related_queries: ClassifiedRisingQuery[];
  search_results: ClassifiedSearchResult[];
  news_results: ClassifiedNewsArticle[];
  /**
   * **`null` は「取得していない」(Top2 以外)、`[]` は「取得したが0件」。**
   * 意味が違うので UI で区別する(docs/api.md)。
   */
  maps_results: MapsPlace[] | null;
  versions: Versions;
  /** ISO8601 UTC。 */
  computed_at: string;
}

// --- エラー ---------------------------------------------------------------------------

export type ApiErrorCode =
  | 'INVALID_REQUEST'
  | 'SCAN_NOT_FOUND'
  | 'COUNTRY_NOT_FOUND'
  | 'ROUTE_NOT_FOUND'
  | 'METHOD_NOT_ALLOWED'
  | 'INTERNAL_ERROR';

export interface ApiErrorBody {
  error: {
    code: ApiErrorCode | string;
    message: string;
  };
}

/** 4エンドポイントを型付きで呼ぶ薄い層の契約。mock と live が実装する。 */
export interface ApiClient {
  listTopics(signal?: AbortSignal): Promise<TopicsResponse>;
  createScan(request: CreateScanRequest, signal?: AbortSignal): Promise<CreateScanResponse>;
  getScan(scanId: string, signal?: AbortSignal): Promise<ScanSummary>;
  getCountry(scanId: string, country: CountryCode, signal?: AbortSignal): Promise<CountryDetail>;
}
