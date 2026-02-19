import axios, { AxiosResponse } from 'axios';
// Apne types ka path check kar lena
import { ChatRequest, ChatResponse } from '../types'; 

class ChatApiService {
  private baseUrl: string;
  private sessionId: string;

  constructor(baseUrl: string = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.sessionId = this.generateSessionId();
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  async sendMessage(request: ChatRequest | string): Promise<ChatResponse> {
    try {
      let chatRequest: ChatRequest;
      if (typeof request === 'string') {
        chatRequest = { user_question: request, user_session_id: this.sessionId };
      } else {
        chatRequest = { ...request, user_session_id: request.user_session_id || this.sessionId };
      }

      const endpoint = this.baseUrl.endsWith('/api') ? '/chat' : '/api/chat';
      const finalUrl = `${this.baseUrl}${endpoint}`;

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
        message: 'Bhai, backend se connection nahi ban paa raha. Check karo uvicorn chal raha hai?' 
      };
    }
  }

  async getInitialMessage(userName?: string): Promise<string> {
    try {
      const params = userName ? { name: userName } : {};
      const endpoint = this.baseUrl.endsWith('/api') ? '/chat/initial-message' : '/api/chat/initial-message';
      const finalUrl = `${this.baseUrl}${endpoint}`;

      const response: AxiosResponse<any> = await axios.get(finalUrl, { params });
      
      // Handle both: { message: "Hi" } or just "Hi"
      return response.data?.message || (typeof response.data === 'string' ? response.data : "Welcome!");
    } catch (error) {
      return `Hi ${userName || 'there'}, I'm the MPS Support Assistant. Backend connect nahi hua, par main yahi hoon!`;
    }
  }
}

export default ChatApiService;