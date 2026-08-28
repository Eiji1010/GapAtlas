/**
 * `GET /scans/{scan_id}/countries/{country}` を1件読む。Screen 2 / Screen 3 が使う。
 *
 * **effect の中で同期的に `setState` しない**(cascading render になる)。
 * 「まだ読み込んでいない」状態は保持している key との差から**導出**する。
 */

import { useEffect, useState } from 'react';

import { describeApiError } from '../api/errors';
import type { ApiClient, CountryCode, CountryDetail } from '../api/types';

export interface CountryDetailState {
  loading: boolean;
  detail: CountryDetail | null;
  error: string | null;
}

interface LoadedState extends CountryDetailState {
  /** どの `(scan_id, country)` の結果かを表す。導出に使う。 */
  key: string | null;
}

const EMPTY: CountryDetailState = { loading: false, detail: null, error: null };

function makeKey(scanId: string | null, country: CountryCode | null): string | null {
  return scanId === null || country === null ? null : `${scanId}:${country}`;
}

export function useCountryDetail(
  client: ApiClient,
  scanId: string | null,
  country: CountryCode | null,
): CountryDetailState {
  const key = makeKey(scanId, country);
  const [state, setState] = useState<LoadedState>({ key: null, ...EMPTY });

  useEffect(() => {
    if (scanId === null || country === null) {
      return;
    }

    let cancelled = false;
    client
      .getCountry(scanId, country)
      .then((detail) => {
        if (!cancelled) {
          setState({ key: makeKey(scanId, country), loading: false, detail, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            key: makeKey(scanId, country),
            loading: false,
            detail: null,
            error: describeApiError(error),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [client, scanId, country]);

  if (key === null) {
    return EMPTY;
  }
  if (state.key !== key) {
    // 対象が変わった直後。前の国の結果を見せない。
    return { loading: true, detail: null, error: null };
  }
  return { loading: state.loading, detail: state.detail, error: state.error };
}
