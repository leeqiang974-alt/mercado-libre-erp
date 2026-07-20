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
  createSourceVariantCollectionJob,
  createSourceVariantCollectionJobs,
  createSourceVariantDraft,
  getSourceProduct,
  listCollectionJobs,
  listCollectionJobStatuses,
  runCollectionJob,
  type CollectionBatchResult,
  type CollectionJobRecord,
  type AmazonSourceVariant,
  type SourceProductRecord,
  type SourceVariantCollectionBatchResult,
} from "../api/client";
import { MERCADO_LIBRE_SITES } from "../domain/sites";

type ImportMode = "url" | "html";

const JOB_LABELS: Record<CollectionJobRecord["status"], string> = {
  pending: "Pending",
  running: "Running",
  completed: "Collected",
  needs_manual_action: "Manual action",
  failed: "Failed",
};

const BATCH_LABELS: Record<CollectionBatchResult["items"][number]["outcome"], string> = {
  created: "Queued",
  duplicate_input: "Duplicate input",
  existing: "Already exists",
  invalid: "Invalid URL",
};

const BATCH_DETAILS: Record<string, string> = {
  only_public_amazon_product_urls_allowed: "Use a public Amazon product URL",
  duplicate_amazon_product_in_request: "Same product appears earlier in this batch",
  collection_job_already_exists: "A collection job already exists",
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
  onCollectUrl,
  status,
}: {
  onImportHtml: (
    sourceUrl: string,
    html: string,
    targetSiteId: string,
    persist: boolean,
    collectionJobId: number | null,
  ) => Promise<void>;
  onCollectUrl: (sourceUrl: string, targetSiteId: string) => Promise<void>;
  status: string;
}) {
  const [mode, setMode] = useState<ImportMode>("url");
  const [sourceUrls, setSourceUrls] = useState("");
  const [snapshotUrl, setSnapshotUrl] = useState("");
  const [targetSiteId, setTargetSiteId] = useState("MLM");
  const [html, setHtml] = useState("");
  const [persist, setPersist] = useState(true);
  const [snapshotJobId, setSnapshotJobId] = useState<number | null>(null);
  const [allowExisting, setAllowExisting] = useState(false);
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
      const [jobs, knownStatuses] = await Promise.all([
        listCollectionJobs(),
        listCollectionJobStatuses(knownJobIds),
      ]);
      if (requestEpoch === collectionRequestEpoch.current) {
        setCollectionJobs(jobs);
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
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    async function poll() {
      await refreshCollectionJobs(false);
      if (!cancelled) {
        timer = window.setTimeout(() => void poll(), 5000);
      }
    }
    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [refreshCollectionJobs]);

  async function runUrlCollection() {
    setError("");
    setBusyAction("collect");
    try {
      await onCollectUrl(urlEntries[0], targetSiteId);
      await refreshCollectionJobs(false);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Collection failed");
    } finally {
      setBusyAction("");
    }
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
    } catch (variantError) {
      setError(variantError instanceof Error ? variantError.message : "Failed to create variant draft");
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
      [...Object.values(knownVariantJobs), ...collectionJobs].map((job) => [job.id, job]),
    ).values(),
  ).sort((left, right) => right.id - left.id);
  const urlEntries = sourceUrls
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean);
  const urlCountValid = urlEntries.length > 0 && urlEntries.length <= 100;

  return (
    <section className="workspace import-workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">Source acquisition</p>
          <h2>Amazon import</h2>
          <p>Collect product data into a reviewable draft.</p>
        </div>
        <button
          className="icon-button"
          title="Refresh collection queue"
          aria-label="Refresh collection queue"
          disabled={isBusy}
          onClick={() => void refreshCollectionJobs()}
        >
          <RefreshCw size={17} />
        </button>
      </header>

      <div className="import-mode-switch" role="tablist" aria-label="Amazon import method">
        <button
          role="tab"
          aria-selected={mode === "url"}
          className={mode === "url" ? "selected" : ""}
          onClick={() => setMode("url")}
        >
          <Link2 size={17} /> URL collector
        </button>
        <button
          role="tab"
          aria-selected={mode === "html"}
          className={mode === "html" ? "selected" : ""}
          onClick={() => setMode("html")}
        >
          <FileCode2 size={17} /> HTML snapshot
        </button>
      </div>

      <section className="surface import-source">
        <div className="form-grid two-col">
          <label>
            {mode === "url" ? "Amazon product URLs" : "Amazon product URL"}
            {mode === "url" ? (
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
            Target Mercado Libre site
            <select
              value={targetSiteId}
              onChange={(event) => {
                setTargetSiteId(event.target.value);
                setSnapshotJobId(null);
                setBatchResult(null);
              }}
            >
              {MERCADO_LIBRE_SITES.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.country} ({site.id}) · {site.currency}
                </option>
              ))}
            </select>
          </label>
        </div>

        {mode === "url" ? (
          <>
            <div className="inline-warning import-warning">
              <AlertTriangle size={17} />
              <span>Amazon challenges are stopped and moved to manual snapshot handling.</span>
            </div>
            <div className="batch-options">
              <span className={urlEntries.length > 100 ? "error" : ""}>
                {urlEntries.length} / 100 URLs
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
                Queue previously imported URLs again
              </label>
            </div>
            <div className="button-row">
              <button disabled={urlEntries.length !== 1 || isBusy} onClick={runUrlCollection}>
                {busyAction === "collect" ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
                Collect now
              </button>
              <button
                className="secondary-button"
                disabled={!urlCountValid || isBusy}
                onClick={queueCollectionJob}
              >
                {busyAction === "queue" ? <LoaderCircle className="spin" size={17} /> : <ListPlus size={17} />}
                {urlEntries.length > 1 ? `Add ${urlEntries.length} to queue` : "Add to queue"}
              </button>
            </div>
            {batchResult && (
              <div className="batch-result" aria-live="polite">
                <div className="batch-result-summary">
                  <strong>{batchResult.created_count} queued</strong>
                  <span>{batchResult.existing_count} existing</span>
                  <span>{batchResult.duplicate_count} duplicates</span>
                  <span>{batchResult.invalid_count} invalid</span>
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
                          ? `Job #${item.job.id}`
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
              Amazon HTML snapshot
              <textarea
                className="snapshot-input"
                placeholder="Paste the saved Amazon product page HTML"
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
                {snapshotJobId !== null ? `Resolve job #${snapshotJobId} and save draft` : "Save as product draft"}
              </label>
              <button disabled={!snapshotUrl.trim() || !html.trim() || isBusy} onClick={runHtmlImport}>
                {busyAction === "html" ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}
                Import snapshot
              </button>
            </div>
          </>
        )}

        {status && <p className="status-line">{status}</p>}
        {error && <p className="error import-error" role="alert">{error}</p>}
      </section>

      <section className="saved-section" aria-labelledby="collection-queue-title">
        <div className="section-heading">
          <div>
            <h3 id="collection-queue-title">Collection queue</h3>
            <p>{displayedCollectionJobs.length} jobs</p>
          </div>
        </div>

        {displayedCollectionJobs.length === 0 ? (
          <div className="empty-state compact-empty">
            <Clock3 size={24} />
            <strong>No collection jobs</strong>
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
                        Next attempt {new Date(job.next_attempt_at!).toLocaleString()}
                      </span>
                    )}
                    {job.message && <p>{job.message}</p>}
                    {job.source_product && (
                      <div className="source-snapshot-review">
                        {job.source_product.primary_image_url && (
                          <img src={job.source_product.primary_image_url} alt="" />
                        )}
                        <div className="source-snapshot-copy">
                          <strong>{job.source_product.title}</strong>
                          <span>
                            {job.source_product.collection_method === "browser_page" ? "Page collected" : "Operator snapshot"}
                            {job.source_product.brand ? ` · ${job.source_product.brand}` : ""}
                          </span>
                          <span>
                            {job.source_product.source_currency} {job.source_product.source_price ?? "-"}
                            {` · ${job.source_product.image_count} images`}
                            {` · ${job.source_product.variant_count} variants`}
                          </span>
                          {!job.source_product.has_snapshot && (
                            <p className="source-unavailable">
                              {job.source_product.collection_error || "Source details were not captured."}
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
                                  <strong>Variants</strong>
                                  <small>{missingVariantCount} missing collections</small>
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
                                    ? `${variantBatchResult.created_count} queued · ${variantBatchResult.reused_count} existing`
                                    : missingVariantCount > 0
                                      ? `Collect ${missingVariantCount} missing`
                                      : "All variants queued"}
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
                                          : "Collect variant"}
                                      </button>
                                    )}
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
                                        ? `Draft #${variantDraftIds[`${job.source_product!.id}:${variant.asin}:${job.target_site_id}`]}`
                                        : `Create ${job.target_site_id} draft`}
                                    </button>
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
                    {job.draft_id && <span className="record-id">Draft #{job.draft_id}</span>}
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
                        {expandedSourceId === job.source_product.id ? "Close source" : "Review source"}
                      </button>
                    )}
                    {needsSnapshot && (
                      <button
                        className="secondary-button"
                        disabled={isBusy}
                        onClick={() => useSnapshotFallback(job)}
                      >
                        <FileCode2 size={16} /> Snapshot
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
                        {job.status === "failed" ? "Retry" : "Run"}
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
