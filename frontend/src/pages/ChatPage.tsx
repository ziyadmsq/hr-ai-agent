import { Button } from "@/components/ui/button";
import ChatInput from "@/components/chat/ChatInput";
import ChatMessageList from "@/components/chat/ChatMessageList";
import { useChat } from "@/hooks/useChat";
import { Trash2 } from "lucide-react";

export default function ChatPage() {
  const { messages, isLoading, sendMessage, clearMessages } = useChat();

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div>
          <h2 className="text-lg font-semibold">HR Assistant</h2>
          <p className="text-xs text-muted-foreground">
            AI-powered assistant — answers questions, checks leave, and generates documents
          </p>
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={clearMessages}>
            <Trash2 className="mr-1 h-4 w-4" />
            Clear
          </Button>
        )}
      </div>
      <ChatMessageList messages={messages} isLoading={isLoading} />
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}

