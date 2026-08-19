import { useEffect, useState } from "react";
import { Search, AlertTriangle, Package } from "lucide-react";
import {
  listInventory,
  listWarehouses,
  MOVEMENT_TYPE_LABELS,
  type InventoryRecord,
  type WarehouseRecord,
} from "../api/erpClient";

export function InventoryPage() {
  const [items, setItems] = useState<InventoryRecord[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [warehouseId, setWarehouseId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [lowStockOnly, setLowStockOnly] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const result = await listInventory({
        warehouse_id: warehouseId ? parseInt(warehouseId) : undefined,
        keyword: keyword || undefined,
        low_stock: lowStockOnly,
        page,
        page_size: pageSize,
      });
      setItems(result.items);
      setTotal(result.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void listWarehouses().then(setWarehouses);
  }, []);

  useEffect(() => {
    void refresh();
  }, [page, warehouseId, lowStockOnly]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">库存管理</p>
          <h2>库存查询</h2>
          <p>实时查看各仓库库存水位、库存预警和出入库记录。</p>
        </div>
      </header>

      <div className="metric-strip" style={{ marginBottom: 16 }}>
        <div><span>SKU 总数</span><strong>{total}</strong></div>
        <div><span>库存预警</span>
          <strong style={{ color: "#ea580c" }}>
            {items.filter(i => i.is_low_stock).length}
          </strong>
        </div>
        <div><span>仓库数</span><strong>{warehouses.length}</strong></div>
        <div><span>总库存件数</span>
          <strong>{items.reduce((s, i) => s + i.quantity, 0).toLocaleString()}</strong>
        </div>
      </div>

      <div className="surface" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flex: 1, minWidth: 200 }}>
            <Search size={16} style={{ color: "#7b8794" }} />
            <input
              type="text"
              placeholder="搜索 SKU、商品名称"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (setPage(1), refresh())}
              style={{
                flex: 1, padding: "8px 12px",
                border: "1px solid #dde3ea", borderRadius: 6, fontSize: 14,
              }}
            />
          </div>
          <select
            value={warehouseId}
            onChange={(e) => { setWarehouseId(e.target.value); setPage(1); }}
            style={{ padding: "8px 12px", border: "1px solid #dde3ea", borderRadius: 6, fontSize: 14 }}
          >
            <option value="">全部仓库</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
          <label style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={lowStockOnly}
              onChange={(e) => { setLowStockOnly(e.target.checked); setPage(1); }}
            />
            仅看预警
          </label>
          <button
            className="secondary-button"
            onClick={() => { setPage(1); void refresh(); }}
          >
            查询
          </button>
        </div>
      </div>

      <div className="surface">
        {loading && <div className="empty-state">加载中...</div>}
        {!loading && items.length === 0 && (
          <div className="empty-state">
            <Package size={28} />
            <strong>暂无库存数据</strong>
            <p>没有符合条件的库存记录。</p>
          </div>
        )}
        {!loading && items.length > 0 && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>商品名称</th>
                  <th>可用库存</th>
                  <th>预留</th>
                  <th>安全库存</th>
                  <th>平均成本</th>
                  <th>最近入库</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 500 }}>
                      {item.sku}
                    </td>
                    <td>{item.product_name}</td>
                    <td style={{ fontWeight: 600 }}>{item.available_quantity.toLocaleString()}</td>
                    <td style={{ color: "#7b8794" }}>{item.reserved_quantity}</td>
                    <td style={{ color: "#7b8794" }}>{item.safe_stock}</td>
                    <td>¥{item.avg_cost}</td>
                    <td style={{ fontSize: 13, color: "#52606d" }}>
                      {item.last_inbound_date ? new Date(item.last_inbound_date).toLocaleDateString("zh-CN") : "-"}
                    </td>
                    <td>
                      {item.is_low_stock ? (
                        <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#ea580c", fontSize: 13 }}>
                          <AlertTriangle size={14} /> 库存预警
                        </span>
                      ) : (
                        <span style={{ color: "#c2410c", fontSize: 13 }}>正常</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderTop: "1px solid #e4e7eb" }}>
              <span style={{ fontSize: 13, color: "#52606d" }}>
                共 {total} 条，第 {page} / {totalPages} 页
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="secondary-button"
                  disabled={page === 1}
                  onClick={() => setPage(Math.max(1, page - 1))}
                >
                  上一页
                </button>
                <button
                  className="secondary-button"
                  disabled={page >= totalPages}
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
