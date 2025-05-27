
import React, { useState } from 'react';
import { useAuth } from '../App';
import { loginUser, registerUser, getCurrentUser } from '../services/apiService';
import { User, ApiError, RegisterRequest, ApiErrorDetail } from '../types';
import { LockClosedIcon, UserCircleIcon, ChatBubbleLeftRightIcon } from './Icons';
import { LoadingSpinner } from './LoadingSpinner';
import { API_BASE_URL } from '../constants';


const AuthPage: React.FC = () => {
  const [isLoginView, setIsLoginView] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      if (isLoginView) {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);
        
        await loginUser(formData); 

        const currentUser = await getCurrentUser(); 
        if (currentUser) {
          login(currentUser); 
        } else {
          setError("Login call succeeded, but failed to retrieve user details. Please ensure your browser accepts cookies from the server and check CORS settings if the API is on a different domain.");
        }
      } else {
        const registerData: RegisterRequest = { email, password, full_name: fullName || undefined };
        const registeredUser = await registerUser(registerData);
        setIsLoginView(true);
        setEmail(registeredUser.email); 
        setPassword('');
        setFullName('');
        alert('Registration successful! Please log in.');
      }
    } catch (err) {
      const apiError = err as ApiError;
      if (typeof apiError.detail === 'string') {
        setError(apiError.detail);
      } else if (Array.isArray(apiError.detail)) {
        setError(apiError.detail.map((d: ApiErrorDetail) => d.msg).join(', '));
      } else {
        setError(isLoginView ? 'Login failed. Please check your credentials or server logs.' : 'Registration failed. Please try again or check server logs.');
      }
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-neutral-800 via-neutral-900 to-black p-4">
      <div className="bg-neutral-800 p-8 rounded-xl shadow-2xl w-full max-w-md transform transition-all duration-500 hover:scale-105">
        <div className="flex justify-center mb-6">
          <ChatBubbleLeftRightIcon className="w-16 h-16 text-primary-DEFAULT" />
        </div>
        <h2 className="text-3xl font-bold text-center text-neutral-100 mb-2">
          Market Mate
        </h2>
        <p className="text-center text-neutral-300 mb-8">
          {isLoginView ? 'Welcome back!' : 'Create your account'}
        </p>

        {error && (
          <div className="bg-danger-light border-l-4 border-danger-DEFAULT text-danger-hover p-4 mb-6 rounded-md" role="alert">
            <p className="font-bold">Error</p>
            <p>{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {!isLoginView && (
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-neutral-300">
                Full Name (Optional)
              </label>
              <div className="mt-1 relative rounded-md shadow-sm">
                 <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <UserCircleIcon className="h-5 w-5 text-neutral-500" />
                  </div>
                <input
                  id="fullName"
                  name="fullName"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your Full Name"
                  className="appearance-none block w-full px-3 py-3 pl-10 border border-neutral-600 bg-neutral-700 text-neutral-100 rounded-md placeholder-neutral-500 focus:outline-none focus:ring-primary-DEFAULT focus:border-primary-DEFAULT sm:text-sm"
                />
              </div>
            </div>
          )}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-neutral-300">
              Email address
            </label>
            <div className="mt-1 relative rounded-md shadow-sm">
               <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-neutral-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
                  <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
                </svg>
              </div>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="appearance-none block w-full px-3 py-3 pl-10 border border-neutral-600 bg-neutral-700 text-neutral-100 rounded-md placeholder-neutral-500 focus:outline-none focus:ring-primary-DEFAULT focus:border-primary-DEFAULT sm:text-sm"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-neutral-300">
              Password
            </label>
             <div className="mt-1 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <LockClosedIcon className="h-5 w-5 text-neutral-500" />
                </div>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete={isLoginView ? "current-password" : "new-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="appearance-none block w-full px-3 py-3 pl-10 border border-neutral-600 bg-neutral-700 text-neutral-100 rounded-md placeholder-neutral-500 focus:outline-none focus:ring-primary-DEFAULT focus:border-primary-DEFAULT sm:text-sm"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-neutral-100 bg-primary-DEFAULT hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-DEFAULT disabled:bg-neutral-700 disabled:text-neutral-400"
            >
              {isLoading ? <LoadingSpinner size="sm" color="text-neutral-100" /> : (isLoginView ? 'Sign in' : 'Create account')}
            </button>
          </div>
        </form>

        <p className="mt-8 text-center text-sm text-neutral-400">
          {isLoginView ? "Don't have an account? " : 'Already have an account? '}
          <button
            onClick={() => { 
              setIsLoginView(!isLoginView); 
              setError(null); 
              setEmail(''); 
              setPassword('');
              setFullName('');
            }}
            className="font-medium text-primary-light hover:text-primary-DEFAULT"
          >
            {isLoginView ? 'Sign up' : 'Sign in'}
          </button>
        </p>
        <p className="mt-4 text-xs text-center text-neutral-600">API Base: {API_BASE_URL}</p>
      </div>
    </div>
  );
};

export default AuthPage;