
import { API_BASE_URL } from '../constants';
import { 
  User, 
  ApiError, 
  TokenResponse, 
  RegisterRequest, 
  ChatSession, 
  SessionListItem, 
  CreateSessionResponse, 
  SendMessageResponse,
  Message,
  ApiErrorDetail
} from '../types';

const AUTH_TOKEN_KEY = 'authToken';

// Helper to get the auth token from localStorage
const getAuthToken = (): string | null => {
  return localStorage.getItem(AUTH_TOKEN_KEY);
};

// Helper to set the auth token in localStorage
const setAuthToken = (token: string): void => {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
};

// Helper to remove the auth token from localStorage
const removeAuthToken = (): void => {
  localStorage.removeItem(AUTH_TOKEN_KEY);
};

// Generic API error handler
const handleApiError = async (response: Response): Promise<ApiError> => {
  let errorData: { detail?: string | ApiErrorDetail[] } = {};
  let rawParsedJson: any;

  try {
    rawParsedJson = await response.json();
    if (rawParsedJson && typeof rawParsedJson.detail !== 'undefined') {
      errorData = rawParsedJson; 
    } else if (rawParsedJson) {
      // If no .detail field, but got JSON, the whole thing might be the detail.
      errorData = { detail: rawParsedJson as any };
    } else {
      errorData = { detail: `HTTP error ${response.status}: ${response.statusText || 'Empty error response'}` };
    }
  } catch (e) {
    // JSON parsing failed
    errorData = { detail: `HTTP error ${response.status}: ${response.statusText || 'Server error (non-JSON response)'}` };
  }
  
  let finalDetail: string | ApiErrorDetail[];
  if (typeof errorData.detail === 'string') {
    finalDetail = errorData.detail;
  } else if (Array.isArray(errorData.detail) && errorData.detail.every(item => typeof item === 'object' && item !== null && 'msg' in item && 'type' in item)) {
    finalDetail = errorData.detail as ApiErrorDetail[];
  } else if (errorData.detail) { 
    try {
      finalDetail = JSON.stringify(errorData.detail);
    } catch (stringifyError) {
      finalDetail = 'Error detail could not be stringified.';
    }
  } else { 
    finalDetail = `HTTP error ${response.status}: An unspecified error occurred.`;
  }

  console.error('API Error:', finalDetail, 'Status:', response.status, 'Original Parsed Data:', rawParsedJson);
  return { detail: finalDetail, status: response.status };
};


// Unified request function
const request = async <T>(
  endpoint: string,
  method: string = 'GET',
  body?: any,
  isFormData: boolean = false,
  isAuthenticatedRequest: boolean = true 
): Promise<T> => {
  const headers: HeadersInit = {};
  
  if (isAuthenticatedRequest) {
    const token = getAuthToken(); 
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  // Only set Content-Type for requests that actually have a body and are not FormData
  if (body && !isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  const config: RequestInit = {
    method,
    headers,
    credentials: 'include', 
  };

  if (body) {
    config.body = isFormData ? body : JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const apiError = await handleApiError(response);
    throw apiError;
  }

  if (response.status === 204) { 
    return null as T; 
  }
  
  const text = await response.text();
  if (!text) { 
    return null as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (e) {
    console.warn(`Non-JSON response for ${method} ${endpoint} (status ${response.status}):`, text);
    return text as any as T; 
  }
};

// Authentication
export const loginUser = async (formData: URLSearchParams): Promise<void> => {
  await request<null>('/auth/jwt/login', 'POST', formData, true, false);
};

export const registerUser = async (userData: RegisterRequest): Promise<User> => {
  return request<User>('/auth/register', 'POST', userData, false, false);
};

export const getCurrentUser = async (): Promise<User | null> => {
  try {
    const user = await request<User | null>('/users/me', 'GET', undefined, false, true);
    return user; 
  } catch (error) {
    const apiError = error as ApiError;
    if (apiError.status === 401) { 
        removeAuthToken(); 
    }
    console.warn('Failed to get current user (may indicate no active session, invalid cookie, or API error):', apiError.detail, 'Status:', apiError.status);
    return null;
  }
};

export const logoutUser = async (): Promise<void> => {
  try {
    await request<any>('/auth/jwt/logout', 'POST', {}, false, true);
  } catch (error) {
    const apiError = error as ApiError;
    console.error("Error during backend logout:", apiError.detail, 'Status:', apiError.status);
  } finally {
    removeAuthToken(); 
  }
};


// Chat Sessions
export const getSessions = async (): Promise<SessionListItem[]> => {
  const sessions = await request<SessionListItem[] | null>('/chat/sessions/', 'GET');
  return sessions || []; 
};

export const createSession = async (llm_model: string): Promise<CreateSessionResponse> => {
  return request<CreateSessionResponse>('/chat/create_session/', 'POST', { llm_model });
};

export const getSessionDetails = async (sessionId: string): Promise<ChatSession> => {
  return request<ChatSession>(`/chat/sessions/${sessionId}`, 'GET');
};

export const deleteSession = async (sessionId: string): Promise<void> => {
  await request<null>(`/chat/sessions/${sessionId}`, 'DELETE');
};

// Messages
export const sendMessage = async (sessionId: string, content: string): Promise<SendMessageResponse> => {
  const encodedContent = encodeURIComponent(content);
  const endpoint = `/chat/message/${sessionId}?message=${encodedContent}`;
  // The message content is now in the URL query parameter.
  // The body of the POST request should be empty or undefined.
  return request<SendMessageResponse>(endpoint, 'POST', undefined, false, true);
};
