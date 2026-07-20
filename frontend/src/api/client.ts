const API_BASE = "http://127.0.0.1:8000";

export type ProductDraft = {
  title: string;
  description: string;
  brand: string;
  target_site_id: string;
  target_category_id: string;
  condition: string;
  source_price: number | null;
  source_currency: string;
  price: number | null;
  currency: string;
  stock: number;
  listing_type_id: string;
  image_urls: string[];
  source_product_id?: number | null;
  source_variant_asin?: string;
  source_variant_attributes?: Record<string, string>;
};

export type ProductDraftRead = ProductDraft & {
  id: number;
  source_product_id: number | null;
  source_variant_asin: string;
  source_variant_attributes: Record<string, string>;
  status: string;
  risk_status: string;
};

export type PersistedDraftResponse = {
  id: number | null;
  draft: ProductDraft;
};

export type ReviewResult = {
  id: number;
  product_draft_id: number;
  provider: string;
  model: string;
  prompt_version: string;
  duration_ms: number;
  provider_status: string;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  provider_request_id: string;
  decision: string;
  risk_level: string;
  reason_codes: string[];
  reasons: string[];
  suggested_changes: Record<string, unknown>;
  created_at: string;
};

export class ProviderRequestError extends Error {
  provider: string;
  code: string;
  retryable: boolean;
  retryAfterSeconds: number | null;
  requestId: string;
  providerHttpStatus: number | null;

  constructor(detail: Record<string, unknown>) {
    const provider = String(detail.provider ?? "AI provider");
    const code = String(detail.code ?? "request_failed");
    const retryAfter = typeof detail.retry_after_seconds === "number"
      ? detail.retry_after_seconds
      : null;
    const requestId = typeof detail.request_id === "string" ? detail.request_id : "";
    const providerHttpStatus = typeof detail.provider_http_status === "number"
      ? detail.provider_http_status
      : null;
    const retryMessage = retryAfter !== null
      ? ` Wait ${retryAfter} seconds, then retry manually.`
      : detail.retryable ? " Retry manually when the provider is available." : "";
    const requestMessage = requestId ? ` Request ${requestId}.` : "";
    const statusMessage = providerHttpStatus !== null
      ? ` Provider HTTP ${providerHttpStatus}.`
      : "";
    super(`${provider}: ${readableProviderError(code)}.${statusMessage}${retryMessage}${requestMessage} No automatic retry was sent.`);
    this.name = "ProviderRequestError";
    this.provider = provider;
    this.code = code;
    this.retryable = detail.retryable === true;
    this.retryAfterSeconds = retryAfter;
    this.requestId = requestId;
    this.providerHttpStatus = providerHttpStatus;
  }
}

export type BehavioralAudit = {
  nvidia: Record<string, unknown>;
  claude: Record<string, unknown>;
  aggregate: Record<string, unknown>;
};

export type StoreRecord = {
  id: string;
  site_id: string;
  seller_id: string;
  display_name: string;
  oauth_status: string;
};

export type IntegrationCredentialStatus = {
  meli_client_id_configured: boolean;
  meli_client_secret_configured: boolean;
  claude_api_key_configured: boolean;
  nvidia_api_key_configured: boolean;
  claude_model: string;
  nvidia_model: string;
  meli_redirect_uri: string;
};

export type IntegrationCredentialsUpdate = Partial<{
  meli_client_id: string;
  meli_client_secret: string;
  claude_api_key: string;
  nvidia_api_key: string;
}>;

export type PublishJobRecord = {
  id: number;
  product_draft_id: number;
  store_id: number;
  status: string;
  item_id: string;
  permalink: string;
  shipping_mode: string;
  shipping_logistic_type: string;
  errors: string[];
};

export type DraftListingConfig = {
  id: number;
  product_draft_id: number;
  site_id: string;
  store_id: number | null;
  category_id: string;
  listing_type_id: string;
  fulfillment: string;
  shipping_mode: string;
  shipping_logistic_type: string;
  attributes: { id: string; value_name: string; value_id?: string | null }[];
  created_at: string;
  updated_at: string;
};

export type AttributeSuggestion = {
  source_name: string;
  source_value: string;
  attribute_id: string;
  attribute_name: string;
  value_name: string;
  value_id: string | null;
  confidence: number;
  match_reason: string;
  required: boolean;
  variation_attribute: boolean;
  can_apply: boolean;
};

export type AttributeSuggestionResult = {
  product_draft_id: number;
  category_id: string;
  source_variant_asin: string;
  listing_strategy: string;
  suggestions: AttributeSuggestion[];
  unmatched_source_attributes: Record<string, string>;
};

