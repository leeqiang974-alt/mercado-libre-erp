import { useEffect, useState } from "react";
import { listDrafts, reviewDraftWithProvider, type ProductDraftRead } from "../api/client";
import type { ProductDraft } from "../api/client";

export function DraftsPage({
  draft,
  review,
}: {
  draft: ProductDraft | null;
  review: Record<string, unknown> | null;
}) {
  const [savedDrafts, setSavedDrafts] = useState<ProductDraftRead[]>([]);
  const [providerReview, setProviderReview] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listDrafts()
      .then(setSavedDrafts)
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load drafts"),
      );
  }, []);

  async function runProviderReview(provider: "claude" | "nvidia") {
    if (!draft) return;
    setError("");
    try {
      setProviderReview(await reviewDraftWithProvider(draft, provider));
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "Provider review failed");
    }
  }

  return (
    <section className="panel">
      <h2>Draft Review</h2>
      {!draft && <p>No draft imported yet.</p>}
      {draft && <pre>{JSON.stringify({ draft, review }, null, 2)}</pre>}
      <div className="button-row">
        <button disabled={!draft} onClick={() => runProviderReview("claude")}>
          Claude Review
        </button>
        <button disabled={!draft} onClick={() => runProviderReview("nvidia")}>
          NVIDIA Review
        </button>
      </div>
      {providerReview && (
        <>
          <h3>Provider Review</h3>
          <pre>{JSON.stringify(providerReview, null, 2)}</pre>
        </>
      )}
      <h3>Saved Drafts</h3>
      {error && <p className="error">{error}</p>}
      {savedDrafts.length === 0 && <p>No saved drafts yet.</p>}
      {savedDrafts.length > 0 && <pre>{JSON.stringify(savedDrafts, null, 2)}</pre>}
    </section>
  );
}
