import type { ReactNode } from "react";

import type { DocumentSummaryResponse } from "../../api/types.ts";
import styles from "./document_list.module.css";

/**
 * The contracts in the left rail.
 * @param documents - The contracts to show.
 * @param selectedDocumentId - The open contract, or null.
 * @param onSelectDocument - Opens a contract.
 * @returns The list.
 * @throws Does not throw.
 */
export function DocumentList({
  documents,
  selectedDocumentId,
  onSelectDocument,
}: {
  documents: DocumentSummaryResponse[];
  selectedDocumentId: string | null;
  onSelectDocument: (documentId: string) => void;
}): ReactNode {
  if (documents.length === 0) {
    return <p className={styles.empty}>No contracts yet.</p>;
  }
  return (
    <ul className={styles.list}>
      {documents.map((document) => (
        <li key={document.id}>
          <button
            type="button"
            className={
              document.id === selectedDocumentId
                ? `${styles.contract} ${styles.selected}`
                : styles.contract
            }
            aria-current={document.id === selectedDocumentId ? "true" : undefined}
            onClick={() => onSelectDocument(document.id)}
          >
            <span className={styles.title}>{document.title}</span>
            <span className={styles.meta}>Version {document.version}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
