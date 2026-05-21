import { Download, FileSpreadsheet, FileText, Info } from "lucide-react";

import type { ExportFormat, ExportResponse } from "../types";

type ExportStepProps = {
  exportFormat: ExportFormat;
  splitField: "created_at" | "updated_at";
  dateStart: string;
  dateEnd: string;
  busy: boolean;
  connectedDomain: string | null;
  exportResult: ExportResponse | null;
  setExportFormat: (format: ExportFormat) => void;
  setSplitField: (field: "created_at" | "updated_at") => void;
  setDateStart: (value: string) => void;
  setDateEnd: (value: string) => void;
  runExport: () => Promise<void>;
};

export function ExportStep({
  exportFormat,
  splitField,
  dateStart,
  dateEnd,
  busy,
  connectedDomain,
  exportResult,
  setExportFormat,
  setSplitField,
  setDateStart,
  setDateEnd,
  runExport
}: ExportStepProps) {
  return (
    <section className="panel export-panel">
      <div className="panel-title compact">
        <div>
          <h1>4. Export</h1>
          <p>Choose an output format and optional date range.</p>
        </div>
      </div>

      <h2>Format</h2>
      <div className="format-grid">
        <button className={exportFormat === "xlsx" ? "format-card selected" : "format-card"} onClick={() => setExportFormat("xlsx")}>
          <FileSpreadsheet size={42} />
          <span>
            <strong>XLSX</strong>
            <small>Workbook for Copilot and Excel.</small>
          </span>
        </button>
        <button className={exportFormat === "md" ? "format-card selected" : "format-card"} onClick={() => setExportFormat("md")}>
          <FileText size={42} />
          <span>
            <strong>Markdown</strong>
            <small>Compact ticket and conversation context for AI.</small>
          </span>
        </button>
      </div>

      <h2>Range</h2>
      <div className="grid two">
        <label>
          Date field
          <select value={splitField} onChange={(event) => setSplitField(event.target.value as "created_at" | "updated_at")}>
            <option value="created_at">Created At</option>
            <option value="updated_at">Updated At</option>
          </select>
        </label>
        <label>
          Export destination
          <input value="./exports" readOnly />
        </label>
        <label>
          Start date
          <input type="date" value={dateStart} onChange={(event) => setDateStart(event.target.value)} />
        </label>
        <label>
          End date
          <input type="date" value={dateEnd} onChange={(event) => setDateEnd(event.target.value)} />
        </label>
      </div>
      <div className="info-strip">
        <Info size={18} />
        Large searches are exported in date slices to avoid platform result limits.
      </div>
      <button className="primary wide" onClick={runExport} disabled={busy || !connectedDomain}>
        <Download size={18} /> Export
      </button>

      {exportResult && (
        <div className="manifest-card">
          <strong>Export Finished</strong>
          <p>{exportResult.count} records written.</p>
          {exportResult.xlsx_path && <p>XLSX: {exportResult.xlsx_path}</p>}
          {exportResult.md_path && <p>Markdown: {exportResult.md_path}</p>}
          <p>Manifest: {exportResult.manifest_path}</p>
          {exportResult.warnings.map((warning) => (
            <p className="warning-text" key={warning}>
              {warning}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
