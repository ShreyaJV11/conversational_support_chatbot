import axios, { AxiosResponse } from 'axios';
import { ChatRequest, ChatResponse, InitialMessageResponse, ApiError } from '../types';

class ChatApiService {
  private baseUrl: string;
  private sessionId: string;

  constructor(baseUrl: string = 'http://localhost:3000') {
    this.baseUrl = baseUrl;
    this.sessionId = this.generateSessionId();
  }

  /**
   * Generate a unique session ID for tracking user conversations
   */
  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Send a question to the chatbot API
   */
  async sendMessage(request: ChatRequest | string): Promise<ChatResponse> {
    try {
      // Handle both old string format and new object format for backward compatibility
      let chatRequest: ChatRequest;
      
      if (typeof request === 'string') {
        chatRequest = {
          user_question: request,
          user_session_id: this.sessionId
        };
      } else {
        chatRequest = {
          ...request,
          user_session_id: request.user_session_id || this.sessionId
        };
      }

      const response: AxiosResponse<ChatResponse> = await axios.post(
        `${this.baseUrl}/api/chat`,
        chatRequest,
        {
          headers: {
            'Content-Type': 'application/json',
          },
          timeout: 30000, // 30 second timeout
        }
      );

      return response.data;
    } catch (error) {
      console.error('Chat API error:', error);
      
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 429) {
          throw new Error('Too many requests. Please wait a moment before trying again.');
        } else if (error.response?.status && error.response.status >= 500) {
          throw new Error('Our service is temporarily unavailable. Please try again later.');
        } else if (error.response?.data?.error) {
          const apiError = error.response.data as ApiError;
          throw new Error(apiError.error.message);
        }
      }
      
      // Fallback error response matching the API specification
      return {
        response_type: 'ERROR',
        message: 'Sorry, something went wrong on our end. Your request has been escalated to our support team.'
      };
    }
  }

  /**
   * Get the initial greeting message
   */
  async getInitialMessage(userName?: string): Promise<string> {
    try {
      const params = userName ? { name: userName } : {};
      const response: AxiosResponse<InitialMessageResponse> = await axios.get(
        `${this.baseUrl}/api/chat/initial-message`,
        { params }
      );

      return response.data.message;
    } catch (error) {
      console.error('Initial message API error:', error);
      // Fallback to default message
      const name = userName || 'there';
      return `Hi${name}, I'm the MPS Support Assistant. I can help with DOI, Access, Hosting-related queries and other tech queries by generating context understood technical responses. In other cases, I can help raise a salesforce support ticket. To assist you better, please provide your **Name** and **Email** to start the chat.`;
    }
  }

  /**
   * Check if the chat service is healthy
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await axios.get(`${this.baseUrl}/api/chat/health`, {
        timeout: 5000
      });
      return response.status === 200;
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }

  /**
   * Get current session ID
   */
  getSessionId(): string {
    return this.sessionId;
  }

  /**
   * Reset session (generate new session ID)
   */
  resetSession(): void {
    this.sessionId = this.generateSessionId();
  }
}

export default ChatApiService;