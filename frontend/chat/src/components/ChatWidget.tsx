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
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("mps_chat_session");
    if (existing) return existing;

    const newId = "session_" + Date.now();
    localStorage.setItem("mps_chat_session", newId);
    return newId;
  });

  const {
    apiBaseUrl = 'http://localhost:3000',
    botId,
    organizationId,
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
  
  // RESIZE STATE
  const [size, setSize] = useState({
    width: 320,
    height: 384
  });

  const [isResizing, setIsResizing] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  
  const chatApi = React.useMemo(() => {
    return new ChatApiService({
      baseUrl: apiBaseUrl,
      botId,
      organizationId
    });
  }, [apiBaseUrl, botId, organizationId]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [state.messages, state.isTyping]);

  useEffect(() => {
    if (state.isOpen && initialMessage && state.messages.length === 0) {
      loadInitialMessage();
    }
  }, [state.isOpen, initialMessage, state.messages.length, chatApi]);

  useEffect(() => {
    if (state.userInfo?.name && state.userInfo?.email) {
      const loadSuggestions = async () => {
        try {
          const data = await chatApi.getSuggestions();
          setSuggestions(data);
        } catch (err) {
          console.error("Suggestions error", err);
        }
      };
      loadSuggestions();
    }
  }, [state.userInfo]);

  // Focus input when chat opens
  useEffect(() => {
    if (state.isOpen && !state.isMinimized) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [state.isOpen, state.isMinimized]);

  const loadInitialMessage = async () => {
    try {
      const response = await chatApi.getInitialMessage();

      const botMessage: ChatMessage = {
        id: `msg_${Date.now()}`,
        type: 'bot',
        content: response.message ?? "Welcome!",
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

  const handleSendMessage = async (customMessage?: string) => {
    const message = (customMessage ?? inputValue).trim();
    if (!message || state.isLoading) return;
    
    setSuggestions([]);

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}_user`,
      type: 'user',
      content: message,
      timestamp: new Date()
    };

    const botMessageId = `msg_${Date.now()}_bot`;

    const botMessage: ChatMessage = {
      id: botMessageId,
      type: 'bot',
      content: '',
      timestamp: new Date()
    };

    setState(prev => {
      const updatedMessages = [...prev.messages, userMessage, botMessage];

      return {
        ...prev,
        messages: updatedMessages.slice(-maxMessages),
        isLoading: true,
        isTyping: false,
        hasError: false
      };
    });

    setInputValue('');

    try {
      await new Promise(resolve => setTimeout(resolve, typingDelay));

      const request: any = {
        user_question: message,
        user_session_id: sessionId 
      };

      if (Object.keys(state.userInfo).length > 0) {
        request.user_info = state.userInfo;
      }

      await chatApi.sendMessage(request, (chunk: string) => {
        setState(prev => ({
          ...prev,
          messages: prev.messages.map(msg =>
            msg.id === botMessageId
              ? { ...msg, content: msg.content + chunk }
              : msg
          )
        }));
      });

      setState(prev => ({
        ...prev,
        isLoading: false
      }));

    } catch (error) {
      console.error('Streaming failed:', error);

      setState(prev => ({
        ...prev,
        isLoading: false,
        hasError: true
      }));
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // RESIZE HANDLERS
  const handleResizeStart = () => {
    setIsResizing(true);
  };

  // Only ONE useEffect for handling the resize movement
  useEffect(() => {
    const handleResizeMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      // We parse the position string to an integer, defaulting to 20 if it fails
      const rightPadding = parseInt(String(position.right || '20').replace(/[^0-9]/g, '')) || 20;
      const bottomPadding = parseInt(String(position.bottom || '20').replace(/[^0-9]/g, '')) || 20;

      // Calculate width & height from cursor to the right/bottom edge
      const newWidth = Math.min(Math.max(320, window.innerWidth - e.clientX - rightPadding), 800);
      const newHeight = Math.min(Math.max(350, window.innerHeight - e.clientY - bottomPadding), 800);
      
      setSize({ width: newWidth, height: newHeight });
    };

    const handleResizeEnd = () => setIsResizing(false);

    if (isResizing) {
      window.addEventListener("mousemove", handleResizeMove);
      window.addEventListener("mouseup", handleResizeEnd);
      // Prevent text selection while dragging to keep it smooth
      document.body.style.userSelect = 'none'; 
    } else {
      document.body.style.userSelect = '';
    }

    return () => {
      window.removeEventListener("mousemove", handleResizeMove);
      window.removeEventListener("mouseup", handleResizeEnd);
      document.body.style.userSelect = '';
    };
  }, [isResizing, position]);

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
          className="relative mb-4 bg-white rounded-lg shadow-chat border border-gray-200 transition-all duration-300 animate-slide-up flex flex-col"
          style={{
            width: state.isMinimized ? 320 : size.width,
            height: state.isMinimized ? 56 : size.height
          }}
        >
          {/* ✨ NEW: TOP-LEFT RESIZE HANDLE ✨ */}
          {!state.isMinimized && (
            <div
              onMouseDown={handleResizeStart}
              className="absolute top-0 left-0 w-6 h-6 cursor-nwse-resize z-50"
              title="Drag to resize"
              style={{
                borderTopLeftRadius: '0.5rem',
                // A subtle gradient to show the user it's draggable
                background: 'linear-gradient(135deg, rgba(255,255,255,0.4) 0%, transparent 50%)'
              }}
            />
          )}

          {/* Header */}
          <div className="flex items-center justify-between p-4 bg-primary-600 text-white rounded-t-lg">
            <div className="flex items-center space-x-2">
              <MessageCircle size={20} />
              <span className="font-medium">MPS Support Assistant</span>
              {state.hasError && (
                <AlertCircle size={16} className="text-yellow-300" />
              )}
            </div>
            <div className="flex items-center space-x-2 z-10">
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
              <div className="flex-1 p-4 overflow-y-auto bg-gray-50">
                <div className="space-y-3">
                  {/* Suggested Questions */}
                  {state.userInfo?.name && state.userInfo?.email && state.messages.filter(m => m.type === "user").length === 0 && suggestions.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-2 font-semibold">
                        Suggested Questions
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {suggestions.map((q, index) => (
                          <button
                            key={index}
                            onClick={() => handleSendMessage(q)}
                            className="px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-full hover:bg-primary-50 hover:border-primary-300 transition"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
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
                    onClick={() => handleSendMessage()}
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
        {!state.isOpen && (
          <div className="absolute inset-0 rounded-full bg-primary-600 animate-pulse-ring"></div>
        )}
        
        {state.isOpen ? (
          <X size={24} />
        ) : (
          <MessageCircle size={24} />
        )}

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