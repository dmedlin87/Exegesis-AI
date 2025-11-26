"use client";

import type { FormEvent } from "react";

import { SavedSearchControls } from "./SavedSearchControls";
import styles from "./SearchPageClient.module.css";
import additionalStyles from "./SearchPageClient-additions.module.css";
import type { FilterDisplay, SavedSearch } from "./filters/types";

interface SavedSearchManagerProps {
  isAdvancedUi: boolean;
  savedSearchName: string;
  onSavedSearchNameChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  savedSearches: SavedSearch[];
  onApplySavedSearch: (saved: SavedSearch) => void;
  onDeleteSavedSearch: (id: string) => void;
  formatFilters: (filters: SavedSearch["filters"]) => FilterDisplay;
}

export function SavedSearchManager({
  isAdvancedUi,
  savedSearchName,
  onSavedSearchNameChange,
  onSubmit,
  savedSearches,
  onApplySavedSearch,
  onDeleteSavedSearch,
  formatFilters,
}: SavedSearchManagerProps) {
  const content = (
    <SavedSearchControls
      savedSearchName={savedSearchName}
      onSavedSearchNameChange={onSavedSearchNameChange}
      onSubmit={onSubmit}
      savedSearches={savedSearches}
      onApplySavedSearch={onApplySavedSearch}
      onDeleteSavedSearch={onDeleteSavedSearch}
      formatFilters={formatFilters}
    />
  );

  if (isAdvancedUi) {
    return (
      <section aria-label="Saved searches" className={styles["search-saved-section"]}>
        <h3>Saved searches</h3>
        {content}
      </section>
    );
  }

  return (
    <details
      className={`${styles["search-advanced-details"]} ${additionalStyles.savedSearchesDetails}`}
    >
      <summary className={styles["search-advanced-summary"]}>Saved searches</summary>
      <p className={styles["search-advanced-help"]}>
        Expand to store or recall presets. Saved searches remember every active filter.
      </p>
      {content}
    </details>
  );
}
