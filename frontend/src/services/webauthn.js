import api from './api';

function bufferToBase64url(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

function base64urlToBuffer(base64url) {
  if (!base64url) return null;
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64.padEnd(base64.length + (4 - (base64.length % 4)) % 4, '=');
  const binary = atob(padded);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0)).buffer;
}

export function isWebAuthnSupported() {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential;
}

export async function isPlatformAuthenticatorAvailable() {
  if (!isWebAuthnSupported()) return false;
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch {
    return false;
  }
}

/**
 * Convert server-sent registration options into the shape expected by
 * navigator.credentials.create(). Converts base64url strings to ArrayBuffers.
 */
function prepareRegistrationOptions(serverOptions) {
  return {
    ...serverOptions,
    challenge: base64urlToBuffer(serverOptions.challenge),
    user: {
      ...serverOptions.user,
      id: base64urlToBuffer(serverOptions.user.id),
    },
    excludeCredentials: (serverOptions.excludeCredentials || []).map((c) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    })),
  };
}

/**
 * Convert the PublicKeyCredential returned by credentials.create() into
 * plain base64url strings for sending to the server.
 */
function encodeRegistrationResponse(credential) {
  return {
    credential_id: bufferToBase64url(credential.rawId),
    client_data_json: bufferToBase64url(credential.response.clientDataJSON),
    attestation_object: bufferToBase64url(credential.response.attestationObject),
  };
}

/**
 * Full registration flow:
 * 1. Fetch options from server
 * 2. Prompt user for biometric via browser
 * 3. Send result back to server
 * Returns the saved credential object from the server.
 */
export async function registerPasskey(deviceName) {
  const beginRes = await api.post('/auth/webauthn/register/begin');
  const publicKeyOptions = prepareRegistrationOptions(beginRes.data);

  let credential;
  try {
    credential = await navigator.credentials.create({ publicKey: publicKeyOptions });
  } catch (err) {
    if (err.name === 'NotAllowedError') {
      throw new Error('Biometric prompt was cancelled or timed out.');
    }
    throw err;
  }

  const payload = { ...encodeRegistrationResponse(credential), device_name: deviceName || null };
  const completeRes = await api.post('/auth/webauthn/register/complete', payload);
  return completeRes.data;
}

/**
 * Convert server-sent authentication options into the shape expected by
 * navigator.credentials.get(). Converts base64url strings to ArrayBuffers.
 */
function prepareAuthOptions(serverOptions) {
  return {
    ...serverOptions,
    challenge: base64urlToBuffer(serverOptions.challenge),
    allowCredentials: (serverOptions.allowCredentials || []).map((c) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    })),
  };
}

/**
 * Convert the PublicKeyCredential returned by credentials.get() into
 * plain base64url strings for sending to the server.
 */
function encodeAuthResponse(assertion) {
  return {
    credential_id: bufferToBase64url(assertion.rawId),
    client_data_json: bufferToBase64url(assertion.response.clientDataJSON),
    authenticator_data: bufferToBase64url(assertion.response.authenticatorData),
    signature: bufferToBase64url(assertion.response.signature),
    user_handle: assertion.response.userHandle ? bufferToBase64url(assertion.response.userHandle) : null,
  };
}

/**
 * Full authentication flow using a passkey:
 * 1. Fetch options from server (using userId to limit to known credentials)
 * 2. Prompt user for biometric via browser
 * 3. Send result to server — returns a Token (access_token, refresh_token, user)
 */
export async function authenticateWithPasskey(userId) {
  const beginRes = await api.post('/auth/webauthn/auth/begin', { user_id: userId });
  const publicKeyOptions = prepareAuthOptions(beginRes.data);

  let assertion;
  try {
    assertion = await navigator.credentials.get({ publicKey: publicKeyOptions });
  } catch (err) {
    if (err.name === 'NotAllowedError') {
      throw new Error('Biometric prompt was cancelled or timed out.');
    }
    throw err;
  }

  const payload = { user_id: userId, ...encodeAuthResponse(assertion) };
  const completeRes = await api.post('/auth/webauthn/auth/complete', payload);
  return completeRes.data;
}
