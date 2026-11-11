import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState, type ReactNode } from "react";

import { ApiError } from "./api/client.ts";
import { REVIEWER_NAME, applyChanges } from "./api/endpoints.ts";
import { ApiErrorType, type ChangeRequest, type TextSpanResponse } from "./api/types.ts";
import { ThemeToggle } from "./components/theme_toggle.tsx";
import { Toast } from "./components/toast.tsx";
import { Wordmark } from "./components/wordmark.tsx";
import { DocumentList } from "./features/documents/document_list.tsx";
import { useDocument, useDocumentList } from "./features/documents/use_documents.ts";
import { useSuggestRedlines } from "./features/ai_redlines/use_suggest_redlines.ts";
import { ChangesPanel } from "./features/redline/changes_panel.tsx";
import { DocumentView } from "./features/redline/document_view.tsx";
import {
  MoveDirection,
  ReviewActionType,
  getAcceptedChanges,
  reduceReview,
} from "./features/redline/review_state.ts";
import { SearchBox } from "./features/search/search_box.tsx";
import { SearchResults } from "./features/search/search_results.tsx";
import { useCrossDocumentSearch } from "./features/search/use_search.ts";
import { useKeyboardShortcuts } from "./hooks/use_keyboard_shortcuts.ts";
import { ThemeChoice, useTheme } from "./hooks/use_theme.ts";
import styles from "./app.module.css";

const TOAST_DURATION_MS = 4_000;
const EMPTY_APPLY_NOTE = "Accept at least one change to apply.";
const NETWORK_MESSAGE = "Can't reach the Redline server. Check that it's running.";

interface ApplyRequest {
  documentId: string;
  etag: string;
  changes: ChangeRequest[];
}

interface SearchJump {
  documentId: string;
  highlights: TextSpanResponse[];
  focusStart: number;
  focusEnd: number;
}

/**
 * The review screen: a contract, its suggestions, and search.
 * @returns The screen.
 * @throws Does not throw.
 */