export type ShippingOption = {
  mode: string;
  logistic_type: string;
};

export type DraftApproval = {
  id: number;
  product_draft_id: number;
  status: string;
  approved_by: string;
  note: string;
  approved_at: string;
};

export type PublishValidationResult = {
  allowed: boolean;
  errors: string[];
};

export type PublishExecutionResult = {
  status: string;
  item_id: string;
  permalink: string;
  shipping_mode: string;
  shipping_logistic_type: string;
  errors: string[];
  job_id: number | null;
};

export type AuditEventRecord = {
  id: number;
  actor_type: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  created_at: string;
};

export type SystemReadiness = {
  database: boolean;
  amazon_collector: boolean;
  mercado_libre: {
    credentials_configured: boolean;
    connected_stores: number;
    live_publish_enabled: boolean;
  };
  ai: {
    claude_configured: boolean;
    nvidia_configured: boolean;
  };
  counts: {
    drafts: number;
    collection_jobs: number;
    publish_jobs: number;
  };
};

export type DraftPricingInput = {
  source_price: number;
  source_currency: string;
  target_currency: string;
  exchange_rate: number;
  purchase_extra_cost: number;
  shipping_cost: number;
  platform_fee_rate: number;
  tax_rate: number;
  profit_margin_rate: number;
  rounding_increment: number;
};

export type DraftPricing = DraftPricingInput & {
  id: number;
  product_draft_id: number;
  landed_cost: number;
  target_price: number;
  created_at: string;
  updated_at: string;
};

export async function importAmazonHtml(
  sourceUrl: string,
  html: string,
  targetSiteId: string,
  persist = false,
) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-html`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, html, target_site_id: targetSiteId, persist }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraft | PersistedDraftResponse>;
}

export type CollectionResult = {
  status: "collected" | "needs_manual_action" | "failed";
  source_url: string;
  message: string;
  draft: ProductDraft | null;
  draft_id: number | null;
};

export type CollectionJobRecord = {
  id: number;
  source_url: string;
  target_site_id: string;
  status: "pending" | "running" | "completed" | "needs_manual_action" | "failed";
  message: string;
  source_product_id: number | null;
  draft_id: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  source_product: SourceProductSummary | null;
};

export type AmazonSourceVariant = {
  asin: string;
  attributes: Record<string, string>;
  image_urls: string[];
  selected: boolean;
};

export type SourceProductRecord = {
  id: number;
  source: string;
  source_url: string;
  asin: string;
  status: string;
  collection_method: string;
  collected_at: string | null;
  collection_error: string;
  snapshot: {
    source_url: string;
    title: string;
    price: { amount: number | null; currency: string };
    brand: string;
    bullets: string[];
    description: string;
    images: string[];
    variants: AmazonSourceVariant[];
    technical_details: Record<string, string>;
    measurements: {
      item_weight?: { value: number; unit: string; raw: string; source_label: string } | null;
      package_weight?: { value: number; unit: string; raw: string; source_label: string } | null;
      product_dimensions?: {
        length: number; width: number; height: number; unit: string; raw: string; source_label: string;
      } | null;
      package_dimensions?: {
        length: number; width: number; height: number; unit: string; raw: string; source_label: string;
      } | null;
    };
  } | null;
};

export type SourceProductSummary = {
  id: number;
  asin: string;
  status: string;
  collection_method: string;
  title: string;
  brand: string;
  source_price: number | null;
  source_currency: string;
  primary_image_url: string;
  image_count: number;
  variant_count: number;
  has_snapshot: boolean;
  collection_error: string;
};

export type CollectionBatchItem = {
  input_url: string;
  normalized_url: string;
  outcome: "created" | "duplicate_input" | "existing" | "invalid";
  detail: string;
  job: CollectionJobRecord | null;
};

export type CollectionBatchResult = {
  created_count: number;
  duplicate_count: number;
  existing_count: number;
  invalid_count: number;
  items: CollectionBatchItem[];
};

export async function importAmazonUrl(sourceUrl: string, targetSiteId: string) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, target_site_id: targetSiteId, persist: true }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionResult>;
}

export async function getSystemReadiness() {
  const response = await fetch(`${API_BASE}/api/system/readiness`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<SystemReadiness>;
}

export async function saveDraftPricing(productDraftId: number, payload: DraftPricingInput) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/pricing`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftPricing>;
}

