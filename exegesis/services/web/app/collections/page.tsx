"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";
import {
    Dialog,
    DialogActions,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogTitle,
} from "../components/ui/dialog";
import type {
    CollectionSummary,
    CreateCollectionPayload,
} from "../lib/api-client";
import styles from "./collections.module.css";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isPublic, setIsPublic] = useState(false);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch("/api/collections");
      if (!response.ok) throw new Error("Failed to load collections");
      const data = await response.json();
      setCollections(data.items || []);
    } catch (err) {
      console.error("Error loading collections:", err);
      setError("Failed to load collections. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCollection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      setCreating(true);
      const payload: CreateCollectionPayload = {
        name: name.trim(),
        description: description.trim() || null,
        is_public: isPublic,
      };

      const response = await fetch("/api/collections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error("Failed to create collection");

      const newCollection = await response.json();
      setCollections((prev) => [
        {
          ...newCollection,
          item_count: 0,
        },
        ...prev,
      ]);

      // Reset form
      setName("");
      setDescription("");
      setIsPublic(false);
      setShowCreateModal(false);
    } catch (err) {
      console.error("Error creating collection:", err);
      setError("Failed to create collection. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  const stats = {
    total: collections.length,
    public: collections.filter((c) => c.is_public).length,
    private: collections.filter((c) => !c.is_public).length,
    totalItems: collections.reduce((sum, c) => sum + c.item_count, 0),
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <div className={styles.headerText}>
            <h1>Collections</h1>
            <p className={styles.subtitle}>
              Organize your research materials into curated collections
            </p>
          </div>
          <button
            type="button"
            className={styles.createButton}
            onClick={() => setShowCreateModal(true)}
          >
            <span aria-hidden="true">+</span>
            New Collection
          </button>
        </div>

        <div className={styles.stats}>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.total}</span>
            <span className={styles.statLabel}>Collections</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.totalItems}</span>
            <span className={styles.statLabel}>Items</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.public}</span>
            <span className={styles.statLabel}>Public</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.private}</span>
            <span className={styles.statLabel}>Private</span>
          </div>
        </div>
      </header>

      <main className={styles.content}>
        {loading && collections.length === 0 ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <p>Loading collections...</p>
          </div>
        ) : error ? (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>⚠️</div>
            <h2>Error</h2>
            <p>{error}</p>
            <button
              type="button"
              className={styles.createButton}
              onClick={loadCollections}
            >
              Try Again
            </button>
          </div>
        ) : collections.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>📚</div>
            <h2>No collections yet</h2>
            <p>
              Create your first collection to start organizing your research
              materials, documents, and chat sessions.
            </p>
            <button
              type="button"
              className={styles.createButton}
              onClick={() => setShowCreateModal(true)}
            >
              <span aria-hidden="true">+</span>
              Create Your First Collection
            </button>
          </div>
        ) : (
          <div className={styles.grid}>
            {collections.map((collection) => (
              <Link
                key={collection.id}
                href={`/collections/${collection.id}`}
                className={styles.card}
              >
                <div className={styles.cardHeader}>
                  <h2 className={styles.cardTitle}>{collection.name}</h2>
                  <span
                    className={`${styles.cardBadge} ${collection.is_public ? styles.public : ""}`}
                  >
                    {collection.is_public ? "Public" : "Private"}
                  </span>
                </div>
                {collection.description && (
                  <p className={styles.cardDescription}>
                    {collection.description}
                  </p>
                )}
                <div className={styles.cardMeta}>
                  <span className={styles.cardItemCount}>
                    📄 {collection.item_count} item
                    {collection.item_count !== 1 ? "s" : ""}
                  </span>
                  <span>Updated {formatDate(collection.updated_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>

      {/* Create Collection Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent>
          <DialogTitle>Create New Collection</DialogTitle>
          <DialogDescription>
            Give your collection a name and optional description.
          </DialogDescription>

          <form onSubmit={handleCreateCollection}>
            <div className={styles.formGroup}>
              <label htmlFor="name" className={styles.formLabel}>
                Name <span className={styles.required}>*</span>
              </label>
              <input
                id="name"
                type="text"
                className={styles.formInput}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Pauline Theology Research"
                maxLength={255}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label htmlFor="description" className={styles.formLabel}>
                Description
              </label>
              <textarea
                id="description"
                className={`${styles.formInput} ${styles.formTextarea}`}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this collection contains..."
                maxLength={2000}
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.formCheckbox}>
                <input
                  type="checkbox"
                  checked={isPublic}
                  onChange={(e) => setIsPublic(e.target.checked)}
                />
                <span>Make this collection public</span>
              </label>
            </div>

            <DialogActions>
              <DialogClose asChild>
                <button type="button" className={styles.cancelButton}>
                  Cancel
                </button>
              </DialogClose>
              <button
                type="submit"
                className={styles.submitButton}
                disabled={!name.trim() || creating}
              >
                {creating ? "Creating..." : "Create Collection"}
              </button>
            </DialogActions>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
