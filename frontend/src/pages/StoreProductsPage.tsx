import { useEffect, useState } from "react";
import { ExternalLink, Package, RefreshCw, Search, Store, TrendingUp } from "lucide-react";
import { getStoreItemPriceReference, listStoreItems, listStores, type StoreItem, type StoreItemPriceReference, type StoreRecord } from "../api/client";

export function StoreProductsPage() {
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [items, setItems] = useState<StoreItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [priceReferences, setPriceReferences] = useState<Record<string, StoreItemPriceReference>>({});
  const [loadingReferenceId, setLoadingReferenceId] = useState("");
  const limit = 30;

  const connected = stores.filter((store) => store && store.oauth_status === "connected");
  async function load(nextOffset = offset) {
    if (!storeId) return;
    setLoading(true); setError("");
    try {
      const result = await listStoreItems(Number(storeId), { limit, offset: nextOffset, search });
      setItems(Array.isArray(result.items) ? result.items : []); setTotal(Number(result.total) || 0); setOffset(nextOffset); setPriceReferences({});
    } catch (loadError) { setError(loadError instanceof Error ? loadError.message : "加载店铺商品失败"); }
    finally { setLoading(false); }
  }
  useEffect(() => { void listStores().then((rows) => { setStores(rows); setStoreId(rows.find((store) => store.site_id === "CBT" && store.oauth_status === "connected")?.id ?? rows.find((store) => store.oauth_status === "connected")?.id ?? ""); }); }, []);
  useEffect(() => { if (storeId) void load(0); }, [storeId]);

  async function loadPriceReference(itemId: string) {
    if (!storeId) return;
    setLoadingReferenceId(itemId); setError("");
    try {
      const reference = await getStoreItemPriceReference(Number(storeId), itemId);
      setPriceReferences((current) => ({ ...current, [itemId]: reference }));
    } catch (loadError) { setError(loadError instanceof Error ? loadError.message : "读取官方价格参考失败"); }
    finally { setLoadingReferenceId(""); }
  }

  return <section className="workspace">
    <header className="page-header"><div><p className="eyebrow">商品管理</p><h2>店铺商品</h2><p>读取美客多真实在售、停售、销量、物流与刊登信息；不使用演示数据。</p></div><span className="record-id">{total} 个商品</span></header>
    <section className="surface product-filter-bar">
      <label><Store size={16} /> 店铺<select value={storeId} onChange={(event) => setStoreId(event.target.value)}>{connected.map((store) => <option key={store.id} value={store.id}>{store.display_name} · {store.site_id} · {store.seller_id}</option>)}</select></label>
      <label className="product-search"><Search size={16} /><input value={search} placeholder="按标题或 SKU 搜索" onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void load(0)} /></label>
      <button className="secondary-button" disabled={!storeId || loading} onClick={() => void load(0)}><RefreshCw className={loading ? "spin" : ""} size={16} /> 查询</button>
    </section>
    {error && <p className="inline-warning">{error}</p>}
    <section className="surface store-products-table">
      {loading && <div className="empty-state">正在读取美客多商品...</div>}
      {!loading && items.length === 0 && <div className="empty-state"><Package size={28} /><strong>没有匹配商品</strong></div>}
      {!loading && items.length > 0 && <table className="data-table"><thead><tr><th>商品</th><th>售价 / 销量</th><th>刊登与物流</th><th>官方价格参考</th><th>库存 / 状态</th><th>操作</th></tr></thead><tbody>{items.map((item) => {
        const reference = priceReferences[item.id];
        return <tr key={item.id}><td className="store-product-title">{item.thumbnail ? <img src={item.thumbnail} alt="" /> : <span className="product-image image-placeholder"><Package size={18} /></span>}<span><strong>{item.title || item.id}</strong><small><code>{item.id}</code> · <code>{item.category_id || "-"}</code></small></span></td><td><strong>{item.price ?? "-"} {item.currency_id}</strong><small><TrendingUp size={13} /> 已售 {item.sold_quantity ?? 0} 件</small></td><td><strong>{item.listing_type_id === "gold_pro" ? "高级" : item.listing_type_id === "gold_special" ? "经典" : item.listing_type_id || "-"}</strong><small>{item.free_shipping ? "提供免费配送" : "不提供免费配送"}</small><small>{item.shipping_logistic_type || item.shipping_mode || "物流待配置"}</small></td><td>{reference?.availability === "available" ? <><strong>{reference.suggested_price?.amount ?? "-"} {reference.currency_id} 建议价</strong><small>销售费 {reference.selling_fees ?? "-"} · 运费 {reference.shipping_fees ?? "-"} · 税费 {reference.estimated_taxes?.amount ?? "-"}</small><small>{reference.estimated_after_reference_costs === null ? "官方成本字段不完整，无法试算" : `参考成本后 ${reference.estimated_after_reference_costs} ${reference.currency_id}`}</small></> : reference?.availability === "unavailable" ? <><strong className="pending-income">{reference.reason === "requires_marketplace_child_item" ? "需市场子商品报价" : "暂无官方价格参考"}</strong><small>{reference.reason === "requires_marketplace_child_item" ? "官方报价针对活动的 MLA/MLB/MLM 等市场子商品，不能直接用 CBT 父商品查询" : "该商品当前未获得官方建议，不代表价格或收益为零"}</small></> : <><button className="secondary-button" disabled={loadingReferenceId === item.id} onClick={() => void loadPriceReference(item.id)}>{loadingReferenceId === item.id ? "查询中..." : "查询价格参考"}</button><small>按需读取官方建议价、费用和税费</small></>}</td><td><strong>{item.available_quantity ?? "-"} 件</strong><small>{item.warranty || "未返回质保"}</small><span className={`state-pill ${item.status === "active" ? "ready" : ""}`}>{item.status || (item.load_error ? "详情读取失败" : "-")}</span></td><td className="store-product-actions">{item.permalink ? <a className="icon-button" href={item.permalink} target="_blank" rel="noreferrer" title="打开美客多商品"><ExternalLink size={16} /></a> : <span title="CBT 父商品没有公开链接；详情页将展示各站点子商品链接">无公开链接</span>}<button className="secondary-button" title="商品详情与编辑即将接入" disabled>详情 / 修改</button></td></tr>;
      })}</tbody></table>}
      {total > limit && <div className="table-pagination"><span>第 {Math.floor(offset / limit) + 1} 页，共 {total} 个</span><div><button className="secondary-button" disabled={loading || offset === 0} onClick={() => void load(Math.max(0, offset - limit))}>上一页</button><button className="secondary-button" disabled={loading || offset + limit >= total} onClick={() => void load(offset + limit)}>下一页</button></div></div>}
    </section>
  </section>;
}
