
import React, { useState, useEffect, useCallback } from 'react';
import ChatSidebar from './ChatSidebar';
import ChatView from './ChatView';
import { ChatSession, SessionListItem, Message, CreateSessionResponse } from '../types';
import { getSessions, createSession, getSessionDetails, deleteSession as apiDeleteSession } from '../services/apiService';
import { useAuth } from '../App';
import { DEFAULT_LLM_MODEL } from '../constants';
import { LoadingSpinner } from './LoadingSpinner';

const ChatPage: React.FC = () => {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();

  const fetchSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setError(null);
    try {
      const fetchedSessions = await getSessions();
      fetchedSessions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setSessions(fetchedSessions.map(s => ({...s, title: s.title || s.id.substring(0,8) + "..."}))); 
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
      setError('Failed to load chat sessions.');
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleSelectSession = useCallback(async (sessionId: string) => {
    if (activeSession?.id === sessionId && activeSession.messages.length > 0) return; 

    setIsLoadingMessages(true);
    setError(null);
    try {
      const sessionDetails = await getSessionDetails(sessionId);
      sessionDetails.messages.sort((a,b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
      setActiveSession(sessionDetails);
    } catch (err) {
      console.error('Failed to load session details:', err);
      setError(`Failed to load messages for session ${sessionId}.`);
      setActiveSession(null); 
    } finally {
      setIsLoadingMessages(false);
    }
  }, [activeSession]);

  const handleCreateNewSession = async () => {
    setIsLoadingMessages(true); 
    setError(null);
    try {
      const newSessionData: CreateSessionResponse = await createSession(DEFAULT_LLM_MODEL);
      const newSessionListItem: SessionListItem = { 
        id: newSessionData.id, 
        llm_model: newSessionData.llm_model, 
        created_at: newSessionData.created_at,
        title: `New Chat (${newSessionData.id.substring(0,4)}...)`
      };
      setSessions(prev => [newSessionListItem, ...prev]); 
      setActiveSession({
        id: newSessionData.id,
        llm_model: newSessionData.llm_model,
        created_at: newSessionData.created_at,
        messages: [] 
      });
    } catch (err) {
      console.error('Failed to create new session:', err);
      setError('Failed to create new session.');
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    const optimisticSessions = sessions.filter(s => s.id !== sessionId);
    setSessions(optimisticSessions);
    if (activeSession?.id === sessionId) {
      setActiveSession(null);
    }
    try {
      await apiDeleteSession(sessionId);
    } catch (err) {
      console.error('Failed to delete session:', err);
      setError(`Failed to delete session ${sessionId}. Reverting.`);
      fetchSessions(); 
    }
  };
  
  const handleNewMessage = (message: Message) => {
    if (activeSession) {
      const updatedMessages = [...activeSession.messages, message];
      updatedMessages.sort((a,b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

      const isFirstUserMessageInUpdatedSession = message.role === 'user' && 
                                            updatedMessages.filter(m => m.role === 'user').length === 1;

      setActiveSession(prev => prev ? { ...prev, messages: updatedMessages } : null);

      if (isFirstUserMessageInUpdatedSession) {
        const newTitle = message.content.substring(0, 25) + (message.content.length > 25 ? '...' : '');
        setSessions(prevSessions => prevSessions.map(s => 
            s.id === activeSession.id ? {...s, title: newTitle} : s
        ));
      }
    }
  };


  if (!user) return <LoadingSpinner size="lg"/>; 

  return (
    <div className="flex h-screen overflow-hidden bg-neutral-900">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSession?.id || null}
        onSelectSession={handleSelectSession}
        onCreateNewSession={handleCreateNewSession}
        onDeleteSession={handleDeleteSession}
        isLoading={isLoadingSessions}
        currentUserEmail={user.email}
      />
      <main className="flex-1 flex flex-col overflow-hidden">
        {error && (
          <div className="p-4 bg-danger-light text-danger-hover text-center">{error}</div>
        )}
        {activeSession ? (
          <ChatView
            session={activeSession}
            isLoading={isLoadingMessages}
            onNewMessage={handleNewMessage}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-neutral-500 text-lg p-8">
            {isLoadingSessions || isLoadingMessages ? <LoadingSpinner size="lg"/> : "Select a chat to start, or create a new one."}
          </div>
        )}
      </main>
    </div>
  );
};

export default ChatPage;