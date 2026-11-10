import type { ReactNode } from "react";

import { KeyboardHint } from "./keyboard_hint.tsx";
import styles from "./button.module.css";

export const ButtonVariant = {
  Primary: "primary",
  Secondary: "secondary",
  Ghost: "ghost",
} as const;
export type ButtonVariant = (typeof ButtonVariant)[keyof typeof ButtonVariant];

export const ButtonTone = {
  Default: "default",
  Accept: "accept",
} as const;
export type ButtonTone = (typeof ButtonTone)[keyof typeof ButtonTone];

/**
 * A labeled action, with an optional keyboard hint.
 * @param variant - The visual weight of the action.
 * @param tone - Whether the label uses the accept color.
 * @param label - The words on the button.
 * @param shortcut - The keys to show, or an empty string when there is no shortcut.
 * @param disabled - Whether the action is unavailable.
 * @param onClick - What happens when the button is pressed.
 * @returns The button.
 * @throws Does not throw.
 */
export function Button({
  variant,
  tone,
  label,
  shortcut,
  disabled,
  onClick,
}: {
  variant: ButtonVariant;
  tone: ButtonTone;
  label: string;
  shortcut: string;
  disabled: boolean;
  onClick: () => void;
}): ReactNode {
  const className = [
    styles.button,
    styles[variant],
    tone === ButtonTone.Accept ? styles.accept : "",
  ]
    .filter((name) => name !== "")
    .join(" ");
  return (
    <button
      type="button"
      className={className}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      {label}
      {shortcut === "" ? null : <KeyboardHint keys={shortcut} />}
    </button>
  );
}
