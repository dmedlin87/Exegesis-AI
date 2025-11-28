"use client";

import { FormEvent, useEffect, useId, useMemo, useState } from "react";

import type {
  TheologicalLens,
  TheologicalLensRequest,
  TheologicalLensResponse,
  TheoApiClient,
} from "../../lib/api-client";
import styles from "../settings.module.css";

type TheologicalLensCardProps = {
  client: TheoApiClient;
};

type OperationState =
  | { status: "idle"; message: string | null }
  | { status: "loading"; message: string | null }
  | { status: "saving"; message: string | null }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

const THEOLOGICAL_LENSES: TheologicalLens[] = [
  "General",
  "Historical-Critical",
  "Patristic",
  "Reformational",
  "Modern",
];

const LENS_DESCRIPTIONS: Record<TheologicalLens, string> = {
  General: "No specific theological perspective applied",
  "Historical-Critical":
    "Emphasizes historical context, textual criticism, and original author intent",
  Patristic: "Focuses on early church fathers and patristic interpretations",
  Reformational: "Prioritizes Reformation-era perspectives and sola scriptura",
  Modern: "Incorporates contemporary theological scholarship and modern methods",
};

export default function TheologicalLensCard({
  client,
}: TheologicalLensCardProps): JSX.Element {
  const titleId = useId();
  const descriptionId = useId();
  const lensSelectId = useId();

  const [selectedLens, setSelectedLens] = useState<TheologicalLens>("General");
  const [status, setStatus] = useState<OperationState>({
    status: "idle",
    message: null,
  });

  useEffect(() => {
    let cancelled = false;
    const loadLens = async () => {
      setStatus({ status: "loading", message: "Loading theological lens..." });
      try {
        const response = await client.getTheologicalLens();
        if (!cancelled) {
          setSelectedLens(response.theological_lens);
          setStatus({ status: "idle", message: null });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error && error.message
            ? error.message
            : "Failed to load theological lens";
        setStatus({ status: "error", message });
      }
    };
    loadLens();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload: TheologicalLensRequest = {
      theological_lens: selectedLens,
    };

    setStatus({ status: "saving", message: "Saving theological lens..." });
    try {
      const result = await client.updateTheologicalLens(payload);
      setSelectedLens(result.theological_lens);
      setStatus({ status: "success", message: "Theological lens saved." });
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Failed to save theological lens";
      setStatus({ status: "error", message });
    }
  };

  const statusClass = useMemo(() => {
    switch (status.status) {
      case "success":
        return `${styles.status} ${styles.statusSuccess}`;
      case "error":
        return `${styles.status} ${styles.statusError}`;
      case "loading":
      case "saving":
        return `${styles.status} ${styles.statusInfo}`;
      default:
        return `${styles.status} ${styles.statusInfo}`;
    }
  }, [status.status]);

  return (
    <article
      className={styles.card}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      <header className={styles.cardHeader}>
        <h3 id={titleId} className={styles.cardTitle}>
          Theological Lens
        </h3>
        <span className={styles.badge} aria-live="polite">
          {selectedLens}
        </span>
      </header>
      <p id={descriptionId} className={styles.helperText}>
        Select a theological perspective to influence how the RAG system
        contextualizes biblical passages and commentary.
      </p>
      <form className={styles.formGrid} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label htmlFor={lensSelectId} className={styles.label}>
            Interpretation lens
          </label>
          <select
            id={lensSelectId}
            className={styles.input}
            value={selectedLens}
            onChange={(event) =>
              setSelectedLens(event.target.value as TheologicalLens)
            }
            disabled={status.status === "saving" || status.status === "loading"}
          >
            {THEOLOGICAL_LENSES.map((lens) => (
              <option key={lens} value={lens}>
                {lens}
              </option>
            ))}
          </select>
          <p className={styles.helperText}>
            {LENS_DESCRIPTIONS[selectedLens]}
          </p>
        </div>

        <div className={styles.buttonRow}>
          <button
            type="submit"
            className={`${styles.button} ${styles.buttonPrimary}`}
            disabled={status.status === "saving" || status.status === "loading"}
          >
            {status.status === "saving" ? "Saving…" : "Save lens"}
          </button>
        </div>

        {status.message ? (
          <p role="status" className={statusClass}>
            {status.message}
          </p>
        ) : null}
      </form>
    </article>
  );
}
