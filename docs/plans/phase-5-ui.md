# Phase 5: Review UI

**Project:** Redline (see `docs/plans/build-plan.md`)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed. The JavaScript and frontend rules apply in full: `snake_case` file names, `camelCase` functions, `PascalCase` components, a JSDoc header on every function and component (`@param`, `@returns`, `@throws`, with no types repeated in TypeScript), constants at the top of each file, and **no inline `style` props**. All styling goes in CSS Modules or the global stylesheets.

Check each library's current docs before using it, and pin exact versions in `package.json`. Keep the backend running (`make dev`, on `PORT=8002` if 8000 is taken) while you work. Restart it after `make reseed`, so its search index matches the database.

Do Phase 4's follow-ups first (the section at the end of `phase-4-ai-redline-suggestions.md`: guideline renames, the prompt rule protecting the represented party, and `make reseed`). Report them before checkpoint 1.

## Goal

A review UI that a lawyer would want to use, built and designed in one phase:
1. Open a contract.
2. Ask Claude for redlines, with presets for a playbook review and common asks.
3. See each suggestion as a tracked change in the document, with its reason.
4. Step through the suggestions from the keyboard, accepting or rejecting each.
5. Apply the accepted ones as a new version.

Search works across all contracts or within one, and jumps to the exact match. Light and dark mode both look finished, with a toggle.

The visual direction is **approved**: modern editorial. The section 1 tokens and layout come from the mockup the user signed off on. Build to it; don't reinterpret it.

**Out of scope:** direct text editing in the browser, version history views, stored proposals, version compare, authentication, mobile layouts below 900px wide, virtualized rendering of 10MB documents, and the search mode toggle (an extra only if everything else is done; see the build plan).

## Files

```
redline/
├── Makefile                                  # section 9
├── README.md                                 # section 9
└── frontend/
    ├── package.json                          # section 2
    ├── vite.config.ts                        # section 2
    ├── tsconfig.json                         # section 2
    ├── eslint.config.js                      # section 2 (new)
    ├── .prettierrc.json                      # section 2 (new)
    ├── index.html                            # section 2
    ├── public/theme_boot.js                  # section 7 (new)
    └── src/
        ├── main.tsx                          # section 3
        ├── app.tsx                           # section 3
        ├── app.module.css                    # section 3 (new)
        ├── api/
        │   ├── schema.ts                     # section 4 (new, generated)
        │   ├── types.ts                      # section 4
        │   ├── client.ts                     # section 4
        │   └── endpoints.ts                  # section 4 (new)
        ├── styles/
        │   ├── tokens.css                    # section 1
        │   └── global.css                    # section 1
        ├── hooks/
        │   ├── use_keyboard_shortcuts.ts     # section 7
        │   └── use_theme.ts                  # section 7 (new)
        ├── components/                       # section 8 (delete .gitkeep)
        │   ├── wordmark.tsx / .module.css
        │   ├── button.tsx / .module.css
        │   ├── keyboard_hint.tsx / .module.css
        │   ├── theme_toggle.tsx / .module.css
        │   ├── status_banner.tsx / .module.css
        │   └── toast.tsx / .module.css
        └── features/                         # delete each .gitkeep
            ├── documents/
            │   ├── document_list.tsx / .module.css
            │   └── use_documents.ts
            ├── redline/
            │   ├── document_segments.ts       # section 5
            │   ├── document_segments.test.ts
            │   ├── review_state.ts            # section 6
            │   ├── review_state.test.ts
            │   ├── document_view.tsx / .module.css
            │   ├── changes_panel.tsx / .module.css
            │   ├── suggestion_card.tsx / .module.css
            │   └── apply_bar.tsx / .module.css
            ├── ai_redlines/
            │   ├── redline_composer.tsx / .module.css
            │   ├── dropped_suggestions.tsx / .module.css
            │   └── use_suggest_redlines.ts
            └── search/
                ├── search_box.tsx / .module.css
                ├── search_results.tsx / .module.css
                └── use_search.ts
        └── review_flow.test.tsx               # section 10
```

## 1. Design system (approved)

### Brief

A contract review tool that feels **young, fresh, beautiful, and professional**, not stuffy. The document is the hero, set like a well-made printed draft. The interface around it is quiet, modern, and fast. Color carries meaning only.

