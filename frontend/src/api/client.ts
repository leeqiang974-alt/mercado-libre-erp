// Production uses the same-origin reverse proxy; Vite proxies /api locally.
const API_BASE = "";

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
  video_urls?: string[];
  source_product_id?: number | null;
  source_variant_asin?: string;
  source_variant_attributes?: Record<string, string>;
  content_version?: number;
};

export type ProductDraftRead = ProductDraft & {
  id: number;
  source_product_id: number | null;
  source_variant_asin: string;
  source_variant_attributes: Record<string, string>;
  status: string;
  risk_status: string;
  content_version: number;
};

export type DraftContentUpdate = {
  expected_content_version: number;
  title: string;
  description: string;
  brand: string;
  image_urls: string[];
  video_urls: string[];
};

export type DraftCategoryResult = {
  draft: ProductDraftRead;
  category_id: string;
  attributes_verified: boolean;
  attributes: Record<string, unknown>[];
};

export type GeneratedDraftContent = {
  draft: ProductDraftRead;
  title: string;
  description: string;
  brand: string;
  validation: {
    title_length: number;
    title_valid: boolean;
    description_valid: boolean;
    warranty_included: boolean;
  };
  model: string;
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
  price_config_id: number | null;
  estimated_cost_amount: number | string | null;
  estimated_cost_currency: string;
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

export type ReviewJob = {
  id: number;
  batch_id: string;
  product_draft_id: number;
  draft_version: number;
  status: "pending" | "running" | "completed" | "blocked" | "failed";
  aggregate_review_result_id: number | null;
  error_code: string;
  error_detail: Record<string, unknown>;
  created_at: string;
  next_attempt_at: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type ReviewJobBatchResult = {
  batch_id: string;
  queued_count: number;
  existing_count: number;
  not_ready_count: number;
  not_found_count: number;
  items: {
    draft_id: number;
    outcome: "queued" | "existing" | "not_ready" | "not_found";
    errors: string[];
    job: ReviewJob | null;
  }[];
};

export type StoreRecord = {
  id: string;
  site_id: string;
  seller_id: string;
  display_name: string;
  oauth_status: string;
};

export type CbtMarketplace = {
  site_id: string;
  seller_id: string;
  logistic_type: string;
  user_product: boolean;
  listing_count: number | null;
  listing_limit: number | null;
  available: boolean;
};

export type CbtPublishingProfile = {
  store_id: number;
  seller_id: string;
  site_id: "CBT";
  model: "traditional_global" | "user_products";
  tags: string[];
  marketplaces: CbtMarketplace[];
};

export type CbtListingConfig = {
  id: number;
  product_draft_id: number;
  store_id: number;
  category_id: string;
  family_name: string;
  global_title: string;
  description: string;
  price_usd: number;
  available_quantity: number;
  attributes: { id: string; value_name: string; value_id?: string | null }[];
  sale_terms: { id: string; value_name: string }[];
  sites_to_sell: {
    site_id: string;
    title: string;
    listing_type_id: "gold_special" | "gold_pro";
    logistic_type: "remote";
    picture_urls: string[];
  }[];
  draft_content_version: number;
  draft: ProductDraftRead;
  created_at: string;
  updated_at: string;
};

export type IntegrationCredentialStatus = {
  meli_client_id_configured: boolean;
  meli_client_secret_configured: boolean;
  claude_api_key_configured: boolean;
  nvidia_api_key_configured: boolean;
  volcengine_api_key_configured: boolean;
  claude_model: string;
  nvidia_model: string;
  volcengine_model: string;
  meli_redirect_uri: string;
};

export type IntegrationCredentialsUpdate = Partial<{
  meli_client_id: string;
  meli_client_secret: string;
  claude_api_key: string;
  nvidia_api_key: string;
  volcengine_api_key: string;
}>;

export type IntegrationDiagnosticResult = {
  provider: "mercado_libre" | "claude" | "nvidia";
  subject: string;
  status: "not_configured" | "configured" | "authorization_required" | "verified" | "authentication_failed" | "permission_denied" | "payment_required" | "request_rejected" | "rate_limited" | "model_unavailable" | "unreachable" | "invalid_response";
  code: string;
  model: string;
  store_id: number | null;
  duration_ms: number;
};

export type IntegrationDiagnostics = {
  checked_at: string;
  results: IntegrationDiagnosticResult[];
};

export type ProviderModelPrice = {
  id: number;
  provider: "claude" | "nvidia";
  model: string;
  version: number;
  currency: string;
  input_price_per_million: number | string;
  output_price_per_million: number | string;
  active: boolean;
  created_at: string;
};

export type ProviderModelPriceCreate = {
  provider: "claude" | "nvidia";
  model: string;
  currency: string;
  input_price_per_million: string;
  output_price_per_million: string;
};

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
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type PublishBatchEnqueueResult = {
  batch_id: string;
  queued_count: number;
  existing_count: number;
  not_ready_count: number;
  not_found_count: number;
  items: {
    draft_id: number;
    outcome: "queued" | "existing" | "not_ready" | "not_found";
    errors: string[];
    job: PublishJobRecord | null;
  }[];
};

export type PublishBatchPreflightResult = {
  ready_count: number;
  not_ready_count: number;
  not_found_count: number;
  items: {
    draft_id: number;
    outcome: "ready" | "not_ready" | "not_found";
    errors: string[];
  }[];
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
  available_quantity: number | null;
  attributes: { id: string; value_name: string; value_id?: string | null }[];
  draft_content_version: number;
  draft: ProductDraftRead;
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
  response_details?: Record<string, unknown>;
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
    volcengine_configured: boolean;
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
  cost_currency: string;
  purchase_cost: number;
  domestic_shipping_cost: number;
  exchange_rate: number;
  profit_margin_rate: number;
  rounding_increment: number;
};

export type DraftPricing = DraftPricingInput & {
  id: number;
  product_draft_id: number;
  landed_cost: number;
  target_price: number;
  draft_content_version: number;
  draft: ProductDraftRead;
  created_at: string;
  updated_at: string;
};

export async function importAmazonHtml(
  sourceUrl: string,
  html: string,
  targetSiteId: string,
  persist = false,
  collectionJobId: number | null = null,
) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-html`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_url: sourceUrl,
      html,
      target_site_id: targetSiteId,
      persist,
      collection_job_id: collectionJobId,
    }),
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
  next_attempt_at: string | null;
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
  if (!response.ok) {
    const retryAfter = response.headers.get("Retry-After");
    if (response.status === 429 && retryAfter) {
      throw new Error(`Amazon collection paused. Retry in ${retryAfter} seconds.`);
    }
    throw new Error(await response.text());
  }
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
export const EMPTY_PRICING: DraftPricingInput = {
  source_price: 0,
  source_currency: "CNY",
  target_currency: "MXN",
  cost_currency: "CNY",
  purchase_cost: 0,
  domestic_shipping_cost: 0,
  exchange_rate: 1,
  profit_margin_rate: 0.3,
  rounding_increment: 0.01,
};

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

export async function discoverAmazonProducts(
  keyword: string,
  domain: string,
  targetSiteId: string,
  limit: number,
) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-search/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, domain, target_site_id: targetSiteId, limit }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionBatchResult>;
}

export async function createCollectionJobsFile(
  file: File,
  targetSiteId: string,
  allowExisting: boolean,
) {
  const body = new FormData();
  body.append("file", file);
  body.append("target_site_id", targetSiteId);
  body.append("allow_existing", String(allowExisting));
  const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs/file`, {
    method: "POST",
    body,
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

export async function enqueueBehavioralAuditBatch(draftIds: number[]) {
  const response = await fetch(`${API_BASE}/api/reviews/jobs/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      draft_ids: draftIds,
      acknowledge_provider_costs: true,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ReviewJobBatchResult>;
}

export async function listReviewJobs(limit = 100) {
  const response = await fetch(`${API_BASE}/api/reviews/jobs?limit=${limit}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ReviewJob[]>;
}

export async function getMeliAuthorizationUrl(siteId: string) {
  const response = await fetch(
    `${API_BASE}/api/stores/meli/authorization-url?site_id=${encodeURIComponent(siteId)}`,
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ authorization_url: string; site_id: string }>;
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

export async function runIntegrationDiagnostics() {
  const response = await fetch(`${API_BASE}/api/integrations/diagnostics`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<IntegrationDiagnostics>;
}

export async function getProviderModelPrices(includeHistory = false) {
  const suffix = includeHistory ? "?include_history=true" : "";
  const response = await fetch(`${API_BASE}/api/integrations/model-prices${suffix}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProviderModelPrice[]>;
}

export async function saveProviderModelPrice(payload: ProviderModelPriceCreate) {
  const response = await fetch(`${API_BASE}/api/integrations/model-prices`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProviderModelPrice>;
}

export async function deactivateProviderModelPrice(priceId: number) {
  const response = await fetch(`${API_BASE}/api/integrations/model-prices/${priceId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProviderModelPrice>;
}

export async function listDrafts() {
  const response = await fetch(`${API_BASE}/api/drafts`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraftRead[]>;
}

export async function getDraft(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraftRead>;
}

export async function saveDraftContent(productDraftId: number, payload: DraftContentUpdate) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/content`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraftRead>;
}

export async function confirmDraftCategory(
  productDraftId: number,
  payload: { expected_content_version: number; target_site_id: string; category_id: string },
) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/category`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftCategoryResult>;
}

export async function generateDraftContent(productDraftId: number, categoryId: string) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/generate-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: categoryId, language: "en" }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<GeneratedDraftContent>;
}

export async function listReviewHistory(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/reviews/drafts/${productDraftId}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ReviewResult[]>;
}

export async function getLatestBehavioralReview(productDraftId: number) {
  const response = await fetch(
    `${API_BASE}/api/reviews/drafts/${productDraftId}/latest-behavioral`,
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ReviewResult | null>;
}

export async function listStores() {
  const response = await fetch(`${API_BASE}/api/stores`);
  if (!response.ok) throw new Error(await response.text());
  const payload = await response.json() as unknown;
  if (!Array.isArray(payload)) {
    // A legacy service can still be listening on the local API port. Do not
    // let its incompatible payload crash every page that reads stores.
    if (payload && typeof payload === "object" && "stores" in payload && Array.isArray((payload as { stores: unknown }).stores)) {
      return [];
    }
    throw new Error("店铺接口返回了无法识别的数据格式");
  }
  return payload as StoreRecord[];
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

export async function getCbtPublishingProfile(storeId: number) {
  const response = await fetch(`${API_BASE}/api/stores/${storeId}/cbt-publishing-profile`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CbtPublishingProfile>;
}

export type StoreItem = {
  id: string;
  title?: string;
  thumbnail?: string;
  status?: string;
  category_id?: string;
  price?: number;
  currency_id?: string;
  available_quantity?: number;
  sold_quantity?: number;
  listing_type_id?: string;
  permalink?: string;
  warranty?: string;
  shipping_mode?: string;
  shipping_logistic_type?: string;
  free_shipping?: boolean;
  last_updated?: string;
  has_public_permalink?: boolean;
  load_error?: boolean;
};

export type StoreItemPriceReference = {
  store_id: number;
  item_id: string;
  availability: "available" | "unavailable";
  reason?: "official_no_reference" | "not_eligible_or_not_authorized" | "requires_marketplace_child_item";
  message?: string;
  status?: string;
  currency_id?: string;
  current_price?: { amount?: number; usd_amount?: number };
  suggested_price?: { amount?: number; usd_amount?: number };
  lowest_price?: { amount?: number; usd_amount?: number };
  estimated_taxes?: { amount?: number; usd_amount?: number };
  selling_fees?: number;
  shipping_fees?: number;
  percent_difference?: number;
  applicable_suggestion?: boolean;
  last_updated?: string;
  estimated_after_reference_costs?: number | null;
};

export async function listStoreItems(storeId: number, options: { limit?: number; offset?: number; search?: string } = {}) {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 30), offset: String(options.offset ?? 0),
  });
  if (options.search?.trim()) params.set("search", options.search.trim());
  const response = await fetch(`${API_BASE}/api/stores/${storeId}/items?${params}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ store_id: number; site_id: string; items: StoreItem[]; total: number; limit: number; offset: number }>;
}

export async function getStoreItemPriceReference(storeId: number, itemId: string) {
  const response = await fetch(
    `${API_BASE}/api/stores/${storeId}/items/${encodeURIComponent(itemId)}/price-reference`,
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<StoreItemPriceReference>;
}

export async function getCbtMarketplaceListingTypes(storeId: number, categoryId: string) {
  const response = await fetch(`${API_BASE}/api/stores/${storeId}/cbt/categories/${encodeURIComponent(categoryId)}/marketplace-listing-types`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ store_id: number; category_id: string; markets: Array<{ site_id: string; verified: boolean; listing_type_ids: string[]; error?: string }> }>;
}

export async function getStoreCategoryListingTypes(storeId: number, categoryId: string) {
  const response = await fetch(
    `${API_BASE}/api/stores/${storeId}/categories/${encodeURIComponent(categoryId)}/listing-types`,
  );
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    store_id: number;
    site_id: string;
    category_id: string;
    verified: boolean;
    listing_types: Array<{
      id: string;
      name: string;
      site_id: string;
      remaining_listings: number | null;
    }>;
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

export async function getCategoryDetails(categoryId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/categories/${encodeURIComponent(categoryId)}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{
    id: string;
    name: string;
    name_zh?: string;
    path_from_root: Array<{ id: string; name: string; name_zh?: string }>;
    path_from_root_zh?: Array<{ id: string; name: string; name_zh?: string }>;
    leaf: boolean;
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

export async function listPublishJobs(limit = 100, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(`${API_BASE}/api/publishing/jobs?${params}`);
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

export async function cancelPublishJob(jobId: number) {
  const response = await fetch(`${API_BASE}/api/publishing/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishJobRecord>;
}

export async function reconcilePublishJob(jobId: number) {
  const response = await fetch(`${API_BASE}/api/publishing/jobs/${jobId}/reconcile`, {
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
    available_quantity: number;
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

export async function saveCbtListingConfig(
  productDraftId: number,
  payload: Omit<CbtListingConfig, "id" | "product_draft_id" | "draft_content_version" | "draft" | "created_at" | "updated_at">,
) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/cbt-listing-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CbtListingConfig>;
}

export async function getCbtListingConfig(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/cbt-listing-config?optional=true`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CbtListingConfig | null>;
}

export async function previewCbtPublishFromDraft(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/publishing/cbt/preview-from-draft?product_draft_id=${productDraftId}`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ allowed: boolean; errors: string[]; payload: Record<string, unknown> | null }>;
}

export async function executeCbtPublishFromDraft(productDraftId: number) {
  const response = await fetch(`${API_BASE}/api/publishing/cbt/execute-from-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_draft_id: productDraftId, acknowledge_publish: true }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishExecutionResult>;
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

export async function enqueuePublishBatch(draftIds: number[]) {
  const response = await fetch(`${API_BASE}/api/publishing/enqueue-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      draft_ids: draftIds,
      acknowledge_publish: true,
    }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishBatchEnqueueResult>;
}

export async function preflightPublishBatch(draftIds: number[]) {
  const response = await fetch(`${API_BASE}/api/publishing/preflight-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft_ids: draftIds }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishBatchPreflightResult>;
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
