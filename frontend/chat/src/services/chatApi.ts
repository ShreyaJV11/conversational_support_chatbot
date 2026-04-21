import { ChatRequest, ChatResponse } from '../types';

interface ChatApiConfig {
  baseUrl?: string;
  botId?: number;
  organizationId?: string;
}

class ChatApiService {
  private baseUrl: string;
  private sessionId: string;
  private userInfo?: { name: string; email: string };
  private authToken?: string;

  private botId?: number;
  private organizationId?: string;

  constructor(config: ChatApiConfig = {}, sessionId?: string) {
    const {
      baseUrl = "http://127.0.0.1:8000",
      botId = 1,
      organizationId
    } = config;

    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.botId = botId;
    this.organizationId = organizationId;

    this.sessionId = sessionId || this.generateSessionId();

    // Load token if already stored
    this.authToken = localStorage.getItem("chat_token") || undefined;
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random()
      .toString(36)
      .substring(2, 9)}`;
  }

  // STEP 1 — Set user info manually
  setUserInfo(name: string, email: string) {
    this.userInfo = { name, email };
  }

  async sendMessage(
    request: ChatRequest | string,
    onChunk: (text: string, suggestions?: string[], images?: string[]) => void
  ): Promise<void> {
    try {
      let chatRequest: ChatRequest;

      // If user typed "name,email"
      if (typeof request === "string" && request.includes(",")) {

        const parts = request.split(",");

        if (parts.length === 2) {
          const name = parts[0].trim();
          const email = parts[1].trim();

          this.setUserInfo(name, email);

          chatRequest = {
            user_question: "User Registered",
            user_session_id: this.sessionId,
            user_info: this.userInfo
          };

        } else {
          throw new Error("Invalid name,email format");
        }
      }

      // Normal string message
      else if (typeof request === "string") {

        chatRequest = {
          user_question: request,
          user_session_id: this.sessionId,
          user_info: this.userInfo
        };
      }

      // Structured request
      else {
        chatRequest = {
          ...request,
          user_session_id: request.user_session_id || this.sessionId,
          user_info: request.user_info || this.userInfo
        };
      }

      if (this.botId) {
        (chatRequest as any).bot_id = this.botId;
      }

      if (this.organizationId) {
        (chatRequest as any).organization_id = this.organizationId;
      }

      const finalUrl = `${this.baseUrl}/api/v1/chat`;

      const response = await fetch(finalUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {})
        },
        body: JSON.stringify(chatRequest)
      });
      const suggestionsHeader = response.headers.get("X-Suggestions");
      const suggestions = suggestionsHeader ? JSON.parse(suggestionsHeader) : [];

      const imagesHeader = response.headers.get("X-Images");
      const images = imagesHeader ? JSON.parse(imagesHeader) : [];
      if (!response.ok) {
        throw new Error("Backend connection failed");
      }

      // If backend returns JSON (registration response with token)
      const contentType = response.headers.get("content-type");

      if (contentType && contentType.includes("application/json")) {

        const data = await response.json();

        // Save JWT token
        if (data.token) {
          this.authToken = data.token;
          localStorage.setItem("chat_token", data.token);
        }

        if (data.message) {
          onChunk(data.message, suggestions,images);
        }

        return;
      }

      if (!response.body) {
        throw new Error("Streaming not supported by backend");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      // Streaming response
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        onChunk(chunk, suggestions,images);
      }

    } catch (error) {

      console.error("Chat API streaming error:", error);

      onChunk("\n⚠ Backend connection issue. Please check server.");
    }
  }

  async getInitialMessage(): Promise<ChatResponse> {

    try {

      const finalUrl = `${this.baseUrl}/api/v1/chat/initial-message/${this.botId}`;

      const response = await fetch(finalUrl, {
        method: "GET"
      });

      if (!response.ok) {
        throw new Error("Failed to fetch initial message");
      }

      return await response.json();

    } catch (error) {

      console.error("Initial message error:", error);

      return {
        response_type: "ERROR",
        message: "⚠ Unable to load welcome message."
      };
    }
  }

  async getSuggestions(): Promise<string[]> {

    try {

      const finalUrl = `${this.baseUrl}/api/v1/bot/${this.botId}/suggestions`;

      const response = await fetch(finalUrl, {
        method: "GET"
      });
      if (!response.ok) {
        throw new Error("Failed to fetch suggestions");
      }

      return await response.json();

    } catch (error) {

      console.error("Suggestions error:", error);

      return [];
    }
  }
}

export default ChatApiService;