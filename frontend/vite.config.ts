import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // 画面のテストは DOM を必要とする。
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // `npm run test` は watch にしない(CI が止まる)。package.json で `vitest run` を使う。
    restoreMocks: true,
  },
});
