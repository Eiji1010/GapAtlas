/** API 呼び出しの失敗を表す例外。UI はこれを見てエラー表示へ切り替える。 */
export class ApiError extends Error {
  /** HTTP ステータス。ネットワーク障害など HTTP に到達しなかった場合は 0。 */
  readonly status: number;

  /** `{"error": {"code": ...}}` の code。取得できなかった場合は `null`。 */
  readonly code: string | null;

  constructor(message: string, options: { status: number; code?: string | null }) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code ?? null;
  }
}

/** 画面に出す日本語のメッセージ。原文をそのまま出さず、状況ごとに言い換える。 */
export function describeApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return '予期しないエラーが発生しました。';
  }
  if (error.status === 0) {
    return 'API へ接続できませんでした。バックエンドが起動しているか確認してください。';
  }
  if (error.status === 404) {
    return '対象が見つかりませんでした(404)。スキャンまたは国が存在しません。';
  }
  if (error.status === 400) {
    return 'リクエストが不正です(400)。';
  }
  if (error.status >= 500) {
    return 'API がエラーを返しました(500)。時間をおいて再実行してください。';
  }
  return `API がエラーを返しました(${String(error.status)})。`;
}
