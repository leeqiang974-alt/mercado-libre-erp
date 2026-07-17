import { useEffect, useState } from "react";
import { getSystemReadiness, type SystemReadiness } from "../api/client";

function Status({ ready, children }: { ready: boolean; children: React.ReactNode }) {
  return (
    <div className="readiness-row">
      <span className={`status-dot ${ready ? "ready" : "blocked"}`} />
      <span>{children}</span>
      <strong>{ready ? "Ready" : "Action required"}</strong>
    </div>
  );
}

export function DashboardPage({ onNavigate }: { onNavigate: (page: string) => void }) {
  const [readiness, setReadiness] = useState<SystemReadiness | null>(null);
  const [error, setError] = useState("");

  async function refresh() {
    setError("");
    try {
      setReadiness(await getSystemReadiness());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load system status");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">Operations</p>
          <h2>Amazon to Mercado Libre</h2>
          <p>Collect, prepare, review, and publish non-FULL listings from one queue.</p>
        </div>
        <button className="secondary-button" onClick={refresh}>Refresh status</button>
      </header>

      {error && <p className="error">{error}</p>}
      {!readiness && !error && <p>Loading system status...</p>}
      {readiness && (
        <>
          <div className="metric-strip">
            <div><span>Drafts</span><strong>{readiness.counts.drafts}</strong></div>
            <div><span>Collection jobs</span><strong>{readiness.counts.collection_jobs}</strong></div>
            <div><span>Publish jobs</span><strong>{readiness.counts.publish_jobs}</strong></div>
            <div><span>Stores</span><strong>{readiness.mercado_libre.connected_stores}</strong></div>
          </div>

          <div className="section-grid">
            <section className="surface">
              <h3>Integration readiness</h3>
              <Status ready={readiness.amazon_collector}>Amazon page collector</Status>
              <Status ready={readiness.mercado_libre.credentials_configured}>Mercado Libre application credentials</Status>
              <Status ready={readiness.mercado_libre.connected_stores > 0}>Authorized Mercado Libre store</Status>
              <Status ready={readiness.ai.claude_configured}>Claude review provider</Status>
              <Status ready={readiness.ai.nvidia_configured}>NVIDIA review provider</Status>
              <Status ready={readiness.mercado_libre.live_publish_enabled}>Live publishing</Status>
            </section>

            <section className="surface">
              <h3>Next operation</h3>
              {!readiness.mercado_libre.credentials_configured ? (
                <p>Configure the Mercado Libre application before store authorization.</p>
              ) : readiness.mercado_libre.connected_stores === 0 ? (
                <p>Authorize at least one Mercado Libre store.</p>
              ) : readiness.counts.drafts === 0 ? (
                <p>Add a real Amazon product URL to start the collection queue.</p>
              ) : (
                <p>Open the draft queue, select a collected product, and complete its mapping.</p>
              )}
              <div className="command-list">
                <button onClick={() => onNavigate("import")}>Add Amazon products</button>
                <button className="secondary-button" onClick={() => onNavigate("drafts")}>Open draft queue</button>
                <button className="secondary-button" onClick={() => onNavigate("stores")}>Manage stores</button>
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  );
}
