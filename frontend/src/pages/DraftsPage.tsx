import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Calculator,
  ImageOff,
  ListPlus,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  enqueueBehavioralAuditBatch,
  getDraftPricing,
  getDraftListingConfig,
  getLatestBehavioralReview,
  getSystemReadiness,
  listDrafts,
  listReviewJobs,
  listReviewHistory,
  saveDraftContent,
  saveDraftPricing,
  type DraftContentUpdate,
  type DraftPricing,
  type DraftPricingInput,
  type ProductDraft,
  type ProductDraftRead,
  type ReviewResult,
  type ReviewJob,
  type ReviewJobBatchResult,
  type SystemReadiness,
} from "../api/client";
import { currencyForSite } from "../domain/sites";

const EMPTY_PRICING: DraftPricingInput = {
  source_price: 0,
  source_currency: "USD",
  target_currency: "MXN",
  exchange_rate: 1,
  purchase_extra_cost: 0,
  shipping_cost: 0,
  platform_fee_rate: 0.15,
  tax_rate: 0,
  profit_margin_rate: 0.2,
  rounding_increment: 1,
};

const MAX_REVIEW_BATCH_SIZE = 50;

function ProductImage({ src, alt }: { src?: string; alt: string }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [src]);

  if (!src || failed) {
    return (
      <span className="product-image image-placeholder" aria-label="无商品图片">
        <ImageOff aria-hidden="true" />
      </span>
    );
  }

  return <img className="product-image" src={src} alt={alt} onError={() => setFailed(true)} />;
}

