// Chat API Types
export interface ChatRequest {
  user_question: string;
  user_session_id?: string;
  user_info?: {
    name?: string;
    email?: string;
    organization?: string;
  };
}

export interface ChatResponse {
  response_type: 'ANSWERED' | 'ESCALATED' | 'ERROR' | 'COLLECT_INFO';
  answer?: string;
  message?: string;
  case_id?: string;
  confidence_score?: number;
  info_needed?: ('name' | 'email' | 'organization')[];
}

export interface InitialMessageResponse {
  message: string;
  timestamp: string;
}

// Chat Message Types
export interface ChatMessage {
  id: string;
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
  isTyping?: boolean;
  confidence_score?: number;
  case_id?: string;
}

// Widget Configuration
export interface ChatWidgetConfig {
  apiBaseUrl?: string;
  theme?: {
    primaryColor?: string;
    backgroundColor?: string;
    textColor?: string;
    borderRadius?: string;
  };
  position?: {
    bottom?: string;
    right?: string;
  };
  initialMessage?: boolean;
  userName?: string;
  sessionId?: string;
  maxMessages?: number;
  typingDelay?: number;
}

// Widget State
export interface ChatWidgetState {
  isOpen: boolean;
  isMinimized: boolean;
  messages: ChatMessage[];
  isLoading: boolean;
  hasError: boolean;
  errorMessage?: string;
  isTyping: boolean;
  unreadCount: number;
  collectingInfo: boolean;
  userInfo: {
    name?: string;
    email?: string;
    organization?: string;
  };
  pendingQuestion?: string; // Store the question that triggered info collection
}

// API Error Response
export interface ApiError {
  error: {
    code: string;
    message: string;
    timestamp: string;
    path: string;
    details?: any;
  };
}