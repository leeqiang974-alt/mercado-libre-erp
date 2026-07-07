import type { ProductDraft } from "../api/client";

export function PublishingPage({
  draft,
  review,
}: {
  draft: ProductDraft | null;
  review: Record<string, unknown> | null;
}) {
  const ready = Boolean(draft && review?.decision === "pass");
  return (
    <section className="panel">
      <h2>Publish Queue</h2>
      <p>
        {ready
          ? "Ready for non-FULL Mercado Libre publish preview."
          : "Import and pass review before publishing."}
      </p>
      <button disabled={!ready}>Create Publish Preview</button>
    </section>
  );
}
