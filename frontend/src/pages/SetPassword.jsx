import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { toast } from 'react-hot-toast';
import { Lock, Mail } from 'lucide-react';

const STRENGTH_LEVELS = [
  { label: 'Weak',   bar: 'bg-red-500',    text: 'text-red-600'    },
  { label: 'Fair',   bar: 'bg-orange-400', text: 'text-orange-500' },
  { label: 'Good',   bar: 'bg-yellow-400', text: 'text-yellow-600' },
  { label: 'Strong', bar: 'bg-green-500',  text: 'text-green-600'  },
];

const getPasswordStrength = (pwd) => {
  if (!pwd) return null;
  let score = 0;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[a-z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  return { score, ...STRENGTH_LEVELS[score - 1] };
};

const SetPassword = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const [tokenInfo, setTokenInfo] = useState(null);
  const [verifyingToken, setVerifyingToken] = useState(true);
  const [tokenError, setTokenError] = useState(null);
  
  const token = searchParams.get('token');
  const { register, handleSubmit, formState: { errors }, watch } = useForm();
  const password = watch('password');
  const strength = getPasswordStrength(password);

  React.useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setTokenError('No activation token provided');
        setVerifyingToken(false);
        return;
      }

      try {
        const response = await api.post('/auth/verify-activation-token', null, {
          params: { token }
        });

        if (response.data.valid) {
          setTokenInfo({
            email: response.data.user_email,
            expiresAt: response.data.expires_at
          });
          setTokenError(null);
        } else {
          setTokenError('Activation token is invalid or expired');
        }
      } catch (err) {
        setTokenError('Failed to verify activation token');
      } finally {
        setVerifyingToken(false);
      }
    };

    verifyToken();
  }, [token]);

  const mutation = useMutation({
    mutationFn: (data) => api.post('/auth/set-password', {
      activation_token: token,
      password: data.password
    }),
    onSuccess: (response) => {
      setAuth(response.data);
      toast.success('Password set successfully!');
      navigate('/');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to set password');
    }
  });

  const onSubmit = (data) => {
    mutation.mutate(data);
  };

  if (verifyingToken) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (tokenError) {
    return (
      <div>
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-slate-900">Account Setup</h1>
          <p className="text-slate-600 mt-2">Set your password to activate your account</p>
        </div>

        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-center">
          <p className="font-semibold mb-2">Token Error</p>
          <p className="text-sm">{tokenError}</p>
          <p className="text-xs mt-2">
            Contact your family admin to get a new activation token
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="text-center mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Complete Your Setup</h1>
        <p className="text-slate-600 mt-2">
          Set your password to activate your account
        </p>
      </div>

      {tokenInfo && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-sm">
          <p className="text-slate-700">
            <strong>Account:</strong> {tokenInfo.email}
          </p>
          <p className="text-slate-600 text-xs mt-1">
            Token expires: {new Date(tokenInfo.expiresAt).toLocaleString()}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="email"
              value={tokenInfo?.email || ''}
              disabled
              className="w-full pl-10 pr-3 py-2 border rounded-lg bg-gray-50 text-gray-600"
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">Email is used as your username for login</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Create Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              {...register('password', {
                required: 'Password is required',
                minLength: {
                  value: 8,
                  message: 'Password must be at least 8 characters'
                }
              })}
              type="password"
              className="w-full pl-10 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>
          {errors.password && (
            <p className="text-red-500 text-sm mt-1">{errors.password.message}</p>
          )}
          {strength && (
            <div className="mt-2">
              <div className="flex gap-1 h-1.5">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className={`flex-1 rounded-full ${i <= strength.score ? strength.bar : 'bg-gray-200'}`} />
                ))}
              </div>
              <p className={`text-xs mt-1 ${strength.text}`}>{strength.label}</p>
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Confirm Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: (value) =>
                  value === password || 'Passwords do not match'
              })}
              type="password"
              className="w-full pl-10 pr-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>
          {errors.confirmPassword && (
            <p className="text-red-500 text-sm mt-1">{errors.confirmPassword.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {mutation.isPending ? 'Setting Up Account...' : 'Set Password & Create Account'}
        </button>
      </form>
    </div>
  );
};

export default SetPassword;
