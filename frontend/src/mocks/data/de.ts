/**
 * `DE` のモック詳細。
 *
 * `backend/tests/fixtures/` を fixture モードで通した実際の
 * `GET /api/v1/scans/{scan_id}/countries/{country}` のレスポンスを写したもの。
 * **手で値を変えないこと。** 変えると fixture と矛盾する。
 */

import type { CountryDetail } from '../../api/types';

export const DE_DETAIL: CountryDetail = {
  scan_id: 'scan_demo_001',
  topic_id: 'elder_care',
  country: 'DE',
  status: 'completed',
  need_gap_score: 67,
  confidence: 90,
  components: {
    demand: 78,
    pain: 72,
    solution_gap: 47,
    news_urgency: 61,
  },
  confidence_breakdown: {
    data_completeness: 100,
    sample_sufficiency: 100,
    localization_quality: 70,
    source_agreement: 77,
    freshness: 95,
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
      summary: '直近4週の検索需要が前8週比で 24.6% 上昇した',
      url: null,
    },
    {
      id: 'E2',
      source: 'related_queries',
      summary: '急上昇クエリ 12 件のうち、不足・待機・到達困難に分類されたものが 8 件',
      url: 'https://trends.google.com/trends/explore?q=kein%20Pflegeheimplatz%20frei&date=today+12-m&geo=DE',
    },
    {
      id: 'E3',
      source: 'search',
      summary: '検索結果 上位10件のうち、直接申し込める提供者・仲介は 5 件',
      url: 'https://morgenstern-pflege.example.de/',
    },
    {
      id: 'E4',
      source: 'news',
      summary: '報道 8 件のうち、この課題そのものを扱った記事が 7 件',
      url: 'https://news.example.com/fixture/de_news_01',
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
        query: 'Pflege',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 52.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 50.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 60.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 60.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 64.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 63.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 52.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 43.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 54.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 44.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 59.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 61.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 62.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 46.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 51.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 55.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 57.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 51.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 65.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 58.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 56.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 68.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 66.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 73.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 72.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 74.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 69.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 75.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 88.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 100.0,
          },
        ],
      },
      {
        query: 'Pflegeheim',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 27.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2025-10-12T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2025-10-19T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2025-10-26T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 27.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 33.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 30.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 40.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 39.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 32.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 35.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 38.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 31.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 36.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 34.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 37.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 42.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 49.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 47.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 50.0,
          },
          {
            timestamp: '2026-08-23T00:00:00Z',
            value: 50.0,
          },
        ],
      },
      {
        query: 'häusliche Pflege',
        points: [
          {
            timestamp: '2025-08-31T00:00:00Z',
            value: 15.0,
          },
          {
            timestamp: '2025-09-07T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-09-14T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2025-09-21T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2025-09-28T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-10-05T00:00:00Z',
            value: 21.0,
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
            value: 16.0,
          },
          {
            timestamp: '2025-11-02T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-11-09T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-11-16T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2025-11-23T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2025-11-30T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2025-12-07T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2025-12-14T00:00:00Z',
            value: 17.0,
          },
          {
            timestamp: '2025-12-21T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2025-12-28T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-01-04T00:00:00Z',
            value: 17.0,
          },
          {
            timestamp: '2026-01-11T00:00:00Z',
            value: 15.0,
          },
          {
            timestamp: '2026-01-18T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-01-25T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-02-01T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-02-08T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-02-15T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-02-22T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-03-01T00:00:00Z',
            value: 18.0,
          },
          {
            timestamp: '2026-03-08T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-03-15T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-03-22T00:00:00Z',
            value: 22.0,
          },
          {
            timestamp: '2026-03-29T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-04-05T00:00:00Z',
            value: 17.0,
          },
          {
            timestamp: '2026-04-12T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-04-19T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-04-26T00:00:00Z',
            value: 15.0,
          },
          {
            timestamp: '2026-05-03T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-05-10T00:00:00Z',
            value: 19.0,
          },
          {
            timestamp: '2026-05-17T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-05-24T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-05-31T00:00:00Z',
            value: 16.0,
          },
          {
            timestamp: '2026-06-07T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-06-14T00:00:00Z',
            value: 22.0,
          },
          {
            timestamp: '2026-06-21T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-06-28T00:00:00Z',
            value: 20.0,
          },
          {
            timestamp: '2026-07-05T00:00:00Z',
            value: 22.0,
          },
          {
            timestamp: '2026-07-12T00:00:00Z',
            value: 24.0,
          },
          {
            timestamp: '2026-07-19T00:00:00Z',
            value: 21.0,
          },
          {
            timestamp: '2026-07-26T00:00:00Z',
            value: 28.0,
          },
          {
            timestamp: '2026-08-02T00:00:00Z',
            value: 29.0,
          },
          {
            timestamp: '2026-08-09T00:00:00Z',
            value: 23.0,
          },
          {
            timestamp: '2026-08-16T00:00:00Z',
            value: 30.0,
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
        query: 'kein Pflegeheimplatz frei',
        growth_percent: 5000.0,
        is_breakout: false,
        raw_value: 'Breakout',
        link: 'https://trends.google.com/trends/explore?q=kein%20Pflegeheimplatz%20frei&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflegekräftemangel',
        growth_percent: 260.0,
        is_breakout: false,
        raw_value: '+260%',
        link: 'https://trends.google.com/trends/explore?q=Pflegekr%C3%A4ftemangel&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Kurzzeitpflege kein Platz',
        growth_percent: 240.0,
        is_breakout: false,
        raw_value: '+240%',
        link: 'https://trends.google.com/trends/explore?q=Kurzzeitpflege%20kein%20Platz&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflegeplatz gesucht dringend',
        growth_percent: 225.0,
        is_breakout: false,
        raw_value: '+225%',
        link: 'https://trends.google.com/trends/explore?q=Pflegeplatz%20gesucht%20dringend&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'SHORTAGE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'ambulanter Pflegedienst nimmt keine neuen Patienten auf',
        growth_percent: 205.0,
        is_breakout: false,
        raw_value: '+205%',
        link: 'https://trends.google.com/trends/explore?q=ambulanter%20Pflegedienst%20nimmt%20keine%20neuen%20Patienten%20auf&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflegeplatz Wartezeit',
        growth_percent: 190.0,
        is_breakout: false,
        raw_value: '+190%',
        link: 'https://trends.google.com/trends/explore?q=Pflegeplatz%20Wartezeit&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'WAIT_TIME',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflegekosten steigen',
        growth_percent: 165.0,
        is_breakout: false,
        raw_value: '+165%',
        link: 'https://trends.google.com/trends/explore?q=Pflegekosten%20steigen&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflegeheim Eigenanteil zu hoch',
        growth_percent: 150.0,
        is_breakout: false,
        raw_value: '+150%',
        link: 'https://trends.google.com/trends/explore?q=Pflegeheim%20Eigenanteil%20zu%20hoch&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'COST',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'pflegende Angehörige überlastet',
        growth_percent: 130.0,
        is_breakout: false,
        raw_value: '+130%',
        link: 'https://trends.google.com/trends/explore?q=pflegende%20Angeh%C3%B6rige%20%C3%BCberlastet&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'WORKFORCE',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflege auf dem Land',
        growth_percent: 70.0,
        is_breakout: false,
        raw_value: '+70%',
        link: 'https://trends.google.com/trends/explore?q=Pflege%20auf%20dem%20Land&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'ACCESS',
        confidence: 0.7,
      },
    },
    {
      item: {
        query: 'Pflegeheim schlechte Bewertung',
        growth_percent: 50.0,
        is_breakout: false,
        raw_value: '+50%',
        link: 'https://trends.google.com/trends/explore?q=Pflegeheim%20schlechte%20Bewertung&date=today+12-m&geo=DE',
      },
      classification: {
        classification: 'QUALITY',
        confidence: 0.9,
      },
    },
    {
      item: {
        query: 'Pflegegrad beantragen',
        growth_percent: 45.0,
        is_breakout: false,
        raw_value: '+45%',
        link: 'https://trends.google.com/trends/explore?q=Pflegegrad%20beantragen&date=today+12-m&geo=DE',
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
        title: 'Ambulanter Pflegedienst in Ihrer Nähe | Beispiel Pflegedienst Morgenstern (fiktiv)',
        link: 'https://morgenstern-pflege.example.de/',
        snippet:
          'Fiktiver ambulanter Pflegedienst mit Grundpflege, Behandlungspflege und Verhinderungspflege.',
        displayed_link: 'morgenstern-pflege.example.de',
        source: 'morgenstern-pflege.example.de',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Pflegedienste vergleichen und finden | Beispiel Pflegeportal (fiktiv)',
        link: 'https://portal.example.de/pflegedienst-suche/',
        snippet:
          'Fiktives Portal zum Vergleich von Pflegediensten nach Postleitzahl, Leistungen und Kapazität.',
        displayed_link: 'portal.example.de › pflegedienst-suche',
        source: 'portal.example.de',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Was macht ein ambulanter Pflegedienst? | Beispiel Pflegeratgeber (fiktiv)',
        link: 'https://ratgeber.example.de/ambulante-pflege/',
        snippet:
          'Fiktiver Ratgeberartikel über Leistungen, Abrechnung und Auswahl eines Pflegedienstes.',
        displayed_link: 'ratgeber.example.de › ambulante-pflege',
        source: 'ratgeber.example.de',
      },
      classification: {
        classification: 'INFORMATION',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Pflegeleistungen beantragen | Beispiel Sozialamt (fiktiv)',
        link: 'https://sozialamt.example.de/pflegeleistungen/',
        snippet: 'Fiktive Behördenseite mit Antragswegen, Fristen und Beratungsstellen vor Ort.',
        displayed_link: 'sozialamt.example.de › pflegeleistungen',
        source: 'sozialamt.example.de',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title:
          '24-Stunden-Betreuung und häusliche Pflege | Beispiel Pflegedienst Lindenhof (fiktiv)',
        link: 'https://lindenhof-pflege.example.de/',
        snippet:
          'Fiktiver Pflegedienst mit Betreuung rund um die Uhr, Nachtpflege und Angehörigenberatung.',
        displayed_link: 'lindenhof-pflege.example.de',
        source: 'lindenhof-pflege.example.de',
      },
      classification: {
        classification: 'DIRECT_PROVIDER',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 6,
        title: 'Pflegedienst Kosten und Abrechnung erklärt | Beispiel Pflegewissen (fiktiv)',
        link: 'https://pflegewissen.example.de/kosten-abrechnung/',
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
        position: 7,
        title:
          'Freie Pflegeplätze und Pflegedienste in der Region | Beispiel Pflegefinder (fiktiv)',
        link: 'https://finder.example.de/freie-plaetze/',
        snippet:
          'Fiktive Suchplattform, die gemeldete freie Kapazitäten von Diensten und Heimen anzeigt.',
        displayed_link: 'finder.example.de › freie-plaetze',
        source: 'finder.example.de',
      },
      classification: {
        classification: 'MARKETPLACE',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 8,
        title: 'Pflegestützpunkt: Beratung vor Ort | Beispiel Landkreis (fiktiv)',
        link: 'https://landkreis.example.de/pflegestuetzpunkt/',
        snippet:
          'Fiktive Seite eines Landkreises mit Beratungsterminen und Ansprechpartnern zur Pflege.',
        displayed_link: 'landkreis.example.de › pflegestuetzpunkt',
        source: 'landkreis.example.de',
      },
      classification: {
        classification: 'GOVERNMENT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 9,
        title: 'Pflegedienst Sonnenblume – Grundpflege und Behandlungspflege (fiktiv)',
        link: 'https://sonnenblume-pflege.example.de/',
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
        title: 'Pflegedienst wechseln: worauf achten? | Beispiel Pflegeblog (fiktiv)',
        link: 'https://blog.example.de/pflegedienst-wechseln/',
        snippet:
          'Fiktiver Blogbeitrag zu Kündigungsfristen und Übergabe bei einem Wechsel des Pflegedienstes.',
        displayed_link: 'blog.example.de › pflegedienst-wechseln',
        source: 'blog.example.de',
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
        title: 'Pflegedienste weisen neue Patienten ab – Personal fehlt',
        link: 'https://news.example.com/fixture/de_news_01',
        source_name: 'Beispiel Tagesbericht (fiktiv)',
        published_at: '2026-08-27T02:24:00Z',
        raw_date: '08/27/2026, 04:24 AM, +0200 CEST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 2,
        title: 'Jedes dritte Pflegeheim meldet Aufnahmestopp',
        link: 'https://news.example.com/fixture/de_news_02',
        source_name: 'Beispiel Gesundheitsjournal (fiktiv)',
        published_at: '2026-08-25T09:36:00Z',
        raw_date: '08/25/2026, 11:36 AM, +0200 CEST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 3,
        title: 'Eigenanteil im Pflegeheim steigt erneut deutlich',
        link: 'https://news.example.com/fixture/de_news_03',
        source_name: 'Beispiel Wirtschaftsblatt (fiktiv)',
        published_at: '2026-08-22T21:36:00Z',
        raw_date: '08/22/2026, 11:36 PM, +0200 CEST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 4,
        title: 'Kurzzeitpflege: Angehörige finden monatelang keinen Platz',
        link: 'https://news.example.com/fixture/de_news_04',
        source_name: 'Beispiel Regionalnachrichten (fiktiv)',
        published_at: '2026-08-20T04:48:00Z',
        raw_date: '08/20/2026, 06:48 AM, +0200 CEST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 5,
        title: 'Pflegeverband fordert Sofortprogramm gegen Personalmangel',
        link: 'https://news.example.com/fixture/de_news_05',
        source_name: 'Beispiel Politikreport (fiktiv)',
        published_at: '2026-08-16T09:36:00Z',
        raw_date: '08/16/2026, 11:36 AM, +0200 CEST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 6,
        title: 'Ausbildungszahlen in der Pflege stagnieren',
        link: 'https://news.example.com/fixture/de_news_06',
        source_name: 'Beispiel Bildungsdienst (fiktiv)',
        published_at: '2026-08-11T19:12:00Z',
        raw_date: '08/11/2026, 09:12 PM, +0200 CEST',
      },
      classification: {
        classification: 'RELATED',
        confidence: 0.7,
      },
    },
    {
      item: {
        position: 7,
        title: 'Kliniken verschieben Entlassungen wegen fehlender Pflegeplätze',
        link: 'https://news.example.com/fixture/de_news_07',
        source_name: 'Beispiel Gesundheitsjournal (fiktiv)',
        published_at: '2026-08-06T07:12:00Z',
        raw_date: '08/06/2026, 09:12 AM, +0200 CEST',
      },
      classification: {
        classification: 'DIRECTLY_RELEVANT',
        confidence: 0.9,
      },
    },
    {
      item: {
        position: 8,
        title: 'Ländliche Regionen verlieren ambulante Pflegedienste',
        link: 'https://news.example.com/fixture/de_news_08',
        source_name: 'Beispiel Regionalnachrichten (fiktiv)',
        published_at: '2026-07-31T14:24:00Z',
        raw_date: '07/31/2026, 04:24 PM, +0200 CEST',
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
      title: 'Beispiel Pflegedienst Morgenstern (fiktiv)',
      place_id: 'FIXTURE_PLACE_ID_DE_PLACE_01',
      rating: 4.4,
      reviews: 62,
      place_type: 'Ambulanter Pflegedienst',
      address: 'Beispielstraße 12, Beispielstadt',
      link: null,
    },
    {
      position: 2,
      title: 'Beispiel Pflegedienst Lindenhof (fiktiv)',
      place_id: 'FIXTURE_PLACE_ID_DE_PLACE_02',
      rating: 4.1,
      reviews: 39,
      place_type: 'Ambulanter Pflegedienst',
      address: 'Beispielallee 5, Beispielstadt',
      link: null,
    },
    {
      position: 3,
      title: 'Beispiel Seniorenzentrum Rosengarten (fiktiv)',
      place_id: 'FIXTURE_PLACE_ID_DE_PLACE_03',
      rating: 3.6,
      reviews: 91,
      place_type: 'Pflegeheim',
      address: 'Beispielweg 88, Beispielstadt',
      link: null,
    },
    {
      position: 4,
      title: 'Beispiel Tagespflege Sonnenhof (fiktiv)',
      place_id: 'FIXTURE_PLACE_ID_DE_PLACE_04',
      rating: 4.6,
      reviews: 24,
      place_type: 'Tagespflege',
      address: 'Beispielplatz 3, Beispielstadt',
      link: null,
    },
    {
      position: 5,
      title: 'Beispiel Pflegedienst Sonnenblume (fiktiv)',
      place_id: 'FIXTURE_PLACE_ID_DE_PLACE_05',
      rating: 4.0,
      reviews: 17,
      place_type: 'Ambulanter Pflegedienst',
      address: 'Beispielring 21, Beispielstadt',
      link: null,
    },
    {
      position: 6,
      title: 'Beispiel Kurzzeitpflege am Park (fiktiv)',
      place_id: 'FIXTURE_PLACE_ID_DE_PLACE_06',
      rating: 3.9,
      reviews: 28,
      place_type: 'Kurzzeitpflege',
      address: 'Beispielufer 7, Beispielstadt',
      link: null,
    },
  ],
  versions: {
    query_profile_version: 'elder-care-de-v2',
    score_version: 'gapatlas-score-v1',
    classifier_version: 'gapatlas-classifier-v1-stub',
    prompt_version: 'gapatlas-prompt-v1-stub',
  },
  computed_at: '2026-08-28T00:00:00+00:00',
};
