/**
 * `US` のモック詳細。
 *
 * `backend/tests/fixtures/` を fixture モードで通した実際の
 * `GET /api/v1/scans/{scan_id}/countries/{country}` のレスポンスを写したもの。
 * **手で値を変えないこと。** 変えると fixture と矛盾する。
 */

import type { CountryDetail } from '../../api/types';

export const US_DETAIL: CountryDetail = {
  scan_id: 'scan_demo_001',
  topic_id: 'elder_care',
  country: 'US',
  status: 'completed',
  need_gap_score: 55,
  confidence: 90,
  components: {
    demand: 54,
    pain: 70,
    solution_gap: 40,
    news_urgency: 60,
  },
  confidence_breakdown: {
    data_completeness: 100,
    sample_sufficiency: 100,
    localization_quality: 70,
    source_agreement: 78,
    freshness: 96,
  },
  source_status: {
    trends: 'ok',
    related_queries: 'ok',
    search: 'ok',
    news: 'ok',
    maps: 'not_requested',
  },
  evidence: [
    {
      id: 'E1',
      source: 'trends',
      summary: '直近4週の検索需要が前8週比で 0.7% 上昇した',
      url: null,
    },
    {
      id: 'E2',
      source: 'related_queries',
      summary: '急上昇クエリ 12 件のうち、不足・待機・到達困難に分類されたものが 8 件',
      url: 'https://trends.google.com/trends/explore?q=home%20health%20aide%20shortage&date=today+12-m&geo=US',
    },
    {
      id: 'E3',
      source: 'search',
      summary: '検索結果 上位10件のうち、直接申し込める提供者・仲介は 7 件',
      url: 'https://finder.example.com/elder-care/',
    },
    {
      id: 'E4',
      source: 'news',
      summary: '報道 8 件のうち、この課題そのものを扱った記事が 6 件',
      url: 'https://news.example.com/fixture/us_news_01',
    },
  ],
  trends: {
    series: [
      {
        query: 'elder care',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 90.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 99.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 100.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 98.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 99.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 97.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 98.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 100.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 100.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 98.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 92.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 96.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 90.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 87.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 85.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 92.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 87.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 86.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 92.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 92.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 87.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 91.0,
          },
        ],
      },
      {
        query: 'nursing home',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 79.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 70.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 71.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 71.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 70.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 71.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 70.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 70.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 70.0,
          },
        ],
      },
      {
        query: 'home care for seniors',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 38.0,
          },
        ],
      },
    ],
  },
  related_queries: [
    {
      item: {
        query: 'home health aide shortage',
        growth_percent: 310.0,
        is_breakout: false,
        raw_value: '+310%',
        link: 'https://trends.google.com/trends/explore?q=home%20health%20aide%20shortage&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: "can't find a caregiver",
        growth_percent: 5000.0,
        is_breakout: false,
        raw_value: 'Breakout',
        link: 'https://trends.google.com/trends/explore?q=can%27t%20find%20a%20caregiver&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'nursing home waitlist',
        growth_percent: 240.0,
        is_breakout: false,
        raw_value: '+240%',
        link: 'https://trends.google.com/trends/explore?q=nursing%20home%20waitlist&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'nursing home understaffed',
        growth_percent: 220.0,
        is_breakout: false,
        raw_value: '+220%',
        link: 'https://trends.google.com/trends/explore?q=nursing%20home%20understaffed&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'medicaid waiver waiting list',
        growth_percent: 180.0,
        is_breakout: false,
        raw_value: '+180%',
        link: 'https://trends.google.com/trends/explore?q=medicaid%20waiver%20waiting%20list&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'no home care availability',
        growth_percent: 160.0,
        is_breakout: false,
        raw_value: '+160%',
        link: 'https://trends.google.com/trends/explore?q=no%20home%20care%20availability&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'caregiver burnout symptoms',
        growth_percent: 150.0,
        is_breakout: false,
        raw_value: '+150%',
        link: 'https://trends.google.com/trends/explore?q=caregiver%20burnout%20symptoms&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'assisted living cost per month',
        growth_percent: 130.0,
        is_breakout: false,
        raw_value: '+130%',
        link: 'https://trends.google.com/trends/explore?q=assisted%20living%20cost%20per%20month&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'elder care in rural counties',
        growth_percent: 95.0,
        is_breakout: false,
        raw_value: '+95%',
        link: 'https://trends.google.com/trends/explore?q=elder%20care%20in%20rural%20counties&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.7,
      },
    },
    {
      item: {
        query: 'paying for long term care',
        growth_percent: 85.0,
        is_breakout: false,
        raw_value: '+85%',
        link: 'https://trends.google.com/trends/explore?q=paying%20for%20long%20term%20care&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'nursing home neglect warning signs',
        growth_percent: 70.0,
        is_breakout: false,
        raw_value: '+70%',
        link: 'https://trends.google.com/trends/explore?q=nursing%20home%20neglect%20warning%20signs&date=today+12-m&geo=US',
      },
      classification: {
        classification: 'QUALITY',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'what is assisted living',
        growth_percent: 35.0,
        is_breakout: false,
        raw_value: '+35%',
        link: 'https://trends.google.com/trends/explore?q=what%20is%20assisted%20living&date=today+12-m&geo=US',
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
        title: 'Find Elder Care Services Near You | Example Care Finder (fictional)',
        link: 'https://finder.example.com/elder-care/',
        snippet:
          'Fictional directory. Search in-home care, adult day programs and assisted living by ZIP code.',
        displayed_link: 'finder.example.com › elder-care',
        source: 'finder.example.com',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'In-Home Elder Care Services | Example Home Care Group (fictional)',
        link: 'https://homecare.example.com/services/',
        snippet:
          'Fictional agency providing personal care, companion care and 24-hour live-in support.',
        displayed_link: 'homecare.example.com › services',
        source: 'homecare.example.com',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Assisted Living and Memory Care | Example Senior Living (fictional)',
        link: 'https://seniorliving.example.com/',
        snippet:
          'Fictional operator of assisted living communities with on-site nursing and memory care.',
        displayed_link: 'seniorliving.example.com',
        source: 'seniorliving.example.com',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Local Aging Services and Benefits | Example County Aging Office (fictional)',
        link: 'https://agingservices.example.org/',
        snippet:
          'Fictional public agency page listing meal programs, transport and caregiver support benefits.',
        displayed_link: 'agingservices.example.org',
        source: 'agingservices.example.org',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'Compare Home Care Agencies by ZIP | Example Care Marketplace (fictional)',
        link: 'https://marketplace.example.com/home-care/',
        snippet:
          'Fictional marketplace comparing hourly rates, availability and services of local agencies.',
        displayed_link: 'marketplace.example.com › home-care',
        source: 'marketplace.example.com',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 6,
        title: 'What Elder Care Services Cost in 2026 | Example Senior Guide (fictional)',
        link: 'https://guide.example.org/elder-care-costs/',
        snippet:
          'Fictional editorial guide explaining typical hourly and monthly costs by type of care.',
        displayed_link: 'guide.example.org › elder-care-costs',
        source: 'guide.example.org',
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'Adult Day Health Program | Example Community Care (fictional)',
        link: 'https://communitycare.example.com/adult-day/',
        snippet: null,
        displayed_link: null,
        source: null,
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.6,
      },
    },
    {
      item: {
        position: 8,
        title: 'Browse Verified Caregivers | Example Caregiver Match (fictional)',
        link: 'https://match.example.com/caregivers/',
        snippet:
          'Fictional platform where families book background-checked caregivers by the hour.',
        displayed_link: 'match.example.com › caregivers',
        source: 'match.example.com',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 9,
        title: 'Skilled Nursing and Respite Care | Example Valley Care Services (fictional)',
        link: 'https://valleycare.example.com/',
        snippet:
          'Fictional provider offering skilled nursing visits, respite stays and post-hospital care.',
        displayed_link: 'valleycare.example.com',
        source: 'valleycare.example.com',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 10,
        title: 'Elder Care Checklist for Families | Example Family Guide (fictional)',
        link: 'https://familyguide.example.org/elder-care-checklist/',
        snippet: null,
        displayed_link: null,
        source: null,
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
  ],
  news_results: [
    {
      item: {
        position: 1,
        title: 'Home care agencies turn away clients as aide shortage deepens',
        link: 'https://news.example.com/fixture/us_news_01',
        source_name: 'Example Health Wire (fictional)',
        published_at: '2026-08-27T14:24:00Z',
        raw_date: '08/27/2026, 10:24 AM, -0400 EDT',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Nursing homes in rural counties cut beds amid staffing gaps',
        link: 'https://news.example.com/fixture/us_news_02',
        source_name: 'Example National Report (fictional)',
        published_at: '2026-08-26T12:00:00Z',
        raw_date: '08/26/2026, 08:00 AM, -0400 EDT',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Wages rise but elder care vacancies stay near record highs',
        link: 'https://news.example.com/fixture/us_news_03',
        source_name: 'Example Business Daily (fictional)',
        published_at: '2026-08-24T02:24:00Z',
        raw_date: '08/23/2026, 10:24 PM, -0400 EDT',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Families wait months for in-home aides, survey finds',
        link: 'https://news.example.com/fixture/us_news_04',
        source_name: 'Example Policy Review (fictional)',
        published_at: '2026-08-21T19:12:00Z',
        raw_date: '08/21/2026, 03:12 PM, -0400 EDT',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'State lawmakers weigh training grants for caregivers',
        link: 'https://news.example.com/fixture/us_news_05',
        source_name: 'Example Statehouse News (fictional)',
        published_at: '2026-08-17T04:48:00Z',
        raw_date: '08/17/2026, 12:48 AM, -0400 EDT',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 6,
        title: 'Assisted living operators say hiring is their top business risk',
        link: 'https://news.example.com/fixture/us_news_06',
        source_name: 'Example Care Business Journal (fictional)',
        published_at: '2026-08-12T21:36:00Z',
        raw_date: '08/12/2026, 05:36 PM, -0400 EDT',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'Immigration rules reshape the elder care workforce debate',
        link: 'https://news.example.com/fixture/us_news_07',
        source_name: 'Example National Report (fictional)',
        published_at: '2026-08-07T14:24:00Z',
        raw_date: '08/07/2026, 10:24 AM, -0400 EDT',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 8,
        title: 'Adult day centers reopen slowly as staff shortages persist',
        link: 'https://news.example.com/fixture/us_news_08',
        source_name: 'Example Health Wire (fictional)',
        published_at: '2026-08-01T07:12:00Z',
        raw_date: '08/01/2026, 03:12 AM, -0400 EDT',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
  ],
  maps_results: null,
  versions: {
    query_profile_version: 'elder-care-us-v2',
    score_version: 'gapatlas-score-v1',
    classifier_version: 'gapatlas-classifier-v1-stub',
    prompt_version: 'gapatlas-prompt-v1-stub',
  },
  computed_at: '2026-08-28T00:00:00+00:00',
};
