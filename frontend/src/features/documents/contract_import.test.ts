import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ImportError,
  ImportProblem,
  ImportType,
  getImportType,
  prepareContractText,
  readContractText,
} from "./contract_import.ts";

const FIXTURE_PATH = resolve("src/test_fixtures/two_sections.docx");
const TEN_MEGABYTES = 10 * 1024 * 1024;

/**
 * A file the browser would hand the import.
 * @param name - The file name.
 * @param contents - The file bytes.
 * @returns The file.
 * @throws Does not throw.
 */
function buildContractFile(name: string, contents: Uint8Array): File {
  const bytes = Uint8Array.from(contents);
  return new File([bytes], name);
}

describe("contract import", () => {
  it("detects docx and txt no matter the letter case", () => {
    expect(getImportType("Vendor.DOCX")).toBe(ImportType.Docx);
    expect(getImportType("notes.Txt")).toBe(ImportType.Text);
  });

  it("marks other extensions unsupported", () => {
    expect(getImportType("scan.pdf")).toBe(ImportType.Unsupported);
    expect(getImportType("notes")).toBe(ImportType.Unsupported);
  });

  it("turns Windows line endings into Unix ones and keeps a normal blank line", () => {
    expect(prepareContractText("1. Term\r\n\r\n\r\nOne year.\n\nSigned.\r\n")).toBe(
      "1. Term\n\nOne year.\n\nSigned.",
    );
  });

  it("reads the two-section fixture", async () => {
    const bytes = new Uint8Array(readFileSync(FIXTURE_PATH));
    const text = await readContractText(buildContractFile("two_sections.docx", bytes));

    expect(text).toContain("1. Parties");
    expect(text).toContain("2. Term");
  });

  it("refuses pasted text over 10MB and accepts text within 10MB", () => {
    const withinLimit = "a".repeat(TEN_MEGABYTES - 1);
    expect(prepareContractText(withinLimit)).toBe(withinLimit);

    let caught: unknown = null;
    try {
      prepareContractText("a".repeat(TEN_MEGABYTES + 1));
    } catch (error) {
      caught = error;
    }
    expect(caught).toBeInstanceOf(ImportError);
    if (!(caught instanceof ImportError)) {
      return;
    }
    expect(caught.problem).toBe(ImportProblem.TooLarge);
  });
});
