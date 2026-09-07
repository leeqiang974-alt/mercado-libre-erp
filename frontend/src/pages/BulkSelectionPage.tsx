import { useCallback, useEffect, useState } from "react";
import { Search, RefreshCw, CheckSquare, Square, Download, AlertCircle, Package, Layers, PauseCircle, PlayCircle } from "lucide-react";

interface BulkProduct {
  id: number;
  asin: string;
  title: string;
  source_price: number | null;
  source_currency: string;
  image_url: string;
  variant_count: number;
  measurements: { weight_kg?: number | null; length_cm?: number | null; width_cm?: number | null; height_cm?: number | null };
}

interface StoreItemLite {
  item_id: string;
  title: string;
  status: string;
  store_id: number;
  display_name: string;
  site_id: string;
}

export function BulkSelectionPage() {
  const [minPrice, setMinPrice] = useState("3");
  const [maxPrice, setMaxPrice] = useState("8");
  const [keyword, setKeyword] = useState("");
  const [products, setProducts] = useState<BulkProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // 批量建草稿参数
  const [targetCategory, setTargetCategory] = useState("");
  const [priceMode, setPriceMode] = useState<"multiplier" | "fixed">("multiplier");
  const [priceValue, setPriceValue] = useState("1.3");
  const [creating, setCreating] = useState(false);

  // 已上架商品批量上下架
  const [storeItems, setStoreItems] = useState<StoreItemLite[]>([]);
  const [storeItemsLoading, setStoreItemsLoading] = useState(false);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

  const API = "";

  async function fetchProducts() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (minPrice) params.set("min_price", minPrice);
      if (maxPrice) params.set("max_price", maxPrice);
      if (keyword.trim()) params.set("keyword", keyword.trim());
      params.set("limit", "100");
      const r = await fetch(`${API}/api/bulk-selection/products?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setProducts(d.products || []);
      setTotal(d.total || 0);
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  const fetchStoreItems = useCallback(async () => {
    setStoreItemsLoading(true);
    setError("");
    try {
      const r = await fetch(`${API}/api/stores/3/items?limit=50`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      const items: StoreItemLite[] = (d.items || [])
        .filter((it: { status?: string }) => it.status === "active" || it.status === "paused")
        .map((it: { id: string; title?: string; status?: string }) => ({
          item_id: it.id,
          title: it.title || it.id,
          status: it.status || "",
          store_id: 3,
          display_name: d.store_name || "晨",
          site_id: d.site_id || "CBT",
        }));
      setStoreItems(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载已上架商品失败");
    } finally {
      setStoreItemsLoading(false);
    }
  }, [API]);

  useEffect(() => {
    void fetchProducts();
    void fetchStoreItems();
  }, [fetchStoreItems]);

  function toggleProduct(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllProducts() {
    setSelected((prev) => (prev.size === products.length ? new Set() : new Set(products.map((p) => p.id))));
  }

  async function createDrafts() {
    if (selected.size === 0) {
      setMessage("请先勾选产品");
      return;
    }
    setCreating(true);
    setMessage("");
    try {
      const r = await fetch(`${API}/api/bulk-selection/drafts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_product_ids: [...selected],
          target_site_id: "CBT",
          target_category_id: targetCategory.trim(),
          price_mode: priceMode,
          price_value: parseFloat(priceValue) || 1.3,
          stock: 999,
        }),
      });
      const d = await r.json();
      setMessage(`批量建草稿完成：成功 ${d.created_count} 个，跳过 ${d.skipped_count} 个（已有草稿/缺价格）`);
      setSelected(new Set());
      void fetchProducts();
    } catch (e) {
      setMessage(`建草稿失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setCreating(false);
    }
  }

  function toggleItem(itemId: string) {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  function toggleAllItems() {
    setSelectedItems((prev) => (prev.size === storeItems.length ? new Set() : new Set(storeItems.map((i) => i.item_id))));
  }

  async function bulkToggle(action: "pause" | "activate") {
    if (selectedItems.size === 0) {
      setMessage("请先勾选已上架商品");
      return;
    }
    setMessage("");
    try {
      const r = await fetch(`${API}/api/bulk-selection/items/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ store_id: 3, item_ids: [...selectedItems], action }),
      });
      const d = await r.json();
      setMessage(`${action === "pause" ? "批量暂停" : "批量恢复"}完成：成功 ${d.success_count} / ${d.results.length}`);
      setSelectedItems(new Set());
      void fetchStoreItems();
    } catch (e) {
      setMessage(`操作失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
  }

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">批量选品</p>
          <h2>批量选品中心</h2>
          <p>按分类/价格带筛选已采集 Amazon 产品，一键批量生成草稿；已上架商品批量上下架</p>
        </div>
        <button className="secondary-button" onClick={() => void fetchProducts()}>
          <RefreshCw size={14} /> 刷新
        </button>
      </header>

      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          {error}
        </div>
      )}
      {message && (
        <div className="notice-banner">
          <AlertCircle size={16} />
          {message}
        </div>
      )}

      {/* 筛选区 */}
      <section className="surface">
        <h3>
          <Search size={16} /> 筛选 Amazon 产品（按采购价）
        </h3>
        <div className="filter-row" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <label>
            最低价 $
            <input type="number" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>
            最高价 $
            <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>
            关键词
            <input type="text" value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="如 shower / cable / organizer" style={{ width: 220 }} />
          </label>
          <button className="primary-button" onClick={() => void fetchProducts()}>
            <Search size={14} /> 查询
          </button>
          <span className="muted-text">共 {total} 个符合价格带的产品</span>
        </div>
      </section>

      {/* 产品列表 */}
      <section className="surface">
        <h3>
          <Layers size={16} /> 产品列表 {loading && <span className="muted-text">加载中...</span>}
        </h3>
        <div className="bulk-toolbar" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
          <button className="secondary-button" onClick={toggleAllProducts}>
            {selected.size === products.length && products.length > 0 ? <CheckSquare size={14} /> : <Square size={14} />}
            全选 / 取消（{selected.size}）
          </button>
          <span style={{ marginLeft: 8 }} />
          <label>
            目标分类ID
            <input type="text" value={targetCategory} onChange={(e) => setTargetCategory(e.target.value)} placeholder="如 CBT95418（可留空稍后在草稿页选）" style={{ width: 220 }} />
          </label>
          <select value={priceMode} onChange={(e) => setPriceMode(e.target.value as "multiplier" | "fixed")}>
            <option value="multiplier">净收益=采购价×倍数</option>
            <option value="fixed">净收益=统一价</option>
          </select>
          <input type="number" step="0.1" value={priceValue} onChange={(e) => setPriceValue(e.target.value)} style={{ width: 80 }} />
          <button className="primary-button" onClick={() => void createDrafts()} disabled={creating}>
            <Download size={14} /> {creating ? "创建中..." : `批量生成 ${selected.size} 个草稿`}
          </button>
        </div>
        {selected.size > 0 && (
          <div className="selected-preview" style={{ marginTop: 10, padding: "10px 12px", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, fontSize: 13 }}>
            <strong>已选 {selected.size} 个产品（生成前请核对）：</strong>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 16px", marginTop: 6 }}>
              {products.filter((p) => selected.has(p.id)).map((p) => (
                <span key={p.id} style={{ color: "#1d4ed8" }}>
                  {"\u2022"} ${p.source_price ?? "-"} {p.title ? p.title.slice(0, 48) : p.asin || `#${p.id}`}
                </span>
              ))}
            </div>
          </div>
        )}
        {products.length === 0 && !loading ? (
          <div className="empty-tip">
            <AlertCircle size={16} />
            <span>没有符合条件的产品。调整价格带或关键词，或等待挂机采集补充数据。</span>
          </div>
        ) : (
          <div className="product-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
            {products.map((p) => (
              <div
                key={p.id}
                className="bulk-product-card"
                style={{
                  border: "1px solid var(--border,#e5e7eb)",
                  borderRadius: 10,
                  padding: 10,
                  cursor: "pointer",
                  background: selected.has(p.id) ? "#eff6ff" : "#fff",
                  borderColor: selected.has(p.id) ? "#2563eb" : undefined,
                }}
                onClick={() => toggleProduct(p.id)}
              >
                <div style={{ display: "flex", gap: 10 }}>
                  {p.image_url ? (
                    <img src={p.image_url} alt="" style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 6, background: "#f3f4f6" }} />
                  ) : (
                    <div style={{ width: 72, height: 72, borderRadius: 6, background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Package size={20} color="#9ca3af" />
                    </div>
                  )}
                  <div style={{ minWidth: 0 }}>
                    <strong style={{ fontSize: 13, display: "block", lineHeight: 1.35 }}>{p.title || p.asin || `#${p.id}`}</strong>
                    <div style={{ marginTop: 6 }}>
                      <span className="price-tag" style={{ background: "#05966915", color: "#059669", padding: "2px 8px", borderRadius: 999, fontWeight: 700, fontSize: 13 }}>
                        ${p.source_price ?? "-"} {p.source_currency}
                      </span>
                      {p.variant_count > 1 && <span className="muted-text" style={{ marginLeft: 6, fontSize: 12 }}>{p.variant_count} 变体</span>}
                    </div>
                    <div className="muted-text" style={{ fontSize: 11, marginTop: 4 }}>ASIN: {p.asin || "-"}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 已上架商品批量上下架 */}
      <section className="surface" style={{ marginTop: 16 }}>
        <h3>
          <Package size={16} /> 已上架商品批量上下架（店铺：晨 CBT）
        </h3>
        <div className="bulk-toolbar" style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
          <button className="secondary-button" onClick={toggleAllItems}>
            {selectedItems.size === storeItems.length && storeItems.length > 0 ? <CheckSquare size={14} /> : <Square size={14} />}
            全选（{selectedItems.size}/{storeItems.length}）
          </button>
          <button className="secondary-button" onClick={() => void bulkToggle("pause")} disabled={storeItemsLoading}>
            <PauseCircle size={14} /> 批量暂停
          </button>
          <button className="secondary-button" onClick={() => void bulkToggle("activate")} disabled={storeItemsLoading}>
            <PlayCircle size={14} /> 批量恢复
          </button>
          {storeItemsLoading && <span className="muted-text">加载中...</span>}
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 30 }}></th>
              <th>商品</th>
              <th>Item ID</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {storeItems.map((it) => (
              <tr key={it.item_id}>
                <td>
                  <input type="checkbox" checked={selectedItems.has(it.item_id)} onChange={() => toggleItem(it.item_id)} />
                </td>
                <td>{it.title}</td>
                <td>{it.item_id}</td>
                <td>
                  <span className={`badge ${it.status === "active" ? "badge-ok" : "badge-error"}`}>{it.status === "active" ? "在售" : "已暂停"}</span>
                </td>
              </tr>
            ))}
            {storeItems.length === 0 && !storeItemsLoading && (
              <tr>
                <td colSpan={4} className="muted-text">暂无已上架商品</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </section>
  );
}
