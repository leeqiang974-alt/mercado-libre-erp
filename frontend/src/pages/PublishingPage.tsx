import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ListChecks,
  RefreshCw,
  Rocket,
  Save,
  Search,
  Store,
} from "lucide-react";
import {
  approveDraft,
  enqueuePublishFromDraft,
  executePublishFromDraft,
  getCategoryAttributes,
  getCategoryPredictions,
  getDraftListingConfig,
  getListingTypes,
  getSystemReadiness,
  listPublishJobs,
  listStores,
  previewPublishFromDraft,
  refreshCategoryAttributes,
  refreshListingTypes,
  retryPublishJob,
  saveDraftListingConfig,
  type DraftApproval,
  type DraftListingConfig,
  type ProductDraft,
  type PublishExecutionResult,
  type PublishJobRecord,
  type PublishValidationResult,
  type StoreRecord,
  type SystemReadiness,
} from "../api/client";
import { currencyForSite, MERCADO_LIBRE_SITES } from "../domain/sites";

const COMMERCIAL_TYPES = [
  { id: "gold_special", label: "Classic", note: "Lower fee, standard visibility" },
  { id: "gold_pro", label: "Premium", note: "Installments and higher visibility" },
];

export function PublishingPage({
  draft,
  draftId,
  review,
  onDraftChange,
  onReviewInvalidated,
}: {
  draft: ProductDraft | null;
  draftId: number | null;
  review: Record<string, unknown> | null;
  onDraftChange: (draft: ProductDraft) => void;
  onReviewInvalidated: () => void;
}) {
  const [siteId, setSiteId] = useState(draft?.target_site_id ?? "MLM");
  const [listingTypes, setListingTypes] = useState<string[]>([]);
  const [listingTypesVerified, setListingTypesVerified] = useState(false);
  const [listingTypeId, setListingTypeId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [categoryAttributes, setCategoryAttributes] = useState<Record<string, unknown>[]>([]);
  const [attributeValues, setAttributeValues] = useState<Record<string, string>>({});
  const [savedConfig, setSavedConfig] = useState<DraftListingConfig | null>(null);
  const [approval, setApproval] = useState<DraftApproval | null>(null);
  const [preview, setPreview] = useState<PublishValidationResult | null>(null);
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [jobs, setJobs] = useState<PublishJobRecord[]>([]);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!draft) return;
    const nextSite = draft.target_site_id;
    setSiteId(nextSite);
    setListingTypes([]);
    setListingTypeId("");
    setCategoryId(draft.target_category_id || "");
    setSavedConfig(null);
    setPreview(null);
    setApproval(null);
    setExecution(null);
    Promise.all([getSystemReadiness(), listStores(), listPublishJobs(), getListingTypes(nextSite)])
      .then(([system, storeRows, jobRows, metadata]) => {
        setReadiness(system);
        setStores(storeRows);
        setJobs(jobRows);
        setListingTypes(metadata.listing_type_ids);
        setListingTypesVerified(metadata.verified);
        const matchingStore = storeRows.find((store) => store.site_id === nextSite);
        setStoreId(matchingStore?.id ?? "");
        const defaultType = metadata.listing_type_ids.includes("gold_special")
          ? "gold_special"
          : metadata.listing_type_ids.includes("gold_pro") ? "gold_pro" : "";
        setListingTypeId(defaultType);
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : "Failed to load publish data"));
    if (draftId) {
      getDraftListingConfig(draftId)
        .then((config) => {
          if (!config) return;
          setSavedConfig(config);
          setSiteId(config.site_id);
          setCategoryId(config.category_id);
          setListingTypeId(config.listing_type_id);
          setAttributeValues(Object.fromEntries(config.attributes.map((item) => [item.id, item.value_name])));
        })
        .catch(() => undefined);
    }
  }, [draftId]);

  const reviewPassed = review?.decision === "pass";
  const expectedCurrency = currencyForSite(siteId);
  const siteMatchesDraft = siteId === draft?.target_site_id;
  const pricingValid = Boolean(siteMatchesDraft && draft?.price && draft.currency === expectedCurrency);
  const siteStores = stores.filter((store) => store.site_id === siteId && store.oauth_status === "connected");
  const selectedStore = siteStores.find((store) => String(store.id) === storeId);
  const commercialTypes = COMMERCIAL_TYPES.map((type) => ({
    ...type,
    available: listingTypes.includes(type.id),
  }));
  const requiredAttributes = useMemo(
    () => categoryAttributes.filter((attribute) => {
      const tags = attribute.tags as Record<string, unknown> | undefined;
      return Boolean(tags?.required || tags?.catalog_required);
    }),
    [categoryAttributes],
  );

  async function changeSite(nextSite: string) {
    setSiteId(nextSite);
    setListingTypes([]);
    setListingTypeId("");
    setCategoryId("");
    setPredictions([]);
    setCategoryAttributes([]);
    setSavedConfig(null);
    setPreview(null);
    const matchingStore = stores.find((store) => store.site_id === nextSite && store.oauth_status === "connected");
    setStoreId(matchingStore?.id ?? "");
    setBusy("listing-types");
    try {
      const result = await getListingTypes(nextSite);
      setListingTypes(result.listing_type_ids);
      setListingTypesVerified(result.verified);
      if (result.listing_type_ids.includes("gold_special")) setListingTypeId("gold_special");
      else if (result.listing_type_ids.includes("gold_pro")) setListingTypeId("gold_pro");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load listing types");
    } finally {
      setBusy("");
    }
  }

  async function refreshCommercialTypes() {
    setBusy("listing-types");
    setStatus("");
    try {
      const result = await refreshListingTypes(siteId);
      setListingTypes(result.listing_type_ids);
      setListingTypesVerified(result.verified);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to refresh listing types");
    } finally {
      setBusy("");
    }
  }

  async function predictDraftCategory() {
    if (!draft) return;
    setBusy("category");
    setStatus("");
    try {
      const result = await getCategoryPredictions(siteId, draft.title);
      setPredictions(result.predictions.slice(0, 6));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to predict category");
    } finally {
      setBusy("");
    }
  }

  async function loadAttributes(force = false) {
    if (!categoryId) return;
    setBusy("attributes");
    setStatus("");
    try {
      const result = force
        ? await refreshCategoryAttributes(categoryId)
        : await getCategoryAttributes(categoryId);
      setCategoryAttributes(result.attributes);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load attributes");
    } finally {
      setBusy("");
    }
  }

  async function saveConfig() {
    if (!draftId) return;
    setBusy("config");
    setStatus("");
    try {
      const attributes = Object.entries(attributeValues)
        .filter(([, value]) => value.trim())
        .map(([id, value_name]) => ({ id, value_name }));
      const config = await saveDraftListingConfig(draftId, {
        site_id: siteId,
        category_id: categoryId,
        listing_type_id: listingTypeId,
        fulfillment: "not_full",
        attributes,
      });
      setSavedConfig(config);
      setPreview(null);
      setApproval(null);
      onReviewInvalidated();
      if (draft) {
        onDraftChange({
          ...draft,
          target_site_id: config.site_id,
          target_category_id: config.category_id,
          listing_type_id: config.listing_type_id,
        });
      }
      setStatus("Listing configuration saved");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to save listing config");
    } finally {
      setBusy("");
    }
  }

  async function approveCurrentDraft() {
    if (!draftId) return;
    setBusy("approval");
    try {
      setApproval(await approveDraft(draftId, "operator", "Approved for non-FULL Mercado Libre publish"));
      setStatus("Human approval recorded");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to approve draft");
    } finally {
      setBusy("");
    }
  }

  async function createPreview() {
    if (!draftId || !review) return;
    setBusy("preview");
    try {
      setPreview(await previewPublishFromDraft(draftId, review, listingTypes, true));
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to create publish preview");
    } finally {
      setBusy("");
    }
  }

  async function executePublish() {
    if (!draftId || !review || !storeId) return;
    setBusy("execute");
    try {
      const result = await executePublishFromDraft(draftId, Number(storeId), review, listingTypes, true);
      setExecution(result);
      setJobs(await listPublishJobs());
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to execute publish request");
    } finally {
      setBusy("");
    }
  }

  async function queuePublish() {
    if (!draftId || !review || !storeId) return;
    setBusy("queue");
    try {
      await enqueuePublishFromDraft(draftId, Number(storeId), review, listingTypes, true);
      setJobs(await listPublishJobs());
      setStatus("Publish job queued");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to queue publish job");
    } finally {
      setBusy("");
    }
  }

  async function retryJob(jobId: number) {
    setBusy(`retry-${jobId}`);
    try {
      setExecution(await retryPublishJob(jobId));
      setJobs(await listPublishJobs());
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to retry publish job");
    } finally {
      setBusy("");
    }
  }

  if (!draft || !draftId) {
    return <section className="workspace"><div className="empty-state">Select and prepare a saved draft before publishing.</div></section>;
  }

  const configReady = Boolean(savedConfig && savedConfig.site_id === siteId && savedConfig.listing_type_id === listingTypeId);
  const canApprove = pricingValid && reviewPassed && configReady;
  const canPreview = canApprove && Boolean(approval);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">Mercado Libre delivery</p>
          <h2>Publish workspace</h2>
          <p>{draft.title}</p>
        </div>
        <span className="record-id">Draft #{draftId}</span>
      </header>

      <div className="publish-progress">
        <ProgressItem label="Priced" ready={pricingValid} />
        <ProgressItem label="AI passed" ready={reviewPassed} />
        <ProgressItem label="Configured" ready={configReady} />
        <ProgressItem label="Approved" ready={Boolean(approval)} />
        <ProgressItem label="Validated" ready={Boolean(preview?.allowed)} />
      </div>

      <section className="surface publish-section">
        <div className="section-heading"><div><span className="step-number">1</span><h3>Market and offer</h3></div><button className="icon-button" title="Refresh listing types" onClick={refreshCommercialTypes} disabled={busy === "listing-types"}><RefreshCw size={17} /></button></div>
        <div className="form-grid two-col">
          <label>Mercado Libre site
            <select value={siteId} onChange={(event) => changeSite(event.target.value)}>
              {MERCADO_LIBRE_SITES.map((site) => <option key={site.id} value={site.id}>{site.country} ({site.id}) · {site.currency}</option>)}
            </select>
          </label>
          <label>Authorized store
            <select value={storeId} onChange={(event) => setStoreId(event.target.value)}>
              <option value="">Select a connected {siteId} store</option>
              {siteStores.map((store) => <option key={store.id} value={store.id}>{store.display_name} · seller {store.seller_id}</option>)}
            </select>
          </label>
        </div>
        {!siteMatchesDraft && <p className="inline-warning">This draft was prepared for {draft.target_site_id}. Return to Import, select {siteId}, then reprice and rerun the AI review before publishing.</p>}
        {siteMatchesDraft && !draft.price && <p className="inline-warning">This draft has no target selling price. Calculate and save a price in {expectedCurrency} before publishing to {siteId}.</p>}
        {siteMatchesDraft && Boolean(draft.price) && draft.currency !== expectedCurrency && <p className="inline-warning">This draft is priced in {draft.currency || "no currency"}. Reprice it in {expectedCurrency} before publishing to {siteId}.</p>}
        {siteStores.length === 0 && <p className="inline-warning">No connected store is authorized for {siteId}.</p>}
        <div className="listing-choice" role="group" aria-label="Listing type">
          {commercialTypes.map((type) => (
            <button key={type.id} className={listingTypeId === type.id ? "selected" : ""} disabled={!type.available} onClick={() => { setListingTypeId(type.id); setSavedConfig(null); setPreview(null); }}>
              <strong>{type.label}</strong><span>{type.available ? type.note : "Unavailable for this site"}</span>
            </button>
          ))}
        </div>
        {!listingTypesVerified && listingTypes.length > 0 && <p className="inline-warning">Classic and Premium are loaded from the standard catalog because live Mercado Libre metadata verification is currently unavailable.</p>}
        <p className="full-exclusion">Shipping follows the connected store and category configuration. FULL is always excluded.</p>
      </section>

      <section className="surface publish-section">
        <div className="section-heading"><div><span className="step-number">2</span><h3>Category and attributes</h3></div></div>
        <div className="category-controls">
          <label>Category ID<input value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setSavedConfig(null); }} placeholder={`${siteId} category`} /></label>
          <button onClick={predictDraftCategory} disabled={busy === "category"}><Search size={16} /> Predict</button>
          <button className="secondary-button" onClick={() => loadAttributes(false)} disabled={!categoryId || busy === "attributes"}><ListChecks size={16} /> Load attributes</button>
        </div>
        {predictions.length > 0 && <div className="prediction-list">{predictions.map((prediction) => {
          const id = String(prediction.category_id ?? "");
          return <button key={id} className={categoryId === id ? "selected" : ""} onClick={() => { setCategoryId(id); setSavedConfig(null); }}>{String(prediction.category_name ?? prediction.domain_name ?? id)}<small>{id}</small></button>;
        })}</div>}
        {requiredAttributes.length > 0 && <div className="form-grid two-col attribute-grid">{requiredAttributes.map((attribute) => {
          const id = String(attribute.id ?? "");
          return <label key={id}>{String(attribute.name ?? id)}<input value={attributeValues[id] ?? ""} onChange={(event) => setAttributeValues((values) => ({ ...values, [id]: event.target.value }))} /></label>;
        })}</div>}
        {categoryAttributes.length > 0 && <div className="action-line"><span>{requiredAttributes.length} required · {categoryAttributes.length} total attributes loaded</span><button className="secondary-button" onClick={() => loadAttributes(true)}><RefreshCw size={16} /> Refresh metadata</button></div>}
        <div className="action-line"><button onClick={saveConfig} disabled={!categoryId || !listingTypeId || !pricingValid || busy === "config"}><Save size={16} /> Save listing configuration</button>{savedConfig && <span className="success-text"><CheckCircle2 size={16} /> Saved as non-FULL</span>}</div>
      </section>

      <section className="surface publish-section">
        <div className="section-heading"><div><span className="step-number">3</span><h3>Approval and publish</h3></div></div>
        <div className="release-summary">
          <div><span>AI decision</span><strong>{String(review?.decision ?? "Not reviewed")}</strong></div>
          <div><span>Store</span><strong>{selectedStore?.display_name ?? "Not selected"}</strong></div>
          <div><span>Offer</span><strong>{COMMERCIAL_TYPES.find((type) => type.id === listingTypeId)?.label ?? "Not selected"}</strong></div>
          <div><span>Price</span><strong>{draft.price ? `${draft.currency} ${draft.price}` : "Not priced"}</strong></div>
        </div>
        <div className="button-row">
          <button disabled={!canApprove || busy === "approval"} onClick={approveCurrentDraft}><CheckCircle2 size={16} /> Record human approval</button>
          <button className="secondary-button" disabled={!canPreview || busy === "preview"} onClick={createPreview}><ListChecks size={16} /> Validate payload</button>
          <button disabled={!preview?.allowed || !selectedStore || !readiness?.mercado_libre.live_publish_enabled || busy === "execute"} onClick={executePublish}><Rocket size={16} /> Publish now</button>
          <button className="secondary-button" disabled={!preview?.allowed || !selectedStore || busy === "queue"} onClick={queuePublish}><Rocket size={16} /> Add to queue</button>
        </div>
        {!readiness?.mercado_libre.live_publish_enabled && <p className="inline-warning">Live publishing is disabled in server configuration.</p>}
        {preview && <div className={`validation-result ${preview.allowed ? "ready" : "blocked"}`}><strong>{preview.allowed ? "Payload is ready" : "Payload is blocked"}</strong>{preview.errors.map((item) => <span key={item}>{item}</span>)}</div>}
        {execution && <div className={`validation-result ${execution.status === "published" ? "ready" : "blocked"}`}><strong>{execution.status}</strong>{execution.item_id && <span>{execution.item_id}</span>}{execution.shipping_mode && <span>Shipping: {execution.shipping_mode}</span>}{execution.errors.map((item) => <span key={item}>{item}</span>)}</div>}
      </section>

      {status && <p className="status-line">{status}</p>}
      {jobs.length > 0 && <section className="saved-section"><div className="section-heading"><div><h3>Publish jobs</h3></div><span>{jobs.length}</span></div><div className="job-list">{jobs.map((job) => {
        const canRetry = job.status === "blocked" || job.status === "failed";
        return <div className="job-row" key={job.id}><span>#{job.id} · draft #{job.product_draft_id} · store #{job.store_id}{job.shipping_mode ? ` · ${job.shipping_mode}` : ""}</span><strong>{job.status}</strong><button className="secondary-button" disabled={!canRetry || busy === `retry-${job.id}`} onClick={() => retryJob(job.id)}><RefreshCw size={16} /> Retry</button></div>;
      })}</div></section>}
    </section>
  );
}

function ProgressItem({ label, ready }: { label: string; ready: boolean }) {
  return <div className={ready ? "ready" : "pending"}><span>{ready ? <CheckCircle2 size={16} /> : null}</span><strong>{label}</strong></div>;
}
