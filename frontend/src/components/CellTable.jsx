import React from "react";
import useStore from "../store/useStore";

export default function CellTable() {
  const { selectedCells, metrics, toggleCell, clearSelection } = useStore();
  if (!selectedCells.length) return <div style={box}><h3>Cell Metrics</h3><p style={{color:"#888"}}>Click cells on video</p></div>;
  return (
    <div style={box}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Metrics ({selectedCells.length})</h3>
        <button onClick={clearSelection} style={btn}>Clear</button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 8 }}>
        <thead><tr>{["Cell","Events","Freq","Amp","Area"].map(h=><th key={h} style={th}>{h}</th>)}</tr></thead>
        <tbody>{selectedCells.map(cid => { const m = metrics[cid]; if (!m) return null;
          return <tr key={cid}><td>#{cid}</td><td>{m.n_events}</td><td>{m.mean_frequency?.toFixed(4)}</td>
            <td>{m.mean_amplitude?.toFixed(3)}</td><td>{m.area}</td></tr>;
        })}</tbody>
      </table>
    </div>
  );
}
const box = { background: "#16213e", borderRadius: 8, padding: 16, color: "#eee", maxHeight: 400, overflowY: "auto" };
const btn = { background: "#e74c3c", color: "#fff", border: "none", borderRadius: 4, padding: "4px 10px", cursor: "pointer" };
const th = { textAlign: "left", borderBottom: "1px solid #444", padding: 4 };
