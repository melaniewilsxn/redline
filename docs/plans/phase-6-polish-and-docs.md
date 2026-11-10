# Phase 6: Review Fixes, Setup, and Final README

**Project:** Redline (see `docs/plans/build-plan.md`)
**Audience:** the coding agent building this phase

Read and follow the `code-guidelines` skill before writing any code. If this plan and the guidelines disagree, the guidelines win: follow them and tell the user what differed. Check each library's current docs before using it.

`docs/infra.md` (Part II) is being written separately with the user. **Don't create or edit it.**

## Goal

Make the submission ready for a reviewer. It has three parts:
- **Part A** fixes what a hands-on walkthrough of the UI found.
- **Part B** fixes what the fresh-clone run found, so a reviewer can go from `git clone` to a working app by following the README top to bottom.
- **Part C** finishes the README (screenshots, the API design rationale, an honest time note) and pushes to GitHub.

**Out of scope:** new features, stored proposals, version compare, and `docs/infra.md`.

## Part A: Fixes from the UI walkthrough

### A1. Show suggestions as word-level redlines

The model often replaces a whole paragraph to make one change. The UI shows that as a full paragraph struck through, then a full paragraph inserted, which is hard to read and isn't how a lawyer marks up a draft. Keep each suggestion as **one** range change (applying is unchanged), but **render** it as a word-level diff between `originalText` and `replacement`.

- Use the `diff` package (jsdiff) `9.0.0`, `diffWordsWithSpace`. It returns strings, not offsets, so count offsets while walking the parts: the original text is the unchanged parts plus the removed parts, and the replacement is the unchanged parts plus the added parts.
- New pure module `features/redline/suggestion_diff.ts`: `buildSuggestionParts(originalText, replacement)` returns a list of parts, each with `kind` (`SuggestionPartKind.Unchanged | Removed | Added`, same constant-object pattern as the other enums) and `text`.
- Rendering in `DocumentView`:
  - **pending:** unchanged words as plain text, removed words as `<del>`, added words as `<ins>`;
  - **accepted:** unchanged and added words, with added words on `--accept-bg`; removed words collapse with the existing motion;
  - **rejected:** unchanged and removed words as plain text; added words collapse.
- Search highlights inside a suggestion still mark the original text: highlight unchanged and removed parts by their offset within `originalText`.
- Tests in `suggestion_diff.test.ts`:
  - `keeps unchanged words between a removed and an added word`
  - `returns one added part for a pure insertion`
  - `returns one removed part for a pure deletion`
  - `joins unchanged parts back to the original and added parts to the replacement` (the round-trip property)
  - one render test in `review_flow.test.tsx`: a pending suggestion that changes one word shows exactly one `<del>` and one `<ins>`

### A2. Give each suggestion a real title

Card titles are the first 60 characters of the rationale, cut mid-phrase ("Indemnification: a one-way Customer indemnity is never"), and the rationale below repeats them. Have the model return a title.

- **Backend:**
  - add a required `title` string to each suggestion in `SUGGESTIONS_SCHEMA`;
  - add `title` to `RedlineSuggestion`, `AnchoredSuggestion`, `DroppedSuggestion`, `SuggestionResponse`, and `DroppedSuggestionResponse`;
  - `parse_suggestions` reads it like the other fields.
- **`SYSTEM_PROMPT`:** `title`: 2 to 6 words in sentence case naming the change, for example "Make the indemnity mutual" or "Cap liability at 12 months' fees".
- An empty `title` doesn't fail the response or drop the suggestion. The card shows "Suggested change" as its heading. Replacement, prefix, and suffix may still be empty.
- Update the existing schema, parse, and anchoring tests, and the fake client fixtures.
- Run `make ui-types`. The card shows `title` as its heading and the full rationale below it.

### A3. Use the approved AI tag colors

The AI tag renders with `--text-muted` on the page background. The approved design uses `--ai` text on `--ai-bg`, but those tokens were never added to `tokens.css`. Add `--ai` and `--ai-bg` for light and dark, with the values from the Phase 5 token table, then point `.tag` in `suggestion_card.module.css` at them.

### A4. Show the composer only when a contract is open

With no contract selected, the changes panel shows the composer and **Suggest redlines**, which has nothing to act on. The panel can't tell this apart today (`suggestions === null` also means "no review yet"), so pass it whether a contract is open. Show the composer only when one is; otherwise show one short line: "Open a contract to ask Claude for redlines."

