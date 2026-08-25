import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileCode2,
  FilePlus2,
  Link2,
  ListPlus,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  ScanSearch,
  Search,
  Upload,
} from "lucide-react";
import {
  createCollectionJobsBatch,
  discoverAmazonProducts,
  createKeywordCampaign,
  listKeywordCampaigns,
  createCollectionJobsFile,
  createSourceVariantCollectionJob,
  createSourceVariantCollectionJobs,
  createSourceVariantDraft,
  getDraft,
  getSourceProduct,
  listCollectionJobs,
  listCollectionJobStatuses,
  runCollectionJob,
  type CollectionBatchResult,
  type CollectionJobRecord,
  type AmazonSourceVariant,
  type SourceProductRecord,
  type SourceVariantCollectionBatchResult,
  type ProductDraftRead,
  type KeywordCampaign,
} from "../api/client";
import { MERCADO_LIBRE_SITES } from "../domain/sites";

type ImportMode = "discover" | "url" | "html" | "campaign";

const JOB_LABELS: Record<CollectionJobRecord["status"], string> = {
  pending: "待处理",
  running: "采集中",
  completed: "已完成",
  needs_manual_action: "需人工处理",
  failed: "失败",
};

const BATCH_LABELS: Record<CollectionBatchResult["items"][number]["outcome"], string> = {
  created: "已加入队列",
  duplicate_input: "重复链接",
  existing: "已有任务",
  invalid: "链接无效",
};

const BATCH_DETAILS: Record<string, string> = {
  only_public_amazon_product_urls_allowed: "仅支持公开的 Amazon 商品链接",
  duplicate_amazon_product_in_request: "该商品已在本次导入中",
  collection_job_already_exists: "该商品已有采集任务",
};

const AMAZON_DOMAINS = [
  "amazon.com.mx", "amazon.com.br", "amazon.co.uk", "amazon.co.jp", "amazon.com.au",
  "amazon.com", "amazon.ca", "amazon.de", "amazon.fr", "amazon.it", "amazon.es",
  "amazon.nl", "amazon.in", "amazon.sg", "amazon.ae", "amazon.sa",
];

function canonicalAmazonDomain(hostname: string) {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  return AMAZON_DOMAINS.find((domain) => host === domain || host.endsWith(`.${domain}`)) ?? host;
}

function uniqueSourceVariants(variants: AmazonSourceVariant[]) {
  const byAsin = new Map<string, AmazonSourceVariant>();
  variants.forEach((variant) => {
    const asin = variant.asin.trim().toUpperCase();
    const normalized = { ...variant, asin };
    const existing = byAsin.get(asin);
    byAsin.set(asin, existing ? {
      ...existing,
      attributes: { ...existing.attributes, ...normalized.attributes },
      image_urls: [...new Set([...existing.image_urls, ...normalized.image_urls])],
      selected: existing.selected || normalized.selected,
    } : normalized);
  });
  return [...byAsin.values()];
}

function jobIcon(status: CollectionJobRecord["status"]) {
  if (status === "completed") return <CheckCircle2 size={16} />;
  if (status === "running") return <LoaderCircle className="spin" size={16} />;
  if (status === "pending") return <Clock3 size={16} />;
  return <AlertTriangle size={16} />;
}

function shortSource(sourceUrl: string) {
  try {
    const url = new URL(sourceUrl);
    return `${url.hostname}${url.pathname}`;
  } catch {
    return sourceUrl;
  }
}

function collectionMessage(message: string) {
  const translations: Record<string, string> = {
    "Amazon product page is incomplete; manual action required.": "Amazon 返回的商品页内容不完整，需要人工补救。",
    "Amazon challenge detected; manual action required.": "Amazon 要求验证，需要人工补救。",
    "Amazon redirected this link away from the requested product; verify the ASIN.": "Amazon 已将该链接跳转到非商品页面，请检查 ASIN 是否正确。",
    "Amazon redirected this link to a different ASIN; the requested product was not collected.": "Amazon 已将该链接跳转到另一个 ASIN，原商品未被采集。",
    "Collection timed out; retry is safe.": "采集超时，可以重新采集。",
    "Collection worker interrupted; retry is safe.": "采集服务中断，可以重新采集。",
  };
  return translations[message] ?? message;
}

function findVariantCollectionJob(
  jobs: CollectionJobRecord[],
  sourceUrl: string,
  variantAsin: string,
  targetSiteId: string,
) {
  let sourceHost = "";
  try {
    sourceHost = canonicalAmazonDomain(new URL(sourceUrl).hostname);
  } catch {
    return undefined;
  }
  return jobs.find((job) => {
    if (job.target_site_id !== targetSiteId) return false;
    try {
      const jobUrl = new URL(job.source_url);
      const jobHost = canonicalAmazonDomain(jobUrl.hostname);
      const sameAmazonDomain = sourceHost === jobHost;
      const match = jobUrl.pathname.match(/\/dp\/([a-z0-9]{10})(?:\/|$)/i);
      return sameAmazonDomain && match?.[1].toUpperCase() === variantAsin.toUpperCase();
    } catch {
      return false;
    }
  });
}

