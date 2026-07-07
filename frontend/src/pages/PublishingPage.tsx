import { useState } from "react";
import {
  getCategoryAttributes,
  getCategoryPredictions,
  getDraftListingConfig,
  getListingTypes,
  listPublishJobs,
  previewPublishFromDraft,
  saveDraftListingConfig,
  type DraftListingConfig,
  type PublishJobRecord,
  type PublishValidationResult,
} from "../api/client";
import type { ProductDraft } from "../api/client";

export function PublishingPage({
  draft,
  draftId,
  review,
}: {
  draft: ProductDraft | null;
  draftId: number | null;
  review: Record<string, unknown> | null;
}) {
  const ready = Boolean(draft && review?.decision === "pass");
  const [listingTypes, setListingTypes] = useState<string[]>([]);
  const [listingTypeId, setListingTypeId] = useState("");
  const [fulfillment, setFulfillment] = useState("not_full");
  const [categoryId, setCategoryId] = useState("");
  const [attributesText, setAttributesText] = useState("[]");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [attributes, setAttributes] = useState<Record<string, unknown>[]>([]);
  const [savedConfig, setSavedConfig] = useState<DraftListingConfig | null>(null);
  const [preview, setPreview] = useState<PublishValidationResult | null>(null);
  const [jobs, setJobs] = useState<PublishJobRecord[]>([]);
  const [status, setStatus] = useState("");

  async function loadListingTypes() {
    if (!draft) return;
    setStatus("Loading listing types");
    try {
      const result = await getListingTypes(draft.target_site_id);
      setListingTypes(result.listing_type_ids);
      if (!listingTypeId && result.listing_type_ids.length > 0) {
        setListingTypeId(result.listing_type_ids[0]);
      }
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

  async function loadSavedConfig() {
    if (!draftId) return;
    setStatus("Loading saved listing config");
    try {
      const config = await getDraftListingConfig(draftId);
      setSavedConfig(config);
      setCategoryId(config.category_id);
      setListingTypeId(config.listing_type_id);
      setFulfillment(config.fulfillment);
      setAttributesText(JSON.stringify(config.attributes, null, 2));
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load listing config");
    }
  }

  async function saveConfig() {
    if (!draft || !draftId) return;
    setStatus("Saving listing config");
    try {
      const parsedAttributes = JSON.parse(attributesText || "[]");
      const config = await saveDraftListingConfig(draftId, {
        site_id: draft.target_site_id,
        category_id: categoryId,
        listing_type_id: listingTypeId,
        fulfillment,
        attributes: parsedAttributes,
      });
      setSavedConfig(config);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to save listing config");
    }
  }

  async function previewSavedConfig() {
    if (!draftId || !review) return;
    setStatus("Creating publish preview");
    try {
      setPreview(await previewPublishFromDraft(draftId, review, listingTypes, true));
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to create publish preview");
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
      {draftId && <p>Current draft ID: {draftId}</p>}
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
      <label>
        Listing Type
        <input value={listingTypeId} onChange={(event) => setListingTypeId(event.target.value)} />
      </label>
      <label>
        Fulfillment
        <select value={fulfillment} onChange={(event) => setFulfillment(event.target.value)}>
          <option value="not_full">Not FULL</option>
          <option value="classic">Classic</option>
          <option value="pre">Pre</option>
        </select>
      </label>
      <label>
        Attribute Values JSON
        <textarea
          value={attributesText}
          onChange={(event) => setAttributesText(event.target.value)}
        />
      </label>
      <div className="button-row">
        <button disabled={!categoryId} onClick={loadAttributes}>
          Load Attributes
        </button>
        <button disabled={!draftId} onClick={loadSavedConfig}>
          Load Saved Config
        </button>
        <button disabled={!draftId || !categoryId || !listingTypeId} onClick={saveConfig}>
          Save Listing Config
        </button>
      </div>
      {status && <p>{status}</p>}
      <button disabled={!ready || !draftId || listingTypes.length === 0} onClick={previewSavedConfig}>
        Create Publish Preview
      </button>
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
      {savedConfig && (
        <>
          <h3>Saved Listing Config</h3>
          <pre>{JSON.stringify(savedConfig, null, 2)}</pre>
        </>
      )}
      {preview && (
        <>
          <h3>Publish Preview</h3>
          <pre>{JSON.stringify(preview, null, 2)}</pre>
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
