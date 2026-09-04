import { useCallback, useEffect, useState } from "react";
import {
  getDiagnosticsSummary,
  listDiagnosticErrors,
  searchDiagnostics,
  type DiagnosticJobRecord,
  type DiagnosticsSearchResults,
  type DiagnosticsSummary,
} from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  pending: "排队中",
  validating: "发布中",
  published: "已发布",
  failed: "失败",
  blocked: "待核对",
  cancelled: "已取消",
};

function formatTime(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function errorList(errors: string[]) {
  if (!errors || errors.length === 0) return <span className="muted">无错误记录</span>;
  return (
    <ul className="diag-error-list">
      {errors.map((err, index) => (
        <li key={index}>{err}</li>
      ))}
    </ul>
  );
}

export function DiagnosticsPage() {
  const [days, setDays] = useState(7);
  const [summary, setSummary] = useState<DiagnosticsSummary | null>(null);
  const [jobRows, setJobRows] = useState<DiagnosticJobRecord[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<DiagnosticsSearchResults | null>(null);
  const [searching, setSearching] = useState(false);
  const [status, setStatus] = useState("");

  const refreshAll = useCallback(async (targetDays = days, targetFilter = statusFilter) => {
    setStatus("正在读取系统诊断…");
    try {
      const [summaryData, errorsData] = await Promise.all([
        getDiagnosticsSummary(targetDays),
        listDiagnosticErrors({ days: targetDays, status: targetFilter || undefined, limit: 50 }),
      ]);
      setSummary(summaryData);
      setJobRows(errorsData.items);
      setJobTotal(errorsData.total);
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "读取系统诊断失败");
    }
  }, [days, statusFilter]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  function changeDays(nextDays: number) {
    setDays(nextDays);
    void refreshAll(nextDays, statusFilter);
  }

  function changeStatusFilter(nextStatus: string) {
    setStatusFilter(nextStatus);
    void refreshAll(days, nextStatus);
  }

  async function runSearch() {
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    setStatus("正在全局检索…");
    try {
      setSearchResults(await searchDiagnostics(q, 20));
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "全局检索失败");
    } finally {
      setSearching(false);
    }
  }

  const totals = summary?.totals ?? {};
  const topErrors = summary?.top_errors ?? [];
  const staleJobs = summary?.stale_jobs ?? [];

  return (
    <section className="panel">
      <div className="diag-header">
        <h2>系统诊断</h2>
        <div className="button-row">
          {[7, 30, 90].map((n) => (
            <button key={n} className={days === n ? "active" : ""} onClick={() => changeDays(n)}>
              近 {n} 天
            </button>
          ))}
          <button onClick={() => void refreshAll()}>刷新</button>
        </div>
      </div>
      {status && <p>{status}</p>}

      {/* 概览卡片 */}
      <div className="diag-cards">
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <div className="diag-card" key={key}>
            <strong>{label}</strong>
            <span className={key === "failed" && (totals[key] ?? 0) > 0 ? "num-warn" : "num"}>{totals[key] ?? 0}</span>
          </div>
        ))}
      </div>

      {/* Top 错误排行 */}
      <h3>反复出现的问题排行</h3>
      {topErrors.length === 0 && <p className="muted">近 {days} 天没有失败/待核对记录。</p>}
      {topErrors.length > 0 && (
        <ol className="diag-top-errors">
          {topErrors.map((bucket) => (
            <li key={bucket.kind}>
              <span className="diag-err-kind">{bucket.kind}</span>
              <span className="diag-err-count">{bucket.count} 条</span>
              <span className="muted">涉及草稿：{bucket.sample_draft_ids.join("、")}</span>
            </li>
          ))}
        </ol>
      )}

      {/* 全局检索 */}
      <h3>全局检索</h3>
      <div className="diag-search">
        <input
          type="search"
          placeholder="搜索草稿标题 / 草稿ID / 任务ID / 错误关键词 / 店铺 / 审计动作…"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") void runSearch(); }}
        />
        <button onClick={() => void runSearch()} disabled={searching}>
          {searching ? "检索中…" : "检索"}
        </button>
      </div>
      {searchResults && (
        <div className="diag-search-results">
          <h4>草稿（{searchResults.drafts.length}）</h4>
          {searchResults.drafts.length === 0 && <p className="muted">无</p>}
          <ul>
            {searchResults.drafts.map((d) => (
              <li key={`d-${d.id}`}>
                草稿 #{d.id} · {d.title} · 状态 {STATUS_LABELS[d.status] ?? d.status} · {d.target_site_id}
              </li>
            ))}
          </ul>
          <h4>发布任务（{searchResults.publish_jobs.length}）</h4>
          {searchResults.publish_jobs.length === 0 && <p className="muted">无</p>}
          <ul>
            {searchResults.publish_jobs.map((job) => (
              <li key={`j-${job.job_id}`}>
                任务 #{job.job_id} · 草稿 #{job.draft_id} · {STATUS_LABELS[job.status] ?? job.status}
                {job.errors.length > 0 && ` · ${job.errors[0]}`}
              </li>
            ))}
          </ul>
          <h4>审计事件（{searchResults.audit_events.length}）</h4>
          {searchResults.audit_events.length === 0 && <p className="muted">无</p>}
          <ul>
            {searchResults.audit_events.map((ev) => (
              <li key={`a-${ev.id}`}>
                #{ev.id} · {ev.action} · {ev.entity_type} #{ev.entity_id} · {ev.actor_id} · {formatTime(ev.created_at)}
              </li>
            ))}
          </ul>
          <h4>店铺（{searchResults.stores.length}）</h4>
          {searchResults.stores.length === 0 && <p className="muted">无</p>}
          <ul>
            {searchResults.stores.map((store) => (
              <li key={`s-${store.id}`}>
                {store.display_name} · 卖家 {store.seller_id} · {store.site_id} · {store.oauth_status}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 卡住任务 */}
      <h3>卡住的任务（排队 / 发布中超过预期）</h3>
      {staleJobs.length === 0 && <p className="muted">没有卡住的任务。</p>}
      {staleJobs.length > 0 && (
        <table className="diag-table">
          <thead>
            <tr><th>任务</th><th>草稿</th><th>状态</th><th>创建时间</th><th>已等待</th></tr>
          </thead>
          <tbody>
            {staleJobs.map((job) => (
              <tr key={job.job_id}>
                <td>#{job.job_id}</td>
                <td>#{job.draft_id}</td>
                <td>{STATUS_LABELS[job.status] ?? job.status}</td>
                <td>{formatTime(job.created_at)}</td>
                <td>{job.age_seconds != null ? `${Math.round(job.age_seconds / 60)} 分钟` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 失败/待核对任务明细 */}
      <h3>失败与待核对任务（{jobTotal}）</h3>
      <div className="button-row">
        {["", "failed", "blocked", "non-published"].map((value) => (
          <button key={value || "all"} className={statusFilter === value ? "active" : ""} onClick={() => changeStatusFilter(value)}>
            {value === "" ? "失败+待核对" : value === "failed" ? "失败" : value === "blocked" ? "待核对" : "全部非成功"}
          </button>
        ))}
      </div>
      {jobRows.length === 0 && <p className="muted">没有符合条件的记录。</p>}
      {jobRows.length > 0 && (
        <table className="diag-table">
          <thead>
            <tr><th>任务</th><th>草稿</th><th>状态</th><th>错误信息</th><th>时间</th></tr>
          </thead>
          <tbody>
            {jobRows.map((job) => (
              <tr key={job.job_id}>
                <td>#{job.job_id}{job.item_id ? <div className="muted small">{job.item_id}</div> : null}</td>
                <td>#{job.draft_id}<div className="muted small">{job.draft_title || ""}</div></td>
                <td>{STATUS_LABELS[job.status] ?? job.status}</td>
                <td>{errorList(job.errors)}</td>
                <td>{formatTime(job.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
