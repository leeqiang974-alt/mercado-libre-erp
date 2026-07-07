import { useState } from "react";
import {
  getCategoryAttributes,
  getCategoryPredictions,
  getListingTypes,
  listPublishJobs,
  type PublishJobRecord,
} from "../api/client";
import type { ProductDraft } from "../api/client";

export function PublishingPage({
  draft,
  review,
}: {
  draft: ProductDraft | null;
  review: Record<string, unknown> | null;
}) {
  const ready = Boolean(draft && review?.decision === "pass");
  const [listingTypes, setListingTypes] = useState<string[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [attributes, setAttributes] = useState<Record<string, unknown>[]>([]);
  const [jobs, setJobs] = useState<PublishJobRecord[]>([]);
  const [status, setStatus] = useState("");

  async function loadListingTypes() {
    if (!draft) return;
    setStatus("Loading listing types");
    try {
      const result = await getListingTypes(draft.target_site_id);
      setListingTypes(result.listing_type_ids);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load listing types");
    }
  }

  async function predictDraftCategory() {
    if (!draft) return;
    setStatus("Predicting category");
    try {
      const result = await getCategoryPredictions(draft.target_site_id, draft.title);
      setPredictions(result.predictions);
      const first = result.predictions[0];
      if (first?.category_id && typeof first.category_id === "string") {
        setCategoryId(first.category_id);
      }
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to predict category");
    }
  }

  async function loadAttributes() {
    if (!categoryId) return;
    setStatus("Loading category attributes");
    try {
      const result = await getCategoryAttributes(categoryId);
      setAttributes(result.attributes);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load attributes");
    }
  }

  async function refreshJobs() {
    setStatus("Loading publish jobs");
    try {
      setJobs(await listPublishJobs());
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load publish jobs");
    }
  }

  return (
    <section className="panel">
      <h2>Publish Queue</h2>
      <p>
        {ready
          ? "Ready for non-FULL Mercado Libre publish preview."
          : "Import and pass review before publishing."}
      </p>
      <div className="button-row">
        <button disabled={!draft} onClick={loadListingTypes}>
          Load Listing Types
        </button>
        <button disabled={!draft} onClick={predictDraftCategory}>
          Predict Category
        </button>
      </div>
      <label>
        Category ID
        <input value={categoryId} onChange={(event) => setCategoryId(event.target.value)} />
      </label>
      <div className="button-row">
        <button disabled={!categoryId} onClick={loadAttributes}>
          Load Attributes
        </button>
      </div>
      {status && <p>{status}</p>}
      <button disabled={!ready}>Create Publish Preview</button>
      <div className="button-row">
        <button onClick={refreshJobs}>Refresh Publish Jobs</button>
      </div>
      {listingTypes.length > 0 && (
        <>
          <h3>Listing Types</h3>
          <pre>{JSON.stringify(listingTypes, null, 2)}</pre>
        </>
      )}
      {predictions.length > 0 && (
        <>
          <h3>Category Predictions</h3>
          <pre>{JSON.stringify(predictions, null, 2)}</pre>
        </>
      )}
      {attributes.length > 0 && (
        <>
          <h3>Category Attributes</h3>
          <pre>{JSON.stringify(attributes, null, 2)}</pre>
        </>
      )}
      {jobs.length > 0 && (
        <>
          <h3>Publish Jobs</h3>
          <pre>{JSON.stringify(jobs, null, 2)}</pre>
        </>
      )}
    </section>
  );
}
