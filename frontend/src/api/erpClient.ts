const API_BASE = "";

async function get<T>(url: string): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

// ============ 统计概览 ============
export async function getErpOverview(): Promise<ErpOverview> {
  return get<ErpOverview>("/api/erp/overview");
}

export interface ErpOverview {
  total_orders: number;
  today_orders: number;
  pending_orders: number;
  total_sales: string;
  today_sales: string;
  total_skus: number;
  low_stock_skus: number;
  pending_shipment: number;
  currency: string;
  // 真实业务数据
  total_stores: number;
  total_drafts: number;
  pending_publish: number;
  published_count: number;
}

// ============ 订单 ============
export async function listOrders(params: {
  status?: string;
  site_id?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResult<OrderRecord>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.site_id) q.set("site_id", params.site_id);
  if (params.keyword) q.set("keyword", params.keyword);
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return get<PaginatedResult<OrderRecord>>(`/api/erp/orders?${q.toString()}`);
}

export async function getOrderDetail(orderId: number): Promise<OrderDetail> {
  return get<OrderDetail>(`/api/erp/orders/${orderId}`);
}

export interface OrderRecord {
  id: number;
  order_id: string;
  site_id: string;
  status: string;
  buyer_name: string;
  total_amount: string;
  currency_id: string;
  shipping_cost: string;
  tracking_number: string | null;
  order_date: string;
  payment_date: string | null;
  order_date_source: string | null;
  payment_date_source: string | null;
}

export interface OrderDetail extends OrderRecord {
  buyer_email: string;
  buyer_phone: string;
  shipping_address: string;
  shipping_city: string;
  shipping_state: string;
  shipping_zip_code: string;
  commission_fee: string;
  shipping_method: string;
  tracking_url: string | null;
  shipping_date: string | null;
  items: OrderItem[];
}

export interface OrderItem {
  id: number;
  item_id: string;
  sku: string;
  title: string;
  quantity: number;
  unit_price: string;
  variation_name: string;
  image_url: string | null;
}

