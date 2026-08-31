import { useEffect, useState } from "react";
import { listAuditEvents, type AuditEventRecord } from "../api/client";

export function AuditPage() {
  const [events, setEvents] = useState<AuditEventRecord[]>([]);
  const [status, setStatus] = useState("");

  async function refreshEvents() {
    setStatus("正在读取操作日志");
    try {
      setEvents(await listAuditEvents());
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "读取操作日志失败");
    }
  }

  useEffect(() => {
    void refreshEvents();
  }, []);

  return (
    <section className="panel">
      <h2>操作日志</h2>
      <div className="button-row">
        <button onClick={refreshEvents}>刷新日志</button>
      </div>
      {status && <p>{status}</p>}
      {events.length === 0 && <p>暂无操作记录。</p>}
      {events.length > 0 && <div className="audit-event-list">{events.map((event) => (
        <article className="audit-event" key={event.id}>
          <strong>{event.action === "draft.deleted" ? "删除草稿" : event.action}</strong>
          <span>对象：{event.entity_type} #{event.entity_id} · 操作人：{event.actor_id}</span>
          <time>{new Date(event.created_at).toLocaleString("zh-CN")}</time>
          <details><summary>查看变更</summary><pre>{JSON.stringify({ before: event.before, after: event.after }, null, 2)}</pre></details>
        </article>
      ))}</div>}
    </section>
  );
}
