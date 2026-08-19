import { useEffect, useState } from "react";
import { Search, Filter, Package } from "lucide-react";
import {
  listOrders,
  getOrderDetail,
  ORDER_STATUS_LABELS,
  type OrderRecord,
  type OrderDetail,
} from "../api/erpClient";

function formatMarketplaceTime(source: string | null, fallback: string | null) {
  if (source) {
    return source.replace("T", " ").replace(/\.\d+(?=Z|[+-]\d{2}:\d{2}$)/, "");
  }
  return fallback ? `${fallback.replace("T", " ").replace(/\.\d+Z$/, "")} UTC` : "-";
}

function formatBeijingTime(source: string | null) {
  return source
    ? new Intl.DateTimeFormat("zh-CN", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      }).format(new Date(source))
    : "-";
}

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [keyword, setKeyword] = useState("");
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const result = await listOrders({
        status: status || undefined,
        keyword: keyword || undefined,
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
    void refresh();
  }, [page, status]);

  async function openDetail(order: OrderRecord) {
    setDetailLoading(true);
    try {
      const detail = await getOrderDetail(order.id);
      setSelectedOrder(detail);
    } finally {
      setDetailLoading(false);
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">订单管理</p>
          <h2>订单列表</h2>
          <p>查看和管理各店铺订单，支持搜索、筛选和详情查看。</p>
        </div>
      </header>

      <div className="surface" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flex: 1, minWidth: 200 }}>
            <Search size={16} style={{ color: "#57534e" }} />
            <input
              type="text"
              placeholder="搜索订单号、买家姓名"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (setPage(1), void refresh())}
              style={{
                flex: 1,
                padding: "8px 12px",
                border: "1px solid #dde3ea",
                borderRadius: 6,
                fontSize: 14,
              }}
            />
          </div>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            style={{ padding: "8px 12px", border: "1px solid #dde3ea", borderRadius: 6, fontSize: 14 }}
          >
            <option value="">全部状态</option>
            {Object.entries(ORDER_STATUS_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <button
            className="secondary-button"
            onClick={() => { setPage(1); void refresh(); }}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <Filter size={16} /> 筛选
          </button>
        </div>
      </div>

      <div className="surface">
        {loading && <div className="empty-state">加载中...</div>}
        {!loading && orders.length === 0 && (
          <div className="empty-state">
            <Package size={28} />
            <strong>暂无订单</strong>
            <p>暂无符合条件的订单记录。</p>
          </div>
        )}
        {!loading && orders.length > 0 && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>订单号</th>
                  <th>站点</th>
                  <th>买家</th>
                  <th>状态</th>
                  <th>金额</th>
                  <th>运单号</th>
                  <th>下单时间（美客多）</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 13 }}>{order.order_id}</td>
                    <td>{order.site_id}</td>
                    <td>{order.buyer_name}</td>
                    <td>
                      <span className={`status-tag status-${order.status}`}>
                        {ORDER_STATUS_LABELS[order.status] || order.status}
                      </span>
                    </td>
                    <td>${order.total_amount} {order.currency_id}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 12, color: "#57534e" }}>
                      {order.tracking_number || "-"}
                    </td>
                    <td style={{ fontSize: 13, color: "#52606d" }}>
                      {formatMarketplaceTime(order.order_date_source, order.order_date)}
                    </td>
                    <td>
                      <button
                        className="link-button"
                        onClick={() => void openDetail(order)}
                      >
                        查看详情
                      </button>
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

      {selectedOrder && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setSelectedOrder(null)}
        >
          <div
            style={{
              background: "white", borderRadius: 12, padding: 24,
              maxWidth: 700, width: "90%", maxHeight: "85vh", overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>订单详情</h3>
              <button className="secondary-button" onClick={() => setSelectedOrder(null)}>关闭</button>
            </div>
            {detailLoading && <p>加载中...</p>}
            {!detailLoading && selectedOrder && (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
                  <div><strong>订单号：</strong>{selectedOrder.order_id}</div>
                  <div><strong>站点：</strong>{selectedOrder.site_id}</div>
                  <div><strong>状态：</strong>
                    <span className={`status-tag status-${selectedOrder.status}`}>
                      {ORDER_STATUS_LABELS[selectedOrder.status] || selectedOrder.status}
                    </span>
                  </div>
                  <div><strong>金额：</strong>${selectedOrder.total_amount} {selectedOrder.currency_id}</div>
                  <div><strong>买家：</strong>{selectedOrder.buyer_name}</div>
                  <div><strong>电话：</strong>{selectedOrder.buyer_phone}</div>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <strong>收货地址：</strong>
                    {selectedOrder.shipping_address}, {selectedOrder.shipping_city}, {selectedOrder.shipping_state} {selectedOrder.shipping_zip_code}
                  </div>
                  <div><strong>下单时间（美客多）：</strong>
                    {formatMarketplaceTime(selectedOrder.order_date_source, selectedOrder.order_date)}
                  </div>
                  <div><strong>付款时间（美客多）：</strong>
                    {formatMarketplaceTime(selectedOrder.payment_date_source, selectedOrder.payment_date)}
                  </div>
                  <div><strong>下单时间（北京时间）：</strong>
                    {formatBeijingTime(selectedOrder.order_date_source || selectedOrder.order_date)}
                  </div>
                  <div><strong>付款时间（北京时间）：</strong>
                    {formatBeijingTime(selectedOrder.payment_date_source || selectedOrder.payment_date)}
                  </div>
                  <div><strong>运单号：</strong>{selectedOrder.tracking_number || "-"}</div>
                  <div><strong>物流方式：</strong>{selectedOrder.shipping_method || "-"}</div>
                </div>

                <h4 style={{ margin: "16px 0 8px" }}>商品明细</h4>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>图片</th>
                      <th>SKU</th>
                      <th>商品名称</th>
                      <th>变体</th>
                      <th>数量</th>
                      <th>单价</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedOrder.items?.map((item) => (
                      <tr key={item.id}>
                        <td>
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt={item.title || item.item_id}
                              style={{ width: 56, height: 56, objectFit: "cover", borderRadius: 6, border: "1px solid #e4e7eb" }}
                            />
                          ) : <span style={{ color: "#9aa5b1", fontSize: 12 }}>无图片</span>}
                        </td>
                        <td style={{ fontFamily: "monospace", fontSize: 12 }}>{item.sku}</td>
                        <td>{item.title}</td>
                        <td>{item.variation_name || "-"}</td>
                        <td>{item.quantity}</td>
                        <td>${item.unit_price}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
