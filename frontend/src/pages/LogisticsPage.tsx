import { useEffect, useState } from "react";
import { Search, Truck } from "lucide-react";
import {
  listShipments,
  SHIPPING_STATUS_LABELS,
  type ShipmentRecord,
} from "../api/erpClient";

export function LogisticsPage() {
  const [items, setItems] = useState<ShipmentRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [keyword, setKeyword] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      const result = await listShipments({
        status: status || undefined,
        keyword: keyword || undefined,
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
    void refresh();
  }, [page, status]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">物流管理</p>
          <h2>物流跟踪</h2>
          <p>对接物流渠道，实时跟踪包裹状态，异常预警。</p>
        </div>
      </header>

      <div className="metric-strip" style={{ marginBottom: 16 }}>
        <div><span>运输中</span><strong style={{ color: "#d97706" }}>
          {items.filter(i => i.status === "in_transit").length}
        </strong></div>
        <div><span>待发货</span><strong style={{ color: "#2563eb" }}>
          {items.filter(i => i.status === "pending").length}
        </strong></div>
        <div><span>已签收</span><strong style={{ color: "#059669" }}>
          {items.filter(i => i.status === "delivered").length}
        </strong></div>
        <div><span>异常</span><strong style={{ color: "#dc2626" }}>
          {items.filter(i => i.status === "exception" || i.status === "returned").length}
        </strong></div>
      </div>

      <div className="surface" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flex: 1, minWidth: 200 }}>
            <Search size={16} style={{ color: "#7b8794" }} />
            <input
              type="text"
              placeholder="搜索运单号、订单号"
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
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            style={{ padding: "8px 12px", border: "1px solid #dde3ea", borderRadius: 6, fontSize: 14 }}
          >
            <option value="">全部状态</option>
            {Object.entries(SHIPPING_STATUS_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
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
            <Truck size={28} />
            <strong>暂无物流单</strong>
            <p>没有符合条件的物流记录。</p>
          </div>
        )}
        {!loading && items.length > 0 && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>运单号</th>
                  <th>订单号</th>
                  <th>物流商</th>
                  <th>目的地址</th>
                  <th>运费</th>
                  <th>最新状态</th>
                  <th>状态更新</th>
                </tr>
              </thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 500 }}>
                      {s.tracking_number}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12, color: "#7b8794" }}>
                      {s.meli_order_id || "-"}
                    </td>
                    <td>{s.carrier || "-"}</td>
                    <td style={{ fontSize: 13 }}>{s.destination || "-"}</td>
                    <td>${s.shipping_fee}</td>
                    <td>
                      <span className={`status-tag status-${s.status}`}>
                        {SHIPPING_STATUS_LABELS[s.status] || s.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: "#52606d" }}>
                      {s.latest_status_time ? new Date(s.latest_status_time).toLocaleString("zh-CN") : "-"}
                      <div style={{ marginTop: 2, fontSize: 11, color: "#9aa5b1" }}>
                        {s.latest_status_text}
                      </div>
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
