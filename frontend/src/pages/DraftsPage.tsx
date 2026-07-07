import type { ProductDraft } from "../api/client";

export function DraftsPage({
  draft,
  review,
}: {
  draft: ProductDraft | null;
  review: Record<string, unknown> | null;
}) {
  return (
    <section className="panel">
      <h2>Draft Review</h2>
      {!draft && <p>No draft imported yet.</p>}
      {draft && <pre>{JSON.stringify({ draft, review }, null, 2)}</pre>}
    </section>
  );
}
