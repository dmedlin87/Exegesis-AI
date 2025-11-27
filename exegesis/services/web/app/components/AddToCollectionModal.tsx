"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type {
    AddCollectionItemPayload,
    CollectionItemType,
    CollectionSummary,
} from "../lib/api-client";
import styles from "./AddToCollectionModal.module.css";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "./ui/dialog";

export interface AddToCollectionModalProps {
  /** Whether the modal is open */
  open: boolean;
  /** Callback when open state changes */
  onOpenChange: (open: boolean) => void;
  /** Type of item being added */
  itemType: CollectionItemType;
  /** ID of the item being added */
  itemId: string;
  /** Optional display name for the item */
  itemName?: string;
  /** Callback when item is successfully added */
  onSuccess?: (collectionId: string) => void;
}

/**
 * Reusable modal component for adding items to collections.
 * Can be used on Document, Chat, or other pages to let users
 * organize items into their collections.
 */
export function AddToCollectionModal({
  open,
  onOpenChange,
  itemType,
  itemId,
  itemName,
  onSuccess,
}: AddToCollectionModalProps): JSX.Element {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [adding, setAdding] = useState(false);
  const [success, setSuccess] = useState(false);

  const loadCollections = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("/api/collections?include_public=false");
      if (!response.ok) throw new Error("Failed to load collections");
      const data = await response.json();
      setCollections(data.items || []);
    } catch (err) {
      console.error("Error loading collections:", err);
      setError("Failed to load collections");
    } finally {
      setLoading(false);
    }
  }, []);

  // Load collections when modal opens
  useEffect(() => {
    if (open) {
      loadCollections();
      // Reset state when opening
      setSelectedCollectionId(null);
      setNotes("");
      setSuccess(false);
      setError(null);
    }
  }, [open, loadCollections]);

  const handleAddToCollection = async () => {
    if (!selectedCollectionId) return;

    try {
      setAdding(true);
      setError(null);

      const payload: AddCollectionItemPayload = {
        item_type: itemType,
        item_id: itemId,
        notes: notes.trim() || null,
      };

      const response = await fetch(
        `/api/collections/${encodeURIComponent(selectedCollectionId)}/items`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to add item to collection");
      }

      setSuccess(true);
      onSuccess?.(selectedCollectionId);

      // Close modal after short delay to show success
      setTimeout(() => {
        onOpenChange(false);
      }, 1500);
    } catch (err) {
      console.error("Error adding to collection:", err);
      setError(err instanceof Error ? err.message : "Failed to add item to collection");
    } finally {
      setAdding(false);
    }
  };

  const itemTypeLabel =
    itemType === "document"
      ? "document"
      : itemType === "chat_session"
        ? "chat session"
        : itemType === "research_note"
          ? "research note"
          : "passage";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Add to Collection</DialogTitle>
        <DialogDescription>
          Choose a collection for this {itemTypeLabel}
          {itemName ? `: "${itemName}"` : ""}.
        </DialogDescription>

        {error && <div className={styles.error}>{error}</div>}

        {success ? (
          <div className={styles.success}>
            Successfully added to collection!
          </div>
        ) : loading ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <p>Loading collections...</p>
          </div>
        ) : collections.length === 0 ? (
          <div className={styles.empty}>
            <p>You don&apos;t have any collections yet.</p>
            <Link
              href="/collections"
              className={styles.createLink}
              onClick={() => onOpenChange(false)}
            >
              Create a Collection
            </Link>
          </div>
        ) : (
          <>
            <div className={styles.collectionList} role="radiogroup" aria-label="Select a collection">
              {collections.map((collection) => (
                <button
                  key={collection.id}
                  type="button"
                  className={`${styles.collectionOption} ${
                    selectedCollectionId === collection.id ? styles.selected : ""
                  }`}
                  onClick={() => setSelectedCollectionId(collection.id)}
                  disabled={adding}
                  role="radio"
                  aria-checked={selectedCollectionId === collection.id}
                >
                  <input
                    type="radio"
                    className={styles.collectionRadio}
                    checked={selectedCollectionId === collection.id}
                    onChange={() => setSelectedCollectionId(collection.id)}
                    tabIndex={-1}
                    aria-hidden="true"
                  />
                  <div className={styles.collectionInfo}>
                    <p className={styles.collectionName}>{collection.name}</p>
                    <div className={styles.collectionMeta}>
                      <span>
                        {collection.item_count} item{collection.item_count !== 1 ? "s" : ""}
                      </span>
                      <span className={`${styles.badge} ${collection.is_public ? styles.public : ""}`}>
                        {collection.is_public ? "Public" : "Private"}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <div className={styles.notesSection}>
              <label htmlFor="collection-notes" className={styles.notesLabel}>
                Notes (optional)
              </label>
              <textarea
                id="collection-notes"
                className={styles.notesInput}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add a note about why you're saving this..."
                maxLength={5000}
                disabled={adding}
              />
            </div>

            <div className={styles.actions}>
              <DialogClose asChild>
                <button type="button" className={styles.cancelButton} disabled={adding}>
                  Cancel
                </button>
              </DialogClose>
              <button
                type="button"
                className={styles.addButton}
                onClick={handleAddToCollection}
                disabled={!selectedCollectionId || adding}
              >
                {adding ? "Adding..." : "Add to Collection"}
              </button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default AddToCollectionModal;