**The one memorable thing is the redline itself:** the wordmark ("Red" in ink, "line" in the deletion red) and the moment a change is accepted. Everything else stays disciplined.

### Color tokens (`styles/tokens.css`)

Define the tokens on `:root` for light mode. Redefine them for dark mode under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { ... } }`, and again under `:root[data-theme="dark"]`. Components only use these tokens, never raw hex.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--surface-page` | `#F7F6F3` | `#121317` | app background, rails |
| `--surface-document` | `#FFFFFF` | `#1A1C22` | the document column, cards |
| `--surface-selected` | `#F1EFEA` | `#22252C` | selected list row, active card |
| `--border` | `#E6E3DC` | `#2A2D35` | hairlines |
| `--text` | `#1C1B19` | `#ECEAE5` | body text |
| `--text-muted` | `#6B6860` | `#9A978F` | secondary text, hints |
| `--redline-delete` | `#C4372B` | `#FF8A7A` | deleted text, change bar, wordmark "line" |
| `--redline-delete-bg` | `#FBECEA` | `rgba(255, 138, 122, 0.13)` | behind deleted text |
| `--redline-insert` | `#2F5BD3` | `#8FB0FF` | inserted text |
| `--redline-insert-bg` | `#EAF0FD` | `rgba(143, 176, 255, 0.13)` | behind inserted text |
| `--accept` | `#1F7A5A` | `#5FD3A4` | accept actions, accepted state |
| `--accept-bg` | `#E6F3EC` | `rgba(95, 211, 164, 0.13)` | behind accepted text |
| `--ai` | `#6D5BD0` | `#A99BFF` | the "AI" tag |
| `--ai-bg` | `#EFECFB` | `rgba(169, 155, 255, 0.14)` | behind the "AI" tag |
| `--search-highlight` | `#FCEFC7` | `rgba(250, 199, 117, 0.22)` | search matches (`<mark>`) |
| `--focus-ring` | `#2F5BD3` | `#8FB0FF` | keyboard focus outline |

Check contrast: body text and muted text must reach WCAG AA (4.5:1) on their surfaces in both modes, and redline text on its tint must too. Adjust a value by the smallest step needed, and report any change.

### Type

Load fonts with Fontsource packages (`@fontsource/instrument-sans`, `@fontsource/instrument-serif`, `@fontsource-variable/newsreader`, or the current equivalents), so there are no external font requests.

| Role | Face | Size / line height |
|---|---|---|
| Wordmark | Instrument Serif | 24px |
| Document section headings | Instrument Serif | 22px / 1.3 |
| Document body | Newsreader, optical size on | 17px / 1.72, measure `68ch` max |
| Interface | Instrument Sans 400 and 500 | 13px base / 1.45; 12px secondary; 11px hints |
| Panel headings | Instrument Sans 500 | 14px |

Rules:
- Sentence case everywhere. No all-caps labels, and no eyebrow labels above headings.
- Two interface weights only: 400 and 500.
- Don't join metadata with middle dots. Put each piece in its own element ("Version 2" on one line, "5 suggestions" on the next).

**Section headings in the document:** a paragraph that matches `^\d+(\.\d+)*\.\s+\S` and is under 80 characters (for example, "11. Indemnification") renders as a heading in Instrument Serif. Everything else renders as body text.

### Spacing, radius, and motion tokens

- Spacing: `--space-1` to `--space-8` = 4, 8, 12, 16, 24, 32, 48, 64px.
- Radius depends on hierarchy, not one value everywhere: `--radius-control: 6px` (buttons, inputs, keyboard hints), `--radius-card: 10px` (suggestion cards), `--radius-tag: 999px` (the AI tag). The document column has no radius.
- Motion: `--duration-fast: 140ms`, `--duration-base: 240ms`, `--ease-out: cubic-bezier(0.2, 0.7, 0.2, 1)`. Under `prefers-reduced-motion: reduce`, durations are 0ms.
- No gradients and no decorative shadows. One soft shadow token, `--shadow-popover`, is used only for the toast.

### Layout

