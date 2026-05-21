import type { FilterCondition, FilterField } from "../types";

export function uid() {
  return crypto.randomUUID();
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function operatorLabel(operator: string): string {
  const labels: Record<string, string> = {
    eq: "is",
    neq: "is not",
    between: "between",
    gt: "after",
    gte: "on or after",
    lt: "before",
    lte: "on or before"
  };
  return labels[operator] ?? operator;
}

export function prepareFilters(filters: FilterCondition[], fields: FilterField[]) {
  const fieldsByKey = new Map(fields.map((field) => [field.search_key, field]));
  // Empty rows are allowed while the user is composing the search, but the API
  // should receive only complete filter conditions.
  return filters
    .filter((item) => item.field && item.operator && item.value)
    .map((item) => {
      const selected = fieldsByKey.get(item.field);
      return {
        field: item.field,
        operator: item.operator,
        value: item.value,
        value_to: item.value_to,
        type: item.type,
        choices:
          item.operator === "neq" && selected?.choices.length
            ? selected.choices.map((choice) => choice.value)
            : []
      };
    });
}

export function firstField(fields: FilterField[], preferred = "status") {
  return fields.find((field) => field.search_key === preferred) ?? fields[0];
}

export function makeFilter(field: FilterField): FilterCondition {
  return {
    id: uid(),
    field: field.search_key,
    operator: field.operators[0] ?? "eq",
    value: "",
    type: field.type
  };
}
