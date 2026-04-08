import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Bot, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { ChatMessage } from '../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

interface DetailDropdownProps {
  content: string;
}

const DetailDropdown: React.FC<DetailDropdownProps> = ({ content }) => {
  const [open, setOpen] = useState(false);
  
  // Extract images from content
  const imageRegex = /\[IMAGE_REF:(https?:\/\/[^\]]+)\]/g;
  const images: string[] = [];
  let match;
  while ((match = imageRegex.exec(content)) !== null) {
    images.push(match[1]);
  }
  
  // Remove image markers from text content
  const textContent = content.replace(imageRegex, '').trim();
  
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="text-blue-600 underline text-xs"
      >
        {open ? 'Hide Details' : 'Show Details'}
      </button>
      {open && (
        <div className="mt-1 text-sm prose prose-slate max-w-none border-l-2 border-gray-200 pl-2">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {textContent}
          </ReactMarkdown>
          {images.length > 0 && (
            <div className="mt-3 space-y-2">
              {images.map((url, idx) => (
                <img
                  key={idx}
                  src={url}
                  alt={`Reference ${idx + 1}`}
                  className="max-w-full rounded border border-gray-200 shadow-sm"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isBot = message.type === 'bot';

  const formatTime = (timestamp: Date) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getConfidenceColor = (score?: number) => {
    if (!score) return 'text-gray-400';
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  // Split short and detailed answers
  let shortAnswer = message.content;
  let detailedAnswer = '';
  const shortImages: string[] = [];
  
  if (isBot && message.content.includes('DETAILED_ANSWER:')) {
    const parts = message.content.split('DETAILED_ANSWER:');
    shortAnswer = parts[0].replace('SHORT_ANSWER:', '').trim();
    detailedAnswer = parts[1].trim();
  }
  
  // Extract images from short answer
  const imageRegex = /\[IMAGE_REF:(https?:\/\/[^\]]+)\]/g;
  let match;
  while ((match = imageRegex.exec(shortAnswer)) !== null) {
    shortImages.push(match[1]);
  }
  
  // Remove image markers from short answer text
  shortAnswer = shortAnswer.replace(imageRegex, '').trim();

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 animate-fade-in`}>
      <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start gap-2`}>

        {/* Avatar */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-sm ${
          isUser ? 'bg-emerald-600 text-white' : 'bg-white border border-gray-200 text-gray-600'
        }`}>
          {isUser ? <User size={16} /> : <Bot size={16} />}
        </div>

        {/* Message Container */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
          <div className={`px-4 py-2 rounded-2xl shadow-sm break-words ${
            isUser
              ? 'bg-emerald-600 text-white rounded-tr-none'
              : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none'
          }`}>

            {/* SHORT_ANSWER */}
            <div className="text-sm leading-relaxed prose prose-slate max-w-none overflow-wrap-anywhere">
              {isBot ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    ul: ({node, ...props}) => <ul className="list-disc ml-4 my-2" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal ml-4 my-2" {...props} />,
                    li: ({node, ...props}) => <li className="mb-1" {...props} />,
                    strong: ({node, ...props}) => <span className="font-bold text-indigo-900" {...props} />,
                    a: ({node, ...props}) => <a className="text-blue-600 underline break-all" target="_blank" rel="noreferrer" {...props} />
                  }}
                >
                  {shortAnswer}
                </ReactMarkdown>
              ) : (
                <p className="whitespace-pre-wrap break-words">{shortAnswer}</p>
              )}
            </div>

            {/* Images in SHORT_ANSWER */}
            {isBot && shortImages.length > 0 && (
              <div className="mt-2 space-y-2">
                {shortImages.map((url, idx) => (
                  <img
                    key={idx}
                    src={url}
                    alt={`Reference ${idx + 1}`}
                    className="max-w-full rounded border border-gray-200 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => window.open(url, '_blank')}
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ))}
              </div>
            )}

            {/* DETAILED_ANSWER Dropdown */}
            {isBot && detailedAnswer && <DetailDropdown content={detailedAnswer} />}

            {/* Metadata (Confidence & Case ID) */}
            {isBot && (message.confidence_score || message.case_id) && (
              <div className="mt-3 pt-2 border-t border-gray-50 space-y-1">
                {message.confidence_score && (
                  <div className="flex items-center gap-1 text-[10px]">
                    <CheckCircle size={10} className={getConfidenceColor(message.confidence_score)} />
                    <span className={`${getConfidenceColor(message.confidence_score)} font-semibold uppercase tracking-wider`}>
                      {message.confidence_score >= 0.8 ? 'High Confidence' : 'AI Response'}
                      ({(message.confidence_score * 100).toFixed(0)}%)
                    </span>
                  </div>
                )}
                {message.case_id && (
                  <div className="flex items-center gap-1 text-[10px] bg-orange-50 p-1 rounded">
                    <AlertTriangle size={10} className="text-orange-600" />
                    <span className="text-orange-700 font-medium tracking-tight">CASE: {message.case_id}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Timestamp */}
          <span className="text-[10px] text-gray-400 mt-1 px-1">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;