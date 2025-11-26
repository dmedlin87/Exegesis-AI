"use client";

import {
  COLLECTION_FACETS,
  CUSTOM_PRESET_VALUE,
  DATASET_FILTERS,
  DOMAIN_OPTIONS,
  MODE_PRESETS,
  SOURCE_OPTIONS,
  TRADITION_OPTIONS,
  VARIANT_FILTERS,
} from "./filters/constants";
import styles from "./SearchPageClient.module.css";
import additionalStyles from "./SearchPageClient-additions.module.css";

interface AdvancedSearchFiltersProps {
  activePreset: (typeof MODE_PRESETS)[number] | undefined;
  presetSelection: string;
  presetIsCustom: boolean;
  isAdvancedUi: boolean;
  isSearching: boolean;
  isPresetPending: boolean;
  collection: string;
  author: string;
  sourceType: string;
  theologicalTradition: string;
  topicDomain: string;
  collectionFacets: string[];
  datasetFacets: string[];
  variantFacets: string[];
  dateStart: string;
  dateEnd: string;
  includeVariants: boolean;
  includeDisputed: boolean;
  onPresetChange: (value: string) => void;
  onCollectionChange: (value: string) => void;
  onAuthorChange: (value: string) => void;
  onSourceTypeChange: (value: string) => void;
  onTheologicalTraditionChange: (value: string) => void;
  onTopicDomainChange: (value: string) => void;
  onDateStartChange: (value: string) => void;
  onDateEndChange: (value: string) => void;
  onIncludeVariantsChange: (value: boolean) => void;
  onIncludeDisputedChange: (value: boolean) => void;
  onToggleCollectionFacet: (value: string) => void;
  onToggleDatasetFacet: (value: string) => void;
  onToggleVariantFacet: (value: string) => void;
  onMarkPresetAsCustom: () => void;
}

