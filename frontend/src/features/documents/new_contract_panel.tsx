import { useState, type ChangeEvent, type DragEvent, type ReactNode } from "react";

import { ApiError } from "../../api/client.ts";
import { Button, ButtonTone, ButtonVariant } from "../../components/button.tsx";
import { getParagraphTexts } from "../redline/document_segments.ts";
import { ImportError, prepareContractText, readContractText } from "./contract_import.ts";
import styles from "./new_contract_panel.module.css";

export const NewContractMode = {
  NewContract: "newContract",
  NextDraft: "nextDraft",
} as const;
export type NewContractMode = (typeof NewContractMode)[keyof typeof NewContractMode];

const PREVIEW_PARAGRAPH_COUNT = 2;
const EMPTY_TEXT_MESSAGE = "That file has no text we can read";
const MISSING_TITLE_MESSAGE = "Add a title";
const IDENTICAL_DRAFT_MESSAGE = "This draft matches the saved version";
const NETWORK_MESSAGE = "Can't reach the Redline server. Check that it's running.";

/**
 * Bring in a contract file, or the other side's next draft.
 * @param mode - Whether this creates a contract or replaces the open one.
 * @param savedText - The open contract's text, used to refuse an identical draft.
 * @param saveLabel - The words on the save button.
 * @param onCancel - Closes the panel.
 * @param onSaveNewContract - Stores a new contract.
 * @param onSaveNextDraft - Stores the text as the next version.
 * @returns The panel.
 * @throws Does not throw.
 */
