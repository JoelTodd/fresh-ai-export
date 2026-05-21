import { Download, Filter, Link, List } from "lucide-react";

import type { StepDefinition } from "./types";

// Browser development can point directly at FastAPI. The WebView2 app leaves
// this blank and relies on its loopback UI server to proxy /api requests.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export const steps: StepDefinition[] = [
  { id: "connect", label: "Connect", icon: Link },
  { id: "filters", label: "Select", icon: Filter },
  { id: "preview", label: "Review", icon: List },
  { id: "export", label: "Export", icon: Download }
];
