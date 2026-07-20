import { useEffect, useState, type ReactNode } from "react";
import { CheckCircle2, KeyRound, Link2, RefreshCw, Save, Store as StoreIcon, Trash2 } from "lucide-react";
import {
  getIntegrationCredentialStatus,
  getMeliAuthorizationUrl,
  listStores,
  saveIntegrationCredentials,
  type IntegrationCredentialStatus,
  type IntegrationCredentialsUpdate,
  type StoreRecord,
} from "../api/client";

export function StoresPage() {
  const [status, setStatus] = useState("");
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [credentialStatus, setCredentialStatus] = useState<IntegrationCredentialStatus | null>(null);
  const [credentials, setCredentials] = useState({
    meli_client_id: "",
    meli_client_secret: "",
    claude_api_key: "",
    nvidia_api_key: "",
  });
  const [savingCredentials, setSavingCredentials] = useState(false);
  const hasCredentialChanges = Object.values(credentials).some((value) => value.trim());

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
    void getIntegrationCredentialStatus()
      .then(setCredentialStatus)
      .catch((error) => setStatus(error instanceof Error ? error.message : "Failed to load credentials"));
  }, []);

  async function saveCredentials() {
    const payload = Object.fromEntries(
      Object.entries(credentials).filter(([, value]) => value.trim()),
    ) as IntegrationCredentialsUpdate;
    if (Object.keys(payload).length === 0) return;
    setSavingCredentials(true);
    setStatus("");
    try {
      setCredentialStatus(await saveIntegrationCredentials(payload));
      setCredentials({
        meli_client_id: "",
        meli_client_secret: "",
        claude_api_key: "",
        nvidia_api_key: "",
      });
      setStatus("Integration credentials updated.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to update credentials");
    } finally {
      setSavingCredentials(false);
    }
  }

  async function clearCredentials(payload: IntegrationCredentialsUpdate) {
    setSavingCredentials(true);
    setStatus("");
    try {
      setCredentialStatus(await saveIntegrationCredentials(payload));
      setStatus("Integration credentials cleared.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to clear credentials");
    } finally {
      setSavingCredentials(false);
    }
  }

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
          <button className="icon-text" onClick={startAuthorization} disabled={loading || !credentialStatus?.meli_client_id_configured || !credentialStatus?.meli_client_secret_configured}>
            <Link2 size={16} /> Connect store
          </button>
        </div>
      </header>

      {status && <div className="status-line">{status}</div>}

      <section className="integration-settings">
        <div className="section-heading">
          <div>
            <h3>Integration credentials</h3>
            <p>{credentialStatus?.meli_redirect_uri ?? ""}</p>
          </div>
          <button className="icon-text" onClick={saveCredentials} disabled={savingCredentials || !hasCredentialChanges}>
            <Save size={16} /> Save credentials
          </button>
        </div>
        <div className="credential-provider-list">
          <CredentialRow
            icon={<StoreIcon size={18} />}
            name="Mercado Libre app"
            state={credentialStatus?.meli_client_id_configured && credentialStatus.meli_client_secret_configured ? "Configured" : "Not configured"}
            fields={[
              ["Client ID", "meli_client_id"],
              ["Client secret", "meli_client_secret"],
            ]}
            values={credentials}
            onChange={(key, value) => setCredentials((current) => ({ ...current, [key]: value }))}
            onClear={() => clearCredentials({ meli_client_id: "", meli_client_secret: "" })}
            clearDisabled={savingCredentials || !(credentialStatus?.meli_client_id_configured || credentialStatus?.meli_client_secret_configured)}
          />
          <CredentialRow
            icon={<KeyRound size={18} />}
            name="Claude"
            state={credentialStatus?.claude_api_key_configured ? credentialStatus.claude_model : "Not configured"}
            fields={[["API key", "claude_api_key"]]}
            values={credentials}
            onChange={(key, value) => setCredentials((current) => ({ ...current, [key]: value }))}
            onClear={() => clearCredentials({ claude_api_key: "" })}
            clearDisabled={savingCredentials || !credentialStatus?.claude_api_key_configured}
          />
          <CredentialRow
            icon={<KeyRound size={18} />}
            name="NVIDIA"
            state={credentialStatus?.nvidia_api_key_configured ? credentialStatus.nvidia_model : "Not configured"}
            fields={[["API key", "nvidia_api_key"]]}
            values={credentials}
            onChange={(key, value) => setCredentials((current) => ({ ...current, [key]: value }))}
            onClear={() => clearCredentials({ nvidia_api_key: "" })}
            clearDisabled={savingCredentials || !credentialStatus?.nvidia_api_key_configured}
          />
        </div>
      </section>

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

type CredentialKey = "meli_client_id" | "meli_client_secret" | "claude_api_key" | "nvidia_api_key";

function CredentialRow({
  icon,
  name,
  state,
  fields,
  values,
  onChange,
  onClear,
  clearDisabled,
}: {
  icon: ReactNode;
  name: string;
  state: string;
  fields: [string, CredentialKey][];
  values: Record<CredentialKey, string>;
  onChange: (key: CredentialKey, value: string) => void;
  onClear: () => void;
  clearDisabled: boolean;
}) {
  return (
    <div className="credential-provider-row">
      <div className="credential-provider-name">
        {icon}
        <span><strong>{name}</strong><small>{state}</small></span>
      </div>
      {fields.map(([label, key]) => (
        <label key={key}>
          {label}
          <input type="password" value={values[key]} onChange={(event) => onChange(key, event.target.value)} autoComplete="new-password" />
        </label>
      ))}
      {fields.length === 1 && <span />}
      <button className="icon-button secondary-button" title={`Clear ${name} credentials`} aria-label={`Clear ${name} credentials`} disabled={clearDisabled} onClick={onClear}><Trash2 size={16} /></button>
    </div>
  );
}
