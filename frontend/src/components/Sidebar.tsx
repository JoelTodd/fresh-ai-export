import { Cloud, Info, Settings } from "lucide-react";

import { API_BASE, steps } from "../config";
import type { Step } from "../types";

type SidebarProps = {
  active: Step;
  setActive: (step: Step) => void;
  connectedDomain: string | null;
  showMessage: (message: string) => void;
};

export function Sidebar({ active, setActive, connectedDomain, showMessage }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Cloud size={28} />
        <strong>Ticket Exporter</strong>
      </div>
      <nav className="nav">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <button
              className={active === step.id ? "nav-item active" : "nav-item"}
              key={step.id}
              onClick={() => setActive(step.id)}
            >
              <Icon size={18} />
              {step.label}
            </button>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <button className="nav-item quiet" onClick={() => showMessage(`API: ${API_BASE}`)}>
          <Settings size={17} />
          Settings
        </button>
        <button
          className="nav-item quiet"
          onClick={() =>
            showMessage(
              connectedDomain
                ? `Connected to ${connectedDomain}.`
                : "Connect an account, choose filters, and export tickets."
            )
          }
        >
          <Info size={17} />
          About
        </button>
      </div>
    </aside>
  );
}