export async function getDraftPricing(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/pricing?optional=true`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftPricing | null>;
}

export async function createCollectionJob(sourceUrl: string, targetSiteId: string) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, target_site_id: targetSiteId }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionJobRecord>;
}

export async function createCollectionJobsBatch(
  sourceUrls: string[],
  targetSiteId: string,
  allowExisting: boolean,
) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_urls: sourceUrls,
      target_site_id: targetSiteId,
      allow_existing: allowExisting,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionBatchResult>;
}

export async function listCollectionJobs(limit = 100, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs?${params}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionJobRecord[]>;
}

export async function listCollectionJobStatuses(jobIds: number[]) {
  const uniqueIds = [...new Set(jobIds)];
  const chunks = Array.from(
    { length: Math.ceil(uniqueIds.length / 200) },
    (_, index) => uniqueIds.slice(index * 200, (index + 1) * 200),
  );
  const pages = await Promise.all(chunks.map(async (chunk) => {
    const params = new URLSearchParams();
    chunk.forEach((jobId) => params.append("job_ids", String(jobId)));
    const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs/status?${params}`);
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<CollectionJobRecord[]>;
  }));
  return pages.flat();
}

export async function getSourceProduct(sourceProductId: number) {
  const response = await fetch(`${API_BASE}/api/imports/source-products/${sourceProductId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<SourceProductRecord>;
}

export async function createSourceVariantDraft(
  sourceProductId: number,
  variantAsin: string,
  targetSiteId: string,
) {
  const response = await fetch(
    `${API_BASE}/api/imports/source-products/${sourceProductId}/variants/${variantAsin}/draft`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_site_id: targetSiteId }),
    },
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraftRead>;
}

export async function createSourceVariantCollectionJob(
  sourceProductId: number,
  variantAsin: string,
  targetSiteId: string,
) {
  const response = await fetch(
    `${API_BASE}/api/imports/source-products/${sourceProductId}/variants/${variantAsin}/collection-job`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_site_id: targetSiteId }),
    },
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionJobRecord>;
}

export type SourceVariantCollectionBatchResult = {
  created_count: number;
  reused_count: number;
  skipped_selected_count: number;
  jobs: CollectionJobRecord[];
};

export async function createSourceVariantCollectionJobs(
  sourceProductId: number,
  targetSiteId: string,
) {
  const response = await fetch(
    `${API_BASE}/api/imports/source-products/${sourceProductId}/variants/collection-jobs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_site_id: targetSiteId }),
    },
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<SourceVariantCollectionBatchResult>;
}

export async function runCollectionJob(jobId: number) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs/${jobId}/run`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionJobRecord>;
}

export async function reviewDraft(draft: ProductDraft, productDraftId?: number | null) {
  const url = reviewUrl("local", productDraftId);
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function reviewDraftWithProvider(
  draft: ProductDraft,
  provider: "claude" | "nvidia",
  productDraftId?: number | null,
) {
  const response = await fetch(reviewUrl(provider, productDraftId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!response.ok) await throwProviderError(response);
  return response.json();
}

export async function reviewDraftWithBehavioralAudit(
  draft: ProductDraft,
  productDraftId?: number | null,
) {
  const url = `${API_BASE}/api/reviews/behavioral-audit${
    productDraftId ? `?product_draft_id=${productDraftId}` : ""
  }`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!response.ok) await throwProviderError(response);
  return response.json() as Promise<BehavioralAudit>;
}

export async function getMeliAuthorizationUrl() {
  const response = await fetch(`${API_BASE}/api/stores/meli/authorization-url`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ authorization_url: string }>;
}

export async function getIntegrationCredentialStatus() {
  const response = await fetch(`${API_BASE}/api/integrations/credentials`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<IntegrationCredentialStatus>;
}

export async function saveIntegrationCredentials(payload: IntegrationCredentialsUpdate) {
  const response = await fetch(`${API_BASE}/api/integrations/credentials`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<IntegrationCredentialStatus>;
}

export async function listDrafts() {
  const response = await fetch(`${API_BASE}/api/drafts`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraftRead[]>;
}

export async function listReviewHistory(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/reviews/drafts/${productDraftId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ReviewResult[]>;
}

export async function listStores() {
  const response = await fetch(`${API_BASE}/api/stores`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<StoreRecord[]>;
}

export async function getStoreShippingOptions(storeId: number) {
  const response = await fetch(`${API_BASE}/api/stores/${storeId}/shipping-options`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    store_id: number;
    site_id: string;
    verified: boolean;
    options: ShippingOption[];
  }>;
}

export async function getListingTypes(siteId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/sites/${siteId}/listing-types`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    listing_type_ids: string[];
    source: "mercado_libre_api" | "cache" | "standard_catalog";
    verified: boolean;
  }>;
}

