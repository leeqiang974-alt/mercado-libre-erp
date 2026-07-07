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

export async function reviewDraft(draft: ProductDraft) {
  const response = await fetch(`${API_BASE}/api/reviews/local`, {
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

export async function listPublishJobs() {
  const response = await fetch(`${API_BASE}/api/publishing/jobs`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<PublishJobRecord[]>;
}
