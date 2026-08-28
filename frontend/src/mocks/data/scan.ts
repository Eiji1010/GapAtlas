/**
 * スキャン概要のうち、国別詳細から導けない部分のモック。
 *
 * fixture モードの実行結果(stub LLM)をそのまま写している。
 */

import type { OpportunityBrief, Versions } from '../../api/types';

export const MOCK_OPPORTUNITY_BRIEF: OpportunityBrief = {
  why_now:
    'Stub mode: this brief is assembled in code, without a language model. The signals observed for elder_care in Japan during the scanned window are listed as evidence below. [E1] [E2] [E3] [E4] [E5]',
  what_people_are_struggling_with:
    'The recorded difficulties are exactly the ones summarised in the evidence; read each entry rather than this sentence. [E1] [E2] [E3] [E4] [E5]',
  visible_solutions:
    'What the search results made visible for this country is described in the same evidence entries. [E1] [E2] [E3] [E4] [E5]',
  what_this_does_not_prove:
    'This is a search-visible signal only. It does not measure the objective severity of the problem. Low visible solution coverage is not the same as low actual supply of services. Google Trends values are relative within the requested period and region, so demand levels are not compared across countries. Media coverage volume reflects editorial attention, not the presence or absence of the problem.',
  next_validation:
    'Treat this as a starting point: check official statistics and regulation for the country, then run local interviews with providers and families before drawing any conclusion.',
  cited_evidence_ids: ['E1', 'E2', 'E3', 'E4', 'E5'],
};

export const MOCK_VERSIONS: Versions = {
  query_profile_version:
    'elder-care-de-v2,elder-care-gb-v2,elder-care-in-v2,elder-care-jp-v2,elder-care-us-v2',
  score_version: 'gapatlas-score-v1',
  classifier_version: 'gapatlas-classifier-v1-stub',
  prompt_version: 'gapatlas-prompt-v1-stub',
};
