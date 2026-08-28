/**
 * Opportunity Brief 本文の `[E1]` 引用を Evidence へ対応づけて描く。
 *
 * `docs/requirements.md`「Evidence には ID(`E1` `E2` ...)を付与し、AIは
 * `Demand accelerated [E1]` のように引用する」。UI 側では同じ ID の Evidence
 * へのリンクとツールチップにする。**外部 URL はここで作らない**
 * (AGENTS.md「AI に URL を生成させない」の帰結)。リンク先は同じページ内の
 * Evidence 一覧のみ。
 */

import type { Evidence } from '../api/types';
import { evidenceAnchorId } from './evidenceAnchor';

/** `[E1]` の形。id は `E` + 1始まりの連番(domain の EVIDENCE_ID_PATTERN)。 */
const CITATION_PATTERN = /\[(E[1-9][0-9]*)\]/g;

interface BriefTextProps {
  text: string;
  evidenceById: ReadonlyMap<string, Evidence>;
}

export function BriefText({ text, evidenceById }: BriefTextProps) {
  const nodes: React.ReactNode[] = [];
  let cursor = 0;

  for (const match of text.matchAll(CITATION_PATTERN)) {
    const id = match[1];
    const index = match.index;
    if (id === undefined) {
      continue;
    }
    if (index > cursor) {
      nodes.push(text.slice(cursor, index));
    }
    const evidence = evidenceById.get(id);
    if (evidence === undefined) {
      // 対応する Evidence が無い引用は、リンクにせず原文のまま出す。
      // 存在しない根拠へ誘導しないため。
      nodes.push(
        <span key={`${id}-${String(index)}`} className="citation citation--unresolved">
          [{id}]
        </span>,
      );
    } else {
      nodes.push(
        <a
          key={`${id}-${String(index)}`}
          className="citation"
          href={`#${evidenceAnchorId(id)}`}
          title={`${id}: ${evidence.summary}`}
        >
          [{id}]
        </a>,
      );
    }
    cursor = index + match[0].length;
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return <p className="brief-text">{nodes}</p>;
}
