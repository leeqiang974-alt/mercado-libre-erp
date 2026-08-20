import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Globe2,
  Image,
  ListChecks,
  RefreshCw,
  Save,
  Search,
  Store,
} from "lucide-react";
import {
  confirmDraftCategory,
  getCategoryAttributes,
  getCategoryDetails,
  getCategoryPredictions,
  getCbtListingConfig,
  getCbtPublishingProfile,
  getDraftPricing,
  executeCbtPublishFromDraft,
  getSystemReadiness,
  listDrafts,
  listStores,
  previewCbtPublishFromDraft,
  saveDraftContent,
  saveDraftPricing,
  saveCbtListingConfig,
  type CbtListingConfig,
  type CbtMarketplace,
  type CbtPublishingProfile,
  type DraftPricing,
  type DraftPricingInput,
  type ProductDraft,
  type ProductDraftRead,
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

function createRemoteOffer(market: CbtMarketplace, title: string): Offer {
  return {
    site_id: market.site_id,
    title: normalizeCbtTitle(title),
    listing_type_id: "gold_pro",
    logistic_type: "remote",
    picture_urls: [],
  };
}

function remoteMarketsForProfile(profile: CbtPublishingProfile): CbtMarketplace[] {
  return Array.from(
    new Map(
      profile.marketplaces
        .filter((market) => market.available && market.logistic_type === "remote")
        .map((market) => [market.site_id, market]),
    ).values(),
  );
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
  const [listingRail, setListingRail] = useState<ProductDraftRead[]>([]);
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
  const [publishConfirmed, setPublishConfirmed] = useState(false);
  const [execution, setExecution] = useState<PublishExecutionResult | null>(null);
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [pricing, setPricing] = useState<DraftPricing | null>(null);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [configLoaded, setConfigLoaded] = useState(false);
  const [hasSavedConfig, setHasSavedConfig] = useState(false);
  const offersInitializedRef = useRef(false);

  const cbtStores = stores.filter((store) => store.site_id === "CBT" && store.oauth_status === "connected");
  const remoteMarkets = useMemo(
    () => (profile ? remoteMarketsForProfile(profile) : []),
    [profile],
  );
  const fullMarkets = useMemo(() => {
    const configured = (profile?.marketplaces ?? []).filter(
      (market) => market.site_id === "MLM" && market.logistic_type === "fulfillment",
    );
    return configured.length > 0 ? configured : [{
      site_id: "MLM",
      seller_id: "",
      logistic_type: "fulfillment",
      user_product: false,
      listing_count: null,
      listing_limit: null,
      available: false,
    } satisfies CbtMarketplace];
  }, [profile]);
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
  const allRemoteSelected = remoteMarkets.length > 0
    && remoteMarkets.every((market) => offers.some((offer) => offer.site_id === market.site_id));
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
    listDrafts().then(setListingRail).catch(() => undefined);
  }, [draftId]);

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
        setHasSavedConfig(Boolean(config));
        setConfigLoaded(true);
        offersInitializedRef.current = Boolean(config);
        if (!config) return;
        setSaved(config);
        setCategoryId(config.category_id);
        getCategoryDetails(config.category_id)
          .then((details) => {
            if (!cancelled) {
              setCategoryLeafVerified(details.verified && details.leaf);
              setCategoryPath((details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean).join(" > "));
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
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        if (configLoaded && !hasSavedConfig && data.model === "traditional_global" && !offersInitializedRef.current) {
          setOffers(remoteMarketsForProfile(data).map((market) => createRemoteOffer(market, globalTitle)));
          offersInitializedRef.current = true;
        }
      })
      .catch((error) => !cancelled && setStatus(error instanceof Error ? error.message : "无法读取店铺跨境能力"))
      .finally(() => !cancelled && setBusy(""));
    return () => { cancelled = true; };
  }, [storeId, profileReloadKey, configLoaded, hasSavedConfig]);

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
      const confirmed = await confirmDraftCategory(draftId, {
        expected_content_version: draft.content_version ?? 1,
        target_site_id: "CBT",
        category_id: categoryId,
      });
      onDraftChange(confirmed.draft);
      setCategoryLeafVerified(true);
      setCategoryPath((details.path_from_root_zh ?? details.path_from_root).map((item) => item.name_zh || item.name).filter(Boolean).join(" > "));
      const result = await getCategoryAttributes(categoryId);
      setAttributeDefinitions(result.attributes);
      setStatus(result.verified ? "已读取美客多官方类目属性" : "属性尚未验证");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "读取类目属性失败");
    } finally { setBusy(""); }
  }

  function setAttribute(id: string, value: string) {
    setAttributes((current) => ({ ...current, [id]: value }));
    setSaved(null); setPreview(null); setPublishConfirmed(false); setExecution(null);
  }

  function toggleMarket(siteId: string) {
    offersInitializedRef.current = true;
    setOffers((current) => {
      if (current.some((offer) => offer.site_id === siteId)) return current.filter((offer) => offer.site_id !== siteId);
      return [...current, { site_id: siteId, title: globalTitle, listing_type_id: "gold_pro", logistic_type: "remote", picture_urls: [] }];
    });
    setSaved(null); setPreview(null); setPublishConfirmed(false); setExecution(null);
  }

  function toggleAllRemoteMarkets() {
    offersInitializedRef.current = true;
    setOffers(allRemoteSelected ? [] : remoteMarkets.map((market) => createRemoteOffer(market, globalTitle)));
    setSaved(null); setPreview(null); setPublishConfirmed(false); setExecution(null);
  }

  function updateOffer(siteId: string, key: "title" | "listing_type_id", value: string) {
    setOffers((current) => current.map((offer) => offer.site_id === siteId
      ? { ...offer, [key]: key === "title" ? normalizeCbtTitle(value) : value } as Offer : offer));
    setSaved(null); setPreview(null); setPublishConfirmed(false); setExecution(null);
  }

  async function saveProductContent() {
    const updated = await saveDraftContent(draftId, {
      expected_content_version: draft.content_version ?? 1,
      title: normalizeCbtTitle(globalTitle),
      description: sanitizeCbtDescription(description),
      brand: "Unbranded",
      image_urls: draft.image_urls.filter(Boolean),
      video_urls: draft.video_urls ?? [],
    });
    onDraftChange(updated);
    return updated;
  }

  async function setCoverImage(url: string) {
    const image_urls = [url, ...draft.image_urls.filter((item) => item !== url)];
    try {
      setBusy("media");
      const updated = await saveDraftContent(draftId, { expected_content_version: draft.content_version ?? 1, title: normalizeCbtTitle(globalTitle), description: sanitizeCbtDescription(description), brand: "Unbranded", image_urls, video_urls: draft.video_urls ?? [] });
      onDraftChange(updated);
      setStatus("主图已保存。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "保存图片顺序失败"); }
    finally { setBusy(""); }
  }

  async function removeImage(url: string) {
    const image_urls = draft.image_urls.filter((item) => item !== url);
    try {
      setBusy("media");
      const updated = await saveDraftContent(draftId, { expected_content_version: draft.content_version ?? 1, title: normalizeCbtTitle(globalTitle), description: sanitizeCbtDescription(description), brand: "Unbranded", image_urls, video_urls: draft.video_urls ?? [] });
      onDraftChange(updated);
      setStatus("图片已移除。");
    } catch (error) { setStatus(error instanceof Error ? error.message : "删除图片失败"); }
    finally { setBusy(""); }
  }

  async function saveConfig() {
    if (!canSave) return;
    setBusy("save"); setStatus(""); setPreview(null); setPublishConfirmed(false); setExecution(null);
    try {
      await saveProductContent();
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
      setStatus("跨境刊登配置已保存，可直接进行官方请求预检。");
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

  async function executePublish() {
    setBusy("execute"); setStatus("");
    try {
      setExecution(await executeCbtPublishFromDraft(draftId));
    } catch (error) { setStatus(error instanceof Error ? error.message : "跨境发布请求失败"); }
    finally { setBusy(""); }
  }

  return <section className="workspace wf-listing-editor">
    <header className="wf-header">
      <div><p className="eyebrow">GLOBAL SELLING · CBT</p><h2>编辑产品 / 跨境上架</h2><p>按“店铺和类目 → 商品资料 → 图片 → 描述 → SKU → 销售配置”一次完成，不再分散到多个页面。</p></div>
      <button className="secondary-button" onClick={onBackToEditing}><ArrowLeft size={16} /> 返回上架库</button>
    </header>

    <aside className="wf-step-nav" aria-label="上架步骤">
      {[['store-category','店铺和类目'],['basic','产品基本信息'],['media','产品图片'],['description','描述'],['variants','变体与 SKU'],['sales','销售配置']].map(([id,label], index) => <a key={id} href={`#${id}`}><span>{index + 1}</span>{label}</a>)}
    </aside>

    <div className="wf-listing-layout">
      <aside className="drafts-sidebar surface wf-listing-rail">
        <div className="drafts-sidebar-heading"><h3>上架库</h3><span>{listingRail.length} 个</span></div>
        <p className="section-note">选择商品后，在右侧完成分类、素材、售价和站点配置。</p>
        <div className="draft-rail-list">{listingRail.map((item) => <button className={`draft-rail-item ${item.id === draftId ? "selected" : ""}`} key={item.id} onClick={() => { window.location.href = `/?draft_id=${item.id}#publishing`; }}><img className="product-image" src={item.image_urls[0] || ""} alt="" /><span><strong>{item.title || "未命名商品"}</strong><small>#{item.id} · {item.target_site_id}</small><small>{item.risk_status}</small></span></button>)}</div>
      </aside>
      <main className="wf-editor-main">
      <section id="store-category" className="surface wf-section">
        <div className="wf-section-title"><span>1</span><div><h3>店铺和类目</h3><p>先确认跨境店和最底层 CBT 分类，确认后才加载官方属性。</p></div><button className="icon-button" title="刷新店铺能力" disabled={!storeId || busy === "profile"} onClick={() => setProfileReloadKey((value) => value + 1)}><RefreshCw size={17} /></button></div>
        <div className="wf-form-row"><label>店铺 *<select value={storeId} onChange={(event) => { setStoreId(event.target.value); setOffers([]); setHasSavedConfig(false); offersInitializedRef.current = false; setPreview(null); }}><option value="">选择 CBT 店铺</option>{cbtStores.map((store) => <option key={store.id} value={store.id}>{store.display_name} · 卖家 {store.seller_id}</option>)}</select></label>
          <div className="wf-sites"><strong>同时发布到站点</strong><label><input type="checkbox" checked={allRemoteSelected} disabled={profile?.model !== "traditional_global" || remoteMarkets.length === 0} onChange={toggleAllRemoteMarkets} /> 全选</label>{remoteMarkets.map((market) => <label key={market.site_id}><input type="checkbox" checked={offers.some((offer) => offer.site_id === market.site_id)} onChange={() => toggleMarket(market.site_id)} /> {MARKET_NAMES[market.site_id]}</label>)}<label className="is-disabled"><input type="checkbox" disabled /> 墨西哥（FULL）</label></div></div>
        {profile && <p className="section-note">卖家 {profile.seller_id} · {profile.model === "traditional_global" ? "传统 Global Selling" : "User Products"}。Remote 站点默认全部勾选；墨西哥 FULL 由独立流程处理。</p>}
        <div className="wf-category-line"><label>Mercado Libre 最终分类 *<input value={categoryId} placeholder="先用标题搜索 CBT 最底层分类" onChange={(event) => { setCategoryId(event.target.value.toUpperCase()); setCategoryLeafVerified(false); setCategoryPath(""); setSaved(null); setPreview(null); }} /></label><button onClick={predictCategory} disabled={!globalTitle.trim() || busy === "category"}><Search size={16} /> 选择分类</button><button className="secondary-button" onClick={loadAttributes} disabled={!categoryId.startsWith("CBT") || busy === "attributes"}><ListChecks size={16} /> 确认分类</button></div>
        {categoryPath && <p className="category-path-label">{categoryPath} · {categoryLeafVerified ? "最底层分类已确认" : "待确认"}</p>}
        {predictions.length > 0 && <div className="prediction-list">{predictions.map((item) => { const id = String(item.category_id ?? ""); const name = String(item.category_name_zh ?? item.category_name ?? item.domain_name ?? id); return <button key={id} onClick={() => { setCategoryId(id); setCategoryLeafVerified(false); setCategoryPath(""); setAttributeDefinitions([]); }}>{name}<small>{id} · 点击后确认分类</small></button>; })}</div>}
      </section>

      <section id="basic" className="surface wf-section"><div className="wf-section-title"><span>2</span><div><h3>产品基本信息</h3><p>标题强制英文不超过 60 字符；品牌固定为无品牌。</p></div></div><div className="form-grid two-col"><label>Parent SKU / 产品族名称 *<input value={familyName} placeholder="例如 SKU02761" onChange={(event) => { setFamilyName(event.target.value); setSaved(null); setPreview(null); }} /></label><label>可售库存 *<input type="number" min="1" step="1" value={quantity} onChange={(event) => { setQuantity(event.target.value); setSaved(null); setPreview(null); }} /></label></div><label>英文标题 *<div className="wf-title-input"><input maxLength={60} value={globalTitle} onChange={(event) => { setGlobalTitle(normalizeCbtTitle(event.target.value)); setSaved(null); setPreview(null); }} /><small>{globalTitle.length}/60</small></div></label><label>品牌（固定）<input disabled value="Unbranded（无品牌）" /></label></section>

      <section id="media" className="surface wf-section"><div className="wf-section-title"><span>3</span><div><h3>产品图片</h3><p>使用采集到的原图；第 1 张是主图。小规格缩略图不会入库。</p></div><strong>{draft.image_urls.length} 张</strong></div><div className="wf-media-grid">{draft.image_urls.map((url,index) => <article className={`wf-media-card ${index === 0 ? "cover" : ""}`} key={url}><div className="wf-media-label">{index === 0 ? "主图" : `图片 ${index + 1}`}</div><img src={url} alt={`商品图片 ${index + 1}`} /><div><button className="tiny-button" disabled={index === 0 || busy === "media"} onClick={() => setCoverImage(url)}>设为主图</button><button className="tiny-button danger" disabled={busy === "media"} onClick={() => removeImage(url)}>删除</button></div></article>)}</div>{draft.image_urls.length === 0 && <p className="inline-warning">当前没有可发布图片，请先回到上架库补充素材。</p>}<div className="wf-video-line"><strong>产品视频</strong><span>{draft.video_urls?.length ?? 0}/3 个；视频独立保存，未进入商品图片。</span></div></section>

      <section id="description" className="surface wf-section"><div className="wf-section-title"><span>4</span><div><h3>描述</h3><p>英文、基于采集信息；不出现品牌。末尾保留 7 天店铺保修说明。</p></div></div><label>英文商品描述 *<textarea rows={10} value={description} onChange={(event) => { setDescription(sanitizeCbtDescription(event.target.value)); setSaved(null); setPreview(null); }} /></label></section>

      <section id="variants" className="surface wf-section"><div className="wf-section-title"><span>5</span><div><h3>变体与 SKU</h3><p>当前为采集到的 SKU 信息；选择分类后才可确认官方变体属性。</p></div></div><div className="wf-sku-row"><div><span>来源 ASIN</span><strong>{draft.source_variant_asin || "未提供"}</strong></div><div><span>已采集规格</span><strong>{Object.entries(draft.source_variant_attributes ?? {}).map(([key,value]) => `${key}: ${value}`).join(" · ") || "单品，无变体"}</strong></div><div><span>卖家 SKU *</span><input value={attributes.SELLER_SKU ?? ""} placeholder="内部 SKU" onChange={(event) => setAttribute("SELLER_SKU", event.target.value)} /></div></div><div className="form-grid two-col cbt-attributes">{requiredIds.filter((id) => id !== "SELLER_SKU").map((id) => { const definition = attributeDefinitions.find((item) => String(item.id).toUpperCase() === id); return <label key={id}>{String(definition?.name ?? id)} *<input value={attributes[id] ?? ""} placeholder={id === "ITEM_CONDITION" ? "New" : "例如 10 cm / 250 g"} onChange={(event) => setAttribute(id, event.target.value)} /></label>; })}</div><label>质保条款<input value={warranty} placeholder="例如 No warranty" onChange={(event) => { setWarranty(event.target.value); setSaved(null); setPreview(null); }} /></label>{missing.length > 0 && <p className="inline-warning">还缺少官方必填字段：{missing.join("、")}。</p>}</section>

      <section id="sales" className="surface wf-section"><div className="wf-section-title"><span>6</span><div><h3>销售配置</h3><p>只填写一次全球 USD 售价；净收益只扣采购成本和国内运费。</p></div></div><div className="cbt-pricing-rule">全球销售统一运输不进入单品成本。预估净收益 = USD 售价 −（采购成本 + 国内运费）× USD 汇率。</div><div className="cbt-sales-table-wrap"><table className="cbt-sales-table"><thead><tr><th>站点</th><th>售价（USD）</th><th>预估净收益</th><th>刊登类型</th><th>标题</th></tr></thead><tbody><tr className="cbt-global-row"><th><Globe2 size={16} /> 全球</th><td><input type="number" min="0.01" step="0.01" value={priceUsd} onChange={(event) => { setPriceUsd(event.target.value); setSaved(null); setPreview(null); }} /></td><td><strong>{estimatedProfitUsd === null ? "请先填写成本" : estimatedProfitUsd.toFixed(2)}</strong></td><td><span className="cbt-derived-value">按站点配置</span></td><td><div className="cbt-title-input"><input maxLength={60} value={globalTitle} onChange={(event) => setGlobalTitle(normalizeCbtTitle(event.target.value))} /><small>{globalTitle.length}/60</small></div></td></tr>{remoteMarkets.map((market) => { const offer = offers.find((item) => item.site_id === market.site_id); const enabled = Boolean(offer); return <tr className={enabled ? "" : "disabled"} key={market.site_id}><th><label className="cbt-site-toggle"><input type="checkbox" checked={enabled} onChange={() => toggleMarket(market.site_id)} /><span><strong>{MARKET_NAMES[market.site_id] ?? market.site_id}</strong><small>{market.site_id} · Remote</small></span></label></th><td><span className="cbt-derived-value">{priceUsd || "-"}</span></td><td><span className="cbt-derived-value">{estimatedProfitUsd === null ? "-" : estimatedProfitUsd.toFixed(2)}</span></td><td><select disabled={!enabled} value={offer?.listing_type_id ?? "gold_pro"} onChange={(event) => updateOffer(market.site_id, "listing_type_id", event.target.value)}><option value="gold_pro">Premium（优质）</option><option value="gold_special">Classic（经典）</option></select></td><td><div className="cbt-title-input"><input disabled={!enabled} maxLength={60} value={offer?.title ?? globalTitle} onChange={(event) => updateOffer(market.site_id, "title", event.target.value)} /><small>{(offer?.title ?? globalTitle).length}/60</small></div></td></tr>; })}{fullMarkets.map((market) => <tr className="disabled cbt-full-row" key={`${market.site_id}-${market.logistic_type}`}><th><label className="cbt-site-toggle"><input type="checkbox" disabled /><span><strong>墨西哥（FULL）</strong><small>MLM · FULL 履约不参与本次发布</small></span></label></th><td>不发布</td><td>-</td><td>已排除</td><td>由 FULL 流程单独管理</td></tr>)}</tbody></table></div>{pricing && pricing.target_currency !== "USD" && <p className="inline-warning">请补充 USD 成本定价后保存；当前草稿的本地站价格不能用于 CBT 发布。</p>}{preview && <div className={`validation-result ${preview.allowed ? "ready" : "blocked"}`}><strong>{preview.allowed ? "官方请求预检通过" : "刊登请求未通过"}</strong>{preview.errors.map((error) => <span key={error}>{error}</span>)}</div>}{execution && <div className={`validation-result ${execution.status === "published" ? "ready" : "blocked"}`}><strong>{execution.status === "published" ? "已提交并创建商品" : "未创建商品"}</strong>{execution.item_id && <span>商品 ID：{execution.item_id}</span>}{execution.permalink && <a href={execution.permalink} target="_blank" rel="noreferrer">打开商品页</a>}{execution.errors.map((error) => <span key={error}>{error}</span>)}</div>}</section>
      </main>
    </div>
    <footer className="wf-action-bar"><span>{status || (saved ? "配置已保存" : "请先完成必填内容")}</span><div><button className="secondary-button" onClick={onBackToEditing}>取消</button><button disabled={!canSave || busy === "save"} onClick={saveConfig}><Save size={16} /> 保存</button><button className="secondary-button" disabled={!saved || busy === "preview"} onClick={previewPayload}><ListChecks size={16} /> 预检</button><label className="check-row"><input type="checkbox" checked={publishConfirmed} disabled={!preview?.allowed || !readiness?.mercado_libre.live_publish_enabled} onChange={(event) => setPublishConfirmed(event.target.checked)} />确认发布</label><button disabled={!publishConfirmed || !preview?.allowed || !readiness?.mercado_libre.live_publish_enabled || busy === "execute"} onClick={executePublish}><Globe2 size={16} /> 立即发布</button></div></footer>
  </section>;
}
