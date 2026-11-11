import { Document, HeadingLevel, Packer, Paragraph } from "docx";

import { getParagraphTexts, isHeading } from "../redline/document_segments.ts";

const UNSAFE_FILE_NAME_CHARACTERS = '\\/:*?"<>|';
const FIRST_PRINTABLE_CHARACTER = 32;
const TEXT_FILE_TYPE = "text/plain;charset=utf-8";

/**
 * Build a Word file whose headings match the ones on screen.
 * @param title - The contract title.
 * @param text - The saved contract text.
 * @returns The .docx file.
 * @throws Does not throw.
 */
export async function buildDocxBlob(title: string, text: string): Promise<Blob> {
  const paragraphs = [
    new Paragraph({ text: title, heading: HeadingLevel.TITLE }),
    ...getParagraphTexts(text).map((paragraph) => paragraphForExport(paragraph)),
  ];
  const document = new Document({ sections: [{ children: paragraphs }] });
  return Packer.toBlob(document);
}

/**
 * Build a plain-text file of the saved contract.
 * @param text - The saved contract text.
 * @returns The .txt file.
 * @throws Does not throw.
 */
export function buildTextBlob(text: string): Blob {
  return new Blob([text], { type: TEXT_FILE_TYPE });
}

/**
 * Name a download after the contract and its version.
 * @param title - The contract title.
 * @param version - The saved version.
 * @param extension - The file extension, without a dot.
 * @returns A file name that is safe to save.
 * @throws Does not throw.
 */
export function buildDownloadFileName(title: string, version: number, extension: string): string {
  const safeTitle = getSafeFileTitle(title);
  return `${safeTitle} v${version}.${extension}`;
}

/**
 * Save a file in the browser.
 * @param blob - The file contents.
 * @param fileName - The name to save it as.
 * @throws Does not throw.
 */
export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Turn a title into words a file name can use.
 * @param title - The contract title.
 * @returns The title with unsafe characters replaced by spaces.
 * @throws Does not throw.
 */
function getSafeFileTitle(title: string): string {
  let safeTitle = "";
  for (const character of title) {
    const code = character.codePointAt(0);
    if (
      code === undefined ||
      code < FIRST_PRINTABLE_CHARACTER ||
      UNSAFE_FILE_NAME_CHARACTERS.includes(character)
    ) {
      safeTitle += " ";
      continue;
    }
    safeTitle += character;
  }
  return safeTitle.replace(/\s+/g, " ").trim();
}

/**
 * One exported paragraph, headed when the screen would head it.
 * @param paragraph - The paragraph text.
 * @returns The Word paragraph.
 * @throws Does not throw.
 */
function paragraphForExport(paragraph: string): Paragraph {
  if (isHeading(paragraph)) {
    return new Paragraph({ text: paragraph, heading: HeadingLevel.HEADING_2 });
  }
  return new Paragraph({ text: paragraph });
}
