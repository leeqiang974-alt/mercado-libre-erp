import { useState } from "react";
import { Layout } from "./components/Layout";
import { importAmazonHtml, type ProductDraft } from "./api/client";
import { ImportPage } from "./pages/ImportPage";
import { DraftsPage } from "./pages/DraftsPage";
import { PublishingPage } from "./pages/PublishingPage";
import { StoresPage } from "./pages/StoresPage";
import { AuditPage } from "./pages/AuditPage";
import { DashboardPage } from "./pages/DashboardPage";
import { OrdersPage } from "./pages/OrdersPage";
import { InventoryPage } from "./pages/InventoryPage";
import { WarehousePage } from "./pages/WarehousePage";
import { PurchasePage } from "./pages/PurchasePage";
import { LogisticsPage } from "./pages/LogisticsPage";
import { FinancePage } from "./pages/FinancePage";
import { ReportsPage } from "./pages/ReportsPage";
import { MessagesPage } from "./pages/MessagesPage";
import { StoreProductsPage } from "./pages/StoreProductsPage";

export function App() {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [page, setPage] = useState(() =>
    new URLSearchParams(window.location.search).get("meli_auth") ? "stores" : "dashboard",
  );
  const [status, setStatus] = useState("");
  const [draftContentDirty, setDraftContentDirty] = useState(false);

  function changePage(nextPage: string) {
    if (
      page === "drafts"
      && nextPage !== "drafts"
      && draftContentDirty
      && !window.confirm("丢弃未保存的商品内容修改？")
    ) return;
    setPage(nextPage);
  }

  async function importAndReview(
    sourceUrl: string,
    html: string,
    targetSiteId: string,
    persist: boolean,
    collectionJobId: number | null,
  ) {
    setStatus("正在导入 Amazon 页面快照");
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
    setStatus("草稿已保存。请选择 Claude、NVIDIA 或组合审核。");
    setPage("drafts");
  }

  return (
    <Layout page={page} onPageChange={changePage}>
      {page === "dashboard" && <DashboardPage onNavigate={setPage} />}

      {/* 商品管理 */}
      {page === "import" && (
        <ImportPage
          onImportHtml={importAndReview}
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
          onContentDirtyChange={setDraftContentDirty}
          onSelectDraft={(selectedDraft) => {
            setDraft(selectedDraft);
            setDraftId(selectedDraft.id);
            setReview(null);
            setStatus(`已选择草稿 #${selectedDraft.id}`);
          }}
        />
      )}
      {page === "products" && <StoreProductsPage />}
      {page === "publishing" && (
        <PublishingPage
          draft={draft}
          draftId={draftId}
          review={review}
          onDraftChange={setDraft}
          onReviewInvalidated={() => setReview(null)}
        />
      )}

      {/* 订单管理 */}
      {page === "orders" && <OrdersPage />}

      {/* 库存管理 */}
      {page === "inventory" && <InventoryPage />}
      {page === "warehouse" && <WarehousePage />}

      {/* 采购管理 */}
      {page === "purchase" && <PurchasePage />}

      {/* 物流管理 */}
      {page === "logistics" && <LogisticsPage />}

      {/* 客户服务 */}
      {page === "messages" && <MessagesPage />}

      {/* 财务报表 */}
      {page === "finance" && <FinancePage />}
      {page === "reports" && <ReportsPage />}

      {/* 店铺设置 */}
      {page === "stores" && <StoresPage />}
      {page === "audit" && <AuditPage />}
    </Layout>
  );
}
