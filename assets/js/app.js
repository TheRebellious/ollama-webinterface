import { el } from "./ui/elements.js";
import { state } from "./state.js";
import { setSettingsOpen, setSidebarCollapsed, setStatus } from "./ui/status.js";
import { effectiveContextSize, updateSettingRanges } from "./ui/settings.js";
import { renderMessages } from "./ui/chat.js";
import {
  createConversation,
  deleteCurrentConversation,
  loadConversation,
  loadConversations,
  saveCurrentConversation,
} from "./ui/conversations.js";
import { addFiles, renderAttachments } from "./services/files.js";
import { loadModels, loadModelContext, loadRunningModels } from "./services/models.js";
import { loadConfig, loadSystemInfo } from "./services/system.js";
import { sendPrompt } from "./services/chat.js";
import { post } from "./api/client.js";

// Event Listeners
el.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  sendPrompt();
});

el.prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendPrompt();
  }
});

el.model.addEventListener("change", () => {
  el.activeModel.textContent = el.model.value || "No model selected";
  loadRunningModels();
  loadModelContext();
});

el.preloadModel.addEventListener("click", async () => {
  if (!el.model.value || state.busy) return;
  el.preloadModel.disabled = true;
  el.preloadModel.textContent = "Loading model...";
  try {
    await post("/api/preload", { model: el.model.value, context: effectiveContextSize() });
    el.preloadModel.textContent = "Model preloaded";
    await loadRunningModels();
  } catch (error) {
    el.preloadModel.textContent = "Preload failed";
    console.error("Could not preload model", error);
  } finally {
    setTimeout(() => {
      el.preloadModel.disabled = false;
      el.preloadModel.textContent = "Preload model";
    }, 2500);
  }
});

el.conversationSelect.addEventListener("change", () =>
  loadConversation(el.conversationSelect.value)
);

el.newConversation.addEventListener("click", () => {
  createConversation();
  el.prompt.focus();
});

el.deleteConversation.addEventListener("click", deleteCurrentConversation);

el.refreshModels.addEventListener("click", () => loadModels(true));
el.refreshSystem.addEventListener("click", loadSystemInfo);

el.temperature.addEventListener("input", updateSettingRanges);
el.contextMode.addEventListener("change", updateSettingRanges);
el.context.addEventListener("input", updateSettingRanges);

el.fileInput.addEventListener("change", (event) =>
  addFiles(Array.from(event.target.files || []))
);

el.clearChat.addEventListener("click", () => {
  state.messages = [];
  state.attachments = [];
  renderAttachments();
  renderMessages();
  saveCurrentConversation();
});

el.shutdownServer.addEventListener("click", async () => {
  el.shutdownServer.disabled = true;
  el.shutdownServer.textContent = "Exiting...";
  try {
    await fetch("/api/shutdown", { method: "POST" });
  } finally {
    setStatus("bad", "Server stopped");
  }
});

el.collapseSidebar.addEventListener("click", () => setSidebarCollapsed(true));
el.expandSidebar.addEventListener("click", () => setSidebarCollapsed(false));
el.openSettings.addEventListener("click", () => setSettingsOpen(true));
el.closeSettings.addEventListener("click", () => setSettingsOpen(false));
el.settingsOverlay.addEventListener("click", () => setSettingsOpen(false));

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setSettingsOpen(false);
});

// Initial startup
loadConversations();
updateSettingRanges();
loadConfig();
loadSystemInfo();
loadModels();

// Optimized polling based on document visibility (PE-002)
let systemIntervalId = null;
let modelsIntervalId = null;

function startPolling(intervalMs = 5000) {
  stopPolling();
  systemIntervalId = setInterval(loadSystemInfo, intervalMs);
  modelsIntervalId = setInterval(loadRunningModels, intervalMs);
}

function stopPolling() {
  if (systemIntervalId) clearInterval(systemIntervalId);
  if (modelsIntervalId) clearInterval(modelsIntervalId);
  systemIntervalId = null;
  modelsIntervalId = null;
}

// Start active polling
startPolling(5000);

// Adjust polling on visibility changes
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    // Slow down polling when user is in another tab to reduce CPU/network overhead
    startPolling(30000);
  } else {
    // Resume active polling immediately when tab becomes visible
    loadSystemInfo();
    loadRunningModels();
    startPolling(5000);
  }
});
