import { useEffect } from "react";

export interface ShortcutBinding {
  key: string;
  modifiers: string[];
  handler: () => void;
  allowInTextField: boolean;
}

const TEXT_FIELD_TAGS = ["input", "textarea"];

/**
 * Run keyboard bindings while this component is mounted.
 * @param bindings - The shortcuts to listen for.
 * @throws Does not throw.
 */
export function useKeyboardShortcuts(bindings: ShortcutBinding[]): void {
  useEffect(() => {
    /**
     * Run the binding that matches this key, if one does.
     * @param event - The key event.
     * @throws Does not throw.
     */
    function onKeyDown(event: KeyboardEvent): void {
      const binding = bindings.find((candidate) => matchesBinding(event, candidate));
      if (binding === undefined) {
        return;
      }
      event.preventDefault();
      binding.handler();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [bindings]);
}

/**
 * Return whether the event matches one binding.
 * @param event - The key event.
 * @param binding - The shortcut.
 * @returns Whether the handler should run.
 * @throws Does not throw.
 */
function matchesBinding(event: KeyboardEvent, binding: ShortcutBinding): boolean {
  if (event.key.toLowerCase() !== binding.key.toLowerCase()) {
    return false;
  }
  if (!modifiersMatch(event, binding.modifiers)) {
    return false;
  }
  return binding.allowInTextField || !focusIsInTextField(event.target);
}

/**
 * Return whether the event has exactly the requested modifier keys.
 * @param event - The key event.
 * @param modifiers - The modifier names: meta, ctrl, shift, or alt.
 * @returns Whether the modifiers match.
 * @throws Does not throw.
 */
function modifiersMatch(event: KeyboardEvent, modifiers: string[]): boolean {
  const expected = new Set(modifiers.map((modifier) => modifier.toLowerCase()));
  const pressed = new Set<string>();
  if (event.metaKey) {
    pressed.add("meta");
  }
  if (event.ctrlKey) {
    pressed.add("ctrl");
  }
  if (event.shiftKey) {
    pressed.add("shift");
  }
  if (event.altKey) {
    pressed.add("alt");
  }
  if (pressed.size !== expected.size) {
    return false;
  }
  for (const modifier of pressed) {
    if (!expected.has(modifier)) {
      return false;
    }
  }
  return true;
}

/**
 * Return whether the event target is a field the user is typing in.
 * @param target - The event target.
 * @returns Whether shortcuts should stay quiet.
 * @throws Does not throw.
 */
function focusIsInTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  return TEXT_FIELD_TAGS.includes(target.tagName.toLowerCase());
}
