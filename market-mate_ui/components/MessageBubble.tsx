
import React from 'react';
import { Message } from '../types';
import { UserCircleIcon } from './Icons'; 

const BotIcon: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" {...props}>
        <path fillRule="evenodd" d="M4.5 3.75a3 3 0 00-3 3v10.5a3 3 0 003 3h15a3 3 0 003-3V6.75a3 3 0 00-3-3h-15zm4.125 3.375a.75.75 0 000 1.5h6.75a.75.75 0 000-1.5h-6.75zm0 3.75a.75.75 0 000 1.5h6.75a.75.75 0 000-1.5h-6.75zm0 3.75a.75.75 0 000 1.5h6.75a.75.75 0 000-1.5h-6.75z" clipRule="evenodd" />
    </svg>
);


const MessageBubble: React.FC<{ message: Message }> = ({ message }) => {
  const isUser = message.role === 'user';

  const formattedTimestamp = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} group`}>
      <div className={`flex items-end space-x-2 max-w-xs md:max-w-md lg:max-w-lg ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
        {isUser ? (
          <UserCircleIcon className="w-6 h-6 text-neutral-500 self-start mt-1" />
        ) : (
          <BotIcon className="w-6 h-6 text-neutral-400 self-start mt-1" /> // Changed BotIcon color
        )}
        <div
          className={`px-4 py-3 rounded-xl shadow-md ${
            isUser 
              ? 'bg-primary-DEFAULT text-neutral-100 rounded-br-none' 
              : 'bg-secondary-light text-neutral-100 rounded-bl-none' // AI message background from new theme
          }`}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
         <p className={`text-xs text-neutral-500 mt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${isUser ? 'text-right mr-1' : 'text-left ml-1'}`}>
            {formattedTimestamp}
          </p>
      </div>
    </div>
  );
};

export default MessageBubble;