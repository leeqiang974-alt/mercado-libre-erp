import { useEffect, useState } from "react";
import { DollarSign, TrendingUp, TrendingDown, PieChart } from "lucide-react";
import {
  getProfitSummary,
  getProfitDaily,
  getTopProductsProfit,
  type ProfitSummary,
  type DailyProfitPoint,
  type ProductProfit,
} from "../api/erpClient";

export function FinancePage() {
  const [summary, setSummary] = useState<ProfitSummary | null>(null);
  const [dailyData, setDailyData] = useState<DailyProfitPoint[]>([]);
  const [topProducts, setTopProducts] = useState<ProductProfit[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const [s, d, t] = await Promise.all([
        getProfitSummary({ days }),
        getProfitDaily({ days }),
        getTopProductsProfit({ days, limit: 10 }),
      ]);
      setSummary(s);
      setDailyData(d);
      setTopProducts(t);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [days]);

  // 计算最大销售额用于柱状图比例
  const maxSales = Math.max(...dailyData.map(d => parseFloat(d.sales)), 1);
  const maxProfit = Math.max(...topProducts.map(p => parseFloat(p.profit)), 1);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">财务报表</p>
          <h2>利润核算</h2>
          <p>按商品、订单、店铺维度核算真实利润。</p>
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

      {!loading && summary && (
        <>
          <div className="metric-strip" style={{ marginBottom: 16 }}>
            <div>
              <span>销售额</span>
              <strong style={{ color: "#c2410c" }}>${summary.total_sales}</strong>
              <small style={{ color: "#7b8794", display: "block", marginTop: 4 }}>
                {summary.orders_count} 笔订单
              </small>
            </div>
            <div>
              <span>商品成本</span>
              <strong>${summary.total_product_cost}</strong>
            </div>
            <div>
              <span>物流费用</span>
              <strong>${summary.total_shipping_cost}</strong>
            </div>
            <div>
              <span>平台佣金</span>
              <strong>${summary.total_platform_fee}</strong>
            </div>
          </div>

          <div className="metric-strip" style={{ marginBottom: 24 }}>
            <div style={{ borderLeft: "3px solid #fb923c" }}>
              <span>毛利润</span>
              <strong style={{ color: "#c2410c" }}>${summary.total_gross_profit}</strong>
            </div>
            <div style={{ borderLeft: "3px solid #2563eb" }}>
              <span>净利润</span>
              <strong style={{ color: "#c2410c" }}>${summary.total_net_profit}</strong>
            </div>
            <div style={{ borderLeft: `3px solid ${parseFloat(summary.net_margin) >= 20 ? "#fb923c" : "#ea580c"}` }}>
              <span>净利率</span>
              <strong style={{ color: parseFloat(summary.net_margin) >= 20 ? "#c2410c" : "#d97706" }}>
                {summary.net_margin}%
              </strong>
            </div>
            <div>
              <span>统计周期</span>
              <strong>{summary.days} 天</strong>
            </div>
          </div>

          <div className="section-grid" style={{ marginBottom: 24 }}>
            <section className="surface">
              <h3>销售与利润趋势</h3>
              <div style={{ marginTop: 16, height: 220, position: "relative" }}>
                <div style={{ display: "flex", alignItems: "flex-end", height: 180, gap: 2, borderBottom: "1px solid #e5e7eb" }}>
                  {dailyData.map((d, i) => {
                    const h = (parseFloat(d.sales) / maxSales) * 150;
                    const pH = (parseFloat(d.profit) / maxSales) * 150;
                    return (
                      <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                        <div style={{ width: "100%", height: h, background: "#f97316", borderRadius: "2px 2px 0 0", minHeight: 2 }} title={`销售额: $${d.sales}`} />
                        <div style={{ width: "60%", height: pH, background: "#fb923c", borderRadius: "2px 2px 0 0", minHeight: 1 }} title={`利润: $${d.profit}`} />
                      </div>
                    );
                  })}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "#9ca3af" }}>
                  <span>{dailyData[0]?.date?.slice(5)}</span>
                  <span>{dailyData[Math.floor(dailyData.length / 2)]?.date?.slice(5)}</span>
                  <span>{dailyData[dailyData.length - 1]?.date?.slice(5)}</span>
                </div>
              </div>
              <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 12, justifyContent: "center" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 12, height: 12, background: "#f97316", display: "inline-block" }}></span>
                  销售额
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ width: 12, height: 12, background: "#fb923c", display: "inline-block" }}></span>
                  净利润
                </span>
              </div>
            </section>

            <section className="surface">
              <h3>商品利润排行</h3>
              <div style={{ marginTop: 16 }}>
                {topProducts.length === 0 && <p style={{ color: "#7b8794" }}>暂无数据</p>}
                {topProducts.map((p, i) => (
                  <div key={p.sku} style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                      <span style={{ fontWeight: 500 }}>
                        <span style={{ color: "#9ca3af", marginRight: 6 }}>{i + 1}.</span>
                        {p.sku}
                      </span>
                      <span style={{ color: "#c2410c", fontWeight: 600 }}>${p.profit}</span>
                    </div>
                    <div style={{ height: 8, background: "#e5e7eb", borderRadius: 4, overflow: "hidden" }}>
                      <div
                        style={{
                          width: `${(parseFloat(p.profit) / maxProfit) * 100}%`,
                          height: "100%",
                          background: i < 3 ? "#ea580c" : "#fb923c",
                        }}
                      />
                    </div>
                    <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                      销量 {p.quantity} · 销售 ${p.sales}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <div className="surface">
            <h3>成本构成</h3>
            <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 24 }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>商品成本</span>
                  <span style={{ fontWeight: 500 }}>${summary.total_product_cost}</span>
                </div>
                <div style={{ height: 10, background: "#e5e7eb", borderRadius: 5, overflow: "hidden" }}>
                  <div style={{ width: `${(parseFloat(summary.total_product_cost) / parseFloat(summary.total_sales)) * 100}%`, height: "100%", background: "#f97316" }} />
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>物流费用</span>
                  <span style={{ fontWeight: 500 }}>${summary.total_shipping_cost}</span>
                </div>
                <div style={{ height: 10, background: "#e5e7eb", borderRadius: 5, overflow: "hidden" }}>
                  <div style={{ width: `${(parseFloat(summary.total_shipping_cost) / parseFloat(summary.total_sales)) * 100}%`, height: "100%", background: "#ea580c" }} />
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>平台佣金</span>
                  <span style={{ fontWeight: 500 }}>${summary.total_platform_fee}</span>
                </div>
                <div style={{ height: 10, background: "#e5e7eb", borderRadius: 5, overflow: "hidden" }}>
                  <div style={{ width: `${(parseFloat(summary.total_platform_fee) / parseFloat(summary.total_sales)) * 100}%`, height: "100%", background: "#fb923c" }} />
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
