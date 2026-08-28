/** 画面に出す日本語ラベル。API が返す enum 値の対応表。 */

import type {
  CountryCode,
  CountryStatus,
  NewsRelevance,
  PainCategory,
  ScanStatus,
  SolutionCategory,
  SourceName,
  SourceStatus,
} from './api/types';

/** MVP 対象国。順序は `docs/api.md` の例(JP・US・GB・DE・IN)。 */
export const MVP_COUNTRIES: readonly CountryCode[] = ['JP', 'US', 'GB', 'DE', 'IN'];

export const COUNTRY_LABELS: Record<CountryCode, string> = {
  JP: '日本 (Japan)',
  US: 'アメリカ (United States)',
  GB: 'イギリス (United Kingdom)',
  DE: 'ドイツ (Germany)',
  IN: 'インド (India)',
};

export const COUNTRY_STATUS_LABELS: Record<CountryStatus, string> = {
  pending: '待機中',
  processing: '処理中',
  completed: '完了',
  insufficient_evidence: 'Insufficient Evidence(判断材料が不足)',
  failed: '失敗',
};

export const SCAN_STATUS_LABELS: Record<ScanStatus, string> = {
  processing: '処理中',
  completed: '完了',
  partially_failed: '一部失敗',
};

export const SOURCE_LABELS: Record<SourceName, string> = {
  trends: 'Trends',
  related_queries: 'Related Queries',
  search: 'Search',
  news: 'News',
  maps: 'Maps',
};

export const SOURCE_STATUS_LABELS: Record<SourceStatus, string> = {
  ok: '取得済み',
  missing: '欠損',
  not_requested: '取得していない',
};

export const COMPONENT_LABELS = {
  demand: 'Demand',
  pain: 'Pain',
  solution_gap: 'Solution Gap',
  news_urgency: 'News Urgency',
} as const;

export const CONFIDENCE_BREAKDOWN_LABELS = {
  data_completeness: 'Data completeness',
  sample_sufficiency: 'Sample sufficiency',
  localization_quality: 'Localization quality',
  source_agreement: 'Source agreement',
  freshness: 'Freshness',
} as const;

/** 分類ラベルは英語のまま出す。スコア定義(docs/scoring.md)の識別子そのもの。 */
export const PAIN_CATEGORY_LABELS: Record<PainCategory, string> = {
  ACCESS: 'ACCESS',
  SHORTAGE: 'SHORTAGE',
  WAIT_TIME: 'WAIT_TIME',
  COST: 'COST',
  QUALITY: 'QUALITY',
  WORKFORCE: 'WORKFORCE',
  NEUTRAL: 'NEUTRAL',
};

export const SOLUTION_CATEGORY_LABELS: Record<SolutionCategory, string> = {
  DIRECT_PROVIDER: 'DIRECT_PROVIDER',
  MARKETPLACE: 'MARKETPLACE',
  GOVERNMENT: 'GOVERNMENT',
  INFORMATION: 'INFORMATION',
  NEWS: 'NEWS',
  OTHER: 'OTHER',
};

export const NEWS_RELEVANCE_LABELS: Record<NewsRelevance, string> = {
  DIRECTLY_RELEVANT: 'DIRECTLY_RELEVANT',
  RELATED: 'RELATED',
  UNRELATED: 'UNRELATED',
};

/** `null` のスコアは 0 と区別して表示する(欠損と「値が 0」は別)。 */
export function formatScore(value: number | null): string {
  return value === null ? '—' : String(value);
}

/** ISO8601 の日付部分だけを出す。ロケール依存の書式にしない。 */
export function formatDate(value: string | null): string {
  return value === null ? '—' : value.slice(0, 10);
}
