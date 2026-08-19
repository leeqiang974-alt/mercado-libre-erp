import { useEffect, useState } from "react";
import { BarChart3, TrendingUp, ShoppingCart } from "lucide-react";
import {
  getSalesDaily,
  getErpOverview,
  type DailySalesPoint,
  type ErpOverview,
} from "../api/erpClient";

export function ReportsPage() {
  const [dailyData, setDailyData] = useState<DailySalesPoint[]>([]);
  const [overview, setOverview] = useState<ErpOverview | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const [d, o] = await Promise.all([
        getSalesDaily({ days }),
        getErpOverview(),
      ]);
      setDailyData(d);
      setOverview(o);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [days]);

  const maxSales = Math.max(...dailyData.map(d => parseFloat(d.sales)), 1);
  const maxOrders = Math.max(...dailyData.map(d => d.orders), 1);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">财务报表</p>
          <h2>运营报表</h2>
          <p>销售、订单、库存多维度数据分析。</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              className={days === d ? "" : "secondary-button"}
              onClick={() => setDays(d)}
            >
              近{d}天
            </button>
          ))}
        </div>
      </header>

      {loading && <div className="empty-state">加载中...</div>}

      {!loading && overview && (
        <>
          <div className="metric-strip" style={{ marginBottom: 24 }}>
            <div>
              <span>总销售额</span>
              <strong style={{ color: "#c2410c" }}>${overview.total_sales}</strong>
              <small style={{ color: "#7b8794", display: "block", marginTop: 4 }}>
                历史累计
              </small>
            </div>
            <div>
              <span>今日销售额</span>
              <strong style={{ color: "#c2410c" }}>${overview.today_sales}</strong>
              <small style={{ color: "#7b8794", display: "block", marginTop: 4 }}>
                {overview.today_orders} 单
              </small>
            </div>
            <div>
              <span>总订单数</span>
              <strong>{overview.total_orders}</strong>
              <small style={{ color: "#7b8794", display: "block", marginTop: 4 }}>
                待处理 {overview.pending_orders} 单
              </small>
            </div>
            <div>
              <span>库存预警</span>
              <strong style={{ color: "#ea580c" }}>{overview.low_stock_skus} 个</strong>
              <small style={{ color: "#7b8794", display: "block", marginTop: 4 }}>
                {overview.total_skus} 个 SKU
              </small>
            </div>
          </div>

          <div className="section-grid" style={{ marginBottom: 24 }}>
            <section className="surface">
              <h3>销售趋势</h3>
              <p style={{ fontSize: 13, color: "#7b8794", margin: "4px 0 16px" }}>
                每日销售额变化
              </p>
              <div style={{ height: 260, position: "relative" }}>
                <div style={{ display: "flex", alignItems: "flex-end", height: 220, gap: 1, borderBottom: "1px solid #e5e7eb" }}>
                  {dailyData.map((d, i) => {
                    const h = (parseFloat(d.sales) / maxSales) * 200;
                    return (
                      <div
                        key={i}
                        title={`${d.date}: $${d.sales}`}
                        style={{
                          flex: 1,
                          background: "linear-gradient(180deg, #f97316, #fdba74)",
                          borderRadius: "3px 3px 0 0",
                          height: Math.max(h, 2),
                          transition: "height 0.3s",
                        }}
                      />
                    );
                  })}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "#9ca3af" }}>
                  {dailyData.length > 0 && (
                    <>
                      <span>{dailyData[0]?.date?.slice(5)}</span>
                      <span>{dailyData[Math.floor(dailyData.length / 2)]?.date?.slice(5)}</span>
                      <span>{dailyData[dailyData.length - 1]?.date?.slice(5)}</span>
                    </>
                  )}
                </div>
              </div>
            </section>

            <section className="surface">
              <h3>订单量趋势</h3>
              <p style={{ fontSize: 13, color: "#7b8794", margin: "4px 0 16px" }}>
                每日订单数量变化
              </p>
              <div style={{ height: 260, position: "relative" }}>
                <div style={{ display: "flex", alignItems: "flex-end", height: 220, gap: 1, borderBottom: "1px solid #e5e7eb" }}>
                  {dailyData.map((d, i) => {
                    const h = (d.orders / maxOrders) * 200;
                    return (
                      <div
                        key={i}
                        title={`${d.date}: ${d.orders} 单`}
                        style={{
                          flex: 1,
                          background: "linear-gradient(180deg, #fb923c, #fdba74)",
                          borderRadius: "3px 3px 0 0",
                          height: Math.max(h, 2),
                        }}
                      />
                    );
                  })}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "#9ca3af" }}>
                  {dailyData.length > 0 && (
                    <>
                      <span>{dailyData[0]?.date?.slice(5)}</span>
                      <span>{dailyData[Math.floor(dailyData.length / 2)]?.date?.slice(5)}</span>
                      <span>{dailyData[dailyData.length - 1]?.date?.slice(5)}</span>
                    </>
                  )}
                </div>
              </div>
            </section>
          </div>

          <div className="surface">
            <h3>关键指标概览</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16, marginTop: 16 }}>
              <div style={{ padding: 16, background: "#f8fafc", borderRadius: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <ShoppingCart size={18} style={{ color: "#ea580c" }} />
                  <span style={{ fontSize: 13, color: "#52606d" }}>客单价</span>
                </div>
                <strong style={{ fontSize: 22 }}>
                  ${(parseFloat(overview.total_sales) / overview.total_orders).toFixed(2)}
                </strong>
              </div>
              <div style={{ padding: 16, background: "#f8fafc", borderRadius: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <TrendingUp size={18} style={{ color: "#c2410c" }} />
                  <span style={{ fontSize: 13, color: "#52606d" }}>今日订单</span>
                </div>
                <strong style={{ fontSize: 22 }}>{overview.today_orders}</strong>
                <span style={{ fontSize: 12, color: "#7b8794", marginLeft: 6 }}>单</span>
              </div>
              <div style={{ padding: 16, background: "#f8fafc", borderRadius: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <BarChart3 size={18} style={{ color: "#f59e0b" }} />
                  <span style={{ fontSize: 13, color: "#52606d" }}>库存 SKU</span>
                </div>
                <strong style={{ fontSize: 22 }}>{overview.total_skus}</strong>
                <span style={{ fontSize: 12, color: "#7b8794", marginLeft: 6 }}>个</span>
              </div>
              <div style={{ padding: 16, background: "#f8fafc", borderRadius: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <TrendingUp size={18} style={{ color: "#f59e0b" }} />
                  <span style={{ fontSize: 13, color: "#52606d" }}>待发货</span>
                </div>
                <strong style={{ fontSize: 22, color: "#c2410c" }}>{overview.pending_shipment}</strong>
                <span style={{ fontSize: 12, color: "#7b8794", marginLeft: 6 }}>单</span>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
