import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Fingerprint, Trash2, Plus, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../services/api';
import {
  isWebAuthnSupported,
  isPlatformAuthenticatorAvailable,
  registerPasskey,
} from '../../services/webauthn';
import { useAuthStore } from '../../store/authStore';

export default function SecuritySettings() {
  const { setHasPasskey, setPasskeyUserId, user } = useAuthStore();
  const queryClient = useQueryClient();
  const [platformAvailable, setPlatformAvailable] = useState(false);
  const [deviceName, setDeviceName] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);

  useEffect(() => {
    if (isWebAuthnSupported()) {
      isPlatformAuthenticatorAvailable().then(setPlatformAvailable);
    }
  }, []);

  const { data: credentials = [], isLoading } = useQuery({
    queryKey: ['webauthn-credentials'],
    queryFn: () => api.get('/auth/webauthn/credentials').then((r) => r.data),
    enabled: platformAvailable,
  });

  const deleteMutation = useMutation({
    mutationFn: (credentialId) => api.delete(`/auth/webauthn/credentials/${credentialId}`),
    onSuccess: (_, credentialId) => {
      queryClient.invalidateQueries({ queryKey: ['webauthn-credentials'] });
      // If no credentials remain, clear the hasPasskey flag
      const remaining = credentials.filter((c) => c.credential_id !== credentialId);
      if (remaining.length === 0) setHasPasskey(false);
      toast.success('Passkey removed');
    },
    onError: () => toast.error('Failed to remove passkey'),
  });

  const handleRegister = async () => {
    setIsRegistering(true);
    try {
      await registerPasskey(deviceName.trim() || null);
      setHasPasskey(true);
      if (user?.id) setPasskeyUserId(user.id);
      setDeviceName('');
      queryClient.invalidateQueries({ queryKey: ['webauthn-credentials'] });
      toast.success('Biometric login enabled for this device');
    } catch (err) {
      toast.error(err.message || 'Failed to register passkey');
    } finally {
      setIsRegistering(false);
    }
  };

  if (!isWebAuthnSupported() || !platformAvailable) {
    return (
      <div className="p-6">
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-2">Security</h2>
        <p className="text-slate-500 dark:text-slate-400 text-sm">
          Biometric login is not supported on this device or browser.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-indigo-600" />
          Biometric Login
        </h2>
        <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
          Use your fingerprint or face to sign in without typing your password.
          Each device you register appears below.
        </p>
      </div>

      {/* Registered credentials */}
      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : credentials.length > 0 ? (
        <ul className="divide-y divide-slate-200 dark:divide-slate-700 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
          {credentials.map((cred) => (
            <li key={cred.id} className="flex items-center justify-between px-4 py-3 bg-white dark:bg-slate-800">
              <div className="flex items-center gap-3">
                <Fingerprint className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                    {cred.device_name || 'Unnamed device'}
                  </p>
                  <p className="text-xs text-slate-500">
                    Added {new Date(cred.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <button
                onClick={() => deleteMutation.mutate(cred.credential_id)}
                disabled={deleteMutation.isPending}
                className="p-2 text-slate-400 hover:text-red-500 transition-colors disabled:opacity-40"
                title="Remove this passkey"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">No passkeys registered yet.</p>
      )}

      {/* Register new passkey */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
          Device label (optional)
        </label>
        <input
          type="text"
          value={deviceName}
          onChange={(e) => setDeviceName(e.target.value)}
          placeholder="e.g. My Android Phone"
          className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 text-sm"
        />
        <button
          onClick={handleRegister}
          disabled={isRegistering}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium text-sm"
        >
          <Plus className="w-4 h-4" />
          {isRegistering ? 'Follow the prompt on your device…' : 'Add biometric login'}
        </button>
      </div>
    </div>
  );
}
