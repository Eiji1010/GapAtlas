/**
 * 画面は3つだけ(`docs/requirements.md`「Frontend」)。ルータを足さず、
 * 状態で切り替える。**要件にない画面遷移を増やさない。**
 */

import { useMemo, useState } from 'react';

import { createApiClient } from './api/config';
import type { CountryCode } from './api/types';
import { useCountryDetail } from './hooks/useCountryDetail';
import { useScan } from './hooks/useScan';
import { CountryEvidenceScreen } from './screens/CountryEvidenceScreen';
import { DiscoverScreen } from './screens/DiscoverScreen';
import { OpportunityBriefScreen } from './screens/OpportunityBriefScreen';
import { sortRanking } from './api/ranking';
import type { ApiClient } from './api/types';

type Screen = 'discover' | 'country' | 'brief';

interface AppProps {
  /** テストはフェイクを注入する。省略時は環境変数から組み立てる。 */
  client?: ApiClient;
}

export default function App({ client }: AppProps = {}) {
  const apiClient = useMemo(() => client ?? createApiClient(import.meta.env), [client]);
  const scan = useScan(apiClient);
  const [screen, setScreen] = useState<Screen>('discover');
  const [country, setCountry] = useState<CountryCode | null>(null);

  // Brief は Top1 の国のものなので、その国の Evidence を引用先にする。
  const topCountry = useMemo<CountryCode | null>(() => {
    if (scan.summary === null) {
      return null;
    }
    const rankable = sortRanking(scan.summary.ranking).filter(
      (entry) => entry.status === 'completed',
    );
    return rankable[0]?.country ?? null;
  }, [scan.summary]);

  const detailCountry = screen === 'brief' ? topCountry : country;
  const detail = useCountryDetail(apiClient, scan.scanId, detailCountry);

  return (
    <div className="app">
      <header className="app-header">
        <h1>GapAtlas</h1>
        <p>Discover where needs are rising faster than solutions.</p>
        {screen !== 'discover' && (
          <nav className="breadcrumb">
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setScreen('discover');
              }}
            >
              ← ランキングへ戻る
            </button>
          </nav>
        )}
      </header>

      {screen === 'discover' && (
        <DiscoverScreen
          scan={scan}
          onSelectCountry={(selected) => {
            setCountry(selected);
            setScreen('country');
          }}
          onOpenBrief={() => {
            setScreen('brief');
          }}
        />
      )}

      {screen === 'country' && country !== null && (
        <CountryEvidenceScreen
          country={country}
          loading={detail.loading}
          detail={detail.detail}
          error={detail.error}
        />
      )}

      {screen === 'brief' && (
        <OpportunityBriefScreen
          country={topCountry}
          brief={scan.summary?.opportunity_brief ?? null}
          evidence={detail.detail?.evidence ?? []}
        />
      )}
    </div>
  );
}
