/**
 * `POST /scans` と、`GET /scans/{scan_id}` の **2秒間隔 Polling**。
 *
 * `docs/requirements.md`「更新方式」: WebSocket / SSE は使わない。
 * `status` が `completed` / `partially_failed` になったら **必ず Polling を
 * 止める**。止め忘れは無限ポーリングになる。
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { describeApiError } from '../api/errors';
import type { ApiClient, CountryCode, ScanStatus, ScanSummary } from '../api/types';

/** docs/requirements.md「2秒程度の Polling」。 */
export const POLL_INTERVAL_MS = 2000;

/** Polling を止めてよいスキャン状態。 */
const TERMINAL_STATUSES: readonly ScanStatus[] = ['completed', 'partially_failed'];

export function isTerminal(status: ScanStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export type ScanPhase = 'idle' | 'starting' | 'polling' | 'finished' | 'error';

export interface ScanState {
  phase: ScanPhase;
  scanId: string | null;
  summary: ScanSummary | null;
  error: string | null;
}

const INITIAL_STATE: ScanState = {
  phase: 'idle',
  scanId: null,
  summary: null,
  error: null,
};

export interface UseScanResult extends ScanState {
  /** `Analyze Live Signals` ボタンから呼ぶ。 */
  start: (countries: readonly CountryCode[]) => Promise<void>;
}

export function useScan(client: ApiClient): UseScanResult {
  const [state, setState] = useState<ScanState>(INITIAL_STATE);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      // アンマウント時に必ず止める。画面を離れても叩き続けないこと。
      mountedRef.current = false;
      stopPolling();
    };
  }, [stopPolling]);

  const poll = useCallback(
    async (scanId: string): Promise<void> => {
      try {
        const summary = await client.getScan(scanId);
        if (!mountedRef.current) {
          return;
        }
        if (isTerminal(summary.status)) {
          stopPolling();
        }
        setState({
          phase: isTerminal(summary.status) ? 'finished' : 'polling',
          scanId,
          summary,
          error: null,
        });
      } catch (error) {
        stopPolling();
        if (!mountedRef.current) {
          return;
        }
        setState((previous) => ({
          ...previous,
          phase: 'error',
          error: describeApiError(error),
        }));
      }
    },
    [client, stopPolling],
  );

  const start = useCallback(
    async (countries: readonly CountryCode[]): Promise<void> => {
      stopPolling();
      setState({ phase: 'starting', scanId: null, summary: null, error: null });

      let scanId: string;
      try {
        const created = await client.createScan({
          topic_id: 'elder_care',
          countries: [...countries],
        });
        scanId = created.scan_id;
      } catch (error) {
        if (mountedRef.current) {
          setState({
            phase: 'error',
            scanId: null,
            summary: null,
            error: describeApiError(error),
          });
        }
        return;
      }

      if (!mountedRef.current) {
        return;
      }
      setState({ phase: 'polling', scanId, summary: null, error: null });

      // 先に interval を張り、そのうえで即時に1回読む。即時分で完了していれば
      // `poll` の中で `stopPolling` が走るため、余計な Polling は発生しない。
      intervalRef.current = setInterval(() => {
        void poll(scanId);
      }, POLL_INTERVAL_MS);
      await poll(scanId);
    },
    [client, poll, stopPolling],
  );

  return { ...state, start };
}
