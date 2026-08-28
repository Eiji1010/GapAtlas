/**
 * UI に必ず出す注記。
 *
 * 正本は `docs/methodology.md`「この文書の内容は UI にも反映します」と
 * `docs/scoring.md`「表示上の必須注記」。**省略してはいけない要件**であり、
 * 文言を1か所に置いて画面とテストで共有する。
 */

/** Solution Coverage Gap の近くに出す(docs/scoring.md 4章「表示上の必須注記」)。 */
export const NOTE_SOLUTION_GAP =
  'Solution Coverage Gap は実際のサービス供給不足ではなく、検索上で見える Solution Coverage の不足です。';

/** Maps の近くに出す(docs/methodology.md「Maps の件数 = 事業者数」は成り立たない)。 */
export const NOTE_MAPS = 'Maps の件数は事業者数ではありません。Core Score にも使用していません。';

/** スコアの近くに出す(docs/methodology.md「何を示さないか」)。 */
export const NOTE_SCORE_NOT_SEVERITY =
  'このスコアは社会問題の客観的な深刻度ではありません。検索という窓から見えるシグナルです。';

/** スコアの近くに出す(docs/scoring.md 2章「禁止事項」)。 */
export const NOTE_SCORE_NOT_CROSS_COUNTRY_DEMAND =
  '国同士の絶対的な検索需要を比較していません。Google Trends の値は期間・地域内の相対値です。';

/** Evidence Confidence の読み方(docs/methodology.md「Evidence Confidence を分けている理由」)。 */
export const NOTE_LOW_CONFIDENCE =
  'Evidence Confidence が低い国は、シグナルが弱いのではなく、まだ判断材料が足りないと読みます。';

/** ニュースの近くに出す(docs/scoring.md 5章「禁止事項」)。 */
export const NOTE_NEWS =
  'ニュースが少ないことは、問題が存在しない根拠にはなりません。News の重みは全体の 10% です。';

/** `insufficient_evidence` の国に出す(docs/scoring.md 7章)。 */
export const NOTE_INSUFFICIENT_EVIDENCE =
  'Insufficient Evidence はエラーではありません。判断材料が足りないため Need Gap Signal Score を出していません。';
