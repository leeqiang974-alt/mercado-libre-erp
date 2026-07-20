import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileCode2,
  Link2,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Upload,
} from "lucide-react";
import {
  createCollectionJob,
  listCollectionJobs,
  runCollectionJob,
  type CollectionJobRecord,
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
  ) => Promise<void>;
  onCollectUrl: (sourceUrl: string, targetSiteId: string) => Promise<void>;
  status: string;
}) {
  const [mode, setMode] = useState<ImportMode>("url");
  const [sourceUrl, setSourceUrl] = useState("");
  const [targetSiteId, setTargetSiteId] = useState("MLM");
  const [html, setHtml] = useState("");
  const [persist, setPersist] = useState(true);
  const [collectionJobs, setCollectionJobs] = useState<CollectionJobRecord[]>([]);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");

  const refreshCollectionJobs = useCallback(async (showError = true) => {
    try {
      setCollectionJobs(await listCollectionJobs());
    } catch (jobError) {
      if (showError) {
        setError(jobError instanceof Error ? jobError.message : "Failed to load collection jobs");
      }
    }
  }, []);

  useEffect(() => {
    void refreshCollectionJobs();
    const timer = window.setInterval(() => void refreshCollectionJobs(false), 5000);
    return () => window.clearInterval(timer);
  }, [refreshCollectionJobs]);

  async function runUrlCollection() {
    setError("");
    setBusyAction("collect");
    try {
      await onCollectUrl(sourceUrl, targetSiteId);
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
      await onImportHtml(sourceUrl, html, targetSiteId, persist);
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
      await createCollectionJob(sourceUrl, targetSiteId);
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
      await runCollectionJob(job.id);
      await refreshCollectionJobs(false);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to run collection job");
    } finally {
      setBusyAction("");
    }
  }

  function useSnapshotFallback(job: CollectionJobRecord) {
    setSourceUrl(job.source_url);
    setTargetSiteId(job.target_site_id);
    setMode("html");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const isBusy = Boolean(busyAction);

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
            Amazon product URL
            <input
              type="url"
              placeholder="https://www.amazon.com/dp/..."
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
            />
          </label>
          <label>
            Target Mercado Libre site
            <select value={targetSiteId} onChange={(event) => setTargetSiteId(event.target.value)}>
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
            <div className="button-row">
              <button disabled={!sourceUrl.trim() || isBusy} onClick={runUrlCollection}>
                {busyAction === "collect" ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
                Collect now
              </button>
              <button
                className="secondary-button"
                disabled={!sourceUrl.trim() || isBusy}
                onClick={queueCollectionJob}
              >
                {busyAction === "queue" ? <LoaderCircle className="spin" size={17} /> : <Plus size={17} />}
                Add to queue
              </button>
            </div>
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
                />
                Save as product draft
              </label>
              <button disabled={!sourceUrl.trim() || !html.trim() || isBusy} onClick={runHtmlImport}>
                {busyAction === "html" ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}
                Import snapshot
              </button>
            </div>
          </>
        )}

        {status && <p className="status-line">{status}</p>}
        {error && <p className="error import-error">{error}</p>}
      </section>

      <section className="saved-section" aria-labelledby="collection-queue-title">
        <div className="section-heading">
          <div>
            <h3 id="collection-queue-title">Collection queue</h3>
            <p>{collectionJobs.length} jobs</p>
          </div>
        </div>

        {collectionJobs.length === 0 ? (
          <div className="empty-state compact-empty">
            <Clock3 size={24} />
            <strong>No collection jobs</strong>
          </div>
        ) : (
          <div className="collection-job-list">
            {collectionJobs.map((job) => {
              const canRun = job.status !== "running" && job.status !== "completed";
              const needsSnapshot = job.status === "needs_manual_action";
              return (
                <article className={`collection-job ${job.status}`} key={job.id}>
                  <div className={`collection-job-state ${job.status}`}>
                    {jobIcon(job.status)}
                    <span>{JOB_LABELS[job.status]}</span>
                  </div>
                  <div className="collection-job-copy">
                    <strong title={job.source_url}>{shortSource(job.source_url)}</strong>
                    <span>#{job.id} · {job.target_site_id} · {new Date(job.created_at).toLocaleString()}</span>
                    {job.message && <p>{job.message}</p>}
                  </div>
                  <div className="collection-job-actions">
                    {job.draft_id && <span className="record-id">Draft #{job.draft_id}</span>}
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
