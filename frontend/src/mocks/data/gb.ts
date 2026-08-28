/**
 * `GB` のモック詳細。
 *
 * `backend/tests/fixtures/` を fixture モードで通した実際の
 * `GET /api/v1/scans/{scan_id}/countries/{country}` のレスポンスを写したもの。
 * **手で値を変えないこと。** 変えると fixture と矛盾する。
 */

import type { CountryDetail } from '../../api/types';

export const GB_DETAIL: CountryDetail = {
  scan_id: 'scan_demo_001',
  topic_id: 'elder_care',
  country: 'GB',
  status: 'completed',
  need_gap_score: 58,
  confidence: 90,
  components: {
    demand: 43,
    pain: 76,
    solution_gap: 63,
    news_urgency: 60,
  },
  confidence_breakdown: {
    data_completeness: 100,
    sample_sufficiency: 100,
    localization_quality: 70,
    source_agreement: 77,
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
      summary: '直近4週の検索需要が前8週比で 4.0% 低下した',
      url: null,
    },
    {
      id: 'E2',
      source: 'related_queries',
      summary: '急上昇クエリ 12 件のうち、不足・待機・到達困難に分類されたものが 8 件',
      url: 'https://trends.google.com/trends/explore?q=hospital%20discharge%20waiting%20for%20care%20package&date=today+12-m&geo=GB',
    },
    {
      id: 'E3',
      source: 'search',
      summary: '検索結果 上位10件のうち、直接申し込める提供者・仲介は 3 件',
      url: 'https://council.example.co.uk/adult-social-care/',
    },
    {
      id: 'E4',
      source: 'news',
      summary: '報道 8 件のうち、この課題そのものを扱った記事が 7 件',
      url: 'https://news.example.com/fixture/gb_news_01',
    },
  ],
  trends: {
    series: [
      {
        query: 'elderly care',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 90.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 92.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 97.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 95.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 100.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 96.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 100.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 98.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 96.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 94.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 96.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 89.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 87.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 93.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 86.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 86.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 85.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 81.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 83.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 83.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 78.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 76.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 79.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 80.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 70.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 67.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 65.0,
          },
        ],
      },
      {
        query: 'care home',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 78.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 84.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 81.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 83.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 79.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 85.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 82.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 85.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 84.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 79.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 80.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 77.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 76.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 76.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 70.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 64.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 64.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 60.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 64.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 60.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 60.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 53.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 53.0,
          },
        ],
      },
      {
        query: 'home care',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 45.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 46.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 44.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 45.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 48.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 46.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 45.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 44.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 44.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 41.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 29.0,
          },
        ],
      },
    ],
  },
  related_queries: [
    {
      item: {
        query: 'hospital discharge waiting for care package',
        growth_percent: 310.0,
        is_breakout: false,
        raw_value: '+310%',
        link: 'https://trends.google.com/trends/explore?q=hospital%20discharge%20waiting%20for%20care%20package&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'no carers available in my area',
        growth_percent: 5000.0,
        is_breakout: false,
        raw_value: 'Breakout',
        link: 'https://trends.google.com/trends/explore?q=no%20carers%20available%20in%20my%20area&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'carer shortage',
        growth_percent: 280.0,
        is_breakout: false,
        raw_value: '+280%',
        link: 'https://trends.google.com/trends/explore?q=carer%20shortage&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'domiciliary care unavailable',
        growth_percent: 230.0,
        is_breakout: false,
        raw_value: '+230%',
        link: 'https://trends.google.com/trends/explore?q=domiciliary%20care%20unavailable&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'care home waiting list',
        growth_percent: 200.0,
        is_breakout: false,
        raw_value: '+200%',
        link: 'https://trends.google.com/trends/explore?q=care%20home%20waiting%20list&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'care needs assessment delay',
        growth_percent: 175.0,
        is_breakout: false,
        raw_value: '+175%',
        link: 'https://trends.google.com/trends/explore?q=care%20needs%20assessment%20delay&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'respite care not available',
        growth_percent: 140.0,
        is_breakout: false,
        raw_value: '+140%',
        link: 'https://trends.google.com/trends/explore?q=respite%20care%20not%20available&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'care home fees per week',
        growth_percent: 120.0,
        is_breakout: false,
        raw_value: '+120%',
        link: 'https://trends.google.com/trends/explore?q=care%20home%20fees%20per%20week&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'self funding care home advice',
        growth_percent: 90.0,
        is_breakout: false,
        raw_value: '+90%',
        link: 'https://trends.google.com/trends/explore?q=self%20funding%20care%20home%20advice&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'rural care home access',
        growth_percent: 65.0,
        is_breakout: false,
        raw_value: '+65%',
        link: 'https://trends.google.com/trends/explore?q=rural%20care%20home%20access&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'care home poor inspection rating',
        growth_percent: 55.0,
        is_breakout: false,
        raw_value: '+55%',
        link: 'https://trends.google.com/trends/explore?q=care%20home%20poor%20inspection%20rating&date=today+12-m&geo=GB',
      },
      classification: {
        classification: 'QUALITY',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'what is social care',
        growth_percent: 30.0,
        is_breakout: false,
        raw_value: '+30%',
        link: 'https://trends.google.com/trends/explore?q=what%20is%20social%20care&date=today+12-m&geo=GB',
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
        title: 'Adult social care and support | Example Borough Council (fictional)',
        link: 'https://council.example.co.uk/adult-social-care/',
        snippet:
          'Fictional council page describing home care, day services and how to arrange support.',
        displayed_link: 'council.example.co.uk › adult-social-care',
        source: 'council.example.co.uk',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Getting a care needs assessment | Example Public Care Service (fictional)',
        link: 'https://care-service.example.co.uk/assessment/',
        snippet:
          'Fictional public service guidance on requesting an assessment and what happens afterwards.',
        displayed_link: 'care-service.example.co.uk › assessment',
        source: 'care-service.example.co.uk',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Types of elderly care explained | Example Care Advice (fictional)',
        link: 'https://advice.example.co.uk/elderly-care-types/',
        snippet:
          'Fictional advice article comparing residential care, home care and live-in care options.',
        displayed_link: 'advice.example.co.uk › elderly-care-types',
        source: 'advice.example.co.uk',
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Search care homes and home care near you | Example Care Directory (fictional)',
        link: 'https://directory.example.co.uk/search/',
        snippet:
          'Fictional directory listing providers with vacancies, weekly fees and inspection summaries.',
        displayed_link: 'directory.example.co.uk › search',
        source: 'directory.example.co.uk',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'Paying for care: what your council covers | Example Borough Council (fictional)',
        link: 'https://council.example.co.uk/paying-for-care/',
        snippet:
          'Fictional council page on means testing, capital limits and self-funded care arrangements.',
        displayed_link: 'council.example.co.uk › paying-for-care',
        source: 'council.example.co.uk',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 6,
        title: 'Home care visits across the county | Example Willow Home Care (fictional)',
        link: 'https://willowcare.example.co.uk/',
        snippet:
          'Fictional domiciliary care agency providing personal care visits and overnight support.',
        displayed_link: 'willowcare.example.co.uk',
        source: 'willowcare.example.co.uk',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'Care home fees guide 2026 | Example Money Advice (fictional)',
        link: 'https://money-advice.example.co.uk/care-home-fees/',
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
        position: 8,
        title: 'Care quality inspection reports | Example Care Regulator (fictional)',
        link: 'https://inspections.example.co.uk/reports/',
        snippet:
          'Fictional regulator page publishing inspection ratings and enforcement notices for providers.',
        displayed_link: 'inspections.example.co.uk › reports',
        source: 'inspections.example.co.uk',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 9,
        title: 'Residential and respite care | Example Meadow Care Homes (fictional)',
        link: 'https://meadowcare.example.co.uk/',
        snippet: null,
        displayed_link: null,
        source: null,
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 10,
        title:
          'Councils warn of rising social care waiting lists | Example Daily Report (fictional)',
        link: 'https://news.example.co.uk/social-care-waiting-lists/',
        snippet:
          'Fictional news article reporting on assessment backlogs and unfilled care packages.',
        displayed_link: 'news.example.co.uk › social-care',
        source: 'news.example.co.uk',
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
        title: 'Care providers hand back contracts as staff shortages bite',
        link: 'https://news.example.com/fixture/gb_news_01',
        source_name: 'Example Daily Report (fictional)',
        published_at: '2026-08-27T07:12:00Z',
        raw_date: '08/27/2026, 08:12 AM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Thousands wait for care packages after hospital discharge',
        link: 'https://news.example.com/fixture/gb_news_02',
        source_name: 'Example Health Monitor (fictional)',
        published_at: '2026-08-25T16:48:00Z',
        raw_date: '08/25/2026, 05:48 PM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Council social care budgets face record overspend',
        link: 'https://news.example.com/fixture/gb_news_03',
        source_name: 'Example Local Government News (fictional)',
        published_at: '2026-08-23T09:36:00Z',
        raw_date: '08/23/2026, 10:36 AM, +0100 BST',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 4,
        title: 'Home care visits cut short as rotas go unfilled',
        link: 'https://news.example.com/fixture/gb_news_04',
        source_name: 'Example Care Weekly (fictional)',
        published_at: '2026-08-19T19:12:00Z',
        raw_date: '08/19/2026, 08:12 PM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'Unpaid carers say they cannot get respite breaks',
        link: 'https://news.example.com/fixture/gb_news_05',
        source_name: 'Example Community Voice (fictional)',
        published_at: '2026-08-15T02:24:00Z',
        raw_date: '08/15/2026, 03:24 AM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 6,
        title: 'Care home closures leave rural areas without beds',
        link: 'https://news.example.com/fixture/gb_news_06',
        source_name: 'Example Daily Report (fictional)',
        published_at: '2026-08-10T12:00:00Z',
        raw_date: '08/10/2026, 01:00 PM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 7,
        title: 'Ministers urged to publish long-term social care plan',
        link: 'https://news.example.com/fixture/gb_news_07',
        source_name: 'Example Policy Review (fictional)',
        published_at: '2026-08-04T21:36:00Z',
        raw_date: '08/04/2026, 10:36 PM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 8,
        title: 'Recruitment drive fails to fill care vacancies',
        link: 'https://news.example.com/fixture/gb_news_08',
        source_name: 'Example Care Weekly (fictional)',
        published_at: '2026-07-30T02:24:00Z',
        raw_date: '07/30/2026, 03:24 AM, +0100 BST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
  ],
  maps_results: null,
  versions: {
    query_profile_version: 'elder-care-gb-v2',
    score_version: 'gapatlas-score-v1',
    classifier_version: 'gapatlas-classifier-v1-stub',
    prompt_version: 'gapatlas-prompt-v1-stub',
  },
  computed_at: '2026-08-28T00:00:00+00:00',
};
