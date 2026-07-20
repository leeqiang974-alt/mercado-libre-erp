import { useState } from "react";
import { Layout } from "./components/Layout";
import { importAmazonHtml, importAmazonUrl, type ProductDraft } from "./api/client";
import { ImportPage } from "./pages/ImportPage";
import { DraftsPage } from "./pages/DraftsPage";
import { PublishingPage } from "./pages/PublishingPage";
import { StoresPage } from "./pages/StoresPage";
import { AuditPage } from "./pages/AuditPage";
import { DashboardPage } from "./pages/DashboardPage";

export function App() {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [page, setPage] = useState(() =>
    new URLSearchParams(window.location.search).get("meli_auth") ? "stores" : "dashboard",
  );
  const [status, setStatus] = useState("");

  async function importAndReview(
    sourceUrl: string,
    html: string,
    targetSiteId: string,
    persist: boolean,
    collectionJobId: number | null,
  ) {
    setStatus("Importing Amazon page snapshot");
    const importResult = await importAmazonHtml(
      sourceUrl,
      html,
      targetSiteId,
      persist,
      collectionJobId,
    );
    const nextDraft = "draft" in importResult ? importResult.draft : importResult;
    const nextDraftId = "draft" in importResult ? importResult.id : null;
    setDraft(nextDraft);
    setDraftId(nextDraftId);
    setReview(null);
    setStatus("Draft saved. Select Claude, NVIDIA, or combined review.");
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
    setReview(null);
    setStatus("Draft saved. Select Claude, NVIDIA, or combined review.");
    setPage("drafts");
  }

  return (
    <Layout page={page} onPageChange={setPage}>
      {page === "dashboard" && <DashboardPage onNavigate={setPage} />}
      {page === "import" && (
        <ImportPage
          onImportHtml={importAndReview}
          onCollectUrl={collectUrlAndReview}
          status={status}
        />
      )}
      {page === "drafts" && (
        <DraftsPage
          draft={draft}
          draftId={draftId}
          review={review}
          onReviewChange={setReview}
          onDraftChange={setDraft}
          onSelectDraft={(selectedDraft) => {
            setDraft(selectedDraft);
            setDraftId(selectedDraft.id);
            setReview(null);
            setStatus(`Draft #${selectedDraft.id} selected`);
          }}
        />
      )}
      {page === "publishing" && (
        <PublishingPage
          draft={draft}
          draftId={draftId}
          review={review}
          onDraftChange={setDraft}
          onReviewInvalidated={() => setReview(null)}
        />
      )}
      {page === "stores" && <StoresPage />}
      {page === "audit" && <AuditPage />}
    </Layout>
  );
}
