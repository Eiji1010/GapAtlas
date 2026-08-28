/**
 * `IN` のモック詳細。
 *
 * `backend/tests/fixtures/` を fixture モードで通した実際の
 * `GET /api/v1/scans/{scan_id}/countries/{country}` のレスポンスを写したもの。
 * **手で値を変えないこと。** 変えると fixture と矛盾する。
 */

import type { CountryDetail } from '../../api/types';

export const IN_DETAIL: CountryDetail = {
  scan_id: 'scan_demo_001',
  topic_id: 'elder_care',
  country: 'IN',
  status: 'completed',
  need_gap_score: 66,
  confidence: 92,
  components: {
    demand: 68,
    pain: 59,
    solution_gap: 74,
    news_urgency: 60,
  },
  confidence_breakdown: {
    data_completeness: 100,
    sample_sufficiency: 100,
    localization_quality: 70,
    source_agreement: 88,
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
      summary: '直近4週の検索需要が前8週比で 25.2% 上昇した',
      url: null,
    },
    {
      id: 'E2',
      source: 'related_queries',
      summary: '急上昇クエリ 12 件のうち、不足・待機・到達困難に分類されたものが 7 件',
      url: 'https://trends.google.com/trends/explore?q=geriatric%20care%20in%20tier%202%20cities&date=today+12-m&geo=IN',
    },
    {
      id: 'E3',
      source: 'search',
      summary: '検索結果 上位10件のうち、直接申し込める提供者・仲介は 4 件',
      url: 'https://guide.example.co.in/elder-care-services/',
    },
    {
      id: 'E4',
      source: 'news',
      summary: '報道 8 件のうち、この課題そのものを扱った記事が 6 件',
      url: 'https://news.example.com/fixture/in_news_01',
    },
  ],
  trends: {
    series: [
      {
        query: 'elder care',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 80.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 97.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 71.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 97.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 84.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 80.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 84.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 76.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 100.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 91.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 90.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 96.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 85.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 83.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 83.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 76.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 81.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 81.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 71.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 78.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 81.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 71.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 87.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 74.0,
          },
        ],
      },
      {
        query: 'old age home',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 27.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 26.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 25.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 28.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 22.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 27.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 26.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 27.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 22.0,
          },
        ],
      },
      {
        query: 'home nursing',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 17.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 13.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 13.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 10.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 10.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 13.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 9.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 10.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 8.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 12.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 8.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 17.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 8.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 15.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 0.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 11.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 0.0,
          },
        ],
      },
    ],
  },
  related_queries: [
    {
      item: {
        query: 'geriatric care in tier 2 cities',
        growth_percent: 340.0,
        is_breakout: false,
        raw_value: '+340%',
        link: 'https://trends.google.com/trends/explore?q=geriatric%20care%20in%20tier%202%20cities&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.7,
      },
    },
    {
      item: {
        query: 'no elder care service in my city',
        growth_percent: 5000.0,
        is_breakout: false,
        raw_value: 'Breakout',
        link: 'https://trends.google.com/trends/explore?q=no%20elder%20care%20service%20in%20my%20city&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.7,
      },
    },
    {
      item: {
        query: 'attendant for elderly at home',
        growth_percent: 280.0,
        is_breakout: false,
        raw_value: '+280%',
        link: 'https://trends.google.com/trends/explore?q=attendant%20for%20elderly%20at%20home&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'NEUTRAL',
        confidence: 0.4,
      },
    },
    {
      item: {
        query: 'elder care for parents living alone',
        growth_percent: 260.0,
        is_breakout: false,
        raw_value: '+260%',
        link: 'https://trends.google.com/trends/explore?q=elder%20care%20for%20parents%20living%20alone&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.7,
      },
    },
    {
      item: {
        query: 'affordable old age home',
        growth_percent: 230.0,
        is_breakout: false,
        raw_value: '+230%',
        link: 'https://trends.google.com/trends/explore?q=affordable%20old%20age%20home&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'home nursing charges per day',
        growth_percent: 190.0,
        is_breakout: false,
        raw_value: '+190%',
        link: 'https://trends.google.com/trends/explore?q=home%20nursing%20charges%20per%20day&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'nursing attendant not available',
        growth_percent: 175.0,
        is_breakout: false,
        raw_value: '+175%',
        link: 'https://trends.google.com/trends/explore?q=nursing%20attendant%20not%20available&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'old age home waiting list',
        growth_percent: 150.0,
        is_breakout: false,
        raw_value: '+150%',
        link: 'https://trends.google.com/trends/explore?q=old%20age%20home%20waiting%20list&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'trained caregiver shortage',
        growth_percent: 120.0,
        is_breakout: false,
        raw_value: '+120%',
        link: 'https://trends.google.com/trends/explore?q=trained%20caregiver%20shortage&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'old age home complaints',
        growth_percent: 60.0,
        is_breakout: false,
        raw_value: '+60%',
        link: 'https://trends.google.com/trends/explore?q=old%20age%20home%20complaints&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'QUALITY',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'old age home admission process',
        growth_percent: 55.0,
        is_breakout: false,
        raw_value: '+55%',
        link: 'https://trends.google.com/trends/explore?q=old%20age%20home%20admission%20process&date=today+12-m&geo=IN',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'senior citizen home care services',
        growth_percent: 40.0,
        is_breakout: false,
        raw_value: '+40%',
        link: 'https://trends.google.com/trends/explore?q=senior%20citizen%20home%20care%20services&date=today+12-m&geo=IN',
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
        title: 'Elder care services in India: a complete guide | Example Senior Guide (fictional)',
        link: 'https://guide.example.co.in/elder-care-services/',
        snippet:
          'Fictional guide covering home nursing, day care and assisted living options for families.',
        displayed_link: 'guide.example.co.in › elder-care-services',
        source: 'guide.example.co.in',
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Find elder care and home nursing near you | Example Care Connect (fictional)',
        link: 'https://connect.example.co.in/elder-care/',
        snippet:
          'Fictional platform that matches families with verified attendants and nursing providers.',
        displayed_link: 'connect.example.co.in › elder-care',
        source: 'connect.example.co.in',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title:
          'Types of elder care available for Indian families | Example Care Journal (fictional)',
        link: 'https://journal.example.co.in/types-of-elder-care/',
        snippet:
          'Fictional explainer comparing live-in attendants, day care centres and residential homes.',
        displayed_link: 'journal.example.co.in › types-of-elder-care',
        source: 'journal.example.co.in',
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Home nursing and attendant services | Example Ashirwad Care (fictional)',
        link: 'https://ashirwadcare.example.co.in/',
        snippet:
          'Fictional provider offering trained attendants, nursing visits and physiotherapy at home.',
        displayed_link: 'ashirwadcare.example.co.in',
        source: 'ashirwadcare.example.co.in',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'How much does elder care cost in India? | Example Money Notes (fictional)',
        link: 'https://moneynotes.example.co.in/elder-care-cost/',
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
        title: 'Compare old age homes and assisted living | Example Senior Finder (fictional)',
        link: 'https://finder.example.co.in/old-age-homes/',
        snippet:
          'Fictional comparison site listing monthly charges, room types and admission requirements.',
        displayed_link: 'finder.example.co.in › old-age-homes',
        source: 'finder.example.co.in',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'Elder care services - community discussion thread | Example Forum (fictional)',
        link: 'https://forum.example.co.in/threads/elder-care-services/',
        snippet:
          'Fictional user forum thread where families share experiences of hiring elder care help.',
        displayed_link: 'forum.example.co.in › threads',
        source: 'forum.example.co.in',
      },
      classification: {
        classification: 'OTHER',
        confidence: 0.8,
      },
    },
    {
      item: {
        position: 8,
        title: 'Assisted living and geriatric care centre | Example Sahara Senior Care (fictional)',
        link: 'https://saharasenior.example.co.in/',
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
        position: 9,
        title:
          'Demand for home-based elder care rises in metros | Example Business Report (fictional)',
        link: 'https://news.example.co.in/home-elder-care-demand/',
        snippet:
          'Fictional news article on the growth of paid home care services in large Indian cities.',
        displayed_link: 'news.example.co.in › business',
        source: 'news.example.co.in',
      },
      classification: {
        classification: 'NEWS',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 10,
        title:
          'Government schemes for senior citizens explained | Example Policy Digest (fictional)',
        link: 'https://digest.example.co.in/senior-citizen-schemes/',
        snippet:
          'Fictional summary of pension, health and welfare schemes available to older citizens.',
        displayed_link: 'digest.example.co.in › schemes',
        source: 'digest.example.co.in',
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
        title: 'Demand for home nursing surges as families live apart',
        link: 'https://news.example.com/fixture/in_news_01',
        source_name: 'Example India Business Report (fictional)',
        published_at: '2026-08-27T12:00:00Z',
        raw_date: '08/27/2026, 05:30 PM, +0530 IST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Old age homes in smaller cities report long waiting lists',
        link: 'https://news.example.com/fixture/in_news_02',
        source_name: 'Example Nationwide Daily (fictional)',
        published_at: '2026-08-25T21:36:00Z',
        raw_date: '08/26/2026, 03:06 AM, +0530 IST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Trained geriatric caregivers remain scarce, say operators',
        link: 'https://news.example.com/fixture/in_news_03',
        source_name: 'Example Health Digest (fictional)',
        published_at: '2026-08-23T14:24:00Z',
        raw_date: '08/23/2026, 07:54 PM, +0530 IST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Senior citizens in tier-2 cities struggle to find day care',
        link: 'https://news.example.com/fixture/in_news_04',
        source_name: 'Example Urban Affairs Weekly (fictional)',
        published_at: '2026-08-20T16:48:00Z',
        raw_date: '08/20/2026, 10:18 PM, +0530 IST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'Insurance cover for elder care draws policy attention',
        link: 'https://news.example.com/fixture/in_news_05',
        source_name: 'Example Finance Review (fictional)',
        published_at: '2026-08-16T19:12:00Z',
        raw_date: '08/17/2026, 12:42 AM, +0530 IST',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 6,
        title: 'Families abroad turn to paid caretakers for ageing parents',
        link: 'https://news.example.com/fixture/in_news_06',
        source_name: 'Example Diaspora Report (fictional)',
        published_at: '2026-08-12T04:48:00Z',
        raw_date: '08/12/2026, 10:18 AM, +0530 IST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'Elder abuse complaints rise in institutional care',
        link: 'https://news.example.com/fixture/in_news_07',
        source_name: 'Example Social Affairs Monitor (fictional)',
        published_at: '2026-08-05T09:36:00Z',
        raw_date: '08/05/2026, 03:06 PM, +0530 IST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 8,
        title: 'Startups target the home-based elder care market',
        link: 'https://news.example.com/fixture/in_news_08',
        source_name: 'Example Startup Journal (fictional)',
        published_at: '2026-07-31T04:48:00Z',
        raw_date: '07/31/2026, 10:18 AM, +0530 IST',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
  ],
  maps_results: null,
  versions: {
    query_profile_version: 'elder-care-in-v2',
    score_version: 'gapatlas-score-v1',
    classifier_version: 'gapatlas-classifier-v1-stub',
    prompt_version: 'gapatlas-prompt-v1-stub',
  },
  computed_at: '2026-08-28T00:00:00+00:00',
};
