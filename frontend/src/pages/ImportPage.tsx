import { useState } from "react";

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
      </div>
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
