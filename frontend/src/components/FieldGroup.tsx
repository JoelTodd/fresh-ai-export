import type { FilterField } from "../types";

type FieldGroupProps = {
  title: string;
  fields: FilterField[];
  addFilter: (field: FilterField) => void;
};

export function FieldGroup({ title, fields, addFilter }: FieldGroupProps) {
  return (
    <div className="field-group">
      <strong>{title}</strong>
      {fields.length === 0 ? (
        <span className="field-empty">No fields</span>
      ) : (
        fields.map((field) => (
          <button key={field.search_key} className={`field-pill ${field.source}`} onClick={() => addFilter(field)}>
            <span />
            {field.label}
          </button>
        ))
      )}
    </div>
  );
}
