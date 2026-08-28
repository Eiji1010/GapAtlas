/**
 * Screen 1: Discover。
 *
 * `docs/requirements.md`「Screen 1」: Elder Care / Countries / Analyze Live
 * Signals ボタン / 進捗表示 / 国別ランキング(Need Gap・Confidence)。
 *
 * **処理中も部分的なランキングを出す。** バックエンドは1国終わるたびに概要を
 * 更新する(docs/api.md)。
 */

import { useState } from 'react';

import { sortRanking } from '../api/ranking';
import type { CountryCode } from '../api/types';
import { Note } from '../components/Note';
import type { UseScanResult } from '../hooks/useScan';
import { COUNTRY_LABELS, COUNTRY_STATUS_LABELS, MVP_COUNTRIES, formatScore } from '../labels';
import {
  NOTE_LOW_CONFIDENCE,
  NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND,
  NOTE_SCORE_NOT_SEVERITY,
} from '../notes';

interface DiscoverScreenProps {
  scan: UseScanResult;
  onSelectCountry: (country: CountryCode) => void;
  onOpenBrief: () => void;
}

export function DiscoverScreen({ scan, onSelectCountry, onOpenBrief }: DiscoverScreenProps) {
  const [selected, setSelected] = useState<readonly CountryCode[]>(MVP_COUNTRIES);
  const running = scan.phase === 'starting' || scan.phase === 'polling';

  const toggle = (country: CountryCode) => {
    setSelected((current) =>
      current.includes(country)
        ? current.filter((item) => item !== country)
        : [...current, country],
    );
  };

  const ranking = scan.summary === null ? [] : sortRanking(scan.summary.ranking);

  return (
    <section>
      <h2>Elder Care</h2>
      <p className="muted">
        検索需要と困りごとが増えている一方で、検索上で見える解決策が追いついていない国を探します。
      </p>

      <fieldset className="country-picker">
        <legend>Countries</legend>
        {MVP_COUNTRIES.map((country) => (
          <label key={country}>
            <input
              type="checkbox"
              checked={selected.includes(country)}
              disabled={running}
              onChange={() => {
                toggle(country);
              }}
            />
            {COUNTRY_LABELS[country]}
          </label>
        ))}
      </fieldset>

      <button
        type="button"
        disabled={running || selected.length === 0}
        onClick={() => {
          void scan.start(selected);
        }}
      >
        Analyze Live Signals
      </button>

      {scan.error !== null && <p className="error">{scan.error}</p>}

      {scan.summary !== null && (
        <p aria-live="polite">
          進捗: {scan.summary.progress.completed} / {scan.summary.progress.total} 国（
          {scan.summary.status === 'processing' ? '処理中' : '完了'}）
        </p>
      )}

      {ranking.length > 0 && (
        <>
          <table>
            <caption>国別ランキング</caption>
            <thead>
              <tr>
                <th scope="col">国</th>
                <th scope="col">状態</th>
                <th scope="col" className="numeric">
                  Need Gap
                </th>
                <th scope="col" className="numeric">
                  Confidence
                </th>
                <th scope="col">詳細</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((entry) => (
                <tr key={entry.country}>
                  <th scope="row">{COUNTRY_LABELS[entry.country]}</th>
                  <td>{COUNTRY_STATUS_LABELS[entry.status]}</td>
                  <td className="numeric">{formatScore(entry.need_gap_score)}</td>
                  <td className="numeric">{entry.confidence}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => {
                        onSelectCountry(entry.country);
                      }}
                    >
                      Evidence を見る
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <Note>{NOTE_SCORE_NOT_SEVERITY}</Note>
          <Note>{NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND}</Note>
          <Note>{NOTE_LOW_CONFIDENCE}</Note>
        </>
      )}

      {scan.summary?.opportunity_brief != null && (
        <button type="button" className="secondary" onClick={onOpenBrief}>
          Opportunity Brief を見る
        </button>
      )}
    </section>
  );
}
