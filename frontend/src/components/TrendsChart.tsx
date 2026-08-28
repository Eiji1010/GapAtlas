/**
 * Trends の週次系列を素の SVG で描く。
 *
 * グラフライブラリを足さない(依存は必要最小限)。値は Google Trends の
 * 0〜100 で、**期間・地域内の相対値**であるため軸も 0〜100 に固定する。
 */

import type { TrendsTimeseries } from '../api/types';
import { formatDate } from '../labels';

const WIDTH = 640;
const HEIGHT = 180;
const PADDING_X = 8;
const PADDING_Y = 8;
/** 系列ごとの線色。3クエリ想定(QueryProfile の `demand_queries`)。 */
const SERIES_COLORS = ['#2f6f4f', '#a8552b', '#3b5c9c', '#7a3f86', '#5d5d2b'];

interface TrendsChartProps {
  timeseries: TrendsTimeseries | null;
}

function buildPoints(values: readonly number[]): string {
  if (values.length === 0) {
    return '';
  }
  const innerWidth = WIDTH - PADDING_X * 2;
  const innerHeight = HEIGHT - PADDING_Y * 2;
  const step = values.length === 1 ? 0 : innerWidth / (values.length - 1);
  return values
    .map((value, index) => {
      const x = PADDING_X + step * index;
      // Trends の値域は 0〜100。上端が 100 になるよう反転する。
      const y = PADDING_Y + innerHeight * (1 - Math.min(Math.max(value, 0), 100) / 100);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

export function TrendsChart({ timeseries }: TrendsChartProps) {
  const series = timeseries?.series ?? [];
  const drawable = series.filter((entry) => entry.points.length > 0);

  if (drawable.length === 0) {
    return <p className="empty">Trends の系列を取得できませんでした。</p>;
  }

  const first = drawable[0];
  const firstPoint = first?.points[0] ?? null;
  const lastPoint = first?.points[first.points.length - 1] ?? null;

  return (
    <div className="trends-chart">
      <svg
        viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
        className="trends-chart__svg"
        role="img"
        aria-label="Google Trends の週次系列"
      >
        <line
          x1={PADDING_X}
          y1={HEIGHT - PADDING_Y}
          x2={WIDTH - PADDING_X}
          y2={HEIGHT - PADDING_Y}
          className="trends-chart__axis"
        />
        {drawable.map((entry, index) => (
          <polyline
            key={entry.query}
            points={buildPoints(entry.points.map((point) => point.value))}
            fill="none"
            stroke={SERIES_COLORS[index % SERIES_COLORS.length]}
            strokeWidth={2}
          />
        ))}
      </svg>
      <ul className="trends-chart__legend">
        {drawable.map((entry, index) => (
          <li key={entry.query}>
            <span
              className="trends-chart__swatch"
              style={{ backgroundColor: SERIES_COLORS[index % SERIES_COLORS.length] }}
              aria-hidden="true"
            />
            {entry.query}
            <span className="muted"> ({String(entry.points.length)} 点)</span>
          </li>
        ))}
      </ul>
      <p className="muted">
        期間: {formatDate(firstPoint?.timestamp ?? null)} 〜{' '}
        {formatDate(lastPoint?.timestamp ?? null)}／ 縦軸は Google Trends の
        0〜100(期間・地域内の相対値)
      </p>
    </div>
  );
}
