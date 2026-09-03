import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Globe2,
  Image,
  ListChecks,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Store,
} from "lucide-react";
import {
  confirmDraftCategory,
  createSourceVariantDraft,
  getCategoryAttributes,
  getCategoryDetails,
  getCbtCategoryPredictions,
  getCbtCategoryTree,
  getCbtListingConfig,
  getCbtMarketplaceListingTypes,
  getCbtPublishingProfile,
  getDraft,
  getDraftPricing,
  executeCbtPublishFromDraft,
  generateDraftContent,
  getSystemReadiness,
  deleteDraft,
  getSourceProduct,
  listDrafts,
  listStores,
  mirrorDraftImagesToOss,
  previewCbtPublishFromDraft,
  saveDraftContent,
  saveDraftPricing,
  saveCbtListingConfig,
  searchAlibaba1688SimilarOffers,
  type Alibaba1688SimilarResult,
  type AmazonSourceVariant,
  type CbtListingConfig,
  type CbtMarketplace,
  type CbtPublishingProfile,
  type DraftPricing,
  type DraftPricingInput,
  type ProductDraft,
  type ProductDraftRead,
  type PublishExecutionResult,
  type SystemReadiness,
  type StoreRecord,
} from "../api/client";

const REQUIRED_ATTRIBUTE_IDS = [
  "ITEM_CONDITION",
  "SELLER_SKU",
  "PACKAGE_LENGTH",
  "PACKAGE_WIDTH",
  "PACKAGE_HEIGHT",
  "PACKAGE_WEIGHT",
];
const MAX_PRODUCT_IMAGES = 12;
const MAX_PRODUCT_VIDEOS = 3;

const MARKET_NAMES: Record<string, string> = {
  MLA: "阿根廷", MLB: "巴西", MLC: "智利", MCO: "哥伦比亚", MLM: "墨西哥", MLU: "乌拉圭",
};

type SitePublishResult = {
  siteId: string;
  itemId: string;
  state: "success" | "failed" | "pending";
  message: string;
};

function readableSitePublishError(error: unknown) {
  const record = error && typeof error === "object" ? error as Record<string, unknown> : {};
  const cause = Array.isArray(record.cause) ? record.cause[0] : null;
  const detail = cause && typeof cause === "object" ? cause as Record<string, unknown> : {};
  const code = String(detail.code ?? record.error ?? record.message ?? "");
  const message = String(detail.message ?? record.message ?? "美客多未返回具体原因");
  if (code === "invalid.listing_type_id") return "该站点不支持当前刊登类型，请改为 Classic 或选择官方允许类型";
  if (code === "item.shipping.mode.not_supported") return "该站点暂不支持当前 Remote 物流";
  if (code === "local_rate_limited") return "美客多限流，稍后仅重试该站点";
  if (code === "item.net_proceeds") return "目标净收益过低，请提高 USD 净收益";
  if (code === "invalid.item.attribute.values") return "分类属性值不符合该站点要求";
  return message;
}

function sitePublishResults(details: Record<string, unknown>): SitePublishResult[] {
  const rows = Array.isArray(details.site_items) ? details.site_items : [];
  const fallbackSites = new Set(
    (Array.isArray(details.listing_type_fallbacks) ? details.listing_type_fallbacks : [])
      .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
      .filter((row) => row.from === "gold_pro" && row.to === "gold_special")
      .map((row) => String(row.site_id ?? "").toUpperCase()),
  );
  return rows.filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object")).map((row) => {
    const siteId = String(row.site_id ?? "").toUpperCase();
    const itemId = String(row.item_id ?? "");
    const error = row.error;
    const downgraded = fallbackSites.has(siteId);
    return {
      siteId,
      itemId,
      state: error ? "failed" : itemId ? "success" : "pending",
      message: error
        ? readableSitePublishError(error)
        : itemId
          ? `${downgraded ? "Premium 不支持，已自动降为 Classic；" : ""}已创建商品：${itemId}`
          : "美客多正在处理",
    };
  });
}

function SitePublishResults({ details }: { details: Record<string, unknown> }) {
  const results = sitePublishResults(details);
  if (!results.length) return null;
  return <div className="site-publish-results" aria-label="各站点发布结果">
    {results.map((result) => <div className={`site-publish-result ${result.state}`} key={result.siteId}>
      <i aria-hidden="true" />
      <div><strong>{MARKET_NAMES[result.siteId] ?? result.siteId}</strong><small>{result.siteId} · {result.message}</small></div>
    </div>)}
  </div>;
}

const ATTRIBUTE_NAMES_ZH: Record<string, string> = {
  ITEM_CONDITION: "商品状况", SELLER_SKU: "卖家 SKU", PACKAGE_LENGTH: "包装长度",
  PACKAGE_WIDTH: "包装宽度", PACKAGE_HEIGHT: "包装高度", PACKAGE_WEIGHT: "包装重量",
  BRAND: "品牌", MODEL: "型号", WARRANTY_TYPE: "质保类型", COLOR: "颜色",
  MATERIAL: "材质", GTIN: "商品条码", EAN: "商品条码", UPC: "商品条码",
};

function defaultSku(draftId: number) {
  return `xy${String(draftId).padStart(6, "0")}`;
}

function CbtMediaImage({ src, alt }: { src: string; alt: string }) {
  const [dimensions, setDimensions] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  return <>
    <img
      src={src}
      alt={alt}
      onLoad={(event) => {
        setFailed(false);
        setDimensions(`${event.currentTarget.naturalWidth} × ${event.currentTarget.naturalHeight}`);
      }}
      onError={() => {
        setFailed(true);
        setDimensions(null);
      }}
    />
    <span className={`wf-media-dimensions ${failed ? "error" : ""}`} aria-live="polite">
      {failed ? "图片加载失败" : dimensions ? `${dimensions} px` : "读取尺寸中…"}
    </span>
  </>;
}

// The rail is an operator control, so one draft must never be rendered twice.
// This also protects the UI from a stale/repeated response during a refresh.
function uniqueDrafts(items: ProductDraftRead[]) {
  return Array.from(new Map(items.map((item) => [item.id, item])).values());
}

function attributeNameZh(attribute: Record<string, unknown> | undefined, id: string) {
  return ATTRIBUTE_NAMES_ZH[id] ?? String(attribute?.name_zh ?? attribute?.name ?? id);
}

function readableVariantDraftError(error: unknown) {
  const raw = error instanceof Error ? error.message : "";
  try {
    const detail = JSON.parse(raw) as { detail?: string };
    if (detail.detail === "variant_page_collection_required") {
      return "该 ASIN 还没有单独采集页面，请先打开这个 ASIN 的 Amazon 页面并点击采集，再回来编辑。";
    }
    if (detail.detail === "source_variant_not_found") return "源商品中没有找到这个 ASIN 的变体证据。";
    if (detail.detail === "source_snapshot_unavailable") return "源商品采集快照不可用，请先重新采集。";
  } catch {
    // Keep the server message when it is not a JSON error response.
  }
  return raw || "建立变体独立草稿失败";
}

function normalizedAttributeKey(value: string) {
  return value.replace(/[^a-z0-9]+/gi, "").toLowerCase();
}

function sourceVariantValueForDefinition(
  definition: Record<string, unknown>,
  sourceAttributes: Record<string, string>,
) {
  const targetKeys = new Set([
    normalizedAttributeKey(String(definition.id ?? "")),
    normalizedAttributeKey(String(definition.name ?? "")),
  ]);
  for (const [sourceName, sourceValue] of Object.entries(sourceAttributes)) {
    const sourceKey = normalizedAttributeKey(sourceName);
    if (sourceKey && targetKeys.has(sourceKey)) return sourceValue;
    // Amazon uses Colour in some locales while Mercado Libre exposes COLOR.
    if ((sourceKey === "color" || sourceKey === "colour") && targetKeys.has("color")) return sourceValue;
  }
  return "";
}

function attributesForSave(
  attributes: Record<string, string>,
  definitions: Record<string, unknown>[],
  savedAttributes: CbtListingConfig["attributes"] = [],
) {
  const definitionsById = new Map(
    definitions.map((definition) => [String(definition.id ?? "").toUpperCase(), definition]),
  );
  const savedById = new Map(savedAttributes.map((attribute) => [attribute.id.toUpperCase(), attribute]));
  return Object.entries(attributes).filter(([, value]) => value.trim()).map(([rawId, rawName]) => {
    const id = rawId.toUpperCase();
    const value_name = rawName.trim();
    const definition = definitionsById.get(id);
    const values = Array.isArray(definition?.values)
      ? definition.values.filter((value): value is Record<string, unknown> => Boolean(value && typeof value === "object"))
      : [];
    const official = values.find(
      (value) => String(value.name ?? "").trim().toLowerCase() === value_name.toLowerCase(),
    );
    if (official?.id) {
      return { id, value_name: String(official.name ?? value_name), value_id: String(official.id) };
    }
    const previous = savedById.get(id);
    if (previous?.value_id && previous.value_name.trim().toLowerCase() === value_name.toLowerCase()) {
      return { id, value_name, value_id: previous.value_id };
    }
    return { id, value_name };
  });
}

type Offer = CbtListingConfig["sites_to_sell"][number];

function normalizeCbtTitle(value: string) {
  // Do not silently cut a generated title. The UI blocks publishing above 60
  // characters so the operator can regenerate it or edit the actual wording.
  return value.replace(/\s+/g, " ").trim();
}

