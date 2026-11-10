import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { useKeyboardShortcuts, type ShortcutBinding } from "./use_keyboard_shortcuts.ts";

/**
 * Mount one binding.
 * @param binding - The shortcut under test.
 * @returns Nothing.
 * @throws Does not throw.
 */
function ShortcutHost({ binding }: { binding: ShortcutBinding }): null {
  useKeyboardShortcuts([binding]);
  return null;
}

describe("keyboard shortcuts", () => {
  it("calls the handler for a bound key", async () => {
    const handler = vi.fn();
    render(
      <ShortcutHost binding={{ key: "j", modifiers: [], handler, allowInTextField: false }} />,
    );

    await userEvent.keyboard("j");

    expect(handler).toHaveBeenCalledOnce();
  });

  it("ignores a bound key while typing in a text field", async () => {
    const handler = vi.fn();
    const user = userEvent.setup();
    render(
      <>
        <input aria-label="Instruction" />
        <ShortcutHost binding={{ key: "j", modifiers: [], handler, allowInTextField: false }} />
      </>,
    );

    await user.click(screen.getByLabelText("Instruction"));
    await user.keyboard("j");

    expect(handler).not.toHaveBeenCalled();
  });

  it("calls an allowInTextField binding while typing in a text field", async () => {
    const handler = vi.fn();
    const user = userEvent.setup();
    render(
      <>
        <input aria-label="Instruction" />
        <ShortcutHost
          binding={{ key: "Enter", modifiers: ["meta"], handler, allowInTextField: true }}
        />
      </>,
    );

    await user.click(screen.getByLabelText("Instruction"));
    await user.keyboard("{Meta>}{Enter}{/Meta}");

    expect(handler).toHaveBeenCalledOnce();
  });
});
