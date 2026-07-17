import { useEffect, useState } from "react";
import { Bot, Calculator, RefreshCw, ShieldCheck } from "lucide-react";
import {
  getDraftPricing,
  getDraftListingConfig,
  getSystemReadiness,
  listDrafts,
  listReviewHistory,
  reviewDraftWithBehavioralAudit,
  reviewDraftWithProvider,
  saveDraftPricing,
  type DraftPricing,
  type DraftPricingInput,
  type ProductDraft,
  type ProductDraftRead,
  type ReviewResult,
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

export function DraftsPage({
  draft,
  draftId,
  review,
  onReviewChange,
  onSelectDraft,
  onDraftChange,
}: {
  draft: ProductDraft | null;
  draftId: number | null;
  review: Record<string, unknown> | null;
  onReviewChange: (review: Record<string, unknown> | null) => void;
  onSelectDraft: (draft: ProductDraftRead) => void;
  onDraftChange: (draft: ProductDraft) => void;
}) {
  const [savedDrafts, setSavedDrafts] = useState<ProductDraftRead[]>([]);
  const [providerReview, setProviderReview] = useState<Record<string, unknown> | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewResult[]>([]);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [pricing, setPricing] = useState<DraftPricingInput>(EMPTY_PRICING);
  const [pricingResult, setPricingResult] = useState<DraftPricing | null>(null);
  const [listingConfigured, setListingConfigured] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([listDrafts(), getSystemReadiness()])
      .then(([drafts, system]) => {
        setSavedDrafts(drafts);
        setReadiness(system);
      })
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load drafts"),
      );
  }, []);

  useEffect(() => {
    if (!draft) return;
    setProviderReview(null);
    setReviewHistory([]);
    setPricingResult(null);
    setListingConfigured(false);
    setPricing({
      ...EMPTY_PRICING,
      source_price: draft.source_price ?? draft.price ?? 0,
      source_currency: draft.source_currency || draft.currency || "USD",
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
  }, [draftId]);

  function updatePricing(name: keyof DraftPricingInput, value: string) {
    if (name === "source_currency" || name === "target_currency") {
      setPricing((current) => ({ ...current, [name]: value.toUpperCase() }));
      return;
    }
    setPricing((current) => ({ ...current, [name]: Number(value) }));
  }

  async function calculateAndSavePricing() {
    if (!draft || !draftId) return;
    setBusy("pricing");
    setError("");
    try {
      const saved = await saveDraftPricing(draftId, pricing);
      setPricingResult(saved);
      const updatedDraft = {
        ...draft,
        source_price: saved.source_price,
        source_currency: saved.source_currency,
        price: saved.target_price,
        currency: saved.target_currency,
      };
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

  async function runProviderReview(provider: "claude" | "nvidia") {
    if (!draft) return;
    setBusy(provider);
    setError("");
    try {
      const nextReview = await reviewDraftWithProvider(draft, provider, draftId);
      setProviderReview(nextReview);
      onReviewChange(nextReview);
      if (draftId) setReviewHistory(await listReviewHistory(draftId));
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : "Provider review failed");
    } finally {
      setBusy("");
    }
  }

  async function runBehavioralAudit() {
    if (!draft) return;
    setBusy("combined");
    setError("");
    try {
      const result = await reviewDraftWithBehavioralAudit(draft, draftId);
      setProviderReview(result);
      onReviewChange(result.aggregate);
      if (draftId) setReviewHistory(await listReviewHistory(draftId));
    } catch (auditError) {
      setError(auditError instanceof Error ? auditError.message : "Behavioral audit failed");
    } finally {
      setBusy("");
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

  const pricingReady = Boolean(draft?.price && draft.currency && pricingResult);
  const claudeReady = Boolean(readiness?.ai.claude_configured);
  const nvidiaReady = Boolean(readiness?.ai.nvidia_configured);
  const decision = typeof review?.decision === "string" ? review.decision : "not reviewed";

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">Prepare and review</p>
          <h2>Product draft</h2>
          <p>Price and configure the final listing before Claude and NVIDIA review it.</p>
        </div>
        {draftId && <span className="record-id">Draft #{draftId}</span>}
      </header>

      {!draft && <div className="empty-state">Select a saved draft or collect an Amazon URL first.</div>}
      {draft && (
        <>
          <div className="product-summary">
            <img src={draft.image_urls[0]} alt="" />
            <div>
              <h3>{draft.title || "Untitled product"}</h3>
              <p>{draft.brand || "Brand not captured"}</p>
              <div className="price-pair">
                <span>Amazon source <strong>{draft.source_currency} {draft.source_price ?? "-"}</strong></span>
                <span>Mercado Libre <strong>{draft.currency} {draft.price ?? "Not priced"}</strong></span>
              </div>
            </div>
          </div>

          <div className="workflow-grid">
            <section className="surface">
              <div className="section-heading">
                <div><span className="step-number">1</span><h3>Price for {draft.target_site_id}</h3></div>
                <span className={`state-pill ${pricingReady ? "ready" : "blocked"}`}>
                  {pricingReady ? "Saved" : "Required"}
                </span>
              </div>
              <div className="form-grid three-col">
                <label>Source price<input type="number" min="0" step="0.01" value={pricing.source_price} onChange={(event) => updatePricing("source_price", event.target.value)} /></label>
                <label>Source currency<input value={pricing.source_currency} onChange={(event) => updatePricing("source_currency", event.target.value)} /></label>
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
                <button disabled={!draftId || pricing.source_price <= 0 || pricing.exchange_rate <= 0 || busy === "pricing"} onClick={calculateAndSavePricing}>
                  <Calculator size={16} /> Calculate and save
                </button>
                {pricingResult && (
                  <div className="calculation-result">
                    <span>Landed cost {pricingResult.target_currency} {pricingResult.landed_cost}</span>
                    <strong>Selling price {pricingResult.target_currency} {pricingResult.target_price}</strong>
                  </div>
                )}
              </div>
            </section>

            <section className="surface">
              <div className="section-heading">
                <div><span className="step-number">2</span><h3>Claude + NVIDIA review</h3></div>
                <span className={`state-pill ${decision === "pass" ? "ready" : "blocked"}`}>{decision}</span>
              </div>
              <div className="provider-status">
                <div><Bot size={18} /><span>Claude</span><strong>{claudeReady ? "Configured" : "API key required"}</strong></div>
                <div><ShieldCheck size={18} /><span>NVIDIA</span><strong>{nvidiaReady ? "Configured" : "API key required"}</strong></div>
              </div>
              <div className="button-row">
                <button disabled={!pricingReady || !listingConfigured || !claudeReady || Boolean(busy)} onClick={() => runProviderReview("claude")}><Bot size={16} /> Claude review</button>
                <button disabled={!pricingReady || !listingConfigured || !nvidiaReady || Boolean(busy)} onClick={() => runProviderReview("nvidia")}><ShieldCheck size={16} /> NVIDIA review</button>
                <button disabled={!pricingReady || !listingConfigured || !claudeReady || !nvidiaReady || Boolean(busy)} onClick={runBehavioralAudit}><ShieldCheck size={16} /> Combined audit</button>
                <button className="secondary-button" disabled={!draftId} onClick={refreshReviewHistory}><RefreshCw size={16} /> History</button>
              </div>
              {!pricingReady && <p className="inline-warning">Save pricing before running provider review.</p>}
              {pricingReady && !listingConfigured && <p className="inline-warning">Save the target category, Classic/Premium offer, and required attributes in Publish before running provider review.</p>}
              {providerReview && <ReviewSummary value={providerReview} />}
              {reviewHistory.length > 0 && <p className="muted">{reviewHistory.length} saved review result(s).</p>}
            </section>
          </div>
        </>
      )}

      {error && <p className="error">{error}</p>}
      <section className="saved-section">
        <div className="section-heading"><div><h3>Saved drafts</h3></div><span>{savedDrafts.length}</span></div>
        {savedDrafts.length === 0 && <p>No saved drafts yet.</p>}
        <div className="draft-list">
          {savedDrafts.map((savedDraft) => (
            <button className={`draft-row ${draftId === savedDraft.id ? "selected" : ""}`} key={savedDraft.id} onClick={() => onSelectDraft(savedDraft)}>
              <img src={savedDraft.image_urls[0]} alt="" />
              <span className="draft-copy">
                <strong>{savedDraft.title}</strong>
                <small>#{savedDraft.id} · {savedDraft.target_site_id} · source {savedDraft.source_currency} {savedDraft.source_price ?? "-"} · target {savedDraft.currency} {savedDraft.price ?? "not priced"}</small>
              </span>
              <span className="draft-state">{savedDraft.risk_status}</span>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
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
