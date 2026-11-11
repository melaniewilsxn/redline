# Phase 7: Add Contracts, Edit as Tracked Changes, Download

**Project:** Redline (see `docs/plans/build-plan.md`)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed. Check each library's current docs before using it, and pin exact versions. Use the frontend conventions already in the code: constant-object enums, CSS Modules, JSDoc with `@throws`, no inline `style` props. Leave `docs/infra.md` alone.

## Goal

Make the whole negotiation round work in the UI:
1. bring in the other side's draft;
2. mark it up with your own edits and Claude's suggestions;
3. apply one new version;
4. download it to send back.

**This phase is frontend only.** Everything it needs already exists in the API: `POST /documents`, `PATCH /documents/{id}` with range targets and `If-Match`, and `GET /documents/{id}`.

**Out of scope:** keeping Word formatting (documents stay plain text), PDF import, rich text editing, and comparing versions.

## Files

```
frontend/
├── package.json                                  # mammoth, docx (section 1)
└── src/
    ├── api/endpoints.ts                          # createDocument (section 2)
    ├── features/
    │   ├── documents/
    │   │   ├── new_contract_panel.tsx / .module.css   # section 2 (new)
    │   │   ├── contract_import.ts                     # section 2 (new)
    │   │   ├── contract_import.test.ts                # section 6 (new)
    │   │   ├── contract_export.ts                     # section 4 (new)
    │   │   ├── contract_export.test.ts                # section 6 (new)
    │   │   └── document_list.tsx                      # New contract button
    │   └── redline/
    │       ├── paragraph_edit.ts                      # section 3 (new)
    │       ├── paragraph_edit.test.ts                 # section 6 (new)
    │       ├── paragraph_editor.tsx / .module.css     # section 3 (new)
    │       ├── review_state.ts                        # section 3
    │       ├── review_state.test.ts                   # section 6
    │       ├── document_segments.ts                   # source on suggestions
    │       ├── document_view.tsx                      # editing, Download menu
    │       ├── suggestion_card.tsx                    # "You" cards
    │       └── changes_panel.tsx                      # review without AI
    ├── hooks/use_keyboard_shortcuts.ts           # E binding
    └── review_flow.test.tsx                      # section 6
```

## 1. Libraries

- **`mammoth`** reads `.docx` files in the browser. Use `mammoth.extractRawText({ arrayBuffer })`, which returns paragraphs separated by blank lines. Check its current browser import path and version.
- **`docx`** writes `.docx` files: `Document`, `Paragraph`, `HeadingLevel`, and `Packer.toBlob`.

Pin both exactly. Both are established libraries for solved problems; don't hand-roll either format.

## 2. Add a contract

- **`createDocument(title, text)`** in `api/endpoints.ts` calls `POST /documents` with `author: REVIEWER_NAME`. It returns the document and its ETag.
- **New contract button:** at the top of the document list (secondary button, `+` icon, label "New contract"). It replaces the document list with `NewContractPanel` until saved or cancelled.
- **`NewContractPanel`:**
  - a drop zone that also opens a file picker, with the label "Drop a .docx or .txt file, or choose one";
  - **or** a "Paste text instead" link that shows a textarea;
  - a **Title** field. When a file is chosen, it's filled from the file name without its extension; you can edit it.
  - **Add contract** (primary) and **Cancel**.

  While a file is read, show "Reading {file name}…". After reading, show the character count and the first two paragraphs as a preview, so you can see it came out right.
- **`contract_import.ts`**, pure where possible:
  - `getImportType(fileName)` returns the `ImportType` constant (`Docx`, `Text`, or `Unsupported`) from the extension, case-insensitive.
  - `readContractText(file)` reads `.txt` as UTF-8, and `.docx` through mammoth.
  - `normalizeContractText(text)` converts `\r\n` to `\n`, trims trailing spaces on each line, collapses runs of three or more newlines to one blank line, and trims the ends. This keeps the paragraph rules working (sections split on blank lines, and `^\d+\.` headings).