```
┌──────────────┬─────────────────────────────────────────┬────────────────────┐
│ Redline      │  Master services agreement   Version 1  │ Changes      1 of 5│
│              │  [Suggest redlines]           [search]  │ ┌────────────────┐ │
│ [ / search ] │ ─────────────────────────────────────── │ │ AI  Indemnif.  │ │
│              │                                         │ │ reason…        │ │
│ Documents    │ ┃ 11. Indemnification                   │ │ [Accept A][Rej R]│
│ ▌Master serv │ ┃ ~~The Customer shall~~ Each party …   │ └────────────────┘ │
│  Mutual NDA  │                                         │ ┌────────────────┐ │
│  SaaS subscr │   12. Limitation of liability …         │ │ …              │ │
│              │                                         │                    │
│              │                                         │ [Apply 3 changes]  │
│ ◐ theme      │                                         │ J K move  / search │
└──────────────┴─────────────────────────────────────────┴────────────────────┘
   240px              flexible, document centered            340px
```

- Three columns. The left rail and the changes panel sit on `--surface-page`, and the document column on `--surface-document`, with `0.5px` borders between them. Each column scrolls on its own, and the page itself never scrolls.
- The document text is left-aligned (never justified), centered in its column at a `68ch` maximum width, with generous top padding.
- **Change bars:** any paragraph containing a pending or accepted suggestion gets a 2px left border in `--redline-delete` (pending) or `--accept` (accepted). It's set by a CSS class on the paragraph, so no positioning is needed.
- Below 1100px, the changes panel narrows to 300px. Below 900px, it's out of scope: show a calm note asking for a wider window.

### The signature moment: accepting a change

When a suggestion is accepted, the deleted text gets its strikethrough, then collapses (`max-width` and `opacity` to 0 over `--duration-base`). The inserted text's tint shifts from `--redline-insert-bg` to `--accept-bg`, and its paragraph's change bar turns green. Rejecting does the reverse: the insertion collapses and the original returns to plain text. Undo restores the pending look. This is the only orchestrated motion in the app. Elsewhere, motion only answers actions: the card opening, the toast arriving.

## 2. Tooling

- Vite with the React and TypeScript template, React 19, TypeScript in `strict` mode, `@tanstack/react-query` v5, Vitest, `@testing-library/react`, ESLint flat config with `typescript-eslint` and `eslint-plugin-react-hooks`, Prettier, and `openapi-typescript`. Use the latest stable versions, pinned exactly.
- **`vite.config.ts`:** a dev proxy from `/api` to `process.env.REDLINE_API_URL`, defaulting to `http://localhost:8000`, that strips the `/api` prefix. Because the browser only talks to the Vite origin, the backend needs no CORS. Vitest runs in the `jsdom` environment.
- **`package.json` scripts:** `dev`, `build`, `test` (`vitest run`), `lint` (`eslint . && tsc --noEmit && prettier --check .`), `format`, and `generate:api-types` (`openapi-typescript $REDLINE_API_URL/openapi.json -o src/api/schema.ts`, with the same default URL).
- **`index.html`:** title "Redline", and an inline SVG favicon of a short red strikethrough line. `<head>` loads `public/theme_boot.js` (section 7), which sets `data-theme` before first paint.

## 3. App shell

- **`main.tsx`:** imports the fonts, `tokens.css`, and `global.css`, creates one `QueryClient` (`staleTime: 30_000`; queries `retry: 1` with no retry on 4xx; mutations, meaning suggest and apply, are never retried, so one click never sends a review twice), and renders `<App />`.
- **`app.tsx`:** the three-column layout. It holds the selected document id and the current search jump target, and renders `DocumentList` and `SearchBox` (left), `DocumentView` (center), and `ChangesPanel` (right).
- **Empty center state** (no document selected): a short invitation, "Choose a contract to review", with one line saying what you can do ("Ask Claude for redlines, then accept or reject each one.").
- **`global.css`:** a reset, `body` on `--surface-page` with `color: var(--text)`, a visible `:focus-visible` ring using `--focus-ring` with a 2px offset, `<mark>` styling with `--search-highlight`, and `content-visibility: auto` on document paragraphs so long contracts render quickly. Keep it only if jump-to-match still lands on the right paragraph (check at checkpoint 2). If skipped layout makes jumps land wrong, remove it and say so.

## 4. API layer

