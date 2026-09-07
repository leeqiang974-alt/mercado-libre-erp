import {
  Activity,
  ClipboardList,
  FilePenLine,
  Gauge,
  Store,
  Upload,
  ShoppingCart,
  Package,
  Truck,
  DollarSign,
  Users,
  Settings,
  Bell,
  BarChart3,
  Warehouse,
  ShoppingBag,
  MessageSquare,
  ListPlus,
  Layers,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { getLlmProviders, setLlmProvider, type LlmProviderInfo } from "../api/erpClient";

const menuGroups = [
  {
    title: "首页",
    items: [{ id: "dashboard", label: "工作台", icon: Gauge }],
  },
  {
    title: "商品管理",
    items: [
      { id: "import", label: "智能采集", icon: Upload },
      { id: "collection-tasks", label: "采集任务", icon: ListPlus },
      { id: "bulk-selection", label: "批量选品", icon: Layers },
      { id: "drafts", label: "上架库", icon: FilePenLine },
      { id: "products", label: "店铺已上架", icon: Package },
    ],
  },
  {
    title: "订单管理",
    items: [{ id: "orders", label: "订单列表", icon: ShoppingCart }],
  },
  {
    title: "库存管理",
    items: [
      { id: "inventory", label: "库存查询", icon: Package },
      { id: "warehouse", label: "仓库管理", icon: Warehouse },
    ],
  },
  {
    title: "采购管理",
    items: [{ id: "purchase", label: "采购单", icon: ShoppingBag }],
  },
  {
    title: "物流管理",
    items: [{ id: "logistics", label: "物流跟踪", icon: Truck }],
  },
  {
    title: "客户服务",
    items: [{ id: "messages", label: "消息中心", icon: MessageSquare }],
  },
  {
    title: "财务报表",
    items: [
      { id: "finance", label: "利润核算", icon: DollarSign },
      { id: "reports", label: "运营报表", icon: BarChart3 },
    ],
  },
  {
    title: "店铺设置",
    items: [
      { id: "stores", label: "店铺管理", icon: Store },
      { id: "audit", label: "操作日志", icon: ClipboardList },
      { id: "diagnostics", label: "系统诊断", icon: Activity },
    ],
  },
];

export function Layout({
  page,
  onPageChange,
  children,
}: {
  page: string;
  onPageChange: (page: string) => void;
  children: ReactNode;
}) {
  const [llmProviders, setLlmProviders] = useState<LlmProviderInfo[]>([]);
  const [llmCurrent, setLlmCurrent] = useState("");
  const [llmSwitching, setLlmSwitching] = useState(false);

  useEffect(() => {
    getLlmProviders()
      .then((data) => {
        setLlmProviders(data.providers);
        setLlmCurrent(data.current);
      })
      .catch(() => {
        /* 后端不可用时静默降级，不影响导航 */
      });
  }, []);

  const onLlmChange = async (provider: string) => {
    setLlmSwitching(true);
    try {
      const result = await setLlmProvider(provider);
      setLlmCurrent(result.provider);
    } catch {
      /* 切换失败保留原选择 */
    }
    setLlmSwitching(false);
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>美客多 ERP</h1>
        <div className="sidebar-subtitle">XUANX-ERP</div>
        {menuGroups.map((group) => (
          <div key={group.title} className="sidebar-group">
            <div className="sidebar-group-title">{group.title}</div>
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  className={page === item.id ? "active" : ""}
                  key={item.id}
                  onClick={() => onPageChange(item.id)}
                  title={item.label}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        ))}
              <div className="sidebar-group sidebar-llm-group">
          <div className="sidebar-group-title">AI 模型</div>
          <select
            className="sidebar-llm-select"
            value={llmCurrent}
            disabled={llmSwitching}
            onChange={(event) => onLlmChange(event.target.value)}
            title="上架库 AI 内容生成使用的模型"
          >
            {llmProviders.length === 0 && <option value="">加载中…</option>}
            {llmProviders.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}（{provider.model}）
              </option>
            ))}
          </select>
        </div>
      </aside>
      <main>{children}</main>
    </div>
  );
}
