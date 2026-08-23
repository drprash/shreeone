import { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import QuickAdd from './QuickAdd';

// Dispatched (e.g. by the getting-started checklist) to open the form remotely
export const OPEN_QUICK_ADD_EVENT = 'shreeone-open-quick-add';

const FloatingAddTransactionButton = ({ accounts, categories, baseCurrency, defaultAccountId }) => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const open = () => setIsOpen(true);
    window.addEventListener(OPEN_QUICK_ADD_EVENT, open);
    return () => window.removeEventListener(OPEN_QUICK_ADD_EVENT, open);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center"
        title="Add Transaction"
      >
        <Plus className="w-6 h-6" />
      </button>

      {isOpen && (
        <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
          <div className="w-full max-w-lg mx-3 sm:mx-4 slide-in">
            <QuickAdd
              accounts={accounts}
              categories={categories}
              baseCurrency={baseCurrency}
              defaultAccountId={defaultAccountId}
              onSuccess={() => setIsOpen(false)}
              onClose={() => setIsOpen(false)}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default FloatingAddTransactionButton;
