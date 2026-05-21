import { Info, Search } from "lucide-react";

import { displayValue } from "../lib/filters";
import type { PreviewResponse, Step } from "../types";

type PreviewStepProps = {
  preview: PreviewResponse | null;
  busy: boolean;
  connectedDomain: string | null;
  setActiveStep: (step: Step) => void;
  runPreview: () => Promise<void>;
};

export function PreviewStep({ preview, busy, connectedDomain, setActiveStep, runPreview }: PreviewStepProps) {
  return (
    <section className="panel preview-panel">
      <div className="panel-title compact">
        <div>
          <h1>3. Review Matches</h1>
          <p>Check the first page before exporting the full ticket records.</p>
        </div>
        <div className="total-match">
          Matches <strong>{preview?.total ?? "-"}</strong>
        </div>
      </div>
      {preview?.warnings.map((warning) => (
        <div className="notice" key={warning}>
          <Info size={18} />
          <span>{warning}</span>
          <button onClick={() => setActiveStep("export")}>Set Date Range</button>
        </div>
      ))}
      {preview ? (
        <>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Subject</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Requester</th>
                  <th>Group</th>
                  <th>Created At</th>
                  <th>Updated At</th>
                  <th>Tags</th>
                </tr>
              </thead>
              <tbody>
                {preview.tickets.map((ticket) => (
                  <tr key={displayValue(ticket.id)}>
                    <td>#{displayValue(ticket.id)}</td>
                    <td>{displayValue(ticket.subject)}</td>
                    <td>
                      <span className="badge green">{displayValue(ticket.status)}</span>
                    </td>
                    <td>
                      <span className="badge rose">{displayValue(ticket.priority)}</span>
                    </td>
                    <td>{displayValue(ticket.requester_id)}</td>
                    <td>{displayValue(ticket.group_id)}</td>
                    <td>{displayValue(ticket.created_at)}</td>
                    <td>{displayValue(ticket.updated_at)}</td>
                    <td>{displayValue(ticket.tags)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="preview-footer">
            <span>Showing page 1. Use a date range when the match count is high.</span>
            <button className="primary" onClick={() => setActiveStep("export")}>
              Continue
            </button>
          </div>
        </>
      ) : (
        <div className="empty-state">
          <Search size={32} />
          <p>No matches loaded yet.</p>
          <button className="primary" onClick={runPreview} disabled={busy || !connectedDomain}>
            Review Matches
          </button>
        </div>
      )}
    </section>
  );
}
