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

export async function importAmazonHtml(sourceUrl: string, html: string, targetSiteId: string) {
  const response = await fetch(`${API_BASE}/api/imports/amazon-html`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl, html, target_site_id: targetSiteId }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<ProductDraft>;
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
