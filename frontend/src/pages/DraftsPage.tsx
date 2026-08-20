import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Calculator,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Edit3,
  GripVertical,
  ImageOff,
  ListPlus,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
  Video,
} from "lucide-react";
import {
  enqueueBehavioralAuditBatch,
  getDraftPricing,
  getDraftListingConfig,
  getCategoryAttributes,
  getCategoryDetails,
  getCategoryPredictions,
  confirmDraftCategory,
  generateDraftContent,
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
  cost_currency: "CNY",
  purchase_cost: 0,
  domestic_shipping_cost: 0,
  exchange_rate: 1,
  profit_margin_rate: 0.2,
  rounding_increment: 0.01,
};

const MAX_REVIEW_BATCH_SIZE = 50;
const UNBRANDED = "Unbranded";

const MARKETING_TERMS = [
  "best", "top", "hot", "sale", "discount", "free shipping", "limited",
  "premium", "buy now", "deal", "clearance", "guaranteed",
];

function removePhrase(value: string, phrase: string) {
  if (!phrase.trim()) return value;
  return value.replace(
    new RegExp(`(?<![A-Za-z0-9])${phrase.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![A-Za-z0-9])`, "ig"),
    "",
  );
}

function normalizeListingTitle(value: string, sourceBrand = "") {
  let title = value.replace(/\s+/g, " ").trim();
  title = removePhrase(title, sourceBrand);
  MARKETING_TERMS.forEach((term) => { title = removePhrase(title, term); });
  return title.replace(/\s+/g, " ").trim().slice(0, 60).trimEnd();
}

