import { create } from "zustand";
const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const useStore = create((set, get) => ({
  jobId: null, nFrames: 0, dims: [0, 0], rois: {},
  selectedCells: [], hoveredCell: null, currentFrame: 0, isPlaying: false,
  traces: {}, metrics: {}, traceMode: "dff",

  setExperiment: (jobId, nFrames, dims) =>
    set({ jobId, nFrames, dims, selectedCells: [], traces: {}, metrics: {} }),
  setRois: (rois) => set({ rois }),
  setFrame: (f) => set({ currentFrame: f }),
  setPlaying: (p) => set({ isPlaying: p }),
  setHovered: (c) => set({ hoveredCell: c }),
  setTraceMode: (m) => set({ traceMode: m }),
  clearSelection: () => set({ selectedCells: [] }),

  toggleCell: async (cid) => {
    const s = get();
    if (s.selectedCells.includes(cid)) {
      set({ selectedCells: s.selectedCells.filter((x) => x !== cid) });
    } else {
      if (!s.traces[cid]) {
        const r = await fetch(API + "/cell/" + s.jobId + "/" + cid).then((x) => x.json());
        set({
          traces: { ...s.traces, [cid]: { raw: r.raw, dff: r.dff } },
          metrics: { ...s.metrics, [cid]: r.metrics },
          selectedCells: [...s.selectedCells, cid],
        });
        return;
      }
      set({ selectedCells: [...s.selectedCells, cid] });
    }
  },
}));
export default useStore;
export { API };
