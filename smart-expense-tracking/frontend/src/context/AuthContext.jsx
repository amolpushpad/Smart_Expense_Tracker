import { createContext, useContext, useEffect, useState } from 'react';
import { api, ensureCsrfToken, setCsrfToken } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refreshProfile = async () => {
    const response = await api.get('/auth/me');
    setUser(response.data.data.user);
    return response.data.data.user;
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await ensureCsrfToken();
        const response = await api.get('/auth/me');
        if (mounted) setUser(response.data.data.user);
      } catch (bootstrapError) {
        if (mounted) {
          setUser(null);
          if (bootstrapError.response?.status !== 401) {
            setError(bootstrapError.response?.data?.message || 'Unable to reach the server. Check that the backend is running.');
          }
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const login = async (email, password, remember = false) => {
    setError('');
    try {
      const response = await api.post('/auth/login', { email, password, remember });
      setCsrfToken(response.data.data.csrf_token);
      setUser(response.data.data.user);
      return response.data.data.user;
    } catch (requestError) {
      setError(requestError.response?.data?.message || 'Unable to reach the server. Check that the backend is running.');
      throw requestError;
    }
  };

  const register = async (name, email, password) => {
    setError('');
    try {
      return await api.post('/auth/register', { name, email, password });
    } catch (requestError) {
      setError(requestError.response?.data?.message || 'Unable to reach the server. Check that the backend is running.');
      throw requestError;
    }
  };

  const logout = async () => {
    try {
      const response = await api.post('/auth/logout');
      setCsrfToken(response.data.data.csrf_token);
      setUser(null);
      return true;
    } catch (requestError) {
      setError(requestError.response?.data?.message || 'Could not contact the server to end the session.');
      return false;
    }
  };

  const clearError = () => setError('');
  return <AuthContext.Provider value={{ user, loading, error, login, register, logout, refreshProfile, clearError }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
