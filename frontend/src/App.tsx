import { useState } from "react";
import { Layout } from "./components/Layout";
import { importAmazonHtml, importAmazonUrl, reviewDraft, type ProductDraft } from "./api/client";
import { ImportPage } from "./pages/ImportPage";
import { DraftsPage } from "./pages/DraftsPage";
import { PublishingPage } from "./pages/PublishingPage";
import { StoresPage } from "./pages/StoresPage";
import { AuditPage } from "./pages/AuditPage";

export function App() {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [page, setPage] = useState("import");
  const [status, setStatus] = useState("");

  async function importAndReview(sourceUrl: string, html: string, targetSiteId: string, persist: boolean) {
    setStatus("Importing Amazon page snapshot");
    const importResult = await importAmazonHtml(sourceUrl, html, targetSiteId, persist);
    const nextDraft = "draft" in importResult ? importResult.draft : importResult;
    const nextDraftId = "draft" in importResult ? importResult.id : null;
    setDraft(nextDraft);
    setDraftId(nextDraftId);
    setStatus("Running local review");
    const nextReview = await reviewDraft(nextDraft, nextDraftId);
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
    setDraftId(result.draft_id);
    setStatus("Running local review");
    const nextReview = await reviewDraft(result.draft, result.draft_id);
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
      {page === "drafts" && <DraftsPage draft={draft} draftId={draftId} review={review} />}
      {page === "publishing" && <PublishingPage draft={draft} draftId={draftId} review={review} />}
      {page === "stores" && <StoresPage />}
      {page === "audit" && <AuditPage />}
    </Layout>
  );
}
