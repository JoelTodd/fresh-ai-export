import type React from "react";

export type Step = "connect" | "filters" | "preview" | "export";
export type ExportFormat = "xlsx" | "md";

declare global {
  interface Window {
    desktopWindow?: {
      minimize: () => Promise<void>;
      toggleMaximize: () => Promise<boolean>;
      close: () => Promise<void>;
    };
  }
}

export type RateLimitInfo = {
  limit?: string | null;
  remaining?: string | null;
  used_current_request?: string | null;
  reset?: string | null;
  retry_after?: string | null;
  raw?: Record<string, string>;
};

export type FieldChoice = {
  label: string;
  value: string | number | boolean;
};

export type FilterField = {
  name: string;
  search_key: string;
  label: string;
  type: string;
  source: "standard" | "freshdesk" | "custom";
  choices: FieldChoice[];
  operators: string[];
};

export type FilterCondition = {
  id: string;
  field: string;
  operator: string;
  value: string;
  value_to?: string;
  type?: string;
};

export type GeneratedQuery = {
  query: string;
  wrapped_query: string;
};

export type PreviewResponse = GeneratedQuery & {
  encoded_query: string;
  total: number;
  page: number;
  tickets: Array<Record<string, unknown>>;
  rate_limit?: RateLimitInfo | null;
  warnings: string[];
};

export type ExportResponse = {
  query: string;
  count: number;
  xlsx_path?: string | null;
  md_path?: string | null;
  manifest_path: string;
  warnings: string[];
  incomplete_windows: Array<Record<string, unknown>>;
};

export type StepDefinition = {
  id: Step;
  label: string;
  icon: React.ElementType;
};
