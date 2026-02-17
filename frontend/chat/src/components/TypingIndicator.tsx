import React from 'react';
import { Bot } from 'lucide-react';

const TypingIndicator: React.FC = () => {
  return (
    <div className="flex justify-start animate-fade-in">
      <div className="flex items-end space-x-2 max-w-xs">
        {/* Bot Avatar */}
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center">
          <Bot size={16} />
        </div>

        {/* Typing Animation */}
        <div className="bg-white border border-gray-200 rounded-lg rounded-bl-none px-4 py-3 shadow-sm">
          <div className="flex items-center space-x-1">
            <div className="text-gray-500 text-sm mr-2">MPS Assistant is typing</div>
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;