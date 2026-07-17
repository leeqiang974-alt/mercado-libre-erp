import { useState } from "react";
import {
  createCollectionJob,
  listCollectionJobs,
  runCollectionJob,
  type CollectionJobRecord,
} from "../api/client";
import { MERCADO_LIBRE_SITES } from "../domain/sites";

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
  const [sourceUrl, setSourceUrl] = useState("");
  const [targetSiteId, setTargetSiteId] = useState("MLM");
  const [html, setHtml] = useState("");
  const [persist, setPersist] = useState(true);
  const [collectionJobs, setCollectionJobs] = useState<CollectionJobRecord[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function runUrlCollection() {
    setError("");
    try {
      await onCollectUrl(sourceUrl, targetSiteId);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Collection failed");
    }
  }

  async function runHtmlImport() {
    setError("");
    try {
      await onImportHtml(sourceUrl, html, targetSiteId, persist);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Import failed");
    }
  }

  async function queueCollectionJob() {
    setError("");
    try {
      const job = await createCollectionJob(sourceUrl, targetSiteId);
      setSelectedJobId(job.id);
      setCollectionJobs(await listCollectionJobs());
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to create collection job");
    }
  }

  async function refreshCollectionJobs() {
    setError("");
    try {
      const jobs = await listCollectionJobs();
      setCollectionJobs(jobs);
      if (!selectedJobId && jobs.length > 0) {
        setSelectedJobId(jobs[0].id);
      }
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to load collection jobs");
    }
  }

  async function runSelectedCollectionJob() {
    if (!selectedJobId) return;
    setError("");
    try {
      await runCollectionJob(selectedJobId);
      setCollectionJobs(await listCollectionJobs());
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : "Failed to run collection job");
    }
  }

  return (
    <section className="panel">
      <h2>Amazon Page Import</h2>
      <label>
        Source URL
        <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
      </label>
      <label>
        Target Mercado Libre site
        <select value={targetSiteId} onChange={(event) => setTargetSiteId(event.target.value)}>
          {MERCADO_LIBRE_SITES.map((site) => (
            <option key={site.id} value={site.id}>{site.country} ({site.id}) · {site.currency}</option>
          ))}
        </select>
      </label>
      <div className="button-row">
        <button disabled={!sourceUrl.trim()} onClick={runUrlCollection}>Collect and save</button>
        <button disabled={!sourceUrl.trim()} onClick={queueCollectionJob}>Add to collection queue</button>
        <button onClick={refreshCollectionJobs}>Refresh Jobs</button>
        <button disabled={!selectedJobId} onClick={runSelectedCollectionJob}>
          Run Selected Job
        </button>
      </div>
      {collectionJobs.length > 0 && (
        <>
          <label>
            Collection Job
            <select
              value={selectedJobId ?? ""}
              onChange={(event) => setSelectedJobId(Number(event.target.value))}
            >
              {collectionJobs.map((job) => (
                <option key={job.id} value={job.id}>
                  #{job.id} {job.status} {job.source_url}
                </option>
              ))}
            </select>
          </label>
          <pre>{JSON.stringify(collectionJobs, null, 2)}</pre>
        </>
      )}
      <details className="advanced-section">
        <summary>Advanced: import saved HTML</summary>
      <label>
        Amazon HTML snapshot
        <textarea value={html} onChange={(event) => setHtml(event.target.value)} />
      </label>
      <label className="check-row">
        <input
          type="checkbox"
          checked={persist}
          onChange={(event) => setPersist(event.target.checked)}
        />
        Save snapshot import as draft
      </label>
      <div className="button-row">
        <button disabled={!sourceUrl.trim() || !html.trim()} onClick={runHtmlImport}>Import and save snapshot</button>
      </div>
      </details>
      <p>{status}</p>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
