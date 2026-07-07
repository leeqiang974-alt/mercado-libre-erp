import { useState } from "react";
import {
  createCollectionJob,
  listCollectionJobs,
  runCollectionJob,
  type CollectionJobRecord,
} from "../api/client";

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
  const [sourceUrl, setSourceUrl] = useState("https://www.amazon.com/dp/B000TEST");
  const [targetSiteId, setTargetSiteId] = useState("MLM");
  const [html, setHtml] = useState(
    "<span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
  );
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
        Site
        <input value={targetSiteId} onChange={(event) => setTargetSiteId(event.target.value)} />
      </label>
      <div className="button-row">
        <button onClick={runUrlCollection}>Collect URL and Review</button>
        <button onClick={queueCollectionJob}>Queue URL Job</button>
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
      <label>
        HTML Snapshot
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
        <button onClick={runHtmlImport}>Import Snapshot and Review</button>
      </div>
      <p>{status}</p>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
