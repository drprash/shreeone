import { Lock, Users, Globe, Info } from 'lucide-react';

/**
 * PrivacyIndicator Component
 * 
 * Displays the current privacy level and what data the user can see.
 * Only shown to non-admin members.
 */
const PrivacyIndicator = ({ privacyLevel, userRole }) => {
  // Admin sees everything, no need to show indicator
  if (userRole === 'ADMIN') return null;
  
  const config = {
    PRIVATE: {
      icon: Lock,
      label: 'Private',
      description: 'Showing only your transactions',
      color: 'text-red-600 bg-red-50 border-red-200',
      info: 'Other family members cannot see your personal transactions'
    },
    SHARED: {
      icon: Users,
      label: 'Shared',
      description: 'Showing shared accounts + your transactions',
      color: 'text-yellow-600 bg-yellow-50 border-yellow-200',
      info: 'Family members see shared account transactions and their own'
    },
    FAMILY: {
      icon: Globe,
      label: 'Family',
      description: 'Showing all family transactions',
      color: 'text-blue-600 bg-blue-50 border-blue-200',
      info: 'All family members can see all transactions'
    }
  };
  
  const settings = config[privacyLevel] || config.FAMILY;
  const Icon = settings.icon;
  
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border mb-6 ${settings.color}`}>
      <Info className="w-5 h-5 mt-0.5 flex-shrink-0" />
      <div>
        <div className="flex items-center gap-2 font-medium text-sm">
          <Icon className="w-4 h-4" />
          <span className="capitalize">{settings.label} Mode</span>
        </div>
        <p className="text-sm mt-1 opacity-90">{settings.info}</p>
      </div>
    </div>
  );
};

export default PrivacyIndicator;
