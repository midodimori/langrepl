"use client";

import { useEffect } from "react";

const DARK_STYLES = `
  /* Window */
  .inspector-window {
    background: #18181b !important;
    color: #d4d4d8 !important;
    border-color: #3f3f46 !important;
    font-family: ui-monospace, monospace !important;
  }
  .rounded-xl { border-color: #3f3f46 !important; }
  .shadow-lg { box-shadow: 0 4px 32px rgba(0,0,0,0.8) !important; }

  /* Hide logo */
  img[alt="Inspector logo"] { display: none !important; }

  /* Backgrounds */
  .bg-white { background: #18181b !important; }
  .bg-white\\/95 { background: rgba(24, 24, 27, 0.95) !important; }
  .bg-gray-50 { background: #1c1c1f !important; }
  .bg-gray-100 { background: #27272a !important; }
  .bg-gray-200 { background: #3f3f46 !important; }
  .bg-blue-50 { background: #0c2d48 !important; }
  .bg-blue-100 { background: #0c2d48 !important; }
  .bg-green-50 { background: #052e16 !important; }
  .bg-green-100 { background: #052e16 !important; }
  .bg-yellow-50 { background: #422006 !important; }
  .bg-yellow-100 { background: #422006 !important; }
  .bg-purple-50 { background: #2e1065 !important; }
  .bg-purple-100 { background: #2e1065 !important; }
  .bg-red-50 { background: #450a0a !important; }

  /* Text */
  .text-gray-900 { color: #e4e4e7 !important; }
  .text-gray-800 { color: #d4d4d8 !important; }
  .text-gray-700 { color: #a1a1aa !important; }
  .text-gray-600 { color: #a1a1aa !important; }
  .text-gray-500 { color: #71717a !important; }
  .text-gray-400 { color: #71717a !important; }
  .text-green-700 { color: #4ade80 !important; }

  /* Borders */
  .border-gray-200 { border-color: #3f3f46 !important; }
  .border-gray-300 { border-color: #3f3f46 !important; }
  .border-gray-100 { border-color: #27272a !important; }
  .border-b { border-bottom-color: #3f3f46 !important; }
  .border-green-200 { border-color: #166534 !important; }

  /* Agent tab — role badges */
  .bg-blue-100.text-blue-800 { background: #1e3a5f !important; color: #7dd3fc !important; border-color: #1e3a5f !important; }
  .bg-green-100.text-green-800 { background: #14532d !important; color: #86efac !important; border-color: #14532d !important; }

  /* Agent tab — cards */
  .rounded-lg.border {
    background: #18181b !important;
    border-color: #3f3f46 !important;
  }

  /* Agent tab — stat boxes (Total Events, Messages, etc) */
  .rounded-md.bg-gray-50 {
    background: #27272a !important;
    border: 1px solid #3f3f46 !important;
  }
  .rounded-md.bg-gray-50:hover,
  .hover\\:bg-gray-100:hover {
    background: #3f3f46 !important;
  }

  /* Agent tab — code/state JSON blocks */
  .overflow-auto.rounded-md.bg-gray-50 {
    background: #0a0a0a !important;
    border: 1px solid #27272a !important;
    color: #a1a1aa !important;
  }

  /* Agent tab — stat numbers */
  .text-2xl, .text-xl { color: #e4e4e7 !important; }

  /* Agent tab — stat labels */
  .truncate.whitespace-nowrap.text-xs { color: #71717a !important; }

  /* Agent tab — icon */
  .bg-blue-600 { background: #1e3a5f !important; }
  .bg-blue-500 { background: #1e3a5f !important; }

  /* Agent tab — idle/status badge */
  .rounded-full.bg-gray-100 {
    background: #27272a !important;
    border: 1px solid #3f3f46 !important;
  }

  /* Agent tab — idle dot */
  .bg-gray-400 { background: #52525b !important; }

  /* General — muted text */
  .text-gray-400 { color: #52525b !important; }

  /* AG-UI Events tab — table alternating rows */
  .bg-gray-50\\/50 { background: rgba(39, 39, 42, 0.3) !important; }
  .hover\\:bg-blue-50\\/50:hover { background: rgba(34, 211, 238, 0.08) !important; }

  /* AG-UI Events tab — event type badges */
  .bg-blue-50.text-blue-700.border-blue-200 { background: #1e3a5f !important; color: #7dd3fc !important; border-color: #2563eb33 !important; }
  .bg-sky-50.text-sky-700.border-sky-200 { background: #0c4a6e !important; color: #7dd3fc !important; border-color: #0ea5e933 !important; }
  .bg-violet-50.text-violet-700.border-violet-200 { background: #2e1065 !important; color: #c4b5fd !important; border-color: #7c3aed33 !important; }
  .bg-gray-100.text-gray-600.border-gray-200 { background: #27272a !important; color: #71717a !important; border-color: #3f3f46 !important; }
  .bg-yellow-100.text-yellow-800 { background: #422006 !important; color: #fde047 !important; border-color: #a1600033 !important; }
  .bg-purple-100.text-purple-800 { background: #3b0764 !important; color: #c4b5fd !important; border-color: #7c3aed33 !important; }
  .bg-red-100.text-red-800 { background: #450a0a !important; color: #fca5a5 !important; border-color: #dc262633 !important; }
  .bg-green-50.text-green-700.border-green-200 { background: #14532d !important; color: #86efac !important; border-color: #16a34a33 !important; }
  .bg-amber-50.text-amber-700.border-amber-200 { background: #422006 !important; color: #fbbf24 !important; border-color: #d9770633 !important; }
  .bg-cyan-50.text-cyan-700.border-cyan-200 { background: #083344 !important; color: #22d3ee !important; border-color: #06b6d433 !important; }

  /* Inputs & selects */
  input, select {
    background: #27272a !important;
    color: #d4d4d8 !important;
    border-color: #3f3f46 !important;
  }
  input::placeholder { color: #52525b !important; }

  /* Connected status bar */
  .bg-emerald-50 { background: #18181b !important; }
  .border-emerald-200 { border-color: #27272a !important; }
  .text-emerald-700 { color: #22d3ee !important; }
  .bg-white\\/60 { background: rgba(39, 39, 42, 0.6) !important; }
  .text-green-700 { color: #22d3ee !important; }
  .text-green-600 { color: #52525b !important; }

  /* Header buttons (copy, close) — match send button style */
  .text-gray-400 { color: #52525b !important; }
  .hover\\:bg-gray-100:hover { background: transparent !important; }
  .hover\\:text-gray-600:hover { color: #22d3ee !important; }

  /* Tab bar — inactive */
  button.text-gray-600 {
    color: #52525b !important;
  }
  button.text-gray-600:hover {
    color: #22d3ee !important;
    background: transparent !important;
  }
  .hover\\:text-gray-900:hover { color: #22d3ee !important; }
  /* Active tab */
  button.bg-gray-900 {
    background: transparent !important;
    color: #22d3ee !important;
    box-shadow: none !important;
    border-bottom: 2px solid #22d3ee !important;
    border-radius: 0 !important;
  }
  .text-white { color: #22d3ee !important; }

  /* Agent selector button in header */
  .border-gray-200.text-gray-700 {
    background: #27272a !important;
    border-color: #3f3f46 !important;
    color: #d4d4d8 !important;
  }

  /* Table */
  thead { background: #1c1c1f !important; }
  table { table-layout: fixed !important; width: 100% !important; }
  th { color: #71717a !important; font-weight: 500 !important; }
  tr { border-color: #27272a !important; }
  tr:hover { background: #27272a !important; }
  td, th { border-color: #27272a !important; overflow: hidden !important; text-overflow: ellipsis !important; }
  .max-w-xs { max-width: 140px !important; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #18181b; }
  ::-webkit-scrollbar-thumb { background: #3f3f46; border-radius: 3px; }

  /* SVG icons */
  svg { color: currentColor !important; }

  /* Drag handle */
  .drag-handle { cursor: grab !important; }

  /* Resize handle */
  .cursor-se-resize, .cursor-nwse-resize {
    opacity: 0.3 !important;
  }
`;

export function DevConsoleTheme() {
  useEffect(() => {
    const inject = () => {
      const inspector = document.querySelector("cpk-web-inspector");
      if (!inspector?.shadowRoot) return false;
      if (inspector.shadowRoot.querySelector("#langrepl-dark-theme")) return true;

      const style = document.createElement("style");
      style.id = "langrepl-dark-theme";
      style.textContent = DARK_STYLES;
      inspector.shadowRoot.appendChild(style);
      return true;
    };

    // The web component may not exist yet — observe for it
    if (inject()) return;

    const observer = new MutationObserver(() => {
      if (inject()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    return () => observer.disconnect();
  }, []);

  return null;
}
