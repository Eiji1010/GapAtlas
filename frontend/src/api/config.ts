/**
 * 実行時設定と `ApiClient` の組み立て。
 *
 * - `VITE_API_MODE`: `mock`(既定)/ `live`
 * - `VITE_API_BASE_URL`: live モードで呼ぶ API のベース URL
 *
 * **秘密情報をここへ置かない。** `VITE_` 接頭辞の値はビルド成果物へ
 * 埋め込まれる。SerpApi / Anthropic のキーはバックエンドのみが持つ。
 */

import { HttpApiClient } from './httpClient';
import type { ApiClient } from './types';
import { MockApiClient } from '../mocks/mockClient';

export type ApiMode = 'mock' | 'live';

/**
 * 既定はローカル開発用。ハードコードした値を live の既定にしないため、
 * `.env` で上書きできるようにしている(`frontend/.env.example`)。
 */
export const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1';

/**
 * 既定は `mock`。
 *
 * バックエンドを起動していなくてもデモが動くことを優先する
 * (AGENTS.md「fixture mode を常に維持する」と同じ思想)。
 */
export const DEFAULT_API_MODE: ApiMode = 'mock';

export function resolveApiMode(value: string | undefined): ApiMode {
  return value === 'live' ? 'live' : DEFAULT_API_MODE;
}

export function resolveApiBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim();
  return trimmed !== undefined && trimmed !== '' ? trimmed : DEFAULT_API_BASE_URL;
}

export function createApiClient(env: ImportMetaEnv): ApiClient {
  if (resolveApiMode(env.VITE_API_MODE) === 'live') {
    return new HttpApiClient(resolveApiBaseUrl(env.VITE_API_BASE_URL));
  }
  return new MockApiClient();
}
