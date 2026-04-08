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
    this.authToken = localStorage.getItem("chat_token") || undefined;
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random()
      .toString(36)
      .substring(2, 9)}`;
  }

  setUserInfo(name: string, email: string) {
    this.userInfo = { name, email };
  }

  async sendMessage(
    request: ChatRequest | string,
    // ✅ ADDED third param: images[] from backend get_answers()["images"]
    onChunk: (text: string, suggestions?: string[], images?: string[]) => void
  ): Promise<void> {
    try {
      let chatRequest: ChatRequest;

      // --- Registration / Name,Email Handling ---
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

      // --- Normal Message Handling ---
      else if (typeof request === "string") {
        chatRequest = {
          user_question: request,
          user_session_id: this.sessionId,
          user_info: this.userInfo
        };
      }

      // --- Structured Object Handling ---
      else {
        chatRequest = {
          ...request,
          user_session_id: request.user_session_id || this.sessionId,
          user_info: request.user_info || this.userInfo
        };
      }

      // Inject Bot ID and Org ID if present
      if (this.botId) {
        (chatRequest as any).bot_id = this.botId;
      }

      if (this.organizationId) {
        (chatRequest as any).organization_id = this.organizationId;
      }

      const finalUrl = `${this.baseUrl}/api/chat`;

      const response = await fetch(finalUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {})
        },
        body: JSON.stringify(chatRequest)
      });

      if (!response.ok) {
        throw new Error("Backend connection failed");
      }

      // HEADER suggestions
      const suggestionsHeader = response.headers.get("X-Suggestions");
      let suggestions: string[] = [];

      if (suggestionsHeader) {
        try {
          suggestions = JSON.parse(suggestionsHeader);
        } catch (e) {
          console.error("Failed to parse suggestions header:", e);
          suggestions = suggestionsHeader.includes("|")
            ? suggestionsHeader.split("|")
            : [];
        }
      }

      const contentType = response.headers.get("content-type");

      // ── JSON response
      if (contentType && contentType.includes("application/json")) {
        const data = await response.json();

        if (data.token) {
          this.authToken = data.token;
          localStorage.setItem("chat_token", data.token);
        }

        const finalSuggestions = data.suggestions || suggestions;

        // ✅ NEW: backend returns {text, images} from get_answers()
        if (data.text !== undefined) {
          onChunk(data.text, finalSuggestions, data.images || []);
          return;
        }

        // Legacy: plain {message} response (welcome message etc.)
        if (data.message) {
          onChunk(data.message, finalSuggestions, []);
        }

        return;
      }

      // ── Streaming response
      if (!response.body) {
        throw new Error("Streaming not supported by backend");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        
        // Stream each chunk immediately to the UI
        if (chunk) {
          onChunk(chunk, suggestions, []);
        }
      }

      return;

    } catch (error) {
      console.error("Chat API streaming error:", error);
      onChunk("\n⚠ Backend connection issue. Please check server.", [], []);
    }
  }

  async getInitialMessage(): Promise<ChatResponse> {
    try {
      const finalUrl = `${this.baseUrl}/api/chat/initial-message/${this.botId}`;

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

  async getSuggestions(userQuery: string): Promise<string[]> {
    try {
      const finalUrl = `${this.baseUrl}/bot/${this.botId}/suggestions?user_query=${encodeURIComponent(userQuery)}`;

      const response = await fetch(finalUrl, {
        method: "GET"
      });

      if (!response.ok) {
        throw new Error("Failed to fetch suggestions");
      }

      const data = await response.json();
      return data.suggestions || [];

    } catch (error) {
      console.error("Suggestions error:", error);
      return [];
    }
  }
}

export default ChatApiService;