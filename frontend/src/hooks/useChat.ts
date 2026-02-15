import { useState, useCallback, useRef } from "react";
import api from "@/lib/api";

export interface ToolCallInfo {
  tool: string;
  arguments: Record<string, unknown>;
  result: unknown;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallInfo[];
  timestamp: Date;
}

let messageIdCounter = 0;
function nextId(): string {
  messageIdCounter += 1;
  return `msg-${messageIdCounter}-${Date.now()}`;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const conversationIdRef = useRef<string | null>(null);

  const ensureConversation = useCallback(async (): Promise<string> => {
    if (conversationIdRef.current) {
      return conversationIdRef.current;
    }
    const { data } = await api.post("/v1/chat/conversations");
    conversationIdRef.current = data.id;
    return data.id;
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const conversationId = await ensureConversation();

        const { data } = await api.post("/v1/chat/message", {
          conversation_id: conversationId,
          content,
        });

        const assistantMsg: ChatMessage = {
          id: nextId(),
          role: "assistant",
          content: data.response,
          toolCalls: data.tool_calls ?? undefined,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch {
        const errorMsg: ChatMessage = {
          id: nextId(),
          role: "assistant",
          content:
            "Sorry, I encountered an error processing your question. Please try again.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [ensureConversation],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    conversationIdRef.current = null;
  }, []);

  return { messages, isLoading, sendMessage, clearMessages };
}

