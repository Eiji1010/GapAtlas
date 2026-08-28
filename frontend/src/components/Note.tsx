/** UI 必須注記の表示。文言は `src/notes.ts` が正本。 */

interface NoteProps {
  children: string;
}

export function Note({ children }: NoteProps) {
  return (
    <p className="note" role="note">
      {children}
    </p>
  );
}
