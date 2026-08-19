import { useEffect, useState } from "react";
import { Search, ShoppingBag } from "lucide-react";
import {
  listPurchaseOrders,
  listSuppliers,
  PURCHASE_STATUS_LABELS,
  type PurchaseOrderRecord,
  type SupplierRecord,
} from "../api/erpClient";

export function PurchasePage() {
  const [orders, setOrders] = useState<PurchaseOrderRecord[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [supplierId, setSupplierId] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      const result = await listPurchaseOrders({
        status: status || undefined,
        supplier_id: supplierId ? parseInt(supplierId) : undefined,
        page,
        page_size: pageSize,
      });
      setOrders(result.items);
      setTotal(result.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void listSuppliers().then(setSuppliers);
  }, []);

  useEffect(() => {
    void refresh();
  }, [page, status, supplierId]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">采购管理</p>
          <h2>采购单</h2>
          <p>供应商管理、采购订单、到货入库全流程。</p>
        </div>
      </header>

      <div className="surface" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <select
            value={supplierId}
            onChange={(e) => { setSupplierId(e.target.value); setPage(1); }}
            style={{ padding: "8px 12px", border: "1px solid #dde3ea", borderRadius: 6, fontSize: 14, minWidth: 180 }}
          >
            <option value="">全部供应商</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            style={{ padding: "8px 12px", border: "1px solid #dde3ea", borderRadius: 6, fontSize: 14 }}
          >
            <option value="">全部状态</option>
            {Object.entries(PURCHASE_STATUS_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="surface">
        {loading && <div className="empty-state">加载中...</div>}
        {!loading && orders.length === 0 && (
          <div className="empty-state">
            <ShoppingBag size={28} />
            <strong>暂无采购单</strong>
            <p>没有符合条件的采购单。</p>
          </div>
        )}
        {!loading && orders.length > 0 && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>采购单号</th>
                  <th>供应商</th>
                  <th>状态</th>
                  <th>总金额</th>
                  <th>预计到货</th>
                  <th>创建时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 13, fontWeight: 500 }}>
                      {o.po_number}
                    </td>
                    <td>{suppliers.find(s => s.id === o.supplier_id)?.name || "-"}</td>
                    <td>
                      <span className={`status-tag status-${o.status}`}>
                        {PURCHASE_STATUS_LABELS[o.status] || o.status}
                      </span>
                    </td>
                    <td>¥{o.total_cost} {o.currency}</td>
                    <td style={{ fontSize: 13, color: "#52606d" }}>
                      {o.expected_date ? new Date(o.expected_date).toLocaleDateString("zh-CN") : "-"}
                    </td>
                    <td style={{ fontSize: 13, color: "#52606d" }}>
                      {new Date(o.created_at).toLocaleDateString("zh-CN")}
                    </td>
                    <td>
                      <button className="link-button">查看详情</button>
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
