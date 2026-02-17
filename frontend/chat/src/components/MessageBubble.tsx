import React from 'react';
import { User, Bot, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { ChatMessage } from '../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isBot = message.type === 'bot';

  const formatTime = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const renderBotMessageContent = (content: string) => {
    // Split content by newlines and render with proper spacing
    const lines = content.split('\n');
    return lines.map((line, index) => (
      <React.Fragment key={index}>
        {line}
        {index < lines.length - 1 && <br />}
      </React.Fragment>
    ));
  };

  const getConfidenceColor = (score?: number) => {
    if (!score) return '';
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getConfidenceLabel = (score?: number) => {
    if (!score) return '';
    if (score >= 0.8) return 'High confidence';
    if (score >= 0.6) return 'Medium confidence';
    return 'Low confidence';
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`flex max-w-xs lg:max-w-md ${isUser ? 'flex-row-reverse' : 'flex-row'} items-end space-x-2`}>
        {/* Avatar */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser 
            ? 'bg-primary-600 text-white' 
            : 'bg-gray-200 text-gray-600'
        }`}>
          {isUser ? <User size={16} /> : <Bot size={16} />}
        </div>

        {/* Message Content */}
        <div className={`px-4 py-2 rounded-lg ${
          isUser 
            ? 'bg-primary-600 text-white rounded-br-none' 
            : 'bg-white border border-gray-200 text-gray-800 rounded-bl-none'
        } shadow-sm`}>
          {/* Message Text */}
          <div className="text-sm leading-relaxed">
            {isBot ? renderBotMessageContent(message.content) : message.content}
          </div>

          {/* Bot Message Metadata */}
          {isBot && (
            <div className="mt-2 space-y-1">
              {/* Confidence Score */}
              {message.confidence_score && (
                <div className="flex items-center space-x-1 text-xs">
                  <CheckCircle size={12} className={getConfidenceColor(message.confidence_score)} />
                  <span className={`${getConfidenceColor(message.confidence_score)} font-medium`}>
                    {getConfidenceLabel(message.confidence_score)}
                  </span>
                  <span className="text-gray-500">
                    ({(message.confidence_score * 100).toFixed(1)}%)
                  </span>
                </div>
              )}

              {/* Case ID for Escalated Messages */}
              {message.case_id && (
                <div className="flex items-center space-x-1 text-xs">
                  <AlertTriangle size={12} className="text-orange-500" />
                  <span className="text-gray-600">Case ID:</span>
                  <span className="font-mono text-orange-600 font-medium">
                    {message.case_id}
                  </span>
                  <button
                    onClick={() => {
                      // Copy case ID to clipboard
                      navigator.clipboard.writeText(message.case_id || '').then(() => {
                        // Could show a toast notification here
                        console.log('Case ID copied to clipboard');
                      }).catch(err => {
                        console.error('Failed to copy case ID:', err);
                      });
                    }}
                    className="text-gray-400 hover:text-gray-600 transition-colors cursor-pointer"
                    title="Copy Case ID"
                  >
                    <ExternalLink size={10} />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Timestamp */}
          <div className={`text-xs mt-1 ${
            isUser ? 'text-primary-200' : 'text-gray-500'
          }`}>
            {formatTime(message.timestamp)}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;