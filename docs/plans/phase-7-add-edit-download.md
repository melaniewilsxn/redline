# Phase 7: Add Contracts and Download

**Project:** Redline (see `docs/plans/build-plan.md`)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed. Check each library's current docs before using it, and pin exact versions. Use the frontend conventions already in the code: constant-object enums, CSS Modules, JSDoc with `@throws`, no inline `style` props. Leave `docs/infra.md` alone.

## Goal

Make a whole negotiation round demoable in the UI:
1. bring in the other side's draft;
2. review it with Claude;
3. apply your decisions as the next version;
4. download that version to send back.

**This phase is frontend only.** It uses the existing `POST /documents`, `PATCH /documents/{id}`, and `GET /documents/{id}`.

**Out of scope, recorded as next steps in the README:**
- typing your own edits in the browser;
- keeping Word formatting;
- PDF import;
- a Word add-in.

## Files

```
frontend/
├── package.json                                  # mammoth, docx (section 1)
└── src/
    ├── api/endpoints.ts                          # createDocument (section 2)
    ├── test_fixtures/two_sections.docx           # section 5 (new)
    ├── features/
    │   ├── documents/
    │   │   ├── new_contract_panel.tsx / .module.css   # section 2 (new)
    │   │   ├── contract_import.ts                     # section 2 (new)
    │   │   ├── contract_import.test.ts                # section 5 (new)
    │   │   ├── contract_export.ts                     # section 3 (new)
    │   │   ├── contract_export.test.ts                # section 5 (new)
    │   │   └── document_list.tsx                      # New contract button
    │   └── redline/document_view.tsx                  # Download menu
    └── review_flow.test.tsx                      # section 5
```

## 1. Libraries

- **`mammoth`** reads `.docx` in the browser: `mammoth.extractRawText({ arrayBuffer })` returns paragraphs separated by blank lines. Check its current browser import path.
- **`docx`** writes `.docx`: `Document`, `Paragraph`, `HeadingLevel`, and `Packer.toBlob`.

Pin both exactly. Both are established libraries for solved problems, so don't hand-roll either format.

## 2. Add a contract

- **`createDocument(title, text)`** in `api/endpoints.ts` calls `POST /documents` with `author: REVIEWER_NAME`, and returns the document and its ETag.
- **New contract button** at the top of the document list (secondary, `+` icon, "New contract"). It replaces the document list with `NewContractPanel` until the contract is saved or cancelled.
- **`NewContractPanel`:**
  - a drop zone that also opens a file picker: "Drop a .docx or .txt file, or choose one";
  - **or** a "Paste text instead" link that shows a textarea;
  - a **Title** field, filled from the file name without its extension when a file is chosen, and editable;
  - **Add contract** (primary) and **Cancel**.

  While a file is read, show "Reading {file name}…". After reading, show the character count and the first two paragraphs as a preview, so you can see it came out right.
- **`contract_import.ts`**, pure where possible:
  - `getImportType(fileName)` returns the `ImportType` constant (`Docx`, `Text`, or `Unsupported`) from the extension, case-insensitive.
  - `readContractText(file)` reads `.txt` as UTF-8, and `.docx` through mammoth.
  - `normalizeContractText(text)` converts `\r\n` to `\n`, trims trailing spaces on each line, collapses runs of three or more newlines to one blank line, and trims the ends. Sections then split on blank lines, and `^\d+\.` headings work.
- **Errors:**
  - unsupported type: "Choose a .docx or .txt file";
  - empty result: "That file has no text we can read";
  - mammoth failure: "Couldn't read that Word file. Try saving it as .docx again, or paste the text";
  - no title: "Add a title";
  - an API failure: the existing messages;
  - a file over 10MB is refused before reading: "Contracts over 10MB aren't supported yet".
- **On success:** refresh the document list, open the new contract, and show the toast "Added {title}".
- **10MB cap:** applies to pasted text as well as files, with the same message.
- **Button placement:** the New contract button sits above the list area, so it stays visible in the empty state and while search results show.

### Upload the next draft

When the other side replies, their draft becomes the **next version of the same contract**, which is what version history is for.
- An **Upload next draft** button in the document header (secondary, next to Download) opens the same import panel, in a "next draft" mode: no title field, and the button reads **Save as version {n + 1}**.
- Saving sends one `PATCH` whose single change is a `RangeTarget` covering the whole saved text (`start: 0`, `end: text.length`), with the new text as the replacement, `If-Match` set to the document's current ETag, and `author: REVIEWER_NAME`. No new endpoint is needed.
- An identical draft ("This draft matches the saved version") is refused before sending. A 412 shows the existing stale banner.
- It's not allowed while a review has unapplied accepted changes. Show the note "Apply or discard your review before uploading the next draft."
- On success: refetch, clear any search highlights, and show the toast "Saved their draft as version {n}."
- `createDocument` and this upload share `readContractText` and `normalizeContractText`. The panel component takes a `NewContractMode` constant (`NewContract`, `NextDraft`) rather than a boolean.

