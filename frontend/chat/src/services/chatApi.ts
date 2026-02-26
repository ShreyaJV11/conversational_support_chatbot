import axios, { AxiosResponse } from 'axios';
import { ChatRequest, ChatResponse } from '../types';

class ChatApiService {
  private baseUrl: string;
  private sessionId: string;
  private userInfo?: { name: string; email: string };

  constructor(baseUrl: string = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.sessionId = this.generateSessionId();
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random()
      .toString(36)
      .substring(2, 9)}`;
  }

  // ✅ STEP 1 — Set user info manually (recommended way)
  setUserInfo(name: string, email: string) {
    this.userInfo = { name, email };
  }
async sendMessage(request: ChatRequest | string): Promise<ChatResponse> {
  try {
    let chatRequest: ChatRequest;

    // -----------------------------
    // 🔹 If user typed name,email
    // -----------------------------
    if (typeof request === 'string' && request.includes(',')) {
      const parts = request.split(',');

      if (parts.length === 2) {
        const name = parts[0].trim();
        const email = parts[1].trim();

        this.setUserInfo(name, email);

        // Send to backend so it stores user
        chatRequest = {
          user_question: "User Registered",
          user_session_id: this.sessionId,
          user_info: this.userInfo
        };

      } else {
        throw new Error("Invalid name,email format");
      }
    }

    // -----------------------------
    // 🔹 Normal chat message
    // -----------------------------
    else if (typeof request === 'string') {
      chatRequest = {
        user_question: request,
        user_session_id: this.sessionId,
        user_info: this.userInfo
      };
    }

    else {
      chatRequest = {
        ...request,
        user_session_id: request.user_session_id || this.sessionId,
        user_info: request.user_info || this.userInfo
      };
    }

    console.log("SENDING TO BACKEND:", chatRequest);

    const finalUrl = `${this.baseUrl}/api/chat`;

    const response: AxiosResponse<ChatResponse> = await axios.post(
      finalUrl,
      chatRequest,
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000,
      }
    );

    return response.data;

  } catch (error) {
    console.error('Chat API error:', error);
    return {
      response_type: 'ERROR',
      message:
        'Bhai backend issue aa raha hai. Check karo uvicorn chal raha hai?'
    };
  }
}
async getInitialMessage(): Promise<ChatResponse> {
    try {
      const endpoint = this.baseUrl.endsWith('/api')
        ? '/chat/initial-message'
        : '/api/chat/initial-message';

      const finalUrl = `${this.baseUrl}${endpoint}`;

      const response: AxiosResponse<ChatResponse> = await axios.get(finalUrl);

      return response.data;
    } catch (error) {
      return {
        response_type: "ERROR",
        message: "Backend connect nahi ho raha."
      };
    }
  }

}
export default ChatApiService;