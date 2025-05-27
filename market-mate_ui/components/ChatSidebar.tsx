
import React from 'react';
import { SessionListItem } from '../types';
import { useAuth } from '../App';
import { PlusCircleIcon, UserCircleIcon, ArrowRightOnRectangleIcon, TrashIcon, ChatBubbleLeftRightIcon } from './Icons';
import { LoadingSpinner } from './LoadingSpinner';

interface ChatSidebarProps {
  sessions: SessionListItem[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onCreateNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  isLoading: boolean;
  currentUserEmail: string;
}

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateNewSession,
  onDeleteSession,
  isLoading,
  currentUserEmail,
}) => {
  const { logout, user } = useAuth();

  const handleLogout = async () => {
    if (window.confirm('Are you sure you want to log out?')) {
      await logout();
    }
  };

  return (
    <div className="w-72 bg-neutral-800 text-neutral-100 flex flex-col h-full shadow-lg">
      <div className="p-4 border-b border-neutral-700">
        <div className="flex items-center space-x-2 mb-4">
            <ChatBubbleLeftRightIcon className="w-8 h-8 text-primary-light" /> {/* Use a lighter primary for icon if primary.DEFAULT is darkish gray */}
            <h1 className="text-xl font-semibold text-neutral-100">Market Mate</h1>
        </div>
        <button
          onClick={onCreateNewSession}
          className="w-full flex items-center justify-center space-x-2 bg-primary-DEFAULT hover:bg-primary-hover text-neutral-100 font-medium py-2.5 px-4 rounded-lg transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-light"
        >
          <PlusCircleIcon className="w-5 h-5" />
          <span>New Chat</span>
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {isLoading && <div className="flex justify-center p-4"><LoadingSpinner color="text-neutral-100"/></div>}
        {!isLoading && sessions.length === 0 && (
          <p className="text-center text-neutral-400 p-4 text-sm">No chat sessions yet. Create one to get started!</p>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`group flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors duration-150 ease-in-out
                        ${activeSessionId === session.id ? 'bg-primary-DEFAULT text-neutral-100' : 'hover:bg-neutral-700 text-neutral-200'}`}
            onClick={() => onSelectSession(session.id)}
          >
            <div className="flex-1 overflow-hidden">
                <p className="text-sm font-medium truncate">{session.title || `Chat ${session.id.substring(0, 8)}`}</p>
                <p className={`text-xs ${activeSessionId === session.id ? 'text-neutral-300' : 'text-neutral-400 group-hover:text-neutral-300'}`}>
                    Model: {session.llm_model}
                </p>
            </div>
            <button
                onClick={(e) => {
                    e.stopPropagation(); 
                    if (window.confirm(`Are you sure you want to delete chat "${session.title || session.id}"?`)) {
                        onDeleteSession(session.id);
                    }
                }}
                className={`ml-2 p-1 rounded hover:bg-danger-DEFAULT text-neutral-400 hover:text-white opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity duration-150
                           ${activeSessionId === session.id ? 'opacity-100 text-neutral-300 hover:bg-red-400 hover:text-white' : ''} `}
                aria-label="Delete session"
            >
                <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-neutral-700">
        <div className="flex items-center space-x-3 mb-3">
          <UserCircleIcon className="w-8 h-8 text-neutral-400" />
          <div>
            <p className="text-sm font-medium text-neutral-100 truncate">{user?.full_name || currentUserEmail}</p>
            <p className="text-xs text-neutral-400">Online</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center space-x-2 bg-neutral-700 hover:bg-neutral-600 text-neutral-100 font-medium py-2 px-4 rounded-lg transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-neutral-500"
        >
          <ArrowRightOnRectangleIcon className="w-5 h-5" />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export default ChatSidebar;