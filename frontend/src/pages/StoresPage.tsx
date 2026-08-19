import { useEffect, useState, type ReactNode } from "react";
import { Activity, CheckCircle2, CircleAlert, DollarSign, KeyRound, Link2, RefreshCw, Save, Store as StoreIcon, Trash2 } from "lucide-react";
import {
  deactivateProviderModelPrice,
  getIntegrationCredentialStatus,
  getMeliAuthorizationUrl,
  getProviderModelPrices,
  listStores,
  runIntegrationDiagnostics,
  saveIntegrationCredentials,
  saveProviderModelPrice,
  type IntegrationDiagnosticResult,
  type IntegrationDiagnostics,
  type IntegrationCredentialStatus,
  type IntegrationCredentialsUpdate,
  type ProviderModelPrice,
  type StoreRecord,
} from "../api/client";
import { MERCADO_LIBRE_SITES } from "../domain/sites";

export function StoresPage() {
  const [status, setStatus] = useState("");
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [authorizationSiteId, setAuthorizationSiteId] = useState("MLM");
  const [credentialStatus, setCredentialStatus] = useState<IntegrationCredentialStatus | null>(null);
  const [credentials, setCredentials] = useState({
    meli_client_id: "",
    meli_client_secret: "",
    claude_api_key: "",
    nvidia_api_key: "",
    volcengine_api_key: "",
  });
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnostics, setDiagnostics] = useState<IntegrationDiagnostics | null>(null);
  const [modelPrices, setModelPrices] = useState<ProviderModelPrice[]>([]);
  const [savingPrice, setSavingPrice] = useState<"claude" | "nvidia" | null>(null);
  const [priceInputs, setPriceInputs] = useState({
    claude: { currency: "USD", input: "", output: "" },
    nvidia: { currency: "USD", input: "", output: "" },
  });
  const hasCredentialChanges = Object.values(credentials).some((value) => value.trim());

  async function refreshStores() {
    setLoading(true);
    setDiagnostics(null);
    try {
      setStores(await listStores());
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "加载店铺失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("meli_auth") === "authorized") {
      setStatus(
        `店铺 ${query.get("seller_id") ?? ""} 已成功连接到站点 ${query.get("site_id") ?? ""}。`,
      );
      window.history.replaceState({}, "", window.location.pathname);
    }
    void refreshStores();
    void getIntegrationCredentialStatus()
      .then(setCredentialStatus)
      .catch((error) => setStatus(error instanceof Error ? error.message : "加载凭证失败"));
    void getProviderModelPrices()
      .then(setModelPrices)
      .catch((error) => setStatus(error instanceof Error ? error.message : "加载模型价格失败"));
  }, []);

  useEffect(() => {
    if (!credentialStatus) return;
    setPriceInputs((current) => {
      const next = { ...current };
      for (const provider of ["claude", "nvidia"] as const) {
        const model = provider === "claude" ? credentialStatus.claude_model : credentialStatus.nvidia_model;
        const price = modelPrices.find((item) => item.provider === provider && item.model === model);
        if (price) {
          next[provider] = {
            currency: price.currency,
            input: String(price.input_price_per_million),
            output: String(price.output_price_per_million),
          };
        }
      }
      return next;
    });
  }, [credentialStatus, modelPrices]);

  async function saveCredentials() {
    const payload = Object.fromEntries(
      Object.entries(credentials).filter(([, value]) => value.trim()),
    ) as IntegrationCredentialsUpdate;
    if (Object.keys(payload).length === 0) return;
    setSavingCredentials(true);
    setStatus("");
    try {
      setCredentialStatus(await saveIntegrationCredentials(payload));
      setDiagnostics(null);
      setCredentials({
        meli_client_id: "",
        meli_client_secret: "",
        claude_api_key: "",
        nvidia_api_key: "",
        volcengine_api_key: "",
      });
      setStatus("集成凭证已更新。");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "更新凭证失败");
    } finally {
      setSavingCredentials(false);
    }
  }

  async function clearCredentials(payload: IntegrationCredentialsUpdate) {
    setSavingCredentials(true);
    setStatus("");
    try {
      setCredentialStatus(await saveIntegrationCredentials(payload));
      setDiagnostics(null);
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
      const result = await getMeliAuthorizationUrl(authorizationSiteId);
      window.location.assign(result.authorization_url);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Authorization failed");
    }
  }

  async function diagnoseConnections() {
    setDiagnosing(true);
    setStatus("");
    setDiagnostics(null);
    try {
      const result = await runIntegrationDiagnostics();
      setDiagnostics(result);
      setStatus("Connection diagnostics completed.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Connection diagnostics failed");
    } finally {
      setDiagnosing(false);
    }
  }

  async function saveModelPrice(provider: "claude" | "nvidia") {
    if (!credentialStatus) return;
    const values = priceInputs[provider];
    const decimalPattern = /^(?:0|[1-9]\d*)(?:\.\d{1,6})?$/;
    const inputPrice = values.input.trim();
    const outputPrice = values.output.trim();
    const currency = values.currency.trim().toUpperCase();
    if (!decimalPattern.test(inputPrice) || !decimalPattern.test(outputPrice)) {
      setStatus("Enter non-negative model prices with up to six decimal places.");
      return;
    }
    if (!/^[A-Z]{3}$/.test(currency)) {
      setStatus("Enter a three-letter currency code.");
      return;
    }
    setSavingPrice(provider);
    setStatus("");
    try {
      await saveProviderModelPrice({
        provider,
        model: provider === "claude" ? credentialStatus.claude_model : credentialStatus.nvidia_model,
        currency,
        input_price_per_million: inputPrice,
        output_price_per_million: outputPrice,
      });
      setModelPrices(await getProviderModelPrices());
      setStatus(`${provider === "claude" ? "Claude" : "NVIDIA"} model price version saved.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to save model price");
    } finally {
      setSavingPrice(null);
    }
  }

  async function clearModelPrice(provider: "claude" | "nvidia") {
    if (!credentialStatus) return;
    const model = provider === "claude" ? credentialStatus.claude_model : credentialStatus.nvidia_model;
    const current = modelPrices.find((item) => item.provider === provider && item.model === model);
    if (!current) return;
    setSavingPrice(provider);
    setStatus("");
    try {
      await deactivateProviderModelPrice(current.id);
      setModelPrices(await getProviderModelPrices());
      setPriceInputs((values) => ({ ...values, [provider]: { currency: "USD", input: "", output: "" } }));
      setStatus(`${provider === "claude" ? "Claude" : "NVIDIA"} model price deactivated.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to deactivate model price");
    } finally {
      setSavingPrice(null);
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
          <label>Authorization site
            <select
              value={authorizationSiteId}
              onChange={(event) => setAuthorizationSiteId(event.target.value)}
            >
              {MERCADO_LIBRE_SITES.map((site) => (
                <option key={site.id} value={site.id}>{site.country} ({site.id})</option>
              ))}
            </select>
          </label>
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
          <div className="section-heading-actions">
            <button className="secondary-button icon-text" onClick={diagnoseConnections} disabled={diagnosing || savingCredentials}>
              <Activity size={16} /> Run diagnostics
            </button>
            <button className="icon-text" onClick={saveCredentials} disabled={savingCredentials || !hasCredentialChanges}>
              <Save size={16} /> Save credentials
            </button>
          </div>
        </div>
        <div className="credential-provider-list">
          <CredentialRow
            icon={<StoreIcon size={18} />}
            name="美客多应用"
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
            fields={[["API Key", "claude_api_key"]]}
            values={credentials}
            onChange={(key, value) => setCredentials((current) => ({ ...current, [key]: value }))}
            onClear={() => clearCredentials({ claude_api_key: "" })}
            clearDisabled={savingCredentials || !credentialStatus?.claude_api_key_configured}
          />
          <CredentialRow
            icon={<KeyRound size={18} />}
            name="NVIDIA"
            state={credentialStatus?.nvidia_api_key_configured ? credentialStatus.nvidia_model : "Not configured"}
            fields={[["API Key", "nvidia_api_key"]]}
            values={credentials}
            onChange={(key, value) => setCredentials((current) => ({ ...current, [key]: value }))}
            onClear={() => clearCredentials({ nvidia_api_key: "" })}
            clearDisabled={savingCredentials || !credentialStatus?.nvidia_api_key_configured}
          />
          <CredentialRow
            icon={<KeyRound size={18} />}
            name="火山 AI"
            state={credentialStatus?.volcengine_api_key_configured ? credentialStatus.volcengine_model : "未配置"}
            fields={[["API Key", "volcengine_api_key"]]}
            values={credentials}
            onChange={(key, value) => setCredentials((current) => ({ ...current, [key]: value }))}
            onClear={() => clearCredentials({ volcengine_api_key: "" })}
            clearDisabled={savingCredentials || !credentialStatus?.volcengine_api_key_configured}
          />
        </div>
        {diagnostics && (
          <>
            <div className="diagnostic-result-list">
              {diagnostics.results.map((result) => (
                <DiagnosticRow key={`${result.provider}:${result.subject}`} result={result} stores={stores} />
              ))}
            </div>
            <small className="diagnostic-checked-at">Checked {new Date(diagnostics.checked_at).toLocaleString()}</small>
          </>
        )}
      </section>

      <section className="integration-settings">
        <div className="section-heading">
          <div>
            <h3>AI model prices</h3>
            <p>Currency per million input and output tokens</p>
          </div>
        </div>
        <div className="credential-provider-list">
          {(["claude", "nvidia"] as const).map((provider) => {
            const model = provider === "claude" ? credentialStatus?.claude_model ?? "" : credentialStatus?.nvidia_model ?? "";
            const current = modelPrices.find((item) => item.provider === provider && item.model === model);
            return (
              <div className="credential-provider-row model-price-row" key={provider}>
                <div className="credential-provider-name">
                  <DollarSign size={18} />
                  <span><strong>{provider === "claude" ? "Claude" : "NVIDIA"}</strong><small>{model}{current ? ` · ${current.currency} · version ${current.version}` : " · USD · unpriced"}</small></span>
                </div>
                <label>
                  Input / 1M
                  <input type="number" min="0" step="0.000001" value={priceInputs[provider].input} onChange={(event) => setPriceInputs((values) => ({ ...values, [provider]: { ...values[provider], input: event.target.value } }))} />
                </label>
                <label>
                  Output / 1M
                  <input type="number" min="0" step="0.000001" value={priceInputs[provider].output} onChange={(event) => setPriceInputs((values) => ({ ...values, [provider]: { ...values[provider], output: event.target.value } }))} />
                </label>
                <label>
                  Currency
                  <input value={priceInputs[provider].currency} maxLength={3} onChange={(event) => setPriceInputs((values) => ({ ...values, [provider]: { ...values[provider], currency: event.target.value.toUpperCase() } }))} />
                </label>
                <div className="price-row-actions">
                  <button className="icon-button" title={`Save ${provider} model price`} aria-label={`Save ${provider} model price`} disabled={savingPrice !== null || !model || !priceInputs[provider].input || !priceInputs[provider].output} onClick={() => saveModelPrice(provider)}><Save size={16} /></button>
                  <button className="icon-button secondary-button" title={`Deactivate ${provider} model price`} aria-label={`Deactivate ${provider} model price`} disabled={savingPrice !== null || !current} onClick={() => clearModelPrice(provider)}><Trash2 size={16} /></button>
                </div>
              </div>
            );
          })}
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

function DiagnosticRow({ result, stores }: { result: IntegrationDiagnosticResult; stores: StoreRecord[] }) {
  const ready = result.status === "verified" || result.status === "configured";
  const store = result.store_id ? stores.find((item) => Number(item.id) === result.store_id) : null;
  const label = result.provider === "mercado_libre"
    ? store?.display_name ?? "美客多应用"
    : result.provider === "claude" ? "Claude" : "NVIDIA";
  return (
    <div className={`diagnostic-result-row ${ready ? "ready" : "blocked"}`}>
      {ready ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}
      <strong>{label}</strong>
      <span>{diagnosticMessage(result)}</span>
      <small>{result.duration_ms} ms</small>
    </div>
  );
}

function diagnosticMessage(result: IntegrationDiagnosticResult) {
  const messages: Record<string, string> = {
    app_credentials_required: "需要配置应用凭证",
    app_credentials_incomplete: "应用凭证不完整",
    oauth_authorization_required: "需要卖家授权",
    authorized_store_available: "Application configured",
    connected_store_verification_failed: "无法验证已连接店铺",
    api_key_required: "需要 API Key",
    credentials_valid_model_available: `${result.model} available`,
    configured_model_not_available: `${result.model} unavailable`,
    provider_authentication_failed: "认证失败",
    provider_permission_denied: "权限不足",
    provider_payment_required: "需付费",
    provider_request_rejected: "请求被拒绝",
    provider_rate_limited: "速率限制",
    provider_unavailable: "服务不可用",
    models_response_invalid: "服务响应无效",
    store_not_connected: "需要店铺授权",
    store_token_unavailable: "店铺 Token 不可用",
    store_reauthorization_required: "店铺授权已过期",
    token_refresh_response_invalid: "Token 刷新响应无效",
    store_identity_mismatch: "卖家身份不匹配",
    seller_profile_invalid: "卖家资料无效",
    store_identity_verified: "卖家身份已验证",
  };
  return messages[result.code] ?? result.code;
}

type CredentialKey = "meli_client_id" | "meli_client_secret" | "claude_api_key" | "nvidia_api_key" | "volcengine_api_key";

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
