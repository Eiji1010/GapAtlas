/**
 * ランキングの並び順。
 *
 * 正本は `docs/api.md`「`ranking` は `need_gap_score` の降順。`need_gap_score`
 * が `null` の国(`INSUFFICIENT_EVIDENCE`)は末尾へ回す。`need_gap_score = 0`
 * は有効なスコアであり `null` より上に来る。末尾側は `INSUFFICIENT_EVIDENCE`
 * → `FAILED` の順」。
 *
 * 並べ替えは本来 API の責務であり、ここでの並べ替えは表示側の防御である。
 * 部分的なランキングを Polling で受け取る画面が、順序の崩れた応答をそのまま
 * 見せないようにする。
 */

import type { CountryStatus, RankingEntry } from './types';

/** 末尾側の順序。`FAILED` は必ず最後(docs/api.md)。 */
const STATUS_RANK: Record<CountryStatus, number> = {
  completed: 0,
  insufficient_evidence: 1,
  failed: 2,
  processing: 3,
  pending: 4,
};

function compare(a: RankingEntry, b: RankingEntry): number {
  // `null` は 0(取りうる最小スコア)として並べ、同点は status で決着させる。
  // これによりスコアを持つ国が必ず先に来る。
  const scoreA = a.need_gap_score ?? 0;
  const scoreB = b.need_gap_score ?? 0;
  if (scoreA !== scoreB) {
    return scoreB - scoreA;
  }
  if (STATUS_RANK[a.status] !== STATUS_RANK[b.status]) {
    return STATUS_RANK[a.status] - STATUS_RANK[b.status];
  }
  if (a.confidence !== b.confidence) {
    return b.confidence - a.confidence;
  }
  return a.country.localeCompare(b.country);
}

/** ランキングを表示順に並べ替える。元の配列は変更しない。 */
export function sortRanking(ranking: readonly RankingEntry[]): RankingEntry[] {
  return [...ranking].sort(compare);
}
