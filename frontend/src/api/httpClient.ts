/**
 * `docs/api.md` の4エンドポイントを型付きで呼ぶ薄い層。
 *
 * ベース URL は環境変数から受け取る。ここでハードコードしない。
 */

import { ApiError } from './errors';
import type {
  ApiClient,
  CountryCode,
  CountryDetail,
  CreateScanRequest,
  CreateScanResponse,
  ScanSummary,
  TopicsResponse,
} from './types';

function isErrorBody(value: unknown): value is { error: { code?: unknown; message?: unknown } } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as { error: unknown }).error === 'object' &&
    (value as { error: unknown }).error !== null
  );
}

/** `{"error": {"code": ..., "message": ...}}` から code を取り出す。 */
function extractCode(body: unknown): string | null {
  if (!isErrorBody(body)) {
    return null;
  }
  const code = body.error.code;
  return typeof code === 'string' ? code : null;
}

export class HttpApiClient implements ApiClient {
  private readonly baseUrl: string;

  private readonly fetchFn: typeof fetch;

  /**
   * @param baseUrl `/api/v1` までを含むベース URL。末尾の `/` は無視する。
   * @param fetchFn テストで差し替えるための注入点。既定はグローバルの `fetch`。
   */
  constructor(baseUrl: string, fetchFn: typeof fetch = globalThis.fetch.bind(globalThis)) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.fetchFn = fetchFn;
  }

  listTopics(signal?: AbortSignal): Promise<TopicsResponse> {
    return this.request<TopicsResponse>('/topics', { method: 'GET' }, signal);
  }

  createScan(request: CreateScanRequest, signal?: AbortSignal): Promise<CreateScanResponse> {
    return this.request<CreateScanResponse>(
      '/scans',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      },
      signal,
    );
  }

  getScan(scanId: string, signal?: AbortSignal): Promise<ScanSummary> {
    return this.request<ScanSummary>(
      `/scans/${encodeURIComponent(scanId)}`,
      { method: 'GET' },
      signal,
    );
  }

  getCountry(scanId: string, country: CountryCode, signal?: AbortSignal): Promise<CountryDetail> {
    return this.request<CountryDetail>(
      `/scans/${encodeURIComponent(scanId)}/countries/${encodeURIComponent(country)}`,
      { method: 'GET' },
      signal,
    );
  }

  private async request<T>(path: string, init: RequestInit, signal?: AbortSignal): Promise<T> {
    let response: Response;
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}`, {
        ...init,
        ...(signal === undefined ? {} : { signal }),
      });
    } catch (cause) {
      // ネットワーク障害・CORS 拒否。HTTP ステータスが存在しないので 0 とする。
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        throw cause;
      }
      throw new ApiError('failed to reach the API', { status: 0 });
    }

    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(`API responded with ${String(response.status)}`, {
        status: response.status,
        code: extractCode(body),
      });
    }
    return body as T;
  }
}
