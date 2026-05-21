import React from "react";

import { api } from "./api/client";
import { Sidebar } from "./components/Sidebar";
import { WindowChrome } from "./components/WindowChrome";
import { firstField, makeFilter, prepareFilters } from "./lib/filters";
import { ConnectStep } from "./screens/ConnectStep";
import { ExportStep } from "./screens/ExportStep";
import { FiltersStep } from "./screens/FiltersStep";
import { PreviewStep } from "./screens/PreviewStep";
import type {
  ExportFormat,
  ExportResponse,
  FilterCondition,
  FilterField,
  GeneratedQuery,
  PreviewResponse,
  RateLimitInfo,
  Step
} from "./types";

export function App() {
  const [activeStep, setActiveStep] = React.useState<Step>("connect");
  const [domain, setDomain] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");
  const [connectedDomain, setConnectedDomain] = React.useState<string | null>(null);
  const [fields, setFields] = React.useState<FilterField[]>([]);
  const [connectionRateLimit, setConnectionRateLimit] = React.useState<RateLimitInfo | null>(null);
  const [fieldSearch, setFieldSearch] = React.useState("");
  const [filters, setFilters] = React.useState<FilterCondition[]>([]);
  const [rawQuery, setRawQuery] = React.useState("");
  const [generated, setGenerated] = React.useState<GeneratedQuery | null>(null);
  const [preview, setPreview] = React.useState<PreviewResponse | null>(null);
  const [exportResult, setExportResult] = React.useState<ExportResponse | null>(null);
  const [exportFormat, setExportFormat] = React.useState<ExportFormat>("xlsx");
  const [splitField, setSplitField] = React.useState<"created_at" | "updated_at">("created_at");
  const [dateStart, setDateStart] = React.useState("");
  const [dateEnd, setDateEnd] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!message) return;
    const timeout = window.setTimeout(() => setMessage(""), 3200);
    return () => window.clearTimeout(timeout);
  }, [message]);

  function showMessage(text: string) {
    setMessage(text);
  }

  function reconcileFilters(nextFields: FilterField[]) {
    setFields(nextFields);
    setFilters((current) => {
      // Field metadata can change between refreshes. Keep valid filters, update
      // their type/operator metadata, and seed a sensible default for new users.
      const allowed = new Map(nextFields.map((field) => [field.search_key, field]));
      const kept = current
        .filter((filter) => allowed.has(filter.field))
        .map((filter) => {
          const field = allowed.get(filter.field)!;
          return {
            ...filter,
            type: field.type,
            operator: field.operators.includes(filter.operator) ? filter.operator : (field.operators[0] ?? "eq")
          };
        });
      if (kept.length > 0) return kept;
      const preferred = firstField(nextFields);
      return preferred ? [makeFilter(preferred)] : [];
    });
  }

  async function loadFields(refresh = false) {
    const response = await api<{ fields: FilterField[] }>(refresh ? "/api/fields?refresh=true" : "/api/fields");
    reconcileFilters(response.fields);
  }

  async function connect() {
    setBusy(true);
    setMessage("");
    try {
      const response = await api<{ ok: boolean; domain: string; message: string; rate_limit?: RateLimitInfo }>("/api/connect", {
        method: "POST",
        body: JSON.stringify({ domain, api_key: apiKey })
      });
      setConnectedDomain(response.domain);
      setConnectionRateLimit(response.rate_limit ?? null);
      setApiKey("");
      showMessage(response.message);
      await loadFields();
      setActiveStep("filters");
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Connection failed");
    } finally {
      setBusy(false);
    }
  }

  async function generateQuery() {
    setBusy(true);
    setMessage("");
    try {
      const response = await api<GeneratedQuery>("/api/query", {
        method: "POST",
        body: JSON.stringify({ filters: prepareFilters(filters, fields), raw_query: rawQuery || null })
      });
      setGenerated(response);
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Could not generate query");
    } finally {
      setBusy(false);
    }
  }

  async function runPreview() {
    setBusy(true);
    setMessage("");
    setPreview(null);
    try {
      const response = await api<PreviewResponse>("/api/preview", {
        method: "POST",
        body: JSON.stringify({ filters: prepareFilters(filters, fields), raw_query: rawQuery || null, page: 1 })
      });
      setPreview(response);
      setGenerated({ query: response.query, wrapped_query: response.wrapped_query });
      setActiveStep("preview");
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function runExport() {
    setBusy(true);
    setMessage("");
    setExportResult(null);
    try {
      const response = await api<ExportResponse>("/api/export", {
        method: "POST",
        body: JSON.stringify({
          filters: prepareFilters(filters, fields),
          raw_query: rawQuery || null,
          export_format: exportFormat,
          split_field: splitField,
          date_start: dateStart || null,
          date_end: dateEnd || null
        })
      });
      setExportResult(response);
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  function addFilter(field?: FilterField) {
    const next = field ?? firstField(fields);
    if (!next) return;
    setFilters((current) => [...current, makeFilter(next)]);
  }

  function updateFilter(id: string, patch: Partial<FilterCondition>) {
    setFilters((current) =>
      current.map((item) => {
        if (item.id !== id) return item;
        const next = { ...item, ...patch };
        if (patch.field) {
          const selected = fields.find((field) => field.search_key === patch.field);
          next.operator = selected?.operators[0] ?? "eq";
          next.type = selected?.type;
          next.value = "";
          next.value_to = "";
        }
        return next;
      })
    );
  }

  async function copyQuery() {
    if (!generated?.wrapped_query) return;
    await navigator.clipboard.writeText(generated.wrapped_query);
    showMessage("Query copied.");
  }

  return (
    <div className="desktop-shell">
      <WindowChrome />
      <div className="app-shell">
        <Sidebar active={activeStep} setActive={setActiveStep} connectedDomain={connectedDomain} showMessage={showMessage} />

        <main className="workspace">
          {activeStep === "connect" && (
            <ConnectStep
              domain={domain}
              apiKey={apiKey}
              connectedDomain={connectedDomain}
              rateLimit={connectionRateLimit}
              busy={busy}
              setDomain={setDomain}
              setApiKey={setApiKey}
              connect={connect}
            />
          )}

          {activeStep === "filters" && (
            <FiltersStep
              fields={fields}
              filters={filters}
              fieldSearch={fieldSearch}
              rawQuery={rawQuery}
              generated={generated}
              busy={busy}
              connectedDomain={connectedDomain}
              setFieldSearch={setFieldSearch}
              setRawQuery={setRawQuery}
              setFilters={setFilters}
              addFilter={addFilter}
              updateFilter={updateFilter}
              loadFields={loadFields}
              generateQuery={generateQuery}
              runPreview={runPreview}
              copyQuery={copyQuery}
            />
          )}

          {activeStep === "preview" && (
            <PreviewStep
              preview={preview}
              busy={busy}
              connectedDomain={connectedDomain}
              setActiveStep={setActiveStep}
              runPreview={runPreview}
            />
          )}

          {activeStep === "export" && (
            <ExportStep
              exportFormat={exportFormat}
              splitField={splitField}
              dateStart={dateStart}
              dateEnd={dateEnd}
              busy={busy}
              connectedDomain={connectedDomain}
              exportResult={exportResult}
              setExportFormat={setExportFormat}
              setSplitField={setSplitField}
              setDateStart={setDateStart}
              setDateEnd={setDateEnd}
              runExport={runExport}
            />
          )}
        </main>
      </div>

      {message && <div className="toast">{message}</div>}
    </div>
  );
}
