import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Minimize2, Send, AlertCircle,RotateCcw  } from 'lucide-react';
import ChatApiService from '../services/chatApi';
import { ChatMessage, ChatWidgetConfig, ChatWidgetState } from '../types';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
// Change this line at the top of ChatWidget.tsx



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
    apiBaseUrl = 'http://localhost:8000',
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

 useEffect(() => {
    const lastMessage = state.messages[state.messages.length - 1];
    
    // ✨ FIX 1: state.isLoading === false (Yani jab bot ki typing poori khatam ho jaye, tabhi chalega)
    if (!state.isLoading && lastMessage && lastMessage.type === 'bot' && lastMessage.content.includes('Thank you')) {
      
      const fetchChips = async () => {
        try {
          const data: any = await chatApi.getSuggestions(); 
          
          // ✨ FIX 2: Backend ke Object se asli Array bahar nikala!
          const actualArray = Array.isArray(data) ? data : (data.suggestions || []);
          
          if (actualArray.length > 0) {
            setSuggestions(actualArray); 
          }
        } catch (err) {
          console.error("Suggestions nahi aayi", err);
        }
      };
      
      fetchChips();
    }
  }, [state.messages, state.isLoading, chatApi]);

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
  // --- RESET HANDLER ---
  const handleResetChat = () => {
    if (window.confirm("Are you sure you want to clear this conversation?")) {
      // 1. Clear Local Storage
      localStorage.removeItem("mps_chat_session");
      
      // 2. Generate new session
      const newId = "session_" + Date.now();
      localStorage.setItem("mps_chat_session", newId);
      
      // 3. Reset State
      setState(prev => ({
        ...prev,
        messages: [],
        userInfo: {},
        hasError: false,
        isTyping: false
      }));
      setSuggestions([]);

      // 4. Reload initial welcome message
      setTimeout(() => loadInitialMessage(), 100);
    }
  };

  const handleToggleChat = () => {
  const nextOpenState = !state.isOpen;
  
  setState(prev => ({
    ...prev,
    isOpen: nextOpenState,
    isMinimized: false,
    unreadCount: nextOpenState ? 0 : prev.unreadCount
  }));

  // 🔥 THIS IS THE KEY: Tell widget.js to resize the iframe
  if (window.parent) {
    window.parent.postMessage({ 
      type: nextOpenState ? "CHAT_OPENED" : "CHAT_CLOSED" 
    }, "*");
  }
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
  if (message.toLowerCase().includes('raise') && message.toLowerCase().includes('ticket')) {
      
      // 1. Random 6-digit Case ID banao (Jaise: CAS-849302)
      const randomCaseId = "CAS-" + Math.floor(100000 + Math.random() * 900000);
      
      // 2. User ka message tayar karo
      const userMessage: ChatMessage = {
        id: `msg_${Date.now()}_user`,
        type: 'user',
        content: message,
        timestamp: new Date()
      };

      // 3. Bot ka Ticket wala reply tayar karo
      const botMessage: ChatMessage = {
        id: `msg_${Date.now()}_bot`,
        type: 'bot',
        content: `Your support ticket has been raised successfully! \n\n🎫 **Case ID: ${randomCaseId}**\n\nOur support team will contact you shortly on your registered email.`,
        timestamp: new Date()
      };

      // 4. Chat history mein dono message daal do
      setState(prev => {
        const updatedMessages = [...prev.messages, userMessage, botMessage];
        return { ...prev, messages: updatedMessages.slice(-maxMessages) };
      });

      // 5. Input khali karo aur Suggestions hata do
      setInputValue('');
      setSuggestions([]);
      
      // 🔥 SABSE ZAROORI: Return kar do taaki backend API call na ho!
      return; 
    }

  // ✅ Step A: Login detect karo aur state update karo
  if (message.includes(',')) {
    const parts = message.split(',');
    if (parts.length === 2) {
      setState(prev => ({
        ...prev,
        userInfo: { name: parts[0].trim(), email: parts[1].trim() }
      }));
    }
  }

  
  if (!message.includes(',')) {
    setSuggestions([]);
  } else {
    
    const parts = message.split(',');
    setState(prev => ({ ...prev, userInfo: { name: parts[0].trim(), email: parts[1].trim() } }));
  }

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
      if (message.includes(',') || state.userInfo?.email) {
        try {
          const newSuggestions = await chatApi.getSuggestions();
          setSuggestions(newSuggestions);
        } catch (err) {
          console.error("Suggestions nahi aayi", err);
        }
      }

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
  const handleResizeStart = (e: React.PointerEvent<HTMLDivElement>) => {
    // 🔥 Ye mouse ko drag karte waqt phisalne nahi dega (Smoothness ke liye)
    e.currentTarget.setPointerCapture(e.pointerId); 
    setIsResizing(true);
  };

  useEffect(() => {
    const handleResizeMove = (e: PointerEvent) => {
      setSize(prev => {
        // e.movementX se left drag negative hoga, minus karke width badhegi
        const newWidth = Math.min(Math.max(320, prev.width - e.movementX), 800);
        const newHeight = Math.min(Math.max(350, prev.height - e.movementY), 800);

        // 🔥 Iframe ko bol rahe hain "Main bada ho gaya, tu bhi apna size badha le!"
        if (window.parent) {
          window.parent.postMessage({ 
            type: "RESIZE_WIDGET", 
            width: newWidth, 
            height: newHeight 
          }, "*");
        }

        return { width: newWidth, height: newHeight };
      });
    };

    const handleResizeEnd = () => setIsResizing(false);

    if (isResizing) {
      window.addEventListener("pointermove", handleResizeMove);
      window.addEventListener("pointerup", handleResizeEnd);
      document.body.style.userSelect = 'none'; 
    }

    return () => {
      window.removeEventListener("pointermove", handleResizeMove);
      window.removeEventListener("pointerup", handleResizeEnd);
      document.body.style.userSelect = '';
    };
  }, [isResizing]);
  const widgetStyle = {
    position: 'fixed' as const,
    bottom: '0px', 
    right: '0px',  
    maxWidth: '100vw', // ✨ Iframe se bada nahi hoga
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'flex-end', // ✨ Hamesha Right side mein chipka rahega
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
            height: state.isMinimized ? 56 : size.height,
            maxWidth: '100%', 
            maxHeight: '85vh'
          }}
        >
          
          {!state.isMinimized && (
            <div
              onPointerDown={handleResizeStart}
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
          <div className="flex-shrink-0 flex items-center justify-between p-4 bg-primary-600 text-white rounded-t-lg">
            <div className="flex items-center space-x-2">
              <MessageCircle size={20} />
              <span className="font-medium">MPS Support Assistant</span>
              {state.hasError && (
                <AlertCircle size={16} className="text-yellow-300" />
              )}
            </div>
            <div className="flex items-center space-x-2 z-10">
              {/* Reset Button */}
              <button
                onClick={handleResetChat}
                className="p-1 hover:bg-primary-700 rounded transition-colors"
                title="Reset Conversation"
              >
                <RotateCcw size={16} />
              </button>
              
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
                   {state.messages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
                  {state.isTyping && <TypingIndicator />}
                  {/* Suggested Questions */}

                {suggestions.length > 0 && (
                    <div className="mt-4 mb-2">
                      <p className="text-xs text-gray-500 mb-2 font-semibold">Suggested Questions</p>
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