export function NewContractPanel({
  mode,
  savedText,
  saveLabel,
  onCancel,
  onSaveNewContract,
  onSaveNextDraft,
}: {
  mode: NewContractMode;
  savedText: string;
  saveLabel: string;
  onCancel: () => void;
  onSaveNewContract: (title: string, text: string) => Promise<void>;
  onSaveNextDraft: (text: string) => Promise<void>;
}): ReactNode {
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [contractText, setContractText] = useState("");
  const [title, setTitle] = useState("");
  const [readingFileName, setReadingFileName] = useState("");
  const [failureMessage, setFailureMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const preview = pasteOpen
    ? getPastedPreview(pasteText)
    : { text: contractText, failureMessage: "" };

  return (
    <div className={styles.panel}>
      {pasteOpen ? (
        <div className={styles.paste}>
          <label className={styles.label}>
            Contract text
            <textarea
              className={styles.textarea}
              value={pasteText}
              onChange={(event) => setPasteText(event.target.value)}
            />
          </label>
          <button type="button" className={styles.link} onClick={() => setPasteOpen(false)}>
            Choose a file instead
          </button>
        </div>
      ) : (
        <div className={styles.file}>
          <label
            className={styles.drop}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              void readDroppedFile(event);
            }}
          >
            Drop a .docx or .txt file, or choose one
            <input
              className="visuallyHidden"
              type="file"
              accept=".docx,.txt,text/plain"
              onChange={(event) => void readChosenFile(event)}
            />
          </label>
          <button type="button" className={styles.link} onClick={() => setPasteOpen(true)}>
            Paste text instead
          </button>
        </div>
      )}
      {readingFileName === "" ? null : <p className={styles.status}>Reading {readingFileName}…</p>}
      {mode === NewContractMode.NewContract ? (
        <label className={styles.label}>
          Title
          <input
            className={styles.title}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
      ) : null}
      {preview.failureMessage === "" && preview.text !== "" ? (
        <div className={styles.preview}>
          <p className={styles.count}>{preview.text.length.toLocaleString()} characters</p>
          {getParagraphTexts(preview.text)
            .slice(0, PREVIEW_PARAGRAPH_COUNT)
            .map((paragraph, index) => (
              <p key={`${index}-${paragraph}`} className={styles.paragraph}>
                {paragraph}
              </p>
            ))}
        </div>
      ) : null}
      {failureMessage === "" && preview.failureMessage === "" ? null : (
        <p className={styles.problem} role="alert">
          {failureMessage === "" ? preview.failureMessage : failureMessage}
        </p>
      )}
      <div className={styles.actions}>
        <Button
          variant={ButtonVariant.Primary}
          tone={ButtonTone.Default}
          label={saveLabel}
          shortcut=""
          disabled={saving || readingFileName !== ""}
          onClick={() =>
            void (mode === NewContractMode.NewContract ? saveNewContract() : saveNextDraft())
          }
        />
        <Button
          variant={ButtonVariant.Secondary}
          tone={ButtonTone.Default}
          label="Cancel"
          shortcut=""
          disabled={saving}
          onClick={onCancel}
        />
      </div>
    </div>
  );

  /**
   * Read the file dropped on the zone.
   * @param event - The drop event.
   * @throws Does not throw.
   */
  async function readDroppedFile(event: DragEvent<HTMLLabelElement>): Promise<void> {
    const file = event.dataTransfer.files[0];
    if (file === undefined) {
      return;
    }
    await readFile(file);
  }

  /**
   * Read the file chosen from the picker.
   * @param event - The file input change.
   * @throws Does not throw.
   */
  async function readChosenFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = event.target.files;
    if (files === null || files.length === 0) {
      return;
    }
    const file = files[0];
    if (file === undefined) {
      return;
    }
    event.target.value = "";
    await readFile(file);
  }

  /**
   * Read one file into the preview.
   * @param file - The file to read.
   * @throws Does not throw.
   */
  async function readFile(file: File): Promise<void> {
    setFailureMessage("");
    setReadingFileName(file.name);
    try {
      const text = await readContractText(file);
      setContractText(text);
      if (mode === NewContractMode.NewContract) {
        setTitle(getTitleFromFileName(file.name));
      }
    } catch (error) {
      setContractText("");
      setFailureMessage(getFailureMessage(error));
    } finally {
      setReadingFileName("");
    }
  }

  /**
   * The text to store, or null when it cannot be stored.
   * @returns The contract text.
   * @throws Does not throw.
   */
  function getTextToSave(): string | null {
    const text = pasteOpen ? preview.text : contractText;
    if (preview.failureMessage !== "") {
      setFailureMessage(preview.failureMessage);
      return null;
    }
    if (text === "") {
      setFailureMessage(EMPTY_TEXT_MESSAGE);
      return null;
    }
    return text;
  }

  /**
   * Store a new contract.
   * @throws Does not throw.
   */
  async function saveNewContract(): Promise<void> {
    const text = getTextToSave();
    if (text === null) {
      return;
    }
    const trimmedTitle = title.trim();
    if (trimmedTitle === "") {
      setFailureMessage(MISSING_TITLE_MESSAGE);
      return;
    }
    setSaving(true);
    setFailureMessage("");
    try {
      await onSaveNewContract(trimmedTitle, text);
    } catch (error) {
      setFailureMessage(getFailureMessage(error));
    } finally {
      setSaving(false);
    }
  }

  /**
   * Store the other side's draft as the next version.
   * @throws Does not throw.
   */
  async function saveNextDraft(): Promise<void> {
    const text = getTextToSave();
    if (text === null) {
      return;
    }
    if (text === savedText) {
      setFailureMessage(IDENTICAL_DRAFT_MESSAGE);
      return;
    }
    setSaving(true);
    setFailureMessage("");
    try {
      await onSaveNextDraft(text);
    } catch (error) {
      setFailureMessage(getFailureMessage(error));
    } finally {
      setSaving(false);
    }
  }
}

interface ContractPreview {
  text: string;
  failureMessage: string;
}

/**
 * The pasted text to preview, or why it cannot be previewed.
 * @param pasteText - The textarea contents.
 * @returns The preview text and any failure message.
 * @throws Does not throw.
 */
function getPastedPreview(pasteText: string): ContractPreview {
  if (pasteText.trim() === "") {
    return { text: "", failureMessage: "" };
  }
  try {
    return { text: prepareContractText(pasteText), failureMessage: "" };
  } catch (error) {
    return { text: "", failureMessage: getFailureMessage(error) };
  }
}

/**
 * The title implied by a file name.
 * @param fileName - The file's name.
 * @returns The name without its extension.
 * @throws Does not throw.
 */
function getTitleFromFileName(fileName: string): string {
  const dot = fileName.lastIndexOf(".");
  if (dot <= 0) {
    return fileName;
  }
  return fileName.slice(0, dot);
}

/**
 * A message safe to show for a failed read or save.
 * @param error - The failure.
 * @returns The message.
 * @throws Does not throw.
 */
function getFailureMessage(error: unknown): string {
  if (error instanceof ImportError || error instanceof ApiError) {
    return error.message;
  }
  return NETWORK_MESSAGE;
}
