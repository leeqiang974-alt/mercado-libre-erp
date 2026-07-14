import { useEffect, useState } from "react";
import {
  approveDraft,
  enqueuePublishFromDraft,
  executePublishFromDraft,
  getCategoryAttributes,
  getCategoryPredictions,
  getDraftListingConfig,
  getListingTypes,
  listPublishJobs,
  listStores,
  previewPublishFromDraft,
  refreshCategoryAttributes,
  refreshListingTypes,
  retryPublishJob,
  saveDraftListingConfig,
  type DraftListingConfig,
  type DraftApproval,
  type PublishExecutionResult,
  type PublishJobRecord,
  type PublishValidationResult,
  type StoreRecord,
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
  const [siteId, setSiteId] = useState(draft?.target_site_id ?? "MLM");
  const [listingTypes, setListingTypes] = useState<string[]>([]);
  const [listingTypeId, setListingTypeId] = useState("");
  const [fulfillment, setFulfillment] = useState("not_full");
  const [categoryId, setCategoryId] = useState("");
  const [attributesText, setAttributesText] = useState("[]");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [attributes, setAttributes] = useState<Record<string, unknown>[]>([]);
  const [savedConfig, setSavedConfig] = useState<DraftListingConfig | null>(null);
  const [approval, setApproval] = useState<DraftApproval | null>(null);
  const [preview, setPreview] = useState<PublishValidationResult | null>(null);
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [jobs, setJobs] = useState<PublishJobRecord[]>([]);
  const [retryingJobId, setRetryingJobId] = useState<number | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!draft) return;
    setSiteId(draft.target_site_id);
    setListingTypes([]);
    setListingTypeId("");
    setSavedConfig(null);
    setPreview(null);
    setApproval(null);
    setExecution(null);
  }, [draft?.target_site_id, draftId]);

  async function loadListingTypes() {
    if (!draft) return;
    setStatus("Loading listing types");
    try {
      const result = await getListingTypes(siteId);
      setListingTypes(result.listing_type_ids);
      if (!listingTypeId && result.listing_type_ids.length > 0) {
        setListingTypeId(result.listing_type_ids[0]);
      }
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load listing types");
    }
  }

  async function forceRefreshListingTypes() {
    if (!draft) return;
    setStatus("Refreshing listing types");
    try {
      const result = await refreshListingTypes(siteId);
      setListingTypes(result.listing_type_ids);
      if (result.listing_type_ids.length > 0) {
        setListingTypeId(result.listing_type_ids[0]);
      }
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to refresh listing types");
    }
  }

  async function predictDraftCategory() {
    if (!draft) return;
    setStatus("Predicting category");
    try {
      const result = await getCategoryPredictions(siteId, draft.title);
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

  async function forceRefreshAttributes() {
    if (!categoryId) return;
    setStatus("Refreshing category attributes");
    try {
      const result = await refreshCategoryAttributes(categoryId);
      setAttributes(result.attributes);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to refresh attributes");
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

  async function refreshStores() {
    setStatus("Loading stores");
    try {
      const result = await listStores();
      setStores(result);
      if (!storeId && result.length > 0) {
        setStoreId(result[0].id);
      }
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load stores");
    }
  }

  async function loadSavedConfig() {
    if (!draftId) return;
    setStatus("Loading saved listing config");
    try {
      const config = await getDraftListingConfig(draftId);
      setSavedConfig(config);
      setSiteId(config.site_id);
      setListingTypes([]);
      const metadata = await getListingTypes(config.site_id);
      setListingTypes(metadata.listing_type_ids);
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
        site_id: siteId,
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

  async function approveCurrentDraft() {
    if (!draftId) return;
    setStatus("Approving draft");
    try {
      setApproval(await approveDraft(draftId, "operator", "Approved for Mercado Libre publish"));
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to approve draft");
    }
  }

  async function executeSavedConfig() {
    if (!draftId || !review || !storeId) return;
    setStatus("Executing publish request");
    try {
      const result = await executePublishFromDraft(
        draftId,
        Number(storeId),
        review,
        listingTypes,
        true,
      );
      setExecution(result);
      setJobs(await listPublishJobs());
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to execute publish request");
    }
  }

  async function enqueueSavedConfig() {
    if (!draftId || !review || !storeId) return;
    setStatus("Queueing publish job");
    try {
      await enqueuePublishFromDraft(draftId, Number(storeId), review, listingTypes, true);
      setJobs(await listPublishJobs());
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to queue publish job");
    }
  }

  async function retryJob(jobId: number) {
    setRetryingJobId(jobId);
    setStatus(`Retrying publish job #${jobId}`);
    try {
      setExecution(await retryPublishJob(jobId));
      setJobs(await listPublishJobs());
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to retry publish job");
    } finally {
      setRetryingJobId(null);
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
        <button disabled={!draft} onClick={forceRefreshListingTypes}>
          Refresh Listing Types
        </button>
        <button disabled={!draft} onClick={predictDraftCategory}>
          Predict Category
        </button>
        <button onClick={refreshStores}>Load Stores</button>
      </div>
      <label>
        Mercado Libre Site ID
        <input
          value={siteId}
          onChange={(event) => {
            setSiteId(event.target.value.toUpperCase());
            setListingTypes([]);
            setListingTypeId("");
            setCategoryId("");
            setPredictions([]);
            setAttributes([]);
            setSavedConfig(null);
            setPreview(null);
          }}
        />
      </label>
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
        <button disabled={!categoryId} onClick={forceRefreshAttributes}>
          Refresh Attributes
        </button>
        <button disabled={!draftId} onClick={loadSavedConfig}>
          Load Saved Config
        </button>
        <button disabled={!draftId || !categoryId || !listingTypeId} onClick={saveConfig}>
          Save Listing Config
        </button>
        <button disabled={!draftId || !savedConfig} onClick={approveCurrentDraft}>
          Approve Draft
        </button>
      </div>
      {status && <p>{status}</p>}
      {stores.length > 0 && (
        <label>
          Store
          <select value={storeId} onChange={(event) => setStoreId(event.target.value)}>
            {stores.map((store) => (
              <option key={store.id} value={store.id}>
                #{store.id} {store.display_name} {store.site_id}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="button-row">
        <button disabled={!ready || !draftId || listingTypes.length === 0} onClick={previewSavedConfig}>
          Create Publish Preview
        </button>
        <button
          disabled={!preview?.allowed || !draftId || !storeId || listingTypes.length === 0}
          onClick={executeSavedConfig}
        >
          Execute Publish
        </button>
        <button
          disabled={!ready || !draftId || !storeId || listingTypes.length === 0}
          onClick={enqueueSavedConfig}
        >
          Queue Publish Job
        </button>
      </div>
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
      {approval && (
        <>
          <h3>Draft Approval</h3>
          <pre>{JSON.stringify(approval, null, 2)}</pre>
        </>
      )}
      {preview && (
        <>
          <h3>Publish Preview</h3>
          <pre>{JSON.stringify(preview, null, 2)}</pre>
        </>
      )}
      {execution && (
        <>
          <h3>Publish Execution</h3>
          <pre>{JSON.stringify(execution, null, 2)}</pre>
        </>
      )}
      {jobs.length > 0 && (
        <>
          <h3>Publish Jobs</h3>
          <div className="job-list">
            {jobs.map((job) => {
              const canRetry = job.status === "blocked" || job.status === "failed";
              return (
                <div className="job-row" key={job.id}>
                  <span>
                    #{job.id} draft #{job.product_draft_id} store #{job.store_id} {job.status}
                  </span>
                  <button
                    disabled={!canRetry || retryingJobId === job.id}
                    onClick={() => retryJob(job.id)}
                  >
                    Retry
                  </button>
                </div>
              );
            })}
          </div>
          <pre>{JSON.stringify(jobs, null, 2)}</pre>
        </>
      )}
    </section>
  );
}
