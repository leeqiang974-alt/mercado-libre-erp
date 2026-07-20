import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  ListChecks,
  RefreshCw,
  Rocket,
  Save,
  Search,
  Store,
  Truck,
} from "lucide-react";
import {
  approveDraft,
  enqueuePublishFromDraft,
  executePublishFromDraft,
  getCategoryAttributes,
  getCategoryPredictions,
  getDraftListingConfig,
  getListingTypes,
  getStoreShippingOptions,
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
  type ShippingOption,
  type SystemReadiness,
} from "../api/client";
import { currencyForSite, MERCADO_LIBRE_SITES } from "../domain/sites";

const COMMERCIAL_TYPES = [
  { id: "gold_special", label: "Classic", note: "Lower fee, standard visibility" },
  { id: "gold_pro", label: "Premium", note: "Installments and higher visibility" },
];

const SHIPPING_LABELS: Record<string, string> = {
  "me2:drop_off": "Mercado Envíos · drop-off",
  "me2:cross_docking": "Mercado Envíos · cross-docking",
  "me2:xd_drop_off": "Mercado Envíos · XD drop-off",
  "me2:self_service": "Mercado Envíos · self-service",
  "me2:turbo": "Mercado Envíos · turbo",
  "me1:default": "Mercado Envíos 1",
  "not_specified:not_specified": "Seller-arranged shipping",
};

