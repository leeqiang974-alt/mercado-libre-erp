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
  deleteDraft,
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
import { CbtGlobalPublishingPanel } from "./CbtGlobalPublishingPanel";

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
const MIN_LISTING_IMAGE_EDGE = 500;

function publicationStatusLabel(draft: ProductDraftRead) {
  if (draft.publication_status === "published") return `已发布：${draft.published_sites.join("、") || "CBT"}`;
  if (draft.publication_status === "pending" || draft.publication_status === "validating") return "发布中";
  if (draft.publication_status === "failed" || draft.publication_status === "blocked") return "发布失败，可修改后重试";
  return "未发布";
}

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
    if (candidate.resolution < MIN_LISTING_IMAGE_EDGE) return;
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

  async function removeSavedDraft(event: React.MouseEvent, item: ProductDraftRead) {
    event.stopPropagation();
    if (["published", "pending", "validating"].includes(item.publication_status || "")) return;
    if (!window.confirm(`确定删除“${item.title || "未命名商品"}”吗？`)) return;
    try {
      await deleteDraft(item.id);
      setSavedDrafts((current) => current.filter((draftItem) => draftItem.id !== item.id));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "删除商品失败");
    }
  }

  // The listing library is also the entrypoint.  Do not render a blank page
  // when the URL is simply #drafts: the operator must always be able to pick
  // a product from the left rail.
  if (!draft || !draftId) {
    return (
      <section className="wf-listing-layout">
        <aside className="drafts-sidebar surface wf-listing-rail">
          <div className="drafts-sidebar-heading"><h3>上架库</h3><span>{savedDrafts.length} 个</span></div>
          <p className="section-note">选择商品后，在右侧完成分类、素材、售价和站点配置。</p>
          <div className="draft-rail-list">
            {savedDrafts.map((item) => (
              <button className="draft-rail-item" key={item.id} onClick={() => selectSavedDraft(item)}>
                {!['published', 'pending', 'validating'].includes(item.publication_status || '') && <span className="draft-delete-wrap"><span className="draft-delete-icon" aria-hidden="true">×</span><span className="draft-delete-tooltip">删除商品</span><span role="button" tabIndex={0} className="draft-delete-hit" aria-label={`删除 ${item.title || "未命名商品"}`} onClick={(event) => void removeSavedDraft(event, item)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") void removeSavedDraft(event as unknown as React.MouseEvent, item); }} /></span>}
                <ProductImage src={item.image_urls[0]} alt="" />
                <span>
                  <strong>{item.title || "未命名商品"}</strong>
                  <small>#{item.id} · {item.target_site_id}</small>
                  <small>{publicationStatusLabel(item)}</small>
                </span>
              </button>
            ))}
          </div>
        </aside>
        <div className="workspace"><div className="empty-state">请从左侧上架库选择一个商品。</div></div>
      </section>
    );
  }

  // This is deliberately the only operator listing surface: the library rail
  // and every publish field live in one editor, with no next-page transition.
  return <CbtGlobalPublishingPanel
    draft={draft}
    draftId={draftId}
    onDraftChange={onDraftChange}
    onReviewInvalidated={() => onReviewChange(null)}
    onBackToEditing={() => undefined}
  />;

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
