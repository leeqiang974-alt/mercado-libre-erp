import { useState } from "react";

export function ImportPage({
  onImport,
  status,
}: {
  onImport: (sourceUrl: string, html: string, targetSiteId: string) => Promise<void>;
  status: string;
}) {
  const [sourceUrl, setSourceUrl] = useState("https://www.amazon.com/dp/B000TEST");
  const [targetSiteId, setTargetSiteId] = useState("MLM");
  const [html, setHtml] = useState(
    "<span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
  );
  const [error, setError] = useState("");

  async function runImport() {
    setError("");
    try {
      await onImport(sourceUrl, html, targetSiteId);
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
      <label>
        HTML Snapshot
        <textarea value={html} onChange={(event) => setHtml(event.target.value)} />
      </label>
      <button onClick={runImport}>Import and Review</button>
      <p>{status}</p>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
