import { useEffect, useState } from "react";
import { getMeliAuthorizationUrl, listStores, type StoreRecord } from "../api/client";

export function StoresPage() {
  const [status, setStatus] = useState("");
  const [authUrl, setAuthUrl] = useState("");
  const [stores, setStores] = useState<StoreRecord[]>([]);

  async function refreshStores() {
    try {
      setStores(await listStores());
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load stores");
    }
  }

  useEffect(() => {
    void refreshStores();
  }, []);

  async function startAuthorization() {
    setStatus("Preparing authorization link");
    setAuthUrl("");
    try {
      const result = await getMeliAuthorizationUrl();
      setAuthUrl(result.authorization_url);
      setStatus(`State: ${result.state}`);
      window.open(result.authorization_url, "_blank", "noopener,noreferrer");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Authorization failed");
    }
  }

  return (
    <section className="panel">
      <h2>Authorized Stores</h2>
      <button onClick={startAuthorization}>Connect Mercado Libre Store</button>
      <p>{status}</p>
      {authUrl && (
        <p>
          <a href={authUrl} target="_blank" rel="noreferrer">
            Open authorization link
          </a>
        </p>
      )}
      <h3>Connected Stores</h3>
      {stores.length === 0 && <p>No stores connected yet.</p>}
      {stores.length > 0 && <pre>{JSON.stringify(stores, null, 2)}</pre>}
    </section>
  );
}
