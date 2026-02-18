import { create } from 'zustand';

const createEmptyScheduleByDay = () => (
  ['L', 'M', 'Mc', 'X', 'V'].reduce((acc, day) => {
    acc[day] = { schedule: [], stats: null };
    return acc;
  }, {})
);

export const useWorkspaceStudioStore = create((set) => ({
  activeWorkspaceId: null,
  routes: [],
  scheduleByDay: createEmptyScheduleByDay(),
  activeDay: 'L',
  selectedBusId: null,
  selectedRouteId: null,
  dirty: false,
  lastSavedAt: null,

  setActiveWorkspaceId: (activeWorkspaceId) => set({ activeWorkspaceId }),
  setRoutes: (routes) => set({ routes: Array.isArray(routes) ? routes : [] }),
  setScheduleByDay: (scheduleByDay) => set({
    scheduleByDay: scheduleByDay && typeof scheduleByDay === 'object'
      ? scheduleByDay
      : createEmptyScheduleByDay(),
  }),
  setActiveDay: (activeDay) => set({ activeDay }),
  setSelectedBusId: (selectedBusId) => set({ selectedBusId }),
  setSelectedRouteId: (selectedRouteId) => set({ selectedRouteId }),
  setDirty: (dirty) => set({ dirty: !!dirty }),
  markSaved: (timestamp = new Date().toISOString()) => set({ dirty: false, lastSavedAt: timestamp }),
  resetStudio: () => set({
    routes: [],
    scheduleByDay: createEmptyScheduleByDay(),
    activeDay: 'L',
    selectedBusId: null,
    selectedRouteId: null,
    dirty: false,
    lastSavedAt: null,
  }),
}));
