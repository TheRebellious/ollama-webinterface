import { el } from "./elements.js";
import { state } from "../state.js";

/**
 * Set the server/Ollama connection status indicator and text.
 *
 * @param {"ok"|"bad"|""} kind - Status indicator class.
 * @param {string} text - Human-readable status label.
 */
export function setStatus(kind, text) {
  el.statusDot.className = `dot ${kind}`;
  el.statusText.textContent = text;
  el.connectionStatus.textContent = text;
  state.online = kind === "ok";
}

/**
 * Toggle UI busy state during prompt generation, disabling inputs and showing progress.
 *
 * @param {boolean} value - True if currently generating response.
 */
export function setBusy(value) {
  state.busy = value;
  el.app.classList.toggle("is-busy", value);
  el.send.disabled = value || !state.online || !el.model.value;
  el.send.textContent = value ? "Generating..." : "Send";
  if (value) {
    el.statusDot.className = "dot loading";
    el.statusText.textContent = "Generating";
    el.connectionStatus.textContent = "Generating response...";
  } else if (state.online) {
    setStatus("ok", "Connected");
  }
}

/**
 * Set the active/idle runtime status indicator for the selected model.
 *
 * @param {"ok"|"bad"|""} kind - Runtime dot style.
 * @param {string} text - Description string (e.g. "Selected model is active").
 */
export function setModelRuntime(kind, text) {
  el.modelRuntimeDot.className = `runtime-dot ${kind}`;
  el.modelRuntimeText.textContent = text;
}

/**
 * Open or close the settings overlay / drawer.
 *
 * @param {boolean} open - True to open settings drawer.
 */
export const setSettingsOpen = (open) => el.app.classList.toggle("settings-open", open);

/**
 * Expand or collapse the sidebar on desktop screens.
 *
 * @param {boolean} collapsed - True to collapse sidebar.
 */
export const setSidebarCollapsed = (collapsed) => el.app.classList.toggle("sidebar-collapsed", collapsed);