- **Errors:**
  - an unsupported type: "Choose a .docx or .txt file";
  - an empty result: "That file has no text we can read";
  - mammoth failing: "Couldn't read that Word file. Try saving it as .docx again, or paste the text";
  - a title missing: "Add a title";
  - the API failing: the existing error messages.

  A file over 10MB shows "Contracts over 10MB aren't supported yet" before reading.
- **On success:** refresh the document list, open the new contract, and show the toast "Added {title}".

## 3. Your own edits as tracked changes

### Model

- Add `source: SuggestionSource` to `ReviewSuggestion`, where `SuggestionSource = { Ai: "ai", Reviewer: "reviewer" }`. AI suggestions get `Ai` in `toReviewSuggestion`.
- **Reviewer edits are created already accepted.** You made them, so you don't accept your own work. They render in the accepted style, with a "You" card. For a reviewer edit, **Undo** removes the edit entirely; it doesn't return to pending.
- **A review can start without AI.** The first edit, when no review exists, starts one with the document's current ETag, no suggestions, and no dropped list. The apply bar appears as soon as there's anything to apply.

### `paragraph_edit.ts` (pure)

`buildParagraphEdit(paragraphStart, originalText, editedText, editId)` returns a reviewer `ReviewSuggestion`, or `null` when nothing changed.

It trims the common prefix and the common suffix between the original and edited paragraph, then snaps both cuts outward to word boundaries. The edit is exactly the changed middle: `start = paragraphStart + prefixLength`, `end = paragraphStart + originalText.length - suffixLength`, and `replacement` is the edited middle. A tracked edit is then as small as what you actually changed, and the word-level rendering from Phase 6 shows it cleanly.

The title is "Your edit", and the rationale is empty (the card shows no rationale line). The id is `you-{n}`.

### Editing rules

- **Open the editor** by double-clicking a paragraph, or pressing `E` on the paragraph holding the active suggestion or the last clicked paragraph. Headings are editable too.
- **`ParagraphEditor`:** a textarea in the document's serif font, sized to its content, replacing the paragraph in place. **Save** (⌘/Ctrl+Enter) and **Cancel** (Esc), with keyboard hints. Review shortcuts (`A`, `R`, `J`, `K`, `U`, `E`) are ignored while it has focus. That already works for text fields.
- **A paragraph with any AI suggestion can't be edited.** Opening it shows the inline note "Accept or reject the suggestions here, then apply, before editing this paragraph." AI suggestions point at the saved text, so editing under them would put them in the wrong place.
- **Editing a paragraph that already has your edit** opens the editor on your edited text. Saving rebuilds the edit against the **original** paragraph text, replacing the old one. Saving it back to the original removes the edit.
- **One reviewer edit per paragraph,** which the rebuild rule guarantees.

### Reducer (`review_state.ts`)

New actions:
- `reviewStarted` (`documentId`, `etag`);
- `editSaved` (an edit from `buildParagraphEdit`; it replaces any reviewer edit with the same paragraph start, or is added in document order);
- `editRemoved` (`suggestionId`).

`undone` on a reviewer edit dispatches the same removal. `loaded`, when AI suggestions arrive while reviewer edits exist, keeps the reviewer edits and drops any AI suggestion that overlaps one. A dropped one goes into `dropped` with the client-side reason `overlaps_your_edit` ("Overlaps your edit"). This needs a matching `DroppedSuggestionReason` constant in the UI only, so define it in `review_state.ts`. `getAcceptedChanges` already includes every accepted suggestion, so reviewer edits apply with no change.

Asking Claude for suggestions while you have unapplied edits is allowed. The AI sees the saved text, and the suggestions anchor to it.

## 4. Download

- **In the document header:** a **Download** button opening a two-item menu, "Word document (.docx)" and "Plain text (.txt)".
- **`contract_export.ts`:**
  - `buildDocxBlob(title, text)` creates a `docx` document with the title as `HeadingLevel.TITLE`, each heading paragraph (the existing heading rule) as `HEADING_2`, and each other paragraph as a normal paragraph, then `Packer.toBlob`.
  - `buildTextBlob(text)` returns a UTF-8 text blob.
  - `buildDownloadFileName(title, version, extension)` builds `"{Title} v{version}.{ext}"`, replacing characters not allowed in file names with spaces.
