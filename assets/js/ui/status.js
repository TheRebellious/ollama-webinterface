import { el } from "./elements.js";
import { state } from "../state.js";
export function setStatus(kind, text) {
  el.statusDot.className = `dot ${kind}`; el.statusText.textContent = text; el.connectionStatus.textContent = text;
  state.online = kind === "ok";
}
export function setBusy(value) {
  state.busy = value; el.app.classList.toggle("is-busy", value); el.send.disabled = value || !state.online || !el.model.value;
  el.send.textContent = value ? "Generating..." : "Send";
  if (value) { el.statusDot.className = "dot loading"; el.statusText.textContent = "Generating"; el.connectionStatus.textContent = "Generating response..."; }
  else if (state.online) setStatus("ok", "Connected");
}
export function setModelRuntime(kind, text) { el.modelRuntimeDot.className = `runtime-dot ${kind}`; el.modelRuntimeText.textContent = text; }
export const setSettingsOpen = (open) => el.app.classList.toggle("settings-open", open);
export const setSidebarCollapsed = (collapsed) => el.app.classList.toggle("sidebar-collapsed", collapsed);
