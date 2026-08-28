import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactRefresh.configs.vite,
      // 整形は Prettier に任せる。競合するルールを最後に無効化する。
      prettier,
    ],
    // react-hooks の共有設定は eslintrc 形式( が配列)なので
    // flat config へそのまま展開できない。プラグインを自分で登録する。
    plugins: { 'react-hooks': reactHooks },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      '@typescript-eslint/consistent-type-imports': 'error',
      // API が返した URL のみを使う(AGENTS.md「AI に URL を生成させない」)。
      // 型で表現しきれないため、明示的な any の禁止で穴を塞ぐ。
      '@typescript-eslint/no-explicit-any': 'error',
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**/*.ts'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    files: ['*.config.{js,ts}'],
    languageOptions: {
      globals: globals.node,
    },
  },
);