export function App(): ReactNode {
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [jump, setJump] = useState<SearchJump | null>(null);
  const [instruction, setInstruction] = useState("");
  const [instructionMissing, setInstructionMissing] = useState(false);
  const [review, dispatchReview] = useReducer(reduceReview, null);
  const [hoveredSuggestionId, setHoveredSuggestionId] = useState<string | null>(null);
  const [staleReview, setStaleReview] = useState(false);
  const [applyNote, setApplyNote] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const documents = useDocumentList();
  const openDocument = useDocument(selectedDocumentId);
  const search = useCrossDocumentSearch(searchQuery);
  const suggest = useSuggestRedlines();
  const apply = useMutation({
    mutationFn: (request: ApplyRequest) =>
      applyChanges(request.documentId, request.etag, request.changes, REVIEWER_NAME),
    retry: false,
  });

  useEffect(() => {
    if (toast === null) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), TOAST_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useKeyboardShortcuts([
    {
      key: "j",
      modifiers: [],
      allowInTextField: false,
      handler: () => move(MoveDirection.Next),
    },
    {
      key: "k",
      modifiers: [],
      allowInTextField: false,
      handler: () => move(MoveDirection.Previous),
    },
    {
      key: "a",
      modifiers: [],
      allowInTextField: false,
      handler: () => decide(ReviewActionType.Accepted),
    },
    {
      key: "r",
      modifiers: [],
      allowInTextField: false,
      handler: () => decide(ReviewActionType.Rejected),
    },
    {
      key: "u",
      modifiers: [],
      allowInTextField: false,
      handler: () => decide(ReviewActionType.Undone),
    },
    { key: "/", modifiers: [], allowInTextField: false, handler: focusSearch },
    { key: "Enter", modifiers: ["meta"], allowInTextField: true, handler: commandEnter },
    { key: "Enter", modifiers: ["ctrl"], allowInTextField: true, handler: commandEnter },
    { key: "Escape", modifiers: [], allowInTextField: true, handler: clearSearchOrComposer },
  ]);

  const jumpForDocument = jump !== null && jump.documentId === selectedDocumentId ? jump : null;
  const suggestions = review?.suggestions ?? null;

  return (
    <>
      <div className={styles.shell}>
        <aside className={styles.rail}>
          <div className={styles.railHeader}>
            <Wordmark onSelectHome={closeDocument} />
            <ThemeToggle theme={theme} onCycle={cycleTheme} />
          </div>
          <SearchBox
            query={searchQuery}
            inputRef={searchInputRef}
            onQueryChange={changeSearchQuery}
          />
          <div className={styles.railBody}>
            {search.trimmedQuery !== "" ? (
              <SearchResults
                query={search.trimmedQuery}
                documents={documents.data?.body.documents ?? []}
                hits={search.textHits}
                textSettled={search.textSettled}
                onOpenDocument={selectDocument}
                onOpenMatch={openMatch}
              />
            ) : (
              <DocumentList
                documents={documents.data?.body.documents ?? []}
                selectedDocumentId={selectedDocumentId}
                onSelectDocument={selectDocument}
              />
            )}
          </div>
        </aside>
        <DocumentView
          document={openDocument.data?.body ?? null}
          suggestions={suggestions ?? []}
          activeSuggestionId={review?.activeSuggestionId ?? null}
          hoveredSuggestionId={hoveredSuggestionId}
          jumpStart={jumpForDocument?.focusStart ?? null}
          persistedHighlights={jumpForDocument?.highlights ?? []}
          focusStart={jumpForDocument?.focusStart ?? null}
          focusEnd={jumpForDocument?.focusEnd ?? null}
          loading={selectedDocumentId !== null && openDocument.isLoading}
          failed={openDocument.isError}
          onSelectSuggestion={(suggestionId) =>
            dispatchReview({ type: ReviewActionType.Selected, suggestionId })
          }
          onHoverSuggestion={setHoveredSuggestionId}
        />
        <ChangesPanel
          contractOpen={selectedDocumentId !== null}
          suggestions={suggestions}
          dropped={review?.dropped ?? []}
          activeSuggestionId={review?.activeSuggestionId ?? null}
          instruction={instruction}
          instructionMissing={instructionMissing}
          reviewing={suggest.isPending}
          suggestError={suggest.error}
          staleReview={staleReview}
          applyNote={applyNote}
          onInstructionChange={setInstruction}
          onSubmitInstruction={submitInstruction}
          onSelectSuggestion={(suggestionId) =>
            dispatchReview({ type: ReviewActionType.Selected, suggestionId })
          }
          onHoverSuggestion={setHoveredSuggestionId}
          onAccept={(suggestionId) =>
            dispatchReview({ type: ReviewActionType.Accepted, suggestionId })
          }
          onReject={(suggestionId) =>
            dispatchReview({ type: ReviewActionType.Rejected, suggestionId })
          }
          onUndo={(suggestionId) => dispatchReview({ type: ReviewActionType.Undone, suggestionId })}
          onAcceptAll={() => dispatchReview({ type: ReviewActionType.AcceptedAll })}
          onApply={applyAccepted}
          onDiscard={discardReview}
        />
      </div>
      <div className={styles.narrow}>
        <p>
          Redline needs a wider window. Make this window at least 900 pixels wide to review a
          contract.
        </p>
      </div>
      {toast === null ? null : <Toast message={toast} />}
    </>
  );

  /**
   * Open a contract and drop any review of a different one.
   * @param documentId - The contract to open.
   * @throws Does not throw.
   */
  function selectDocument(documentId: string): void {
    if (documentId !== selectedDocumentId) {
      discardReview();
      setInstruction("");
    }
    setSelectedDocumentId(documentId);
    setJump(null);
  }

  /**
   * Return to the list of contracts.
   * @throws Does not throw.
   */
  function closeDocument(): void {
    setSelectedDocumentId(null);
    setJump(null);
    discardReview();
    setInstruction("");
  }

  /**
   * Open a contract at a search match.
   * @param documentId - The contract that matched.
   * @param start - The match start.
   * @param end - The match end.
   * @throws Does not throw.
   */
  function openMatch(
    documentId: string,
    highlights: TextSpanResponse[],
    focusStart: number,
    focusEnd: number,
  ): void {
    if (documentId !== selectedDocumentId) {
      discardReview();
      setInstruction("");
    }
    setSelectedDocumentId(documentId);
    setJump({ documentId, highlights, focusStart, focusEnd });
  }

  /**
   * Store the rail search, and drop kept matches when it is cleared.
   * @param query - The text in the search field.
   * @throws Does not throw.
   */
  function changeSearchQuery(query: string): void {
    setSearchQuery(query);
    if (query.trim() === "") {
      setJump(null);
    }
  }

  /**
   * Send an instruction when it has something to say.
   * @param nextInstruction - The instruction from the field or a preset.
   * @throws Does not throw.
   */
  function submitInstruction(nextInstruction: string): void {
    const trimmed = nextInstruction.trim();
    if (selectedDocumentId === null || trimmed === "") {
      setInstructionMissing(trimmed === "");
      return;
    }
    setInstruction(trimmed);
    setInstructionMissing(false);
    setApplyNote("");
    setJump(null);
    suggest.mutate(
      { documentId: selectedDocumentId, instruction: trimmed },
      {
        onSuccess: (response) => {
          dispatchReview({
            type: ReviewActionType.Loaded,
            documentId: selectedDocumentId,
            etag: response.etag ?? "",
            response: response.body,
          });
          setStaleReview(false);
        },
      },
    );
  }

  /**
   * Apply the accepted suggestions, or explain that none are accepted.
   * @throws Does not throw.
   */
  function applyAccepted(): void {
    if (
      review === null ||
      selectedDocumentId === null ||
      review.documentId !== selectedDocumentId
    ) {
      return;
    }
    const changes = getAcceptedChanges(review);
    if (changes.length === 0) {
      setApplyNote(EMPTY_APPLY_NOTE);
      return;
    }
    setApplyNote("");
    const acceptedCount = changes.length;
    apply.mutate(
      { documentId: selectedDocumentId, etag: review.etag, changes },
      {
        onSuccess: (response) => {
          dispatchReview({ type: ReviewActionType.Cleared });
          setStaleReview(false);
          setToast(appliedMessage(acceptedCount, response.body.document.version));
          void queryClient.invalidateQueries({ queryKey: ["document", selectedDocumentId] });
          void queryClient.invalidateQueries({ queryKey: ["documents"] });
        },
        onError: (error: unknown) => {
          if (error instanceof ApiError && error.errorType === ApiErrorType.PreconditionFailed) {
            setStaleReview(true);
            return;
          }
          setApplyNote(
            error instanceof ApiError && error.status === 0 ? NETWORK_MESSAGE : errorMessage(error),
          );
        },
      },
    );
  }

  /**
   * Close the review and its banners.
   * @throws Does not throw.
   */
  function discardReview(): void {
    dispatchReview({ type: ReviewActionType.Cleared });
    setStaleReview(false);
    setApplyNote("");
    setHoveredSuggestionId(null);
    suggest.reset();
  }

  /**
   * Move to the next or previous suggestion.
   * @param direction - Which way to move.
   * @throws Does not throw.
   */
  function move(direction: MoveDirection): void {
    if (review === null) {
      return;
    }
    dispatchReview({ type: ReviewActionType.Moved, direction });
  }

  /**
   * Accept, reject, or undo the active suggestion.
   * @param type - The decision.
   * @throws Does not throw.
   */
  function decide(
    type:
      | typeof ReviewActionType.Accepted
      | typeof ReviewActionType.Rejected
      | typeof ReviewActionType.Undone,
  ): void {
    if (review?.activeSuggestionId == null) {
      return;
    }
    dispatchReview({ type, suggestionId: review.activeSuggestionId });
    setApplyNote("");
  }

  /**
   * Submit the composer, or apply the review once it is open.
   * @throws Does not throw.
   */
  function commandEnter(): void {
    if (suggest.isPending || apply.isPending) {
      return;
    }
    if (review === null) {
      submitInstruction(instruction);
      return;
    }
    applyAccepted();
  }

  /**
   * Clear the search, or the composer when search is already empty.
   * @throws Does not throw.
   */
  function clearSearchOrComposer(): void {
    if (searchQuery !== "") {
      changeSearchQuery("");
      return;
    }
    if (review === null) {
      setInstruction("");
      setInstructionMissing(false);
    }
  }

  /**
   * Put the cursor in the contract search.
   * @throws Does not throw.
   */
  function focusSearch(): void {
    searchInputRef.current?.focus();
  }

  /**
   * Switch between the light and dark themes.
   * @throws Does not throw.
   */
  function cycleTheme(): void {
    if (theme === ThemeChoice.Light) {
      setTheme(ThemeChoice.Dark);
      return;
    }
    setTheme(ThemeChoice.Light);
  }
}

/**
 * Build the confirmation shown after a version is saved.
 * @param acceptedCount - How many changes were saved.
 * @param version - The version they were saved as.
 * @returns The toast text.
 * @throws Does not throw.
 */
function appliedMessage(acceptedCount: number, version: number): string {
  const changeLabel = acceptedCount === 1 ? "1 change" : `${acceptedCount} changes`;
  return `Applied ${changeLabel}. Now version ${version}.`;
}

/**
 * A short message for an apply failure that is not a stale review.
 * @param error - The failure.
 * @returns The note under the apply bar.
 * @throws Does not throw.
 */
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.errorMessage;
  }
  return NETWORK_MESSAGE;
}
