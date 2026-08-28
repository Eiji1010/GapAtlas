/**
 * Vitest の共通セットアップ。
 *
 * `@testing-library/jest-dom` は**追加していない**(依存を増やさない方針)。
 * アサーションは Vitest 標準の `expect` と DOM の素の API で書く。
 */

import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// `globals: true` を使っていないため、自動 cleanup は効かない。明示的に呼ぶ。
afterEach(() => {
  cleanup();
});
