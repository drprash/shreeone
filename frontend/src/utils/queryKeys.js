/**
 * Centralized React Query cache key factory.
 *
 * Convention:
 *  - Full keys (with all params) are used as queryKey in useQuery definitions.
 *  - Prefix keys (fewer/no params) are used in invalidateQueries to match all
 *    queries whose key starts with the same prefix.
 *
 * React Query performs prefix/fuzzy matching when invalidating, so
 * invalidateQueries({ queryKey: ['transactions'] }) invalidates both
 * transactionsList and transactionsByAccount keys.
 */
export const queryKeys = {
  // Dashboard
  dashboard:               (userId)                           => ['dashboard', userId],
  dashboardAll:            ()                                 => ['dashboard'],
  dashboardMember:         (memberId)                         => ['dashboard', 'member', memberId],

  // Accounts
  accounts:                ()                                 => ['accounts'],
  account:                 (accountId)                        => ['account', accountId],

  // Transactions
  transactionsList:        (filter, userId)                   => ['transactions', filter, userId],
  transactionsByAccount:   (accountId, dateFilter, typeFilter)=> ['transactions', accountId, dateFilter, typeFilter],
  transactionsAll:         ()                                 => ['transactions'],
  transactionsByAccountAll:(accountId)                        => ['transactions', accountId],

  // Categories
  categories:              ()                                 => ['categories'],

  // Settings
  familySettings:          ()                                 => ['family-settings'],
};