- **`api/schema.ts`** is **generated** from the running backend's OpenAPI document with `npm run generate:api-types`, then committed. The types can't drift from FastAPI's schemas, and no response type is hand-written.
- **`api/types.ts`** re-exports the named shapes the UI uses from `schema.ts` (for example, `export type DocumentResponse = components["schemas"]["DocumentResponse"]`), plus `ErrorType` as a string union taken from the schema.
- **`api/client.ts`:**
  - `class ApiError extends Error` has `status`, `errorType`, and `errorMessage` fields, built from the backend's `{ error, code, error_type }` body. When the body isn't JSON, `errorType` is `"internal_error"` and the message is generic.
  - `requestJson<T>(path, options)` prefixes `/api`, sends and accepts JSON, throws `ApiError` on any non-2xx, and returns `{ body: T, etag: string | null }`. The `ETag` header is part of the result, because writes need it.
- **`api/endpoints.ts`**, one function per endpoint:
  - `listDocuments()` (requests `limit=100`; the API's default page is 20)
  - `getDocument(documentId)`
  - `applyChanges(documentId, etag, changes, author)`
  - `searchDocuments(query, documentIds, limit)`
  - `searchDocument(documentId, query, limit)`
  - `suggestRedlines(documentId, instruction)`

  `applyChanges` sends `If-Match`.

The author for applied changes is the constant `REVIEWER_NAME = "Reviewer"` in `endpoints.ts`. A real user name comes with authentication (README next steps).

## 5. Rendering a document with changes (`document_segments.ts`)

This is pure, so it can be tested without React.

Enumerations use a constant object plus a derived type, not TypeScript `enum`. The guidelines' enum rule is met, and it works with `erasableSyntaxOnly`, which current Vite templates enable. Code always writes `SuggestionStatus.Accepted`, never the bare string.

```ts
export const SuggestionStatus = { Pending: "pending", Accepted: "accepted", Rejected: "rejected" } as const;
export type SuggestionStatus = (typeof SuggestionStatus)[keyof typeof SuggestionStatus];
// Same pattern for SegmentKind (Text, Suggestion) and ChangeState (None, Pending, Accepted).

export interface ReviewSuggestion {
  suggestionId: string;
  start: number;
  end: number;
  originalText: string;
  replacement: string;
  rationale: string;
  status: SuggestionStatus;
}

export type DocumentSegment =
  | { kind: typeof SegmentKind.Text; start: number; end: number; text: string; highlighted: boolean }
  | { kind: typeof SegmentKind.Suggestion; start: number; end: number; suggestion: ReviewSuggestion; highlighted: boolean };

export interface DocumentParagraph {
  start: number;
  end: number;
  isHeading: boolean;
  segments: DocumentSegment[];
  changeState: ChangeState;
}
```

`buildDocumentParagraphs(text, suggestions, highlights)`:
1. Split the text into paragraphs on blank lines (`/\n\s*\n/`), keeping each paragraph's absolute offsets. Paragraphs **tile** the text the way the search chunker does: the blank lines after a paragraph belong to it, so no character, and no suggestion, falls in a gap. Apply the heading rule from section 1.
2. Within each paragraph, cut at every suggestion boundary and every highlight boundary. Pieces inside a suggestion's span belong to that suggestion's segment. A suggestion never crosses a paragraph boundary in practice. If one does, it renders whole in the paragraph where it starts, and the next paragraph begins after its end; test this case.
3. `highlighted` marks a piece that falls inside a search highlight. Inside a suggestion, the highlight shows on the original (deleted) text.
4. `changeState` is `"pending"` if any suggestion in the paragraph is pending, otherwise `"accepted"` if any is accepted, otherwise `"none"`.

Every rendered segment carries `data-start={start}`, so the view can scroll to an offset (section 6).

**Mapping API shapes.** The generated types keep the API's `snake_case` names (`suggestion_id`, `original_text`). They're converted to the camelCase review types in one function, `toReviewSuggestion(response)`, in `review_state.ts`, and nowhere else. A snippet highlight is an absolute document offset, so inside a snippet a `<mark>` starts at `highlight.start - snippet.start`.

## 6. Review state and the review flow

### `review_state.ts` (pure reducer, tested)

```ts
export interface ReviewState {
  documentId: string;
  etag: string;          // the ETag the suggestions were computed against
  suggestions: ReviewSuggestion[];
  dropped: DroppedSuggestionResponse[];
  activeSuggestionId: string | null;
}
```

Actions: `loaded` (from an `AiRedlineResponse` and its ETag; all pending, the first one active), `moved` (`direction: "next" | "previous"`, wrapping around), `selected` (by id), `accepted`, `rejected`, `undone` (back to pending, for the active or a given id), `acceptedAll` (every pending one), and `cleared`. Accepting or rejecting the active suggestion moves to the next pending one, so a reviewer can press `A` `A` `R` `A` through a whole review.

`getAcceptedChanges(state)` returns the range-target `ChangeRequest`s for the accepted suggestions, using the generated types.

### `DocumentView`

- **Header:** the document title (Instrument Serif, 22px), "Version N" (muted, on its own line), a **Suggest redlines** button that opens the composer in the changes panel, and an in-document search field.
- **Body:** renders `buildDocumentParagraphs(...)`.
  - Text segments are plain.
  - Suggestion segments, by status:
    - pending: `<del>` original + `<ins>` replacement, in redline colors;
    - accepted: the collapsing `<del>` and the insertion on `--accept-bg`;
    - rejected: the original as plain text, with the insertion collapsed.
  - The active suggestion gets a `1.5px` outline in `--focus-ring` with a small offset, and is scrolled into view (`scrollIntoView({ block: "center", behavior })`, `"auto"` under reduced motion).
  - Clicking a suggestion selects it. Hovering a card in the panel highlights its segment, and the reverse.
- **Jumping to a search match:** scroll to the element whose `data-start` is closest at or before the match start, then briefly pulse its highlight (one 600ms fade of `--search-highlight`; none under reduced motion).

### `ChangesPanel`

Its states, in order:

1. **No review yet:** `RedlineComposer`.
2. **Reviewing (loading):** skeleton lines and "Reviewing the agreement. This usually takes under 15 seconds." Use `aria-live="polite"`.
3. **Review loaded:**
   - a header with "Changes" and "{active} of {total}";
   - the list of `SuggestionCard`s;
   - `DroppedSuggestions` when there are any;
   - the `ApplyBar` pinned at the bottom.
4. **Errors**, shown as a `StatusBanner` with an action. Messages say what happened and what to do:
   - `ai_not_configured`: "AI suggestions aren't set up. Add ANTHROPIC_API_KEY to .env and restart the server."
   - `model_unavailable` / `model_response_invalid`: "Claude couldn't finish this review. Try again." with a **Try again** button.
   - a network failure: "Can't reach the Redline server. Check that it's running."

### `RedlineComposer`

- A textarea with placeholder "Make the indemnification mutual".
- Three preset chips that fill and submit: "Review against our playbook", "Make the indemnification mutual", "Cap our liability at 12 months' fees".
- A **Suggest redlines** button, submitted with ⌘/Ctrl+Enter.
- An empty instruction shows an inline error, "Describe the changes you want", and doesn't submit.

### `SuggestionCard`

- The AI tag and a short title. The title is the first sentence of the rationale, cut at 60 characters on a word boundary.
- The full rationale in muted text.
- **Accept** (`A`) and **Reject** (`R`) buttons with keyboard hints. Once decided, the card shows its state ("Accepted" in `--accept`, "Rejected" muted) with an **Undo** (`U`) action.
- The active card uses `--surface-selected`.

### `DroppedSuggestions`

A collapsed row, "2 suggestions couldn't be placed". Expanded, it shows each one's text and reason in plain words:
- `target_not_found`: "Quoted text isn't in the document"
- `ambiguous_target`: "Quoted text appears more than once"
- `overlaps_earlier_suggestion`: "Overlaps another suggestion"
- `no_change`: "Suggested no change"
- `empty_target`: "Quoted nothing"

### `ApplyBar`

- **Apply {n} changes** (the one primary button in the view; ⌘/Ctrl+Enter), plus **Accept all** and **Discard review** as secondary actions.
- Apply calls `applyChanges` with the review's ETag and `getAcceptedChanges(state)`.
- **On success:** refetch the document and the document list, clear the review, and show a toast: "Applied 3 changes. Now version 2."
- **On a 412:** a `StatusBanner`: "This contract changed since the review. Run the review again to get fresh suggestions." with **Run again** (resubmits the last instruction) and **Discard review** buttons.
- **With zero accepted:** the button stays enabled. Pressing it shows the inline note "Accept at least one change to apply." (The guidelines prefer responding over disabling.)

### Search

- **`SearchBox` (left rail):** `/` focuses it from anywhere outside a text field, and Escape clears it. Queries are debounced by 250ms and need at least 2 characters.
- **`SearchResults`:** replaces the document list while a query is active. Results are grouped by document: the title, the match count, and up to 3 snippets with `<mark>` highlights built from the snippet's highlight offsets. Each snippet is a button. Pressing it opens that document and jumps to the match.
- **In-document search** (`DocumentView` header): uses `searchDocument`, shows "{n} matches" with previous and next buttons (`Enter` / `Shift+Enter`), and passes the current hit's highlights to `buildDocumentParagraphs`.
- **Empty results:** "No matches for “{query}”. Every word must appear; put exact phrases in quotes."

## 7. Hooks

**`use_keyboard_shortcuts.ts`:** `useKeyboardShortcuts(bindings)`, where `bindings` is a list of `{ key, modifiers, handler, allowInTextField }`. Shortcuts are ignored while focus is in an input, textarea, or `contenteditable`, unless `allowInTextField` is set (the ⌘/Ctrl+Enter submit). Bindings:

| Key | Action |
|---|---|
| `J` / `K` (either case) | next / previous suggestion |
| `A` | accept the active suggestion |
| `R` | reject the active suggestion |
| `U` | undo the active decision |
| `/` | focus search |
| ⌘/Ctrl + Enter | submit the composer while it's open; once a review is loaded, apply the accepted changes |
| `Esc` | clear search, or close the composer |

The changes panel footer shows the main hints ("J K to move", "/ to search") in `KeyboardHint` chips.

**`use_theme.ts`:** `useTheme()` returns `{ theme, setTheme }`, where `theme` is `"system" | "light" | "dark"`. It writes `data-theme` on `<html>` ("light" or "dark"; removed for "system") and stores the choice in `localStorage` under `redline-theme`. Every `localStorage` read and write is wrapped in `try`/`catch`, falling back to `"system"`. `public/theme_boot.js`, a tiny script loaded in `<head>`, applies the stored theme before React mounts, so there's no flash of the wrong theme and `index.html` keeps no inline script.

`ThemeToggle` (bottom of the left rail) cycles system → light → dark, with an icon and an accessible label naming the current mode.

## 8. Shared components

- **`Wordmark`:** "Red" in `--text` and "line" in `--redline-delete`, Instrument Serif 24px. As a link, it clears the selection.
- **`Button`:** `variant: "primary" | "secondary" | "ghost"`, plus an optional `shortcut` string that renders a `KeyboardHint`. Primary is ink (`--text` background, `--surface-document` text). Accept buttons use a secondary style with `--accept` text.
- **`KeyboardHint`:** an 11px chip with a hairline border and `--radius-control`.
- **`StatusBanner`:** the message, an optional action button, and `role="status"`.
- **`Toast`:** a bottom-center `--surface-document` card with `--shadow-popover`. It auto-hides after 4 seconds, uses `aria-live="polite"`, and enters with one 140ms fade.

## 9. Makefile and README

- **Makefile targets:**
  - `ui-install`: `cd frontend && npm install`
  - `ui`: `cd frontend && REDLINE_API_URL=http://localhost:$(PORT) npm run dev`, reusing the existing `PORT ?= 8000`
  - `ui-test`: `cd frontend && npm test`
  - `ui-lint`: `cd frontend && npm run lint`
  - `ui-types`: `cd frontend && REDLINE_API_URL=http://localhost:$(PORT) npm run generate:api-types`
- **README:** a **Review UI** section covering how to run it (two terminals: `make dev`, then `make ui`), the review flow, the keyboard shortcuts table, and theme. Phase 6 adds screenshots.

## 10. Tests

Vitest, set up / act / assert, asserting on structured values rather than strings where possible.

### `document_segments.test.ts`

- `splits paragraphs on blank lines with absolute offsets`
- `marks a numbered short paragraph as a heading`
- `does not mark a long numbered paragraph as a heading`
- `places a suggestion as one segment between text segments`
- `splits text at highlight boundaries`
- `highlights the original text inside a suggestion`
- `sets change state pending when any suggestion is pending`
- `sets change state accepted when all suggestions are decided and one is accepted`
- `keeps a suggestion that crosses a paragraph break whole in its first paragraph`

### `review_state.test.ts`

- `loaded makes every suggestion pending and the first active`
- `moved next wraps from last to first`
- `moved previous wraps from first to last`
- `accepted marks the active suggestion and moves to the next pending one`
- `rejected marks the active suggestion and moves to the next pending one`
- `undone returns a decided suggestion to pending`
- `acceptedAll accepts only pending suggestions`
- `getAcceptedChanges returns range targets for accepted suggestions only`
- `selected makes that suggestion active`
- `cleared empties the review`
- `moved next goes to the following suggestion when not at the end`
- `accepted with no pending suggestions left keeps the active one`

### `api/client.test.ts`

Mock `fetch`.
- `returns the body and the ETag on success`
- `throws ApiError with the backend error type on a JSON error body`
- `throws ApiError with internal_error when the error body is not JSON`

### `hooks/use_keyboard_shortcuts.test.ts`

- `calls the handler for a bound key`
- `ignores a bound key while typing in a text field`
- `calls an allowInTextField binding while typing in a text field`

### `review_flow.test.tsx`

React Testing Library, with `fetch` mocked to return a document, an `AiRedlineResponse` with two suggestions, and a successful `PATCH`.
- `reviewer accepts one suggestion, rejects one, and applies`: open the document, click the playbook preset, press `A`, then `R`, then ⌘+Enter. Assert the `PATCH` body holds exactly one range change with the right offsets and `If-Match`, and that the toast reports version 2.
- `stale review shows the changed-since banner`: the `PATCH` returns 412 with `precondition_failed`. Assert the banner and its **Run again** action.

## 11. Design notes (for the README)

- **The document stays the hero.** Serif body at a comfortable measure, quiet chrome, and color only where it means something (delete, insert, accept, AI).
- **Familiar conventions:** strikethrough and underline as well as color, so changes read even without color, and redlines look the way lawyers already read them.
- **Review, then apply.** Decisions are staged, then applied as one versioned write with `If-Match`, so the reviewer always applies exactly what they reviewed.
- **Generated API types** keep the frontend in lockstep with the FastAPI schemas.
- **Keyboard first,** because partners review changes, not documents.

## Checkpoints ✅

Stop at each checkpoint and report before going on. From checkpoint 2 on, attach screenshots: 1440 × 900, light and dark, at device scale factor 2.

1. **Scaffold.** `make ui-install`, `make ui-types` (with the backend running), `make ui-lint`, and `make ui` boots to the empty state with the wordmark and theme toggle. Report the pinned versions in `package.json` and a screenshot.
2. **Data flows.** The document list, document view (headings and body), and search across documents with jump-to-match all work against the seeded data, using the tokens. Report screenshots of a search result and of a jumped-to match.
3. **Review flow.** `make reseed` and restart the backend. Run "Review against our playbook" on the MSA, step through with `J`/`K`/`A`/`R`/`U`, apply, and check the new version. Then show the 412 banner by applying a stale review (apply once, then reuse the old review state through a second tab). `make ui-test` passes. Report screenshots of: a pending review, a mix of accepted and rejected suggestions, the toast after applying, and the 412 banner.
4. **Design pass.** Go through section 1 line by line and fix every gap. Check contrast and report any token changes. Check reduced motion. Report the light and dark screenshots of the pending-review state, side by side. The user will compare them with the approved mockup.
5. **Final.** `make ui-lint`, `make ui-test`, `make lint`, and `make test`, with totals. Report the README's new section headings.

## Definition of done

- [ ] The UI matches the approved design: tokens, type, layout, change bars, and the accept and reject motion, in light and dark, with a theme toggle that remembers the choice.
- [ ] A reviewer can run an AI review, step through it from the keyboard, accept and reject, and apply as a new version; a stale apply shows the 412 banner.
- [ ] Search across documents and within a document works, with highlighted snippets and jump-to-match.
- [ ] Errors show plain messages with a next step, including AI not configured, model failure, server down, and stale review.
- [ ] API types are generated from the backend's OpenAPI document and committed.
- [ ] No inline `style` props, and every function and component has a JSDoc header.
- [ ] Every test named in section 10 exists and passes, and `make ui-lint` is clean.
- [ ] Each checkpoint was reported with screenshots.
