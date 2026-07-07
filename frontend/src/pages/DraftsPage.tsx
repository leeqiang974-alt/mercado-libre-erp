import { useEffect, useState } from "react";
import {
  listDrafts,
  listReviewHistory,
  reviewDraftWithProvider,
  type ProductDraftRead,
  type ReviewResult,
} from "../api/client";
import type { ProductDraft } from "../api/client";

export function DraftsPage({
  draft,
  draftId,
  review,
}: {
  draft: ProductDraft | null;
  draftId: number | null;
  review: Record<string, unknown> | null;
}) {
  const [savedDrafts, setSavedDrafts] = useState<ProductDraftRead[]>([]);
  const [providerReview, setProviderReview] = useState<Record<string, unknown> | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewResult[]>([]);
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
      const nextReview = await reviewDraftWithProvider(draft, provider, draftId);
      setProviderReview(nextReview);
      if (draftId) {
        setReviewHistory(await listReviewHistory(draftId));
      }
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "Provider review failed");
    }
  }

  async function refreshReviewHistory() {
    if (!draftId) return;
    setError("");
    try {
      setReviewHistory(await listReviewHistory(draftId));
    } catch (historyError) {
      setError(historyError instanceof Error ? historyError.message : "Failed to load review history");
    }
  }

  return (
    <section className="panel">
      <h2>Draft Review</h2>
      {!draft && <p>No draft imported yet.</p>}
      {draftId && <p>Current draft ID: {draftId}</p>}
      {draft && <pre>{JSON.stringify({ draft, review }, null, 2)}</pre>}
      <div className="button-row">
        <button disabled={!draft} onClick={() => runProviderReview("claude")}>
          Claude Review
        </button>
        <button disabled={!draft} onClick={() => runProviderReview("nvidia")}>
          NVIDIA Review
        </button>
        <button disabled={!draftId} onClick={refreshReviewHistory}>
          Refresh Review History
        </button>
      </div>
      {providerReview && (
        <>
          <h3>Provider Review</h3>
          <pre>{JSON.stringify(providerReview, null, 2)}</pre>
        </>
      )}
      {reviewHistory.length > 0 && (
        <>
          <h3>Review History</h3>
          <pre>{JSON.stringify(reviewHistory, null, 2)}</pre>
        </>
      )}
      <h3>Saved Drafts</h3>
      {error && <p className="error">{error}</p>}
      {savedDrafts.length === 0 && <p>No saved drafts yet.</p>}
      {savedDrafts.length > 0 && <pre>{JSON.stringify(savedDrafts, null, 2)}</pre>}
    </section>
  );
}
