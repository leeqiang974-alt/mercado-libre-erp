const API_BASE = "http://127.0.0.1:8000";

export type ProductDraft = {
  title: string;
  description: string;
  brand: string;
  target_site_id: string;
  target_category_id: string;
  condition: string;
  price: number | null;
  currency: string;
  stock: number;
  listing_type_id: string;
  image_urls: string[];
};

export type ProductDraftRead = ProductDraft & {
  id: number;
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
  decision: string;
  risk_level: string;
  reason_codes: string[];
  reasons: string[];
  suggested_changes: Record<string, unknown>;
};

export type StoreRecord = {
  id: string;
  site_id: string;
  seller_id: string;
  display_name: string;
  oauth_status: string;
  token_reference: string;
};

export type PublishJobRecord = {
  id: number;
  product_draft_id: number;
  store_id: number;
  status: string;
  item_id: string;
  permalink: string;
  errors: string[];
};

export type DraftListingConfig = {
  id: number;
  product_draft_id: number;
  site_id: string;
  category_id: string;
  listing_type_id: string;
  fulfillment: string;
  attributes: { id: string; value_name: string }[];
  created_at: string;
  updated_at: string;
};

export type PublishValidationResult = {
  allowed: boolean;
  errors: string[];
};

export type PublishExecutionResult = {
  status: string;
  item_id: string;
  permalink: string;
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
};

export async function importAmazonUrl(sourceUrl: string, targetSiteId: string) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, target_site_id: targetSiteId }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionResult>;
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

export async function listCollectionJobs() {
  const response = await fetch(`${API_BASE}/api/imports/amazon-url/jobs`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<CollectionJobRecord[]>;
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
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function getMeliAuthorizationUrl() {
  const response = await fetch(`${API_BASE}/api/stores/meli/authorization-url`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ authorization_url: string; state: string }>;
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

export async function getListingTypes(siteId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/sites/${siteId}/listing-types`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ listing_type_ids: string[] }>;
}

export async function refreshListingTypes(siteId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/sites/${siteId}/listing-types/refresh`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ listing_type_ids: string[] }>;
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
  return response.json() as Promise<{ attributes: Record<string, unknown>[] }>;
}

export async function refreshCategoryAttributes(categoryId: string) {
  const response = await fetch(`${API_BASE}/api/metadata/categories/${categoryId}/attributes/refresh`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ attributes: Record<string, unknown>[] }>;
}

export async function listPublishJobs() {
  const response = await fetch(`${API_BASE}/api/publishing/jobs`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishJobRecord[]>;
}

export async function saveDraftListingConfig(
  productDraftId: number,
  payload: {
    site_id: string;
    category_id: string;
    listing_type_id: string;
    fulfillment: string;
    attributes: { id: string; value_name: string }[];
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
  const response = await fetch(`${API_BASE}/api/drafts/${productDraftId}/listing-config`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<DraftListingConfig>;
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

export async function listAuditEvents(limit = 100) {
  const response = await fetch(`${API_BASE}/api/audit-events?limit=${limit}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<AuditEventRecord[]>;
}

function reviewUrl(provider: "local" | "claude" | "nvidia", productDraftId?: number | null) {
  const query = productDraftId ? `?product_draft_id=${productDraftId}` : "";
  return `${API_BASE}/api/reviews/${provider}${query}`;
}
