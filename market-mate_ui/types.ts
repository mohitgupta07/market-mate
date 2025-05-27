
export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_verified?: boolean;
}

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg: string;
  type: string;
}
export interface ApiError {
  detail?: string | ApiErrorDetail[];
  status?: number; // Added to include HTTP status code
}

export interface Message {
  id: string; // Can be client-generated for optimistic updates, or server ID
  role: 'user' | 'assistant';
  content: string;
  timestamp: string; // ISO string
  sessionId?: string; // Optional, if messages are stored flat and associated later
}

export interface ChatSession {
  id: string;
  llm_model: string;
  created_at: string;
  user_id?: string; // Optional, might be implicit
  // Assuming 'messages' array comes from GET /chat/sessions/{id}
  messages: Message[]; 
  title?: string; // For display, can be derived
}

// For POST /chat/message/{session_id} response.
// Assuming it returns the AI's message object.
export interface SendMessageResponse extends Message {
  // any other fields the API might return for a message
}

// For POST /chat/create_session response
export interface CreateSessionResponse {
   id: string;
   llm_model: string;
   created_at: string;
   user_id: string; 
   // FastAPI often returns the created object
}

// For GET /chat/sessions response (list of sessions)
export interface SessionListItem {
  id: string;
  llm_model: string;
  created_at: string;
  title?: string; // Derived or from API (e.g. first message snippet)
  // might also include a snippet of the last message or number of messages
}

// For /auth/jwt/login
export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// For /auth/register
export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
  is_active?: boolean; // Defaults usually handled by backend
  is_superuser?: boolean; // Defaults usually handled by backend
  is_verified?: boolean; // Defaults usually handled by backend
}