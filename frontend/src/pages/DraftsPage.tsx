import { useEffect, useState } from "react";
import { listDrafts, type ProductDraftRead } from "../api/client";
import type { ProductDraft } from "../api/client";

export function DraftsPage({
  draft,
  review,
}: {
  draft: ProductDraft | null;
  review: Record<string, unknown> | null;
}) {
  const [savedDrafts, setSavedDrafts] = useState<ProductDraftRead[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listDrafts()
      .then(setSavedDrafts)
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load drafts"),
      );
  }, []);

  return (
    <section className="panel">
      <h2>Draft Review</h2>
      {!draft && <p>No draft imported yet.</p>}
      {draft && <pre>{JSON.stringify({ draft, review }, null, 2)}</pre>}
      <h3>Saved Drafts</h3>
      {error && <p className="error">{error}</p>}
      {savedDrafts.length === 0 && <p>No saved drafts yet.</p>}
      {savedDrafts.length > 0 && <pre>{JSON.stringify(savedDrafts, null, 2)}</pre>}
    </section>
  );
}
