import type { ReactNode, Ref } from "react";

import { KeyboardHint } from "../../components/keyboard_hint.tsx";
import styles from "./search_box.module.css";

/**
 * The search field in the left rail.
 * @param query - The current text.
 * @param inputRef - The field the slash shortcut focuses when no contract is open.
 * @param showSlashHint - Whether this field is the one slash focuses.
 * @param onQueryChange - Stores the typed text.
 * @returns The field.
 * @throws Does not throw.
 */
export function SearchBox({
  query,
  inputRef,
  showSlashHint,
  onQueryChange,
}: {
  query: string;
  inputRef: Ref<HTMLInputElement>;
  showSlashHint: boolean;
  onQueryChange: (query: string) => void;
}): ReactNode {
  return (
    <label className={styles.field}>
      <span className="visuallyHidden">Search contracts</span>
      <input
        ref={inputRef}
        className={styles.input}
        value={query}
        placeholder="Search contracts"
        onChange={(event) => onQueryChange(event.target.value)}
      />
      {showSlashHint ? <KeyboardHint keys="/" /> : null}
    </label>
  );
}
