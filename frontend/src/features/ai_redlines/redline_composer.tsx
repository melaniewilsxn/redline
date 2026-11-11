import type { ReactNode } from "react";

import { Button, ButtonTone, ButtonVariant } from "../../components/button.tsx";
import styles from "./redline_composer.module.css";

const INSTRUCTION_PLACEHOLDER = "Make the indemnification mutual";
const EMPTY_INSTRUCTION_MESSAGE = "Describe the changes you want";
const PRESET_INSTRUCTIONS = [
  "Review against our playbook",
  "Make the indemnification mutual",
  "Cap our liability at 12 months' fees",
];

/**
 * The instruction field and the preset reviews.
 * @param instruction - The current instruction.
 * @param instructionMissing - Whether the last submit was empty.
 * @param onInstructionChange - Stores the typed instruction.
 * @param onSubmit - Sends the instruction.
 * @returns The composer.
 * @throws Does not throw.
 */
export function RedlineComposer({
  instruction,
  instructionMissing,
  onInstructionChange,
  onSubmit,
}: {
  instruction: string;
  instructionMissing: boolean;
  onInstructionChange: (instruction: string) => void;
  onSubmit: (instruction: string) => void;
}): ReactNode {
  return (
    <form
      className={styles.composer}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(instruction);
      }}
    >
      <div className={styles.entry}>
        <label className={styles.instruction}>
          <span className="visuallyHidden">What should Claude change?</span>
          <textarea
            className={styles.field}
            value={instruction}
            placeholder={INSTRUCTION_PLACEHOLDER}
            onChange={(event) => onInstructionChange(event.target.value)}
          />
        </label>
        {instructionMissing ? <p className={styles.note}>{EMPTY_INSTRUCTION_MESSAGE}</p> : null}
        <div className={styles.actions}>
          <Button
            variant={ButtonVariant.Primary}
            tone={ButtonTone.Default}
            label="Suggest redlines"
            shortcut="⌘ Enter"
            disabled={false}
            onClick={() => onSubmit(instruction)}
          />
        </div>
      </div>
      <div className={styles.presets}>
        {PRESET_INSTRUCTIONS.map((preset) => (
          <button
            key={preset}
            type="button"
            className={styles.preset}
            onClick={() => onSubmit(preset)}
          >
            {preset}
          </button>
        ))}
      </div>
    </form>
  );
}
