import React, { useState, useEffect } from 'react';
import settingsAPI from '../../services/settingsAPI';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { Copy, Check } from 'lucide-react';

const MemberManagement = () => {
  const user = useAuthStore((state) => state.user);
  const [members, setMembers] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showAddMemberModal, setShowAddMemberModal] = useState(false);
  const [showPermissionsModal, setShowPermissionsModal] = useState(false);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [selectedMember, setSelectedMember] = useState(null);
  const [resetPasswordToken, setResetPasswordToken] = useState(null);
  const [copiedToken, setCopiedToken] = useState(null);

  const [memberForm, setMemberForm] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: 'MEMBER'
  });

  const [inviteData, setInviteData] = useState(null);

  const [permissionsForm, setPermissionsForm] = useState({
    can_add_transaction: true,
    can_edit_transaction: true,
    can_delete_transaction: false,
    can_add_account: false,
    can_edit_account: false,
    can_delete_account: false,
    can_manage_categories: false,
    can_view_all_accounts: true,
    can_view_all_transactions: true,
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [usersRes, permsRes] = await Promise.all([
        api.get('/admin/users'),
        settingsAPI.getPermissions(),
      ]);

      setMembers(usersRes.data);
      const permMap = {};
      permsRes.data.forEach((perm) => {
        permMap[perm.user_id] = perm;
      });
      setPermissions(permMap);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load members');
    } finally {
      setLoading(false);
    }
  };

  const handleAddMember = async (e) => {
    e.preventDefault();
    try {
      setError(null);
      const response = await api.post('/admin/members', {
        email: memberForm.email,
        first_name: memberForm.first_name,
        last_name: memberForm.last_name,
        role: memberForm.role,
      });

      setInviteData(response.data);
      setMemberForm({ email: '', first_name: '', last_name: '', role: 'MEMBER' });
      setSuccessMessage('Member created successfully! Share the activation token below.');
      setTimeout(() => setSuccessMessage(null), 5000);
      fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add member');
    }
  };

  const copyToClipboard = (text, tokenId) => {
    navigator.clipboard.writeText(text);
    setCopiedToken(tokenId);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const handleUpdatePermissions = async (memberId) => {
    try {
      setError(null);
      await settingsAPI.updateMemberPermissions(memberId, permissionsForm);
      setSuccessMessage('Permissions updated successfully!');
      setShowPermissionsModal(false);
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update permissions');
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!window.confirm('Are you sure you want to remove this member? They will lose access to the family account.')) {
      return;
    }

    try {
      setError(null);
      await settingsAPI.removeMember(memberId);
      setSuccessMessage('Member removed successfully!');
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove member');
    }
  };

  const handleReactivateMember = async (memberId) => {
    try {
      setError(null);
      await settingsAPI.reactivateMember(memberId);
      setSuccessMessage('Member reactivated successfully!');
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reactivate member');
    }
  };

  const handleTransferAdminRole = async (memberId) => {
    if (!window.confirm('Are you sure? You will become a regular member after transferring the admin role.')) {
      return;
    }

    try {
      setError(null);
      await settingsAPI.transferAdminRole({ new_admin_user_id: memberId });
      setSuccessMessage('Admin role transferred successfully!');
      const newUser = { ...user, role: 'MEMBER' };
      useAuthStore.setState({ user: newUser });
      fetchData();
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to transfer admin role');
    }
  };

  const handleResetPassword = async (member) => {
    try {
      setError(null);
      setSelectedMember(member);
      const response = await api.post(`/admin/users/${member.id}/reset-password`);
      setResetPasswordToken(response.data);
      setShowResetPasswordModal(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate password reset token');
    }
  };

  const openPermissionsModal = (member) => {
    setSelectedMember(member);
    const memberPerms = permissions[member.id];
    if (memberPerms) {
      setPermissionsForm({
        can_add_transaction: memberPerms.can_add_transaction,
        can_edit_transaction: memberPerms.can_edit_transaction,
        can_delete_transaction: memberPerms.can_delete_transaction,
        can_add_account: memberPerms.can_add_account,
        can_edit_account: memberPerms.can_edit_account,
        can_delete_account: memberPerms.can_delete_account,
        can_manage_categories: memberPerms.can_manage_categories,
        can_view_all_accounts: memberPerms.can_view_all_accounts,
        can_view_all_transactions: memberPerms.can_view_all_transactions,
      });
    }
    setShowPermissionsModal(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
          {successMessage}
        </div>
      )}

      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-slate-900">Family Members</h2>
        <button
          onClick={() => {
            setShowAddMemberModal(true);
            setInviteData(null);
          }}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
        >
          + Add Member
        </button>
      </div>

      {/* Members Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="px-4 py-3 text-left font-semibold text-slate-700">Name</th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">Email</th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">Role</th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">Status</th>
              <th className="px-4 py-3 text-left font-semibold text-slate-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.id} className="border-b border-slate-200 hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3">{member.first_name} {member.last_name}</td>
                <td className="px-4 py-3">{member.email}</td>
                <td className="px-4 py-3">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium text-white ${
                    member.role === 'ADMIN'
                      ? 'admin-badge'
                      : 'bg-indigo-600'
                  }`}>
                    {member.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    member.active
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {member.active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    {member.id !== user.id && member.active && (
                      <>
                        <button
                          onClick={() => openPermissionsModal(member)}
                          className="px-3 py-1 bg-blue-100 text-blue-700 rounded text-sm hover:bg-blue-200 transition-colors"
                        >
                          Permissions
                        </button>
                        <button
                          onClick={() => handleResetPassword(member)}
                          className="px-3 py-1 bg-orange-100 text-orange-700 rounded text-sm hover:bg-orange-200 transition-colors"
                        >
                          Reset Password
                        </button>
                        {member.role !== 'ADMIN' && (
                          <button
                            onClick={() => handleRemoveMember(member.id)}
                            className="px-3 py-1 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200 transition-colors"
                          >
                            Remove
                          </button>
                        )}
                        {member.role !== 'ADMIN' && (
                          <button
                            onClick={() => handleTransferAdminRole(member.id)}
                            className="px-3 py-1 admin-badge text-white rounded text-sm hover:opacity-90 transition-opacity"
                          >
                            Make Admin
                          </button>
                        )}
                      </>
                    )}
                    {member.id !== user.id && !member.active && (
                      <button
                        onClick={() => handleReactivateMember(member.id)}
                        className="px-3 py-1 bg-green-100 text-green-700 rounded text-sm hover:bg-green-200 transition-colors"
                      >
                        Reactivate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Member Modal */}
      {showAddMemberModal && (
        <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg p-6 max-w-md w-full mx-4 slide-in">
            {!inviteData ? (
              <>
                <h3 className="text-xl font-bold text-slate-900 mb-4">Add Family Member</h3>
                <form onSubmit={handleAddMember}>
                  <div className="space-y-4 mb-6">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        Email
                      </label>
                      <input
                        type="email"
                        value={memberForm.email}
                        onChange={(e) => setMemberForm({ ...memberForm, email: e.target.value })}
                        placeholder="member@example.com"
                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                        required
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                          First Name
                        </label>
                        <input
                          type="text"
                          value={memberForm.first_name}
                          onChange={(e) => setMemberForm({ ...memberForm, first_name: e.target.value })}
                          placeholder="John"
                          className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                          required
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                          Last Name
                        </label>
                        <input
                          type="text"
                          value={memberForm.last_name}
                          onChange={(e) => setMemberForm({ ...memberForm, last_name: e.target.value })}
                          placeholder="Doe"
                          className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">
                        Role
                      </label>
                      <select
                        value={memberForm.role}
                        onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })}
                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:border-indigo-500"
                      >
                        <option value="MEMBER">Member</option>
                        <option value="ADMIN">Admin</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      type="submit"
                      className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                    >
                      Create Member
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowAddMemberModal(false)}
                      className="flex-1 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors font-medium"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <>
                <h3 className="text-xl font-bold text-slate-900 mb-4">Member Created!</h3>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                  <p className="text-sm text-slate-700 mb-3">
                    <strong>Share this activation token with the member:</strong>
                  </p>
                  <div className="bg-white border border-blue-300 rounded p-3 flex items-center justify-between mb-2">
                    <code className="text-xs text-slate-700 break-all flex-1">
                      {inviteData.activation_token}
                    </code>
                    <button
                      onClick={() => copyToClipboard(inviteData.activation_token, 'token')}
                      className="ml-2 p-2 hover:bg-slate-200 rounded transition-colors"
                      title="Copy token"
                    >
                      {copiedToken === 'token' ? (
                        <Check className="w-4 h-4 text-green-600" />
                      ) : (
                        <Copy className="w-4 h-4 text-slate-600" />
                      )}
                    </button>
                  </div>
                  <p className="text-xs text-slate-600">
                    Token expires: {new Date(inviteData.activation_expires_at).toLocaleString()}
                  </p>
                </div>

                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-6">
                  <p className="text-sm text-slate-700">
                    <strong>Instructions:</strong>
                  </p>
                  <ol className="text-xs text-slate-600 mt-2 list-decimal list-inside space-y-1">
                    <li>Send the activation token to the member</li>
                    <li>They visit the app and use "Set Password" option</li>
                    <li>They paste the token and create their password</li>
                    <li>They can then log in normally</li>
                  </ol>
                </div>

                <button
                  onClick={() => {
                    setShowAddMemberModal(false);
                    setInviteData(null);
                  }}
                  className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
                >
                  Done
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Permissions Modal */}
      {showPermissionsModal && selectedMember && (
        <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg p-6 max-w-2xl w-full mx-4 max-h-96 overflow-y-auto slide-in">
            <h3 className="text-xl font-bold text-slate-900 mb-4">
              Permissions for {selectedMember.first_name} {selectedMember.last_name}
            </h3>
            <div className="space-y-3 mb-6">
              {/* Transaction Permissions */}
              <div className="border-b pb-3">
                <h4 className="font-semibold text-slate-700 mb-2">Transaction Permissions</h4>
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_add_transaction}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_add_transaction: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can add transactions</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_edit_transaction}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_edit_transaction: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can edit transactions</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_delete_transaction}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_delete_transaction: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can delete transactions</span>
                </label>
              </div>

              {/* Account Permissions */}
              <div className="border-b pb-3">
                <h4 className="font-semibold text-slate-700 mb-2">Account Permissions</h4>
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_add_account}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_add_account: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can add accounts</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_edit_account}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_edit_account: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can edit accounts</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_delete_account}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_delete_account: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can delete accounts</span>
                </label>
              </div>

              {/* Management & Viewing Permissions */}
              <div>
                <h4 className="font-semibold text-slate-700 mb-2">Other Permissions</h4>
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_manage_categories}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_manage_categories: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can manage categories</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_view_all_accounts}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_view_all_accounts: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can view all accounts</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={permissionsForm.can_view_all_transactions}
                    onChange={(e) => setPermissionsForm({ ...permissionsForm, can_view_all_transactions: e.target.checked })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-slate-600">Can view all transactions</span>
                </label>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => handleUpdatePermissions(selectedMember.id)}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Save Permissions
              </button>
              <button
                onClick={() => setShowPermissionsModal(false)}
                className="flex-1 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showResetPasswordModal && resetPasswordToken && (
        <div className="modal-backdrop fixed inset-0 flex items-center justify-center z-50 p-4">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-lg max-w-md w-full p-6 slide-in">
            <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">
              Password Reset Token for {selectedMember?.first_name}
            </h3>
            <p className="text-slate-600 dark:text-slate-400 mb-4">
              Share this token with {selectedMember?.first_name} so they can reset their password. Token expires in 72 hours.
            </p>

            <div className="space-y-3 mb-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Reset Token (Valid for 72 hours)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={resetPasswordToken.token}
                    readOnly
                    className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-600 dark:text-slate-400 font-mono text-xs break-all"
                  />
                  <button
                    onClick={() => copyToClipboard(resetPasswordToken.token, 'reset')}
                    className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                    title="Copy token"
                  >
                    {copiedToken === 'reset' ? (
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
                  value={resetPasswordToken.user_email}
                  readOnly
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-600 dark:text-slate-400"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => {
                  setShowResetPasswordModal(false);
                  setResetPasswordToken(null);
                }}
                className="flex-1 px-4 py-2 bg-indigo-600 dark:bg-indigo-700 text-white rounded-lg hover:bg-indigo-700 dark:hover:bg-indigo-600 transition-colors font-medium"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MemberManagement;
