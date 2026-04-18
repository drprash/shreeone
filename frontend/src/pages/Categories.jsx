import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { Plus, Edit, Trash2, X, TrendingUp, TrendingDown, GripVertical, ArrowLeftRight } from 'lucide-react';
import { queryKeys } from '../utils/queryKeys';
import LoadingSpinner from '../components/LoadingSpinner';
import toast from 'react-hot-toast';
import { useCreateCategory, useUpdateCategory, useDeleteCategory } from '../hooks/useCategoryMutations';

const CATEGORY_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6',
  '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899',
  '#f43f5e', '#78716c', '#64748b',
  '#FFD700', '#C0C0C0', '#B87333', '#CD7F32'
];

const Categories = () => {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [isReordering, setIsReordering] = useState(false);
  const [orderedCategories, setOrderedCategories] = useState([]);
  const draggedId = useRef(null);

  const [formData, setFormData] = useState({
    name: '',
    type: 'EXPENSE',
    color: CATEGORY_COLORS[0]
  });

  const { data: categories, isLoading } = useQuery({
    queryKey: queryKeys.categories(),
    queryFn: () => api.get('/categories/').then(res => res.data)
  });

  const { mutate: createCategoryMutate, isPending: createPending } = useCreateCategory({
    onSuccess: () => { setShowModal(false); resetForm(); },
  });

  const { mutate: updateCategoryMutate, isPending: updatePending } = useUpdateCategory({
    onSuccess: () => { setShowModal(false); setEditingCategory(null); },
  });

  const { mutate: deleteCategoryMutate } = useDeleteCategory();

  const reorderMutation = useMutation({
    mutationFn: (items) => api.put('/categories/reorder', items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories() });
      toast.success('Order saved');
    },
    onError: () => {
      toast.error('Failed to save order');
    }
  });

  // Sync orderedCategories when data changes
  useEffect(() => {
    if (categories) {
      setOrderedCategories([...categories]);
    }
  }, [categories]);

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'EXPENSE',
      color: CATEGORY_COLORS[0]
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (editingCategory) {
      updateCategoryMutate({ id: editingCategory.id, data: formData });
    } else {
      createCategoryMutate(formData);
    }
  };

  const startEdit = (category) => {
    setEditingCategory(category);
    setFormData({
      name: category.name,
      type: category.type,
      color: category.color
    });
    setShowModal(true);
  };

  // Drag-and-drop handlers (within same type group)
  const handleDragStart = (e, id) => {
    draggedId.current = id;
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e, targetId, groupType) => {
    e.preventDefault();
    if (!draggedId.current || draggedId.current === targetId) return;

    const newOrdered = [...orderedCategories];
    const dragIdx = newOrdered.findIndex(c => c.id === draggedId.current);
    const targetIdx = newOrdered.findIndex(c => c.id === targetId);

    // Only allow drops within same type group
    if (newOrdered[dragIdx]?.type !== groupType || newOrdered[targetIdx]?.type !== groupType) return;

    const [dragged] = newOrdered.splice(dragIdx, 1);
    newOrdered.splice(targetIdx, 0, dragged);
    setOrderedCategories(newOrdered);

    // Re-assign sort_order within this group and save
    const groupCategories = newOrdered.filter(c => c.type === groupType);
    const reorderItems = groupCategories.map((c, i) => ({ id: c.id, sort_order: i }));
    reorderMutation.mutate(reorderItems);

    draggedId.current = null;
  };

  const handleDragEnd = () => {
    draggedId.current = null;
  };

  const incomeCategories = orderedCategories.filter(c => c.type === 'INCOME');
  const expenseCategories = orderedCategories.filter(c => c.type === 'EXPENSE');

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const renderCategoryCard = (category) => (
    <div
      key={category.id}
      className="card-hover bg-white dark:bg-slate-800 rounded-lg shadow p-3 sm:p-4 flex items-center justify-between border border-gray-100 dark:border-slate-700"
    >
      <div className="flex items-center gap-3">
        <div
          className="w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: category.color }}
        >
          {category.type === 'INCOME' ? (
            <TrendingUp className="w-5 h-5 text-white" />
          ) : (
            <TrendingDown className="w-5 h-5 text-white" />
          )}
        </div>
        <div>
          <h3 className="font-medium text-gray-900">{category.name}</h3>
          <span className={`text-xs px-2 py-0.5 rounded ${
            category.type === 'INCOME' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}>
            {category.type}
          </span>
        </div>
      </div>
      {user?.role === 'ADMIN' && (
        <div className="flex gap-2">
          <button
            onClick={() => startEdit(category)}
            className="text-gray-400 hover:text-blue-600"
          >
            <Edit className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              if (confirm('Delete this category?')) {
                deleteCategoryMutate(category.id);
              }
            }}
            className="text-gray-400 hover:text-red-600"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );

  const renderReorderRow = (category) => (
    <div
      key={category.id}
      draggable
      onDragStart={(e) => handleDragStart(e, category.id)}
      onDragOver={handleDragOver}
      onDrop={(e) => handleDrop(e, category.id, category.type)}
      onDragEnd={handleDragEnd}
      className="flex items-center gap-3 bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 px-4 py-3 cursor-grab active:cursor-grabbing select-none"
      style={{ opacity: draggedId.current === category.id ? 0.4 : 1 }}
    >
      <GripVertical className="w-5 h-5 text-gray-400 flex-shrink-0" />
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: category.color }}
      >
        {category.type === 'INCOME' ? (
          <TrendingUp className="w-4 h-4 text-white" />
        ) : (
          <TrendingDown className="w-4 h-4 text-white" />
        )}
      </div>
      <p className="font-medium text-gray-900 flex-1">{category.name}</p>
    </div>
  );

  const renderGroup = (label, groupCategories, icon, groupType) => (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-700 mb-4 flex items-center gap-2">
        {icon}
        {label}
      </h2>
      {isReordering ? (
        <div className="space-y-2">
          {groupCategories.map(renderReorderRow)}
          {groupCategories.length === 0 && (
            <p className="text-gray-500 text-center py-4 bg-gray-50 rounded-lg text-sm">No categories</p>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {groupCategories.map(renderCategoryCard)}
          </div>
          {groupCategories.length === 0 && (
            <p className="text-gray-500 text-center py-8 bg-gray-50 rounded-lg">
              No {label.toLowerCase()} yet
            </p>
          )}
        </>
      )}
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Categories</h1>
          <p className="text-gray-600 mt-1">Manage income and expense categories</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {user?.role === 'ADMIN' && (
            <button
              onClick={() => setIsReordering(!isReordering)}
              className={`px-4 py-2.5 rounded-lg flex items-center gap-2 border ${
                isReordering
                  ? 'bg-green-600 text-white border-green-600 hover:bg-green-700'
                  : 'bg-white dark:bg-slate-800 text-gray-700 dark:text-slate-200 border-gray-300 dark:border-slate-600 hover:bg-gray-50'
              }`}
            >
              <ArrowLeftRight className="w-4 h-4" />
              {isReordering ? 'Done Reordering' : 'Reorder'}
            </button>
          )}
          {user?.role === 'ADMIN' && !isReordering && (
            <button
              onClick={() => {
                setEditingCategory(null);
                resetForm();
                setShowModal(true);
              }}
              className="bg-blue-600 text-white px-4 py-2.5 rounded-lg flex items-center gap-2 hover:bg-blue-700"
            >
              <Plus className="w-5 h-5" />
              Add Category
            </button>
          )}
        </div>
      </div>

      {isReordering && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-sm text-blue-700 dark:text-blue-300">
            Drag categories within each group to reorder. Changes save automatically.
          </p>
        </div>
      )}

      {renderGroup(
        'Income Categories',
        incomeCategories,
        <TrendingUp className="w-5 h-5 text-green-600" />,
        'INCOME'
      )}

      {renderGroup(
        'Expense Categories',
        expenseCategories,
        <TrendingDown className="w-5 h-5 text-red-600" />,
        'EXPENSE'
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-backdrop fixed inset-0 flex items-start sm:items-center justify-center z-50 p-3 sm:p-4 overflow-y-auto">
          <div className="glass-panel bg-white dark:bg-slate-800 rounded-lg shadow-xl w-full max-w-md mx-3 sm:mx-4 p-4 sm:p-6 max-h-[92vh] overflow-y-auto slide-in">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">
                {editingCategory ? 'Edit Category' : 'New Category'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Groceries"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
                <div className="flex gap-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="EXPENSE"
                      checked={formData.type === 'EXPENSE'}
                      onChange={(e) => setFormData({...formData, type: e.target.value})}
                      className="mr-2"
                    />
                    <span className="text-red-600 font-medium">Expense</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="INCOME"
                      checked={formData.type === 'INCOME'}
                      onChange={(e) => setFormData({...formData, type: e.target.value})}
                      className="mr-2"
                    />
                    <span className="text-green-600 font-medium">Income</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
                <div className="flex flex-wrap gap-2">
                  {CATEGORY_COLORS.map(color => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => setFormData({...formData, color})}
                      className={`w-8 h-8 rounded-full border-2 ${
                        formData.color === color ? 'border-gray-900' : 'border-transparent'
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2.5 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createPending || updatePending}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {editingCategory ? 'Save Changes' : 'Create Category'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Categories;