### A5. Keep search matches marked after a jump

After jumping from a search result, the match is highlighted for 600ms, then disappears, so the reader loses their place. Today `openMatch` keeps only the first highlight of the clicked snippet, and the pulse animation ends at `background: transparent`. Instead:
- keep every highlight from the opened hit (all of its snippets) marked in the document until the search is cleared, another document is opened, or a review loads;
- give the jumped-to match a stronger treatment (a `1.5px` `--focus-ring` outline on that `<mark>`);
- keep the one-time pulse, but have it end on the mark color, not `transparent` (no pulse under reduced motion).

### A6. Hide in-document Previous and Next until there's a query

Show **Previous**, **Next**, and "{n} matches" only while the in-document search field has a query. Today the buttons always show, and the count shows only while a request is in flight.

### A7. Fix the sample contracts' capitalization

There are 60 sentences across the three contracts that start with a lowercase "the" ("…in each order. the Customer shall…"), an artifact of how the repeated phrase was written. Capitalize every sentence-initial and line-initial "the" to "The". Mid-sentence "the Customer shall" stays, so context targets still have repeated text to work with. After the change, search the repo (`tests/`, `samples/curl_requests.sh`, the README) for any quote that depended on the lowercase form, and update it.

### A8. Proper titles for the seeded contracts

Titles come from file names, so they read "master services agreement" and "mutual nda". Add `CONTRACT_TITLES` to `scripts/seed.py`, mapping each file to its title: "Master Services Agreement", "Mutual NDA", "SaaS Subscription Agreement". These are document names, so they keep their capitals. A contract file missing from the map is a startup error that names the file. `samples/curl_requests.sh` finds the MSA by the title `master services agreement`; change that lookup to `Master Services Agreement`.

### A9. Check dark mode with a visible browser

The page's computed colors are correct in dark mode (`--surface-document` resolves to `#1A1C22`), but screenshots from a hidden browser pane showed the document column white. Take dark screenshots in a **visible** browser window: the pending review, after accepting a change, and after applying. Confirm the document column is dark in each. If any area doesn't repaint after accepting a change (Phase 5 saw paragraphs stop painting once), find the cause: look for a transition or `will-change` keeping a stale layer. Don't hide it.

## Part B: Fixes from the fresh-clone run

### B1. One setup path in the README

Rewrite **Setup** as one numbered path that a reviewer follows top to bottom:

1. **Prerequisites:** Docker Desktop, uv, and Node 22 or newer with npm. Name the versions tested. uv installs Python 3.14 itself.
2. `cp .env.example .env`. Optionally add `ANTHROPIC_API_KEY` for AI suggestions; everything else works without it.
3. `make db-up`
4. `make install` (backend) and `make ui-install` (frontend)
5. `make seed`
6. In two terminals: `make dev` (API at `http://localhost:8000`, interactive docs at `/docs`) and `make ui` (review UI at `http://localhost:5173`).
7. To reset the sample contracts later: `make reseed`, then restart `make dev`.

### B2. Ports in one place

- `docker-compose.yml`: publish `${POSTGRES_PORT:-5433}:5432`. `.env.example` documents `POSTGRES_PORT` next to `DATABASE_URL` and `TEST_DATABASE_URL`, with a comment that the three must agree.
- A **Ports** subsection: the API on 8000, the UI on 5173, Postgres on 5433, and what to change when each is taken:
  - `make dev PORT=8002` and `make ui PORT=8002`
  - `BASE_URL=http://localhost:8002 ./samples/curl_requests.sh`
  - `POSTGRES_PORT` plus the two URLs in `.env`
- The usage curl examples use `$BASE_URL` (defaulting to `http://localhost:8000`), so they work on any port.

### B3. Make the frontend targets install on first use

Add a `frontend/node_modules` target that depends on `frontend/package.json` and `frontend/package-lock.json`, runs `npm ci`, and touches the folder. `ui-install`, `ui`, `ui-test`, `ui-lint`, and `ui-types` all depend on it, so there's one install path. `make ui-test` on a fresh clone then installs and runs instead of failing with `vitest: command not found`.

### B4. Show how to run the curl walkthrough

The README shows the command (`./samples/curl_requests.sh`), says it prints status codes and short JSON (not contract text), that `BASE_URL` picks the server, and that without an API key the AI step prints `ai_not_configured` and skips applying.

