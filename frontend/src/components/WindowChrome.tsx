import { Cloud, Maximize2, Minus, X } from "lucide-react";

export function WindowChrome() {
  const minimizeWindow = () => window.desktopWindow?.minimize();
  const toggleMaximizeWindow = () => window.desktopWindow?.toggleMaximize();
  const closeWindow = () => {
    if (window.desktopWindow) {
      window.desktopWindow.close();
      return;
    }
    window.close();
  };

  return (
    <header className="window-chrome">
      <div className="chrome-brand">
        <Cloud size={18} />
      </div>
      <div className="chrome-title">
        <span>Ticket Exporter</span>
      </div>
      <div className="window-actions">
        <button aria-label="Minimize window" title="Minimize" onClick={minimizeWindow}>
          <Minus size={16} />
        </button>
        <button aria-label="Maximize window" title="Maximize" onClick={toggleMaximizeWindow}>
          <Maximize2 size={14} />
        </button>
        <button aria-label="Close window" title="Close" className="close" onClick={closeWindow}>
          <X size={16} />
        </button>
      </div>
    </header>
  );
}
