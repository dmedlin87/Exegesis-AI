import { useInsertionEffect, useRef } from "react";

/**
 * Returns a ref that always contains the latest value.
 *
 * This is useful when you need to access the current value inside callbacks
 * without adding it to dependency arrays (which would cause the callback to
 * be recreated on every change).
 *
 * This pattern avoids the anti-pattern of syncing state to refs via useEffect.
 * useInsertionEffect runs synchronously before any DOM mutations, ensuring
 * the ref is always up-to-date before any effects or event handlers run.
 *
 * When React's useEffectEvent becomes stable, consider migrating to that API
 * for callbacks that need to read "latest" values without re-creating.
 *
 * @example
 * ```tsx
 * const conversationRef = useLatest(conversation);
 *
 * const handleSubmit = useCallback(() => {
 *   // Always reads the latest conversation, no stale closure
 *   const current = conversationRef.current;
 *   sendMessage(current);
 * }, []); // Empty deps - callback identity is stable
 * ```
 */
export function useLatest<T>(value: T) {
  const ref = useRef<T>(value);

  // useInsertionEffect runs synchronously before layout effects,
  // ensuring the ref is updated before any other effects read it.
  // This is safer than useEffect for this pattern.
  useInsertionEffect(() => {
    ref.current = value;
  });

  return ref;
}
