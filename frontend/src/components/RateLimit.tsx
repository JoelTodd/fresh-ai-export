import { Info } from "lucide-react";

import type { RateLimitInfo } from "../types";

export function RateLimit({ value }: { value?: RateLimitInfo | null }) {
  const hasValues =
    value &&
    (value.limit ||
      value.remaining ||
      value.used_current_request ||
      value.reset ||
      value.retry_after ||
      (value.raw && Object.keys(value.raw).length > 0));
  if (!hasValues) return null;
  return (
    <div className="rate-card">
      <div className="rate-header">
        <span>Rate Limit</span>
        <Info size={15} />
      </div>
      <div className="rate-meter">
        <span style={{ width: value.remaining ? "72%" : "18%" }} />
      </div>
      <div className="rate-grid">
        {value.limit && <span>Limit: {value.limit}</span>}
        {value.remaining && <span>Remaining: {value.remaining}</span>}
        {value.used_current_request && <span>Used: {value.used_current_request}</span>}
        {value.reset && <span>Resets: {value.reset}</span>}
        {value.retry_after && <span>Retry after: {value.retry_after}</span>}
      </div>
    </div>
  );
}
