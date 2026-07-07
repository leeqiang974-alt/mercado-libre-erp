import { useState } from "react";
import { Layout } from "./components/Layout";
import { importAmazonHtml, importAmazonUrl, reviewDraft, type ProductDraft } from "./api/client";
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

  async function collectUrlAndReview(sourceUrl: string, targetSiteId: string) {
    setStatus("Collecting Amazon page");
    const result = await importAmazonUrl(sourceUrl, targetSiteId);
    if (result.status !== "collected" || !result.draft) {
      setStatus(result.message);
      setDraft(null);
      setReview(null);
      return;
    }
    setDraft(result.draft);
    setStatus("Running local review");
    const nextReview = await reviewDraft(result.draft);
    setReview(nextReview);
    setStatus(`Review complete: ${nextReview.decision}`);
    setPage("drafts");
  }

  return (
    <Layout page={page} onPageChange={setPage}>
      {page === "import" && (
        <ImportPage
          onImportHtml={importAndReview}
          onCollectUrl={collectUrlAndReview}
          status={status}
        />
      )}
      {page === "drafts" && <DraftsPage draft={draft} review={review} />}
      {page === "publishing" && <PublishingPage draft={draft} review={review} />}
    </Layout>
  );
}
