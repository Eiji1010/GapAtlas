/**
 * Screen 2: Country Evidence。
 *
 * `docs/requirements.md`「Screen 2」: Country / Need Gap Signal Score /
 * Evidence Confidence / Demand / Pain / Solution Gap / News Urgency /
 * Trends / Related Queries / Search / News / Maps(Top2のみ)。
 *
 * **`maps_results` の `null` と `[]` は意味が違う**(docs/api.md)。
 * `null` は「取得していない」、`[]` は「取得したが0件」。
 */

import type { CountryCode, CountryDetail } from '../api/types';
import { evidenceAnchorId } from '../components/evidenceAnchor';
import { Note } from '../components/Note';
import { ScoreBar } from '../components/ScoreBar';
import { TrendsChart } from '../components/TrendsChart';
import {
  CONFIDENCE_BREAKDOWN_LABELS,
  COMPONENT_LABELS,
  COUNTRY_LABELS,
  COUNTRY_STATUS_LABELS,
  NEWS_RELEVANCE_LABELS,
  PAIN_CATEGORY_LABELS,
  SOLUTION_CATEGORY_LABELS,
  SOURCE_LABELS,
  SOURCE_STATUS_LABELS,
  formatDate,
  formatScore,
} from '../labels';
import {
  NOTE_INSUFFICIENT_EVIDENCE,
  NOTE_MAPS,
  NOTE_NEWS,
  NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND,
  NOTE_SCORE_NOT_SEVERITY,
  NOTE_SOLUTION_GAP,
} from '../notes';

interface CountryEvidenceScreenProps {
  country: CountryCode;
  loading: boolean;
  detail: CountryDetail | null;
  error: string | null;
}

export function CountryEvidenceScreen({
  country,
  loading,
  detail,
  error,
}: CountryEvidenceScreenProps) {
  if (loading) {
    return <p>読み込み中…</p>;
  }
  if (error !== null) {
    return <p className="error">{error}</p>;
  }
  if (detail === null) {
    return <p className="muted">まだ結果がありません。</p>;
  }

  const scoreless = detail.need_gap_score === null;

  return (
    <section>
      <h2>{COUNTRY_LABELS[country]}</h2>
      <p className="muted">
        状態: {COUNTRY_STATUS_LABELS[detail.status]} / 算出時刻: {formatDate(detail.computed_at)}
      </p>

      <div className="card">
        <h3>スコア</h3>
        <p>
          Need Gap Signal Score:{' '}
          <strong>{scoreless ? 'スコアなし' : formatScore(detail.need_gap_score)}</strong>
        </p>
        <p>
          Evidence Confidence: <strong>{detail.confidence}</strong>
        </p>
        {scoreless && <Note>{NOTE_INSUFFICIENT_EVIDENCE}</Note>}

        <ScoreBar label={COMPONENT_LABELS.demand} value={detail.components.demand} />
        <ScoreBar label={COMPONENT_LABELS.pain} value={detail.components.pain} />
        <ScoreBar label={COMPONENT_LABELS.solution_gap} value={detail.components.solution_gap} />
        <ScoreBar label={COMPONENT_LABELS.news_urgency} value={detail.components.news_urgency} />

        <Note>{NOTE_SCORE_NOT_SEVERITY}</Note>
        <Note>{NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND}</Note>
        <Note>{NOTE_SOLUTION_GAP}</Note>
      </div>

      <div className="card">
        <h3>Evidence Confidence の内訳</h3>
        {(
          Object.keys(CONFIDENCE_BREAKDOWN_LABELS) as (keyof typeof CONFIDENCE_BREAKDOWN_LABELS)[]
        ).map((key) => (
          <ScoreBar
            key={key}
            label={CONFIDENCE_BREAKDOWN_LABELS[key]}
            value={detail.confidence_breakdown[key]}
          />
        ))}
        <ul>
          {Object.entries(detail.source_status).map(([source, status]) => (
            <li key={source}>
              {SOURCE_LABELS[source as keyof typeof SOURCE_LABELS]}:{' '}
              {status === undefined ? '-' : SOURCE_STATUS_LABELS[status]}
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>Evidence</h3>
        <ul>
          {detail.evidence.map((item) => (
            <li key={item.id} id={evidenceAnchorId(item.id)}>
              <span className="tag">{item.id}</span> {item.summary}{' '}
              {item.url !== null && (
                <a href={item.url} target="_blank" rel="noreferrer">
                  出典
                </a>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>Trends</h3>
        {detail.trends === null ? (
          <p className="muted">Trends を取得できませんでした。</p>
        ) : (
          <TrendsChart timeseries={detail.trends} />
        )}
      </div>

      <div className="card">
        <h3>Related Queries</h3>
        <table>
          <thead>
            <tr>
              <th scope="col">検索語</th>
              <th scope="col">分類</th>
              <th scope="col" className="numeric">
                成長率
              </th>
            </tr>
          </thead>
          <tbody>
            {detail.related_queries.map((entry) => (
              <tr key={entry.item.query}>
                <td>{entry.item.query}</td>
                <td>
                  {PAIN_CATEGORY_LABELS[entry.classification.classification]}
                  <span className="muted"> ({entry.classification.confidence.toFixed(2)})</span>
                </td>
                <td className="numeric">
                  {entry.item.is_breakout ? 'Breakout' : `+${String(entry.item.growth_percent)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Search</h3>
        <ol>
          {detail.search_results.map((entry) => (
            <li key={entry.item.link}>
              <a href={entry.item.link} target="_blank" rel="noreferrer">
                {entry.item.title}
              </a>{' '}
              <span className="tag">
                {SOLUTION_CATEGORY_LABELS[entry.classification.classification]}
              </span>
            </li>
          ))}
        </ol>
        <Note>{NOTE_SOLUTION_GAP}</Note>
      </div>

      <div className="card">
        <h3>News</h3>
        <ul>
          {detail.news_results.map((entry) => (
            <li key={entry.item.link}>
              <a href={entry.item.link} target="_blank" rel="noreferrer">
                {entry.item.title}
              </a>{' '}
              <span className="tag">
                {NEWS_RELEVANCE_LABELS[entry.classification.classification]}
              </span>{' '}
              <span className="muted">{formatDate(entry.item.published_at)}</span>
            </li>
          ))}
        </ul>
        <Note>{NOTE_NEWS}</Note>
      </div>

      <div className="card">
        <h3>Maps</h3>
        {detail.maps_results === null ? (
          <p className="muted">この国では Maps を取得していません（Top 2 の国のみ取得します）。</p>
        ) : detail.maps_results.length === 0 ? (
          <p className="muted">Maps を取得しましたが、該当は 0 件でした。</p>
        ) : (
          <ul>
            {detail.maps_results.map((place) => (
              <li key={`${String(place.position)}-${place.title}`}>
                {place.title}
                {place.address !== null && <span className="muted"> / {place.address}</span>}
              </li>
            ))}
          </ul>
        )}
        <Note>{NOTE_MAPS}</Note>
      </div>
    </section>
  );
}
