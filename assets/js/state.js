export const state = {
  messages: [],
  attachments: [],
  conversations: [],
  conversationId: null,
  busy: false,
  online: false,
  maxFileBytes: 10 * 1024 * 1024,
  detectedContextTokens: null,
  modelContextTokens: null,
  contextSource: null,
};

export const allowedExtensions = new Set(
  "txt md markdown csv json jsonl log xml yaml yml toml ini conf cfg py js ts tsx jsx html css sh ps1 sql java c cpp h hpp cs go rs php rb swift kt kts r lua dockerfile gitignore docx xlsx pptx".split(
    " "
  )
);

export const officeExtensions = new Set(["docx", "xlsx", "pptx"]);

export const storageKeys = {
  conversations: "ollama-console-conversations",
  current: "ollama-console-current-conversation",
  preferences: "ollama-console-preferences",
};
