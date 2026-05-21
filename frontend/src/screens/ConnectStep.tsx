import { CheckCircle2, Link } from "lucide-react";

import { RateLimit } from "../components/RateLimit";
import type { RateLimitInfo } from "../types";

type ConnectStepProps = {
  domain: string;
  apiKey: string;
  connectedDomain: string | null;
  rateLimit: RateLimitInfo | null;
  busy: boolean;
  setDomain: (value: string) => void;
  setApiKey: (value: string) => void;
  connect: () => void;
};

export function ConnectStep({
  domain,
  apiKey,
  connectedDomain,
  rateLimit,
  busy,
  setDomain,
  setApiKey,
  connect
}: ConnectStepProps) {
  return (
    <section className="panel connect-panel">
      <div className="panel-title">
        <div>
          <h1>1. Connect Account</h1>
          <p>Enter your domain and API key to load available ticket fields.</p>
        </div>
      </div>
      <div className="form-stack">
        <label>
          Domain
          <input value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="yourcompany.freshdesk.com" />
          <span>Use the full support portal domain.</span>
        </label>
        <label>
          API Key
          <input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="API key"
          />
          <span>Used for this session to fetch fields and tickets.</span>
        </label>
        <button className="primary" onClick={connect} disabled={busy || !domain || !apiKey}>
          <Link size={17} /> Test Connection
        </button>
      </div>
      {connectedDomain && (
        <div className="success-card">
          <CheckCircle2 size={24} />
          <div>
            <strong>Connected</strong>
            <p>{connectedDomain}</p>
          </div>
          <span>Just now</span>
        </div>
      )}
      <RateLimit value={rateLimit} />
    </section>
  );
}
