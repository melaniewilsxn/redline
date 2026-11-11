import mammoth from "mammoth";

export const ImportType = {
  Docx: "docx",
  Text: "text",
  Unsupported: "unsupported",
} as const;
export type ImportType = (typeof ImportType)[keyof typeof ImportType];

export const ImportProblem = {
  Unsupported: "unsupported",
  Empty: "empty",
  Unreadable: "unreadable",
  TooLarge: "tooLarge",
} as const;
export type ImportProblem = (typeof ImportProblem)[keyof typeof ImportProblem];

const MAXIMUM_CONTRACT_BYTES = 10 * 1024 * 1024;
const DOCX_EXTENSION = ".docx";
const TEXT_EXTENSION = ".txt";
const WINDOWS_LINE_ENDING = /\r\n/g;
const CARRIAGE_RETURN = /\r/g;
const LINE_TRAILING_SPACE = /[ \t]+$/gm;
const EXTRA_BLANK_LINES = /\n{3,}/g;
const UNSUPPORTED_FILE_MESSAGE = "Choose a .docx or .txt file";
const EMPTY_TEXT_MESSAGE = "That file has no text we can read";
const UNREADABLE_WORD_MESSAGE =
  "Couldn't read that Word file. Try saving it as .docx again, or paste the text";
const TOO_LARGE_MESSAGE = "Contracts over 10MB aren't supported yet";

/**
 * A contract file Redline cannot use.
 * @throws Does not throw.
 */
export class ImportError extends Error {
  readonly problem: ImportProblem;

  /**
   * Store which import problem this is.
   * @param problem - Why the text cannot be used.
   */
  constructor(problem: ImportProblem) {
    super(importProblemMessage(problem));
    this.name = "ImportError";
    this.problem = problem;
  }
}

/**
 * Decide how a file should be read, from its extension.
 * @param fileName - The file's name, including the extension.
 * @returns The import type.
 * @throws Does not throw.
 */
export function getImportType(fileName: string): ImportType {
  const lowerName = fileName.toLowerCase();
  const dot = lowerName.lastIndexOf(".");
  if (dot === -1) {
    return ImportType.Unsupported;
  }
  const extension = lowerName.slice(dot);
  if (extension === DOCX_EXTENSION) {
    return ImportType.Docx;
  }
  if (extension === TEXT_EXTENSION) {
    return ImportType.Text;
  }
  return ImportType.Unsupported;
}

/**
 * Read a .txt or .docx file into contract text.
 * @param file - The file the reviewer chose.
 * @returns The normalized contract text.
 * @throws {ImportError} When the file cannot be used.
 */
export async function readContractText(file: File): Promise<string> {
  const importType = getImportType(file.name);
  if (importType === ImportType.Unsupported) {
    throw new ImportError(ImportProblem.Unsupported);
  }
  if (file.size > MAXIMUM_CONTRACT_BYTES) {
    throw new ImportError(ImportProblem.TooLarge);
  }
  const rawText = importType === ImportType.Docx ? await readDocxText(file) : await file.text();
  return prepareContractText(rawText);
}

/**
 * Normalize pasted or extracted text and refuse an empty or oversized result.
 * @param text - The text before it is stored.
 * @returns The contract text.
 * @throws {ImportError} When the text is empty or over 10MB.
 */
export function prepareContractText(text: string): string {
  if (new TextEncoder().encode(text).length > MAXIMUM_CONTRACT_BYTES) {
    throw new ImportError(ImportProblem.TooLarge);
  }
  const normalized = normalizeContractText(text);
  if (normalized === "") {
    throw new ImportError(ImportProblem.Empty);
  }
  return normalized;
}

/**
 * Make contract text use one blank line between paragraphs.
 * @param text - The text as it was read.
 * @returns The text with Unix line endings and one blank line at most.
 * @throws Does not throw.
 */
export function normalizeContractText(text: string): string {
  const unix = text.replace(WINDOWS_LINE_ENDING, "\n").replace(CARRIAGE_RETURN, "\n");
  const trimmedLines = unix.replace(LINE_TRAILING_SPACE, "");
  return trimmedLines.replace(EXTRA_BLANK_LINES, "\n\n").trim();
}

/**
 * Read the words out of a Word file.
 * @param file - A .docx file.
 * @returns The raw text mammoth extracted.
 * @throws {ImportError} When mammoth cannot read the file.
 */
async function readDocxText(file: File): Promise<string> {
  try {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText(openDocx(arrayBuffer));
    return result.value;
  } catch (error) {
    if (error instanceof ImportError) {
      throw error;
    }
    throw new ImportError(ImportProblem.Unreadable);
  }
}

/**
 * Point mammoth at a docx buffer in either the browser or the test runner.
 * @param arrayBuffer - The docx bytes.
 * @returns The input mammoth reads.
 * @throws Does not throw.
 */
function openDocx(arrayBuffer: ArrayBuffer): { arrayBuffer: ArrayBuffer; buffer: ArrayBuffer } {
  return { arrayBuffer, buffer: arrayBuffer };
}

/**
 * The sentence shown for an import problem.
 * @param problem - Why the text cannot be used.
 * @returns The message.
 * @throws Does not throw.
 */
function importProblemMessage(problem: ImportProblem): string {
  switch (problem) {
    case ImportProblem.Unsupported:
      return UNSUPPORTED_FILE_MESSAGE;
    case ImportProblem.Empty:
      return EMPTY_TEXT_MESSAGE;
    case ImportProblem.Unreadable:
      return UNREADABLE_WORD_MESSAGE;
    case ImportProblem.TooLarge:
      return TOO_LARGE_MESSAGE;
  }
}