export function DraftsPage({
  draft,
  draftId,
  review,
  onReviewChange,
  onSelectDraft,
  onDraftChange,
  onContentDirtyChange,
}: {
  draft: ProductDraft | null;
  draftId: number | null;
  review: Record<string, unknown> | null;
  onReviewChange: (review: Record<string, unknown> | null) => void;
  onSelectDraft: (draft: ProductDraftRead) => void;
  onDraftChange: (draft: ProductDraft) => void;
  onContentDirtyChange: (dirty: boolean) => void;
}) {
  const [savedDrafts, setSavedDrafts] = useState<ProductDraftRead[]>([]);
  const [providerReview, setProviderReview] = useState<Record<string, unknown> | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewResult[]>([]);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [pricing, setPricing] = useState<DraftPricingInput>(EMPTY_PRICING);
  const [pricingResult, setPricingResult] = useState<DraftPricing | null>(null);
  const [listingConfigured, setListingConfigured] = useState(false);
  const [selectedDraftIds, setSelectedDraftIds] = useState<Set<number>>(new Set());
  const [providerCostAcknowledged, setProviderCostAcknowledged] = useState(false);
  const [reviewJobs, setReviewJobs] = useState<ReviewJob[]>([]);
  const [batchReviewResult, setBatchReviewResult] = useState<ReviewJobBatchResult | null>(null);
  const [contentForm, setContentForm] = useState<DraftContentUpdate | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const draftEpochRef = useRef(0);
  const historyEpochRef = useRef(0);
  const currentDraftIdRef = useRef(draftId);
  currentDraftIdRef.current = draftId;

  useEffect(() => {
    Promise.all([listDrafts(), getSystemReadiness(), listReviewJobs()])
      .then(([drafts, system, jobs]) => {
        setSavedDrafts(drafts);
        setReadiness(system);
        setReviewJobs(jobs);
      })
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "加载草稿失败"),
      );
  }, []);

  useEffect(() => {
    if (!reviewJobs.some((job) => job.status === "pending" || job.status === "running")) return;
    const timer = window.setTimeout(() => {
      const activeDraftId = currentDraftIdRef.current;
      Promise.all([
        listReviewJobs(),
        listDrafts(),
        activeDraftId ? listReviewHistory(activeDraftId) : Promise.resolve([]),
        activeDraftId ? getLatestBehavioralReview(activeDraftId) : Promise.resolve(null),
      ])
        .then(([jobs, drafts, history, currentAggregate]) => {
          setReviewJobs(jobs);
          setSavedDrafts(drafts);
          if (activeDraftId && currentDraftIdRef.current === activeDraftId) {
            setReviewHistory(history);
            setProviderReview(currentAggregate);
            onReviewChange(currentAggregate);
          }
        })
        .catch((loadError) => setError(
          loadError instanceof Error ? loadError.message : "Failed to refresh review jobs",
        ));
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [reviewJobs, onReviewChange]);

  useEffect(() => {
    if (!draftId || draft?.content_version || savedDrafts.length === 0) return;
    const persisted = savedDrafts.find((item) => item.id === draftId);
    if (persisted) onDraftChange(persisted);
  }, [draftId, draft?.content_version, savedDrafts, onDraftChange]);

  useEffect(() => {
    if (!draft || !draft.content_version) {
      setContentForm(null);
      return;
    }
    setContentForm({
      expected_content_version: draft.content_version,
      title: draft.title,
      description: draft.description,
      brand: draft.brand,
      image_urls: draft.image_urls.length > 0 ? draft.image_urls : [""],
    });
  }, [draftId, draft?.content_version]);

  useEffect(() => {
    draftEpochRef.current += 1;
    historyEpochRef.current += 1;
    if (!draft) return;
    setBusy("");
    setProviderReview(null);
    setReviewHistory([]);
    setPricingResult(null);
    setListingConfigured(false);
    setPricing({
      ...EMPTY_PRICING,
      source_price: draft.source_price ?? 0,
      source_currency: draft.source_currency || "",
      target_currency: currencyForSite(draft.target_site_id) || draft.currency,
    });
    if (!draftId) return;
    getDraftListingConfig(draftId)
      .then((config) => setListingConfigured(Boolean(config)))
      .catch(() => setListingConfigured(false));
    getDraftPricing(draftId)
      .then((saved) => {
        if (!saved) return;
        setPricing(saved);
        setPricingResult(saved);
      })
      .catch(() => undefined);
    Promise.all([listReviewHistory(draftId), getLatestBehavioralReview(draftId)])
      .then(([history, aggregate]) => {
        if (currentDraftIdRef.current !== draftId) return;
        setReviewHistory(history);
        if (aggregate) {
          setProviderReview(aggregate);
          onReviewChange(aggregate);
        }
      })
      .catch(() => undefined);
  }, [
    draftId,
    draft?.target_site_id,
    draft?.source_price,
    draft?.source_currency,
    draft?.price,
    draft?.currency,
  ]);

  function updatePricing(name: keyof DraftPricingInput, value: string) {
    if (name === "source_currency" || name === "target_currency") {
      setPricing((current) => ({ ...current, [name]: value.toUpperCase() }));
      return;
    }
    setPricing((current) => ({ ...current, [name]: Number(value) }));
  }

  function updateContentField(name: "title" | "description" | "brand", value: string) {
    setContentForm((current) => (current ? { ...current, [name]: value } : current));
  }

  function updateContentImage(index: number, value: string) {
    setContentForm((current) => {
      if (!current) return current;
      const imageUrls = [...current.image_urls];
      imageUrls[index] = value;
      return { ...current, image_urls: imageUrls };
    });
  }

  function removeContentImage(index: number) {
    setContentForm((current) => {
      if (!current) return current;
      const imageUrls = current.image_urls.filter((_, itemIndex) => itemIndex !== index);
      return { ...current, image_urls: imageUrls.length > 0 ? imageUrls : [""] };
    });
  }

  async function saveContent() {
    if (!draftId || !contentForm || !draft?.content_version) return;
    setBusy("content");
    setError("");
    try {
      const updated = await saveDraftContent(draftId, {
        ...contentForm,
        expected_content_version: draft.content_version,
        image_urls: contentForm.image_urls.map((url) => url.trim()).filter(Boolean),
      });
      onDraftChange(updated);
      setContentForm({
        expected_content_version: updated.content_version,
        title: updated.title,
        description: updated.description,
        brand: updated.brand,
        image_urls: updated.image_urls.length > 0 ? updated.image_urls : [""],
      });
      if (updated.content_version !== draft.content_version) {
        onReviewChange(null);
        setProviderReview(null);
      }
      setSavedDrafts((items) => items.map((item) => (item.id === draftId ? updated : item)));
    } catch (contentError) {
      const message = contentError instanceof Error ? contentError.message : "Failed to save content";
      setError(message.includes("draft_content_version_conflict")
        ? "This draft changed in another operation. Reload it before saving your edits."
        : message);
    } finally {
      setBusy("");
    }
  }

  async function calculateAndSavePricing() {
    if (!draft || !draftId) return;
    setBusy("pricing");
    setError("");
    try {
      const saved = await saveDraftPricing(draftId, pricing);
      setPricingResult(saved);
      const updatedDraft = saved.draft;
      onDraftChange(updatedDraft);
      onReviewChange(null);
      setProviderReview(null);
      setSavedDrafts((items) =>
        items.map((item) => (item.id === draftId ? { ...item, ...updatedDraft } : item)),
      );
    } catch (pricingError) {
      setError(pricingError instanceof Error ? pricingError.message : "Pricing failed");
    } finally {
      setBusy("");
    }
  }

  async function queueCurrentReview() {
    if (!draftId || !providerCostAcknowledged) return;
    setBusy("combined");
    setError("");
    try {
      const result = await enqueueBehavioralAuditBatch([draftId]);
      setBatchReviewResult(result);
      setReviewJobs(await listReviewJobs());
      setProviderCostAcknowledged(false);
    } catch (auditError) {
      setError(auditError instanceof Error ? auditError.message : "Behavioral audit failed");
    } finally {
      setBusy("");
    }
  }

  async function refreshReviewHistory() {
    if (!draftId) return;
    const requestedDraftId = draftId;
    const requestEpoch = ++historyEpochRef.current;
    setError("");
    try {
      const history = await listReviewHistory(requestedDraftId);
      if (
        historyEpochRef.current !== requestEpoch
        || currentDraftIdRef.current !== requestedDraftId
        || history.some((item) => item.product_draft_id !== requestedDraftId)
      ) return;
      setReviewHistory(history);
    } catch (historyError) {
      if (
        historyEpochRef.current === requestEpoch
        && currentDraftIdRef.current === requestedDraftId
      ) setError(historyError instanceof Error ? historyError.message : "Failed to load review history");
    }
  }

  function toggleBatchDraft(draftIdToToggle: number) {
    setSelectedDraftIds((current) => {
      const next = new Set(current);
      if (next.has(draftIdToToggle)) next.delete(draftIdToToggle);
      else if (next.size < MAX_REVIEW_BATCH_SIZE) next.add(draftIdToToggle);
      else setError(`A review batch can contain at most ${MAX_REVIEW_BATCH_SIZE} drafts.`);
      return next;
    });
    setBatchReviewResult(null);
  }

  async function queueBatchReview() {
    const draftIds = [...selectedDraftIds];
    if (
      !providerCostAcknowledged
      || draftIds.length === 0
      || Boolean(contentDirty && draftId && selectedDraftIds.has(draftId))
    ) return;
    setBusy("batch-review");
    setError("");
    try {
      const result = await enqueueBehavioralAuditBatch(draftIds);
      setBatchReviewResult(result);
      setReviewJobs(await listReviewJobs());
      setSelectedDraftIds(new Set());
      setProviderCostAcknowledged(false);
    } catch (batchError) {
      setError(batchError instanceof Error ? batchError.message : "Failed to queue batch review");
    } finally {
      setBusy("");
    }
  }

  const pricingReady = Boolean(draft?.price && draft.currency && pricingResult);
  const claudeReady = Boolean(readiness?.ai.claude_configured);
  const nvidiaReady = Boolean(readiness?.ai.nvidia_configured);
  const decision = typeof review?.decision === "string" ? review.decision : "not reviewed";
  const normalizedContentImages = contentForm?.image_urls.map((url) => url.trim()).filter(Boolean) ?? [];
  const contentDirty = Boolean(
    draft
    && contentForm
    && (
      contentForm.title !== draft.title
      || contentForm.description !== draft.description
      || contentForm.brand !== draft.brand
      || JSON.stringify(normalizedContentImages) !== JSON.stringify(draft.image_urls)
    )
  );

  useEffect(() => {
    onContentDirtyChange(contentDirty);
    return () => onContentDirtyChange(false);
  }, [contentDirty, onContentDirtyChange]);

  function selectSavedDraft(savedDraft: ProductDraftRead) {
    if (
      contentDirty
      && savedDraft.id !== draftId
      && !window.confirm("Discard unsaved listing content changes?")
    ) return;
    onSelectDraft(savedDraft);
  }

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">准备与审核</p>
          <h2>商品草稿</h2>
          <p>Price and configure the final listing before Claude and NVIDIA review it.</p>
        </div>
        {draftId && <span className="record-id">Draft #{draftId}</span>}
      </header>

      {!draft && <div className="empty-state">请先选择草稿，或去商品采集页面导入 Amazon 商品</div>}
      {draft && (
        <>
          <div className="product-summary">
            <ProductImage src={draft.image_urls[0]} alt={draft.title || "Product"} />
            <div>
              <h3>{draft.title || "未命名商品"}</h3>
              <p>{draft.brand || "Brand not captured"}</p>
              {draft.source_variant_asin && (
                <div className="variant-provenance">
                  <span>Amazon variant · {draft.source_variant_asin}</span>
                  <div>
                    {Object.entries(draft.source_variant_attributes ?? {}).map(([name, value]) => (
                      <span key={name}>{name}: {value}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="price-pair">
                <span>Amazon source <strong>{draft.source_currency} {draft.source_price ?? "-"}</strong></span>
                <span>Mercado Libre <strong>{draft.currency} {draft.price ?? "Not priced"}</strong></span>
              </div>
            </div>
          </div>

          {contentForm && (
            <section className="surface content-editor">
              <div className="section-heading">
                <div><h3>商品内容</h3></div>
                <span className={`state-pill ${contentDirty ? "blocked" : "ready"}`}>
                  {contentDirty ? "Unsaved" : `Version ${draft.content_version}`}
                </span>
              </div>
              <div className="form-grid two-col">
                <label className="full-span">标题<input
                    maxLength={200}
                    value={contentForm.title}
                    onChange={(event) => updateContentField("title", event.target.value)}
                  />
                </label>
                <label>品牌<input
                    maxLength={120}
                    value={contentForm.brand}
                    onChange={(event) => updateContentField("brand", event.target.value)}
                  />
                </label>
                <label className="full-span">商品描述<textarea
                    maxLength={50000}
                    rows={6}
                    value={contentForm.description}
                    onChange={(event) => updateContentField("description", event.target.value)}
                  />
                </label>
              </div>
              <div className="image-url-editor">
                <div className="section-heading compact">
                  <div><h4>Product images</h4></div>
                  <span>{contentForm.image_urls.filter(Boolean).length} / 12</span>
                </div>
                {contentForm.image_urls.map((url, index) => (
                  <div className="image-url-row" key={`${index}-${contentForm.expected_content_version}`}>
                    <ProductImage src={url} alt={`Product image ${index + 1}`} />
                    <input
                      aria-label={`商品图片链接 ${index + 1}`}
                      value={url}
                      onChange={(event) => updateContentImage(index, event.target.value)}
                    />
                    <button
                      className="icon-button secondary-button"
                      title="Remove image"
                      aria-label={`删除图片 ${index + 1}`}
                      onClick={() => removeContentImage(index)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                <button
                  className="secondary-button"
                  disabled={contentForm.image_urls.length >= 12}
                  onClick={() => setContentForm((current) => current
                    ? { ...current, image_urls: [...current.image_urls, ""] }
                    : current)}
                >
                  <Plus size={16} /> Add image
                </button>
              </div>
              <div className="action-line">
                <button
                  disabled={!contentForm.title.trim() || !contentDirty || busy === "content"}
                  onClick={saveContent}
                >
                  <Save size={16} /> {busy === "content" ? "Saving" : "保存内容"}
                </button>
                <button
                  className="secondary-button"
                  disabled={!contentDirty || busy === "content"}
                  onClick={() => setContentForm({
                    expected_content_version: draft.content_version ?? 1,
                    title: draft.title,
                    description: draft.description,
                    brand: draft.brand,
                    image_urls: draft.image_urls.length > 0 ? draft.image_urls : [""],
                  })}
                >
                  Reset
                </button>
                <span>Saving content requires a new AI 合规审核.</span>
              </div>
            </section>
          )}

          <div className="workflow-grid">
            <section className="surface">
              <div className="section-heading">
                <div><span className="step-number">1</span><h3>价格设置 · {draft.target_site_id}</h3></div>
                <span className={`state-pill ${pricingReady ? "ready" : "blocked"}`}>
                  {pricingReady ? "已保存" : "必填"}
                </span>
              </div>
              <div className="form-grid three-col">
                <label>Source price<input type="number" value={draft.source_price ?? ""} readOnly /></label>
                <label>Source currency<input value={draft.source_currency} readOnly /></label>
                <label>Exchange rate<input type="number" min="0" step="0.0001" value={pricing.exchange_rate} onChange={(event) => updatePricing("exchange_rate", event.target.value)} /></label>
                <label>Purchase extras<input type="number" min="0" step="0.01" value={pricing.purchase_extra_cost} onChange={(event) => updatePricing("purchase_extra_cost", event.target.value)} /></label>
                <label>Shipping cost<input type="number" min="0" step="0.01" value={pricing.shipping_cost} onChange={(event) => updatePricing("shipping_cost", event.target.value)} /></label>
                <label>Target currency<input value={pricing.target_currency} readOnly /></label>
                <label>Platform fee %<input type="number" min="0" max="99" step="0.1" value={pricing.platform_fee_rate * 100} onChange={(event) => updatePricing("platform_fee_rate", String(Number(event.target.value) / 100))} /></label>
                <label>Tax %<input type="number" min="0" max="99" step="0.1" value={pricing.tax_rate * 100} onChange={(event) => updatePricing("tax_rate", String(Number(event.target.value) / 100))} /></label>
                <label>Target profit %<input type="number" min="0" max="99" step="0.1" value={pricing.profit_margin_rate * 100} onChange={(event) => updatePricing("profit_margin_rate", String(Number(event.target.value) / 100))} /></label>
                <label>Round up to<input type="number" min="0.01" step="0.01" value={pricing.rounding_increment} onChange={(event) => updatePricing("rounding_increment", event.target.value)} /></label>
              </div>
              <div className="action-line">
                <button disabled={!draftId || contentDirty || pricing.source_price <= 0 || pricing.exchange_rate <= 0 || busy === "pricing"} onClick={calculateAndSavePricing}>
                  <Calculator size={16} /> Calculate and save
                </button>
                {pricingResult && (
                  <div className="calculation-result">
                    <span>Landed cost {pricingResult.target_currency} {pricingResult.landed_cost}</span>
                    <strong>Selling price {pricingResult.target_currency} {pricingResult.target_price}</strong>
                  </div>
                )}
              </div>
              {(!draft.source_price || !draft.source_currency) && (
                <p className="inline-warning">Amazon source price evidence is missing. Recollect the source page before pricing.</p>
              )}
            </section>

            <section className="surface">
              <div className="section-heading">
                <div><span className="step-number">2</span><h3>AI 合规审核</h3></div>
                <span className={`state-pill ${decision === "pass" ? "ready" : "blocked"}`}>{decision}</span>
              </div>
              <div className="provider-status">
                <div><Bot size={18} /><span>Claude</span><strong>{claudeReady ? "Configured" : "API key required"}</strong></div>
                <div><ShieldCheck size={18} /><span>NVIDIA</span><strong>{nvidiaReady ? "Configured" : "API key required"}</strong></div>
              </div>
              <div className="button-row">
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={providerCostAcknowledged}
                    onChange={(event) => setProviderCostAcknowledged(event.target.checked)}
                  />
                  Confirm Claude and NVIDIA usage costs
                </label>
                <button disabled={!draftId || contentDirty || !pricingReady || !listingConfigured || !claudeReady || !nvidiaReady || !providerCostAcknowledged || Boolean(busy)} onClick={queueCurrentReview}><ShieldCheck size={16} /> Queue combined audit</button>
                <button className="secondary-button" disabled={!draftId} onClick={refreshReviewHistory}><RefreshCw size={16} /> History</button>
              </div>
              {!pricingReady && <p className="inline-warning">Save pricing before running provider review.</p>}
              {pricingReady && !listingConfigured && <p className="inline-warning">Save the target category, Classic/Premium offer, and required attributes in Publish before running provider review.</p>}
              {providerReview && <ReviewSummary value={providerReview} />}
              {reviewHistory.length > 0 && (
                <div className="review-history-list">
                  {reviewHistory.map((result) => (
                    <div className="review-history-row" key={result.id}>
                      <span>
                        <strong>{result.provider}</strong>
                        <small>{result.model || "Unspecified model"} · {result.prompt_version || "legacy prompt"}</small>
                        {result.provider_status !== "completed" && (
                          <small className="warning-text">Historical evidence · draft changed</small>
                        )}
                        {result.provider_request_id && <small>Request {result.provider_request_id}</small>}
                      </span>
                      <span className="review-telemetry">
                        <small>{result.duration_ms > 0 ? `${result.duration_ms} ms` : "Time unavailable"}</small>
                        <small>
                          {result.total_tokens !== null
                            ? `${result.total_tokens} tokens · ${result.input_tokens ?? "?"} in / ${result.output_tokens ?? "?"} out`
                            : "Tokens unavailable"}
                        </small>
                        <small>
                          {result.estimated_cost_amount !== null
                            ? `${result.estimated_cost_currency} ${formatCost(result.estimated_cost_amount)}${result.price_config_id ? ` · price #${result.price_config_id}` : " · combined"}`
                            : result.price_config_id ? `Cost unavailable · price #${result.price_config_id}` : "Cost unavailable"}
                        </small>
                      </span>
                      <strong className={result.decision === "pass" && result.provider_status === "completed" ? "success-text" : ""}>{result.decision}</strong>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      )}

      {error && <p className="error">{error}</p>}
      <section className="saved-section">
        <div className="section-heading"><div><h3>已保存草稿</h3></div><span>{savedDrafts.length}</span></div>
        {savedDrafts.length === 0 && <p>No saved drafts yet.</p>}
        {savedDrafts.length > 0 && (
          <div className="batch-review-controls">
            <div className="action-line">
              <span>{selectedDraftIds.size} / {MAX_REVIEW_BATCH_SIZE} selected</span>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={providerCostAcknowledged}
                  onChange={(event) => setProviderCostAcknowledged(event.target.checked)}
                />
                Confirm Claude and NVIDIA usage costs
              </label>
              <button
                disabled={
                  selectedDraftIds.size === 0
                  || Boolean(contentDirty && draftId && selectedDraftIds.has(draftId))
                  || !providerCostAcknowledged
                  || !claudeReady
                  || !nvidiaReady
                  || Boolean(busy)
                }
                onClick={queueBatchReview}
              >
                <ListPlus size={16} /> Queue combined audits
              </button>
            </div>
            {batchReviewResult && (
              <div className="batch-result-summary" aria-live="polite">
                <strong>{batchReviewResult.queued_count} queued</strong>
                <span>{batchReviewResult.existing_count} active</span>
                <span>{batchReviewResult.not_ready_count} not ready</span>
                <span>{batchReviewResult.not_found_count} missing</span>
              </div>
            )}
            {batchReviewResult?.items.some((item) => item.errors.length > 0) && (
              <div className="batch-review-errors">
                {batchReviewResult.items.filter((item) => item.errors.length > 0).map((item) => (
                  <span key={item.draft_id}>Draft #{item.draft_id}: {item.errors.join(", ")}</span>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="draft-list">
          {savedDrafts.map((savedDraft) => (
            <div className="draft-selection-row" key={savedDraft.id}>
              <label className="draft-selector">
                <input
                  type="checkbox"
                  aria-label={`选择草稿 ${savedDraft.id} for combined audit`}
                  checked={selectedDraftIds.has(savedDraft.id)}
                  disabled={
                    Boolean(contentDirty && savedDraft.id === draftId)
                    || (
                      !selectedDraftIds.has(savedDraft.id)
                      && selectedDraftIds.size >= MAX_REVIEW_BATCH_SIZE
                    )
                  }
                  onChange={() => toggleBatchDraft(savedDraft.id)}
                />
              </label>
              <button className={`draft-row ${draftId === savedDraft.id ? "selected" : ""}`} onClick={() => selectSavedDraft(savedDraft)}>
                <ProductImage src={savedDraft.image_urls[0]} alt={savedDraft.title || "Product"} />
                <span className="draft-copy">
                  <strong>{savedDraft.title}</strong>
                  <small>#{savedDraft.id} · {savedDraft.target_site_id} · source {savedDraft.source_currency} {savedDraft.source_price ?? "-"} · target {savedDraft.currency} {savedDraft.price ?? "not priced"}</small>
                  {savedDraft.source_variant_asin && (
                    <small>
                      {savedDraft.source_variant_asin}
                      {Object.entries(savedDraft.source_variant_attributes).slice(0, 2).map(
                        ([name, value]) => ` · ${name}: ${value}`,
                      )}
                    </small>
                  )}
                </span>
                <span className="draft-state">{savedDraft.risk_status}</span>
              </button>
            </div>
          ))}
        </div>
        {reviewJobs.length > 0 && (
          <div className="review-job-list">
            {reviewJobs.slice(0, 20).map((job) => (
              <div key={job.id}>
                <span>Review #{job.id} · draft #{job.product_draft_id}</span>
                <strong>{job.status}</strong>
                {job.error_code && <small>{job.error_code}</small>}
                {job.next_attempt_at && (
                  <small>Available after {new Date(job.next_attempt_at).toLocaleString()}</small>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

function formatCost(value: number | string) {
  const raw = String(value);
  const match = /^(\d+)(?:\.(\d+))?$/.exec(raw);
  if (!match) return raw;
  return `${match[1]}.${(match[2] ?? "").padEnd(8, "0").slice(0, 8)}`;
}

function ReviewSummary({ value }: { value: Record<string, unknown> }) {
  const aggregate = (value.aggregate as Record<string, unknown> | undefined) ?? value;
  const reasons = Array.isArray(aggregate.reasons) ? aggregate.reasons : [];
  return (
    <div className="review-summary">
      <strong>{String(aggregate.decision ?? "Review complete")}</strong>
      <span>Risk: {String(aggregate.risk_level ?? "unknown")}</span>
      {reasons.map((reason) => <p key={String(reason)}>{String(reason)}</p>)}
    </div>
  );
}
