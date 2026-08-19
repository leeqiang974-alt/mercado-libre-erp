import { useEffect, useState } from "react";
import {
  Package,
  ShoppingCart,
  Store,
  TrendingUp,
  DollarSign,
  Truck,
  FileText,
  Rocket,
  RefreshCw,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { getErpOverview, type ErpOverview } from "../api/erpClient";

export function DashboardPage({ onNavigate }: { onNavigate: (page: string) => void }) {
  const [overview, setOverview] = useState<ErpOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setOverview(await getErpOverview());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const stats = [
    { label: "已授权店铺", value: overview?.total_stores || 0, icon: Store, color: "#ea580c", page: "stores" },
    { label: "商品草稿", value: overview?.total_drafts || 0, icon: FileText, color: "#2563eb", page: "drafts" },
    { label: "待刊登", value: overview?.pending_publish || 0, icon: Rocket, color: "#d97706", page: "publishing" },
    { label: "已刊登", value: overview?.published_count || 0, icon: Package, color: "#059669", page: "publishing" },
  ];

  const orderStats = [
    { label: "总订单数", value: overview?.total_orders || 0, icon: ShoppingCart },
    { label: "今日订单", value: overview?.today_orders || 0, icon: TrendingUp },
    { label: "待发货", value: overview?.pending_shipment || 0, icon: Truck },
    { label: "总销售额", value: `$${overview?.total_sales || "0"}`, icon: DollarSign },
  ];

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">运营总览</p>
          <h2>工作台</h2>
          <p>美客多跨境电商 ERP - 商品采集、智能审核、一键刊登</p>
        </div>
        <button className="secondary-button" onClick={() => void refresh()}>
          <RefreshCw size={14} /> 刷新
        </button>
      </header>

      {error && (
        <div className="error-banner">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* 核心业务指标 */}
      <div className="metric-strip">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="metric-card" onClick={() => onNavigate(s.page)}>
              <div className="metric-icon" style={{ background: `${s.color}15`, color: s.color }}>
                <Icon size={20} />
              </div>
              <div>
                <span>{s.label}</span>
                <strong>{s.value}</strong>
              </div>
              <ChevronRight size={16} className="metric-arrow" />
            </div>
          );
        })}
      </div>

      {/* 订单与销售 */}
      <div className="section-grid">
        <section className="surface">
          <h3>订单与销售</h3>
          <div className="order-stats">
            {orderStats.map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.label} className="order-stat-item">
                  <Icon size={18} style={{ color: "#ea580c" }} />
                  <div>
                    <span>{s.label}</span>
                    <strong>{s.value}</strong>
                  </div>
                </div>
              );
            })}
          </div>
          {overview && overview.total_orders === 0 && (
            <div className="empty-tip">
              <AlertCircle size={16} />
              <span>暂无订单数据，订单同步功能待 Marketplace API 权限开通后启用</span>
            </div>
          )}
        </section>

        <section className="surface">
          <h3>快捷操作</h3>
          <div className="quick-actions">
            <button onClick={() => onNavigate("import")}>
              <Package size={18} />
              <div>
                <strong>采集商品</strong>
                <span>从 Amazon 导入商品</span>
              </div>
              <ChevronRight size={16} />
            </button>
            <button onClick={() => onNavigate("drafts")}>
              <FileText size={18} />
              <div>
                <strong>编辑草稿</strong>
                <span>完善商品信息并刊登</span>
              </div>
              <ChevronRight size={16} />
            </button>
            <button onClick={() => onNavigate("orders")}>
              <ShoppingCart size={18} />
              <div>
                <strong>订单管理</strong>
                <span>查看和处理订单</span>
              </div>
              <ChevronRight size={16} />
            </button>
            <button onClick={() => onNavigate("stores")}>
              <Store size={18} />
              <div>
                <strong>店铺管理</strong>
                <span>授权和管理店铺</span>
              </div>
              <ChevronRight size={16} />
            </button>
          </div>
        </section>
      </div>

      {/* 库存与物流 */}
      <div className="section-grid">
        <section className="surface">
          <h3>库存概览</h3>
          <div className="inventory-summary">
            <div className="inv-item">
              <span>SKU 总数</span>
              <strong>{overview?.total_skus || 0}</strong>
            </div>
            <div className="inv-item">
              <span>低库存预警</span>
              <strong className="warning">{overview?.low_stock_skus || 0}</strong>
            </div>
          </div>
          <button className="secondary-button full-width" onClick={() => onNavigate("inventory")}>
            查看库存详情
          </button>
        </section>

        <section className="surface">
          <h3>使用指南</h3>
          <div className="guide-steps">
            <div className="guide-step">
              <span className="step-num">1</span>
              <div>
                <strong>授权店铺</strong>
                <p>在店铺管理中授权美客多店铺</p>
              </div>
            </div>
            <div className="guide-step">
              <span className="step-num">2</span>
              <div>
                <strong>采集商品</strong>
                <p>从 Amazon 导入商品信息生成草稿</p>
              </div>
            </div>
            <div className="guide-step">
              <span className="step-num">3</span>
              <div>
                <strong>编辑刊登</strong>
                <p>完善类目、价格、物流后一键刊登</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}