export function AdvancedSearchFilters({
  activePreset,
  presetSelection,
  presetIsCustom,
  isAdvancedUi,
  isSearching,
  isPresetPending,
  collection,
  author,
  sourceType,
  theologicalTradition,
  topicDomain,
  collectionFacets,
  datasetFacets,
  variantFacets,
  dateStart,
  dateEnd,
  includeVariants,
  includeDisputed,
  onPresetChange,
  onCollectionChange,
  onAuthorChange,
  onSourceTypeChange,
  onTheologicalTraditionChange,
  onTopicDomainChange,
  onDateStartChange,
  onDateEndChange,
  onIncludeVariantsChange,
  onIncludeDisputedChange,
  onToggleCollectionFacet,
  onToggleDatasetFacet,
  onToggleVariantFacet,
  onMarkPresetAsCustom,
}: AdvancedSearchFiltersProps) {
  const content = (
    <div className={styles["search-advanced-controls"]}>
      <div>
        <label className={styles["search-form__label"]}>
          <span className={styles["search-form__label-text"]}>Mode preset</span>
          <select
            name="preset"
            value={presetIsCustom ? CUSTOM_PRESET_VALUE : presetSelection}
            onChange={(event) => onPresetChange(event.target.value)}
            className={styles["search-form__select"]}
            disabled={isSearching || isPresetPending}
            aria-busy={isPresetPending}
          >
            {MODE_PRESETS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {activePreset?.description && (
          <p className={`${styles["search-advanced-help"]} ${additionalStyles.presetDescription}`}>
            {activePreset.description}
          </p>
        )}
      </div>
      <label className={styles["search-form__label"]}>
        <span className={styles["search-form__label-text"]}>Collection</span>
        <input
          name="collection"
          type="text"
          value={collection}
          onChange={(event) => {
            onCollectionChange(event.target.value);
            onMarkPresetAsCustom();
          }}
          placeholder="Gospels"
          className={styles["search-form__input"]}
        />
      </label>
      <label className={styles["search-form__label"]}>
        <span className={styles["search-form__label-text"]}>Author</span>
        <input
          name="author"
          type="text"
          value={author}
          onChange={(event) => {
            onAuthorChange(event.target.value);
            onMarkPresetAsCustom();
          }}
          placeholder="Jane Doe"
          className={styles["search-form__input"]}
        />
      </label>
      <label className={styles["search-form__label"]}>
        <span className={styles["search-form__label-text"]}>Source type</span>
        <select
          name="source_type"
          value={sourceType}
          onChange={(event) => {
            onSourceTypeChange(event.target.value);
            onMarkPresetAsCustom();
          }}
          className={styles["search-form__select"]}
        >
          {SOURCE_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className={styles["search-form__label"]}>
        <span className={styles["search-form__label-text"]}>Theological tradition</span>
        <select
          name="theological_tradition"
          value={theologicalTradition}
          onChange={(event) => {
            onTheologicalTraditionChange(event.target.value);
            onMarkPresetAsCustom();
          }}
          className={styles["search-form__select"]}
        >
          {TRADITION_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <label className={styles["search-form__label"]}>
        <span className={styles["search-form__label-text"]}>Topic domain</span>
        <select
          name="topic_domain"
          value={topicDomain}
          onChange={(event) => {
            onTopicDomainChange(event.target.value);
            onMarkPresetAsCustom();
          }}
          className={styles["search-form__select"]}
        >
          {DOMAIN_OPTIONS.map((option) => (
            <option key={option.value || "any"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <fieldset className={styles["search-fieldset"]}>
        <legend className={styles["search-fieldset__legend"]}>Collection facets</legend>
        <div className={styles["search-fieldset__grid"]}>
          {COLLECTION_FACETS.map((facet) => (
            <label key={facet} className={styles["search-fieldset__checkbox-label"]}>
              <input
                type="checkbox"
                checked={collectionFacets.includes(facet)}
                onChange={() => onToggleCollectionFacet(facet)}
              />
              {facet}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset className={styles["search-fieldset"]}>
        <legend className={styles["search-fieldset__legend"]}>Dataset facets</legend>
        <div className={styles["search-fieldset__grid"]}>
          {DATASET_FILTERS.map((dataset) => {
            const isActive = datasetFacets.includes(dataset.value);
            return (
              <label key={dataset.value} className={styles["search-dataset-item"]}>
                <span className={styles["search-dataset-item__header"]}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={() => onToggleDatasetFacet(dataset.value)}
                  />
                  <strong>{dataset.label}</strong>
                </span>
                <span className={styles["search-dataset-item__desc"]}>
                  {dataset.description}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <fieldset className={styles["search-fieldset"]}>
        <legend className={styles["search-fieldset__legend"]}>Variant focus</legend>
        <div className={styles["search-fieldset__grid"]}>
          {VARIANT_FILTERS.map((variant) => (
            <label key={variant.value} className={styles["search-fieldset__checkbox-label"]}>
              <input
                type="checkbox"
                checked={variantFacets.includes(variant.value)}
                onChange={() => onToggleVariantFacet(variant.value)}
              />
              {variant.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className={styles["search-date-fields"]}>
        <label className={styles["search-form__label"]}>
          <span className={styles["search-form__label-text"]}>Date from</span>
          <input
            type="date"
            name="date_start"
            value={dateStart}
            onChange={(event) => {
              onDateStartChange(event.target.value);
              onMarkPresetAsCustom();
            }}
            className={styles["search-form__input"]}
          />
        </label>
        <label className={styles["search-form__label"]}>
          <span className={styles["search-form__label-text"]}>Date to</span>
          <input
            type="date"
            name="date_end"
            value={dateEnd}
            onChange={(event) => {
              onDateEndChange(event.target.value);
              onMarkPresetAsCustom();
            }}
            className={styles["search-form__input"]}
          />
        </label>
      </div>
      <div className={styles["search-fieldset__grid"]}>
        <label className={styles["search-fieldset__checkbox-label"]}>
          <input
            type="checkbox"
            checked={includeVariants}
            onChange={(event) => {
              onIncludeVariantsChange(event.target.checked);
              onMarkPresetAsCustom();
            }}
          />
          Include textual variants
        </label>
        <label className={styles["search-fieldset__checkbox-label"]}>
          <input
            type="checkbox"
            checked={includeDisputed}
            onChange={(event) => {
              onIncludeDisputedChange(event.target.checked);
              onMarkPresetAsCustom();
            }}
          />
          Include disputed readings
        </label>
      </div>
    </div>
  );

  if (isAdvancedUi) {
    return content;
  }

  return (
    <details className={styles["search-advanced-details"]}>
      <summary className={styles["search-advanced-summary"]}>Advanced</summary>
      <p className={styles["search-advanced-help"]}>
        Expand to tune presets, guardrail filters, and dataset facets. Saved search tools live here too.
      </p>
      {content}
    </details>
  );
}
