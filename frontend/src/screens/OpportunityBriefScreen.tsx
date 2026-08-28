/**
 * Screen 3: Opportunity Brief。
 *
 * `docs/requirements.md`「Screen 3」の5節を、要件どおりの見出しで出す。
 * 本文の `[E1]` 引用は、対応する Evidence へのリンクとツールチップにする
 * (`components/BriefText.tsx`)。
 *
 * **Brief は Top1 の国についてのみ生成される。** 生成されなかった場合
 * (`null`)は、誤った断定を出すより出さないほうが安全という方針の結果で
 * あることを明示する(docs/llm-prompts.md)。
 */

import type { CountryCode, Evidence, OpportunityBrief } from '../api/types';
import { BriefText } from '../components/BriefText';
import { evidenceAnchorId } from '../components/evidenceAnchor';
import { Note } from '../components/Note';
import { COUNTRY_LABELS } from '../labels';
import { NOTE_SCORE_NOT_SEVERITY } from '../notes';

const SECTIONS: readonly { key: keyof OpportunityBrief; heading: string }[] = [
  { key: 'why_now', heading: 'WHY NOW' },
  { key: 'what_people_are_struggling_with', heading: 'WHAT PEOPLE ARE STRUGGLING WITH' },
  { key: 'visible_solutions', heading: 'VISIBLE SOLUTIONS' },
  { key: 'what_this_does_not_prove', heading: 'WHAT THIS DOES NOT PROVE' },
  { key: 'next_validation', heading: 'NEXT VALIDATION' },
];

interface OpportunityBriefScreenProps {
  country: CountryCode | null;
  brief: OpportunityBrief | null;
  evidence: readonly Evidence[];
}

export function OpportunityBriefScreen({ country, brief, evidence }: OpportunityBriefScreenProps) {
  if (brief === null) {
    return (
      <section>
        <h2>Opportunity Brief</h2>
        <p className="muted">
          Opportunity Brief
          は生成されていません。検証に通らない生成結果は採用しません（誤った断定を出すより出さない方針です）。
        </p>
      </section>
    );
  }

  const evidenceById = new Map(evidence.map((item) => [item.id, item]));

  return (
    <section>
      <h2>Opportunity Brief{country !== null && `: ${COUNTRY_LABELS[country]}`}</h2>

      {SECTIONS.map(({ key, heading }) => (
        <div className="card" key={key}>
          <h3>{heading}</h3>
          <BriefText text={String(brief[key])} evidenceById={evidenceById} />
        </div>
      ))}

      <div className="card">
        <h3>引用された Evidence</h3>
        {evidence.length === 0 ? (
          <p className="muted">Evidence を取得できていません。</p>
        ) : (
          <ul>
            {evidence.map((item) => (
              <li key={item.id} id={evidenceAnchorId(item.id)}>
                <span className="tag">{item.id}</span> {item.summary}
              </li>
            ))}
          </ul>
        )}
      </div>

      <Note>{NOTE_SCORE_NOT_SEVERITY}</Note>
    </section>
  );
}
