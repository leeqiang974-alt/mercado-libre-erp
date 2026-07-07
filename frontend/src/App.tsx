import { useState } from "react";
import { Layout } from "./components/Layout";
import { importAmazonHtml, reviewDraft, type ProductDraft } from "./api/client";
import { ImportPage } from "./pages/ImportPage";
import { DraftsPage } from "./pages/DraftsPage";
import { PublishingPage } from "./pages/PublishingPage";

export function App() {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [page, setPage] = useState("import");
  const [status, setStatus] = useState("");

  async function importAndReview(sourceUrl: string, html: string, targetSiteId: string) {
    setStatus("Importing Amazon page snapshot");
    const nextDraft = await importAmazonHtml(sourceUrl, html, targetSiteId);
    setDraft(nextDraft);
    setStatus("Running local review");
    const nextReview = await reviewDraft(nextDraft);
    setReview(nextReview);
    setStatus(`Review complete: ${nextReview.decision}`);
    setPage("drafts");
  }

  return (
    <Layout page={page} onPageChange={setPage}>
      {page === "import" && <ImportPage onImport={importAndReview} status={status} />}
      {page === "drafts" && <DraftsPage draft={draft} review={review} />}
      {page === "publishing" && <PublishingPage draft={draft} review={review} />}
    </Layout>
  );
}
