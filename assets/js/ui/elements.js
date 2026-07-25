const byId = (id) => document.querySelector(`#${id}`);

export const el = Object.fromEntries(
  "app model modelRuntimeDot modelRuntimeText conversationSelect newConversation deleteConversation activeModel connectionStatus statusDot statusText temperature temperatureValue contextMode context contextValue contextMaxLabel contextHelp systemPrompt chat emptyState composer prompt send fileInput fileHelp attachments attachmentNote systemHost systemCpu systemMemory systemDisk systemLoadLabel systemLoad systemUptime systemGpu systemNote refreshSystem refreshModels clearChat shutdownServer collapseSidebar expandSidebar openSettings closeSettings settingsOverlay"
    .split(" ").map((id) => [id, byId(id)])
);