function sanitizeUnbrandedDescription(value: string, sourceBrand = "") {
  return value
    .split("\n")
    .filter((line) => !/^\s*(brand|brand name|marca)\s*[:\-]/i.test(line))
    .join("\n")
    .split(sourceBrand ? new RegExp(`(?<![A-Za-z0-9])${sourceBrand.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![A-Za-z0-9])`, "ig") : /$^/)
    .join("")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function sourceBrandFromDraft(draft: ProductDraft) {
  const match = draft.description.match(/^\s*Brand\s*:\s*(.+?)\s*$/im);
  return match?.[1]?.trim() ?? "";
}

function imageIdentity(url: string) {
  try {
    const parsed = new URL(url);
    parsed.pathname = parsed.pathname.replace(/\._AC(?:_[A-Z]+\d*)*_(?=\.[A-Za-z0-9]+$)/i, "");
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().toLowerCase();
  } catch {
    return url.trim().toLowerCase();
  }
}

function imageResolution(url: string) {
  const match = url.match(/\._AC_(?:SL|SX|SY|US)(\d+)_/i);
  return match ? Number(match[1]) : 10000;
}

function selectListingImages(urls: string[], limit = 12) {
  const selected = new Map<string, { url: string; resolution: number; index: number }>();
  urls.forEach((rawUrl, index) => {
    const url = rawUrl.trim();
    if (!url) return;
    const identity = imageIdentity(url);
    const candidate = { url, resolution: imageResolution(url), index };
    const current = selected.get(identity);
    if (!current || candidate.resolution > current.resolution) selected.set(identity, candidate);
  });
  return [...selected.values()].slice(0, limit).map((item) => item.url);
}

function categoryPathLabel(value: unknown) {
  if (!Array.isArray(value)) return "官方候选分类";
  return value
    .map((item) => {
      if (!item || typeof item !== "object") return String(item);
      const record = item as Record<string, unknown>;
      return String(record.name_zh ?? record.name ?? "");
    })
    .filter(Boolean)
    .join(" > ") || "官方候选分类";
}

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

function MediaImage({ src, alt }: { src: string; alt: string }) {
  const [dimensions, setDimensions] = useState("");
  if (!src) return <ProductImage src={src} alt={alt} />;
  return (
    <>
      <img
        className="product-image"
        src={src}
        alt={alt}
        onLoad={(event) => setDimensions(`${event.currentTarget.naturalWidth} × ${event.currentTarget.naturalHeight}`)}
      />
      <small className="media-dimensions">{dimensions || "读取图片尺寸中"}</small>
    </>
  );
}

export function DraftsPage({
  draft,
  draftId,
  review,
  onReviewChange,
  onSelectDraft,
  onDraftChange,
  onContentDirtyChange,
  onContinueListing,
}: {
  draft: ProductDraft | null;
  draftId: number | null;
  review: Record<string, unknown> | null;
  onReviewChange: (review: Record<string, unknown> | null) => void;
  onSelectDraft: (draft: ProductDraftRead) => void;
  onDraftChange: (draft: ProductDraft) => void;
  onContentDirtyChange: (dirty: boolean) => void;
  onContinueListing: () => void;
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
  const [categoryQuery, setCategoryQuery] = useState("");
  const [categoryPredictions, setCategoryPredictions] = useState<Record<string, unknown>[]>([]);
  const [categoryAttributes, setCategoryAttributes] = useState<Record<string, unknown>[]>([]);
  const [categoryVerified, setCategoryVerified] = useState(false);
  const [categoryLeafVerified, setCategoryLeafVerified] = useState(false);
  const [categoryLabel, setCategoryLabel] = useState("");
  const [categoryPath, setCategoryPath] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [draggingImageIndex, setDraggingImageIndex] = useState<number | null>(null);
  const draftEpochRef = useRef(0);
  const historyEpochRef = useRef(0);
  const currentDraftIdRef = useRef(draftId);
  const imageInputRefs = useRef<Record<number, HTMLInputElement | null>>({});
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
    const sourceBrand = sourceBrandFromDraft(draft);
    setContentForm({
      expected_content_version: draft.content_version,
      title: normalizeListingTitle(draft.title, sourceBrand),
      description: sanitizeUnbrandedDescription(draft.description, sourceBrand),
      brand: UNBRANDED,
      image_urls: selectListingImages(draft.image_urls).length > 0 ? selectListingImages(draft.image_urls) : [""],
      video_urls: draft.video_urls ?? [],
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
    setCategoryQuery(draft.title);
    setCategoryAttributes([]);
    setCategoryVerified(false);
    setCategoryLeafVerified(false);
    setCategoryLabel("");
    setCategoryPath([]);
    setPricing({
      ...EMPTY_PRICING,
      source_price: draft.source_price ?? 0,
      source_currency: draft.source_currency || "",
      target_currency: currencyForSite(draft.target_site_id) || draft.currency,
    });
    if (!draftId) return;
    if (draft.target_category_id) {
      getCategoryDetails(draft.target_category_id)
        .then((result) => {
          setCategoryLeafVerified(result.verified && result.leaf);
          setCategoryLabel(result.name_zh || result.name);
          setCategoryPath((result.path_from_root_zh ?? result.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean));
        })
        .catch(() => setCategoryLeafVerified(false));
      getCategoryAttributes(draft.target_category_id)
        .then((result) => {
          setCategoryAttributes(result.attributes);
          setCategoryVerified(result.verified);
        })
        .catch(() => undefined);
    }
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
    setContentForm((current) => {
      if (!current) return current;
      if (name === "brand") return { ...current, brand: UNBRANDED };
      return {
        ...current,
        [name]: name === "title" ? normalizeListingTitle(value, draft ? sourceBrandFromDraft(draft) : "") : value,
      };
    });
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

  function moveContentImage(index: number, direction: -1 | 1) {
    setContentForm((current) => {
      if (!current) return current;
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.image_urls.length) return current;
      const imageUrls = [...current.image_urls];
      [imageUrls[index], imageUrls[nextIndex]] = [imageUrls[nextIndex], imageUrls[index]];
      return { ...current, image_urls: imageUrls };
    });
  }

  function setCoverImage(index: number) {
    if (index === 0) return;
    setContentForm((current) => {
      if (!current || index < 0 || index >= current.image_urls.length) return current;
      const imageUrls = [...current.image_urls];
      const [cover] = imageUrls.splice(index, 1);
      imageUrls.unshift(cover);
      return { ...current, image_urls: imageUrls };
    });
  }

  function dropContentImage(targetIndex: number) {
    setContentForm((current) => {
      if (!current || draggingImageIndex === null || draggingImageIndex === targetIndex) return current;
      const imageUrls = [...current.image_urls];
      const [moved] = imageUrls.splice(draggingImageIndex, 1);
      imageUrls.splice(targetIndex, 0, moved);
      return { ...current, image_urls: imageUrls };
    });
    setDraggingImageIndex(null);
  }

  function updateContentVideo(index: number, value: string) {
    setContentForm((current) => {
      if (!current) return current;
      const videoUrls = [...(current.video_urls ?? [])];
      videoUrls[index] = value;
      return { ...current, video_urls: videoUrls };
    });
  }

  function removeContentVideo(index: number) {
    setContentForm((current) => current
      ? { ...current, video_urls: (current.video_urls ?? []).filter((_, itemIndex) => itemIndex !== index) }
      : current);
  }

  async function searchCategories() {
    if (!draft) return;
    const query = categoryQuery.trim() || draft.title.trim();
    if (!query) return;
    setBusy("category-search");
    setError("");
    try {
      const result = await getCategoryPredictions(draft.target_site_id, query);
      const enrichedPredictions = await Promise.all(result.predictions.slice(0, 8).map(async (prediction) => {
        const categoryId = String(prediction.category_id ?? prediction.id ?? "");
        if (!categoryId) return prediction;
        try {
          const details = await getCategoryDetails(categoryId);
          return {
            ...prediction,
            category_name_zh: details.name_zh,
            path_from_root: details.path_from_root,
            path_from_root_zh: details.path_from_root_zh,
            is_leaf: details.leaf,
          };
        } catch {
          return prediction;
        }
      }));
      setCategoryPredictions(enrichedPredictions);
    } catch (categoryError) {
      setError(readableDraftError(categoryError, "分类搜索失败"));
    } finally {
      setBusy("");
    }
  }

  async function confirmCategory(categoryId: string) {
    if (!draftId || !draft?.content_version) return;
    setBusy("category-confirm");
    setError("");
    try {
      const details = await getCategoryDetails(categoryId);
      if (!details.verified || !details.leaf) {
        throw new Error("该分类还有下级分类，请选择最底层分类后再确认。 ");
      }
      const result = await confirmDraftCategory(draftId, {
        expected_content_version: draft.content_version,
        target_site_id: draft.target_site_id,
        category_id: categoryId,
      });
      onDraftChange(result.draft);
      let attributes = result.attributes;
      let verified = result.attributes_verified;
      if (!verified) {
        const metadata = await getCategoryAttributes(categoryId);
        attributes = metadata.attributes;
        verified = metadata.verified;
      }
      setCategoryAttributes(attributes);
      setCategoryVerified(verified);
      setCategoryLeafVerified(true);
      setCategoryLabel(details.name_zh || details.name);
      setCategoryPath((details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean));
      setCategoryPredictions([]);
      setListingConfigured(false);
      onReviewChange(null);
      setProviderReview(null);
      setSavedDrafts((items) => items.map((item) => item.id === draftId ? result.draft : item));
    } catch (categoryError) {
      setError(readableDraftError(categoryError, "分类确认失败"));
    } finally {
      setBusy("");
    }
  }

  async function generateContentWithVolcengine() {
    if (!draftId || !categoryConfirmed) return;
    setBusy("generate-content");
    setError("");
    try {
      const result = await generateDraftContent(draftId, draft!.target_category_id);
      onDraftChange(result.draft);
      setSavedDrafts((items) => items.map((item) => item.id === draftId ? result.draft : item));
      setContentForm((current) => current ? {
        ...current,
        expected_content_version: result.draft.content_version,
        title: result.title,
        description: result.description,
        brand: result.brand,
      } : current);
      onReviewChange(null);
      setProviderReview(null);
    } catch (generationError) {
      setError(readableDraftError(generationError, "火山 AI 生成失败"));
    } finally {
      setBusy("");
    }
  }

  async function saveContent() {
    if (!draftId || !contentForm || !draft?.content_version) return;
    setBusy("content");
    setError("");
    try {
      const selectedImages = selectListingImages(contentForm.image_urls);
      const updated = await saveDraftContent(draftId, {
        ...contentForm,
        expected_content_version: draft.content_version,
        title: normalizeListingTitle(contentForm.title, sourceBrandFromDraft(draft)),
        brand: UNBRANDED,
        image_urls: selectedImages,
        description: sanitizeUnbrandedDescription(contentForm.description, sourceBrandFromDraft(draft)),
        video_urls: (contentForm.video_urls ?? []).map((url) => url.trim()).filter(Boolean),
      });
      onDraftChange(updated);
      setContentForm({
        expected_content_version: updated.content_version,
        title: normalizeListingTitle(updated.title, sourceBrandFromDraft(draft)),
        description: sanitizeUnbrandedDescription(updated.description, sourceBrandFromDraft(draft)),
        brand: UNBRANDED,
        image_urls: selectListingImages(updated.image_urls).length > 0 ? selectListingImages(updated.image_urls) : [""],
        video_urls: updated.video_urls ?? [],
      });
      if (updated.content_version !== draft.content_version) {
        onReviewChange(null);
        setProviderReview(null);
      }
      setSavedDrafts((items) => items.map((item) => (item.id === draftId ? updated : item)));
    } catch (contentError) {
      const message = readableDraftError(contentError, "保存内容失败");
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
  const normalizedContentVideos = contentForm?.video_urls?.map((url) => url.trim()).filter(Boolean) ?? [];
  const sourceBrand = draft ? sourceBrandFromDraft(draft) : "";
  const selectedDraftImages = draft ? selectListingImages(draft.image_urls) : [];
  const categoryConfirmed = Boolean(draft?.target_category_id && categoryVerified && categoryLeafVerified);
  const titleValid = Boolean(contentForm?.title.trim() && contentForm.title.length <= 60);
  const contentDirty = Boolean(
    draft
    && contentForm
    && (
      contentForm.title !== draft.title
      || contentForm.description !== draft.description
      || contentForm.brand !== draft.brand
      || JSON.stringify(normalizedContentImages) !== JSON.stringify(draft.image_urls)
      || JSON.stringify(normalizedContentVideos) !== JSON.stringify(draft.video_urls ?? [])
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
          <p className="eyebrow">第二步</p>
          <h2>编辑上架</h2>
          <p>分类、属性、标题、图片、价格都在这一张上架单中处理；能自动处理的交给 AI，不能处理的再人工确认。</p>
        </div>
        {draftId && <span className="record-id">上架单 #{draftId}</span>}
      </header>

      <div className="drafts-layout">
        <aside className="drafts-sidebar surface">
          <div className="drafts-sidebar-heading"><h3>上架库</h3><span>{savedDrafts.length} 个</span></div>
          <p className="section-note">选择商品后，在右侧按顺序完成分类、内容、素材、价格和审核。</p>
          <div className="draft-rail-list">
            {savedDrafts.map((savedDraft) => (
              <button className={`draft-rail-item ${draftId === savedDraft.id ? "selected" : ""}`} key={savedDraft.id} onClick={() => selectSavedDraft(savedDraft)}>
                <ProductImage src={selectListingImages(savedDraft.image_urls)[0] ?? savedDraft.image_urls[0]} alt="" />
                <span><strong>{savedDraft.title || "未命名商品"}</strong><small>#{savedDraft.id} · {savedDraft.target_site_id}</small><small>{savedDraft.risk_status}</small></span>
              </button>
            ))}
          </div>
        </aside>
        <div className="drafts-main">
      {!draft && <div className="empty-state">请先选择草稿，或去商品采集页面导入 Amazon 商品</div>}
      {draft && (
        <>
          <div className="product-summary">
            <ProductImage src={selectedDraftImages[0] ?? draft.image_urls[0]} alt={draft.title || "Product"} />
            <div>
              <h3>{contentForm?.title || normalizeListingTitle(draft.title, sourceBrand) || "未命名商品"}</h3>
              <p>品牌：{UNBRANDED} · 来源素材已隔离</p>
              {draft.source_variant_asin && (
                <div className="variant-provenance">
                  <span>Amazon 变体 · {draft.source_variant_asin}</span>
                  <div>
                    {Object.entries(draft.source_variant_attributes ?? {}).map(([name, value]) => (
                      <span key={name}>{name}: {value}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="price-pair">
                <span>Amazon 采集价 <strong>{draft.source_currency} {draft.source_price ?? "-"}</strong></span>
                <span>美客多售价 <strong>{draft.currency} {draft.price ?? "未定价"}</strong></span>
              </div>
            </div>
          </div>

          <section className="surface category-first-card">
            <div className="section-heading">
              <div><span className="step-number">1</span><h3>先确认 Mercado Libre 最终分类</h3></div>
              <span className={`state-pill ${categoryConfirmed ? "ready" : "blocked"}`}>
                {categoryConfirmed ? "分类已确认" : "必须先完成"}
              </span>
            </div>
            <p className="section-note">先从官方候选中选择最底层分类。只有叶子分类确认后，系统才读取该分类的必填属性、可选值和变体属性；更换分类会清空旧的刊登配置。</p>
            <div className="category-search-line">
              <input
                value={categoryQuery}
                placeholder="输入中文或英文关键词搜索分类"
                onChange={(event) => setCategoryQuery(event.target.value)}
              />
              <button className="secondary-button" disabled={!categoryQuery.trim() || busy === "category-search"} onClick={searchCategories}>
                {busy === "category-search" ? "搜索中" : "搜索分类"}
              </button>
            </div>
            {draft.target_category_id && (
                <div className="category-confirmed-row">
                  <CheckCircle2 size={17} />
                  <span className="category-confirmed-copy"><strong>{categoryLabel || "已确认最终分类"}</strong><small>{categoryPath.length > 0 ? categoryPath.join(" > ") : draft.target_category_id} · {draft.target_category_id}</small></span>
                  <span>{categoryConfirmed ? `叶子分类 · 已读取 ${categoryAttributes.length} 项官方属性` : "正在验证叶子分类和官方属性"}</span>
                </div>
            )}
            {categoryPredictions.length > 0 && (
              <div className="category-prediction-list">
                {categoryPredictions.slice(0, 8).map((prediction, index) => {
                  const categoryId = String(prediction.category_id ?? prediction.id ?? "");
                  const categoryName = String(prediction.category_name ?? prediction.name ?? categoryId);
                  const categoryNameZh = String(prediction.category_name_zh ?? categoryName);
                  const isLeaf = prediction.is_leaf === true ? true : prediction.is_leaf === false ? false : null;
                  const path = categoryPathLabel(prediction.path_from_root_zh ?? prediction.path_from_root);
                  return (
                    <button className={`category-prediction-item ${isLeaf === false ? "is-parent" : ""}`} key={`${categoryId}-${index}`} disabled={!categoryId || isLeaf === false || busy === "category-confirm"} onClick={() => confirmCategory(categoryId)}>
                      <span className="category-prediction-copy"><strong>{categoryNameZh}</strong><small>{path}</small><small className="category-official-label">官方：{categoryName} · {categoryId}</small></span>
                      <span className="category-prediction-action">{busy === "category-confirm" ? "验证中" : isLeaf === true ? "叶子分类 · 验证并确认" : isLeaf === false ? "还有下级分类" : "验证分类"}</span>
                    </button>
                  );
                })}
              </div>
            )}
            {categoryConfirmed && (
              <div className="category-attribute-summary">
                <div className="attribute-summary-head"><strong>官方属性已加载</strong><span>必填 {categoryAttributes.filter((item) => Boolean((item.tags as Record<string, unknown> | undefined)?.required || (item.tags as Record<string, unknown> | undefined)?.catalog_required)).length} 项 · 变体 {categoryAttributes.filter((item) => Boolean((item.tags as Record<string, unknown> | undefined)?.variation_attribute)).length} 项</span></div>
                <div className="attribute-chip-list">
                  {categoryAttributes.filter((item) => !Boolean((item.tags as Record<string, unknown> | undefined)?.hidden)).slice(0, 18).map((item) => (
                    <span key={String(item.id)}>{String(item.name ?? item.id)}{Boolean((item.tags as Record<string, unknown> | undefined)?.required) ? " *" : ""}</span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {contentForm && (
            <section className="surface content-editor">
              <div className="section-heading">
                <div><h3>商品内容</h3></div>
                <span className={`state-pill ${contentDirty ? "blocked" : "ready"}`}>
                  {contentDirty ? "尚未保存" : `版本 ${draft.content_version}`}
                </span>
              </div>
              <div className="form-grid two-col">
                 <label className="full-span">英文标题 <span className={`field-hint ${contentForm.title.length >= 60 ? "limit-reached" : ""}`}>{contentForm.title.length}/60</span><input
                     maxLength={60}
                    value={contentForm.title}
                    onChange={(event) => updateContentField("title", event.target.value)}
                  />
                </label>
                 <label>品牌（固定无品牌）<input
                     value={UNBRANDED}
                     readOnly
                   /><small className="field-note">Amazon 来源品牌仅用于采集证据，不会写入 Mercado Libre。</small>
                 </label>
                 <label className="full-span">商品描述<textarea
                    maxLength={50000}
                    rows={6}
                    value={contentForm.description}
                   onChange={(event) => updateContentField("description", event.target.value)}
                   /><small className="field-note">描述不得出现 Amazon 品牌；保存时系统会再次清理并校验。</small>
                </label>
              </div>
              <div className="ai-content-bar">
                <div><Sparkles size={17} /><span>使用火山 AI 根据 Amazon 素材生成合规英文标题和描述</span></div>
                <button className="secondary-button" disabled={!categoryConfirmed || busy === "generate-content"} onClick={generateContentWithVolcengine}>
                  <Sparkles size={15} /> {busy === "generate-content" ? "生成中" : "火山 AI 生成并保存"}
                </button>
              </div>
              <div className="image-url-editor">
                 <div className="section-heading compact media-library-heading">
                   <div><h4>图片素材库</h4><p className="section-note">拖动图片调整顺序，第一张为主图；系统会合并同一张 Amazon 图片的不同尺寸，保留最高分辨率版本。</p></div>
                  <strong className="media-count">{contentForm.image_urls.filter(Boolean).length} / 12</strong>
                </div>
                {draft.image_urls.length > selectedDraftImages.length && <p className="inline-warning media-normalization-note">已从 {draft.image_urls.length} 条采集资源中去重，当前保留 {selectedDraftImages.length} 张可上架图片。</p>}
                <div className="media-library-grid">
                  {contentForm.image_urls.map((url, index) => (
                   <div
                     className={`media-tile ${index === 0 ? "is-cover" : ""} ${draggingImageIndex === index ? "is-dragging" : ""}`}
                     key={`${index}-${contentForm.expected_content_version}`}
                     draggable
                     onDragStart={() => setDraggingImageIndex(index)}
                     onDragOver={(event) => event.preventDefault()}
                     onDrop={() => dropContentImage(index)}
                     onDragEnd={() => setDraggingImageIndex(null)}
                   >
                      <div className="media-tile-topline"><span><GripVertical size={15} /> 图片 {index + 1}</span><span>{index === 0 ? "主图" : `排序 ${index + 1}`}</span></div>
                      <MediaImage src={url} alt={`商品图片 ${index + 1}`} />
                      {index === 0 && <span className="cover-label">主图</span>}
                      <input ref={(element) => { imageInputRefs.current[index] = element; }} aria-label={`商品图片链接 ${index + 1}`} placeholder="粘贴图片地址" value={url} onChange={(event) => updateContentImage(index, event.target.value)} />
                      <div className="media-tile-actions">
                        <button className="media-tool-button" title="设为主图" aria-label={`图片 ${index + 1} 设为主图`} disabled={index === 0} onClick={() => setCoverImage(index)}><Star size={14} /> 主图</button>
                        <button className="media-tool-button" title="编辑图片地址" aria-label={`编辑图片 ${index + 1} 地址`} onClick={() => imageInputRefs.current[index]?.focus()}><Edit3 size={14} /> 编辑</button>
                        <button className="icon-button secondary-button" title="上移" aria-label={`图片 ${index + 1} 上移`} disabled={index === 0} onClick={() => moveContentImage(index, -1)}><ChevronUp size={14} /></button>
                        <button className="icon-button secondary-button" title="下移" aria-label={`图片 ${index + 1} 下移`} disabled={index === contentForm.image_urls.length - 1} onClick={() => moveContentImage(index, 1)}><ChevronDown size={14} /></button>
                        <button className="icon-button secondary-button media-delete-button" title="删除图片" aria-label={`删除图片 ${index + 1}`} onClick={() => removeContentImage(index)}><Trash2 size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="media-library-toolbar"><span><GripVertical size={15} /> 可拖动排序</span><span>图片必须为公开 HTTPS 地址</span><span>发布最多 12 张</span></div>
                <button
                  className="secondary-button"
                  disabled={contentForm.image_urls.length >= 12}
                  onClick={() => setContentForm((current) => current
                    ? { ...current, image_urls: [...current.image_urls, ""] }
                    : current)}
                >
                  <Plus size={16} /> 添加图片
                </button>
              </div>
              <div className="video-library">
                <div className="section-heading compact"><div><h4><Video size={16} /> 视频素材</h4></div><span>{(contentForm.video_urls ?? []).length} / 3</span></div>
                {(contentForm.video_urls ?? []).map((url, index) => (
                  <div className="video-url-row" key={`${index}-${contentForm.expected_content_version}`}>
                    <Video size={18} /><input aria-label={`视频链接 ${index + 1}`} placeholder="粘贴视频地址（MP4/MOV）" value={url} onChange={(event) => updateContentVideo(index, event.target.value)} /><button className="icon-button secondary-button" aria-label={`删除视频 ${index + 1}`} onClick={() => removeContentVideo(index)}><Trash2 size={15} /></button>
                  </div>
                ))}
                <button className="secondary-button" disabled={(contentForm.video_urls ?? []).length >= 3} onClick={() => setContentForm((current) => current ? { ...current, video_urls: [...(current.video_urls ?? []), ""] } : current)}><Plus size={16} /> 添加视频</button>
                <p className="section-note">视频先独立保存和人工确认，只有目标站点支持时才进入发布请求。</p>
              </div>
              <div className="action-line">
                <button
                   disabled={!titleValid || !contentForm.title.trim() || !contentDirty || busy === "content"}
                  onClick={saveContent}
                >
                  <Save size={16} /> {busy === "content" ? "保存中" : "保存内容"}
                </button>
                <button
                  className="secondary-button"
                  disabled={!contentDirty || busy === "content"}
                  onClick={() => setContentForm({
                    expected_content_version: draft.content_version ?? 1,
                    title: normalizeListingTitle(draft.title, sourceBrand),
                    description: sanitizeUnbrandedDescription(draft.description, sourceBrand),
                    brand: UNBRANDED,
                    image_urls: selectedDraftImages.length > 0 ? selectedDraftImages : [""],
                    video_urls: draft.video_urls ?? [],
                  })}
                >
                  恢复已保存内容
                </button>
                <span>保存后必须重新进行合规审核。</span>
              </div>
            </section>
          )}

          <section className="surface draft-submit-flow">
            <div className="section-heading"><div><h3>上架流程</h3></div><span className="section-note">每一步完成后才能进入下一步</span></div>
            <div className="draft-flow-steps">
              {[
                ["分类", categoryConfirmed],
                ["属性与变体", categoryConfirmed && categoryAttributes.length > 0],
                ["内容与素材", Boolean(contentForm && !contentDirty && contentForm.title.length <= 60)],
                ["价格", pricingReady],
                ["审核与发布", decision === "pass" && listingConfigured],
              ].map(([label, done], index) => (
                <div className={`draft-flow-step ${done ? "done" : "pending"}`} key={String(label)}>
                  <span>{done ? <CheckCircle2 size={16} /> : index + 1}</span><strong>{label}</strong>
                </div>
              ))}
            </div>
            {!categoryConfirmed && <p className="inline-warning">请先在上方确认分类，官方属性和变体才能继续。</p>}
            <div className="action-line listing-next-action">
              <span>完成内容和素材后，在下一步确认属性、站点和价格，再提交发布。</span>
              <button disabled={!categoryConfirmed || contentDirty} onClick={onContinueListing}>继续配置并发布</button>
            </div>
          </section>

          <div className="workflow-grid">
            <section className="surface">
              <div className="section-heading">
                <div><span className="step-number">4</span><h3>售价与利润 · {draft.target_site_id}</h3></div>
                <span className={`state-pill ${pricingReady ? "ready" : "blocked"}`}>
                  {pricingReady ? "已保存" : "必填"}
                </span>
              </div>
              <p className="section-note">只按你的成本和利润定价：采购成本 + 国内运费，再换算为目标站点币种。美客多跨境统一运输不在这里逐商品计费。</p>
              <div className="form-grid three-col">
                <label>Amazon 参考价<input value={`${draft.source_currency} ${draft.source_price ?? "未采集"}`} readOnly /></label>
                <label>实际采购成本（CNY）<input type="number" min="0" step="0.01" value={pricing.purchase_cost || ""} onChange={(event) => updatePricing("purchase_cost", event.target.value)} /></label>
                <label>国内运费（CNY）<input type="number" min="0" step="0.01" value={pricing.domestic_shipping_cost || ""} onChange={(event) => updatePricing("domestic_shipping_cost", event.target.value)} /></label>
                <label>期望利润率 %<input type="number" min="0" max="999" step="0.1" value={pricing.profit_margin_rate * 100} onChange={(event) => updatePricing("profit_margin_rate", String(Number(event.target.value) / 100))} /></label>
                <label>换算汇率（1 CNY =）<input type="number" min="0" step="0.0001" value={pricing.exchange_rate} onChange={(event) => updatePricing("exchange_rate", event.target.value)} /></label>
                <label>目标售价币种<input value={pricing.target_currency} readOnly /></label>
              </div>
              <div className="action-line">
                <button disabled={!draftId || contentDirty || pricing.purchase_cost <= 0 || pricing.exchange_rate <= 0 || busy === "pricing"} onClick={calculateAndSavePricing}>
                  <Calculator size={16} /> 保存建议售价
                </button>
                {pricingResult && (
                  <div className="calculation-result">
                    <span>总成本 {pricingResult.cost_currency} {pricingResult.purchase_cost + pricingResult.domestic_shipping_cost}</span>
                    <strong>建议售价 {pricingResult.target_currency} {pricingResult.target_price}</strong>
                  </div>
                )}
              </div>
              {(!draft.source_price || !draft.source_currency) && (
                <p className="inline-warning">未采集到 Amazon 参考价，请重新采集商品页面后再保存定价。</p>
              )}
            </section>

            <section className="surface">
              <div className="section-heading">
                <div><span className="step-number">5</span><h3>AI 合规审核与提交</h3></div>
                <span className={`state-pill ${decision === "pass" ? "ready" : "blocked"}`}>{decision}</span>
              </div>
              <div className="provider-status">
                <div><Bot size={18} /><span>Claude</span><strong>{claudeReady ? "已配置" : "需要 API 密钥"}</strong></div>
                <div><ShieldCheck size={18} /><span>NVIDIA</span><strong>{nvidiaReady ? "已配置" : "需要 API 密钥"}</strong></div>
              </div>
              <div className="button-row">
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={providerCostAcknowledged}
                    onChange={(event) => setProviderCostAcknowledged(event.target.checked)}
                  />
                  我确认本次会消耗 Claude 和 NVIDIA 的用量费用
                </label>
                <button disabled={!draftId || contentDirty || !pricingReady || !listingConfigured || !claudeReady || !nvidiaReady || !providerCostAcknowledged || Boolean(busy)} onClick={queueCurrentReview}><ShieldCheck size={16} /> 发起 AI 合规审核</button>
                <button className="secondary-button" disabled={!draftId} onClick={refreshReviewHistory}><RefreshCw size={16} /> 查看历史</button>
              </div>
              {!pricingReady && <p className="inline-warning">请先保存价格，再发起 AI 合规审核。</p>}
              {pricingReady && !listingConfigured && <p className="inline-warning">请在下一步保存店铺、刊登方式和必填属性后，再发起 AI 合规审核。</p>}
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
        </div>
      </div>
      <section className="saved-section drafts-library-footer">
        <div className="section-heading"><div><h3>批量自动处理</h3><p>商品积累后，可在这里批量发起 AI 合规审核。</p></div></div>
        {savedDrafts.length > 0 && <details className="advanced-section">
          <summary>批量自动处理（商品积累后使用）</summary>
          <p className="section-note">先在这里选择多张已完成编辑的上架单，再批量发起 AI 合规审核。未完成的商品会被系统拦截。</p>
          <div className="batch-review-controls">
            <div className="action-line">
              <span>已选 {selectedDraftIds.size} / {MAX_REVIEW_BATCH_SIZE}</span>
              <label className="check-row"><input type="checkbox" checked={providerCostAcknowledged} onChange={(event) => setProviderCostAcknowledged(event.target.checked)} />我确认本次会消耗 Claude 和 NVIDIA 的用量费用</label>
              <button disabled={selectedDraftIds.size === 0 || Boolean(contentDirty && draftId && selectedDraftIds.has(draftId)) || !providerCostAcknowledged || !claudeReady || !nvidiaReady || Boolean(busy)} onClick={queueBatchReview}><ListPlus size={16} /> 批量发起 AI 审核</button>
            </div>
            {batchReviewResult && <div className="batch-result-summary" aria-live="polite"><strong>已加入 {batchReviewResult.queued_count} 个</strong><span>进行中 {batchReviewResult.existing_count} 个</span><span>未就绪 {batchReviewResult.not_ready_count} 个</span><span>不存在 {batchReviewResult.not_found_count} 个</span></div>}
            {batchReviewResult?.items.some((item) => item.errors.length > 0) && <div className="batch-review-errors">{batchReviewResult.items.filter((item) => item.errors.length > 0).map((item) => <span key={item.draft_id}>上架单 #{item.draft_id}: {item.errors.join(", ")}</span>)}</div>}
          </div>
          <div className="draft-list">
            {savedDrafts.map((savedDraft) => (
              <div className="draft-selection-row" key={savedDraft.id}>
              <label className="draft-selector">
                <input
                  type="checkbox" aria-label={`选择上架单 ${savedDraft.id} 进行批量审核`}
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
                <ProductImage src={savedDraft.image_urls[0]} alt={savedDraft.title || "商品图片"} />
                <span className="draft-copy">
                  <strong>{savedDraft.title}</strong>
                  <small>上架单 #{savedDraft.id} · {savedDraft.target_site_id} · 采集价 {savedDraft.source_currency} {savedDraft.source_price ?? "-"} · 售价 {savedDraft.currency} {savedDraft.price ?? "未定价"}</small>
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
                <span>审核任务 #{job.id} · 上架单 #{job.product_draft_id}</span>
                <strong>{job.status}</strong>
                {job.error_code && <small>{job.error_code}</small>}
                {job.next_attempt_at && (
                  <small>可执行时间：{new Date(job.next_attempt_at).toLocaleString()}</small>
                )}
              </div>
            ))}
          </div>
        )}
        </details>}
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

function readableDraftError(error: unknown, fallback: string) {
  const raw = error instanceof Error ? error.message : "";
  try {
    const detail = JSON.parse(raw).detail;
    const code = typeof detail === "string" ? detail : detail?.code;
    const messages: Record<string, string> = {
      category_confirmation_required: "请先确认 Mercado Libre 分类。",
      category_attributes_not_verified: "官方分类属性尚未读取成功，请刷新分类属性后再试。",
      category_leaf_not_verified: "请先确认最底层叶子分类，父分类不能直接上架。",
      category_site_mismatch: "分类与目标站点不匹配。",
      volcengine_api_key_required: "请先在店铺管理中配置火山 AI API Key。",
      volcengine_unreachable: "火山 AI 暂时无法连接，请稍后重试。",
      generated_content_invalid: "火山 AI 返回的内容未通过合规检查，请重新生成。",
      draft_content_version_conflict: "草稿已被其他操作修改，请重新选择草稿。",
    };
    if (typeof code === "string" && messages[code]) return messages[code];
  } catch {
    // Keep a stable human-readable fallback for non-JSON errors.
  }
  return raw && !raw.startsWith("{") ? raw : fallback;
}
