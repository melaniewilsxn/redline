import mammoth from "mammoth";
import { describe, expect, it } from "vitest";

import { buildDocxBlob, buildDownloadFileName } from "./contract_export.ts";

const LONG_NUMBERED_PARAGRAPH =
  "1. The parties agree that this sentence is ordinary contract text and is longer than a heading.";

describe("contract export", () => {
  it("builds a file name with the version and no unsafe characters", () => {
    expect(buildDownloadFileName('Vendor: "draft"', 2, "docx")).toBe("Vendor draft v2.docx");
  });

  it("builds a docx with one heading per numbered section", async () => {
    const blob = await buildDocxBlob(
      "Services agreement",
      `1. Parties\n\nThe parties agree.\n\n2. Term\n\n${LONG_NUMBERED_PARAGRAPH}`,
    );
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const html = await mammoth.convertToHtml({
      arrayBuffer: bytes.buffer,
      buffer: Buffer.from(bytes),
    });
    const headings = html.value.match(/<h[1-6]>/g);

    expect(headings).toHaveLength(2);
    expect(html.value).toContain("Services agreement");
    expect(html.value).toContain(LONG_NUMBERED_PARAGRAPH);
    expect(html.value).not.toContain(`<h2>${LONG_NUMBERED_PARAGRAPH}`);
  });
});