export function ImportPage({
  onImportHtml,
  onOpenDraft,
  status,
  initialMode = "discover",
}: {
  onImportHtml: (
    sourceUrl: string,
    html: string,
    targetSiteId: string,
    persist: boolean,
    collectionJobId: number | null,
  ) => Promise<void>;
  onOpenDraft: (draft: ProductDraftRead) => void;
  status: string;
  initialMode?: ImportMode;
}) {
  const [mode, setMode] = useState<ImportMode>(initialMode);
  const [sourceUrls, setSourceUrls] = useState("");
  const [discoveryKeyword, setDiscoveryKeyword] = useState("");
  const [discoveryDomain, setDiscoveryDomain] = useState("amazon.com");
  const [discoveryLimit, setDiscoveryLimit] = useState("20");
  const [campaignKeywords, setCampaignKeywords] = useState("");
  const [campaigns, setCampaigns] = useState<KeywordCampaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const [campaignPage, setCampaignPage] = useState(0);
  const [completedJobs, setCompletedJobs] = useState<CollectionJobRecord[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>("");
  const [snapshotUrl, setSnapshotUrl] = useState("");
  const [targetSiteId, setTargetSiteId] = useState("CBT");
  const [html, setHtml] = useState("");
  const [persist, setPersist] = useState(true);
  const [snapshotJobId, setSnapshotJobId] = useState<number | null>(null);
  const [allowExisting, setAllowExisting] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [batchResult, setBatchResult] = useState<CollectionBatchResult | null>(null);
  const [collectionJobs, setCollectionJobs] = useState<CollectionJobRecord[]>([]);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [sourceDetails, setSourceDetails] = useState<Record<number, SourceProductRecord>>({});
  const [expandedSourceId, setExpandedSourceId] = useState<number | null>(null);
  const [variantDraftIds, setVariantDraftIds] = useState<Record<string, number>>({});
  const [knownVariantJobs, setKnownVariantJobs] = useState<Record<number, CollectionJobRecord>>({});
  const [variantBatchResults, setVariantBatchResults] = useState<Record<string, SourceVariantCollectionBatchResult>>({});
  const collectionRequestEpoch = useRef(0);
  const knownVariantJobsRef = useRef<Record<number, CollectionJobRecord>>({});

  useEffect(() => setMode(initialMode), [initialMode]);

  function setKnownVariantJobSnapshot(jobsById: Record<number, CollectionJobRecord>) {
    const jobs = Object.values(jobsById);
    const active = jobs.filter((job) => job.status === "pending" || job.status === "running");
    const recentTerminal = jobs
      .filter((job) => job.status !== "pending" && job.status !== "running")
      .sort((left, right) => right.id - left.id)
      .slice(0, 100);
    const next = Object.fromEntries([...active, ...recentTerminal].map((job) => [job.id, job]));
    knownVariantJobsRef.current = next;
    setKnownVariantJobs(next);
  }

  function rememberVariantJobs(jobs: CollectionJobRecord[]) {
    if (jobs.length === 0) return;
    const next = {
      ...knownVariantJobsRef.current,
      ...Object.fromEntries(jobs.map((job) => [job.id, job])),
    };
    setKnownVariantJobSnapshot(next);
  }

  const refreshCollectionJobs = useCallback(async (showError = true) => {
    const requestEpoch = ++collectionRequestEpoch.current;
    try {
      const knownJobIds = Object.values(knownVariantJobsRef.current)
        .filter((job) => job.status === "pending" || job.status === "running")
        .map((job) => job.id);
      const [jobs, knownStatuses, completed] = await Promise.all([
        listCollectionJobs(200, 0, selectedCampaignId ?? undefined),
        listCollectionJobStatuses(knownJobIds),
        listCollectionJobs(100, 0, undefined, "completed"),
      ]);
      if (requestEpoch === collectionRequestEpoch.current) {
        setCollectionJobs(jobs);
        setCompletedJobs(completed);
        const nextKnown = { ...knownVariantJobsRef.current };
        const freshById = new Map(
          [...jobs, ...knownStatuses].map((job) => [job.id, job]),
        );
        knownJobIds.forEach((jobId) => {
          const fresh = freshById.get(jobId);
          if (fresh) nextKnown[jobId] = fresh;
          else delete nextKnown[jobId];
        });
        jobs.forEach((job) => {
          if (nextKnown[job.id]) nextKnown[job.id] = job;
        });
        setKnownVariantJobSnapshot(nextKnown);
      }
    } catch (jobError) {
      if (showError && requestEpoch === collectionRequestEpoch.current) {
        setError(jobError instanceof Error ? jobError.message : "Failed to load collection jobs");
      }
    }
  }, [selectedCampaignId]);

  const refreshCampaigns = useCallback(async () => {
    try { setCampaigns(await listKeywordCampaigns()); } catch { /* API may be migrating */ }
  }, []);

  async function refreshTaskDashboard() {
    setIsRefreshing(true);
    try {
      // 任务总览只取轻量的关键词进度；商品明细只在查看某个任务结果时加载。
      if (initialMode === "campaign" && selectedCampaignId === null) {
        await refreshCampaigns();
      } else {
        await Promise.all([refreshCollectionJobs(false), refreshCampaigns()]);
      }
      setLastRefreshedAt(new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    } finally { setIsRefreshing(false); }
  }
  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    async function poll() {
      if (initialMode === "campaign" && selectedCampaignId === null) {
        await refreshCampaigns();
      } else {
        await Promise.all([refreshCollectionJobs(false), refreshCampaigns()]);
      }
      if (!cancelled) {
        timer = window.setTimeout(() => void poll(), 5000);
      }
    }
    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [initialMode, refreshCollectionJobs, refreshCampaigns, selectedCampaignId]);

  async function runUrlCollection() {
    // Every collection goes through a persisted job so a blocked Amazon page has
    // a visible operator recovery action instead of leaving the page busy.
    await queueCollectionJob();
  }

  async function discoverAndQueue() {
    setError("");
    setBusyAction("discover");
    try {
      const result = await discoverAmazonProducts(
        discoveryKeyword.trim(), discoveryDomain, targetSiteId, Number(discoveryLimit),
      );
      setBatchResult(result);
      await refreshCollectionJobs(false);
    } catch (discoveryError) {
      setError(discoveryError instanceof Error ? discoveryError.message : "Amazon 搜索发现失败");
    } finally { setBusyAction(""); }
  }

  async function startKeywordCampaign() {
    const keywords = campaignKeywords.split(/\n|,/).map((value) => value.trim()).filter(Boolean);
    if (!keywords.length) return;
    setError(""); setBusyAction("campaign");
    try {
      await createKeywordCampaign({ name: `关键词采集 ${new Date().toLocaleDateString("zh-CN")}`, keywords, domain: discoveryDomain, target_site_id: targetSiteId, pages_per_keyword: 2 });
      setCampaignKeywords(""); await refreshCampaigns();
    } catch (e) { setError(e instanceof Error ? e.message : "创建关键词任务失败"); } finally { setBusyAction(""); }
  }

  async function runHtmlImport() {
    setError("");
    setBusyAction("html");
    try {
      await onImportHtml(snapshotUrl, html, targetSiteId, persist, snapshotJobId);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Import failed");
    } finally {
      setBusyAction("");
    }
  }

  async function queueCollectionJob() {
    setError("");
    setBusyAction("queue");
    try {
      const result = await createCollectionJobsBatch(urlEntries, targetSiteId, allowExisting);
      setBatchResult(result);
      await refreshCollectionJobs(false);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to create collection job");
    } finally {
      setBusyAction("");
    }
  }

  async function queueCollectionFile() {
    if (!importFile) return;
    setError("");
    setBusyAction("file");
    try {
      const result = await createCollectionJobsFile(importFile, targetSiteId, allowExisting);
      setBatchResult(result);
      setImportFile(null);
      await refreshCollectionJobs(false);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to import collection file");
    } finally {
      setBusyAction("");
    }
  }

  async function runJob(job: CollectionJobRecord) {
    setError("");
    setBusyAction(`job-${job.id}`);
    try {
      const updated = await runCollectionJob(job.id);
      if (knownVariantJobsRef.current[job.id]) {
        rememberVariantJobs([updated]);
      }
      await refreshCollectionJobs(false);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to run collection job");
    } finally {
      setBusyAction("");
    }
  }

  function useSnapshotFallback(job: CollectionJobRecord) {
    setSnapshotUrl(job.source_url);
    setTargetSiteId(job.target_site_id);
    setPersist(true);
    setSnapshotJobId(job.id);
    setMode("html");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function toggleSourceReview(sourceProductId: number) {
    if (expandedSourceId === sourceProductId) {
      setExpandedSourceId(null);
      return;
    }
    setExpandedSourceId(sourceProductId);
    if (sourceDetails[sourceProductId]) return;
    setBusyAction(`source-${sourceProductId}`);
    setError("");
    try {
      const source = await getSourceProduct(sourceProductId);
      setSourceDetails((current) => ({ ...current, [sourceProductId]: source }));
    } catch (sourceError) {
      setExpandedSourceId(null);
      setError(sourceError instanceof Error ? sourceError.message : "Failed to load source product");
    } finally {
      setBusyAction("");
    }
  }

  async function useSourceVariant(
    sourceProductId: number,
    variantAsin: string,
    variantTargetSiteId: string,
  ) {
    const key = `${sourceProductId}:${variantAsin}:${variantTargetSiteId}`;
    setBusyAction(`variant-${key}`);
    setError("");
    try {
      const draft = await createSourceVariantDraft(
        sourceProductId,
        variantAsin,
        variantTargetSiteId,
      );
      setVariantDraftIds((current) => ({ ...current, [key]: draft.id }));
      onOpenDraft(draft);
    } catch (variantError) {
      setError(variantError instanceof Error ? variantError.message : "Failed to create variant draft");
    } finally {
      setBusyAction("");
    }
  }

  async function openDraftEditor(productDraftId: number) {
    setBusyAction(`open-draft-${productDraftId}`);
    setError("");
    try {
      onOpenDraft(await getDraft(productDraftId));
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "打开上架编辑页失败");
    } finally {
      setBusyAction("");
    }
  }

  async function collectSourceVariant(
    sourceProductId: number,
    variantAsin: string,
    variantTargetSiteId: string,
  ) {
    const key = `${sourceProductId}:${variantAsin}:${variantTargetSiteId}`;
    setBusyAction(`collect-variant-${key}`);
    setError("");
    try {
      const created = await createSourceVariantCollectionJob(
        sourceProductId,
        variantAsin,
        variantTargetSiteId,
      );
      rememberVariantJobs([created]);
      await refreshCollectionJobs(false);
    } catch (variantError) {
      setError(variantError instanceof Error ? variantError.message : "Failed to collect variant");
    } finally {
      setBusyAction("");
    }
  }

  async function collectMissingSourceVariants(
    sourceProductId: number,
    variantTargetSiteId: string,
  ) {
    const key = `${sourceProductId}:${variantTargetSiteId}`;
    setBusyAction(`collect-variant-batch-${key}`);
    setError("");
    try {
      const result = await createSourceVariantCollectionJobs(
        sourceProductId,
        variantTargetSiteId,
      );
      setVariantBatchResults((current) => ({ ...current, [key]: result }));
      rememberVariantJobs(result.jobs);
      await refreshCollectionJobs(false);
    } catch (variantError) {
      setError(variantError instanceof Error ? variantError.message : "Failed to collect variants");
    } finally {
      setBusyAction("");
    }
  }

  const isBusy = Boolean(busyAction);
  const displayedCollectionJobs = Array.from(
    new Map(
      [...Object.values(knownVariantJobs), ...collectionJobs]
        .filter((job) => selectedCampaignId === null || job.campaign_id === selectedCampaignId)
        .map((job) => [job.id, job]),
    ).values(),
  ).sort((left, right) => right.id - left.id);
  const selectedCampaign = campaigns.find((campaign) => campaign.id === selectedCampaignId);
  const campaignPageSize = 10;
  const campaignPageCount = Math.max(1, Math.ceil(campaigns.length / campaignPageSize));
  const visibleCampaigns = campaigns.slice(campaignPage * campaignPageSize, (campaignPage + 1) * campaignPageSize);
  const urlEntries = sourceUrls
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean);
  const urlCountValid = urlEntries.length > 0 && urlEntries.length <= 100;

  return (
    <section className="workspace import-workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">第一步</p>
          <h2>{initialMode === "campaign" ? "采集任务" : "智能采集"}</h2>
          <p>{initialMode === "campaign" ? "查看关键词任务和每个商品的实时采集状态。" : "输入关键词自动发现并采集 Amazon 商品；采集成功后，直接进入编辑上架。"}</p>
        </div>
        <div className="page-header-actions"><span className="task-refresh-time">{lastRefreshedAt ? `已刷新 ${lastRefreshedAt}` : "自动每 5 秒刷新"}</span><button className="icon-button" title="立即刷新任务状态" aria-label="立即刷新任务状态" disabled={isBusy || isRefreshing} onClick={() => void refreshTaskDashboard()}><RefreshCw className={isRefreshing ? "spin" : ""} size={17} /></button></div>
      </header>

      {initialMode !== "campaign" && <div className="import-mode-switch" role="tablist" aria-label="Amazon 采集方式">
        <button
          role="tab"
          aria-selected={mode === "discover"}
          className={mode === "discover" ? "selected" : ""}
          onClick={() => setMode("discover")}
        >
          <ScanSearch size={17} /> 智能选品
        </button>
        <button
          role="tab"
          aria-selected={mode === "url"}
          className={mode === "url" ? "selected" : ""}
          onClick={() => setMode("url")}
        >
          <Link2 size={17} /> 链接采集
        </button>
      </div>}

      {mode === "campaign" ? (
        <section className="surface campaign-dashboard">
          <div className="section-heading"><div><h3>关键词采集任务</h3><p>实时显示关键词发现、详情采集、去重和暂停原因。</p></div></div>
          {campaigns.length === 0 ? <div className="empty-state compact-empty"><Clock3 size={24} /><strong>暂无关键词采集任务</strong></div> : visibleCampaigns.map((campaign) => (
            <article className="campaign-task-card" key={campaign.id}>
              <div><strong>{campaign.name}</strong><span className={`campaign-status ${campaign.status}`}>{campaign.status === "running" ? "运行中" : campaign.status === "paused" ? "已暂停" : campaign.status === "completed" ? "已完成" : "等待中"}</span></div>
              <p>当前：{campaign.current_keyword || "全部关键词已发现"} · 第 {campaign.current_page}/{campaign.pages_per_keyword} 页 · 共 {campaign.keyword_count} 个关键词</p>
              <div className="campaign-metrics"><span>发现 <b>{campaign.discovered_count}</b></span><span>已入队 <b>{campaign.queued_count}</b></span><span>已去重 <b>{campaign.duplicate_count}</b></span></div>
              <small>{campaign.message}</small>
              <div className="button-row"><button className="secondary-button" onClick={() => setSelectedCampaignId(selectedCampaignId === campaign.id ? null : campaign.id)}>{selectedCampaignId === campaign.id ? "查看全部采集任务" : "查看此关键词任务结果"}</button></div>
            </article>
          ))}
          {campaignPageCount > 1 && <div className="pagination-row">
            <button className="secondary-button" disabled={campaignPage === 0} onClick={() => setCampaignPage((page) => Math.max(0, page - 1))}>上一页</button>
            <span>第 {campaignPage + 1} / {campaignPageCount} 页，共 {campaigns.length} 个任务</span>
            <button className="secondary-button" disabled={campaignPage >= campaignPageCount - 1} onClick={() => setCampaignPage((page) => Math.min(campaignPageCount - 1, page + 1))}>下一页</button>
          </div>}
        </section>
      ) : <section className="surface import-source">
        {mode === "html" && (
          <div className="section-heading">
            <div>
              <h3>采集异常补救</h3>
              <p>仅当 Amazon 出现验证码或页面无法自动读取时使用。正常选品和采集无需操作这里。</p>
            </div>
            <button className="secondary-button" onClick={() => setMode("discover")}>返回智能选品</button>
          </div>
        )}
        <div className="form-grid two-col">
          <label>
            {mode === "discover" ? "选品关键词" : "Amazon 商品链接"}
            {mode === "discover" ? (
              <input value={discoveryKeyword} placeholder="例如 silicone mold for resin" onChange={(event) => setDiscoveryKeyword(event.target.value)} />
            ) : mode === "url" ? (
              <textarea
                className="batch-url-input"
                placeholder={"https://www.amazon.com/dp/...\nhttps://www.amazon.ca/dp/..."}
                value={sourceUrls}
                onChange={(event) => {
                  setSourceUrls(event.target.value);
                  setBatchResult(null);
                }}
              />
            ) : (
              <input
                type="url"
                placeholder="https://www.amazon.com/dp/..."
                value={snapshotUrl}
                onChange={(event) => {
                  setSnapshotUrl(event.target.value);
                  setSnapshotJobId(null);
                }}
              />
            )}
          </label>
          <label>
            {mode === "discover" ? "Amazon 站点" : "目标美客多站点"}
            <select
              value={mode === "discover" ? discoveryDomain : targetSiteId}
              onChange={(event) => {
                if (mode === "discover") setDiscoveryDomain(event.target.value);
                else setTargetSiteId(event.target.value);
                setSnapshotJobId(null);
                setBatchResult(null);
              }}
            >
              {(mode === "discover" ? ["amazon.com", "amazon.com.mx", "amazon.ca", "amazon.co.uk", "amazon.de", "amazon.co.jp"] : MERCADO_LIBRE_SITES.map((site) => site.id)).map((value) => (
                <option key={value} value={value}>
                  {mode === "discover" ? value : (() => { const site = MERCADO_LIBRE_SITES.find((item) => item.id === value)!; return `${site.country} (${site.id}) · ${site.currency}`; })()}
                </option>
              ))}
            </select>
          </label>
        </div>

        {mode === "discover" ? (
          <>
            <div className="inline-warning import-warning"><ScanSearch size={17} /><span>按关键词从 Amazon 搜索结果发现 ASIN，自动加入采集队列；详情图片、规格与价格仍会从每个商品页独立核验。</span></div>
            <div className="batch-options"><label>发现数量 <select value={discoveryLimit} onChange={(event) => setDiscoveryLimit(event.target.value)}><option value="10">10 个</option><option value="20">20 个</option><option value="50">50 个</option></select></label><label>目标美客多站点 <select value={targetSiteId} onChange={(event) => setTargetSiteId(event.target.value)}>{MERCADO_LIBRE_SITES.map((site) => <option key={site.id} value={site.id}>{site.country} ({site.id})</option>)}</select></label></div>
            <div className="button-row"><button disabled={discoveryKeyword.trim().length < 2 || isBusy} onClick={discoverAndQueue}>{busyAction === "discover" ? <LoaderCircle className="spin" size={17} /> : <ScanSearch size={17} />} 发现并采集</button></div>
            <div className="campaign-panel"><strong>持续关键词采集</strong><small>每行一个关键词；启动后请到“采集任务”查看实时状态。</small><textarea value={campaignKeywords} placeholder={"例如\nsilicone muffin pan\ndrawer organizer"} onChange={(event) => setCampaignKeywords(event.target.value)} /><button disabled={!campaignKeywords.trim() || isBusy} onClick={startKeywordCampaign}>{busyAction === "campaign" ? "创建中…" : "启动关键词任务"}</button></div>
            {batchResult && <div className="batch-result" aria-live="polite"><div className="batch-result-summary"><strong>{batchResult.created_count} 个已加入采集队列</strong><span>{batchResult.existing_count} 个已有任务</span><span>{batchResult.duplicate_count} 个重复</span><span>{batchResult.invalid_count} 个无效</span></div><div className="batch-result-list">{batchResult.items.map((item, index) => <div className={`batch-result-row ${item.outcome}`} key={`${item.input_url}-${index}`}><span>{BATCH_LABELS[item.outcome]}</span><strong title={item.normalized_url || item.input_url}>{shortSource(item.normalized_url || item.input_url)}</strong><small>{item.job ? `任务 #${item.job.id}` : BATCH_DETAILS[item.detail] || item.detail}</small></div>)}</div></div>}
          </>
        ) : mode === "url" ? (
          <>
            <div className="inline-warning import-warning">
              <AlertTriangle size={17} />
              <span>采集任务会自动运行；只有 Amazon 返回验证页或内容不完整时，任务才会显示“人工补救”。</span>
            </div>
            <div className="batch-options">
              <span className={urlEntries.length > 100 ? "error" : ""}>
                {urlEntries.length} / 100 条链接
              </span>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={allowExisting}
                  onChange={(event) => {
                    setAllowExisting(event.target.checked);
                    setBatchResult(null);
                  }}
                />
                允许再次采集已有链接
              </label>
            </div>
            <div className="button-row">
              <button disabled={urlEntries.length !== 1 || isBusy} onClick={runUrlCollection}>
                {busyAction === "queue" ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
                开始采集
              </button>
              <button
                className="secondary-button"
                disabled={!urlCountValid || isBusy}
                onClick={queueCollectionJob}
              >
                {busyAction === "queue" ? <LoaderCircle className="spin" size={17} /> : <ListPlus size={17} />}
                {urlEntries.length > 1 ? `加入 ${urlEntries.length} 个采集任务` : "加入采集队列"}
              </button>
              <label className={`secondary-button file-picker ${isBusy ? "disabled" : ""}`}>
                <Upload size={17} />
                {importFile?.name ?? "选择 CSV/XLSX"}
                <input
                  type="file"
                  accept=".csv,.xlsx"
                  aria-label="选择 CSV 或 XLSX 文件"
                  disabled={isBusy}
                  onChange={(event) => {
                    setImportFile(event.target.files?.[0] ?? null);
                    setBatchResult(null);
                    event.target.value = "";
                  }}
                />
              </label>
              <button
                className="secondary-button"
                disabled={!importFile || isBusy}
                onClick={queueCollectionFile}
              >
                {busyAction === "file" ? <LoaderCircle className="spin" size={17} /> : <FilePlus2 size={17} />}
                导入文件
              </button>
            </div>
            {batchResult && (
              <div className="batch-result" aria-live="polite">
                <div className="batch-result-summary">
                  <strong>{batchResult.created_count} 个已加入队列</strong>
                  <span>{batchResult.existing_count} 个已有任务</span>
                  <span>{batchResult.duplicate_count} 个重复</span>
                  <span>{batchResult.invalid_count} 个无效</span>
                </div>
                <div className="batch-result-list">
                  {batchResult.items.map((item, index) => (
                    <div className={`batch-result-row ${item.outcome}`} key={`${item.input_url}-${index}`}>
                      <span>{BATCH_LABELS[item.outcome]}</span>
                      <strong title={item.normalized_url || item.input_url}>
                        {shortSource(item.normalized_url || item.input_url)}
                      </strong>
                      <small>
                        {item.job
                          ? `任务 #${item.job.id}`
                          : BATCH_DETAILS[item.detail] || item.detail}
                      </small>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <label>
              Amazon 页面内容
              <textarea
                className="snapshot-input"
                placeholder="粘贴已保存的 Amazon 商品详情页页面内容"
                value={html}
                onChange={(event) => setHtml(event.target.value)}
              />
            </label>
            <div className="snapshot-actions">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={persist}
                  onChange={(event) => setPersist(event.target.checked)}
                  disabled={snapshotJobId !== null}
                />
                {snapshotJobId !== null ? `处理任务 #${snapshotJobId} 并保存草稿` : "保存为商品草稿"}
              </label>
              <button disabled={!snapshotUrl.trim() || !html.trim() || isBusy} onClick={runHtmlImport}>
                {busyAction === "html" ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}
                继续处理该商品
              </button>
            </div>
          </>
        )}

        {status && <p className="status-line">{status}</p>}
        {error && <p className="error import-error" role="alert">{error}</p>}
      </section>}

      <section className="saved-section completed-results" aria-labelledby="completed-results-title">
        <div className="section-heading"><div>
          <h3 id="completed-results-title">全部采集结果</h3>
          <p>已成功采集并生成素材的商品，可直接编辑上架。</p>
        </div></div>
        {completedJobs.length === 0 ? <div className="empty-state compact-empty"><Clock3 size={24} /><strong>暂时还没有成功结果</strong></div> : (
          <div className="collection-job-list">
            {completedJobs.map((job) => <article className="collection-job completed" key={`completed-${job.id}`}>
              <div className="collection-job-state completed"><CheckCircle2 size={16} /><span>已完成</span></div>
              <div className="collection-job-copy"><strong>{job.source_product?.title || shortSource(job.source_url)}</strong>
                <span>#{job.id} · {job.campaign_keyword || "独立采集"} · {job.source_product?.image_count ?? 0} 张图片</span></div>
              <div className="collection-job-actions">{job.draft_id && <button className="secondary-button" onClick={() => void openDraftEditor(job.draft_id!)}><FilePlus2 size={16} /> 编辑上架</button>}
                {job.source_product?.primary_image_url && <img className="completed-result-thumb" src={job.source_product.primary_image_url} alt="" />}</div>
            </article>)}
          </div>
        )}
      </section>

      <section className="saved-section" aria-labelledby="collection-queue-title">
        <div className="section-heading">
          <div>
              <h3 id="collection-queue-title">{selectedCampaign ? `${selectedCampaign.name} · 采集结果` : "采集库"}</h3>
              <p>{selectedCampaign ? "按关键词显示该任务采集到的商品；完成后可直接编辑上架。" : `${displayedCollectionJobs.length} 个采集任务`}</p>
          </div>
        </div>

        {displayedCollectionJobs.length === 0 ? (
          <div className="empty-state compact-empty">
            <Clock3 size={24} />
            <strong>暂无采集任务</strong>
          </div>
        ) : (
          <div className="collection-job-list">
            {displayedCollectionJobs.map((job) => {
              const isDeferred = job.status === "pending"
                && Boolean(job.next_attempt_at)
                && new Date(job.next_attempt_at!).getTime() > Date.now();
              const canRun = job.status !== "running"
                && job.status !== "completed"
                && !isDeferred;
              const needsSnapshot = job.status === "needs_manual_action";
              const sourceDetail = job.source_product
                ? sourceDetails[job.source_product.id]
                : undefined;
              const sourceVariants = uniqueSourceVariants(sourceDetail?.snapshot?.variants ?? []);
              const missingVariantCount = sourceVariants.filter(
                (variant) => !variant.selected && !findVariantCollectionJob(
                  displayedCollectionJobs,
                  job.source_url,
                  variant.asin,
                  job.target_site_id,
                ),
              ).length ?? 0;
              const variantBatchKey = job.source_product
                ? `${job.source_product.id}:${job.target_site_id}`
                : "";
              const variantBatchResult = variantBatchResults[variantBatchKey];
              return (
                <article className={`collection-job ${job.status}`} key={job.id}>
                  <div className={`collection-job-state ${job.status}`}>
                    {jobIcon(job.status)}
                    <span>{JOB_LABELS[job.status]}</span>
                  </div>
                  <div className="collection-job-copy">
                    <strong title={job.source_url}>{shortSource(job.source_url)}</strong>
                    <span>#{job.id} · {job.target_site_id} · {new Date(job.created_at).toLocaleString()}</span>
                    {isDeferred && (
                      <span className="collection-job-schedule">
                        下次尝试：{new Date(job.next_attempt_at!).toLocaleString()}
                      </span>
                    )}
                    {job.message && <p>{collectionMessage(job.message)}</p>}
                    {job.source_product && (
                      <div className={`source-snapshot-review ${job.source_product.primary_image_url ? "" : "without-image"}`}>
                        {job.source_product.primary_image_url && (
                          <img src={job.source_product.primary_image_url} alt="" />
                        )}
                        <div className="source-snapshot-copy">
                          <strong>{job.source_product.title}</strong>
                          <span>
                            {job.source_product.collection_method === "operator_snapshot"
                              ? "人工补救采集"
                              : job.source_product.collection_method === "server_browser_headed"
                                ? "服务器浏览器采集"
                                : job.source_product.collection_method === "server_browser_headless"
                                  ? "服务器无头浏览器采集"
                                  : "页面自动采集"}
                            {job.source_product.brand ? ` · ${job.source_product.brand}` : ""}
                          </span>
                          <span>
                            {job.source_product.source_currency} {job.source_product.source_price ?? "-"}
                            {` · ${job.source_product.image_count} 张图片`}
                            {` · ${job.source_product.variant_count} 个变体`}
                          </span>
                          {!job.source_product.has_snapshot && (
                            <p className="source-unavailable">
                              {collectionMessage(job.source_product.collection_error || "未能获取商品页面素材。")}
                            </p>
                          )}
                          {expandedSourceId === job.source_product.id && sourceDetails[job.source_product.id]?.snapshot && (
                            <div className="source-detail">
                              <div className="source-image-gallery">
                                {sourceDetails[job.source_product.id].snapshot!.images.map((imageUrl) => (
                                  <img src={imageUrl} alt="" key={imageUrl} />
                                ))}
                              </div>
                              {sourceDetails[job.source_product.id].snapshot!.bullets.length > 0 && (
                                <ul>
                                  {sourceDetails[job.source_product.id].snapshot!.bullets.map((bullet) => (
                                    <li key={bullet}>{bullet}</li>
                                  ))}
                                </ul>
                              )}
                              {Object.entries(sourceDetails[job.source_product.id].snapshot!.measurements)
                                .filter(([, measurement]) => Boolean(measurement))
                                .length > 0 && (
                                <div className="source-measurements">
                                  {Object.entries(sourceDetails[job.source_product.id].snapshot!.measurements)
                                    .filter((entry): entry is [string, NonNullable<typeof entry[1]>] => Boolean(entry[1]))
                                    .map(([key, measurement]) => (
                                      <span key={key}>
                                        <small>{measurement.source_label}</small>
                                        <strong>{measurement.raw}</strong>
                                      </span>
                                    ))}
                                </div>
                              )}
                              <div className="source-variant-heading">
                                <span>
                                  <strong>变体</strong>
                                  <small>{missingVariantCount} 个待采集</small>
                                </span>
                                <button
                                  className="icon-text-button"
                                  disabled={isBusy || missingVariantCount === 0}
                                  onClick={() => void collectMissingSourceVariants(
                                    job.source_product!.id,
                                    job.target_site_id,
                                  )}
                                >
                                  {busyAction === `collect-variant-batch-${variantBatchKey}` ? (
                                    <LoaderCircle className="spin" size={14} />
                                  ) : (
                                    <ListPlus size={14} />
                                  )}
                                  {variantBatchResult
                                      ? `${variantBatchResult.created_count} 个已加入 · ${variantBatchResult.reused_count} 个已有`
                                      : missingVariantCount > 0
                                        ? `采集其余 ${missingVariantCount} 个`
                                        : "所有变体已加入队列"}
                                </button>
                              </div>
                              <div className="source-variant-list">
                                {sourceVariants.map((variant) => {
                                  const variantJob = findVariantCollectionJob(
                                    displayedCollectionJobs,
                                    job.source_url,
                                    variant.asin,
                                    job.target_site_id,
                                  );
                                  const variantKey = `${job.source_product!.id}:${variant.asin}:${job.target_site_id}`;
                                  return (
                                  <span className={variant.selected ? "selected" : ""} key={variant.asin}>
                                    <strong>{Object.values(variant.attributes).join(" · ") || variant.asin}</strong>
                                    <small>{variant.asin}</small>
                                    {!variant.selected && (
                                      <button
                                        className="icon-text-button"
                                        disabled={isBusy || Boolean(variantJob)}
                                        onClick={() => void collectSourceVariant(
                                          job.source_product!.id,
                                          variant.asin,
                                          job.target_site_id,
                                        )}
                                      >
                                        {busyAction === `collect-variant-${variantKey}` ? (
                                          <LoaderCircle className="spin" size={14} />
                                        ) : (
                                          <ScanSearch size={14} />
                                        )}
                                        {variantJob
                                          ? `${JOB_LABELS[variantJob.status]} #${variantJob.id}`
                                          : "采集该变体"}
                                      </button>
                                    )}
                                    {variant.selected && job.draft_id ? (
                                      <span className="record-id">草稿 #{job.draft_id}</span>
                                    ) : variant.selected ? (
                                      <button
                                        className="icon-text-button"
                                        disabled={isBusy}
                                        onClick={() => void useSourceVariant(
                                          job.source_product!.id,
                                          variant.asin,
                                          job.target_site_id,
                                        )}
                                      >
                                        {busyAction === `variant-${variantKey}` ? (
                                          <LoaderCircle className="spin" size={14} />
                                        ) : (
                                          <FilePlus2 size={14} />
                                        )}
                                        {variantDraftIds[`${job.source_product!.id}:${variant.asin}:${job.target_site_id}`]
                                          ? `草稿 #${variantDraftIds[`${job.source_product!.id}:${variant.asin}:${job.target_site_id}`]}`
                                          : `创建 ${job.target_site_id} 草稿`}
                                      </button>
                                    ) : variantJob?.status === "completed" && variantJob.draft_id ? (
                                      <span className="record-id">草稿 #{variantJob.draft_id}</span>
                                    ) : null}
                                  </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="collection-job-actions">
                    {job.draft_id && <button
                      className="secondary-button"
                      disabled={isBusy}
                      onClick={() => void openDraftEditor(job.draft_id!)}
                    >
                      <FilePlus2 size={16} /> {busyAction === `open-draft-${job.draft_id}` ? "打开中" : "编辑上架"}
                    </button>}
                    {job.source_product?.has_snapshot && (
                      <button
                        className="secondary-button"
                        disabled={isBusy}
                        onClick={() => void toggleSourceReview(job.source_product!.id)}
                      >
                        {busyAction === `source-${job.source_product.id}` ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : (
                          <Search size={16} />
                        )}
                        {expandedSourceId === job.source_product.id ? "收起素材" : "查看素材"}
                      </button>
                    )}
                    {needsSnapshot && (
                      <button
                        className="secondary-button"
                        disabled={isBusy}
                        onClick={() => useSnapshotFallback(job)}
                      >
                        <FileCode2 size={16} /> 人工补救
                      </button>
                    )}
                    {canRun && !needsSnapshot && (
                      <button
                        className="secondary-button"
                        disabled={isBusy}
                        onClick={() => void runJob(job)}
                      >
                        {busyAction === `job-${job.id}` ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : job.status === "failed" ? (
                          <RotateCcw size={16} />
                        ) : (
                          <Play size={16} />
                        )}
                        {job.status === "failed" ? "重新采集" : "立即执行"}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </section>
  );
}
