import { el } from "./elements.js";
import { state, storageKeys } from "../state.js";
import { renderMessages } from "./chat.js";

/**
 * Re-render the conversation dropdown selector.
 */
export function renderConversationSelect() {
  el.conversationSelect.innerHTML = "";
  state.conversations.forEach((conversation) => {
    const option = new Option(
      conversation.title || "New chat",
      conversation.id,
      false,
      conversation.id === state.conversationId
    );
    el.conversationSelect.add(option);
  });
}

/**
 * Safely persists conversation history to localStorage with quota protection (CR-003).
 */
export function persistConversations() {
  try {
    localStorage.setItem(storageKeys.conversations, JSON.stringify(state.conversations));
    if (state.conversationId) {
      localStorage.setItem(storageKeys.current, state.conversationId);
    }
  } catch (error) {
    console.warn("Could not save conversations to localStorage:", error);
    // If quota exceeded, attempt to trim oldest conversation messages
    if (error.name === "QuotaExceededError" || error.code === 22) {
      try {
        if (state.conversations.length > 5) {
          // Drop oldest 20% of conversations to free quota
          state.conversations = state.conversations.slice(0, Math.max(3, state.conversations.length - 2));
          localStorage.setItem(storageKeys.conversations, JSON.stringify(state.conversations));
          renderConversationSelect();
        }
      } catch (quotaError) {
        console.error("Critical: Storage quota exceeded and recovery failed", quotaError);
      }
    }
  }
}

/**
 * Save current active conversation state and update auto-generated title if needed.
 */
export function saveCurrentConversation() {
  const current = state.conversations.find((item) => item.id === state.conversationId);
  if (!current) return;

  current.messages = state.messages;
  current.updatedAt = Date.now();

  const firstUserMessage = state.messages.find((message) => message.role === "user");
  if (firstUserMessage && (current.title === "New chat" || !current.title)) {
    current.title = firstUserMessage.displayContent?.trim().slice(0, 48) || "New chat";
  }

  persistConversations();
  renderConversationSelect();
}

/**
 * Create a new conversation and activate it.
 */
export function createConversation(title = "New chat", messages = []) {
  const conversation = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    title,
    messages,
    updatedAt: Date.now(),
  };
  state.conversations.unshift(conversation);
  state.conversationId = conversation.id;
  state.messages = messages;
  persistConversations();
  renderConversationSelect();
  renderMessages();
}

/**
 * Switch to a specific conversation by ID.
 */
export function loadConversation(id) {
  const conversation = state.conversations.find((item) => item.id === id);
  if (!conversation) return;

  state.conversationId = id;
  state.messages = Array.isArray(conversation.messages) ? conversation.messages : [];
  persistConversations();
  renderConversationSelect();
  renderMessages();
}

/**
 * Load all conversations from localStorage with validation (CR-003).
 */
export function loadConversations() {
  try {
    const raw = localStorage.getItem(storageKeys.conversations);
    if (!raw) {
      state.conversations = [];
    } else {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        // Validate each conversation entry
        state.conversations = parsed.filter(
          (c) => c && typeof c === "object" && typeof c.id === "string"
        );
      } else {
        state.conversations = [];
      }
    }
  } catch (error) {
    console.warn("Malformed conversation data in localStorage, resetting:", error);
    state.conversations = [];
  }

  const current = localStorage.getItem(storageKeys.current);
  if (current && state.conversations.some((item) => item.id === current)) {
    loadConversation(current);
  } else if (state.conversations.length > 0) {
    loadConversation(state.conversations[0].id);
  } else {
    createConversation();
  }
}

/**
 * Delete the currently selected conversation.
 */
export function deleteCurrentConversation() {
  state.conversations = state.conversations.filter((item) => item.id !== state.conversationId);
  if (!state.conversations.length) {
    return createConversation();
  }
  loadConversation(state.conversations[0].id);
}