function shippingKey(option: ShippingOption) {
  return `${option.mode}:${option.logistic_type}`;
}

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
  const [previewFingerprint, setPreviewFingerprint] = useState("");
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [shippingOptions, setShippingOptions] = useState<ShippingOption[]>([]);
  const [selectedShippingKey, setSelectedShippingKey] = useState("");
  const [shippingStatus, setShippingStatus] = useState("");
  const [jobs, setJobs] = useState<PublishJobRecord[]>([]);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const siteRequestEpochRef = useRef(0);
  const categoryPredictionEpochRef = useRef(0);
  const categoryAttributesEpochRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    siteRequestEpochRef.current += 1;
    if (!draft) return () => { cancelled = true; };
    const nextSite = draft.target_site_id;
    setSiteId(nextSite);
    setListingTypes([]);
    setListingTypeId("");
    setCategoryId(draft.target_category_id || "");
    setSavedConfig(null);
    setPreview(null);
    setApproval(null);
    setExecution(null);
    const configRequest = draftId ? getDraftListingConfig(draftId) : Promise.resolve(null);
    Promise.all([
      getSystemReadiness(),
      listStores(),
      listPublishJobs(),
      getListingTypes(nextSite),
      configRequest,
    ])
      .then(([system, storeRows, jobRows, metadata, config]) => {
        if (cancelled) return;
        setReadiness(system);
        setStores(storeRows);
        setJobs(jobRows);
        setListingTypes(metadata.listing_type_ids);
        setListingTypesVerified(metadata.verified);
        if (config) {
          setSavedConfig(config);
          setSiteId(config.site_id);
          setStoreId(config.store_id ? String(config.store_id) : "");
          setCategoryId(config.category_id);
          setListingTypeId(config.listing_type_id);
          setSelectedShippingKey(
            config.shipping_mode && config.shipping_logistic_type
              ? `${config.shipping_mode}:${config.shipping_logistic_type}`
              : "",
          );
          setAttributeValues(
            Object.fromEntries(config.attributes.map((item) => [item.id, item.value_name])),
          );
          return;
        }
        const matchingStore = storeRows.find(
          (store) => store.site_id === nextSite && store.oauth_status === "connected",
        );
        setStoreId(matchingStore?.id ?? "");
        const defaultType = metadata.listing_type_ids.includes("gold_special")
          ? "gold_special"
          : metadata.listing_type_ids.includes("gold_pro") ? "gold_pro" : "";
        setListingTypeId(defaultType);
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : "Failed to load publish data");
        }
      });
    return () => { cancelled = true; };
  }, [draftId]);

  useEffect(() => {
    let cancelled = false;
    if (!storeId) {
      setShippingOptions([]);
      setSelectedShippingKey("");
      setShippingStatus("");
      return () => { cancelled = true; };
    }
    setShippingStatus("Loading verified non-FULL shipping options...");
    getStoreShippingOptions(Number(storeId))
      .then((result) => {
        if (cancelled) return;
        setShippingOptions(result.options);
        setSelectedShippingKey((current) =>
          result.options.some((option) => shippingKey(option) === current)
            ? current
            : result.options[0] ? shippingKey(result.options[0]) : "",
        );
        setShippingStatus(
          result.options.length
            ? `${result.options.length} verified non-FULL option${result.options.length === 1 ? "" : "s"}`
            : "This store exposes no supported non-FULL shipping option.",
        );
      })
      .catch((error) => {
        if (cancelled) return;
        setShippingOptions([]);
        setSelectedShippingKey("");
        setShippingStatus(error instanceof Error ? error.message : "Shipping options unavailable");
      });
    return () => { cancelled = true; };
  }, [storeId]);

  const reviewPassed = review?.decision === "pass";
  const expectedCurrency = currencyForSite(siteId);
  const siteMatchesDraft = siteId === draft?.target_site_id;
  const pricingValid = Boolean(siteMatchesDraft && draft?.price && draft.currency === expectedCurrency);
  const siteStores = stores.filter((store) => store.site_id === siteId && store.oauth_status === "connected");
  const selectedStore = siteStores.find((store) => String(store.id) === storeId);
  const selectedShipping = shippingOptions.find(
    (option) => shippingKey(option) === selectedShippingKey,
  );
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
  const currentAttributes = useMemo(
    () => Object.entries(attributeValues)
      .filter(([, value]) => value.trim())
      .map(([id, value_name]) => ({ id, value_name }))
      .sort((left, right) => left.id.localeCompare(right.id)),
    [attributeValues],
  );
  const currentConfigFingerprint = JSON.stringify({
    draft_id: draftId,
    review_result_id: review?.review_result_id ?? null,
    approval_id: approval?.id ?? null,
    site_id: siteId,
    store_id: Number(storeId),
    category_id: categoryId,
    listing_type_id: listingTypeId,
    shipping_mode: selectedShipping?.mode ?? "",
    shipping_logistic_type: selectedShipping?.logistic_type ?? "",
    attributes: currentAttributes,
  });
  const currentConfigFingerprintRef = useRef(currentConfigFingerprint);
  currentConfigFingerprintRef.current = currentConfigFingerprint;

  useEffect(() => {
    if (previewFingerprint && previewFingerprint !== currentConfigFingerprint) {
      setPreview(null);
      setPreviewFingerprint("");
    }
  }, [currentConfigFingerprint, previewFingerprint]);

  async function changeSite(nextSite: string) {
    const requestEpoch = ++siteRequestEpochRef.current;
    categoryPredictionEpochRef.current += 1;
    categoryAttributesEpochRef.current += 1;
    setSiteId(nextSite);
    setListingTypes([]);
    setListingTypeId("");
    setCategoryId("");
    setPredictions([]);
    setCategoryAttributes([]);
    setAttributeValues({});
    setSavedConfig(null);
    setPreview(null);
    setShippingOptions([]);
    setSelectedShippingKey("");
    const matchingStore = stores.find((store) => store.site_id === nextSite && store.oauth_status === "connected");
    setStoreId(matchingStore?.id ?? "");
    setBusy("listing-types");
    try {
      const result = await getListingTypes(nextSite);
      if (siteRequestEpochRef.current !== requestEpoch) return;
      setListingTypes(result.listing_type_ids);
      setListingTypesVerified(result.verified);
      if (result.listing_type_ids.includes("gold_special")) setListingTypeId("gold_special");
      else if (result.listing_type_ids.includes("gold_pro")) setListingTypeId("gold_pro");
    } catch (error) {
      if (siteRequestEpochRef.current === requestEpoch) {
        setStatus(error instanceof Error ? error.message : "Failed to load listing types");
      }
    } finally {
      if (siteRequestEpochRef.current === requestEpoch) setBusy("");
    }
  }

  async function refreshCommercialTypes() {
    const requestEpoch = ++siteRequestEpochRef.current;
    setBusy("listing-types");
    setStatus("");
    try {
      const result = await refreshListingTypes(siteId);
      if (siteRequestEpochRef.current !== requestEpoch) return;
      setListingTypes(result.listing_type_ids);
      setListingTypesVerified(result.verified);
    } catch (error) {
      if (siteRequestEpochRef.current === requestEpoch) {
        setStatus(error instanceof Error ? error.message : "Failed to refresh listing types");
      }
    } finally {
      if (siteRequestEpochRef.current === requestEpoch) setBusy("");
    }
  }

  async function predictDraftCategory() {
    if (!draft) return;
    const requestEpoch = ++categoryPredictionEpochRef.current;
    setBusy("category");
    setStatus("");
    try {
      const result = await getCategoryPredictions(siteId, draft.title);
      if (categoryPredictionEpochRef.current !== requestEpoch) return;
      setPredictions(result.predictions.slice(0, 6));
    } catch (error) {
      if (categoryPredictionEpochRef.current === requestEpoch) {
        setStatus(error instanceof Error ? error.message : "Failed to predict category");
      }
    } finally {
      if (categoryPredictionEpochRef.current === requestEpoch) setBusy("");
    }
  }

  async function loadAttributes(force = false) {
    if (!categoryId) return;
    const requestedCategoryId = categoryId;
    const requestEpoch = ++categoryAttributesEpochRef.current;
    setBusy("attributes");
    setStatus("");
    try {
      const result = force
        ? await refreshCategoryAttributes(requestedCategoryId)
        : await getCategoryAttributes(requestedCategoryId);
      if (categoryAttributesEpochRef.current !== requestEpoch) return;
      setCategoryAttributes(result.attributes);
    } catch (error) {
      if (categoryAttributesEpochRef.current === requestEpoch) {
        setStatus(error instanceof Error ? error.message : "Failed to load attributes");
      }
    } finally {
      if (categoryAttributesEpochRef.current === requestEpoch) setBusy("");
    }
  }

  function changeCategory(nextCategoryId: string) {
    categoryPredictionEpochRef.current += 1;
    categoryAttributesEpochRef.current += 1;
    setCategoryId(nextCategoryId);
    setCategoryAttributes([]);
    setAttributeValues({});
    setSavedConfig(null);
    setPreview(null);
    setPreviewFingerprint("");
    setBusy((current) => (
      current === "category" || current === "attributes" ? "" : current
    ));
  }

  async function saveConfig() {
    if (!draftId) return;
    setBusy("config");
    setStatus("");
    setPreview(null);
    setPreviewFingerprint("");
    setApproval(null);
    onReviewInvalidated();
    try {
      const config = await saveDraftListingConfig(draftId, {
        site_id: siteId,
        store_id: Number(storeId),
        category_id: categoryId,
        listing_type_id: listingTypeId,
        fulfillment: "not_full",
        shipping_mode: selectedShipping?.mode ?? "",
        shipping_logistic_type: selectedShipping?.logistic_type ?? "",
        attributes: currentAttributes,
      });
      setSavedConfig(config);
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
    const requestedFingerprint = currentConfigFingerprint;
    setBusy("preview");
    setPreview(null);
    setPreviewFingerprint("");
    try {
      const result = await previewPublishFromDraft(draftId, review, listingTypes, true);
      if (currentConfigFingerprintRef.current !== requestedFingerprint) return;
      setPreview(result);
      setPreviewFingerprint(requestedFingerprint);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to create publish preview");
    } finally {
      setBusy("");
    }
  }

  async function executePublish() {
    if (
      !draftId || !review || !storeId || !previewMatchesCurrentConfig || busy === "config"
    ) return;
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
    if (
      !draftId || !review || !storeId || !previewMatchesCurrentConfig || busy === "config"
    ) return;
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

  const configReady = Boolean(
    savedConfig
      && savedConfig.site_id === siteId
      && savedConfig.store_id === Number(storeId)
      && savedConfig.category_id === categoryId
      && savedConfig.listing_type_id === listingTypeId
      && selectedShipping
      && savedConfig.shipping_mode === selectedShipping.mode
      && savedConfig.shipping_logistic_type === selectedShipping.logistic_type
      && JSON.stringify(
        [...savedConfig.attributes].sort((left, right) => left.id.localeCompare(right.id)),
      ) === JSON.stringify(currentAttributes),
  );
  const canApprove = pricingValid && reviewPassed && configReady;
  const canPreview = canApprove && Boolean(approval);
  const previewMatchesCurrentConfig = Boolean(
    preview?.allowed && previewFingerprint === currentConfigFingerprint && configReady,
  );

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
        <ProgressItem label="Validated" ready={previewMatchesCurrentConfig} />
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
            <select value={storeId} onChange={(event) => {
              setStoreId(event.target.value);
              setShippingOptions([]);
              setShippingStatus(event.target.value ? "Loading verified non-FULL shipping options..." : "");
              setSavedConfig(null);
              setPreview(null);
              setSelectedShippingKey("");
            }}>
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
        <div className="shipping-choice">
          <label><Truck size={16} /> Verified non-FULL shipping
            <select
              value={selectedShippingKey}
              disabled={!storeId || shippingOptions.length === 0}
              onChange={(event) => {
                setSelectedShippingKey(event.target.value);
                setSavedConfig(null);
                setPreview(null);
              }}
            >
              <option value="">Select a store shipping option</option>
              {shippingOptions.map((option) => (
                <option key={shippingKey(option)} value={shippingKey(option)}>
                  {SHIPPING_LABELS[shippingKey(option)] ?? `${option.mode} · ${option.logistic_type}`}
                </option>
              ))}
            </select>
          </label>
          {shippingStatus && <span>{shippingStatus}</span>}
        </div>
        <p className="full-exclusion">Options are read from the authorized store. FULL is filtered out and cannot be saved.</p>
      </section>

      <section className="surface publish-section">
        <div className="section-heading"><div><span className="step-number">2</span><h3>Category and attributes</h3></div></div>
        <div className="category-controls">
          <label>Category ID<input value={categoryId} onChange={(event) => changeCategory(event.target.value)} placeholder={`${siteId} category`} /></label>
          <button onClick={predictDraftCategory} disabled={busy === "category"}><Search size={16} /> Predict</button>
          <button className="secondary-button" onClick={() => loadAttributes(false)} disabled={!categoryId || busy === "attributes"}><ListChecks size={16} /> Load attributes</button>
        </div>
        {predictions.length > 0 && <div className="prediction-list">{predictions.map((prediction) => {
          const id = String(prediction.category_id ?? "");
          return <button key={id} className={categoryId === id ? "selected" : ""} onClick={() => changeCategory(id)}>{String(prediction.category_name ?? prediction.domain_name ?? id)}<small>{id}</small></button>;
        })}</div>}
        {requiredAttributes.length > 0 && <div className="form-grid two-col attribute-grid">{requiredAttributes.map((attribute) => {
          const id = String(attribute.id ?? "");
          return <label key={id}>{String(attribute.name ?? id)}<input value={attributeValues[id] ?? ""} onChange={(event) => setAttributeValues((values) => ({ ...values, [id]: event.target.value }))} /></label>;
        })}</div>}
        {categoryAttributes.length > 0 && <div className="action-line"><span>{requiredAttributes.length} required · {categoryAttributes.length} total attributes loaded</span><button className="secondary-button" onClick={() => loadAttributes(true)}><RefreshCw size={16} /> Refresh metadata</button></div>}
        <div className="action-line"><button onClick={saveConfig} disabled={!categoryId || !listingTypeId || !selectedShipping || !pricingValid || busy === "config"}><Save size={16} /> Save listing configuration</button>{savedConfig && <span className="success-text"><CheckCircle2 size={16} /> Saved as non-FULL</span>}</div>
      </section>

      <section className="surface publish-section">
        <div className="section-heading"><div><span className="step-number">3</span><h3>Approval and publish</h3></div></div>
        <div className="release-summary">
          <div><span>AI decision</span><strong>{String(review?.decision ?? "Not reviewed")}</strong></div>
          <div><span>Store</span><strong>{selectedStore?.display_name ?? "Not selected"}</strong></div>
          <div><span>Offer</span><strong>{COMMERCIAL_TYPES.find((type) => type.id === listingTypeId)?.label ?? "Not selected"}</strong></div>
          <div><span>Shipping</span><strong>{selectedShipping ? (SHIPPING_LABELS[selectedShippingKey] ?? selectedShippingKey) : "Not selected"}</strong></div>
          <div><span>Price</span><strong>{draft.price ? `${draft.currency} ${draft.price}` : "Not priced"}</strong></div>
        </div>
        <div className="button-row">
          <button disabled={!canApprove || busy === "approval"} onClick={approveCurrentDraft}><CheckCircle2 size={16} /> Record human approval</button>
          <button className="secondary-button" disabled={!canPreview || busy === "preview"} onClick={createPreview}><ListChecks size={16} /> Validate payload</button>
          <button disabled={!previewMatchesCurrentConfig || !selectedStore || !readiness?.mercado_libre.live_publish_enabled || busy === "execute" || busy === "config"} onClick={executePublish}><Rocket size={16} /> Publish now</button>
          <button className="secondary-button" disabled={!previewMatchesCurrentConfig || !selectedStore || busy === "queue" || busy === "config"} onClick={queuePublish}><Rocket size={16} /> Add to queue</button>
        </div>
        {!readiness?.mercado_libre.live_publish_enabled && <p className="inline-warning">Live publishing is disabled in server configuration.</p>}
        {preview && <div className={`validation-result ${preview.allowed ? "ready" : "blocked"}`}><strong>{preview.allowed ? "Payload is ready" : "Payload is blocked"}</strong>{preview.errors.map((item) => <span key={item}>{item}</span>)}</div>}
        {execution && <div className={`validation-result ${execution.status === "published" ? "ready" : "blocked"}`}><strong>{execution.status}</strong>{execution.item_id && <span>{execution.item_id}</span>}{execution.shipping_mode && <span>Shipping: {execution.shipping_mode}{execution.shipping_logistic_type ? ` · ${execution.shipping_logistic_type}` : ""}</span>}{execution.errors.map((item) => <span key={item}>{item}</span>)}</div>}
      </section>

      {status && <p className="status-line">{status}</p>}
      {jobs.length > 0 && <section className="saved-section"><div className="section-heading"><div><h3>Publish jobs</h3></div><span>{jobs.length}</span></div><div className="job-list">{jobs.map((job) => {
        const canRetry = (job.status === "blocked" || job.status === "failed") && !job.errors.includes("publish_outcome_unknown_manual_reconciliation_required");
        return <div className="job-row" key={job.id}><span>#{job.id} · draft #{job.product_draft_id} · store #{job.store_id}{job.shipping_mode ? ` · ${job.shipping_mode}` : ""}{job.shipping_logistic_type ? `/${job.shipping_logistic_type}` : ""}</span><strong>{job.status}</strong><button className="secondary-button" disabled={!canRetry || Boolean(job.item_id) || busy === `retry-${job.id}`} onClick={() => retryJob(job.id)}><RefreshCw size={16} /> Retry</button></div>;
      })}</div></section>}
    </section>
  );
}

function ProgressItem({ label, ready }: { label: string; ready: boolean }) {
  return <div className={ready ? "ready" : "pending"}><span>{ready ? <CheckCircle2 size={16} /> : null}</span><strong>{label}</strong></div>;
}
