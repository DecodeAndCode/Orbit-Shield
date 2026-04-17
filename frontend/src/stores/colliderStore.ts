import { create } from "zustand";

interface ColliderStore {
  selectedConjunctionId: number | null;
  selectConjunction: (id: number | null) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  alertModalOpen: boolean;
  setAlertModalOpen: (open: boolean) => void;
}

export const useColliderStore = create<ColliderStore>((set) => ({
  selectedConjunctionId: null,
  selectConjunction: (id) => set({ selectedConjunctionId: id }),
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  alertModalOpen: false,
  setAlertModalOpen: (open) => set({ alertModalOpen: open }),
}));
