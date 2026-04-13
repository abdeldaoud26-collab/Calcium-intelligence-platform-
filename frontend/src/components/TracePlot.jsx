import React, { useMemo } from "react";
import Plot from "react-plotly.js";
import useStore from "../store/useStore";
import { COLORS } from "../utils/colors";

export default function TracePlot({ fps = 10 }) {
  const { selectedCells, traces, traceMode, currentFrame } = useStore();
  const data = useMemo(() => selectedCells.map((cid, i) => {
    const t = traces[cid]; if (!t) return null;
    const y = traceMode === "dff" ? t.dff : t.raw;
    return { x: y.map((_, k) => k / fps), y, type: "scatter", mode: "lines",
      name: "Cell " + cid, line: { color: COLORS[i % COLORS.length], width: 2 } };
  }).filter(Boolean), [selectedCells, traces, traceMode, fps]);

  return <Plot data={data} layout={{
    title: selectedCells.length ? "Traces (" + selectedCells.length + " cells)" : "Click cells to plot",
    xaxis: { title: "Time (s)" }, yaxis: { title: traceMode === "dff" ? "ΔF/F₀" : "Raw F" },
    plot_bgcolor: "#1a1a2e", paper_bgcolor: "#16213e", font: { color: "#eee" },
    shapes: [{ type: "line", x0: currentFrame / fps, x1: currentFrame / fps,
      y0: 0, y1: 1, yref: "paper", line: { color: "white", width: 1, dash: "dot" } }],
    margin: { t: 40, r: 20, b: 50, l: 60 }, hovermode: "x unified",
  }} config={{ responsive: true }} style={{ width: "100%", height: "350px" }} />;
}