### B5. Check the npm advisories

Run `npm audit --omit=dev` and `npm audit`, and report both. If production dependencies have no advisories and the moderate ones are only in dev tools, add one line under Testing saying so. If a non-breaking update fixes them, take it and rerun `make ui-test`. Don't use `npm audit fix --force`.

### B6. List every check in Testing

Testing lists `make test` (backend, including the 10MB tests), `make ui-test`, `make bench`, `make lint`, and `make ui-lint`, with what each covers and that database tests roll back.

## Part C: Final README and submission

### C1. README content

Keep the existing sections, and make sure each of these is in it:
- **What it is:** two or three sentences, then a screenshot of a pending review (light).
- **Architecture:** the Mermaid diagram from `docs/plans/build-plan.md` section 3, updated for the shipped scope (no compare, no stored proposals), with its one paragraph on how data moves.
- **API design:** add a short "REST and action endpoints" paragraph:
  - documents and versions are resources;
  - edits are a `PATCH` with our own change format, because JSON Patch addresses JSON fields, not text spans;
  - search is a `GET` because it only reads and can be bookmarked;
  - `POST /documents/{id}/ai-redlines` is an action, because it runs an expensive model call from an instruction, returns a computed result, and isn't repeatable;
  - applying suggestions reuses `PATCH` instead of adding an accept endpoint.
- **AI redline suggestions:** add one real example from a live run: the instruction, one suggestion's title, its rationale, and the original → replacement in a short excerpt, plus a screenshot. A reviewer without a key can see what the feature does.
- **Review UI:** screenshots of the pending review (light and dark), the accepted and rejected mix, and search results.
- **Performance:** the current benchmark table, and its reading, including the common-phrase row explanation.
- **Built with:** one paragraph. "Built with AI coding assistance, as the brief allows." Then which parts make up the core (engine, versioned API, search, tests) and which were added on top (AI suggestions, review UI). **Leave the time figures as `TODO(Melanie): time` for the user to fill in.** Don't guess them.
- **Next steps:** keep the existing items (such as comment threads), and make sure these are there: stored proposals with rebasing (the algorithm exists in `editing/rebase.py`, with tests), version compare, authentication and real user names, `.docx` import and export, multi-process search (a shared or external index), Aho–Corasick for large batches of text targets, a phrase-match boost, and versions stored as deltas.

Screenshots go in `docs/screenshots/` as PNG at 1440 × 900, light and dark, taken in a visible browser after `make reseed`. Use short names: `review_light.png`, `review_dark.png`, `review_decided.png`, `search.png`, `ai_suggestion.png`.

### C2. Final run and push

1. `make reseed`, then restart `make dev`.
2. `make lint`, `make test`, `make ui-lint`, `make ui-test`, `make bench`. Report the totals, and update the README if a number changed.
3. Commit and push, using the problem/solution commit style. One commit per part is fine.
4. Repeat the fresh-clone run from Part B: clone the **pushed** repo (not the local folder) into a temp folder and follow only the README. Report every step's result. Stop the clone's servers and remove the temp folder afterwards. If the run finds a problem, fix it, push again, and rerun.

## Checkpoints ✅

Stop at each checkpoint and report before going on.

1. **Part A.** Report the tests for A1 and A2 by name. Attach light and dark screenshots of a playbook review on a freshly reseeded MSA, showing word-level redlines, titled cards, and the violet AI tag, plus one after a search jump with the marks kept. Report A7's count of changed sentences and any quotes updated.
2. **Part B.** The new Setup and Ports sections pasted in full, the npm audit results, and `make ui-test` on a fresh clone installing on its own.
3. **Part C.** The README's section headings, the screenshot list, all check totals, the fresh-clone run from the pushed repo, and the pushed commit hashes.

## Definition of done

- [ ] A1–A9 are done. Suggestions render as word-level redlines and apply as one range change each. Cards have model-written titles. The AI tag uses the approved colors. Search marks persist after a jump. The sample contracts read correctly with proper titles. Dark mode is confirmed in a visible browser.
- [ ] B1–B6 are done. A fresh clone works by following the README alone, ports are configurable and documented, and frontend targets install on first use.
- [ ] The README has the C1 content and screenshots, with the time figures left as a TODO for the user.
- [ ] Every check passes, the fresh clone of the pushed repo works, and everything is pushed.
- [ ] `docs/infra.md` is untouched.