function sanitizeCbtDescription(value: string) {
  return value
    .split("\n")
    .filter((line) => !/^\s*(brand|brand name|marca)\s*[:\-]/i.test(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function createRemoteOffer(market: CbtMarketplace, title: string): Offer {
  return {
    site_id: market.site_id,
    title: normalizeCbtTitle(title),
    listing_type_id: "gold_pro",
    logistic_type: "remote",
    picture_urls: [],
  };
}

function warrantySaleTerms(warranty: string) {
  if (warranty === "No warranty") {
    return [{ id: "WARRANTY_TYPE", value_id: "6150835", value_name: "No warranty" }];
  }
  return [
    { id: "WARRANTY_TYPE", value_id: "2230280", value_name: "Seller warranty" },
    { id: "WARRANTY_TIME", value_name: warranty },
  ];
}

function remoteMarketsForProfile(profile: CbtPublishingProfile): CbtMarketplace[] {
  return Array.from(
    new Map(
      profile.marketplaces
        .filter((market) => market.available && market.logistic_type === "remote")
        .map((market) => [market.site_id, market]),
    ).values(),
  );
}

export function CbtGlobalPublishingPanel({
  draft,
  draftId,
  onDraftChange,
  onSelectDraft,
  onReviewInvalidated,
  onBackToEditing,
}: {
  draft: ProductDraft;
  draftId: number;
  onDraftChange: (draft: ProductDraft) => void;
  onSelectDraft?: (draft: ProductDraftRead) => void;
  onReviewInvalidated: () => void;
  onBackToEditing: () => void;
}) {
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [listingRail, setListingRail] = useState<ProductDraftRead[]>([]);
  const [listingPage, setListingPage] = useState(1);
  const [listingSearch, setListingSearch] = useState("");
  const [storeId, setStoreId] = useState("");
  const [profile, setProfile] = useState<CbtPublishingProfile | null>(null);
  const [profileReloadKey, setProfileReloadKey] = useState(0);
  const [categoryId, setCategoryId] = useState("");
  const [categoryLeafVerified, setCategoryLeafVerified] = useState(false);
  const [categoryPath, setCategoryPath] = useState("");
  const [categoryActionStatus, setCategoryActionStatus] = useState("");
  const [categorySearchQuery, setCategorySearchQuery] = useState(normalizeCbtTitle(draft.title));
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [categoryTree, setCategoryTree] = useState<Record<string, unknown>[]>([]);
  const [categoryTreePath, setCategoryTreePath] = useState("");
  const [showCategoryTree, setShowCategoryTree] = useState(false);
  const [globalTitle, setGlobalTitle] = useState(normalizeCbtTitle(draft.title));
  const [familyName, setFamilyName] = useState(defaultSku(draftId));
  const [description, setDescription] = useState(sanitizeCbtDescription(draft.description));
  const [videoUrls, setVideoUrls] = useState<string[]>(draft.video_urls ?? []);
  const [priceUsd, setPriceUsd] = useState(draft.currency === "USD" && draft.price ? String(draft.price) : "");
  const [quantity, setQuantity] = useState("999");
  const [attributes, setAttributes] = useState<Record<string, string>>({
    BRAND: "Unbranded", ITEM_CONDITION: "new", SELLER_SKU: defaultSku(draftId), MODEL: defaultSku(draftId),
  });
  const [attributeDefinitions, setAttributeDefinitions] = useState<Record<string, unknown>[]>([]);
  const [sourceVariants, setSourceVariants] = useState<AmazonSourceVariant[]>([]);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [officialTypes, setOfficialTypes] = useState<Record<string, string[]>>({});
  const [officialTypesLoading, setOfficialTypesLoading] = useState(false);
  const [warranty, setWarranty] = useState("7 days");
  const [saved, setSaved] = useState<CbtListingConfig | null>(null);
  const [preview, setPreview] = useState<{ allowed: boolean; errors: string[]; payload: Record<string, unknown> | null } | null>(null);
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [pricing, setPricing] = useState<DraftPricing | null>(null);
  const [busy, setBusy] = useState("");
  const [recollectBusy, setRecollectBusy] = useState<number | null>(null);
  const [variantDraftBusy, setVariantDraftBusy] = useState<string | null>(null);
  const [similarSearchBusy, setSimilarSearchBusy] = useState(false);
  const [similarOffers, setSimilarOffers] = useState<Alibaba1688SimilarResult | null>(null);
  const LISTING_PAGE_SIZE = 20;
  const pendingListingRail = useMemo(
    () => listingRail.filter((item) => item.publication_status !== "published"),
    [listingRail],
  );
  const listingPageCount = Math.max(1, Math.ceil(pendingListingRail.length / LISTING_PAGE_SIZE));
  const listingPageItems = pendingListingRail.slice(
    (listingPage - 1) * LISTING_PAGE_SIZE,
    listingPage * LISTING_PAGE_SIZE,
  );
  const [status, setStatus] = useState("");
  const [configLoaded, setConfigLoaded] = useState(false);
  const [hasSavedConfig, setHasSavedConfig] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [imageZoom, setImageZoom] = useState(1);
  const [aiFeedback, setAiFeedback] = useState<{ field: "title" | "description"; message: string; error: boolean } | null>(null);
  const offersInitializedRef = useRef(false);
  // API responses contain newly allocated arrays even when the media did not
  // change. Compare their contents so a same-draft refresh cannot be mistaken
  // for a new editor context.
  const draftVideoUrlsKey = (draft.video_urls ?? []).join("\u001f");
  const cbtStores = stores.filter((store) => store.site_id === "CBT" && store.oauth_status === "connected" && store.is_enabled);
  const remoteMarkets = useMemo(
    () => (profile ? remoteMarketsForProfile(profile) : []),
    [profile],
  );
  const fullMarkets = useMemo(() => {
    const configured = (profile?.marketplaces ?? []).filter(
      (market) => market.site_id === "MLM" && market.logistic_type === "fulfillment",
    );
    return configured.length > 0 ? configured : [{
      site_id: "MLM",
      seller_id: "",
      logistic_type: "fulfillment",
      user_product: false,
      listing_count: null,
      listing_limit: null,
      available: false,
    } satisfies CbtMarketplace];
  }, [profile]);
  const requiredIds = useMemo(() => {
    const fromMetadata = attributeDefinitions
      .filter((attribute) => {
        const tags = attribute.tags as Record<string, unknown> | undefined;
        return tags?.required === true || tags?.catalog_required === true;
      })
      .map((attribute) => String(attribute.id ?? "").toUpperCase())
      .filter(Boolean);
    return [...new Set([...REQUIRED_ATTRIBUTE_IDS, ...fromMetadata])];
  }, [attributeDefinitions]);
  const variationDefinitions = useMemo(() => attributeDefinitions.filter((attribute) => {
    const tags = attribute.tags as Record<string, unknown> | undefined;
    return tags?.variation_attribute === true;
  }), [attributeDefinitions]);
  const draftVariantAttributes = draft.source_variant_attributes ?? {};
  const draftVariantAttributesKey = Object.entries(draftVariantAttributes)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, value]) => `${name}:${value}`)
    .join("\u001f");
  // Amazon-derived listings are always unbranded. Keep the official attribute
  // in the payload, but never expose a brand entry field to the operator.
  const missing = requiredIds.filter((id) => id !== "BRAND" && !attributes[id]?.trim());
  const allRemoteSelected = remoteMarkets.length > 0
    && remoteMarkets.every((market) => offers.some((offer) => offer.site_id === market.site_id));
  const previewImageIndex = previewImage ? draft.image_urls.indexOf(previewImage) : -1;
  const hasPreviousPreviewImage = previewImageIndex > 0;
  const hasNextPreviewImage = previewImageIndex >= 0 && previewImageIndex < draft.image_urls.length - 1;
  const unitCostUsd = pricing
    ? (pricing.purchase_cost + pricing.domestic_shipping_cost) * pricing.exchange_rate
    : null;
  // Global Selling is operated in the seller's USD net-income mode: the amount
  // entered here is the target net income submitted in the Global Selling config.
  const estimatedProfitUsd = Number(priceUsd) > 0 ? Number(priceUsd) : null;
  const canSave = Boolean(
    storeId && categoryId && categoryLeafVerified && familyName.trim() && globalTitle.trim() && description.trim()
    && Number(priceUsd) > 0 && Number.isInteger(Number(quantity)) && Number(quantity) > 0
    && offers.length > 0 && missing.length === 0,
  );

  useEffect(() => {
    let cancelled = false;
    const refreshListingRail = () => listDrafts().then((items) => {
      if (cancelled) return;
      const uniqueItems = uniqueDrafts(items);
      setListingRail(uniqueItems);
      const currentIndex = uniqueItems.filter((item) => item.publication_status !== "published").findIndex((item) => item.id === draftId);
      setListingPage(currentIndex >= 0 ? Math.floor(currentIndex / LISTING_PAGE_SIZE) + 1 : 1);
    }).catch(() => undefined);
    void refreshListingRail();
    const timer = window.setInterval(() => void refreshListingRail(), 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [draftId]);

  // Selecting another card is an in-page edit-context change, not a document
  // navigation. Reset the visible form immediately so the previous product's
  // data cannot flash while the new configuration is loading. This must be
  // keyed by draftId only: every API response creates fresh array values, so
  // using draft fields as dependencies used to clear a confirmed category
  // when the same draft was refreshed or saved.
  useEffect(() => {
    setCategorySearchQuery(normalizeCbtTitle(draft.title));
    setGlobalTitle(normalizeCbtTitle(draft.title));
    setDescription(sanitizeCbtDescription(draft.description));
    setVideoUrls(draft.video_urls ?? []);
    setFamilyName(defaultSku(draftId));
    setPriceUsd(draft.currency === "USD" && draft.price ? String(draft.price) : "");
    setQuantity("999");
    setCategoryId("");
    setCategoryLeafVerified(false);
    setCategoryPath("");
    setCategoryActionStatus("");
    setPredictions([]);
    setAttributeDefinitions([]);
    setSourceVariants([]);
    setAttributes({ BRAND: "Unbranded", ITEM_CONDITION: "new", SELLER_SKU: defaultSku(draftId), MODEL: defaultSku(draftId) });
    setOffers([]);
    setSaved(null);
    setPreview(null);
    setExecution(null);
    setSimilarOffers(null);
    setStatus("");
    setAiFeedback(null);
    setConfigLoaded(false);
    setHasSavedConfig(false);
    offersInitializedRef.current = false;
  }, [draftId]);

  useEffect(() => {
    let cancelled = false;
    if (!draft.source_product_id) {
      setSourceVariants([]);
      return () => { cancelled = true; };
    }
    getSourceProduct(draft.source_product_id)
      .then((source) => {
        if (!cancelled) setSourceVariants(source.snapshot?.variants ?? []);
      })
      .catch(() => {
        if (!cancelled) setSourceVariants([]);
      });
    return () => { cancelled = true; };
  }, [draftId, draft.source_product_id]);

  useEffect(() => {
    if (!variationDefinitions.length || !Object.keys(draftVariantAttributes).length) return;
    // Only fill empty official variation fields.  Re-collection may enrich
    // Color/Size, but it must never overwrite an operator's manual choice.
    setAttributes((current) => {
      const next = { ...current };
      let changed = false;
      for (const definition of variationDefinitions) {
        const id = String(definition.id ?? "").trim().toUpperCase();
        const sourceValue = sourceVariantValueForDefinition(definition, draftVariantAttributes);
        if (id && sourceValue && !next[id]?.trim()) {
          next[id] = sourceValue;
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [draftId, draftVariantAttributesKey, variationDefinitions]);

  // Keep source content changes (AI generation, recollection, or a server-side
  // save) visible without resetting category confirmation, selected markets,
  // or the category-dependent attribute form. The category confirmation API
  // changes the parent draft's version and object identity, but not any of the
  // values below, so this effect deliberately does not run for that response.
  useEffect(() => {
    setCategorySearchQuery(normalizeCbtTitle(draft.title));
    setGlobalTitle(normalizeCbtTitle(draft.title));
    setDescription(sanitizeCbtDescription(draft.description));
    setVideoUrls(draft.video_urls ?? []);
    if (draft.currency === "USD" && draft.price) setPriceUsd(String(draft.price));
    setSaved(null);
    setPreview(null);
    setExecution(null);
  }, [draftId, draft.title, draft.description, draftVideoUrlsKey, draft.currency, draft.price]);

  useEffect(() => {
    setListingPage((page) => Math.min(Math.max(page, 1), listingPageCount));
  }, [listingPageCount]);

  useEffect(() => {
    const currentIndex = pendingListingRail.findIndex((item) => item.id === draftId);
    setListingPage(currentIndex >= 0 ? Math.floor(currentIndex / LISTING_PAGE_SIZE) + 1 : 1);
  }, [draftId, pendingListingRail]);

  useEffect(() => {
    const query = listingSearch.trim().toLowerCase();
    if (!query) return;
    const exactId = /^\d+$/.test(query)
      ? pendingListingRail.findIndex((item) => String(item.id) === query)
      : -1;
    const matchIndex = exactId >= 0 ? exactId : pendingListingRail.findIndex((item) =>
      String(item.title ?? "").toLowerCase().includes(query),
    );
    if (matchIndex >= 0) setListingPage(Math.floor(matchIndex / LISTING_PAGE_SIZE) + 1);
  }, [listingSearch, pendingListingRail]);

  async function removeListingDraft(event: { stopPropagation: () => void }, item: ProductDraftRead) {
    event.stopPropagation();
    if (["published", "pending", "validating"].includes(item.publication_status || "")) return;
    if (!window.confirm(`确定删除“${item.title || "未命名商品"}”吗？`)) return;
    try {
      await deleteDraft(item.id);
      // Re-read after a successful delete.  The card is removed only after the
      // server confirms it is gone, which avoids a misleading local-only UI.
      const remaining = uniqueDrafts(await listDrafts());
      setListingRail(remaining);
      setStatus(`已删除商品 #${item.id}。`);
      if (item.id === draftId) {
        const next = remaining.find((candidate) => candidate.publication_status !== "published");
        if (next && onSelectDraft) onSelectDraft(next);
        else onBackToEditing();
      }
    } catch (deleteError) {
      setStatus(`未删除商品 #${item.id}：${deleteError instanceof Error ? deleteError.message : "服务器拒绝了删除请求"}`);
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listStores(),
      getCbtListingConfig(draftId),
      getSystemReadiness(),
      getDraftPricing(draftId).catch(() => null),
      // The parent can still hold a compact/stale draft while the editor is
      // opening. Read the authoritative draft before restoring category state.
      // A transient read timeout must not discard the separately readable
      // listing configuration (or its confirmed category).
      getDraft(draftId).catch(() => draft),
    ])
      .then(([storeRows, config, system, savedPricing, persistedDraft]) => {
        if (cancelled) return;
        setStores(storeRows);
        setReadiness(system);
        setPricing(savedPricing);
        const defaultStore = config?.store_id
          ? String(config.store_id)
          : storeRows.find((store) => store.site_id === "CBT" && store.oauth_status === "connected")?.id ?? "";
        setStoreId(defaultStore);
        setHasSavedConfig(Boolean(config));
        setConfigLoaded(true);
        offersInitializedRef.current = Boolean(config);
        if (!config) {
          // Category confirmation is persisted on the draft before the full CBT
          // listing form is saved. Restore that confirmed leaf on reload instead
          // of treating it as merely a source-category hint.
          const confirmedCategoryId = persistedDraft.target_category_id;
          if (confirmedCategoryId?.startsWith("CBT")) {
            setCategoryId(confirmedCategoryId);
            getCategoryDetails(confirmedCategoryId)
              .then(async (details) => {
                if (cancelled) return;
                const isConfirmedLeaf = Boolean(details.verified && details.leaf);
                setCategoryLeafVerified(isConfirmedLeaf);
                setCategoryPath((details.path_from_root_zh ?? details.path_from_root)
                  .map((item) => item.name_zh || item.name)
                  .filter(Boolean)
                  .join(" > "));
                if (!isConfirmedLeaf) {
                  setStatus("已保存的分类不是可刊登的最底层分类，请重新选择叶子分类。");
                  return;
                }
                setCategoryActionStatus("已恢复并确认最终 CBT 分类");
                try {
                  const attributesResult = await getCategoryAttributes(confirmedCategoryId);
                  if (!cancelled) setAttributeDefinitions(attributesResult.attributes);
                } catch {
                  // The confirmed category stays visible even if its optional
                  // attribute metadata is temporarily unavailable.
                }
              })
              .catch(() => !cancelled && setStatus("已保存的最终 CBT 分类暂时无法读取，请稍后刷新。"));
          }
          return;
        }
        setSaved(config);
        setCategoryId(config.category_id);
        getCategoryDetails(config.category_id)
          .then((details) => {
            if (!cancelled) {
              const isConfirmedLeaf = Boolean(details.verified && details.leaf);
              setCategoryLeafVerified(isConfirmedLeaf);
              setCategoryPath((details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean).join(" > "));
              if (isConfirmedLeaf) setCategoryActionStatus("已恢复并确认最终 CBT 分类");
            }
          })
          .catch(() => !cancelled && setCategoryLeafVerified(false));
        setFamilyName(config.family_name || defaultSku(draftId));
        setGlobalTitle(normalizeCbtTitle(config.global_title));
        setDescription(sanitizeCbtDescription(config.description));
        // A saved procurement/domestic-shipping/profit formula is the source
        // of truth for the Remote Net Proceeds amount. Fall back to a legacy
        // manually saved amount only while no formula exists.
        setPriceUsd(String(savedPricing?.target_price ?? config.price_usd));
        setQuantity(String(config.available_quantity || 999));
        setAttributes({ ITEM_CONDITION: "new", SELLER_SKU: defaultSku(draftId), ...Object.fromEntries(config.attributes.map((item) => [item.id, item.value_name])), BRAND: "Unbranded", MODEL: config.family_name || defaultSku(draftId) });
        setOffers(config.sites_to_sell);
        const warrantyType = config.sale_terms.find((term) => term.id === "WARRANTY_TYPE")?.value_name;
        setWarranty(warrantyType === "No warranty" ? "No warranty" : config.sale_terms.find((term) => term.id === "WARRANTY_TIME")?.value_name ?? "7 days");
      })
      .catch((error) => !cancelled && setStatus(error instanceof Error ? error.message : "无法读取跨境刊登配置"));
    return () => { cancelled = true; };
  }, [draftId]);

  useEffect(() => {
    if (!storeId || !categoryId.startsWith("CBT")) { setOfficialTypes({}); return; }
    let cancelled = false;
    setOfficialTypesLoading(true);
    getCbtMarketplaceListingTypes(Number(storeId), categoryId)
      .then((result) => {
        if (cancelled) return;
        const next = Object.fromEntries(result.markets.filter((market) => market.verified).map((market) => [market.site_id, market.listing_type_ids]));
        setOfficialTypes(next);
        setOffers((current) => current.map((offer) => {
          const ids = next[offer.site_id];
          return ids?.length && !ids.includes(offer.listing_type_id) ? { ...offer, listing_type_id: ids[0] as Offer["listing_type_id"] } : offer;
        }));
      })
      .catch(() => !cancelled && setOfficialTypes({}))
      .finally(() => !cancelled && setOfficialTypesLoading(false));
    return () => { cancelled = true; };
  }, [storeId, categoryId]);

  useEffect(() => {
    if (!storeId) { setProfile(null); return; }
    let cancelled = false;
    setBusy("profile");
    getCbtPublishingProfile(Number(storeId))
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        const availableSiteIds = new Set(remoteMarketsForProfile(data).map((market) => market.site_id));
        setOffers((current) => {
          const filtered = current.filter((offer) => availableSiteIds.has(offer.site_id));
          if (filtered.length !== current.length) setStatus("乌拉圭（MLU）当前不支持国际直发，已从本次发布站点排除；请保存配置后再发布。");
          return filtered;
        });
        if (configLoaded && !hasSavedConfig && !offersInitializedRef.current) {
          setOffers(remoteMarketsForProfile(data).map((market) => createRemoteOffer(market, globalTitle)));
          offersInitializedRef.current = true;
        }
      })
      .catch((error) => !cancelled && setStatus(error instanceof Error ? error.message : "无法读取店铺跨境能力"))
      .finally(() => !cancelled && setBusy(""));
    return () => { cancelled = true; };
  }, [storeId, profileReloadKey, configLoaded, hasSavedConfig]);

  useEffect(() => {
    if (!storeId) { setCategoryTree([]); setCategoryTreePath(""); return; }
    getCbtCategoryTree(Number(storeId))
      .then((result) => { setCategoryTree(result.children); setCategoryTreePath("CBT 全部分类"); })
      .catch(() => setCategoryTree([]));
  }, [storeId]);

  async function predictCategory(queryOverride?: string) {
    setBusy("category"); setStatus("");
    try {
      const query = queryOverride?.trim() || categorySearchQuery.trim() || globalTitle;
      if (!query) throw new Error("请输入分类关键词或先填写英文标题。");
      if (!storeId) throw new Error("请先选择已授权 CBT 店铺。");
      const result = await getCbtCategoryPredictions(
        Number(storeId),
        query,
        queryOverride ? "smart" : "manual",
      );
      const enriched = await Promise.all(result.predictions.slice(0, 6).map(async (prediction) => {
        const id = String(prediction.category_id ?? "");
        if (!id) return prediction;
        try {
          const details = await getCategoryDetails(id);
          return { ...prediction, parent_path_zh: (details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean).join(" > "), is_leaf: details.leaf };
        } catch { return prediction; }
      }));
      setPredictions(enriched);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "CBT 类目预测失败");
    } finally { setBusy(""); }
  }

  async function browseCategoryTree(nextCategoryId = "") {
    if (!storeId) return;
    setBusy("category-tree"); setStatus("");
    try {
      const result = await getCbtCategoryTree(Number(storeId), nextCategoryId);
      setCategoryTree(result.children);
      const detail = result.category;
      const path = detail?.path_from_root_zh ?? detail?.path_from_root;
      setCategoryTreePath(Array.isArray(path) ? path.map((item) => {
        const row = item as Record<string, unknown>;
        return String(row.name_zh ?? row.name ?? "");
      }).filter(Boolean).join(" > ") : "CBT 全部分类");
      if (nextCategoryId && result.children.length === 0) {
        await selectCategory(nextCategoryId, detail as Record<string, unknown>);
      }
    } catch (error) { setStatus(error instanceof Error ? error.message : "读取 CBT 分类目录失败"); }
    finally { setBusy(""); }
  }

  function choosePrediction(value: string) {
    const prediction = predictions.find((item) => String(item.category_id ?? "") === value);
    if (!prediction) return;
    if (prediction.is_leaf === true) void selectCategory(value, prediction);
    else void browseCategoryTree(value);
  }

  async function recollectListingDraft(event: { stopPropagation: () => void }, item: ProductDraftRead) {
    event.stopPropagation();
    if (!item.source_product_id || recollectBusy !== null) return;
    setRecollectBusy(item.id);
    setStatus("正在请求本机 Amazon 插件后台采集素材...");
    try {
      const source = await getSourceProduct(item.source_product_id);
      const result = await new Promise<{ ok: boolean; error?: string; quality?: { complete?: boolean; issues?: string[]; image_count?: number; video_count?: number; variant_count?: number; technical_detail_count?: number } | null }>((resolve) => {
        const timer = window.setTimeout(() => {
          window.removeEventListener("meli-amazon-recollect-result", handler);
          resolve({ ok: false, error: "本机 Amazon 插件未返回结果，请确认插件已启用。" });
        }, 30000);
        function handler(event: Event) {
          const detail = (event as CustomEvent<{ sourceProductId?: number; ok?: boolean; error?: string; quality?: { complete?: boolean; issues?: string[]; image_count?: number; video_count?: number; variant_count?: number; technical_detail_count?: number } | null }>).detail;
          if (detail?.sourceProductId !== item.source_product_id) return;
          window.clearTimeout(timer);
          window.removeEventListener("meli-amazon-recollect-result", handler);
          resolve({ ok: detail.ok === true, error: detail.error, quality: detail.quality });
        }
        window.addEventListener("meli-amazon-recollect-result", handler);
        window.dispatchEvent(new CustomEvent("meli-amazon-recollect", {
          detail: { sourceProductId: item.source_product_id, sourceUrl: source.source_url },
        }));
      });
      if (!result.ok) throw new Error(result.error || "重新采集素材失败");
      // Read the full draft after the extension callback. The compact list can
      // briefly lag behind the source-product transaction, which previously
      // left the editor showing the pre-collection media until a full reload.
      let updated = await getDraft(item.id);
      for (let attempt = 0; attempt < 4 && updated.content_version <= item.content_version; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        updated = await getDraft(item.id);
      }
      const refreshedSource = await getSourceProduct(item.source_product_id);
      setSourceVariants(refreshedSource.snapshot?.variants ?? []);
      setListingRail((current) => uniqueDrafts(current.map((row) => row.id === updated.id ? updated : row)));
      if (updated.id === draftId) onDraftChange(updated);
      const qualityWarning = result.quality?.complete === false && result.quality.issues?.length
        ? ` 仍需补全：${result.quality.issues.join("；")}。`
        : "";
      setStatus(`已重新采集：${updated.image_urls.length} 张图片，${updated.video_urls?.length ?? 0} 个视频链接，${result.quality?.variant_count ?? 0} 个变体，${result.quality?.technical_detail_count ?? 0} 条参数。${qualityWarning}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "重新采集素材失败");
    } finally {
      setRecollectBusy(null);
    }
  }

  async function searchByCoverImage() {
    setSimilarSearchBusy(true); setStatus("");
    try {
      const result = await searchAlibaba1688SimilarOffers(draftId);
      setSimilarOffers(result);
      setStatus(`1688 图搜完成：返回 ${result.offers.length} 个价格参考。`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "1688 图搜失败"); }
    finally { setSimilarSearchBusy(false); }
  }

  async function selectCategory(nextCategoryId: string, prediction?: Record<string, unknown>) {
    if (!nextCategoryId) return;
    setCategoryId(nextCategoryId);
    setCategoryActionStatus("正在确认最终 CBT 分类...");
    setBusy("attributes");
    try {
      const details = await getCategoryDetails(nextCategoryId);
      if (!details.verified || !details.leaf) throw new Error("该推荐不是最底层分类，请选择带有叶子标记的分类。");
      const confirmed = await confirmDraftCategory(draftId, {
        expected_content_version: draft.content_version ?? 1,
        target_site_id: "CBT",
        category_id: nextCategoryId,
      });
      onDraftChange(confirmed.draft);
      setListingRail((current) => current.map((item) => item.id === confirmed.draft.id ? confirmed.draft : item));
      setCategoryLeafVerified(true);
      setCategoryPath((details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean).join(" > "));
      setCategoryActionStatus("已确认最终 CBT 分类");
      try {
        const attributesResult = await getCategoryAttributes(nextCategoryId);
        setAttributeDefinitions(attributesResult.attributes);
        setStatus("已自动选择并确认最底层分类，官方属性已加载。");
      } catch (attributeError) {
        // The category PUT has already committed. Do not roll back the
        // confirmed leaf merely because the follow-up metadata read timed out.
        setStatus(attributeError instanceof Error
          ? `已确认最底层分类，但官方属性暂时无法读取：${attributeError.message}`
          : "已确认最底层分类，但官方属性暂时无法读取。请稍后刷新属性。");
      }
    } catch (error) {
      setCategoryLeafVerified(false);
      setCategoryActionStatus(error instanceof Error ? `分类确认失败：${error.message}` : "分类确认失败");
      setStatus(error instanceof Error ? error.message : "自动确认分类失败");
    } finally { setBusy(""); }
  }

  async function loadAttributes() {
    if (!categoryId) return;
    setBusy("attributes"); setStatus("");
    try {
      const details = await getCategoryDetails(categoryId);
      if (!details.verified || !details.leaf) {
        setCategoryLeafVerified(false);
        throw new Error("请确认最底层叶子分类，父分类不能直接上架。");
      }
      const confirmed = await confirmDraftCategory(draftId, {
        expected_content_version: draft.content_version ?? 1,
        target_site_id: "CBT",
        category_id: categoryId,
      });
      onDraftChange(confirmed.draft);
      setListingRail((current) => current.map((item) => item.id === confirmed.draft.id ? confirmed.draft : item));
      setCategoryLeafVerified(true);
      setCategoryPath((details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean).join(" > "));
      setCategoryActionStatus("已确认最终 CBT 分类");
      const result = await getCategoryAttributes(categoryId);
      setAttributeDefinitions(result.attributes);
      setStatus(result.verified ? "已读取美客多官方类目属性" : "属性尚未验证");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "读取类目属性失败");
    } finally { setBusy(""); }
  }

  function setAttribute(id: string, value: string) {
    setAttributes((current) => ({ ...current, [id]: value }));
    setSaved(null); setPreview(null); setExecution(null);
  }

  function toggleMarket(siteId: string) {
    offersInitializedRef.current = true;
    setOffers((current) => {
      if (current.some((offer) => offer.site_id === siteId)) return current.filter((offer) => offer.site_id !== siteId);
      return [...current, { site_id: siteId, title: globalTitle, listing_type_id: "gold_pro", logistic_type: "remote", picture_urls: [] }];
    });
    setSaved(null); setPreview(null); setExecution(null);
  }

  function toggleAllRemoteMarkets() {
    offersInitializedRef.current = true;
    setOffers(allRemoteSelected ? [] : remoteMarkets.map((market) => createRemoteOffer(market, globalTitle)));
    setSaved(null); setPreview(null); setExecution(null);
  }

  function updateOffer(siteId: string, key: "title" | "listing_type_id", value: string) {
    setOffers((current) => current.map((offer) => offer.site_id === siteId
      ? { ...offer, [key]: key === "title" ? normalizeCbtTitle(value) : value } as Offer : offer));
    setSaved(null); setPreview(null); setExecution(null);
  }

  async function saveProductContent() {
    if (draft.image_urls.length > MAX_PRODUCT_IMAGES) {
      throw new Error(`美客多最多允许发布 ${MAX_PRODUCT_IMAGES} 张图片，请先删除多余图片。`);
    }
    if (videoUrls.length > MAX_PRODUCT_VIDEOS) {
      throw new Error(`当前有 ${videoUrls.length} 个视频，最多保留 ${MAX_PRODUCT_VIDEOS} 个。请在视频区删除 ${videoUrls.length - MAX_PRODUCT_VIDEOS} 个后再保存。`);
    }
    const updated = await saveDraftContent(draftId, {
      expected_content_version: draft.content_version ?? 1,
      title: normalizeCbtTitle(globalTitle),
      description: sanitizeCbtDescription(description),
      brand: "Unbranded",
      image_urls: draft.image_urls.filter(Boolean),
      video_urls: videoUrls,
    });
    onDraftChange(updated);
    const ossDraft = await mirrorDraftImagesToOss(draftId);
    onDraftChange(ossDraft);
    return ossDraft;
  }

  // AI requests are intentionally manual. Collection must not spend tokens for
  // drafts that the operator may decide to discard.
  async function generateAiField(field: "title" | "description") {
    if (busy.startsWith("ai-")) return;
    setAiFeedback(null);
    if (!categoryId || !categoryLeafVerified) {
      setAiFeedback({ field, error: true, message: "请先在第 1 步选择并确认最底层 CBT 分类，再使用 AI 生成。" });
      return;
    }
    const operation = field === "title" ? "ai-title" : "ai-description";
    setBusy(operation);
    setStatus("");
    try {
      const result = await generateDraftContent(draftId, categoryId, [field]);
      onDraftChange(result.draft);
      setListingRail((current) => current.map((item) => item.id === result.draft.id ? result.draft : item));
      if (field === "title") setGlobalTitle(normalizeCbtTitle(result.title));
      else setDescription(sanitizeCbtDescription(result.description));
      setSaved(null);
      setPreview(null);
      setExecution(null);
      onReviewInvalidated();
      setAiFeedback({ field, error: false, message: field === "title" ? "AI 英文标题已生成，请检查后保存。" : "AI 英文商品描述已生成，请检查后保存。" });
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "";
      const message = rawMessage.includes("ai_content_already_generated")
        ? "该字段已经由 AI 生成过，系统未再次调用，避免重复消耗。需要重构时，请先清空该字段并保存，再点 AI。"
        : rawMessage.includes("generated_content_invalid")
          ? "AI 返回内容未通过描述质量门禁，本次没有写入；请稍后手动再试。"
          : rawMessage || "AI 生成失败，请稍后重试。";
      setAiFeedback({ field, error: true, message });
    } finally {
      setBusy("");
    }
  }

  function openImagePreview(url: string) {
    setPreviewImage(url);
    setImageZoom(1);
  }

  function closeImagePreview() {
    setPreviewImage(null);
    setImageZoom(1);
  }

  async function editSourceVariant(variant: AmazonSourceVariant) {
    if (!draft.source_product_id || variant.asin === draft.source_variant_asin || variantDraftBusy) return;
    setVariantDraftBusy(variant.asin);
    setStatus(`正在打开 ${variant.asin} 的独立草稿...`);
    try {
      const updated = await createSourceVariantDraft(draft.source_product_id, variant.asin, draft.target_site_id || "CBT");
      setListingRail((current) => uniqueDrafts([...current.filter((item) => item.id !== updated.id), updated]));
      onDraftChange(updated);
      onSelectDraft?.(updated);
      setStatus(`已打开 ${variant.asin} 的独立草稿 #${updated.id}。`);
    } catch (error) {
      setStatus(readableVariantDraftError(error));
    } finally {
      setVariantDraftBusy(null);
    }
  }

  function moveImagePreview(direction: -1 | 1) {
    const currentIndex = previewImage ? draft.image_urls.indexOf(previewImage) : -1;
    const nextImage = draft.image_urls[currentIndex + direction];
    if (!nextImage) return;
    setPreviewImage(nextImage);
    // Each source image opens at its natural fit, rather than preserving a
    // zoom level that may make the next image look unexpectedly cropped.
    setImageZoom(1);
  }

  async function setCoverImage(url: string) {
    if (videoUrls.length > MAX_PRODUCT_VIDEOS) {
      setStatus(`请先在视频区删除 ${videoUrls.length - MAX_PRODUCT_VIDEOS} 个视频，再保存图片修改。`);
      return;
    }
    const image_urls = [url, ...draft.image_urls.filter((item) => item !== url)];
    try {
      setBusy("media");
      const updated = await saveDraftContent(draftId, { expected_content_version: draft.content_version ?? 1, title: normalizeCbtTitle(globalTitle), description: sanitizeCbtDescription(description), brand: "Unbranded", image_urls, video_urls: videoUrls });
      onDraftChange(updated);
      setStatus("主图已保存。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "保存图片顺序失败"); }
    finally { setBusy(""); }
  }

  async function removeImage(url: string) {
    if (videoUrls.length > MAX_PRODUCT_VIDEOS) {
      setStatus(`请先在视频区删除 ${videoUrls.length - MAX_PRODUCT_VIDEOS} 个视频，再保存图片修改。`);
      return;
    }
    const image_urls = draft.image_urls.filter((item) => item !== url);
    try {
      setBusy("media");
      const updated = await saveDraftContent(draftId, { expected_content_version: draft.content_version ?? 1, title: normalizeCbtTitle(globalTitle), description: sanitizeCbtDescription(description), brand: "Unbranded", image_urls, video_urls: videoUrls });
      onDraftChange(updated);
      setStatus("图片已移除。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "删除图片失败"); }
    finally { setBusy(""); }
  }

  async function removeVideo(url: string) {
    const next = videoUrls.filter((item) => item !== url);
    setVideoUrls(next);
    setSaved(null); setPreview(null); setExecution(null);
    if (next.length > MAX_PRODUCT_VIDEOS) {
      setStatus(`已从待保存视频中移除 1 个；还需再移除 ${next.length - MAX_PRODUCT_VIDEOS} 个视频。`);
      return;
    }
    try {
      setBusy("media");
      const updated = await saveDraftContent(draftId, {
        expected_content_version: draft.content_version ?? 1,
        title: normalizeCbtTitle(globalTitle),
        description: sanitizeCbtDescription(description),
        brand: "Unbranded",
        image_urls: draft.image_urls,
        video_urls: next,
      });
      onDraftChange(updated);
      setStatus(`视频已保存，当前保留 ${next.length}/${MAX_PRODUCT_VIDEOS} 个。`);
    } catch (error) {
      setVideoUrls(videoUrls);
      setStatus(error instanceof Error ? error.message : "删除视频失败");
    } finally { setBusy(""); }
  }

  function marketplaceValidationErrors() {
    const errors: string[] = [];
    if (!storeId) errors.push("请选择已授权的跨境店铺");
    if (!categoryId || !categoryLeafVerified) errors.push("请选择并确认美客多最底层分类");
    if (!familyName.trim()) errors.push("请填写 Parent SKU");
    if (!globalTitle.trim() || globalTitle.length > 60) errors.push("英文标题必须为 1–60 个字符");
    if (!description.trim()) errors.push("请填写英文商品描述");
    if (draft.image_urls.length === 0) errors.push("至少需要 1 张商品图片");
    if (draft.image_urls.length > MAX_PRODUCT_IMAGES) errors.push(`美客多最多允许发布 ${MAX_PRODUCT_IMAGES} 张图片，请删除多余图片`);
    if (!Number.isInteger(Number(quantity)) || Number(quantity) < 1) errors.push("库存必须为大于 0 的整数");
    if (Number(priceUsd) <= 0) errors.push("请填写目标净收益（USD）");
    if (offers.length === 0) errors.push("至少选择一个 Remote 发布站点");
    errors.push(...missing.map((id) => `请填写必填属性：${ATTRIBUTE_NAMES_ZH[id] ?? id}`));
    return errors;
  }

  async function saveConfig() {
    if (!canSave) {
      const errors = marketplaceValidationErrors();
      setPreview({ allowed: false, errors, payload: null });
      setStatus(`暂不能保存：${errors[0] ?? "请完善美客多发布要求"}`);
      return;
    }
    setBusy("save"); setStatus(""); setPreview(null); setExecution(null);
    try {
      const savedContent = await saveProductContent();
      const removedSmallImages = Math.max(0, draft.image_urls.length - savedContent.image_urls.length);
      const config = await saveCbtListingConfig(draftId, {
        store_id: Number(storeId), category_id: categoryId, family_name: familyName,
        global_title: normalizeCbtTitle(globalTitle), description: sanitizeCbtDescription(description), price_usd: Number(priceUsd),
        available_quantity: Number(quantity),
        attributes: attributesForSave(attributes, attributeDefinitions, saved?.attributes),
        sale_terms: warrantySaleTerms(warranty),
        sites_to_sell: offers,
      });
      setSaved(config); onDraftChange(config.draft); setListingRail((current) => current.map((item) => item.id === config.draft.id ? config.draft : item)); onReviewInvalidated();
      setStatus(removedSmallImages
        ? `跨境刊登配置已保存；已自动剔除 ${removedSmallImages} 张小于 500×500px 的图片，可直接进行官方请求预检。`
        : "跨境刊登配置已保存，可直接进行官方请求预检。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "保存跨境刊登配置失败"); }
    finally { setBusy(""); }
  }

  async function previewPayload() {
    if (!canSave) {
      const errors = marketplaceValidationErrors();
      setPreview({ allowed: false, errors, payload: null });
      setStatus("预检只检查美客多发布要求；请先补齐上方提示项。");
      return;
    }
    if (!saved) {
      setPreview({ allowed: false, errors: ["请先点击保存，系统会保存当前刊登配置后再调用美客多预检。"], payload: null });
      setStatus("请先保存当前配置。");
      return;
    }
    setBusy("preview"); setStatus("");
    try {
      setPreview(await previewCbtPublishFromDraft(draftId));
    } catch (error) { setStatus(error instanceof Error ? error.message : "生成官方请求预检失败"); }
    finally { setBusy(""); }
  }

  async function executePublish() {
    if (busy) return;
    setStatus("正在等待发布确认…");
    if (!window.confirm("确认向 Mercado Libre 提交真实刊登吗？提交后将创建商品。")) {
      setStatus("已取消发布，未向美客多提交请求。");
      return;
    }
    setBusy("execute"); setExecution(null); setStatus("正在提交跨境发布任务，请等待美客多返回结果…");
    try {
      const result = await executeCbtPublishFromDraft(draftId);
      setExecution(result);
      const normalizedStatus = String(result.status || "").toLowerCase();
      if (normalizedStatus === "published") setStatus(`发布成功${result.item_id ? `，商品 ${result.item_id}` : ""}。`);
      else if (normalizedStatus === "blocked") setStatus(`发布结果待核对${result.job_id ? `（任务 #${result.job_id}）` : ""}，请查看下方逐站点结果。`);
      else setStatus(`发布失败${result.job_id ? `（任务 #${result.job_id}）` : ""}，请查看下方错误明细。`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "跨境发布请求失败，请查看发布任务记录。"); }
    finally { setBusy(""); }
  }

  return <section className="workspace wf-listing-editor">
    <header className="wf-header">
      <div><p className="eyebrow">GLOBAL SELLING · CBT</p><h2>编辑产品 / 跨境上架</h2><p>按“店铺和类目 → 商品资料 → 图片 → 描述 → SKU → 销售配置”一次完成，不再分散到多个页面。</p></div>
      <button className="secondary-button" onClick={onBackToEditing}><ArrowLeft size={16} /> 返回上架库</button>
    </header>

    <aside className="wf-similar-search" aria-label="1688 图搜货源"><strong>1688 图搜货源</strong><small>使用当前商品第 1 张图；结果按平台相似排序，前 5 个只作价格参考。</small><button type="button" onClick={searchByCoverImage} disabled={similarSearchBusy || !draft.image_urls[0]}>{similarSearchBusy ? "搜索中…" : "搜图"}</button>{similarOffers && <div className="similar-offer-list">{similarOffers.offers.map((offer) => <a key={offer.offer_id || offer.rank} href={offer.offer_id ? `https://detail.1688.com/offer/${offer.offer_id}.html` : undefined} target="_blank" rel="noreferrer"><img src={offer.image_url} alt="" /><span><b>{offer.match_level} · #{offer.rank}</b><strong>{offer.title}</strong><em>¥ {offer.price ?? "-"}</em><small>{[offer.province, offer.city].filter(Boolean).join(" ")} · 供货 {offer.supply_amount ?? "-"}</small></span></a>)}</div>}</aside>

    <div className="wf-listing-layout">
      <aside className="drafts-sidebar surface wf-listing-rail">
        <div className="drafts-sidebar-heading"><h3>待上架库</h3><span>{pendingListingRail.length} 个</span></div>
        <p className="section-note">选择商品后，在右侧完成分类、素材、售价和站点配置。</p>
        <label className="listing-search"><Search size={14} /><input value={listingSearch} placeholder="定位商品编号或标题" onChange={(event) => setListingSearch(event.target.value)} /></label>
        {listingSearch.trim() && <p className="listing-search-result">{pendingListingRail.some((item) => String(item.id) === listingSearch.trim()) || pendingListingRail.some((item) => String(item.title ?? "").toLowerCase().includes(listingSearch.trim().toLowerCase())) ? "已定位，保留前后商品" : "未找到，当前显示原列表"}</p>}
        {status && <p className="draft-rail-status" role="status">{status}</p>}
        <div className="draft-rail-list">{listingPageItems.map((item) => <button className={`draft-rail-item ${item.id === draftId ? "selected" : ""}`} key={item.id} onClick={() => onSelectDraft?.(item)}>
          {!['published', 'pending', 'validating'].includes(item.publication_status || '') && <><span className="draft-delete-wrap"><span className="draft-delete-icon" aria-hidden="true">×</span><span className="draft-delete-tooltip">删除商品</span><span role="button" tabIndex={0} className="draft-delete-hit" aria-label={`删除 ${item.title || "未命名商品"}`} onClick={(event) => void removeListingDraft(event, item)} /></span>{item.source_product_id && <span className="draft-recollect-wrap"><span className="draft-recollect-icon" aria-hidden="true">采</span><span className="draft-recollect-tooltip">重新采集素材</span><span role="button" tabIndex={0} className="draft-recollect-hit" aria-label={`重新采集 ${item.title || "未命名商品"}`} onClick={(event) => void recollectListingDraft(event, item)} />{recollectBusy === item.id && <span className="draft-recollect-spinner" aria-label="正在重新采集" />}</span>}</>}
          <img className="product-image" src={item.image_urls[0] || ""} alt="" /><span><strong>{item.title || "未命名商品"}</strong><small>#{item.id} · {item.target_site_id}</small><small>{item.publication_status === "published" ? `已发布：${item.published_sites.join("、") || "CBT"}` : item.publication_status === "pending" || item.publication_status === "validating" ? "发布中" : item.publication_status === "failed" || item.publication_status === "blocked" ? "发布失败，可修改后重试" : "未发布"}</small></span></button>)}</div>
        <div className="listing-pagination" aria-label="上架库分页">
          <button type="button" className="tiny-button" disabled={listingPage <= 1} onClick={() => setListingPage((page) => page - 1)}>上一页</button>
          <span>第 {listingPage}/{listingPageCount} 页</span>
          <button type="button" className="tiny-button" disabled={listingPage >= listingPageCount} onClick={() => setListingPage((page) => page + 1)}>下一页</button>
        </div>
      </aside>
      <main className="wf-editor-main">
      <section id="store-category" className="surface wf-section">
        <div className="wf-section-title"><span>1</span><div><h3>店铺和类目</h3><p>先确认跨境店和最底层 CBT 分类，确认后才加载官方属性。</p></div><button className="icon-button" title="刷新店铺能力" disabled={!storeId || busy === "profile"} onClick={() => setProfileReloadKey((value) => value + 1)}><RefreshCw size={17} /></button></div>
        <div className="wf-form-row"><label>上架店铺 *<select value={storeId} onChange={(event) => { setStoreId(event.target.value); setOffers([]); setHasSavedConfig(false); offersInitializedRef.current = false; setPreview(null); }}><option value="">选择已启用的 CBT 店铺</option>{cbtStores.map((store) => <option key={store.id} value={store.id}>{store.display_name} · 卖家 {store.seller_id}</option>)}</select><small>商品、授权令牌、发布记录和限流将按此店铺独立执行。</small></label>
          <div className="wf-sites"><strong>同时发布到站点</strong><label><input type="checkbox" checked={allRemoteSelected} disabled={profile?.model !== "traditional_global" || remoteMarkets.length === 0} onChange={toggleAllRemoteMarkets} /> 全选</label>{remoteMarkets.map((market) => <label key={market.site_id}><input type="checkbox" checked={offers.some((offer) => offer.site_id === market.site_id)} onChange={() => toggleMarket(market.site_id)} /> {MARKET_NAMES[market.site_id]}</label>)}<label className="is-disabled"><input type="checkbox" disabled /> 墨西哥（FULL）</label></div></div>
        {profile && <p className="section-note">卖家 {profile.seller_id} · {profile.model === "traditional_global" ? "传统 Global Selling" : "User Products"}。Remote 站点默认全部勾选；墨西哥 FULL 由独立流程处理。</p>}
          <div className="wf-category-line"><label>分类关键词搜索<small>标题智能匹配保留；也可输入中文或英文关键词，候选不合适时逐级浏览分类。</small><input value={categorySearchQuery} placeholder="例如：淋浴喷头 / shower head" onChange={(event) => setCategorySearchQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void predictCategory(); }} /></label><button type="button" onClick={() => void predictCategory(globalTitle)} disabled={busy === "category" || busy === "attributes"}><Search size={16} /> 按标题智能匹配</button><button type="button" onClick={() => void predictCategory()} disabled={busy === "category" || busy === "attributes"}><Search size={16} /> 搜索关键词</button></div><label>搜索匹配分类<select className="category-prediction-select" value="" onChange={(event) => choosePrediction(event.target.value)} disabled={predictions.length === 0 || busy === "attributes"}><option value="">{predictions.length ? "选择一个匹配分类" : "输入关键词后搜索"}</option>{predictions.map((item) => { const id = String(item.category_id ?? ""); const name = String(item.category_name_zh ?? item.category_name ?? item.domain_name ?? id); const isLeaf = item.is_leaf === true; return <option key={id} value={id}>{name} · {isLeaf ? "最底层，点击即确认" : "父级，点击进入下一级"}</option>; })}</select></label><label>已选最终 CBT 分类 *<input readOnly value={categoryId} placeholder="选择最底层分类后自动确认" /></label>
        {categoryPath && <p className="category-path-label">{categoryPath}{categoryId ? ` · ${categoryLeafVerified ? "最终 CBT 最底层分类已确认" : "待确认最终 CBT 分类"}` : " · 请在上方选择对应的 CBT 最底层分类"}</p>}
        {categoryActionStatus && <p className={`category-action-status ${categoryLeafVerified ? "success" : "error"}`} role="status">{categoryActionStatus}</p>}
        {predictions.length > 0 && <div className="prediction-list">{predictions.map((item) => { const id = String(item.category_id ?? ""); const name = String(item.category_name_zh ?? item.category_name ?? item.domain_name ?? id); const isSelected = id === categoryId; const isLeaf = item.is_leaf === true; return <button type="button" className={isSelected ? "selected" : ""} key={id} onClick={(event) => { event.preventDefault(); event.stopPropagation(); if (isLeaf) void selectCategory(id, item); else void browseCategoryTree(id); }}><strong>{name}{isLeaf ? " · 最底层" : " · 进入下一级"}</strong><small>{String(item.parent_path_zh ?? item.parent_path ?? "正在读取母级分类路径")}</small><small>{id} · {isSelected ? "已确认并加载属性" : isLeaf ? "点击后自动确认" : "点击进入子分类"}</small></button>; })}</div>}
        <div className="section-note">搜索结果不合适？<button className="tiny-button" type="button" onClick={() => { setShowCategoryTree((value) => !value); if (!showCategoryTree && !categoryTree.length) void browseCategoryTree(); }}>{showCategoryTree ? "收起分类目录" : "浏览完整分类目录"}</button></div>
        {showCategoryTree && <div className="prediction-list"><div className="section-note"><strong>官方 CBT 分类目录</strong> · {categoryTreePath || "正在读取"} <button className="tiny-button" type="button" onClick={() => browseCategoryTree()} disabled={busy === "category-tree"}>返回根分类</button></div>{categoryTree.map((item) => { const id = String(item.id ?? ""); const name = String(item.name_zh ?? item.name ?? id); return <button key={id} type="button" onClick={() => browseCategoryTree(id)}><strong>{name}</strong><small>{id} · 点击展开；没有子分类时即选为最终候选</small></button>; })}</div>}
      </section>

      <section id="basic" className="surface wf-section"><div className="wf-section-title"><span>2</span><div><h3>产品基本信息</h3><p>标题强制英文不超过 60 字符；品牌固定为无品牌。</p></div></div><div className="form-grid two-col"><label>Parent SKU / 产品族名称 *<input value={familyName} placeholder="例如 SKU02761" onChange={(event) => { const value = event.target.value; setFamilyName(value); setAttributes((current) => ({ ...current, MODEL: value })); setSaved(null); setPreview(null); }} /></label><label>可售库存 *<input type="number" min="1" step="1" value={quantity} onChange={(event) => { setQuantity(event.target.value); setSaved(null); setPreview(null); }} /></label></div><label><span className="wf-field-label-row">英文标题 *<button type="button" className="tiny-button wf-ai-button" disabled={busy.startsWith("ai-")} onClick={() => void generateAiField("title")}><Sparkles size={13} />{busy === "ai-title" ? "生成中…" : "AI"}</button></span><div className="wf-title-input"><input value={globalTitle} onChange={(event) => { setGlobalTitle(normalizeCbtTitle(event.target.value)); setSaved(null); setPreview(null); }} /><small>{globalTitle.length}/60</small></div>{aiFeedback?.field === "title" && <small className={`wf-ai-feedback ${aiFeedback.error ? "error" : "success"}`} role="status">{aiFeedback.message}</small>}{globalTitle.length > 60 && <small className="inline-warning">标题超过 60 字符：不会自动截断，请使用 AI 重新生成或手动精简。</small>}</label><label>品牌（固定）<input disabled value="Unbranded（无品牌）" /></label></section>

      <section id="media" className="surface wf-section"><div className="wf-section-title"><span>3</span><div><h3>产品图片</h3><p>使用采集到的原图；第 1 张是主图。小规格缩略图不会入库，美客多最多发布 12 张。</p></div><strong>{draft.image_urls.length}/{MAX_PRODUCT_IMAGES} 张</strong></div>{draft.image_urls.length > MAX_PRODUCT_IMAGES && <p className="inline-warning">当前有 {draft.image_urls.length} 张图片，请删除 {draft.image_urls.length - MAX_PRODUCT_IMAGES} 张后再保存或发布。</p>}<div className="wf-media-grid">{draft.image_urls.map((url,index) => <article className={`wf-media-card ${index === 0 ? "cover" : ""}`} key={url}><div className="wf-media-label">{index === 0 ? "主图" : `图片 ${index + 1}`}</div><button className="wf-media-preview-trigger" type="button" title="点击查看大图" onClick={() => openImagePreview(url)}><CbtMediaImage src={url} alt={`商品图片 ${index + 1}`} /></button><div><button className="tiny-button" disabled={index === 0 || busy === "media"} onClick={() => setCoverImage(url)}>设为主图</button><button className="tiny-button danger" disabled={busy === "media"} onClick={() => removeImage(url)}>删除</button></div></article>)}</div>{draft.image_urls.length === 0 && <p className="inline-warning">当前没有可发布图片，请先回到上架库补充素材。</p>}<div className="wf-video-line"><strong>产品视频</strong><span>{videoUrls.length}/{MAX_PRODUCT_VIDEOS} 个；视频独立保存，未进入商品图片。</span></div>{videoUrls.length > MAX_PRODUCT_VIDEOS && <p className="inline-warning">当前视频超过保存上限。请从下方选择删除 {videoUrls.length - MAX_PRODUCT_VIDEOS} 个；删除到 3 个后会自动保存。</p>}<div className="wf-video-grid">{videoUrls.map((url, index) => <article className="wf-video-card" key={url}><div className="wf-media-label">视频 {index + 1}</div><video controls preload="metadata" src={url}>当前浏览器无法预览此视频。</video><div><a className="tiny-button" href={url} target="_blank" rel="noreferrer">打开视频</a><button className="tiny-button danger" disabled={busy === "media"} onClick={() => void removeVideo(url)}>删除</button></div></article>)}</div>{videoUrls.length === 0 && <p className="section-note">当前未采集到视频链接。</p>}</section>

      <section id="description" className="surface wf-section"><div className="wf-section-title"><span>4</span><div><h3>描述</h3><p>英文、基于采集信息；不出现品牌。末尾保留 7 天店铺保修说明。</p></div><button type="button" className="tiny-button wf-ai-button" disabled={busy.startsWith("ai-")} onClick={() => void generateAiField("description")}><Sparkles size={13} />{busy === "ai-description" ? "生成中…" : "AI 生成描述"}</button></div><label>英文商品描述 *<textarea rows={10} value={description} onChange={(event) => { setDescription(sanitizeCbtDescription(event.target.value)); setSaved(null); setPreview(null); }} /></label>{aiFeedback?.field === "description" && <p className={`wf-ai-feedback ${aiFeedback.error ? "error" : "success"}`} role="status">{aiFeedback.message}</p>}</section>

      <section id="variants" className="surface wf-section">
        <div className="wf-section-title"><span>5</span><div><h3>变体与 SKU</h3><p>先展示 Amazon 采集到的全部变体和 SKU 图；当前高亮 ASIN 可在本页编辑，其他 ASIN 需采集具体页面后生成独立草稿。</p></div></div>
        <div className="wf-sku-row">
          <div><span>来源 ASIN</span><strong>{draft.source_variant_asin || "未提供"}</strong></div>
          <div><span>已采集规格</span><strong>{Object.entries(draftVariantAttributes).map(([key, value]) => `${key}: ${value}`).join(" · ") || "等待重新采集变体"}</strong></div>
          <div><span>卖家 SKU *</span><input value={attributes.SELLER_SKU ?? ""} placeholder="内部 SKU" onChange={(event) => setAttribute("SELLER_SKU", event.target.value)} /></div>
        </div>
        {sourceVariants.length > 0 ? (
          <div className="attribute-mapping" aria-label="Amazon 采集变体">
            <div className="attribute-mapping-heading"><span><strong>Amazon 变体</strong><small>已采集 {sourceVariants.length} 个 ASIN；当前 ASIN 已高亮</small></span></div>
            <div className="attribute-suggestion-list">
              {sourceVariants.map((variant) => <div className={`attribute-suggestion ${variant.selected || variant.asin === draft.source_variant_asin ? "selected" : ""}`} key={variant.asin}>
                <span className="amazon-variant-source">
                  {variant.image_urls[0] ? <a href={variant.image_urls[0]} target="_blank" rel="noreferrer" title="打开 SKU 图片"><img src={variant.image_urls[0]} alt={`${variant.asin} SKU 图片`} /></a> : <span className="amazon-variant-no-image">无 SKU 图</span>}
                  <span><small>{variant.asin}</small><strong>{Object.entries(variant.attributes).map(([name, value]) => `${name}: ${value}`).join(" · ") || "未返回规格"}</strong><small>{variant.image_urls.length > 0 ? `${variant.image_urls.length} 张 SKU 图` : "未采集 SKU 图"}</small></span>
                </span>
                <span className="amazon-variant-actions">
                  {variant.selected || variant.asin === draft.source_variant_asin
                    ? <span className="state-pill ready">本页可编辑</span>
                    : <button type="button" className="tiny-button" disabled={variantDraftBusy !== null} onClick={() => void editSourceVariant(variant)}>{variantDraftBusy === variant.asin ? "打开中..." : "编辑此变体"}</button>}
                  {!(variant.selected || variant.asin === draft.source_variant_asin) && <span className="state-pill">独立草稿</span>}
                </span>
              </div>)}
            </div>
          </div>
        ) : <p className="section-note">当前未采集到变体；点击上架库卡片的绿色“采”可重新抓取当前 Amazon 商品卡。</p>}
        {variationDefinitions.length > 0 && Object.keys(draftVariantAttributes).length > 0 && (
          <div className="form-grid two-col cbt-attributes" aria-label="官方变体属性设置">
            {variationDefinitions.map((definition) => {
              const id = String(definition.id ?? "").toUpperCase();
              const values = Array.isArray(definition.values) ? definition.values.filter((value): value is Record<string, unknown> => Boolean(value && typeof value === "object")) : [];
              const listId = `variation-values-${id}`;
              return <label key={id}>{attributeNameZh(definition, id)}（官方变体属性）
                <input list={values.length ? listId : undefined} value={attributes[id] ?? ""} placeholder={sourceVariantValueForDefinition(definition, draftVariantAttributes) || "填写当前 ASIN 的规格"} onChange={(event) => setAttribute(id, event.target.value)} />
                {values.length > 0 && <datalist id={listId}>{values.map((value) => <option key={String(value.id ?? value.name)} value={String(value.name ?? "")} />)}</datalist>}
              </label>;
            })}
          </div>
        )}
        {sourceVariants.length > 1 && <p className="section-note">当前授权店铺为传统 CBT Global Selling：每个 Amazon ASIN 会保持独立草稿/发布，不会把不同商品强行合并成一个美客多变体。</p>}
        <div className="form-grid two-col cbt-attributes"><label>型号（自动同步 Parent SKU）<input disabled value={familyName} /></label>{requiredIds.filter((id) => id !== "SELLER_SKU" && id !== "BRAND" && id !== "MODEL").map((id) => { const definition = attributeDefinitions.find((item) => String(item.id).toUpperCase() === id); return <label key={id}>{attributeNameZh(definition, id)} *<input value={attributes[id] ?? ""} placeholder={id === "ITEM_CONDITION" ? "new" : "例如 10 cm / 250 g"} onChange={(event) => setAttribute(id, event.target.value)} /></label>; })}</div>
        <label>店铺质保条款<select value={warranty} onChange={(event) => { setWarranty(event.target.value); setSaved(null); setPreview(null); }}><option value="7 days">7 天</option><option value="No warranty">无质保</option><option value="30 days">30 天</option></select></label>{missing.length > 0 && <p className="inline-warning">还缺少官方必填字段：{missing.join("、")}。</p>}
      </section>

      <section id="sales" className="surface wf-section"><div className="wf-section-title"><span>6</span><div><h3>销售配置</h3><p>只填写一次目标净收益（USD）；提交值以 USD 保存，不填写采购成本、国内运费或平台费用。</p></div></div><div className="cbt-pricing-rule">全球销售采用净收益模式：ERP 会把你的“采购成本 + 国内运费 + 利润率”收益测算自动带入 USD 净收益；美客多据此计算各站买家售价。</div><div className="cbt-sales-table-wrap"><table className="cbt-sales-table"><thead><tr><th>站点</th><th>美客多售价</th><th>目标净收益（USD）</th><th>刊登类型</th><th>标题</th></tr></thead><tbody><tr className="cbt-global-row"><th><Globe2 size={16} /> 全球</th><td><span className="cbt-derived-value">由美客多自动计算</span></td><td><input type="number" min="0.01" step="0.01" value={priceUsd} placeholder="填写 USD 净收益" onChange={(event) => { setPriceUsd(event.target.value); setSaved(null); setPreview(null); }} />{pricing && <small>收益测算自动值：USD {pricing.target_price.toFixed(2)}</small>}</td><td><span className="cbt-derived-value">按站点配置</span></td><td><div className="cbt-title-input"><input value={globalTitle} onChange={(event) => setGlobalTitle(normalizeCbtTitle(event.target.value))} /><small>{globalTitle.length}/60</small></div></td></tr>{remoteMarkets.map((market) => { const offer = offers.find((item) => item.site_id === market.site_id); const enabled = Boolean(offer); return <tr className={enabled ? "" : "disabled"} key={market.site_id}><th><div className="cbt-site-toggle"><span><strong>{MARKET_NAMES[market.site_id] ?? market.site_id}</strong><small>{market.site_id} · Remote · {enabled ? "已在上方选中" : "未选中"}</small></span></div></th><td><span className="cbt-derived-value">由美客多结算</span></td><td><span className="cbt-derived-value">{estimatedProfitUsd === null ? "-" : estimatedProfitUsd.toFixed(2)}</span></td><td>{(() => { const ids = officialTypes[market.site_id]; if (!categoryId.startsWith("CBT")) return <span className="cbt-derived-value">请先确认 CBT 分类</span>; if (officialTypesLoading) return <span className="cbt-derived-value">正在读取官方类型…</span>; if (!ids?.length) return <span className="cbt-derived-value">官方未返回，可预检确认</span>; return <select disabled={!enabled} value={offer?.listing_type_id ?? ids[0]} onChange={(event) => updateOffer(market.site_id, "listing_type_id", event.target.value)}>{ids.includes("gold_pro") && <option value="gold_pro">Premium（优质）</option>}{ids.includes("gold_special") && <option value="gold_special">Classic（经典）</option>}</select>; })()}</td><td><div className="cbt-title-input"><input disabled={!enabled} value={offer?.title ?? globalTitle} onChange={(event) => updateOffer(market.site_id, "title", event.target.value)} /><small>{(offer?.title ?? globalTitle).length}/60</small></div></td></tr>; })}{fullMarkets.map((market) => <tr className="disabled cbt-full-row" key={`${market.site_id}-${market.logistic_type}`}><th><div className="cbt-site-toggle"><span><strong>墨西哥（FULL）</strong><small>MLM · FULL 履约不参与本次发布</small></span></div></th><td>不发布</td><td>-</td><td>已排除</td><td>由 FULL 流程单独管理</td></tr>)}</tbody></table></div>{pricing && pricing.target_currency !== "USD" && <p className="inline-warning">请补充 USD 成本定价后保存；当前草稿的本地站价格不能用于 CBT 发布。</p>}{preview && <div className={`validation-result ${preview.allowed ? "ready" : "blocked"}`}><strong>{preview.allowed ? "官方请求预检通过" : "刊登请求未通过"}</strong>{preview.errors.map((error) => <span key={error}>{error}</span>)}</div>}{execution && <div className={`validation-result ${execution.status === "published" ? "ready" : "blocked"}`}><strong>{execution.status === "published" ? "已提交并创建商品" : "未创建商品"}</strong>{execution.item_id && <span>商品 ID：{execution.item_id}</span>}{execution.permalink && <a href={execution.permalink} target="_blank" rel="noreferrer">打开商品页</a>}{execution.errors.map((error) => <span key={error}>{error}</span>)}{execution.response_details && Object.keys(execution.response_details).length > 0 && <SitePublishResults details={execution.response_details} />}</div>}</section>
      </main>
    </div>
    {previewImage && <div className="wf-image-lightbox" role="dialog" aria-modal="true" aria-label="图片大图预览" onClick={closeImagePreview}>
      <div className="wf-image-lightbox-panel" onClick={(event) => event.stopPropagation()}>
        <div className="wf-image-lightbox-actions"><span>图片 {previewImageIndex + 1}/{draft.image_urls.length}</span><button type="button" onClick={() => setImageZoom((value) => Math.max(0.5, Number((value - 0.25).toFixed(2))))}>− 缩小</button><span>{Math.round(imageZoom * 100)}%</span><button type="button" onClick={() => setImageZoom((value) => Math.min(3, Number((value + 0.25).toFixed(2))))}>＋ 放大</button><button type="button" className="danger" onClick={closeImagePreview}>关闭 ×</button></div>
        <div className="wf-image-lightbox-canvas">
          {draft.image_urls.length > 1 && <button type="button" className="wf-image-lightbox-nav previous" aria-label="查看上一张图片" title="上一张图片" disabled={!hasPreviousPreviewImage} onClick={() => moveImagePreview(-1)}><ChevronLeft size={30} /></button>}
          <img src={previewImage} alt={`商品图片大图预览 ${previewImageIndex + 1}`} style={{ transform: `scale(${imageZoom})` }} />
          {draft.image_urls.length > 1 && <button type="button" className="wf-image-lightbox-nav next" aria-label="查看下一张图片" title="下一张图片" disabled={!hasNextPreviewImage} onClick={() => moveImagePreview(1)}><ChevronRight size={30} /></button>}
        </div>
      </div>
    </div>}
    <footer className="wf-action-bar"><span role="status" aria-live="polite">{status || (saved ? "配置已保存" : "请先完成必填内容")}</span><div><button className="secondary-button" onClick={onBackToEditing}>取消</button><button disabled={busy === "save"} onClick={saveConfig}><Save size={16} /> 保存</button><button className="secondary-button" disabled={busy === "preview"} onClick={previewPayload}><ListChecks size={16} /> 预检</button><button disabled={!preview?.allowed || !readiness?.mercado_libre.live_publish_enabled || busy === "execute"} onClick={executePublish} aria-busy={busy === "execute"}>{busy === "execute" ? <RefreshCw className="spin" size={16} /> : <Globe2 size={16} />} {busy === "execute" ? "正在提交…" : "立即发布"}</button></div></footer>
  </section>;
}

