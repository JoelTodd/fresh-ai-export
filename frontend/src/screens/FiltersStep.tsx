import { AlertCircle, CheckCircle2, Clipboard, RefreshCw, Search, Trash2 } from "lucide-react";

import { FieldGroup } from "../components/FieldGroup";
import { operatorLabel } from "../lib/filters";
import type { FilterCondition, FilterField, GeneratedQuery } from "../types";

type FiltersStepProps = {
  fields: FilterField[];
  filters: FilterCondition[];
  fieldSearch: string;
  rawQuery: string;
  generated: GeneratedQuery | null;
  busy: boolean;
  connectedDomain: string | null;
  setFieldSearch: (value: string) => void;
  setRawQuery: (value: string) => void;
  setFilters: React.Dispatch<React.SetStateAction<FilterCondition[]>>;
  addFilter: (field?: FilterField) => void;
  updateFilter: (id: string, patch: Partial<FilterCondition>) => void;
  loadFields: (refresh?: boolean) => Promise<void>;
  generateQuery: () => Promise<void>;
  runPreview: () => Promise<void>;
  copyQuery: () => Promise<void>;
};

export function FiltersStep({
  fields,
  filters,
  fieldSearch,
  rawQuery,
  generated,
  busy,
  connectedDomain,
  setFieldSearch,
  setRawQuery,
  setFilters,
  addFilter,
  updateFilter,
  loadFields,
  generateQuery,
  runPreview,
  copyQuery
}: FiltersStepProps) {
  const standardFields = fields.filter((field) => field.source !== "custom");
  const customFields = fields.filter((field) => field.source === "custom");
  const search = fieldSearch.toLowerCase();
  const filteredStandard = standardFields.filter((field) => `${field.label} ${field.search_key}`.toLowerCase().includes(search));
  const filteredCustom = customFields.filter((field) => `${field.label} ${field.search_key}`.toLowerCase().includes(search));
  const wrappedLength = generated?.wrapped_query.length ?? 0;
  const isQueryTooLong = wrappedLength > 512;

  return (
    <section className="panel filters-panel">
      <div className="panel-title compact">
        <div>
          <h1>2. Select Tickets</h1>
          <p>Choose fields to narrow the export, or paste an existing search query.</p>
        </div>
        <div className={isQueryTooLong ? "query-count bad" : "query-count"}>
          Search length <strong>{wrappedLength || 0} / 512</strong>
        </div>
      </div>
      <div className="filter-layout">
        <aside className="field-browser">
          <label className="search-box">
            <Search size={15} />
            <input value={fieldSearch} onChange={(event) => setFieldSearch(event.target.value)} placeholder="Search fields..." />
          </label>
          <FieldGroup title="Standard" fields={filteredStandard} addFilter={addFilter} />
          <FieldGroup title="Custom" fields={filteredCustom} addFilter={addFilter} />
        </aside>

        <div className="builder">
          <div className="condition-list">
            {filters.map((filter) => {
              const selected = fields.find((field) => field.search_key === filter.field);
              return (
                <div className="condition-row" key={filter.id}>
                  <select value={filter.field} onChange={(event) => updateFilter(filter.id, { field: event.target.value })}>
                    {fields.map((field) => (
                      <option key={field.search_key} value={field.search_key}>
                        {field.label}
                      </option>
                    ))}
                  </select>
                  <select value={filter.operator} onChange={(event) => updateFilter(filter.id, { operator: event.target.value })}>
                    {(selected?.operators ?? ["eq"]).map((operator) => (
                      <option key={operator} value={operator}>
                        {operatorLabel(operator)}
                      </option>
                    ))}
                  </select>
                  {selected?.choices.length ? (
                    <select value={filter.value} onChange={(event) => updateFilter(filter.id, { value: event.target.value })}>
                      <option value="">Choose value</option>
                      {selected.choices.map((choice) => (
                        <option key={`${choice.label}-${choice.value}`} value={String(choice.value)}>
                          {choice.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={selected?.type === "date" ? "date" : "text"}
                      value={filter.value}
                      onChange={(event) => updateFilter(filter.id, { value: event.target.value })}
                      placeholder="Value"
                    />
                  )}
                  {filter.operator === "between" && (
                    <input
                      type="date"
                      value={filter.value_to ?? ""}
                      onChange={(event) => updateFilter(filter.id, { value_to: event.target.value })}
                    />
                  )}
                  <button
                    className="icon-button danger"
                    aria-label="Remove condition"
                    title="Remove condition"
                    onClick={() => setFilters((current) => current.filter((item) => item.id !== filter.id))}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              );
            })}
          </div>
          <div className="button-row">
            <button className="soft" onClick={() => addFilter()} disabled={!fields.length}>
              + Add Rule
            </button>
            <button className="ghost" onClick={() => setFilters([])}>
              Clear All
            </button>
            <button className="ghost" onClick={() => loadFields(true)} disabled={busy || !connectedDomain}>
              <RefreshCw size={16} /> Refresh
            </button>
          </div>

          <label className="advanced-query">
            Search Query
            <textarea value={rawQuery} onChange={(event) => setRawQuery(event.target.value)} placeholder="status:2 AND priority:3" />
            <span>Paste a supported search expression if the field picker is too limiting.</span>
          </label>

          <div className="generated-card">
            <strong>Current Search</strong>
            <pre>{generated?.wrapped_query ?? '"status:2"'}</pre>
            <button className="icon-button copy" onClick={copyQuery} disabled={!generated}>
              <Clipboard size={17} />
            </button>
          </div>
          <div className={isQueryTooLong ? "length-row bad" : "length-row"}>
            {isQueryTooLong ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
            {wrappedLength || 0} / 512 characters
          </div>
          <div className="button-row end">
            <button className="soft" onClick={generateQuery} disabled={busy}>
              Update Search
            </button>
            <button className="primary" onClick={runPreview} disabled={busy || !connectedDomain}>
              <Search size={17} /> Review Matches
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
