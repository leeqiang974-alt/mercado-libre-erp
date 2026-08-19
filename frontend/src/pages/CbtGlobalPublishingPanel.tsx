import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Globe2,
  Image,
  ListChecks,
  RefreshCw,
  Save,
  Search,
  Store,
} from "lucide-react";
import {
  getCategoryAttributes,
  getCategoryDetails,
  getCategoryPredictions,
  getCbtListingConfig,
  getCbtPublishingProfile,
  getDraftPricing,
  approveDraft,
  executeCbtPublishFromDraft,
  getSystemReadiness,
  listStores,
  previewCbtPublishFromDraft,
  saveDraftPricing,
  saveCbtListingConfig,
  type CbtListingConfig,
  type CbtPublishingProfile,
  type DraftPricing,
  type DraftPricingInput,
  type ProductDraft,
  type PublishExecutionResult,
  type SystemReadiness,
  type StoreRecord,
} from "../api/client";

const REQUIRED_ATTRIBUTE_IDS = [
  "ITEM_CONDITION",
  "SELLER_SKU",
  "PACKAGE_LENGTH",
  "PACKAGE_WIDTH",
  "PACKAGE_HEIGHT",
  "PACKAGE_WEIGHT",
];

const MARKET_NAMES: Record<string, string> = {
  MLA: "阿根廷", MLB: "巴西", MLC: "智利", MCO: "哥伦比亚", MLM: "墨西哥", MLU: "乌拉圭",
};

type Offer = CbtListingConfig["sites_to_sell"][number];

function normalizeCbtTitle(value: string) {
  return value.replace(/\s+/g, " ").trim().slice(0, 60);
}

