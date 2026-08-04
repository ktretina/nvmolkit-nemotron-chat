import { useEffect, useMemo, useRef, useState } from "react";
import { createViewer, type GLViewer } from "3dmol";
import Plot from "react-plotly.js";
import type { Data, Layout } from "plotly.js";

import type {
  ConformerStructure,
  ConformerVisualization,
  PlotlyGraph,
  Visualization,
} from "./types";

type RenderingStyle = "stick" | "line" | "sphere";

const ELEMENT_COLORS: Record<string, string> = {
  C: "#aeb5be",
  H: "#f2f4f6",
  N: "#4d8cff",
  O: "#ff5a5f",
  F: "#77d36a",
  P: "#ff9f43",
  S: "#ffd43b",
  Cl: "#56c76c",
  Br: "#b86b43",
  I: "#8b65c2",
};

function ScientificPlot({ graph }: { graph: PlotlyGraph }) {
  return (
    <div className="plot-frame" aria-label={`${graph.layout.title.text} plot`}>
      <Plot
        data={graph.data as Data[]}
        layout={{
          ...(graph.layout as Partial<Layout>),
          autosize: true,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "#d7d9dc" },
          margin: { l: 72, r: 32, t: 58, b: 72 },
        }}
        config={{ responsive: true, displaylogo: false }}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}

function molBlock(structure: ConformerStructure): string {
  const atomLines = structure.atoms.map((atom, index) => {
    const point = structure.coordinates[index];
    const element = /^[A-Z][a-z]?$/.test(atom.element) ? atom.element : "C";
    return `${Number(point[0]).toFixed(4).padStart(10)}${Number(point[1]).toFixed(4).padStart(10)}${Number(point[2]).toFixed(4).padStart(10)} ${element.padEnd(3)} 0  0  0  0  0  0  0  0  0  0  0  0`;
  });
  const bondLines = structure.bonds.map((bond) => {
    const order = bond.order === 1.5 ? 4 : Math.max(1, Math.min(3, Math.round(bond.order)));
    return `${String(bond.begin + 1).padStart(3)}${String(bond.end + 1).padStart(3)}${String(order).padStart(3)}  0  0  0  0`;
  });
  return [
    structure.conformer_id,
    "nvMolKit",
    "",
    `${String(structure.atoms.length).padStart(3)}${String(structure.bonds.length).padStart(3)}  0  0  0  0            999 V2000`,
    ...atomLines,
    ...bondLines,
    "M  END",
    "$$$$",
  ].join("\n");
}

function styleSpec(style: RenderingStyle): Record<string, unknown> {
  if (style === "line") return { line: { colorscheme: "Jmol" } };
  if (style === "sphere") return { sphere: { colorscheme: "Jmol", scale: 0.32 } };
  return { stick: { colorscheme: "Jmol", radius: 0.16 } };
}

function ConformerPane({ visualization }: { visualization: ConformerVisualization }) {
  const firstMolecule = visualization.selectors.molecule_ids[0] ?? "";
  const [moleculeId, setMoleculeId] = useState(firstMolecule);
  const availableConformers = visualization.selectors.conformer_ids_by_molecule[moleculeId] ?? [];
  const [conformerId, setConformerId] = useState(availableConformers[0] ?? "");
  const [renderingStyle, setRenderingStyle] = useState<RenderingStyle>("stick");
  const canvasRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<GLViewer | null>(null);

  useEffect(() => {
    setMoleculeId(firstMolecule);
    setConformerId(visualization.selectors.conformer_ids_by_molecule[firstMolecule]?.[0] ?? "");
  }, [firstMolecule, visualization]);

  useEffect(() => {
    if (canvasRef.current && !viewerRef.current) {
      viewerRef.current = createViewer(canvasRef.current, { backgroundColor: "#090d13" });
    }
    const viewer = viewerRef.current;
    return () => {
      viewer?.clear();
      viewerRef.current = null;
    };
  }, []);

  const selected = useMemo(
    () => visualization.viewer.structures.find((item) => item.conformer_id === conformerId),
    [conformerId, visualization.viewer.structures],
  );

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !selected) return;
    viewer.removeAllModels();
    viewer.addModel(molBlock(selected), "mol");
    viewer.setStyle({}, styleSpec(renderingStyle));
    viewer.zoomTo();
    viewer.render();
  }, [renderingStyle, selected]);

  const elements = Array.from(new Set(selected?.atoms.map((atom) => atom.element) ?? []));

  function chooseMolecule(value: string) {
    setMoleculeId(value);
    setConformerId(visualization.selectors.conformer_ids_by_molecule[value]?.[0] ?? "");
  }

  return (
    <div className="conformer-pane">
      <div className="viewer-controls">
        <label>
          Molecule
          <select value={moleculeId} onChange={(event) => chooseMolecule(event.target.value)}>
            {visualization.selectors.molecule_ids.map((id) => <option key={id}>{id}</option>)}
          </select>
        </label>
        <label>
          Conformer
          <select value={conformerId} onChange={(event) => setConformerId(event.target.value)}>
            {availableConformers.map((id) => <option key={id}>{id}</option>)}
          </select>
        </label>
        <label>
          Rendering style
          <select value={renderingStyle} onChange={(event) => setRenderingStyle(event.target.value as RenderingStyle)}>
            <option value="stick">Stick</option>
            <option value="line">Line</option>
            <option value="sphere">Sphere</option>
          </select>
        </label>
      </div>
      <div className="molecule-canvas" ref={canvasRef} aria-label="Interactive 3D molecular conformer" />
      {visualization.viewer.atom_legend && (
        <div className="atom-legend" aria-label="Atom color legend">
          {elements.map((element) => (
            <span key={element}><i style={{ background: ELEMENT_COLORS[element] ?? "#aeb5be" }} />{element}</span>
          ))}
        </div>
      )}
      <ScientificPlot graph={visualization.energy_plot} />
    </div>
  );
}

export default function AdaptiveViewer({ visualization }: { visualization: Visualization | null }) {
  if (!visualization) {
    return (
      <div className="viewer-empty">
        <span aria-hidden="true">◈</span>
        <h2>Scientific viewer</h2>
        <p>Your latest bundled-data analysis will appear here.</p>
      </div>
    );
  }
  if (visualization.kind === "conformers") {
    return <ConformerPane visualization={visualization} />;
  }
  return <ScientificPlot graph={visualization} />;
}
