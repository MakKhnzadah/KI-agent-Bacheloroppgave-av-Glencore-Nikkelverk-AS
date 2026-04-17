export type StoredChatMessage = {
  role: "user" | "ai";
  content: string;
};

export type StoredChatHistory = Record<string, StoredChatMessage[]>;

const CHAT_STORAGE_PREFIX = "ki_chat_history:";
const KB_CHAT_STORAGE_PREFIX = "ki_kb_chat_sessions:";

export function getChatStorageKey(email: string): string {
  return `${CHAT_STORAGE_PREFIX}${(email || "").trim().toLowerCase()}`;
}

export function getKnowledgeChatStorageKey(email: string): string {
  return `${KB_CHAT_STORAGE_PREFIX}${(email || "").trim().toLowerCase()}`;
}

export function safeParseChatHistory(raw: string | null): StoredChatHistory {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as StoredChatHistory;
  } catch {
    return {};
  }
}

export function safeParseJson<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}
