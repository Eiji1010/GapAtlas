/**
 * 3画面の要件テスト。
 *
 * 見た目ではなく **`docs/requirements.md` と `docs/methodology.md` の要件を
 * 満たしているか**を検証する。特に:
 *
 * - 2秒間隔の Polling と、終端状態での**停止**(止め忘れは無限ポーリング)
 * - `null` と `[]` の区別(Maps)
 * - UI の必須注記が実際に描画されていること
 */

import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { COUNTRY_LABELS } from '../labels';
import { MockApiClient } from '../mocks/mockClient';
import { POLL_INTERVAL_MS } from '../hooks/useScan';
import { CountryEvidenceScreen } from './CountryEvidenceScreen';
import { OpportunityBriefScreen } from './OpportunityBriefScreen';
import {
  NOTE_INSUFFICIENT_EVIDENCE,
  NOTE_MAPS,
  NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND,
  NOTE_SCORE_NOT_SEVERITY,
  NOTE_SOLUTION_GAP,
} from '../notes';
import type { ApiClient, CountryDetail, ScanSummary } from '../api/types';

function clickAnalyze() {
  screen.getByRole('button', { name: 'Analyze Live Signals' }).click();
}

/** タイマーを進めて Polling を1回起こす。 */
async function advanceOnePoll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
  });
}

describe('Screen 1: Discover', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('ボタンを押すとスキャンが始まり、2秒間隔で Polling する', async () => {
    const client = new MockApiClient();
    const getScan = vi.spyOn(client, 'getScan');
    render(<App client={client} />);

    await act(async () => {
      clickAnalyze();
    });

    const first = getScan.mock.calls.length;
    await advanceOnePoll();
    expect(getScan.mock.calls.length).toBeGreaterThan(first);
  });

  it('完了したら Polling を止める（無限ポーリングにしない）', async () => {
    const client = new MockApiClient();
    const getScan = vi.spyOn(client, 'getScan');
    render(<App client={client} />);

    await act(async () => {
      clickAnalyze();
    });
    // モックは1国ずつ完了する。終端まで進める。
    for (let index = 0; index < 10; index += 1) {
      await advanceOnePoll();
    }
    const settled = getScan.mock.calls.length;

    await advanceOnePoll();
    await advanceOnePoll();
    expect(getScan.mock.calls.length).toBe(settled);
  });

  it('処理中でも部分的なランキングと進捗を出す', async () => {
    const client = new MockApiClient();
    render(<App client={client} />);

    await act(async () => {
      clickAnalyze();
    });
    await advanceOnePoll();

    expect(screen.getByText(/進捗:/)).toBeTruthy();
    expect(screen.getByText('国別ランキング')).toBeTruthy();
  });

  it('ランキングは need_gap_score の降順で、null の国は末尾', async () => {
    const summary: ScanSummary = {
      scan_id: 's',
      topic_id: 'elder_care',
      status: 'completed',
      progress: { total: 3, completed: 3 },
      completed_countries: ['JP', 'US', 'GB'],
      ranking: [
        {
          country: 'JP',
          status: 'insufficient_evidence',
          need_gap_score: null,
          confidence: 60,
          demand: null,
          pain: null,
          solution_gap: null,
          news_urgency: null,
        },
        {
          country: 'US',
          status: 'completed',
          need_gap_score: 55,
          confidence: 90,
          demand: 54,
          pain: 70,
          solution_gap: 40,
          news_urgency: 60,
        },
        {
          country: 'GB',
          status: 'completed',
          need_gap_score: 58,
          confidence: 90,
          demand: 43,
          pain: 76,
          solution_gap: 63,
          news_urgency: 60,
        },
      ],
      opportunity_brief: null,
      versions: {
        query_profile_version: 'v',
        score_version: 'v',
        classifier_version: 'v',
        prompt_version: 'v',
      },
    };
    const client: ApiClient = {
      listTopics: () => Promise.reject(new Error('unused')),
      createScan: () => Promise.resolve({ scan_id: 's', status: 'processing' }),
      getScan: () => Promise.resolve(summary),
      getCountry: () => Promise.reject(new Error('unused')),
    };
    render(<App client={client} />);
    await act(async () => {
      clickAnalyze();
    });

    const rows = screen.getAllByRole('row').slice(1);
    const countries = rows.map((row) => row.querySelector('th')?.textContent);
    expect(countries).toEqual([COUNTRY_LABELS.GB, COUNTRY_LABELS.US, COUNTRY_LABELS.JP]);
  });

  it('API エラーでクラッシュせずエラー表示になる', async () => {
    //  は実タイマーを使う。ここだけ偽タイマーを戻す。
    vi.useRealTimers();
    const client: ApiClient = {
      listTopics: () => Promise.reject(new Error('unused')),
      createScan: () => Promise.reject(new Error('boom')),
      getScan: () => Promise.reject(new Error('unused')),
      getCountry: () => Promise.reject(new Error('unused')),
    };
    render(<App client={client} />);
    await act(async () => {
      clickAnalyze();
    });
    await waitFor(() => {
      expect(screen.getByText(/boom|失敗|エラー/)).toBeTruthy();
    });
  });
});

// --- Screen 2 ----------------------------------------------------------------------

