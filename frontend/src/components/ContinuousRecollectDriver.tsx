import { useEffect } from "react";

import {
  claimNextListingRecollectJob,
  failListingRecollectJob,
  type ListingRecollectJob,
} from "../api/client";

const IDLE_POLL_MS = 5_000;
const BETWEEN_PRODUCTS_MS = 20_000;
const COLLECTION_TIMEOUT_MS = 75_000;
let driverMounted = false;

function wait(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

function collectWithListingButtonProtocol(job: ListingRecollectJob) {
  return new Promise<{ ok: boolean; error?: string }>((resolve) => {
    let settled = false;
    const finish = (result: { ok: boolean; error?: string }) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      window.removeEventListener("meli-amazon-recollect-result", handler);
      resolve(result);
    };
    const timer = window.setTimeout(
      () => finish({ ok: false, error: "上架库补采插件 75 秒内未返回结果。" }),
      COLLECTION_TIMEOUT_MS,
    );
    function handler(event: Event) {
      const detail = (event as CustomEvent<{ sourceProductId?: number; ok?: boolean; error?: string }>).detail;
      if (detail?.sourceProductId !== job.sourceProductId) return;
      finish({ ok: detail.ok === true, error: detail.error });
    }
    window.addEventListener("meli-amazon-recollect-result", handler);
    window.dispatchEvent(new CustomEvent("meli-amazon-recollect", {
      detail: { sourceProductId: job.sourceProductId, sourceUrl: job.sourceUrl },
    }));
  });
}

export function ContinuousRecollectDriver() {
  useEffect(() => {
    if (driverMounted) return;
    driverMounted = true;
    let cancelled = false;
    const workerId = `listing-recollect-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const run = async () => {
      while (!cancelled) {
        let hadJob = false;
        try {
          const response = await claimNextListingRecollectJob(workerId);
          const job = response.job;
          if (job) {
            hadJob = true;
            const result = await collectWithListingButtonProtocol(job);
            if (!result.ok) {
              await failListingRecollectJob(job.id, result.error || "上架库绿色“采”流程返回失败。");
            }
          }
        } catch {
          // The campaign/audit pages expose the persisted failure. Keep the
          // global driver quiet and retry only after the normal cooldown.
        }
        if (!cancelled) await wait(hadJob ? BETWEEN_PRODUCTS_MS : IDLE_POLL_MS);
      }
    };
    void run();
    return () => {
      cancelled = true;
      driverMounted = false;
    };
  }, []);

  return null;
}