function sanitizeCbtDescription(value: string) {
  return value
    .split("\n")
    .filter((line) => !/^\s*(brand|brand name|marca)\s*[:\-]/i.test(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function CbtGlobalPublishingPanel({
  draft,
  draftId,
  onDraftChange,
  onReviewInvalidated,
  onBackToEditing,
}: {
  draft: ProductDraft;
  draftId: number;
  onDraftChange: (draft: ProductDraft) => void;
  onReviewInvalidated: () => void;
  onBackToEditing: () => void;
}) {
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [profile, setProfile] = useState<CbtPublishingProfile | null>(null);
  const [profileReloadKey, setProfileReloadKey] = useState(0);
  const [categoryId, setCategoryId] = useState("");
  const [categoryLeafVerified, setCategoryLeafVerified] = useState(false);
  const [categoryPath, setCategoryPath] = useState("");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [globalTitle, setGlobalTitle] = useState(normalizeCbtTitle(draft.title));
  const [familyName, setFamilyName] = useState("");
  const [description, setDescription] = useState(sanitizeCbtDescription(draft.description));
  const [priceUsd, setPriceUsd] = useState(draft.currency === "USD" && draft.price ? String(draft.price) : "");
  const [quantity, setQuantity] = useState(draft.stock > 0 ? String(draft.stock) : "");
  const [attributes, setAttributes] = useState<Record<string, string>>({});
  const [attributeDefinitions, setAttributeDefinitions] = useState<Record<string, unknown>[]>([]);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [warranty, setWarranty] = useState("");
  const [saved, setSaved] = useState<CbtListingConfig | null>(null);
  const [preview, setPreview] = useState<{ allowed: boolean; errors: string[]; payload: Record<string, unknown> | null } | null>(null);
  const [approved, setApproved] = useState(false);
  const [publishConfirmed, setPublishConfirmed] = useState(false);
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [pricing, setPricing] = useState<DraftPricing | null>(null);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const cbtStores = stores.filter((store) => store.site_id === "CBT" && store.oauth_status === "connected");
  const remoteMarkets = (profile?.marketplaces ?? []).filter((market) => market.available);
  const requiredIds = useMemo(() => {
    const fromMetadata = attributeDefinitions
      .filter((attribute) => {
        const tags = attribute.tags as Record<string, unknown> | undefined;
        return tags?.required === true || tags?.catalog_required === true;
      })
      .map((attribute) => String(attribute.id ?? "").toUpperCase())
      .filter(Boolean);
    return [...new Set([...REQUIRED_ATTRIBUTE_IDS, ...fromMetadata])];
  }, [attributeDefinitions]);
  const missing = requiredIds.filter((id) => !attributes[id]?.trim());
  const unitCostUsd = pricing
    ? (pricing.purchase_cost + pricing.domestic_shipping_cost) * pricing.exchange_rate
    : null;
  const estimatedProfitUsd = Number(priceUsd) > 0 && unitCostUsd !== null
    ? Number(priceUsd) - unitCostUsd
    : null;
  const canSave = Boolean(
    storeId && categoryId && categoryLeafVerified && familyName.trim() && globalTitle.trim() && description.trim()
    && Number(priceUsd) > 0 && Number.isInteger(Number(quantity)) && Number(quantity) > 0
    && pricing?.target_currency === "USD" && offers.length > 0 && missing.length === 0,
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listStores(),
      getCbtListingConfig(draftId),
      getSystemReadiness(),
      getDraftPricing(draftId).catch(() => null),
    ])
      .then(([storeRows, config, system, savedPricing]) => {
        if (cancelled) return;
        setStores(storeRows);
        setReadiness(system);
        setPricing(savedPricing);
        const defaultStore = config?.store_id
          ? String(config.store_id)
          : storeRows.find((store) => store.site_id === "CBT" && store.oauth_status === "connected")?.id ?? "";
        setStoreId(defaultStore);
        if (!config) return;
        setSaved(config);
        setCategoryId(config.category_id);
        getCategoryDetails(config.category_id)
          .then((details) => {
            if (!cancelled) {
              setCategoryLeafVerified(details.verified && details.leaf);
              setCategoryPath(details.path_from_root.map((item) => item.name).filter(Boolean).join(" > "));
            }
          })
          .catch(() => !cancelled && setCategoryLeafVerified(false));
        setFamilyName(config.family_name);
        setGlobalTitle(normalizeCbtTitle(config.global_title));
        setDescription(sanitizeCbtDescription(config.description));
        setPriceUsd(String(config.price_usd));
        setQuantity(String(config.available_quantity));
        setAttributes(Object.fromEntries(config.attributes.map((item) => [item.id, item.value_name])));
        setOffers(config.sites_to_sell);
        setWarranty(config.sale_terms.find((term) => term.id === "WARRANTY_TYPE")?.value_name ?? "");
      })
      .catch((error) => !cancelled && setStatus(error instanceof Error ? error.message : "无法读取跨境刊登配置"));
    return () => { cancelled = true; };
  }, [draftId]);

  useEffect(() => {
    if (!storeId) { setProfile(null); return; }
    let cancelled = false;
    setBusy("profile");
    getCbtPublishingProfile(Number(storeId))
      .then((data) => { if (!cancelled) setProfile(data); })
      .catch((error) => !cancelled && setStatus(error instanceof Error ? error.message : "无法读取店铺跨境能力"))
      .finally(() => !cancelled && setBusy(""));
    return () => { cancelled = true; };
  }, [storeId, profileReloadKey]);

  async function predictCategory() {
    setBusy("category"); setStatus("");
    try {
      const result = await getCategoryPredictions("CBT", globalTitle);
      setPredictions(result.predictions.slice(0, 6));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "CBT 类目预测失败");
    } finally { setBusy(""); }
  }

  async function loadAttributes() {
    if (!categoryId) return;
    setBusy("attributes"); setStatus("");
    try {
      const details = await getCategoryDetails(categoryId);
      if (!details.verified || !details.leaf) {
        setCategoryLeafVerified(false);
        throw new Error("请确认最底层叶子分类，父分类不能直接上架。");
      }
      setCategoryLeafVerified(true);
      setCategoryPath(details.path_from_root.map((item) => item.name).filter(Boolean).join(" > "));
      const result = await getCategoryAttributes(categoryId);
      setAttributeDefinitions(result.attributes);
      setStatus(result.verified ? "已读取美客多官方类目属性" : "属性尚未验证");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "读取类目属性失败");
    } finally { setBusy(""); }
  }

  function setAttribute(id: string, value: string) {
    setAttributes((current) => ({ ...current, [id]: value }));
    setSaved(null); setPreview(null); setApproved(false); setPublishConfirmed(false); setExecution(null);
  }

  function toggleMarket(siteId: string) {
    setOffers((current) => {
      if (current.some((offer) => offer.site_id === siteId)) return current.filter((offer) => offer.site_id !== siteId);
      return [...current, { site_id: siteId, title: globalTitle, listing_type_id: "gold_pro", logistic_type: "remote", picture_urls: [] }];
    });
    setSaved(null); setPreview(null); setApproved(false); setPublishConfirmed(false); setExecution(null);
  }

  function updateOffer(siteId: string, key: "title" | "listing_type_id", value: string) {
    setOffers((current) => current.map((offer) => offer.site_id === siteId
      ? { ...offer, [key]: key === "title" ? normalizeCbtTitle(value) : value } as Offer : offer));
    setSaved(null); setPreview(null); setApproved(false); setPublishConfirmed(false); setExecution(null);
  }

  async function saveConfig() {
    if (!canSave) return;
    setBusy("save"); setStatus(""); setPreview(null); setApproved(false); setPublishConfirmed(false); setExecution(null);
    try {
      const currentPricing = pricing;
      const targetPrice = Number(priceUsd);
      const landedCost = unitCostUsd;
      if (!currentPricing || landedCost === null || landedCost <= 0) {
        throw new Error("请先在编辑上架页保存采购成本、国内运费和 USD 汇率。");
      }
      const pricingPayload: DraftPricingInput = {
        source_price: currentPricing.source_price,
        source_currency: currentPricing.source_currency,
        target_currency: "USD",
        cost_currency: "CNY",
        purchase_cost: currentPricing.purchase_cost,
        domestic_shipping_cost: currentPricing.domestic_shipping_cost,
        exchange_rate: currentPricing.exchange_rate,
        profit_margin_rate: targetPrice / landedCost - 1,
        rounding_increment: currentPricing.rounding_increment,
      };
      const savedPricing = await saveDraftPricing(draftId, pricingPayload);
      setPricing(savedPricing);
      const config = await saveCbtListingConfig(draftId, {
        store_id: Number(storeId), category_id: categoryId, family_name: familyName,
        global_title: normalizeCbtTitle(globalTitle), description: sanitizeCbtDescription(description), price_usd: Number(priceUsd),
        available_quantity: Number(quantity),
        attributes: Object.entries(attributes).filter(([, value]) => value.trim()).map(([id, value_name]) => ({ id, value_name })),
        sale_terms: warranty.trim() ? [{ id: "WARRANTY_TYPE", value_name: warranty.trim() }] : [],
        sites_to_sell: offers,
      });
      setSaved(config); onDraftChange(config.draft); onReviewInvalidated();
      setStatus("跨境刊登配置已保存。原有审核已失效，需要按新价格与字段重新审核。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "保存跨境刊登配置失败"); }
    finally { setBusy(""); }
  }

  async function previewPayload() {
    setBusy("preview"); setStatus("");
    try {
      setPreview(await previewCbtPublishFromDraft(draftId));
    } catch (error) { setStatus(error instanceof Error ? error.message : "生成官方请求预检失败"); }
    finally { setBusy(""); }
  }

  async function approveForPublish() {
    setBusy("approval"); setStatus("");
    try {
      await approveDraft(draftId, "operator", "Approved for CBT Global Selling publication");
      setApproved(true);
      setStatus("已记录人工批准。发布前仍会重新校验店铺、审核和素材。");
    } catch (error) {
      setApproved(false);
      setStatus(error instanceof Error ? error.message : "人工批准失败：请先完成当前商品的 AI 审核。");
    } finally { setBusy(""); }
  }

  async function executePublish() {
    setBusy("execute"); setStatus("");
    try {
      setExecution(await executeCbtPublishFromDraft(draftId));
    } catch (error) { setStatus(error instanceof Error ? error.message : "跨境发布请求失败"); }
    finally { setBusy(""); }
  }

  return <section className="workspace cbt-workspace">
    <header className="page-header">
      <div>
        <p className="eyebrow">GLOBAL SELLING · CBT</p>
        <h2>跨境商品上架</h2>
        <p>一个全球商品可同步销售到多个国家；售价统一以 USD 设置，各站分别配置标题和刊登类型。</p>
      </div>
      <button className="secondary-button" onClick={onBackToEditing}><ArrowLeft size={16} /> 返回编辑上架</button>
    </header>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">1</span><h3>跨境店与商品基础资料</h3></div><button className="icon-button" title="刷新店铺能力" disabled={!storeId || busy === "profile"} onClick={() => setProfileReloadKey((value) => value + 1)}><RefreshCw size={17} /></button></div>
      <label>已授权跨境店
        <select value={storeId} onChange={(event) => { setStoreId(event.target.value); setOffers([]); setPreview(null); }}>
          <option value="">选择 CBT 店铺</option>
          {cbtStores.map((store) => <option key={store.id} value={store.id}>{store.display_name} · 卖家 {store.seller_id}</option>)}
        </select>
      </label>
      {busy === "profile" && <p className="status-line">正在读取真实店铺市场和配额...</p>}
      {profile && <>
        <div className="cbt-profile-line"><Store size={16} /><strong>{profile.seller_id}</strong><span>发布模型：{profile.model === "traditional_global" ? "传统 Global Selling" : "User Products"}</span></div>
        {profile.model !== "traditional_global" && <p className="inline-warning">此账号已启用 User Products，不能使用本页的传统 `/global/items` 流程。</p>}
        <p className="section-note">可销售国家和 Remote 物流能力来自已授权店铺；在销售配置表中启用需要发布的国家。</p>
      </>}
    </section>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">2</span><h3>全球商品资料</h3></div></div>
      <div className="form-grid two-col">
        <label>产品族名称 family_name *<input value={familyName} placeholder="例如 Silicone Mold Collection" onChange={(event) => { setFamilyName(event.target.value); setSaved(null); setPreview(null); }} /></label>
        <label>可售库存 *<input type="number" min="1" step="1" value={quantity} onChange={(event) => { setQuantity(event.target.value); setSaved(null); setPreview(null); }} /></label>
      </div>
      <label>英文商品描述（不得包含品牌） *<textarea rows={7} value={description} onChange={(event) => { setDescription(sanitizeCbtDescription(event.target.value)); setSaved(null); setPreview(null); }} /></label>
      <p className="cbt-image-note"><Image size={16} /> 将使用商品来源中已保存的 {draft.image_urls.length} 张图片，并写入每一个目标市场的 `sites_to_sell`。</p>
    </section>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">3</span><h3>CBT 类目、属性与质保</h3></div></div>
      <div className="category-controls"><label>CBT 最终类目 ID *<input value={categoryId} placeholder="CBT..." onChange={(event) => { setCategoryId(event.target.value.toUpperCase()); setCategoryLeafVerified(false); setCategoryPath(""); setSaved(null); setPreview(null); }} /></label><button onClick={predictCategory} disabled={!globalTitle.trim() || busy === "category"}><Search size={16} /> 官方类目预测</button><button className="secondary-button" onClick={loadAttributes} disabled={!categoryId.startsWith("CBT") || busy === "attributes"}><ListChecks size={16} /> 验证叶子类目并读取属性</button></div>
      {categoryPath && <p className="category-path-label">{categoryPath} · {categoryLeafVerified ? "叶子类目已验证" : "待验证"}</p>}
      {predictions.length > 0 && <div className="prediction-list">{predictions.map((item) => { const id = String(item.category_id ?? ""); return <button key={id} onClick={() => { setCategoryId(id); setCategoryLeafVerified(false); setCategoryPath(""); setAttributeDefinitions([]); setPreview(null); }}>{String(item.category_name ?? item.domain_name ?? id)}<small>{id}</small></button>; })}</div>}
      <div className="form-grid two-col cbt-attributes">{requiredIds.map((id) => {
        const definition = attributeDefinitions.find((item) => String(item.id).toUpperCase() === id);
        return <label key={id}>{String(definition?.name ?? id)} *<input value={attributes[id] ?? ""} placeholder={id === "ITEM_CONDITION" ? "New" : id === "SELLER_SKU" ? "内部 SKU" : "例如 10 cm / 250 g"} onChange={(event) => setAttribute(id, event.target.value)} /></label>;
      })}</div>
      <label>质保条款（按类目要求填写）<input value={warranty} placeholder="例如 No warranty" onChange={(event) => { setWarranty(event.target.value); setSaved(null); setPreview(null); }} /></label>
      {missing.length > 0 && <p className="inline-warning">还缺少 {missing.join("、")}。</p>}
    </section>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">4</span><h3>销售配置</h3><p>先设置全球售价，再逐个启用销售国家并确认标题和刊登类型。</p></div></div>
      <div className="cbt-pricing-rule">非 FULL 跨境商品按“售价 - 采购成本 - 国内运费”显示预估净收益；国际运输由美客多统一处理，不作为单品成本输入。</div>
      <div className="cbt-sales-table-wrap">
        <table className="cbt-sales-table">
          <thead><tr><th>销售国家/地区</th><th>售价（USD）</th><th>预估净收益（USD）</th><th>刊登类型</th><th>标题</th></tr></thead>
          <tbody>
            <tr className="cbt-global-row">
              <th><Globe2 size={16} /> 全球商品</th>
              <td><input type="number" min="0.01" step="0.01" value={priceUsd} onChange={(event) => { setPriceUsd(event.target.value); setSaved(null); setPreview(null); setApproved(false); setPublishConfirmed(false); }} /></td>
              <td><strong>{estimatedProfitUsd === null ? "请先完成成本定价" : estimatedProfitUsd.toFixed(2)}</strong></td>
              <td><span className="cbt-derived-value">按国家设置</span></td>
              <td><div className="cbt-title-input"><input maxLength={60} value={globalTitle} onChange={(event) => { setGlobalTitle(normalizeCbtTitle(event.target.value)); setSaved(null); setPreview(null); }} /><small>{globalTitle.length}/60</small></div></td>
            </tr>
            {remoteMarkets.map((market) => {
              const offer = offers.find((item) => item.site_id === market.site_id);
              const enabled = Boolean(offer);
              const capacity = market.listing_count !== null && market.listing_limit !== null ? `${market.listing_count} / ${market.listing_limit}` : "配额待返回";
              return <tr className={enabled ? "" : "disabled"} key={`${market.site_id}-${market.logistic_type}`}>
                <th><label className="cbt-site-toggle"><input type="checkbox" disabled={profile?.model !== "traditional_global"} checked={enabled} onChange={() => toggleMarket(market.site_id)} /><span><strong>{MARKET_NAMES[market.site_id] ?? market.site_id}</strong><small>{market.site_id} · 已刊登/配额 {capacity}</small></span></label></th>
                <td><span className="cbt-derived-value">{priceUsd || "-"}</span></td>
                <td><span className="cbt-derived-value">{estimatedProfitUsd === null ? "-" : estimatedProfitUsd.toFixed(2)}</span></td>
                <td><select disabled={!enabled} value={offer?.listing_type_id ?? "gold_pro"} onChange={(event) => updateOffer(market.site_id, "listing_type_id", event.target.value)}><option value="gold_pro">Premium（优质）</option><option value="gold_special">Classic（经典）</option></select></td>
                <td><div className="cbt-title-input"><input disabled={!enabled} maxLength={60} value={offer?.title ?? globalTitle} onChange={(event) => updateOffer(market.site_id, "title", event.target.value)} /><small>{(offer?.title ?? globalTitle).length}/60</small></div></td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
      {remoteMarkets.length === 0 && <p className="inline-warning">未读取到可用的 Remote 销售国家，请刷新店铺能力或检查跨境店授权。</p>}
      {unitCostUsd === null && <p className="inline-warning">请先返回编辑上架，保存采购成本、国内运费和 USD 汇率，才能核对预估净收益。</p>}
      {pricing && pricing.target_currency !== "USD" && <p className="inline-warning">这张上架单当前不是 CBT 的 USD 定价。请重新以 CBT 为目标站点采集并完成成本定价。</p>}
      {offers.length === 0 && <p className="inline-warning">请至少启用一个可用的 Remote 销售国家。</p>}
      <div className="button-row"><button disabled={!canSave || busy === "save"} onClick={saveConfig}><Save size={16} /> 保存跨境刊登配置</button><button className="secondary-button" disabled={!saved || busy === "preview"} onClick={previewPayload}><ListChecks size={16} /> 生成官方请求预检</button></div>
      {preview && <div className={`validation-result ${preview.allowed ? "ready" : "blocked"}`}><strong>{preview.allowed ? "官方 Global Selling 请求已通过结构校验" : "刊登请求未通过"}</strong>{preview.errors.map((error) => <span key={error}>{error}</span>)}</div>}
      <div className="release-summary"><div><span>商品素材</span><strong>{draft.image_urls.length} 张图片</strong></div><div><span>预检</span><strong>{preview?.allowed ? "通过" : "未完成"}</strong></div><div><span>人工批准</span><strong>{approved ? "已批准" : "未批准"}</strong></div><div><span>线上发布</span><strong>{readiness?.mercado_libre.live_publish_enabled ? "已开启" : "未开启"}</strong></div></div>
      <div className="button-row"><button className="secondary-button" disabled={!preview?.allowed || busy === "approval"} onClick={approveForPublish}><CheckCircle2 size={16} /> 记录人工批准</button><label className="check-row"><input type="checkbox" checked={publishConfirmed} disabled={!approved || !preview?.allowed || !readiness?.mercado_libre.live_publish_enabled} onChange={(event) => setPublishConfirmed(event.target.checked)} />确认向美客多创建商品</label><button disabled={!publishConfirmed || !approved || !preview?.allowed || !readiness?.mercado_libre.live_publish_enabled || busy === "execute"} onClick={executePublish}><Globe2 size={16} /> 提交跨境发布</button></div>
      {!readiness?.mercado_libre.live_publish_enabled && <p className="inline-warning">服务器尚未开启真实发布；可先完成配置、审核、批准和预检。</p>}
      {execution && <div className={`validation-result ${execution.status === "published" ? "ready" : "blocked"}`}><strong>{execution.status === "published" ? "已提交并创建商品" : "未创建商品"}</strong>{execution.item_id && <span>商品 ID：{execution.item_id}</span>}{execution.permalink && <a href={execution.permalink} target="_blank" rel="noreferrer">打开商品页</a>}{execution.errors.map((error) => <span key={error}>{error}</span>)}</div>}
      {status && <p className="status-line">{status}</p>}
    </section>
  </section>;
}