- **What gets downloaded:** the **saved current version**, not unapplied review changes. If a review has unapplied changes, the menu shows a one-line note: "Downloads the saved version. Apply your changes first to include them."

## 5. README

- **A new section at the top, "How it fits a negotiation":**
  - the other side's draft comes in as a new contract (version 1);
  - you mark it up with your own tracked edits and Claude's suggestions;
  - you apply them as the next version, download it, and send it back;
  - their next draft becomes the next version.

  Keep it to one short paragraph and a 4-step list.
- **Review UI:** describe adding a contract (.docx, .txt, or paste), editing (double-click or `E`), and downloading. Add `E` to the shortcuts table.
- **Next steps:** keep Word formatting on import and export, compare two versions as a blackline, and show the other side's changes when their next draft comes in.
- **Screenshots:** add `new_contract.png` (the panel with a .docx preview) and `your_edit.png` (a reviewer edit next to AI suggestions, light), and re-take `review_light.png` if the cards changed.

## 6. Tests

### `contract_import.test.ts`

- `detects docx and txt extensions case-insensitively`
- `marks other extensions unsupported`
- `normalizes Windows line endings and extra blank lines`
- `reads a small docx fixture into paragraphs` (commit a tiny `.docx` fixture with two numbered sections under `src/test_fixtures/`)

### `paragraph_edit.test.ts`

- `returns null when the paragraph is unchanged`
- `trims the shared prefix and suffix to the changed words`
- `snaps cuts to word boundaries`
- `handles an edit at the start and at the end of the paragraph`
- `offsets the edit by the paragraph start`

### `review_state.test.ts`

- `reviewStarted creates an empty review with the document's ETag`
- `editSaved adds an accepted reviewer edit`
- `editSaved replaces the earlier edit in the same paragraph`
- `undone on a reviewer edit removes it`
- `loaded keeps reviewer edits and drops AI suggestions that overlap them`
- `getAcceptedChanges includes reviewer edits and accepted AI suggestions together`

### `contract_export.test.ts`

- `builds a file name with the version and no unsafe characters`
- `builds a docx blob with one heading for each numbered section` (unzip with the `docx` package's own reader, or JSZip if that's what it bundles, and count the heading paragraphs)

### `review_flow.test.tsx`

- `reviewer adds a contract from pasted text and it opens`
- `reviewer edits a paragraph and applies it as a new version`: double-click, change one word, ⌘Enter, Apply. Assert the `PATCH` body holds one range change covering just that word.
- `editing a paragraph with an AI suggestion shows the note instead of the editor`

## Checkpoints ✅

Stop at each checkpoint and report before going on. Take screenshots in a visible browser.

1. **Add a contract.** Import a real `.docx` (write a short two-section one in Word or Pages, or generate one with the `docx` library) and a `.txt`, plus a paste. Report screenshots of the panel with a preview, and the new contract open.
2. **Edit as tracked changes.** On a freshly reseeded MSA:
   - make two edits of your own, then run "Make the indemnification mutual";
   - accept one AI suggestion and reject one;
   - apply, and check the new version holds both your edits and the accepted suggestion.

   Report the `PATCH` body (offsets and replacements only, no full text) and screenshots of the mixed review.
3. **Download.** Download the new version as `.docx` and open it. Report that its title and section headings came through, and the file names.
4. **Final.** `make ui-lint`, `make ui-test`, `make lint`, and `make test` totals; `make reseed`; the README updates and screenshots; commit and push.

## Definition of done

- [ ] You can add a contract from `.docx`, `.txt`, or pasted text, with a preview and plain error messages.
- [ ] You can edit any paragraph without AI suggestions. Edits appear as tracked changes with "You" cards, and apply together with accepted AI suggestions as one version.
- [ ] You can download the saved version as `.docx` or `.txt`.
- [ ] The README tells the negotiation story, and the new screenshots are in.
- [ ] Every test named in section 6 exists and passes, all lint is clean, and it's pushed.
