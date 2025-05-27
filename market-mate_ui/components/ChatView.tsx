
import React, { useState, useEffect, useRef } from 'react';
import { ChatSession, Message, SendMessageResponse } from '../types';
import { sendMessage } from '../services/apiService';
import MessageBubble from './MessageBubble';
import { PaperAirplaneIcon } from './Icons';
import { LoadingSpinner } from './LoadingSpinner';

interface ChatViewProps {
  session: ChatSession;
  isLoading: boolean; // Loading messages for the session
  onNewMessage: (message: Message) => void; // Callback to update parent state
}

const ChatView: React.FC<ChatViewProps> = ({ session, isLoading, onNewMessage }) => {
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [session.messages]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputMessage.trim() || isSending) return;

    const userMessage: Message = {
      id: `temp_user_${Date.now()}`, 
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString(),
      sessionId: session.id,
    };

    setIsSending(true);
    setError(null);
    onNewMessage(userMessage); 
    setInputMessage('');

    try {
      const aiResponse: SendMessageResponse = await sendMessage(session.id, userMessage.content);
      onNewMessage(aiResponse);
    } catch (err) {
      console.error('Failed to send message:', err);
      setError('Failed to get response from Market Mate. Please try again.');
    } finally {
      setIsSending(false);
      setTimeout(scrollToBottom, 100);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-neutral-900">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-neutral-700 overflow-hidden"> {/* Main chat view bg */}
      <header className="p-4 border-b border-neutral-600 bg-neutral-800"> {/* Header bg */}
        <h2 className="text-lg font-semibold text-neutral-100">
          Chat with {session.llm_model}
        </h2>
        <p className="text-xs text-neutral-400">Session ID: {session.id}</p>
      </header>

      {error && (
        <div className="p-2 bg-danger-light text-danger-hover text-sm text-center">{error}</div>
      )}

      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-neutral-900"> {/* Messages area bg */}
        {session.messages.length === 0 && (
            <div className="text-center text-neutral-500 py-10">
                No messages yet. Start the conversation!
            </div>
        )}
        {session.messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-neutral-600 bg-neutral-800"> {/* Input area bg */}
        <form onSubmit={handleSendMessage} className="flex items-center space-x-3">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message to Market Mate..."
            className="flex-1 p-3 border border-neutral-600 bg-neutral-700 text-neutral-100 rounded-lg focus:ring-2 focus:ring-primary-DEFAULT focus:border-primary-DEFAULT outline-none transition-shadow duration-150 placeholder-neutral-400"
            disabled={isSending}
          />
          <button
            type="submit"
            disabled={isSending || !inputMessage.trim()}
            className="p-3 bg-primary-DEFAULT text-neutral-100 rounded-lg hover:bg-primary-hover disabled:bg-neutral-600 disabled:text-neutral-400 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary-DEFAULT focus:ring-offset-1 focus:ring-offset-neutral-800"
            aria-label="Send message"
          >
            {isSending ? <LoadingSpinner size="sm" color="text-neutral-100" /> : <PaperAirplaneIcon className="w-5 h-5" />}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatView;