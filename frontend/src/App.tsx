import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { getDraft, importAmazonHtml, type ProductDraft, type ProductDraftRead } from "./api/client";
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

const HASH_PAGE_ALIASES: Record<string, string> = {
  // Keep the previous product-list URL working, but send operators to the
  // actual listing workspace rather than the old read-only store list.
  items: "drafts",
  drafts: "drafts",
  listing: "drafts",
  products: "products",
  "store-products": "products",
  publishing: "publishing",
};

function pageFromLocation() {
  if (new URLSearchParams(window.location.search).get("meli_auth")) return "stores";
  return HASH_PAGE_ALIASES[window.location.hash.replace(/^#/, "")] ?? "dashboard";
}

function setLocationPage(page: string, draftId?: number | null) {
  const query = new URLSearchParams(window.location.search);
  if (draftId) query.set("draft_id", String(draftId));
  else query.delete("draft_id");
  const hash = page === "drafts" ? "#drafts" : page === "products" ? "#store-products" : `#${page}`;
  const search = query.toString();
  window.history.replaceState({}, "", `${window.location.pathname}${search ? `?${search}` : ""}${hash}`);
}

function draftIdFromLocation(): number | null {
  const value = Number(new URLSearchParams(window.location.search).get("draft_id"));
  return Number.isInteger(value) && value > 0 ? value : null;
}

export function App() {
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [draftId, setDraftId] = useState<number | null>(draftIdFromLocation);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [page, setPage] = useState(pageFromLocation);
  const [status, setStatus] = useState("");
  const [draftContentDirty, setDraftContentDirty] = useState(false);

  useEffect(() => {
    const openLocationRoute = async () => {
      const nextPage = pageFromLocation();
      const draftValue = Number(new URLSearchParams(window.location.search).get("draft_id"));
      if ((nextPage === "drafts" || nextPage === "publishing") && Number.isInteger(draftValue) && draftValue > 0) {
        try {
          const selectedDraft = await getDraft(draftValue);
          setDraft(selectedDraft);
          setDraftId(selectedDraft.id);
          setReview(null);
          setStatus(`正在编辑上架商品 #${selectedDraft.id}`);
        } catch {
          setStatus(`无法读取上架单 #${draftValue}`);
        }
      }
      setPage(nextPage);
    };
    void openLocationRoute();
    window.addEventListener("hashchange", openLocationRoute);
    return () => window.removeEventListener("hashchange", openLocationRoute);
  }, []);

  // Direct Global Selling links must be self-contained. The publishing page
  // cannot rely on the editor having been opened in this browser session.
  useEffect(() => {
    if (page !== "publishing" || !draftId || draft) return;
    let cancelled = false;
    getDraft(draftId)
      .then((selectedDraft) => {
        if (!cancelled) {
          setDraft(selectedDraft);
          setReview(null);
        }
      })
      .catch(() => {
        if (!cancelled) setStatus(`无法读取上架单 #${draftId}`);
      });
    return () => { cancelled = true; };
  }, [page, draftId, draft]);

  function changePage(nextPage: string) {
    if (
      page === "drafts"
      && nextPage !== "drafts"
      && draftContentDirty
      && !window.confirm("丢弃未保存的商品内容修改？")
    ) return;
    setPage(nextPage);
    setLocationPage(nextPage);
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

  function openDraftForListing(selectedDraft: ProductDraftRead) {
    setDraft(selectedDraft);
    setDraftId(selectedDraft.id);
    setReview(null);
    setStatus(`正在编辑上架商品 #${selectedDraft.id}`);
    setPage("drafts");
    setLocationPage("drafts", selectedDraft.id);
  }

  return (
    <Layout page={page} onPageChange={changePage}>
      {page === "dashboard" && <DashboardPage onNavigate={setPage} />}

      {/* 商品管理 */}
      {page === "import" && (
        <ImportPage
          onImportHtml={importAndReview}
          onOpenDraft={openDraftForListing}
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
            openDraftForListing(selectedDraft);
          }}
          onContinueListing={() => {
            setPage("publishing");
            setLocationPage("publishing", draftId);
          }}
        />
      )}
      {page === "products" && <StoreProductsPage onOpenListingLibrary={() => changePage("drafts")} />}
      {page === "publishing" && (
        <PublishingPage
          draft={draft}
          draftId={draftId}
          review={review}
          onDraftChange={setDraft}
          onReviewInvalidated={() => setReview(null)}
          onBackToEditing={() => {
            setPage("drafts");
            setLocationPage("drafts", draftId);
          }}
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
