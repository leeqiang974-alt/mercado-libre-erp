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
  getCategoryPredictions,
  getCbtListingConfig,
  getCbtPublishingProfile,
  approveDraft,
  executeCbtPublishFromDraft,
  getSystemReadiness,
  listStores,
  previewCbtPublishFromDraft,
  saveCbtListingConfig,
  type CbtListingConfig,
  type CbtPublishingProfile,
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

export function CbtGlobalPublishingPanel({
  draft,
  draftId,
  onDraftChange,
  onReviewInvalidated,
  onBack,
}: {
  draft: ProductDraft;
  draftId: number;
  onDraftChange: (draft: ProductDraft) => void;
  onReviewInvalidated: () => void;
  onBack: () => void;
}) {
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [storeId, setStoreId] = useState("");
  const [profile, setProfile] = useState<CbtPublishingProfile | null>(null);
  const [profileReloadKey, setProfileReloadKey] = useState(0);
  const [categoryId, setCategoryId] = useState("");
  const [predictions, setPredictions] = useState<Record<string, unknown>[]>([]);
  const [globalTitle, setGlobalTitle] = useState(draft.title);
  const [familyName, setFamilyName] = useState("");
  const [description, setDescription] = useState(draft.description);
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
  const selectedSites = new Set(offers.map((offer) => offer.site_id));
  const canSave = Boolean(
    storeId && categoryId && familyName.trim() && globalTitle.trim() && description.trim()
    && Number(priceUsd) > 0 && Number.isInteger(Number(quantity)) && Number(quantity) > 0
    && offers.length > 0 && missing.length === 0,
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([listStores(), getCbtListingConfig(draftId), getSystemReadiness()])
      .then(([storeRows, config, system]) => {
        if (cancelled) return;
        setStores(storeRows);
        setReadiness(system);
        const defaultStore = config?.store_id
          ? String(config.store_id)
          : storeRows.find((store) => store.site_id === "CBT" && store.oauth_status === "connected")?.id ?? "";
        setStoreId(defaultStore);
        if (!config) return;
        setSaved(config);
        setCategoryId(config.category_id);
        setFamilyName(config.family_name);
        setGlobalTitle(config.global_title);
        setDescription(config.description);
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
      ? { ...offer, [key]: value } as Offer : offer));
    setSaved(null); setPreview(null); setApproved(false); setPublishConfirmed(false); setExecution(null);
  }

  async function saveConfig() {
    if (!canSave) return;
    setBusy("save"); setStatus(""); setPreview(null); setApproved(false); setPublishConfirmed(false); setExecution(null);
    try {
      const config = await saveCbtListingConfig(draftId, {
        store_id: Number(storeId), category_id: categoryId, family_name: familyName,
        global_title: globalTitle, description, price_usd: Number(priceUsd),
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
        <h2>跨境商品刊登</h2>
        <p>传统跨境店使用 `/global/items`，按目标国家一次创建全球商品。</p>
      </div>
      <button className="secondary-button" onClick={onBack}><ArrowLeft size={16} /> 本土店刊登</button>
    </header>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">1</span><h3>跨境店与目标市场</h3></div><button className="icon-button" title="刷新店铺能力" disabled={!storeId || busy === "profile"} onClick={() => setProfileReloadKey((value) => value + 1)}><RefreshCw size={17} /></button></div>
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
        <div className="cbt-market-grid">
          {profile.marketplaces.map((market) => {
            const checked = selectedSites.has(market.site_id);
            const capacity = market.listing_count !== null && market.listing_limit !== null ? `${market.listing_count} / ${market.listing_limit}` : "配额待返回";
            return <label key={`${market.site_id}-${market.logistic_type}`} className={`cbt-market ${market.available ? "" : "disabled"}`}>
              <input type="checkbox" disabled={!market.available || profile.model !== "traditional_global"} checked={checked} onChange={() => toggleMarket(market.site_id)} />
              <span><strong>{MARKET_NAMES[market.site_id] ?? market.site_id}</strong><small>{market.site_id} · {market.logistic_type}</small><small>已刊登 / 配额：{capacity}</small></span>
              {!market.available && <em>{market.logistic_type === "fulfillment" ? "FULL 不支持" : "不可用"}</em>}
            </label>;
          })}
        </div>
      </>}
    </section>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">2</span><h3>全球商品基础资料</h3></div></div>
      <div className="form-grid two-col">
        <label>英文全局标题 *<input value={globalTitle} onChange={(event) => { setGlobalTitle(event.target.value); setSaved(null); setPreview(null); }} /></label>
        <label>产品族名称 family_name *<input value={familyName} placeholder="例如 Silicone Mold Collection" onChange={(event) => { setFamilyName(event.target.value); setSaved(null); setPreview(null); }} /></label>
        <label>销售价 USD *<input type="number" min="0.01" step="0.01" value={priceUsd} onChange={(event) => { setPriceUsd(event.target.value); setSaved(null); setPreview(null); }} /></label>
        <label>可售库存 *<input type="number" min="1" step="1" value={quantity} onChange={(event) => { setQuantity(event.target.value); setSaved(null); setPreview(null); }} /></label>
      </div>
      <label>英文商品描述 *<textarea rows={7} value={description} onChange={(event) => { setDescription(event.target.value); setSaved(null); setPreview(null); }} /></label>
      <p className="cbt-image-note"><Image size={16} /> 将使用商品来源中已保存的 {draft.image_urls.length} 张图片，并写入每一个目标市场的 `sites_to_sell`。</p>
    </section>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">3</span><h3>CBT 类目、属性与质保</h3></div></div>
      <div className="category-controls"><label>CBT 类目 ID *<input value={categoryId} placeholder="CBT..." onChange={(event) => { setCategoryId(event.target.value.toUpperCase()); setSaved(null); setPreview(null); }} /></label><button onClick={predictCategory} disabled={!globalTitle.trim() || busy === "category"}><Search size={16} /> 官方类目预测</button><button className="secondary-button" onClick={loadAttributes} disabled={!categoryId.startsWith("CBT") || busy === "attributes"}><ListChecks size={16} /> 读取类目属性</button></div>
      {predictions.length > 0 && <div className="prediction-list">{predictions.map((item) => { const id = String(item.category_id ?? ""); return <button key={id} onClick={() => { setCategoryId(id); setAttributeDefinitions([]); setPreview(null); }}>{String(item.category_name ?? item.domain_name ?? id)}<small>{id}</small></button>; })}</div>}
      <div className="form-grid two-col cbt-attributes">{requiredIds.map((id) => {
        const definition = attributeDefinitions.find((item) => String(item.id).toUpperCase() === id);
        return <label key={id}>{String(definition?.name ?? id)} *<input value={attributes[id] ?? ""} placeholder={id === "ITEM_CONDITION" ? "New" : id === "SELLER_SKU" ? "内部 SKU" : "例如 10 cm / 250 g"} onChange={(event) => setAttribute(id, event.target.value)} /></label>;
      })}</div>
      <label>质保条款（按类目要求填写）<input value={warranty} placeholder="例如 No warranty" onChange={(event) => { setWarranty(event.target.value); setSaved(null); setPreview(null); }} /></label>
      {missing.length > 0 && <p className="inline-warning">还缺少 {missing.join("、")}。</p>}
    </section>

    <section className="surface publish-section">
      <div className="section-heading"><div><span className="step-number">4</span><h3>各市场销售设置</h3></div></div>
      {offers.length === 0 && <p className="inline-warning">请先从第一步勾选至少一个 Remote 市场。</p>}
      {offers.map((offer) => <div className="cbt-offer-row" key={offer.site_id}><Globe2 size={18} /><strong>{MARKET_NAMES[offer.site_id] ?? offer.site_id}</strong><label>当地标题<input value={offer.title} onChange={(event) => updateOffer(offer.site_id, "title", event.target.value)} /></label><label>刊登类型<select value={offer.listing_type_id} onChange={(event) => updateOffer(offer.site_id, "listing_type_id", event.target.value)}><option value="gold_pro">Premium</option><option value="gold_special">Classic</option></select></label></div>)}
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
