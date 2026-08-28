/**
 * `JP` のモック詳細。
 *
 * `backend/tests/fixtures/` を fixture モードで通した実際の
 * `GET /api/v1/scans/{scan_id}/countries/{country}` のレスポンスを写したもの。
 * **手で値を変えないこと。** 変えると fixture と矛盾する。
 */

import type { CountryDetail } from '../../api/types';

export const JP_DETAIL: CountryDetail = {
  scan_id: 'scan_demo_001',
  topic_id: 'elder_care',
  country: 'JP',
  status: 'completed',
  need_gap_score: 75,
  confidence: 91,
  components: {
    demand: 85,
    pain: 73,
    solution_gap: 65,
    news_urgency: 64,
  },
  confidence_breakdown: {
    data_completeness: 100,
    sample_sufficiency: 100,
    localization_quality: 70,
    source_agreement: 84,
    freshness: 96,
  },
  source_status: {
    trends: 'ok',
    related_queries: 'ok',
    search: 'ok',
    news: 'ok',
    maps: 'ok',
  },
  evidence: [
    {
      id: 'E1',
      source: 'trends',
      summary: '直近4週の検索需要が前8週比で 31.8% 上昇した',
      url: null,
    },
    {
      id: 'E2',
      source: 'related_queries',
      summary: '急上昇クエリ 12 件のうち、不足・待機・到達困難に分類されたものが 8 件',
      url: 'https://trends.google.com/trends/explore?q=%E7%89%B9%E9%A4%8A%20%E5%BE%85%E6%A9%9F%E6%9C%9F%E9%96%93&date=today+12-m&geo=JP',
    },
    {
      id: 'E3',
      source: 'search',
      summary: '検索結果 上位10件のうち、直接申し込める提供者・仲介は 3 件',
      url: 'https://www.example.go.jp/kaigo/service-search/',
    },
    {
      id: 'E4',
      source: 'news',
      summary: '報道 9 件のうち、この課題そのものを扱った記事が 7 件',
      url: 'https://news.example.com/fixture/jp_news_01',
    },
    {
      id: 'E5',
      source: 'maps',
      summary: '代表都市の周辺で 6 件の事業者が地図検索に現れた(供給量ではない)',
      url: null,
    },
  ],
  trends: {
    series: [
      {
        query: '介護',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 52.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 51.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 52.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 52.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 64.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 76.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 81.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 90.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 100.0,
          },
        ],
      },
      {
        query: '介護施設',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 51.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 59.0,
          },
        ],
      },
      {
        query: '在宅介護',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 17.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 22.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 25.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 26.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 26.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 26.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 28.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 37.0,
          },
        ],
      },
    ],
  },
  related_queries: [
    {
      item: {
        query: '特養 待機期間',
        growth_percent: 180.0,
        is_breakout: false,
        raw_value: '+180%',
        link: 'https://trends.google.com/trends/explore?q=%E7%89%B9%E9%A4%8A%20%E5%BE%85%E6%A9%9F%E6%9C%9F%E9%96%93&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '介護施設 空きがない',
        growth_percent: 5000.0,
        is_breakout: false,
        raw_value: 'Breakout',
        link: 'https://trends.google.com/trends/explore?q=%E4%BB%8B%E8%AD%B7%E6%96%BD%E8%A8%AD%20%E7%A9%BA%E3%81%8D%E3%81%8C%E3%81%AA%E3%81%84&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '訪問介護 断られた',
        growth_percent: 450.0,
        is_breakout: false,
        raw_value: '+450%',
        link: 'https://trends.google.com/trends/explore?q=%E8%A8%AA%E5%95%8F%E4%BB%8B%E8%AD%B7%20%E6%96%AD%E3%82%89%E3%82%8C%E3%81%9F&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'ヘルパー 人手不足',
        growth_percent: 320.0,
        is_breakout: false,
        raw_value: '+320%',
        link: 'https://trends.google.com/trends/explore?q=%E3%83%98%E3%83%AB%E3%83%91%E3%83%BC%20%E4%BA%BA%E6%89%8B%E4%B8%8D%E8%B6%B3&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'ショートステイ 予約 取れない',
        growth_percent: 260.0,
        is_breakout: false,
        raw_value: '+260%',
        link: 'https://trends.google.com/trends/explore?q=%E3%82%B7%E3%83%A7%E3%83%BC%E3%83%88%E3%82%B9%E3%83%86%E3%82%A4%20%E4%BA%88%E7%B4%84%20%E5%8F%96%E3%82%8C%E3%81%AA%E3%81%84&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '介護費用 払えない',
        growth_percent: 210.0,
        is_breakout: false,
        raw_value: '+210%',
        link: 'https://trends.google.com/trends/explore?q=%E4%BB%8B%E8%AD%B7%E8%B2%BB%E7%94%A8%20%E6%89%95%E3%81%88%E3%81%AA%E3%81%84&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '介護 待機 順番',
        growth_percent: 120.0,
        is_breakout: false,
        raw_value: '+120%',
        link: 'https://trends.google.com/trends/explore?q=%E4%BB%8B%E8%AD%B7%20%E5%BE%85%E6%A9%9F%20%E9%A0%86%E7%95%AA&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '老人ホーム 費用 相場',
        growth_percent: 140.0,
        is_breakout: false,
        raw_value: '+140%',
        link: 'https://trends.google.com/trends/explore?q=%E8%80%81%E4%BA%BA%E3%83%9B%E3%83%BC%E3%83%A0%20%E8%B2%BB%E7%94%A8%20%E7%9B%B8%E5%A0%B4&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '地方 介護施設 少ない',
        growth_percent: 90.0,
        is_breakout: false,
        raw_value: '+90%',
        link: 'https://trends.google.com/trends/explore?q=%E5%9C%B0%E6%96%B9%20%E4%BB%8B%E8%AD%B7%E6%96%BD%E8%A8%AD%20%E5%B0%91%E3%81%AA%E3%81%84&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '介護士 離職率',
        growth_percent: 75.0,
        is_breakout: false,
        raw_value: '+75%',
        link: 'https://trends.google.com/trends/explore?q=%E4%BB%8B%E8%AD%B7%E5%A3%AB%20%E9%9B%A2%E8%81%B7%E7%8E%87&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '介護施設 対応 悪い',
        growth_percent: 60.0,
        is_breakout: false,
        raw_value: '+60%',
        link: 'https://trends.google.com/trends/explore?q=%E4%BB%8B%E8%AD%B7%E6%96%BD%E8%A8%AD%20%E5%AF%BE%E5%BF%9C%20%E6%82%AA%E3%81%84&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'QUALITY',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: '介護保険 申請 方法',
        growth_percent: 40.0,
        is_breakout: false,
        raw_value: '+40%',
        link: 'https://trends.google.com/trends/explore?q=%E4%BB%8B%E8%AD%B7%E4%BF%9D%E9%99%BA%20%E7%94%B3%E8%AB%8B%20%E6%96%B9%E6%B3%95&date=today+12-m&geo=JP',
      },
      classification: {
        classification: 'NEUTRAL',
        confidence: 0.4,
      },
    },
  ],
  search_results: [
    {
      item: {
        position: 1,
        title: '介護サービス情報公表システム（架空版） | 架空厚生福祉ポータル',
        link: 'https://www.example.go.jp/kaigo/service-search/',
        snippet:
          '架空の公的ポータルです。事業所の所在地・サービス種別・空き状況の公表情報を検索できます。',
        displayed_link: 'www.example.go.jp › kaigo',
        source: 'www.example.go.jp',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: '介護保険で使えるサービス一覧 | 架空市 福祉課',
        link: 'https://www.example.lg.jp/fukushi/kaigo-service/',
        snippet:
          '架空市が提供する介護保険サービスの種類、自己負担割合、申請窓口をまとめた案内ページです。',
        displayed_link: 'www.example.lg.jp › fukushi',
        source: 'www.example.lg.jp',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: '介護サービスの種類と選び方を解説 | 介護まるわかりガイド（架空）',
        link: 'https://kaigo-guide.example.co.jp/service-types/',
        snippet:
          '訪問介護・通所介護・施設サービスの違いと、家族が選ぶときの比較ポイントを解説した記事です。',
        displayed_link: 'kaigo-guide.example.co.jp',
        source: 'kaigo-guide.example.co.jp',
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: '全国の介護サービスを条件で探す | 介護ナビ（架空）',
        link: 'https://kaigo-navi.example.co.jp/search/',
        snippet:
          '地域・サービス種別・費用帯から介護事業所を検索し、複数事業所へまとめて問い合わせできます。',
        displayed_link: 'kaigo-navi.example.co.jp › search',
        source: 'kaigo-navi.example.co.jp',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: '在宅介護で受けられるサービスまとめ | 架空シニア情報室',
        link: 'https://senior-lab.example.co.jp/home-care/',
        snippet: null,
        displayed_link: null,
        source: null,
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 6,
        title: '訪問介護・デイサービス | 架空あおぞら介護サービス',
        link: 'https://aozora-care.example.co.jp/',
        snippet:
          '架空の在宅介護事業所です。訪問介護、通所介護、福祉用具貸与を同一法人で提供しています。',
        displayed_link: 'aozora-care.example.co.jp',
        source: 'aozora-care.example.co.jp',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: '地域包括支援センターのご案内（架空市）',
        link: 'https://www.example.lg.jp/fukushi/houkatsu/',
        snippet:
          '介護に関する初回相談の窓口案内です。担当地区、受付時間、相談の流れを掲載しています。',
        displayed_link: 'www.example.lg.jp › fukushi',
        source: 'www.example.lg.jp',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 8,
        title: '介護サービス費用の目安 | 架空くらし相談室',
        link: 'https://kurashi-soudan.example.co.jp/kaigo-cost/',
        snippet: null,
        displayed_link: null,
        source: null,
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 9,
        title: '架空ひまわり在宅介護ステーション | 24時間対応の訪問介護',
        link: 'https://himawari-care.example.co.jp/',
        snippet:
          '架空の訪問介護ステーションです。夜間対応型訪問介護と定期巡回サービスを実施しています。',
        displayed_link: 'himawari-care.example.co.jp',
        source: 'himawari-care.example.co.jp',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 10,
        title: '介護サービスの利用者負担見直しを議論 | 架空福祉ニュース',
        link: 'https://news.example.co.jp/welfare/kaigo-futan-2026/',
        snippet: '架空の報道記事です。次期制度改定に向けた利用者負担の議論の経緯をまとめています。',
        displayed_link: 'news.example.co.jp › welfare',
        source: 'news.example.co.jp',
      },
      classification: {
        classification: 'NEWS',
        confidence: 0.9,
      },
    },
  ],
  news_results: [
    {
      item: {
        position: 1,
        title: '介護職員の有効求人倍率が過去最高を更新 架空県で人手不足深刻',
        link: 'https://news.example.com/fixture/jp_news_01',
        source_name: '架空福祉新聞',
        published_at: '2026-08-27T09:36:00Z',
        raw_date: '08/27/2026, 06:36 PM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: '特別養護老人ホーム、職員不足で3割が受け入れ制限',
        link: 'https://news.example.com/fixture/jp_news_02',
        source_name: '架空医療介護ジャーナル',
        published_at: '2026-08-26T04:48:00Z',
        raw_date: '08/26/2026, 01:48 PM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: '訪問介護事業所の廃業が最多に 担い手確保進まず',
        link: 'https://news.example.com/fixture/jp_news_03',
        source_name: '架空経済タイムズ',
        published_at: '2026-08-24T19:12:00Z',
        raw_date: '08/25/2026, 04:12 AM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: '外国人介護人材の受け入れ拡大へ 架空自治体が支援策',
        link: 'https://news.example.com/fixture/jp_news_04',
        source_name: '架空地域ニュース',
        published_at: '2026-08-22T12:00:00Z',
        raw_date: '08/22/2026, 09:00 PM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: '介護報酬改定の議論始まる 人材確保が焦点',
        link: 'https://news.example.com/fixture/jp_news_05',
        source_name: '架空政策ウォッチ',
        published_at: '2026-08-18T21:36:00Z',
        raw_date: '08/19/2026, 06:36 AM, +0900 +09',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 6,
        title: '介護現場の離職率、賃上げでも改善せず',
        link: 'https://news.example.com/fixture/jp_news_06',
        source_name: '架空福祉新聞',
        published_at: '2026-08-14T14:24:00Z',
        raw_date: '08/14/2026, 11:24 PM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'ケアマネジャー不足で相談待ちが常態化',
        link: 'https://news.example.com/fixture/jp_news_07',
        source_name: '架空医療介護ジャーナル',
        published_at: '2026-08-09T07:12:00Z',
        raw_date: '08/09/2026, 04:12 PM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 8,
        title: '介護ロボット導入で夜勤負担を軽減 架空施設の取り組み',
        link: 'https://news.example.com/fixture/jp_news_08',
        source_name: '架空テクノロジーレビュー',
        published_at: '2026-08-03T16:48:00Z',
        raw_date: '08/04/2026, 01:48 AM, +0900 +09',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 9,
        title: '地方の介護施設、募集しても応募ゼロが半数',
        link: 'https://news.example.com/fixture/jp_news_09',
        source_name: '架空地域ニュース',
        published_at: '2026-07-30T09:36:00Z',
        raw_date: '07/30/2026, 06:36 PM, +0900 +09',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
  ],
  maps_results: [
    {
      position: 1,
      title: '架空あおぞら介護サービス 中央事業所',
      place_id: 'FIXTURE_PLACE_ID_JP_PLACE_01',
      rating: 4.3,
      reviews: 48,
      place_type: '訪問介護事業所',
      address: '架空県架空市中央1-2-3 架空ビル2F',
      link: null,
    },
    {
      position: 2,
      title: '架空ひまわり在宅介護ステーション',
      place_id: 'FIXTURE_PLACE_ID_JP_PLACE_02',
      rating: 4.1,
      reviews: 27,
      place_type: '訪問介護事業所',
      address: '架空県架空市北町4-5-6',
      link: null,
    },
    {
      position: 3,
      title: '架空こもれびデイサービスセンター',
      place_id: 'FIXTURE_PLACE_ID_JP_PLACE_03',
      rating: 4.5,
      reviews: 63,
      place_type: '通所介護事業所',
      address: '架空県架空市南町7-8-9',
      link: null,
    },
    {
      position: 4,
      title: '架空みどりの丘 介護老人福祉施設',
      place_id: 'FIXTURE_PLACE_ID_JP_PLACE_04',
      rating: 3.8,
      reviews: 34,
      place_type: '特別養護老人ホーム',
      address: '架空県架空市緑が丘10-11',
      link: null,
    },
    {
      position: 5,
      title: '架空さくら訪問看護・介護ステーション',
      place_id: 'FIXTURE_PLACE_ID_JP_PLACE_05',
      rating: 4.0,
      reviews: 19,
      place_type: '訪問看護ステーション',
      address: '架空県架空市西町12-13',
      link: null,
    },
    {
      position: 6,
      title: '架空やすらぎ小規模多機能ホーム',
      place_id: 'FIXTURE_PLACE_ID_JP_PLACE_06',
      rating: 4.2,
      reviews: 22,
      place_type: '小規模多機能型居宅介護',
      address: '架空県架空市東町14-15',
      link: null,
    },
  ],
  versions: {
    query_profile_version: 'elder-care-jp-v2',
    score_version: 'gapatlas-score-v1',
    classifier_version: 'gapatlas-classifier-v1-stub',
    prompt_version: 'gapatlas-prompt-v1-stub',
  },
  computed_at: '2026-08-28T00:00:00+00:00',
};
