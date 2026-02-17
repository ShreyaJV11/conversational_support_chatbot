import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Minimize2, Send, AlertCircle } from 'lucide-react';
import ChatApiService from '../services/chatApi';
import { ChatMessage, ChatWidgetConfig, ChatWidgetState } from '../types';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';

interface ChatWidgetProps {
  config?: ChatWidgetConfig;
}

const ChatWidget: React.FC<ChatWidgetProps> = ({ config = {} }) => {
  const {
    apiBaseUrl = 'http://localhost:3000',
    theme = {},
    position = { bottom: '20px', right: '20px' },
    initialMessage = true,
    userName,
    maxMessages = 50,
    typingDelay = 1000
  } = config;

  const [state, setState] = useState<ChatWidgetState>({
    isOpen: false,
    isMinimized: false,
    messages: [],
    isLoading: false,
    hasError: false,
    isTyping: false,
    unreadCount: 0,
    collectingInfo: false,
    userInfo: {},
    pendingQuestion: undefined
  });

  const [inputValue, setInputValue] = useState('');
  const [chatApi] = useState(() => new ChatApiService(apiBaseUrl));
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [state.messages, state.isTyping]);

  // Load initial message when widget opens for the first time
  useEffect(() => {
    if (state.isOpen && initialMessage && state.messages.length === 0) {
      loadInitialMessage();
    }
  }, [state.isOpen]);

  // Focus input when chat opens
  useEffect(() => {
    if (state.isOpen && !state.isMinimized) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [state.isOpen, state.isMinimized]);

  const loadInitialMessage = async () => {
    try {
      const initialMsg = await chatApi.getInitialMessage(userName);
      const botMessage: ChatMessage = {
        id: `msg_${Date.now()}`,
        type: 'bot',
        content: initialMsg,
        timestamp: new Date()
      };

      setState(prev => ({
        ...prev,
        messages: [botMessage]
      }));
    } catch (error) {
      console.error('Failed to load initial message:', error);
    }
  };

  const handleToggleChat = () => {
    setState(prev => ({
      ...prev,
      isOpen: !prev.isOpen,
      isMinimized: false,
      unreadCount: prev.isOpen ? prev.unreadCount : 0 // Reset unread count when opening
    }));
  };

  const handleMinimize = () => {
    setState(prev => ({
      ...prev,
      isMinimized: !prev.isMinimized
    }));
  };

  const handleSendMessage = async () => {
    const message = inputValue.trim();
    if (!message || state.isLoading) return;

    // Add user message
    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}_user`,
      type: 'user',
      content: message,
      timestamp: new Date()
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      hasError: false,
      isTyping: true
    }));

    setInputValue('');

    try {
      // Simulate typing delay for better UX
      await new Promise(resolve => setTimeout(resolve, typingDelay));

      // Prepare request with user info if we have it
      const request: any = {
        user_question: message
      };

      // If we're collecting info or have user info, include it
      if (state.collectingInfo && state.pendingQuestion) {
        // This is a response to info collection, parse the user input
        const userInfoResponse = parseUserInfoResponse(message);
        request.user_question = state.pendingQuestion;
        request.user_info = { ...state.userInfo, ...userInfoResponse };
      } else if (Object.keys(state.userInfo).length > 0) {
        request.user_info = state.userInfo;
      }

      const response = await chatApi.sendMessage(request);
      
      // Handle different response types
      let botContent = '';
      let confidence_score: number | undefined;
      let case_id: string | undefined;
      let newState = { ...state };

      switch (response.response_type) {
        case 'ANSWERED':
          botContent = response.answer || 'I was able to find an answer for you.';
          confidence_score = response.confidence_score;
          newState.collectingInfo = false;
          newState.pendingQuestion = undefined;
          break;
        case 'COLLECT_INFO':
          botContent = response.message || 'I need some information to help you.';
          newState.collectingInfo = true;
          newState.pendingQuestion = message;
          break;
        case 'ESCALATED':
          botContent = response.message || 'Your question has been escalated to our support team.';
          case_id = response.case_id;
          newState.collectingInfo = false;
          newState.pendingQuestion = undefined;
          // Store user info for future use
          if (request.user_info) {
            newState.userInfo = request.user_info;
          }
          break;
        case 'ERROR':
          botContent = response.message || 'Sorry, something went wrong. Please try again.';
          newState.collectingInfo = false;
          newState.pendingQuestion = undefined;
          break;
      }

      const botMessage: ChatMessage = {
        id: `msg_${Date.now()}_bot`,
        type: 'bot',
        content: botContent,
        timestamp: new Date(),
        confidence_score,
        case_id
      };

      setState(prev => ({
        ...newState,
        messages: [...prev.messages, botMessage].slice(-maxMessages), // Keep only last N messages
        isLoading: false,
        isTyping: false,
        unreadCount: prev.isOpen ? 0 : prev.unreadCount + 1
      }));

    } catch (error) {
      console.error('Failed to send message:', error);
      
      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        type: 'bot',
        content: error instanceof Error ? error.message : 'Sorry, something went wrong. Please try again.',
        timestamp: new Date()
      };

      setState(prev => ({
        ...prev,
        messages: [...prev.messages, errorMessage],
        isLoading: false,
        hasError: true,
        isTyping: false,
        collectingInfo: false,
        pendingQuestion: undefined
      }));
    }
  };

  // Helper function to parse user info from natural language input
  const parseUserInfoResponse = (input: string): Partial<{ name: string; email: string; organization: string }> => {
    const result: any = {};
    const lines = input.split('\n').map(line => line.trim()).filter(line => line);
    
    // Try to extract info from structured input
    for (const line of lines) {
      const lowerLine = line.toLowerCase();
      if (lowerLine.includes('name:') || lowerLine.includes('name ')) {
        result.name = line.split(':')[1]?.trim() || line.replace(/name\s*/i, '').trim();
      } else if (lowerLine.includes('email:') || lowerLine.includes('email ')) {
        result.email = line.split(':')[1]?.trim() || line.replace(/email\s*/i, '').trim();
      } else if (lowerLine.includes('organization:') || lowerLine.includes('org:') || lowerLine.includes('company:')) {
        result.organization = line.split(':')[1]?.trim() || line.replace(/(organization|org|company)\s*/i, '').trim();
      }
    }

    // If no structured format, try to parse as comma-separated values
    if (Object.keys(result).length === 0 && lines.length === 1) {
      const parts = lines[0].split(',').map(p => p.trim());
      if (parts.length >= 3) {
        result.name = parts[0];
        result.email = parts[1];
        result.organization = parts[2];
      }
    }

    return result;
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const widgetStyle = {
    position: 'fixed' as const,
    bottom: position.bottom,
    right: position.right,
    zIndex: 9999,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
  };

  return (
    <div style={widgetStyle} className="chat-widget">
      {/* Chat Panel */}
      {state.isOpen && (
        <div 
          className={`mb-4 bg-white rounded-lg shadow-chat border border-gray-200 transition-all duration-300 ${
            state.isMinimized ? 'h-14' : 'h-96 w-80'
          } animate-slide-up`}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 bg-primary-600 text-white rounded-t-lg">
            <div className="flex items-center space-x-2">
              <MessageCircle size={20} />
              <span className="font-medium">MPS Support Assistant</span>
              {state.hasError && (
                <AlertCircle size={16} className="text-yellow-300" />
              )}
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleMinimize}
                className="p-1 hover:bg-primary-700 rounded transition-colors"
                title={state.isMinimized ? 'Expand' : 'Minimize'}
              >
                <Minimize2 size={16} />
              </button>
              <button
                onClick={handleToggleChat}
                className="p-1 hover:bg-primary-700 rounded transition-colors"
                title="Close"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Chat Content */}
          {!state.isMinimized && (
            <>
              {/* Messages */}
              <div className="flex-1 p-4 h-64 overflow-y-auto bg-gray-50">
                <div className="space-y-3">
                  {state.messages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
                  {state.isTyping && <TypingIndicator />}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* Input */}
              <div className="p-4 border-t border-gray-200 bg-white rounded-b-lg">
                <div className="flex items-center space-x-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type your question..."
                    disabled={state.isLoading}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
                    maxLength={1000}
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={!inputValue.trim() || state.isLoading}
                    className="p-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    title="Send message"
                  >
                    <Send size={16} />
                  </button>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Press Enter to send • Max 1000 characters
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Floating Button */}
      <button
        onClick={handleToggleChat}
        className={`relative w-14 h-14 bg-primary-600 hover:bg-primary-700 text-white rounded-full shadow-button transition-all duration-300 flex items-center justify-center ${
          state.isOpen ? 'rotate-0' : 'hover:scale-110'
        }`}
        title="Open Support Chat"
      >
        {/* Pulse animation ring when closed */}
        {!state.isOpen && (
          <div className="absolute inset-0 rounded-full bg-primary-600 animate-pulse-ring"></div>
        )}
        
        {state.isOpen ? (
          <X size={24} />
        ) : (
          <MessageCircle size={24} />
        )}

        {/* Unread count badge */}
        {state.unreadCount > 0 && !state.isOpen && (
          <div className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full w-6 h-6 flex items-center justify-center font-bold">
            {state.unreadCount > 9 ? '9+' : state.unreadCount}
          </div>
        )}
      </button>
    </div>
  );
};

export default ChatWidget;