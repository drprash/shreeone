import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { toast } from 'react-hot-toast';
import { Lock, Mail, Key, Fingerprint } from 'lucide-react';
import { isWebAuthnSupported, isPlatformAuthenticatorAvailable, authenticateWithPasskey } from '../services/webauthn';

const extractLoginErrorMessage = (error) => {
  const detail = error?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const firstItem = detail[0];
    if (typeof firstItem === 'string' && firstItem.trim()) {
      return firstItem;
    }
    if (firstItem && typeof firstItem === 'object') {
      const firstItemMessage = firstItem.msg || firstItem.message;
      if (typeof firstItemMessage === 'string' && firstItemMessage.trim()) {
        return firstItemMessage;
      }
    }
  }

  return 'Login failed';
};

const Login = () => {
  const navigate = useNavigate();
  const { setAuth, hasPasskey, passkeyUserId } = useAuthStore();
  const [showSetPasswordMode, setShowSetPasswordMode] = useState(false);
  const [setupToken, setSetupToken] = useState('');
  const [platformAuthAvailable, setPlatformAuthAvailable] = useState(false);
  const [isBiometricPending, setIsBiometricPending] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm();

  useEffect(() => {
    if (hasPasskey && isWebAuthnSupported()) {
      isPlatformAuthenticatorAvailable().then(setPlatformAuthAvailable);
    }
  }, [hasPasskey]);

  const mutation = useMutation({
    mutationFn: (data) => api.post('/auth/login', data),
    onSuccess: (response) => {
      setAuth(response.data);
      toast.success('Welcome back!');
      navigate('/');
    },
    onError: (error) => {
      const detail = extractLoginErrorMessage(error);
      const normalizedDetail = detail.toLowerCase();

      if (normalizedDetail.includes('set your password') || normalizedDetail.includes('activation token')) {
        toast.error('You need to set your password first with your activation token');
        setShowSetPasswordMode(true);
      } else if (normalizedDetail.includes('invalid credentials')) {
        toast.error('Wrong username or password');
      } else {
        toast.error(detail);
      }
    }
  });

  const onSubmit = (data) => {
    mutation.mutate(data);
  };

  const handleSetPasswordWithToken = () => {
    if (!setupToken.trim()) {
      toast.error('Please enter your activation token');
      return;
    }
    navigate(`/set-password?token=${encodeURIComponent(setupToken)}`);
  };

  const handleBiometricLogin = async () => {
    if (!passkeyUserId) return;
    setIsBiometricPending(true);
    try {
      const tokenData = await authenticateWithPasskey(passkeyUserId);
      setAuth(tokenData);
      toast.success('Welcome back!');
      navigate('/');
    } catch (err) {
      toast.error(err.message || 'Biometric authentication failed');
    } finally {
      setIsBiometricPending(false);
    }
  };

  const showBiometricButton = hasPasskey && platformAuthAvailable && passkeyUserId;

  return (
    <div>
      <h2 className="text-2xl font-bold text-center mb-6">Sign In</h2>

      {showSetPasswordMode ? (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-slate-700">
            <p className="font-semibold mb-2">👋 New Member?</p>
            <p>If you were just added to the family, you'll receive an activation token. Use it below to set your password.</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Activation Token
            </label>
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                value={setupToken}
                onChange={(e) => setSetupToken(e.target.value)}
                className="w-full pl-10 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Paste your activation token here"
              />
            </div>
          </div>

          <button
            onClick={handleSetPasswordWithToken}
            className="w-full bg-green-600 text-white py-2 rounded-lg hover:bg-green-700 font-medium"
          >
            Set Password
          </button>

          <button
            onClick={() => setShowSetPasswordMode(false)}
            className="w-full bg-slate-200 text-slate-700 py-2 rounded-lg hover:bg-slate-300 font-medium"
          >
            Back to Sign In
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {showBiometricButton && (
            <>
              <button
                type="button"
                onClick={handleBiometricLogin}
                disabled={isBiometricPending}
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 text-white py-3 rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium text-base"
              >
                <Fingerprint className="w-5 h-5" />
                {isBiometricPending ? 'Authenticating…' : 'Sign in with biometrics'}
              </button>
              <div className="flex items-center gap-3 text-slate-400 text-sm">
                <div className="flex-1 border-t border-slate-200 dark:border-slate-700" />
                <span>or sign in with password</span>
                <div className="flex-1 border-t border-slate-200 dark:border-slate-700" />
              </div>
            </>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  {...register('email', { required: 'Email is required' })}
                  type="email"
                  className="w-full pl-10 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="you@example.com"
                />
              </div>
              {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  {...register('password', { required: 'Password is required' })}
                  type="password"
                  className="w-full pl-10 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="••••••••"
                />
              </div>
              {errors.password && <p className="text-red-500 text-sm mt-1">{errors.password.message}</p>}
            </div>

            <button
              type="submit"
              disabled={mutation.isPending}
              className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {mutation.isPending ? 'Signing in...' : 'Sign In'}
            </button>

            <button
              type="button"
              onClick={() => setShowSetPasswordMode(true)}
              className="w-full text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Set password with activation token?
            </button>

            <div className="border-t pt-4">
              <Link
                to="/forgot-password"
                className="block w-full text-center text-slate-600 hover:text-slate-900 text-sm font-medium py-2 hover:bg-slate-50 rounded-lg transition-colors"
              >
                Forgot your password?
              </Link>
            </div>
          </form>
        </div>
      )}

      <p className="text-center mt-4 text-gray-600">
        Creating a new family?{' '}
        <Link to="/register" className="text-blue-600 hover:underline">
          Create Family Admin Account
        </Link>
      </p>
      <p className="text-center mt-2 text-xs text-gray-500">
        Member accounts are created by your Family Admin from Settings.
      </p>
    </div>
  );
};

export default Login;
