import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  ListChecks,
  ListPlus,
  RefreshCw,
  Rocket,
  Save,
  Search,
  Sparkles,
  Store,
  Truck,
} from "lucide-react";
import {
  approveDraft,
  enqueuePublishBatch,
  enqueuePublishFromDraft,
  executePublishFromDraft,
  getCategoryAttributes,
  getCategoryPredictions,
  getDraftListingConfig,
  getDraftAttributeSuggestions,
  getListingTypes,
  getStoreCategoryListingTypes,
  getStoreShippingOptions,
  getSystemReadiness,
  listPublishJobs,
  listDrafts,
  listStores,
  preflightPublishBatch,
  previewPublishFromDraft,
  refreshCategoryAttributes,
  refreshListingTypes,
  retryPublishJob,
  saveDraftListingConfig,
  type DraftApproval,
  type AttributeSuggestion,
  type DraftListingConfig,
  type ProductDraft,
  type ProductDraftRead,
  type PublishBatchEnqueueResult,
  type PublishBatchPreflightResult,
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

const MAX_PUBLISH_BATCH_SIZE = 50;

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

function readablePublishError(value: string) {
  if (value === "listing_types_not_verified") return "Refresh seller/category listing eligibility before publishing.";
  if (value === "listing_type_not_available") return "This listing type is not available for the selected seller and category.";
  if (value === "category_attributes_not_verified") return "Refresh verified category attributes before publishing.";
  if (value.startsWith("required_category_attribute_missing:")) {
    return `${value.split(":", 2)[1]} is required.`;
  }
  if (value.startsWith("category_attribute_value_id_invalid:")) {
    return `${value.split(":", 2)[1]} has an invalid category value.`;
  }
  if (value.startsWith("category_attribute_value_id_unverifiable:")) {
    return `${value.split(":", 2)[1]} must be reselected from verified category values.`;
  }
  if (value.startsWith("category_attribute_unknown:")) {
    return `${value.split(":", 2)[1]} is not available in this category.`;
  }
  if (value.includes("meli_metadata_unavailable")) {
    return "Mercado Libre attribute metadata is temporarily unavailable.";
  }
  return value;
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
  const [listingTypeNames, setListingTypeNames] = useState<Record<string, string>>({});
  const [listingTypeId, setListingTypeId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [categoryAttributes, setCategoryAttributes] = useState<Record<string, unknown>[]>([]);
  const [categoryAttributesVerified, setCategoryAttributesVerified] = useState(false);
  const [attributeValues, setAttributeValues] = useState<Record<string, string>>({});
  const [attributeValueIds, setAttributeValueIds] = useState<Record<string, string>>({});
  const [attributeSuggestions, setAttributeSuggestions] = useState<AttributeSuggestion[]>([]);
  const [attributeError, setAttributeError] = useState("");
  const [savedConfig, setSavedConfig] = useState<DraftListingConfig | null>(null);
  const [approval, setApproval] = useState<DraftApproval | null>(null);
  const [preview, setPreview] = useState<PublishValidationResult | null>(null);
  const [previewFingerprint, setPreviewFingerprint] = useState("");
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [shippingOptions, setShippingOptions] = useState<ShippingOption[]>([]);
  const [selectedShippingKey, setSelectedShippingKey] = useState("");
  const [availableQuantity, setAvailableQuantity] = useState("");
  const [shippingStatus, setShippingStatus] = useState("");
  const [jobs, setJobs] = useState<PublishJobRecord[]>([]);
  const [jobsRefreshing, setJobsRefreshing] = useState(false);
  const [batchDrafts, setBatchDrafts] = useState<ProductDraftRead[]>([]);
  const [selectedBatchDraftIds, setSelectedBatchDraftIds] = useState<Set<number>>(new Set());
  const [batchPublishAcknowledged, setBatchPublishAcknowledged] = useState(false);
  const [batchPreflightResult, setBatchPreflightResult] = useState<PublishBatchPreflightResult | null>(null);
  const [batchPublishResult, setBatchPublishResult] = useState<PublishBatchEnqueueResult | null>(null);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const initRequestEpochRef = useRef(0);
  const siteRequestEpochRef = useRef(0);
  const listingTypeRequestEpochRef = useRef(0);
  const categoryPredictionEpochRef = useRef(0);
  const categorySelectionEpochRef = useRef(0);
  const categoryAttributesEpochRef = useRef(0);
  const batchPreflightEpochRef = useRef(0);
  const publishJobsRequestEpochRef = useRef(0);
  const publishJobsMountedRef = useRef(true);

  const refreshPublishJobs = useCallback(async (showFeedback = false) => {
    const requestEpoch = ++publishJobsRequestEpochRef.current;
    if (showFeedback) setJobsRefreshing(true);
    try {
      const rows = await listPublishJobs();
      if (
        publishJobsMountedRef.current
        && publishJobsRequestEpochRef.current === requestEpoch
      ) {
        setJobs(rows);
        if (showFeedback) setStatus("Publish jobs refreshed");
      }
    } catch (error) {
      if (
        showFeedback
        && publishJobsMountedRef.current
        && publishJobsRequestEpochRef.current === requestEpoch
      ) {
        setStatus(error instanceof Error ? error.message : "Failed to refresh publish jobs");
      }
    } finally {
      if (showFeedback && publishJobsMountedRef.current) setJobsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    listDrafts()
      .then((rows) => {
        if (!cancelled) setBatchDrafts(rows);
      })
      .catch((error) => {
        if (!cancelled) setStatus(error instanceof Error ? error.message : "Failed to load drafts");
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    publishJobsMountedRef.current = true;
    void refreshPublishJobs(false);
    return () => {
      publishJobsMountedRef.current = false;
      publishJobsRequestEpochRef.current += 1;
    };
  }, [refreshPublishJobs]);

  useEffect(() => {
    if (!jobs.some((job) => job.status === "pending" || job.status === "validating")) return;
    let cancelled = false;
    let timer = 0;
    const poll = async () => {
      await refreshPublishJobs(false);
      if (!cancelled) timer = window.setTimeout(poll, 3000);
    };
    timer = window.setTimeout(poll, 3000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [jobs, refreshPublishJobs]);

  useEffect(() => {
    let cancelled = false;
    const initEpoch = ++initRequestEpochRef.current;
    const initialSiteEpoch = ++siteRequestEpochRef.current;
    const initialListingTypeEpoch = ++listingTypeRequestEpochRef.current;
    const initialCategoryEpoch = ++categorySelectionEpochRef.current;
    categoryAttributesEpochRef.current += 1;
    if (!draft) return () => { cancelled = true; };
    const nextSite = draft.target_site_id;
    setSiteId(nextSite);
    setListingTypes([]);
    setListingTypeId("");
    setCategoryId(draft.target_category_id || "");
    setCategoryAttributes([]);
    setCategoryAttributesVerified(false);
    setAttributeValues({});
    setAttributeValueIds({});
    setAttributeSuggestions([]);
    setAttributeError("");
    setSavedConfig(null);
    setAvailableQuantity("");
    setPreview(null);
    setApproval(null);
    setExecution(null);
    const configRequest = draftId ? getDraftListingConfig(draftId) : Promise.resolve(null);
    Promise.all([
      getSystemReadiness(),
      listStores(),
      getListingTypes(nextSite),
      configRequest,
    ])
      .then(([system, storeRows, metadata, config]) => {
        if (cancelled || initRequestEpochRef.current !== initEpoch) return;
        setReadiness(system);
        setStores(storeRows);
        if (listingTypeRequestEpochRef.current === initialListingTypeEpoch) {
          setListingTypes(metadata.listing_type_ids);
          setListingTypesVerified(metadata.verified);
        }
        if (siteRequestEpochRef.current !== initialSiteEpoch) return;
        if (config && categorySelectionEpochRef.current === initialCategoryEpoch) {
          setSavedConfig(config);
          setSiteId(config.site_id);
          setStoreId(config.store_id ? String(config.store_id) : "");
          setCategoryId(config.category_id);
          setListingTypeId(config.listing_type_id);
          setAvailableQuantity(
            config.available_quantity ? String(config.available_quantity) : "",
          );
          setSelectedShippingKey(
            config.shipping_mode && config.shipping_logistic_type
              ? `${config.shipping_mode}:${config.shipping_logistic_type}`
              : "",
          );
          setAttributeValues(
            Object.fromEntries(config.attributes.map((item) => [item.id, item.value_name])),
          );
          setAttributeValueIds(
            Object.fromEntries(
              config.attributes
                .filter((item) => item.value_id)
                .map((item) => [item.id, item.value_id as string]),
            ),
          );
          void loadAttributes(
            false,
            config.category_id,
            String(config.store_id ?? ""),
            config.listing_type_id,
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
        if (!cancelled && initRequestEpochRef.current === initEpoch) {
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
    label: listingTypeNames[type.id] || type.label,
    available: listingTypes.includes(type.id),
  }));
  const requiredAttributes = useMemo(
    () => categoryAttributes.filter((attribute) => {
      const id = String(attribute.id ?? "");
      const tags = attribute.tags as Record<string, unknown> | undefined;
      return Boolean(id === "ITEM_CONDITION" || tags?.required || tags?.catalog_required);
    }),
    [categoryAttributes],
  );
  const visibleAttributes = useMemo(() => {
    const suggestedIds = new Set(attributeSuggestions.map((item) => item.attribute_id));
    return categoryAttributes.filter((attribute) => {
      const id = String(attribute.id ?? "");
      const tags = attribute.tags as Record<string, unknown> | undefined;
      return Boolean(
        id === "ITEM_CONDITION"
          || tags?.required
          || tags?.catalog_required
          || suggestedIds.has(id),
      );
    });
  }, [attributeSuggestions, categoryAttributes]);
  const currentAttributes = useMemo(
    () => Object.entries(attributeValues)
      .filter(([, value]) => value.trim())
      .map(([id, value_name]) => ({
        id,
        value_name: value_name.trim(),
        ...(attributeValueIds[id] ? { value_id: attributeValueIds[id] } : {}),
      }))
      .sort((left, right) => left.id.localeCompare(right.id)),
    [attributeValueIds, attributeValues],
  );
  const normalizedSavedAttributes = useMemo(
    () => (savedConfig?.attributes ?? [])
      .map(({ id, value_name, value_id }) => ({
        id,
        value_name: value_name.trim(),
        ...(value_id ? { value_id } : {}),
      }))
      .sort((left, right) => left.id.localeCompare(right.id)),
    [savedConfig],
  );
  const missingRequiredAttributes = requiredAttributes.filter((attribute) => {
    const id = String(attribute.id ?? "");
    if (id === "ITEM_CONDITION") return !attributeValueIds[id]?.trim();
    return !attributeValues[id]?.trim();
  });
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
    available_quantity: Number(availableQuantity),
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
    const listingTypeEpoch = ++listingTypeRequestEpochRef.current;
    categorySelectionEpochRef.current += 1;
    categoryPredictionEpochRef.current += 1;
    categoryAttributesEpochRef.current += 1;
    setSiteId(nextSite);
    setListingTypes([]);
    setListingTypeId("");
    setCategoryId("");
    setPredictions([]);
    setCategoryAttributes([]);
    setCategoryAttributesVerified(false);
    setAttributeValues({});
    setAttributeValueIds({});
    setAttributeSuggestions([]);
    setAttributeError("");
    setSavedConfig(null);
    setPreview(null);
    setShippingOptions([]);
    setSelectedShippingKey("");
    const matchingStore = stores.find((store) => store.site_id === nextSite && store.oauth_status === "connected");
    setStoreId(matchingStore?.id ?? "");
    setBusy("listing-types");
    try {
      const result = await getListingTypes(nextSite);
      if (
        siteRequestEpochRef.current !== requestEpoch
        || listingTypeRequestEpochRef.current !== listingTypeEpoch
      ) return;
      setListingTypes(result.listing_type_ids);
      setListingTypesVerified(result.verified);
      if (result.listing_type_ids.includes("gold_special")) setListingTypeId("gold_special");
      else if (result.listing_type_ids.includes("gold_pro")) setListingTypeId("gold_pro");
    } catch (error) {
      if (
        siteRequestEpochRef.current === requestEpoch
        && listingTypeRequestEpochRef.current === listingTypeEpoch
      ) {
        setStatus(error instanceof Error ? error.message : "Failed to load listing types");
      }
    } finally {
      if (
        siteRequestEpochRef.current === requestEpoch
        && listingTypeRequestEpochRef.current === listingTypeEpoch
      ) setBusy("");
    }
  }

  async function refreshCommercialTypes() {
    const requestEpoch = ++listingTypeRequestEpochRef.current;
    setBusy("listing-types");
    setStatus("");
    try {
      if (storeId && categoryId) {
        const result = await getStoreCategoryListingTypes(Number(storeId), categoryId);
        if (listingTypeRequestEpochRef.current !== requestEpoch) return;
        setListingTypes(result.listing_types.map((item) => item.id));
        setListingTypeNames(
          Object.fromEntries(result.listing_types.map((item) => [item.id, item.name])),
        );
        setListingTypesVerified(result.verified);
        return;
      }
      const result = await refreshListingTypes(siteId);
      if (listingTypeRequestEpochRef.current !== requestEpoch) return;
      setListingTypes(result.listing_type_ids);
      setListingTypeNames({});
      setListingTypesVerified(result.verified);
    } catch (error) {
      if (listingTypeRequestEpochRef.current === requestEpoch) {
        setStatus(error instanceof Error ? error.message : "Failed to refresh listing types");
      }
    } finally {
      if (listingTypeRequestEpochRef.current === requestEpoch) setBusy("");
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

  async function loadAttributes(
    force = false,
    categoryOverride = "",
    storeOverride = "",
    listingTypeOverride = "",
  ) {
    const requestedCategoryId = categoryOverride || categoryId;
    const requestedStoreId = storeOverride || storeId;
    const requestedListingTypeId = listingTypeOverride || listingTypeId;
    if (!requestedCategoryId) return;
    const requestEpoch = ++categoryAttributesEpochRef.current;
    setBusy("attributes");
    setStatus("");
    setAttributeError("");
    try {
      const [result, eligibleTypes] = await Promise.all([
        force
          ? refreshCategoryAttributes(requestedCategoryId)
          : getCategoryAttributes(requestedCategoryId),
        requestedStoreId
          ? getStoreCategoryListingTypes(Number(requestedStoreId), requestedCategoryId)
          : Promise.resolve(null),
      ]);
      if (categoryAttributesEpochRef.current !== requestEpoch) return;
      if (eligibleTypes) {
        const eligibleIds = eligibleTypes.listing_types.map((item) => item.id);
        setListingTypes(eligibleIds);
        setListingTypeNames(
          Object.fromEntries(eligibleTypes.listing_types.map((item) => [item.id, item.name])),
        );
        setListingTypesVerified(eligibleTypes.verified);
        if (eligibleIds.includes(requestedListingTypeId)) {
          setListingTypeId(requestedListingTypeId);
        } else {
          setListingTypeId(
            eligibleIds.includes("gold_special")
              ? "gold_special"
              : eligibleIds.includes("gold_pro") ? "gold_pro" : "",
          );
        }
      } else {
        setListingTypesVerified(false);
      }
      setCategoryAttributes(result.attributes);
      setCategoryAttributesVerified(result.verified);
      if (!result.verified) {
        setAttributeError("Refresh verified category attributes before publishing.");
        setAttributeSuggestions([]);
        return;
      }
      if (draftId) {
        const mapped = await getDraftAttributeSuggestions(draftId, requestedCategoryId);
        if (categoryAttributesEpochRef.current !== requestEpoch) return;
        setAttributeSuggestions(mapped.suggestions);
      }
    } catch (error) {
      if (categoryAttributesEpochRef.current === requestEpoch) {
        const message = error instanceof Error ? error.message : "Failed to load attributes";
        setAttributeError(readablePublishError(message));
      }
    } finally {
      if (categoryAttributesEpochRef.current === requestEpoch) setBusy("");
    }
  }

  function changeCategory(nextCategoryId: string) {
    categorySelectionEpochRef.current += 1;
    categoryPredictionEpochRef.current += 1;
    categoryAttributesEpochRef.current += 1;
    listingTypeRequestEpochRef.current += 1;
    setCategoryId(nextCategoryId);
    setCategoryAttributes([]);
    setCategoryAttributesVerified(false);
    setListingTypesVerified(false);
    setListingTypeNames({});
    setAttributeValues({});
    setAttributeValueIds({});
    setAttributeSuggestions([]);
    setAttributeError("");
    setSavedConfig(null);
    setPreview(null);
    setPreviewFingerprint("");
    setBusy((current) => (
      current === "category" || current === "attributes" ? "" : current
    ));
  }

  function applyAttributeSuggestion(suggestion: AttributeSuggestion) {
    if (!suggestion.can_apply) return;
    setAttributeValues((values) => ({
      ...values,
      [suggestion.attribute_id]: suggestion.value_name,
    }));
    setAttributeValueIds((values) => {
      const next = { ...values };
      if (suggestion.value_id) next[suggestion.attribute_id] = suggestion.value_id;
      else delete next[suggestion.attribute_id];
      return next;
    });
    setSavedConfig(null);
    setPreview(null);
  }

  function applyExactSuggestions() {
    attributeSuggestions.filter((item) => item.can_apply).forEach(applyAttributeSuggestion);
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
        available_quantity: Number(availableQuantity),
        attributes: currentAttributes,
      });
      setSavedConfig(config);
      onDraftChange(config.draft);
      setBatchDrafts((items) => items.map((item) => (
        item.id === config.draft.id ? config.draft : item
      )));
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
      await refreshPublishJobs(false);
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
      await refreshPublishJobs(false);
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
      await refreshPublishJobs(false);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to retry publish job");
    } finally {
      setBusy("");
    }
  }

  function toggleBatchDraft(draftIdToToggle: number) {
    batchPreflightEpochRef.current += 1;
    setBatchPublishAcknowledged(false);
    setSelectedBatchDraftIds((current) => {
      const next = new Set(current);
      if (next.has(draftIdToToggle)) next.delete(draftIdToToggle);
      else if (next.size < MAX_PUBLISH_BATCH_SIZE) next.add(draftIdToToggle);
      else setStatus(`A publish batch can contain at most ${MAX_PUBLISH_BATCH_SIZE} drafts.`);
      return next;
    });
    setBatchPublishResult(null);
    setBatchPreflightResult(null);
  }

  async function checkBatchReadiness() {
    const draftIds = [...selectedBatchDraftIds];
    if (draftIds.length === 0) return;
    const requestEpoch = ++batchPreflightEpochRef.current;
    setBusy("batch-preflight");
    setStatus("");
    setBatchPublishAcknowledged(false);
    setBatchPreflightResult(null);
    setBatchPublishResult(null);
    try {
      const result = await preflightPublishBatch(draftIds);
      if (batchPreflightEpochRef.current !== requestEpoch) return;
      setBatchPreflightResult(result);
      setStatus(`${result.ready_count} of ${result.items.length} selected drafts are ready`);
    } catch (error) {
      if (batchPreflightEpochRef.current !== requestEpoch) return;
      setBatchPreflightResult(null);
      setStatus(error instanceof Error ? error.message : "Failed to check publish readiness");
    } finally {
      setBusy("");
    }
  }

  async function queuePublishBatch() {
    const draftIds = [...selectedBatchDraftIds];
    if (
      !batchPublishAcknowledged
      || !batchPreflightResult
      || busy === "batch-preflight"
      || batchPreflightResult.ready_count === 0
      || batchPreflightResult.items.length !== draftIds.length
      || !batchPreflightResult.items.every((item) => selectedBatchDraftIds.has(item.draft_id))
      || draftIds.length === 0
    ) return;
    setBusy("batch-queue");
    setStatus("");
    try {
      const result = await enqueuePublishBatch(draftIds);
      setBatchPublishResult(result);
      await refreshPublishJobs(false);
      setSelectedBatchDraftIds(new Set());
      setBatchPublishAcknowledged(false);
      batchPreflightEpochRef.current += 1;
      setBatchPreflightResult(null);
      setStatus(`${result.queued_count} publish jobs queued`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to queue publish batch");
    } finally {
      setBusy("");
    }
  }

  const batchPreflightMatchesSelection = Boolean(
    batchPreflightResult
    && batchPreflightResult.items.length === selectedBatchDraftIds.size
    && batchPreflightResult.items.every((item) => selectedBatchDraftIds.has(item.draft_id)),
  );

  const batchPublishSection = (
    <section className="saved-section batch-publish-section">
      <div className="section-heading">
        <div><h3>Batch publish queue</h3></div>
        <span>{batchDrafts.length}</span>
      </div>
      {batchDrafts.length === 0 && <p>No saved drafts are available.</p>}
      {batchDrafts.length > 0 && (
        <>
          <div className="batch-review-controls">
            <div className="action-line">
              <span>{selectedBatchDraftIds.size} / {MAX_PUBLISH_BATCH_SIZE} selected</span>
              <button
                className="secondary-button"
                disabled={selectedBatchDraftIds.size === 0 || busy === "batch-preflight"}
                onClick={checkBatchReadiness}
              >
                <ListChecks size={16} /> Check readiness
              </button>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={batchPublishAcknowledged}
                  onChange={(event) => setBatchPublishAcknowledged(event.target.checked)}
                />
                Confirm ready drafts may be published by the worker
              </label>
              <button
                disabled={
                  selectedBatchDraftIds.size === 0
                  || !batchPreflightMatchesSelection
                  || batchPreflightResult?.ready_count === 0
                  || !batchPublishAcknowledged
                  || busy === "batch-preflight"
                  || busy === "batch-queue"
                }
                onClick={queuePublishBatch}
              >
                <ListPlus size={16} /> Queue selected drafts
              </button>
            </div>
            {batchPreflightResult && (
              <div className="batch-result-summary" aria-live="polite">
                <strong>{batchPreflightResult.ready_count} ready</strong>
                <span>{batchPreflightResult.not_ready_count} blocked</span>
                <span>{batchPreflightResult.not_found_count} missing</span>
              </div>
            )}
            {batchPreflightResult?.items.some((item) => item.errors.length > 0) && (
              <div className="batch-review-errors">
                {batchPreflightResult.items.filter((item) => item.errors.length > 0).map((item) => (
                  <span key={item.draft_id}>
                    Draft #{item.draft_id}: {item.errors.map(readablePublishError).join(", ")}
                  </span>
                ))}
              </div>
            )}
            {batchPublishResult && (
              <div className="batch-result-summary" aria-live="polite">
                <strong>{batchPublishResult.queued_count} queued</strong>
                <span>{batchPublishResult.existing_count} existing</span>
                <span>{batchPublishResult.not_ready_count} not ready</span>
                <span>{batchPublishResult.not_found_count} missing</span>
              </div>
            )}
            {batchPublishResult?.items.some((item) => item.errors.length > 0) && (
              <div className="batch-review-errors">
                {batchPublishResult.items.filter((item) => item.errors.length > 0).map((item) => (
                  <span key={item.draft_id}>
                    Draft #{item.draft_id}: {item.errors.map(readablePublishError).join(", ")}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="draft-list">
            {batchDrafts.map((item) => (
              <div className="draft-selection-row" key={item.id}>
                <label className="draft-selector">
                  <input
                    type="checkbox"
                    aria-label={`Select draft ${item.id} for publish queue`}
                    checked={selectedBatchDraftIds.has(item.id)}
                    disabled={
                      !selectedBatchDraftIds.has(item.id)
                      && selectedBatchDraftIds.size >= MAX_PUBLISH_BATCH_SIZE
                    }
                    onChange={() => toggleBatchDraft(item.id)}
                  />
                </label>
                <div className="batch-publish-row">
                  <span>
                    <strong>{item.title}</strong>
                    <small>#{item.id} · {item.target_site_id} · {item.listing_type_id || "offer not configured"}</small>
                  </span>
                  <span>{item.currency} {item.price ?? "not priced"}</span>
                  <span>{item.risk_status}</span>
                  {batchPreflightResult && (() => {
                    const checked = batchPreflightResult.items.find((result) => result.draft_id === item.id);
                    if (!checked) return null;
                    return (
                      <span className={`state-pill ${checked.outcome === "ready" ? "ready" : "blocked"}`}>
                        {checked.outcome === "ready" ? "Ready" : "Blocked"}
                      </span>
                    );
                  })()}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
  const publishJobsSection = (
    <PublishJobHistory
      jobs={jobs}
      refreshing={jobsRefreshing}
      busy={busy}
      onRefresh={() => void refreshPublishJobs(true)}
      onRetry={(jobId) => void retryJob(jobId)}
    />
  );

  if (!draft || !draftId) {
    return (
      <section className="workspace">
        <div className="empty-state">Select and prepare a saved draft before publishing.</div>
        {status && <p className="status-line">{status}</p>}
        {batchPublishSection}
        {publishJobsSection}
      </section>
    );
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
      && savedConfig.available_quantity === Number(availableQuantity)
      && categoryAttributesVerified
      && JSON.stringify(normalizedSavedAttributes) === JSON.stringify(currentAttributes)
      && missingRequiredAttributes.length === 0
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
              categoryAttributesEpochRef.current += 1;
              listingTypeRequestEpochRef.current += 1;
              setStoreId(event.target.value);
              setShippingOptions([]);
              setShippingStatus(event.target.value ? "Loading verified non-FULL shipping options..." : "");
              setListingTypes([]);
              setListingTypesVerified(false);
              setListingTypeNames({});
              setListingTypeId("");
              setSavedConfig(null);
              setPreview(null);
              setSelectedShippingKey("");
            }}>
              <option value="">Select a connected {siteId} store</option>
              {siteStores.map((store) => <option key={store.id} value={store.id}>{store.display_name} · seller {store.seller_id}</option>)}
            </select>
          </label>
          <label>Available quantity
            <input
              type="number"
              min="1"
              step="1"
              value={availableQuantity}
              aria-invalid={!Number.isInteger(Number(availableQuantity)) || Number(availableQuantity) < 1}
              onChange={(event) => {
                setAvailableQuantity(event.target.value);
                setSavedConfig(null);
                setPreview(null);
              }}
            />
          </label>
        </div>
        {!siteMatchesDraft && <p className="inline-warning">This draft was prepared for {draft.target_site_id}. Return to Import, select {siteId}, then reprice and rerun the AI review before publishing.</p>}
        {siteMatchesDraft && !draft.price && <p className="inline-warning">This draft has no target selling price. Calculate and save a price in {expectedCurrency} before publishing to {siteId}.</p>}
        {siteMatchesDraft && Boolean(draft.price) && draft.currency !== expectedCurrency && <p className="inline-warning">This draft is priced in {draft.currency || "no currency"}. Reprice it in {expectedCurrency} before publishing to {siteId}.</p>}
        {siteStores.length === 0 && <p className="inline-warning">No connected store is authorized for {siteId}.</p>}
        <div className="listing-choice" role="group" aria-label="Listing type">
          {commercialTypes.map((type) => (
            <button key={type.id} className={listingTypeId === type.id ? "selected" : ""} disabled={!type.available} onClick={() => { setListingTypeId(type.id); setSavedConfig(null); setPreview(null); }}>
              <strong>{type.label}</strong><span>{type.available ? "Available for this seller and category" : "Unavailable for this seller and category"}</span>
            </button>
          ))}
        </div>
        {!listingTypesVerified && <p className="inline-warning">Load category attributes to verify Classic/Premium eligibility for this authorized seller and category.</p>}
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
        {attributeSuggestions.length > 0 && (
          <div className="attribute-mapping">
            <div className="attribute-mapping-heading">
              <span>
                <strong>Amazon variant {draft.source_variant_asin || "source"}</strong>
                <small>{attributeSuggestions.length} category matches</small>
              </span>
              <button
                className="secondary-button"
                disabled={!attributeSuggestions.some((item) => item.can_apply)}
                onClick={applyExactSuggestions}
              >
                <Sparkles size={16} /> Apply exact matches
              </button>
            </div>
            <div className="attribute-suggestion-list">
              {attributeSuggestions.map((suggestion) => (
                <div className="attribute-suggestion" key={`${suggestion.source_name}-${suggestion.attribute_id}`}>
                  <span><small>{suggestion.source_name}</small><strong>{suggestion.source_value}</strong></span>
                  <ArrowRight size={15} />
                  <span>
                    <small>{suggestion.attribute_id}{suggestion.variation_attribute ? " · variation" : ""}</small>
                    <strong>{suggestion.attribute_name}</strong>
                  </span>
                  {suggestion.can_apply ? (
                    <button
                      className="icon-text-button"
                      onClick={() => applyAttributeSuggestion(suggestion)}
                    >
                      <Sparkles size={14} /> Apply
                    </button>
                  ) : (
                    <span className="state-pill blocked">Manual entry</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        {visibleAttributes.length > 0 && <div className="form-grid two-col attribute-grid">{visibleAttributes.map((attribute) => {
          const id = String(attribute.id ?? "");
          const values = Array.isArray(attribute.values)
            ? attribute.values.filter((value): value is Record<string, unknown> => Boolean(value && typeof value === "object"))
            : [];
          const tags = attribute.tags as Record<string, unknown> | undefined;
          const listId = `attribute-values-${id}`;
          return (
            <label key={id}>
              {String(attribute.name ?? id)}{id === "ITEM_CONDITION" || tags?.required || tags?.catalog_required ? " *" : ""}
              {id === "ITEM_CONDITION" && values.length > 0 ? (
                <select
                  aria-invalid={!attributeValues[id]?.trim()}
                  value={attributeValueIds[id] ?? ""}
                  onChange={(event) => {
                    const exact = values.find((value) => String(value.id ?? "") === event.target.value);
                    setAttributeValues((current) => ({ ...current, [id]: String(exact?.name ?? "") }));
                    setAttributeValueIds((current) => ({ ...current, [id]: event.target.value }));
                    setSavedConfig(null);
                    setPreview(null);
                  }}
                >
                  <option value="">Select item condition</option>
                  {values.map((value) => (
                    <option key={String(value.id)} value={String(value.id)}>{String(value.name ?? "")}</option>
                  ))}
                </select>
              ) : (
                <input
                  list={values.length ? listId : undefined}
                  aria-invalid={Boolean((tags?.required || tags?.catalog_required) && !attributeValues[id]?.trim())}
                  value={attributeValues[id] ?? ""}
                  onChange={(event) => {
                    const valueName = event.target.value;
                    const exactMatches = values.filter(
                      (value) => String(value.name ?? "").toLocaleLowerCase() === valueName.toLocaleLowerCase(),
                    );
                    const exact = exactMatches.length === 1 ? exactMatches[0] : undefined;
                    setAttributeValues((current) => ({ ...current, [id]: valueName }));
                    setAttributeValueIds((current) => {
                      const next = { ...current };
                      if (exact?.id) next[id] = String(exact.id);
                      else delete next[id];
                      return next;
                    });
                    setSavedConfig(null);
                    setPreview(null);
                  }}
                />
              )}
              {id !== "ITEM_CONDITION" && values.length > 0 && (
                <datalist id={listId}>
                  {values.map((value) => (
                    <option key={String(value.id ?? value.name)} value={String(value.name ?? "")} />
                  ))}
                </datalist>
              )}
            </label>
          );
        })}</div>}
        {attributeError && <p className="inline-warning" role="alert">{attributeError}</p>}
        {categoryId && !categoryAttributesVerified && !attributeError && (
          <p className="inline-warning">Load verified category attributes before saving.</p>
        )}
        {missingRequiredAttributes.length > 0 && (
          <p className="inline-warning">
            {missingRequiredAttributes.length} required attribute{missingRequiredAttributes.length === 1 ? "" : "s"} remaining
          </p>
        )}
        {categoryAttributes.length > 0 && <div className="action-line"><span>{requiredAttributes.length} required · {categoryAttributes.length} total attributes loaded</span><button className="secondary-button" onClick={() => loadAttributes(true)}><RefreshCw size={16} /> Refresh metadata</button></div>}
        <div className="action-line"><button onClick={saveConfig} disabled={!categoryId || !categoryAttributesVerified || !listingTypesVerified || !listingTypeId || !selectedShipping || !pricingValid || !Number.isInteger(Number(availableQuantity)) || Number(availableQuantity) < 1 || missingRequiredAttributes.length > 0 || busy === "config"}><Save size={16} /> Save listing configuration</button>{savedConfig && <span className="success-text"><CheckCircle2 size={16} /> Saved as non-FULL</span>}</div>
      </section>

      <section className="surface publish-section">
        <div className="section-heading"><div><span className="step-number">3</span><h3>Approval and publish</h3></div></div>
        <div className="release-summary">
          <div><span>AI decision</span><strong>{String(review?.decision ?? "Not reviewed")}</strong></div>
          <div><span>Store</span><strong>{selectedStore?.display_name ?? "Not selected"}</strong></div>
          <div><span>Offer</span><strong>{COMMERCIAL_TYPES.find((type) => type.id === listingTypeId)?.label ?? "Not selected"}</strong></div>
          <div><span>Shipping</span><strong>{selectedShipping ? (SHIPPING_LABELS[selectedShippingKey] ?? selectedShippingKey) : "Not selected"}</strong></div>
          <div><span>Price</span><strong>{draft.price ? `${draft.currency} ${draft.price}` : "Not priced"}</strong></div>
          <div><span>Inventory</span><strong>{availableQuantity || "Not confirmed"}</strong></div>
        </div>
        <div className="button-row">
          <button disabled={!canApprove || busy === "approval"} onClick={approveCurrentDraft}><CheckCircle2 size={16} /> Record human approval</button>
          <button className="secondary-button" disabled={!canPreview || busy === "preview"} onClick={createPreview}><ListChecks size={16} /> Validate payload</button>
          <button disabled={!previewMatchesCurrentConfig || !selectedStore || !readiness?.mercado_libre.live_publish_enabled || busy === "execute" || busy === "config"} onClick={executePublish}><Rocket size={16} /> Publish now</button>
          <button className="secondary-button" disabled={!previewMatchesCurrentConfig || !selectedStore || busy === "queue" || busy === "config"} onClick={queuePublish}><Rocket size={16} /> Add to queue</button>
        </div>
        {!readiness?.mercado_libre.live_publish_enabled && <p className="inline-warning">Live publishing is disabled in server configuration.</p>}
        {preview && <div className={`validation-result ${preview.allowed ? "ready" : "blocked"}`}><strong>{preview.allowed ? "Payload is ready" : "Payload is blocked"}</strong>{preview.errors.map((item) => <span key={item}>{readablePublishError(item)}</span>)}</div>}
        {execution && <div className={`validation-result ${execution.status === "published" ? "ready" : "blocked"}`}><strong>{execution.status}</strong>{execution.item_id && <span>{execution.item_id}</span>}{execution.shipping_mode && <span>Shipping: {execution.shipping_mode}{execution.shipping_logistic_type ? ` · ${execution.shipping_logistic_type}` : ""}</span>}{execution.errors.map((item) => <span key={item}>{readablePublishError(item)}</span>)}</div>}
      </section>

      {status && <p className="status-line">{status}</p>}
      {batchPublishSection}
      {publishJobsSection}
    </section>
  );
}

function PublishJobHistory({
  jobs,
  refreshing,
  busy,
  onRefresh,
  onRetry,
}: {
  jobs: PublishJobRecord[];
  refreshing: boolean;
  busy: string;
  onRefresh: () => void;
  onRetry: (jobId: number) => void;
}) {
  return (
    <section className="saved-section">
      <div className="section-heading publish-job-heading">
        <div><h3>Publish jobs</h3></div>
        <div className="section-heading-actions">
          <span>{jobs.length}</span>
          <button className="icon-button" title="Refresh publish jobs" disabled={refreshing} onClick={onRefresh}>
            <RefreshCw className={refreshing ? "spin" : ""} size={17} />
          </button>
        </div>
      </div>
      {jobs.length === 0 ? <p>No publish jobs yet.</p> : (
        <div className="job-list">
          {jobs.map((job) => {
            const canRetry = (job.status === "blocked" || job.status === "failed")
              && !job.errors.includes("publish_outcome_unknown_manual_reconciliation_required");
            const stateClass = job.status === "published"
              ? "ready"
              : job.status === "blocked" || job.status === "failed" ? "blocked" : "";
            return (
              <div className="job-row" key={job.id}>
                <span className="job-details">
                  <strong>#{job.id} · draft #{job.product_draft_id}</strong>
                  <small>Store #{job.store_id}{job.shipping_mode ? ` · ${job.shipping_mode}` : ""}{job.shipping_logistic_type ? `/${job.shipping_logistic_type}` : ""}</small>
                  <small>Queued {formatJobTime(job.created_at)}</small>
                  {job.started_at && <small>Started {formatJobTime(job.started_at)}</small>}
                  {job.completed_at && <small>Completed {formatJobTime(job.completed_at)}</small>}
                  {job.item_id && <small>Item {job.item_id}</small>}
                  {job.errors.length > 0 && <small className="error">{job.errors.map(readablePublishError).join(", ")}</small>}
                </span>
                <span className={`state-pill ${stateClass}`}>{job.status}</span>
                <span className="job-actions">
                  {job.permalink && <a className="icon-text-button" href={job.permalink} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open listing</a>}
                  <button className="secondary-button" disabled={!canRetry || Boolean(job.item_id) || busy === `retry-${job.id}`} onClick={() => onRetry(job.id)}><RefreshCw size={16} /> Retry</button>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function formatJobTime(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function ProgressItem({ label, ready }: { label: string; ready: boolean }) {
  return <div className={ready ? "ready" : "pending"}><span>{ready ? <CheckCircle2 size={16} /> : null}</span><strong>{label}</strong></div>;
}
