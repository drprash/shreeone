import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import api from '../services/api';
import { toast } from 'react-hot-toast';
import { Mail, Copy, Check, ArrowLeft } from 'lucide-react';

const ForgotPassword = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState(null);
  const [copiedToken, setCopiedToken] = useState(false);

  const mutation = useMutation({
    mutationFn: (data) => api.post('/auth/forgot-password', {
      email: data.email
    }),
    onSuccess: (response) => {
      setResetToken(response.data);
      toast.success('Password reset token generated!');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to generate reset token');
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error('Please enter your email address');
      return;
    }
    mutation.mutate({ email });
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2000);
  };

  const handleResetPassword = () => {
    navigate(`/set-password?token=${encodeURIComponent(resetToken.token)}`);
  };

  const handleGetNewToken = () => {
    setResetToken(null);
    setEmail('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Back Button */}
        <button
          onClick={() => navigate('/login')}
          className="flex items-center gap-2 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to login
        </button>

        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-8 border border-slate-200 dark:border-slate-700">
          {!resetToken ? (
            <>
              {/* Header */}
              <div className="text-center mb-8">
                <div className="flex justify-center mb-4">
                  <div className="p-3 bg-indigo-100 dark:bg-indigo-900/30 rounded-full">
                    <Mail className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
                  </div>
                </div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Forgot Password?</h1>
                <p className="text-slate-600 dark:text-slate-400 mt-2">
                  Enter your email to generate a password reset token
                </p>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg focus:outline-none focus:border-indigo-500 dark:bg-slate-700 dark:text-slate-100"
                    disabled={mutation.isPending}
                  />
                </div>

                <button
                  type="submit"
                  disabled={mutation.isPending}
                  className="w-full px-4 py-2 bg-indigo-600 dark:bg-indigo-700 text-white rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {mutation.isPending ? 'Generating token...' : 'Generate Reset Token'}
                </button>
              </form>

              {/* Info Box */}
              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  💡 <strong>Tip:</strong> The reset token will be displayed on the next screen. Save it securely!
                </p>
              </div>
            </>
          ) : (
            <>
              {/* Token Display */}
              <div className="text-center mb-8">
                <div className="flex justify-center mb-4">
                  <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-full">
                    <Check className="w-6 h-6 text-green-600 dark:text-green-400" />
                  </div>
                </div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Token Generated!</h1>
                <p className="text-slate-600 dark:text-slate-400 mt-2">
                  Copy the token below and use it to reset your password
                </p>
              </div>

              {/* Token Display Box */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Reset Token (Valid for 72 hours)
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={resetToken.token}
                      readOnly
                      className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-600 dark:text-slate-400 font-mono text-xs break-all"
                    />
                    <button
                      onClick={() => copyToClipboard(resetToken.token)}
                      className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                      title="Copy token"
                    >
                      {copiedToken ? (
                        <Check className="w-5 h-5 text-green-600" />
                      ) : (
                        <Copy className="w-5 h-5 text-slate-600 dark:text-slate-400" />
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    value={resetToken.user_email}
                    readOnly
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-600 dark:text-slate-400"
                  />
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={handleResetPassword}
                    className="flex-1 px-4 py-2 bg-indigo-600 dark:bg-indigo-700 text-white rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-600 transition-colors font-medium"
                  >
                    Reset Password Now
                  </button>
                  <button
                    onClick={handleGetNewToken}
                    className="flex-1 px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-slate-100 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors font-medium"
                  >
                    Get New Token
                  </button>
                </div>
              </div>

              {/* Info Box */}
              <div className="mt-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                <p className="text-sm text-yellow-800 dark:text-yellow-300">
                  ⚠️ <strong>Important:</strong> Save this token in a secure location. It cannot be regenerated once used.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
