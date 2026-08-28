/**
 * モードが `mock` のときに使う `ApiClient`。
 *
 * **バックエンドを起動していなくても3画面すべてが動くこと**が目的。
 * AGENTS.md の「fixture mode を常に維持する」と同じ思想で、外部通信を
 * 一切行わない。
 *
 * 値は `backend/tests/fixtures/` を fixture モードで通した実際のレスポンスを
 * 写したもの(`mocks/data/`)。ここで値を作らない。
 *
 * Polling の進捗も再現する。`getScan` が呼ばれるたびに1国ずつ完了させ、
 * 全国が終わったら `completed` を返して Polling を止められるようにする。
 */

import { ApiError } from '../api/errors';
import { sortRanking } from '../api/ranking';
import type {
  ApiClient,
  CountryCode,
  CountryDetail,
  CreateScanRequest,
  CreateScanResponse,
  RankingEntry,
  ScanSummary,
  TopicsResponse,
} from '../api/types';
import { DE_DETAIL } from './data/de';
import { GB_DETAIL } from './data/gb';
import { IN_DETAIL } from './data/in';
import { JP_DETAIL } from './data/jp';
import { MOCK_OPPORTUNITY_BRIEF, MOCK_VERSIONS } from './data/scan';
import { US_DETAIL } from './data/us';

/** 国別詳細。ランキング順ではなく、`Country` enum の宣言順に持つ。 */
const DETAILS: Record<CountryCode, CountryDetail> = {
  JP: JP_DETAIL,
  US: US_DETAIL,
  GB: GB_DETAIL,
  DE: DE_DETAIL,
  IN: IN_DETAIL,
};

const COUNTRY_LABELS: Record<CountryCode, string> = {
  JP: 'Japan',
  US: 'United States',
  GB: 'United Kingdom',
  DE: 'Germany',
  IN: 'India',
};

const ALL_COUNTRIES: CountryCode[] = ['JP', 'US', 'GB', 'DE', 'IN'];

const MOCK_SCAN_ID = 'scan_mock_001';

/**
 * 完了していく順序。fixture のランキング順(JP → DE → IN → GB → US)。
 *
 * 実際の Worker は国ごとに並行で終わるため到着順は保証されないが、
 * デモでは上位から埋まるほうが進捗として読みやすい。
 */
const COMPLETION_ORDER: CountryCode[] = ['JP', 'DE', 'IN', 'GB', 'US'];

function toRankingEntry(detail: CountryDetail): RankingEntry {
  return {
    country: detail.country,
    status: detail.status,
    need_gap_score: detail.need_gap_score,
    confidence: detail.confidence,
    demand: detail.components.demand,
    pain: detail.components.pain,
    solution_gap: detail.components.solution_gap,
    news_urgency: detail.components.news_urgency,
  };
}

export class MockApiClient implements ApiClient {
  /** `getScan` が呼ばれた回数。1回につき1国ずつ完了させる。 */
  private polls = 0;

  /** `createScan` で受け取った対象国を完了順に並べたもの。未開始なら空。 */
  private pending: CountryCode[] = [];

  listTopics(): Promise<TopicsResponse> {
    return Promise.resolve({
      topics: [
        {
          topic_id: 'elder_care',
          label: 'Elder Care',
          countries: ALL_COUNTRIES.map((country) => ({
            country,
            label: COUNTRY_LABELS[country],
          })),
        },
      ],
    });
  }

  createScan(request: CreateScanRequest): Promise<CreateScanResponse> {
    const requested = request.countries ?? ALL_COUNTRIES;
    this.polls = 0;
    this.pending = COMPLETION_ORDER.filter((country) => requested.includes(country));
    return Promise.resolve({ scan_id: MOCK_SCAN_ID, status: 'processing' });
  }

  getScan(scanId: string): Promise<ScanSummary> {
    if (this.pending.length === 0 || scanId !== MOCK_SCAN_ID) {
      return Promise.reject(
        new ApiError('mock scan not found', { status: 404, code: 'SCAN_NOT_FOUND' }),
      );
    }

    const total = this.pending.length;
    this.polls += 1;
    const completedCount = Math.min(this.polls, total);
    const finished = this.pending.slice(0, completedCount);
    const done = completedCount === total;
    const ranking = sortRanking(finished.map((country) => toRankingEntry(DETAILS[country])));

    return Promise.resolve({
      scan_id: MOCK_SCAN_ID,
      topic_id: 'elder_care',
      status: done ? 'completed' : 'processing',
      progress: { total, completed: completedCount },
      completed_countries: ranking.map((entry) => entry.country),
      ranking,
      // Brief は全国完了後に Top1 について生成される(docs/api.md)。
      opportunity_brief: done ? MOCK_OPPORTUNITY_BRIEF : null,
      versions: MOCK_VERSIONS,
    });
  }

  getCountry(scanId: string, country: CountryCode): Promise<CountryDetail> {
    if (this.pending.length === 0 || scanId !== MOCK_SCAN_ID) {
      return Promise.reject(
        new ApiError('mock scan not found', { status: 404, code: 'SCAN_NOT_FOUND' }),
      );
    }
    const detail = DETAILS[country];
    return Promise.resolve({ ...detail, scan_id: MOCK_SCAN_ID });
  }
}
