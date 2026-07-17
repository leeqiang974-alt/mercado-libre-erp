import { useEffect, useState } from "react";
import { CheckCircle2, Link2, RefreshCw, Store as StoreIcon } from "lucide-react";
import { getMeliAuthorizationUrl, listStores, type StoreRecord } from "../api/client";

export function StoresPage() {
  const [status, setStatus] = useState("");
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [loading, setLoading] = useState(true);

  async function refreshStores() {
    setLoading(true);
    try {
      setStores(await listStores());
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load stores");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("meli_auth") === "authorized") {
      setStatus(`Store ${query.get("seller_id") ?? ""} connected successfully.`);
      window.history.replaceState({}, "", window.location.pathname);
    }
    void refreshStores();
  }, []);

  async function startAuthorization() {
    setStatus("Preparing authorization link");
    try {
      const result = await getMeliAuthorizationUrl();
      window.location.assign(result.authorization_url);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Authorization failed");
    }
  }

  return (
    <section className="workspace">
      <header className="page-header">
        <div>
          <span className="eyebrow">Account connections</span>
          <h2>Authorized stores</h2>
          <p>Connect each Mercado Libre seller account before publishing.</p>
        </div>
        <div className="page-actions">
          <button className="secondary-button icon-text" onClick={() => void refreshStores()} disabled={loading}>
            <RefreshCw size={16} /> Refresh
          </button>
          <button className="icon-text" onClick={startAuthorization}>
            <Link2 size={16} /> Connect store
          </button>
        </div>
      </header>

      {status && <div className="status-line">{status}</div>}

      <div className="section-heading">
        <div>
          <h3>Seller accounts</h3>
          <p>{stores.length} connected</p>
        </div>
      </div>

      {loading && <div className="empty-state">Loading stores...</div>}
      {!loading && stores.length === 0 && (
        <div className="empty-state">
          <StoreIcon size={28} />
          <strong>No stores connected</strong>
          <p>Use Connect store to authorize a seller account.</p>
        </div>
      )}
      {!loading && stores.length > 0 && (
        <div className="store-list">
          {stores.map((store) => (
            <article className="store-row" key={store.id}>
              <div className="store-mark"><StoreIcon size={18} /></div>
              <div>
                <strong>{store.display_name}</strong>
                <p>Seller {store.seller_id}</p>
              </div>
              <div className="store-site">
                <span>Site</span>
                <strong>{store.site_id}</strong>
              </div>
              <span className="connection-status"><CheckCircle2 size={15} /> Connected</span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