export async function refreshListingTypes(siteId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/sites/${siteId}/listing-types/refresh`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    listing_type_ids: string[];
    source: "mercado_libre_api" | "cache" | "standard_catalog";
    verified: boolean;
  }>;
}

export async function getCategoryPredictions(siteId: string, query: string) {
  const response = await fetch(
    `${API_BASE}/api/metadata/sites/${siteId}/category-predictions?q=${encodeURIComponent(query)}`,
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ predictions: Record<string, unknown>[] }>;
}

export async function getCategoryAttributes(categoryId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/categories/${categoryId}/attributes`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    attributes: Record<string, unknown>[];
    verified: boolean;
  }>;
}

export async function getDraftAttributeSuggestions(productDraftId: number, categoryId: string) {
  const params = new URLSearchParams({ category_id: categoryId });
  const response = await fetch(
    `${API_BASE}/api/drafts/${productDraftId}/attribute-suggestions?${params}`,
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<AttributeSuggestionResult>;
}

export async function refreshCategoryAttributes(categoryId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/categories/${categoryId}/attributes/refresh`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    attributes: Record<string, unknown>[];
    verified: boolean;
  }>;
}

export async function listPublishJobs() {
  const response = await fetch(`${API_BASE}/api/publishing/jobs`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishJobRecord[]>;
}

export async function retryPublishJob(jobId: number) {
  const response = await fetch(`${API_BASE}/api/publishing/jobs/${jobId}/retry`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishExecutionResult>;
}

export async function saveDraftListingConfig(
  productDraftId: number,
  payload: {
    site_id: string;
    store_id: number;
    category_id: string;
    listing_type_id: string;
    fulfillment: string;
    shipping_mode: string;
    shipping_logistic_type: string;
    attributes: { id: string; value_name: string; value_id?: string | null }[];
  },
) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/listing-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftListingConfig>;
}

export async function getDraftListingConfig(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/listing-config?optional=true`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftListingConfig | null>;
}

export async function approveDraft(productDraftId: number, approvedBy = "operator", note = "") {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/approval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: approvedBy, note }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftApproval>;
}

export async function previewPublishFromDraft(
  productDraftId: number,
  review: Record<string, unknown>,
  validListingTypeIds: string[],
  humanApproved: boolean,
) {
  const response = await fetch(`${API_BASE}/api/publishing/preview-from-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_draft_id: productDraftId,
      review,
      valid_listing_type_ids: validListingTypeIds,
      human_approved: humanApproved,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishValidationResult>;
}

export async function executePublishFromDraft(
  productDraftId: number,
  storeId: number,
  review: Record<string, unknown>,
  validListingTypeIds: string[],
  humanApproved: boolean,
) {
  const response = await fetch(`${API_BASE}/api/publishing/execute-from-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_draft_id: productDraftId,
      store_id: storeId,
      review,
      valid_listing_type_ids: validListingTypeIds,
      human_approved: humanApproved,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishExecutionResult>;
}

export async function enqueuePublishFromDraft(
  productDraftId: number,
  storeId: number,
  review: Record<string, unknown>,
  validListingTypeIds: string[],
  humanApproved: boolean,
) {
  const response = await fetch(`${API_BASE}/api/publishing/enqueue-from-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_draft_id: productDraftId,
      store_id: storeId,
      review,
      valid_listing_type_ids: validListingTypeIds,
      human_approved: humanApproved,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishJobRecord>;
}

export async function listAuditEvents(limit = 100) {
  const response = await fetch(`${API_BASE}/api/audit-events?limit=${limit}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<AuditEventRecord[]>;
}

function reviewUrl(provider: "local" | "claude" | "nvidia", productDraftId?: number | null) {
  const query = productDraftId ? `?product_draft_id=${productDraftId}` : "";
  return `${API_BASE}/api/reviews/${provider}${query}`;
}

async function throwProviderError(response: Response): Promise<never> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`AI provider request failed with HTTP ${response.status}.`);
  }
  if (
    payload
    && typeof payload === "object"
    && "detail" in payload
    && payload.detail
    && typeof payload.detail === "object"
  ) {
    throw new ProviderRequestError(payload.detail as Record<string, unknown>);
  }
  throw new Error(`AI provider request failed with HTTP ${response.status}.`);
}

function readableProviderError(code: string) {
  const messages: Record<string, string> = {
    api_key_required: "API key is not configured",
    authentication_failed: "API key was rejected",
    billing_required: "billing or credits require attention",
    invalid_response: "provider returned an invalid review response",
    permission_denied: "API key lacks permission",
    provider_unavailable: "provider is temporarily unavailable",
    provider_unreachable: "provider could not be reached",
    rate_limited: "rate limit reached",
    request_rejected: "request was rejected",
  };
  return messages[code] ?? "request failed";
}