## 3. Download

- **A Download button** in the document header opens a two-item menu: "Word document (.docx)" and "Plain text (.txt)".
- **`contract_export.ts`:**
  - `buildDocxBlob(title, text)`: the title as `HeadingLevel.TITLE`, each heading paragraph as `HEADING_2`, and every other paragraph as a normal paragraph, then `Packer.toBlob`. Headings use the **same rule as the screen**, shared from `document_segments.ts` (a numbered line under 80 characters with words after the number), not a bare `^\d+\.` pattern;
  - `buildTextBlob(text)`: a UTF-8 text blob;
  - `buildDownloadFileName(title, version, extension)`: `"{Title} v{version}.{ext}"`, with characters not allowed in file names replaced by spaces.
- **It downloads the saved current version,** not unapplied review decisions. Only when at least one suggestion is accepted and not yet applied, the menu shows the note "Downloads the saved version. Apply your changes first to include them." A review with nothing accepted shows no note, because the saved text is what you'd want.
- The Download button sits with the title in the header, not in the find row, so the find field doesn't move.

## 4. README

- **"How it fits a negotiation"** goes near the top: one short paragraph and four steps.
  1. The other side's draft comes in as a new contract (version 1).
  2. You review it with Claude, accepting and rejecting suggestions.
  3. You apply your decisions as the next version and download it to send back.
  4. When their reply comes back, **Upload next draft** saves it as the next version of the same contract, and the cycle repeats.
- **Review UI:** add adding a contract (.docx, .txt, or paste) and downloading.
- **A "Why plain text" paragraph** in API design: every feature depends on exact character offsets (edit targets, versioned writes, search highlights, anchoring AI suggestions), so documents are plain text by design. Rich formatting needs a document model where a position is no longer a character offset.
- **Next steps:** add a **"Meet lawyers in Word"** item at the top. Lawyers live in Microsoft Word, so the production client is a Word add-in (Office.js) calling this same API:
  - Claude's suggestions appear as native Word tracked changes, with the rationale as comments;
  - search and the review panel live in Word's task pane;
  - formatting stays untouched, because the add-in maps character ranges onto Word's own ranges.

  The engine, versioning, search, and AI anchoring all carry over unchanged. Also list:
  - your own edits as tracked changes in the web UI, staged next to Claude's and applied as one version;
  - keeping formatting on import and export;
  - PDF import;
  - a blackline compare between versions, showing what the other side changed in their draft.

  Rewrite the existing next step that calls ".docx import and export" future work, so it doesn't contradict this phase. What remains future is **keeping formatting**.
- **Screenshots:** add `new_contract.png` (the panel with a .docx preview).

## 5. Tests

`contract_import.test.ts`:
- `detects docx and txt extensions case-insensitively`
- `marks other extensions unsupported`
- `normalizes Windows line endings and extra blank lines`
- `reads a small docx fixture into paragraphs` (a tiny committed `src/test_fixtures/two_sections.docx` with two numbered sections; generate it once with the `docx` library)

`contract_export.test.ts`:
- `builds a file name with the version and no unsafe characters`
- `builds a docx with one heading for each numbered section` (read it back with mammoth's HTML conversion and count heading tags; `extractRawText` drops heading styles, so it can't prove them)

`review_flow.test.tsx`:
- `reviewer adds a contract from pasted text and it opens`
- `download menu notes unapplied accepted changes`, and `download menu shows no note when nothing is accepted or no review is open`
- `uploading the next draft sends one whole-document range change with If-Match`
- `uploading an identical draft is refused`

In `contract_import.test.ts` also:
- `refuses pasted text over 10MB`

## Checkpoints ✅

Stop at each checkpoint and report before going on. Take screenshots in a visible browser.

1. **Add a contract.** Generate a `.docx` from the SaaS sample contract's text with the `docx` library (a real contract, so the playbook has something to find), then import it, plus a `.txt` and a paste. Report screenshots of the panel with a preview, and the new contract open. Run "Review against our playbook" on the imported `.docx`, and report the suggestion count. Keep the two-section fixture only for the unit test.
2. **Next draft.** On that imported contract, upload a modified copy as the next draft. Report the new version number and the versions list (`GET /documents/{id}/versions`).
3. **Download.** Download a version as `.docx` and open it. Report that the title and section headings came through, and the file names.
4. **Final.** `make ui-lint`, `make ui-test`, `make lint`, and `make test` totals; `make reseed` (the import leaves extra contracts behind); README updates and screenshots; commit and push.

## Definition of done

- [ ] You can add a contract from `.docx`, `.txt`, or pasted text, with a preview and plain error messages.
- [ ] You can upload the other side's next draft as the next version of the same contract.
- [ ] You can download the saved version as `.docx` or `.txt`.
- [ ] The README tells the negotiation story, explains why the text is plain, and lists the Word add-in as the lead next step.
- [ ] Every test named in section 5 passes, lint is clean, the sample data is reseeded, and it's pushed.
