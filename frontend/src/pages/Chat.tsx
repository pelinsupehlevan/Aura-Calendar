import { useState, useRef, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { SendIcon } from "lucide-react";
import axios from "axios"; // Add axios import

export default function ChatPage() {
  const { messages, addMessage } = useAppStore();
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
  
    const userMessage = input.trim();
    setInput(""); // Clear the input field
  
    // Add user message to chat
    addMessage({
      role: "user",
      user_message: userMessage,
      content: userMessage
    });
  
    // Set loading state to true
    setIsLoading(true);
    try {
      // Send the user input to the Flask backend
      const response = await axios.post("http://127.0.0.1:5000/api/classify", {
        user_input: userMessage,
      });
  
      console.log("Backend response:", response.data);  // Log the response data
  
      if (response.data.error) {
        throw new Error(response.data.error);
      }
  
      // Check the structure of the response
      const { bot_response } = response.data;
  
      // Add assistant response to chat
      addMessage({
        role: "assistant",
        content: bot_response,
      });
    } catch (error) {
      console.error("Error during request:", error);
      addMessage({
        role: "assistant",
        content: "Sorry, there was an error processing your request. Please try again.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="max-w-2xl mx-auto p-4">
      <Card className="shadow-lg">
        <div className="p-4 space-y-4">
          <h2 className="text-2xl font-bold text-center">Personal Assistant Chatbot</h2>

          <div className="space-y-4 min-h-[400px] max-h-[600px] overflow-y-auto p-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "message",
                  message.role === "user" ? "text-right" : "text-left"
                )}
              >
                <div
                  className={cn(
                    "inline-block p-3 rounded-lg",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  <strong>{message.role === "user" ? "You: " : "Bot: "}</strong>
                  {message.user_message || message.content}

                  {/* Check if message.intent_info exists and render its properties */}
                  {message.intent_info && (
                    <div className="text-sm opacity-75">
                      <div>Saved intent: {String(message.intent_info.intent)}</div>
                      <div>Importance: {String(message.intent_info.importance)}</div>
                      <div>Summary: {String(message.intent_info.summary)}</div>
                    </div>
)}

                  
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="text-left">
                <div className="inline-block p-3 rounded-lg bg-muted">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 rounded-full bg-current animate-bounce" />
                    <div className="w-2 h-2 rounded-full bg-current animate-bounce [animation-delay:0.2s]" />
                    <div className="w-2 h-2 rounded-full bg-current animate-bounce [animation-delay:0.4s]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              type="text"
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={isLoading || !input.trim()}>
              <SendIcon className="h-4 w-4 mr-2" />
              Send
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
