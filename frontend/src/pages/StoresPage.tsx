import { useState } from "react";
import { getMeliAuthorizationUrl } from "../api/client";

export function StoresPage() {
  const [status, setStatus] = useState("");
  const [authUrl, setAuthUrl] = useState("");

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
    </section>
  );
}
