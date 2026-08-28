/**
 * Evidence 一覧の各項目に振る DOM id。Opportunity Brief の `[E1]` 引用の
 * リンク先になる。
 *
 * **コンポーネントと同じファイルに置かない。** Fast Refresh はコンポーネント
 * だけを export するファイルでしか働かない(`react-refresh/only-export-components`)。
 */

export function evidenceAnchorId(evidenceId: string): string {
  return `evidence-${evidenceId}`;
}
