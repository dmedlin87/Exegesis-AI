"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
    Dialog,
    DialogActions,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "../../components/ui/dialog";
import type { CollectionDetail, CollectionItem } from "../../lib/api-client";
import styles from "./page.module.css";

type ItemsByType = {
  document: CollectionItem[];
  chat_session: CollectionItem[];
  research_note: CollectionItem[];
  passage: CollectionItem[];
};

const ITEM_TYPE_LABELS: Record<keyof ItemsByType, string> = {
  document: "Documents",
  chat_session: "Chat Sessions",
  research_note: "Research Notes",
  passage: "Passages",
};

const ITEM_TYPE_ICONS: Record<keyof ItemsByType, string> = {
  document: "📄",
  chat_session: "💬",
  research_note: "📝",
  passage: "📖",
};

export default function CollectionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const collectionId = params?.id as string;

  const [collection, setCollection] = useState<CollectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [removingItemId, setRemovingItemId] = useState<string | null>(null);

  const loadCollection = useCallback(async () => {
    if (!collectionId) return;

    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/collections/${encodeURIComponent(collectionId)}`);
      if (response.status === 404) {
        setError("Collection not found");
        return;
      }
      if (!response.ok) throw new Error("Failed to load collection");
      const data = await response.json();
      setCollection(data);
    } catch (err) {
      console.error("Error loading collection:", err);
      setError("Failed to load collection. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [collectionId]);

  useEffect(() => {
    loadCollection();
  }, [loadCollection]);

  const handleDeleteCollection = async () => {
    if (!collectionId) return;

    try {
      setDeleting(true);
      const response = await fetch(`/api/collections/${encodeURIComponent(collectionId)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Failed to delete collection");
      router.push("/collections");
    } catch (err) {
      console.error("Error deleting collection:", err);
      setError("Failed to delete collection. Please try again.");
      setDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  const handleRemoveItem = async (itemId: string) => {
    if (!collectionId) return;

    try {
      setRemovingItemId(itemId);
      const response = await fetch(
        `/api/collections/${encodeURIComponent(collectionId)}/items/${encodeURIComponent(itemId)}`,
        { method: "DELETE" }
      );
      if (!response.ok) throw new Error("Failed to remove item");

      // Update local state
      setCollection((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          items: prev.items.filter((item) => item.id !== itemId),
        };
      });
    } catch (err) {
      console.error("Error removing item:", err);
      setError("Failed to remove item. Please try again.");
    } finally {
      setRemovingItemId(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  // Group items by type
  const itemsByType: ItemsByType = {
    document: [],
    chat_session: [],
    research_note: [],
    passage: [],
  };

  if (collection?.items) {
    for (const item of collection.items) {
      if (item.item_type in itemsByType) {
        itemsByType[item.item_type as keyof ItemsByType].push(item);
      }
    }
  }

  const nonEmptyGroups = (Object.keys(itemsByType) as Array<keyof ItemsByType>).filter(
    (type) => itemsByType[type].length > 0
  );

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading collection...</p>
        </div>
      </div>
    );
  }

  if (error && !collection) {
    return (
      <div className={styles.page}>
        <Link href="/collections" className={styles.backLink}>
          ← Back to Collections
        </Link>
        <div className={styles.error}>
          <h2>Error</h2>
          <p>{error}</p>
          <button type="button" className={styles.retryButton} onClick={loadCollection}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className={styles.page}>
        <Link href="/collections" className={styles.backLink}>
          ← Back to Collections
        </Link>
        <div className={styles.error}>
          <h2>Collection Not Found</h2>
          <p>The collection you&apos;re looking for doesn&apos;t exist or has been deleted.</p>
          <Link href="/collections" className={styles.retryButton}>
            Go to Collections
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Link href="/collections" className={styles.backLink}>
        ← Back to Collections
      </Link>

      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div className={styles.headerInfo}>
            <h1>{collection.name}</h1>
            <div className={styles.headerMeta}>
              <span className={`${styles.badge} ${collection.is_public ? styles.public : ""}`}>
                {collection.is_public ? "Public" : "Private"}
              </span>
              <span className={styles.metaText}>
                {collection.items.length} item{collection.items.length !== 1 ? "s" : ""}
              </span>
              <span className={styles.metaText}>
                Updated {formatDate(collection.updated_at)}
              </span>
            </div>
            {collection.description && (
              <p className={styles.description}>{collection.description}</p>
            )}
          </div>

          <div className={styles.headerActions}>
            <button
              type="button"
              className={`${styles.actionButton} ${styles.danger}`}
              onClick={() => setShowDeleteDialog(true)}
            >
              Delete
            </button>
          </div>
        </div>
      </header>

      <main className={styles.content}>
        {collection.items.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>📂</div>
            <h2>This collection is empty</h2>
            <p>
              Add documents, chat sessions, or other items to this collection from their respective pages.
            </p>
          </div>
        ) : (
          <div className={styles.itemGroups}>
            {nonEmptyGroups.map((type) => (
              <div key={type} className={styles.itemGroup}>
                <div className={styles.itemGroupHeader}>
                  <h2 className={styles.itemGroupTitle}>
                    <span aria-hidden="true">{ITEM_TYPE_ICONS[type]}</span>
                    {ITEM_TYPE_LABELS[type]}
                    <span className={styles.itemGroupCount}>
                      ({itemsByType[type].length})
                    </span>
                  </h2>
                </div>
                <ul className={styles.itemList}>
                  {itemsByType[type].map((item) => (
                    <li key={item.id} className={styles.itemRow}>
                      <div className={styles.itemInfo}>
                        <p className={styles.itemTitle}>
                          {type === "document" && (
                            <Link href={`/doc/${item.item_id}`}>
                              Document: {item.item_id}
                            </Link>
                          )}
                          {type === "chat_session" && (
                            <Link href={`/chat/${item.item_id}`}>
                              Chat: {item.item_id}
                            </Link>
                          )}
                          {type === "research_note" && `Note: ${item.item_id}`}
                          {type === "passage" && `Passage: ${item.item_id}`}
                        </p>
                        <p className={styles.itemMeta}>
                          Added {formatDate(item.created_at)}
                        </p>
                        {item.notes && (
                          <p className={styles.itemNotes}>&quot;{item.notes}&quot;</p>
                        )}
                      </div>
                      <button
                        type="button"
                        className={styles.removeButton}
                        onClick={() => handleRemoveItem(item.id)}
                        disabled={removingItemId === item.id}
                        aria-label={`Remove item from collection`}
                      >
                        {removingItemId === item.id ? "Removing..." : "Remove"}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogTitle>Delete Collection</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete &quot;{collection.name}&quot;?
          </DialogDescription>
          <p className={styles.confirmText}>
            This action cannot be undone. All items will be removed from this collection,
            but the original documents and chats will not be deleted.
          </p>
          <DialogActions>
            <DialogClose asChild>
              <button type="button" className={styles.actionButton}>
                Cancel
              </button>
            </DialogClose>
            <button
              type="button"
              className={`${styles.actionButton} ${styles.danger}`}
              onClick={handleDeleteCollection}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete Collection"}
            </button>
          </DialogActions>
        </DialogContent>
      </Dialog>
    </div>
  );
}