const BASE_DETAIL: CountryDetail = {
  scan_id: 's',
  topic_id: 'elder_care',
  country: 'JP',
  status: 'completed',
  need_gap_score: 75,
  confidence: 91,
  components: { demand: 85, pain: 73, solution_gap: 65, news_urgency: 63 },
  confidence_breakdown: {
    data_completeness: 100,
    sample_sufficiency: 100,
    localization_quality: 70,
    source_agreement: 88,
    freshness: 95,
  },
  source_status: { trends: 'ok', related_queries: 'ok', search: 'ok', news: 'ok', maps: 'ok' },
  evidence: [{ id: 'E1', source: 'trends', summary: '需要が上昇', url: null }],
  trends: {
    series: [{ query: '介護', points: [{ timestamp: '2026-08-23T00:00:00Z', value: 90 }] }],
  },
  related_queries: [],
  search_results: [],
  news_results: [],
  maps_results: null,
  versions: {
    query_profile_version: 'elder-care-jp-v2',
    score_version: 'gapatlas-score-v1',
    classifier_version: 'gapatlas-classifier-v1-stub',
    prompt_version: 'gapatlas-prompt-v1-stub',
  },
  computed_at: '2026-08-28T00:00:00Z',
};

describe('Screen 2: Country Evidence', () => {
  it('必須注記を描画する（docs/methodology.md は UI にも反映する要件）', () => {
    render(
      <CountryEvidenceScreen country="JP" loading={false} detail={BASE_DETAIL} error={null} />,
    );
    for (const note of [
      NOTE_SCORE_NOT_SEVERITY,
      NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND,
      NOTE_SOLUTION_GAP,
      NOTE_MAPS,
    ]) {
      expect(screen.getAllByText(note).length).toBeGreaterThan(0);
    }
  });

  it('insufficient_evidence は「スコアなし」と Confidence を出す', () => {
    render(
      <CountryEvidenceScreen
        country="JP"
        loading={false}
        detail={{ ...BASE_DETAIL, status: 'insufficient_evidence', need_gap_score: null }}
        error={null}
      />,
    );
    expect(screen.getByText('スコアなし')).toBeTruthy();
    expect(screen.getByText('91')).toBeTruthy();
    expect(screen.getByText(NOTE_INSUFFICIENT_EVIDENCE)).toBeTruthy();
  });

  it('maps_results が null と [] で表示が変わる', () => {
    const { unmount } = render(
      <CountryEvidenceScreen country="JP" loading={false} detail={BASE_DETAIL} error={null} />,
    );
    expect(screen.getByText(/Maps を取得していません/)).toBeTruthy();
    unmount();

    render(
      <CountryEvidenceScreen
        country="JP"
        loading={false}
        detail={{ ...BASE_DETAIL, maps_results: [] }}
        error={null}
      />,
    );
    expect(screen.getByText(/該当は 0 件/)).toBeTruthy();
  });

  it('エラー時にクラッシュしない', () => {
    render(<CountryEvidenceScreen country="JP" loading={false} detail={null} error="not found" />);
    expect(screen.getByText('not found')).toBeTruthy();
  });
});

// --- Screen 3 ----------------------------------------------------------------------

describe('Screen 3: Opportunity Brief', () => {
  it('5節の見出しを要件どおりの英語で出し、引用を Evidence へリンクする', () => {
    render(
      <OpportunityBriefScreen
        country="JP"
        brief={{
          why_now: '需要が上がっている [E1]。',
          what_people_are_struggling_with: '不足 [E1]',
          visible_solutions: '可視 [E1]',
          what_this_does_not_prove: '深刻度ではない',
          next_validation: '一次調査',
          cited_evidence_ids: ['E1'],
        }}
        evidence={BASE_DETAIL.evidence}
      />,
    );
    for (const heading of [
      'WHY NOW',
      'WHAT PEOPLE ARE STRUGGLING WITH',
      'VISIBLE SOLUTIONS',
      'WHAT THIS DOES NOT PROVE',
      'NEXT VALIDATION',
    ]) {
      expect(screen.getByText(heading)).toBeTruthy();
    }
    const citation = screen.getAllByText('[E1]')[0] as HTMLAnchorElement;
    expect(citation.getAttribute('href')).toBe('#evidence-E1');
  });

  it('brief が null のときの表示を持つ', () => {
    render(<OpportunityBriefScreen country={null} brief={null} evidence={[]} />);
    expect(screen.getByText(/生成されていません/)).toBeTruthy();
  });
});

// --- モックモード ------------------------------------------------------------------

describe('モックモード', () => {
  it('バックエンド無しで3画面が動く', async () => {
    vi.useFakeTimers();
    const client = new MockApiClient();
    render(<App client={client} />);

    await act(async () => {
      clickAnalyze();
    });
    for (let index = 0; index < 10; index += 1) {
      await advanceOnePoll();
    }

    // Screen 1 -> Screen 2
    await act(async () => {
      screen.getAllByRole('button', { name: 'Evidence を見る' })[0]?.click();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText('Evidence')).toBeTruthy();

    // Screen 2 -> Screen 1 -> Screen 3
    await act(async () => {
      screen.getByRole('button', { name: '← ランキングへ戻る' }).click();
    });
    await act(async () => {
      screen.getByRole('button', { name: 'Opportunity Brief を見る' }).click();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText('WHY NOW')).toBeTruthy();
    vi.useRealTimers();
  });
});
