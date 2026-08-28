/** 0〜100 のスコアを数値とバーで示す。`null` は「算出不能」として区別する。 */

import { formatScore } from '../labels';

interface ScoreBarProps {
  label: string;
  value: number | null;
}

export function ScoreBar({ label, value }: ScoreBarProps) {
  return (
    <div className="score-bar">
      <span className="score-bar__label">{label}</span>
      <span className="score-bar__track" aria-hidden="true">
        <span className="score-bar__fill" style={{ width: `${String(value ?? 0)}%` }} />
      </span>
      <span className="score-bar__value">{formatScore(value)}</span>
    </div>
  );
}
