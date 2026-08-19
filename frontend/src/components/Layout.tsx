import {
  ClipboardList,
  FileText,
  Gauge,
  Send,
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
} from "lucide-react";
import type { ReactNode } from "react";

const menuGroups = [
  {
    title: "首页",
    items: [{ id: "dashboard", label: "工作台", icon: Gauge }],
  },
  {
    title: "商品管理",
    items: [
      { id: "import", label: "商品采集", icon: Upload },
      { id: "drafts", label: "商品草稿", icon: FileText },
      { id: "publishing", label: "刊登任务", icon: Send },
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
      </aside>
      <main>{children}</main>
    </div>
  );
}
