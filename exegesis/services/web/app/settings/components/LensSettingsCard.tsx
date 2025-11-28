"use client";

import { FormEvent, useEffect, useId, useMemo, useState } from "react";

import type { TheoApiClient } from "../../lib/api-client";
import styles from "../settings.module.css";

type TheologicalLens = "General" | "Historical-Critical" | "Patristic" | "Reformational" | "Modern";

type LensSettingsCardProps = {
  client: TheoApiClient;
};

type OperationState =
  | { status: "idle"; message: string | null }
  | { status: "saving"; message: string | null }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

const THEOLOGICAL_LENS_OPTIONS: { value: TheologicalLens; label: string; description: string }[] = [
  {
    value: "General",
    label: "General",
    description: "Balanced interpretations from multiple theological traditions",
  },
  {
    value: "Historical-Critical",
    label: "Historical-Critical",
    description: "Focus on original languages, historical context, and archaeological evidence",
  },
  {
    value: "Patristic",
    label: "Patristic",
    description: "Emphasize early church fathers and patristic exegesis",
  },
  {
    value: "Reformational",
    label: "Reformational",
    description: "Reformation principles and grammatical-historical exegesis",
  },
  {
    value: "Modern",
    label: "Modern",
    description: "Contemporary scholarship and modern critical methods",
  },
];

export default function LensSettingsCard({ client }: LensSettingsCardProps): JSX.Element {
  const titleId = useId();
  const descriptionId = useId();
  const lensId = useId();

  const [theologicalLens, setTheologicalLens] = useState<TheologicalLens>("General");
  const [status, setStatus] = useState<OperationState>({ status: "idle", message: null });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const response = await fetch(
          `${client.baseUrl}/settings/ai/user-preferences`,
          {
            headers: client._headers(),
          }
        );
        if (response.ok) {
          const data = await response.json();
          setTheologicalLens(data.theological_lens || "General");
        }
      } catch (error) {
        console.error("Failed to load theological lens preference:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadPreferences();
  }, [client]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setStatus({ status: "saving", message: "Saving theological lens preference…" });
    try {
      const response = await fetch(
        `${client.baseUrl}/settings/ai/user-preferences`,
        {
          method: "PUT",
          headers: {
            ...client._headers(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ theological_lens: theologicalLens }),
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to save: ${response.statusText}`);
      }

      const result = await response.json();
      setTheologicalLens(result.theological_lens);
      setStatus({ status: "success", message: "Theological lens preference saved." });
    } catch (error) {
      const message =
        error instanceof Error && error.message ? error.message : "Failed to save preference";
      setStatus({ status: "error", message });
    }
  };

  const statusClass = useMemo(() => {
    switch (status.status) {
      case "success":
        return `${styles.status} ${styles.statusSuccess}`;
      case "error":
        return `${styles.status} ${styles.statusError}`;
      case "saving":
        return `${styles.status} ${styles.statusInfo}`;
      default:
        return `${styles.status} ${styles.statusInfo}`;
    }
  }, [status.status]);

  const selectedOption = THEOLOGICAL_LENS_OPTIONS.find((opt) => opt.value === theologicalLens);

  return (
    <article className={styles.card} aria-labelledby={titleId} aria-describedby={descriptionId}>
      <header className={styles.cardHeader}>
        <h3 id={titleId} className={styles.cardTitle}>
          Theological Lens
        </h3>
      </header>
      <p id={descriptionId} className={styles.helperText}>
        Choose your preferred theological interpretive framework for AI-generated insights.
        This setting influences how the system contextualizes and prioritizes commentary.
      </p>
      {isLoading ? (
        <p className={styles.helperText}>Loading preferences…</p>
      ) : (
        <form className={styles.formGrid} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor={lensId} className={styles.label}>
              Interpretive Framework
            </label>
            <select
              id={lensId}
              className={styles.input}
              value={theologicalLens}
              onChange={(event) => setTheologicalLens(event.target.value as TheologicalLens)}
            >
              {THEOLOGICAL_LENS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {selectedOption && (
              <p className={styles.helperText}>{selectedOption.description}</p>
            )}
          </div>

          <div className={styles.buttonRow}>
            <button
              type="submit"
              className={`${styles.button} ${styles.buttonPrimary}`}
              disabled={status.status === "saving"}
            >
              {status.status === "saving" ? "Saving…" : "Save preference"}
            </button>
          </div>

          {status.message ? (
            <p role="status" className={statusClass}>
              {status.message}
            </p>
          ) : null}
        </form>
      )}
    </article>
  );
}
