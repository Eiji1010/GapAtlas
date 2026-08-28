/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** `mock`(既定)/ `live`。 */
  readonly VITE_API_MODE?: string;
  /** live モードで呼ぶ API のベース URL(`/api/v1` まで)。 */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
