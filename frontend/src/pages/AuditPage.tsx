import { useEffect, useState } from "react";
import { listAuditEvents, type AuditEventRecord } from "../api/client";

export function AuditPage() {
  const [events, setEvents] = useState<AuditEventRecord[]>([]);
  const [status, setStatus] = useState("");

  async function refreshEvents() {
    setStatus("Loading audit events");
    try {
      setEvents(await listAuditEvents());
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load audit events");
    }
  }

  useEffect(() => {
    void refreshEvents();
  }, []);

  return (
    <section className="panel">
      <h2>Audit Events</h2>
      <div className="button-row">
        <button onClick={refreshEvents}>Refresh Audit Events</button>
      </div>
      {status && <p>{status}</p>}
      {events.length === 0 && <p>No audit events yet.</p>}
      {events.length > 0 && <pre>{JSON.stringify(events, null, 2)}</pre>}
    </section>
  );
}