// ============ 库存 ============
export async function listInventory(params: {
  warehouse_id?: number;
  keyword?: string;
  low_stock?: boolean;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResult<InventoryRecord>> {
  const q = new URLSearchParams();
  if (params.warehouse_id) q.set("warehouse_id", String(params.warehouse_id));
  if (params.keyword) q.set("keyword", params.keyword);
  if (params.low_stock) q.set("low_stock", "true");
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return get<PaginatedResult<InventoryRecord>>(`/api/erp/inventory?${q.toString()}`);
}

export async function listInventoryMovements(params: {
  sku?: string;
  warehouse_id?: number;
  movement_type?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResult<InventoryMovement>> {
  const q = new URLSearchParams();
  if (params.sku) q.set("sku", params.sku);
  if (params.warehouse_id) q.set("warehouse_id", String(params.warehouse_id));
  if (params.movement_type) q.set("movement_type", params.movement_type);
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return get<PaginatedResult<InventoryMovement>>(`/api/erp/inventory/movements?${q.toString()}`);
}

export interface InventoryRecord {
  id: number;
  sku: string;
  product_name: string;
  warehouse_id: number;
  quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  safe_stock: number;
  avg_cost: string;
  last_inbound_date: string | null;
  is_low_stock: boolean;
}

export interface InventoryMovement {
  id: number;
  sku: string;
  warehouse_id: number | null;
  movement_type: string;
  quantity_change: number;
  balance_after: number | null;
  reference_type: string | null;
  reference_id: string | null;
  remark: string | null;
  created_at: string;
}

// ============ 仓库 ============
export async function listWarehouses(): Promise<WarehouseRecord[]> {
  return get<WarehouseRecord[]>("/api/erp/warehouses");
}

export interface WarehouseRecord {
  id: number;
  name: string;
  code: string;
  address: string;
  contact_name: string;
  contact_phone: string;
}

// ============ 采购 ============
export async function listPurchaseOrders(params: {
  status?: string;
  supplier_id?: number;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResult<PurchaseOrderRecord>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.supplier_id) q.set("supplier_id", String(params.supplier_id));
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return get<PaginatedResult<PurchaseOrderRecord>>(`/api/erp/purchase-orders?${q.toString()}`);
}

export async function listSuppliers(): Promise<SupplierRecord[]> {
  return get<SupplierRecord[]>("/api/erp/suppliers");
}

export interface PurchaseOrderRecord {
  id: number;
  po_number: string;
  supplier_id: number | null;
  warehouse_id: number | null;
  status: string;
  total_cost: string;
  currency: string;
  expected_date: string | null;
  created_at: string;
}

export interface SupplierRecord {
  id: number;
  name: string;
  contact_name: string;
  contact_phone: string;
  contact_qq: string;
}

// ============ 物流 ============
export async function listShipments(params: {
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResult<ShipmentRecord>> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.keyword) q.set("keyword", params.keyword);
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  return get<PaginatedResult<ShipmentRecord>>(`/api/erp/shipments?${q.toString()}`);
}

export interface ShipmentRecord {
  id: number;
  tracking_number: string;
  meli_order_id: string | null;
  carrier: string | null;
  shipping_method: string | null;
  status: string;
  destination: string | null;
  shipping_fee: string;
  latest_status_text: string | null;
  latest_status_time: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  created_at: string;
}

// ============ 财务 ============
export async function getProfitSummary(params: {
  days?: number;
  site_id?: string;
} = {}): Promise<ProfitSummary> {
  const q = new URLSearchParams();
  if (params.days) q.set("days", String(params.days));
  if (params.site_id) q.set("site_id", params.site_id);
  return get<ProfitSummary>(`/api/erp/profit/summary?${q.toString()}`);
}

export async function getProfitDaily(params: {
  days?: number;
  site_id?: string;
} = {}): Promise<DailyProfitPoint[]> {
  const q = new URLSearchParams();
  if (params.days) q.set("days", String(params.days));
  if (params.site_id) q.set("site_id", params.site_id);
  return get<DailyProfitPoint[]>(`/api/erp/profit/daily?${q.toString()}`);
}

export async function getTopProductsProfit(params: {
  days?: number;
  site_id?: string;
  limit?: number;
} = {}): Promise<ProductProfit[]> {
  const q = new URLSearchParams();
  if (params.days) q.set("days", String(params.days));
  if (params.site_id) q.set("site_id", params.site_id);
  if (params.limit) q.set("limit", String(params.limit));
  return get<ProductProfit[]>(`/api/erp/profit/top-products?${q.toString()}`);
}

export interface ProfitSummary {
  orders_count: number;
  total_sales: string;
  total_product_cost: string;
  total_shipping_cost: string;
  total_platform_fee: string;
  total_gross_profit: string;
  total_net_profit: string;
  net_margin: string;
  currency: string;
  days: number;
}

export interface DailyProfitPoint {
  date: string;
  sales: string;
  profit: string;
}

export interface ProductProfit {
  sku: string;
  quantity: number;
  sales: string;
  profit: string;
}

// ============ 销售趋势 ============
export async function getSalesDaily(params: {
  days?: number;
  site_id?: string;
} = {}): Promise<DailySalesPoint[]> {
  const q = new URLSearchParams();
  if (params.days) q.set("days", String(params.days));
  if (params.site_id) q.set("site_id", params.site_id);
  return get<DailySalesPoint[]>(`/api/erp/sales/daily?${q.toString()}`);
}

export interface DailySalesPoint {
  date: string;
  orders: number;
  sales: string;
  items: number;
}

// ============ 公共类型 ============
export interface PaginatedResult<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

// 订单状态中文映射
export const ORDER_STATUS_LABELS: Record<string, string> = {
  payment_required: "待付款",
  paid: "已付款",
  packing: "备货中",
  shipped: "已发货",
  delivered: "已送达",
  cancelled: "已取消",
  returned: "已退货",
  refunded: "已退款",
};

// 物流状态中文映射
export const SHIPPING_STATUS_LABELS: Record<string, string> = {
  pending: "待发货",
  picked: "已揽收",
  in_transit: "运输中",
  delivered: "已签收",
  exception: "异常",
  returned: "退回",
};

// 采购状态中文映射
export const PURCHASE_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  submitted: "已下单",
  partial: "部分到货",
  received: "全部到货",
  cancelled: "已取消",
};

// 库存变动类型中文映射
export const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  inbound: "入库",
  outbound: "出库",
  adjustment: "调整",
  transfer: "调拨",
};
