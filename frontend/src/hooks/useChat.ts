import { useState, useCallback } from "react";
import api from "@/lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: { chunk_text: string; similarity: number }[];
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

  const sendMessage = useCallback(async (question: string) => {
    const userMsg: ChatMessage = {
      id: nextId(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const { data } = await api.post("/v1/rag/query", {
        question,
        top_k: 5,
      });

      // Build assistant response from RAG results
      const chunks = data.results as {
        chunk_text: string;
        similarity: number;
      }[];

      let answer: string;
      if (chunks.length === 0) {
        answer =
          "I couldn't find any relevant information in the knowledge base. Please try rephrasing your question or contact HR directly.";
      } else {
        answer =
          "Based on the company policies, here's what I found:\n\n" +
          chunks
            .slice(0, 3)
            .map(
              (c, i) =>
                `**Source ${i + 1}** (${(c.similarity * 100).toFixed(0)}% match):\n${c.chunk_text}`
            )
            .join("\n\n");
      }

      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: answer,
        sources: chunks,
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
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, isLoading, sendMessage, clearMessages };
}

