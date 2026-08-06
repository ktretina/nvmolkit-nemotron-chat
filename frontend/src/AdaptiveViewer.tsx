import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
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
  const titleId = useId();
  const descriptionId = useId();
  return (
    <figure className="plot-frame" aria-labelledby={titleId} aria-describedby={descriptionId}>
      <figcaption className="sr-only">
        <span id={titleId}>{graph.layout.title.text}</span>
        <span id={descriptionId}>
          X axis: {graph.layout.xaxis.title.text}. Y axis: {graph.layout.yaxis.title.text}.
        </span>
      </figcaption>
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
    </figure>
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

function PersistentConformerPane({ visualization }: { visualization: ConformerVisualization | null }) {
  const hasVisualization = visualization !== null;
  const firstMolecule = visualization?.selectors.molecule_ids[0] ?? "";
  const [moleculeId, setMoleculeId] = useState(firstMolecule);
  const availableConformers = visualization?.selectors.conformer_ids_by_molecule[moleculeId] ?? [];
  const [conformerId, setConformerId] = useState(availableConformers[0] ?? "");
  const [renderingStyle, setRenderingStyle] = useState<RenderingStyle>("stick");
  const viewerRef = useRef<GLViewer | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    setMoleculeId(firstMolecule);
    setConformerId(visualization?.selectors.conformer_ids_by_molecule[firstMolecule]?.[0] ?? "");
  }, [firstMolecule, visualization]);

  const attachViewerHost = useCallback((node: HTMLDivElement | null) => {
    if (node && visualization && !viewerRef.current) {
      viewerRef.current = createViewer(node, { backgroundColor: "#090d13" });
    }
  }, [hasVisualization]); // Attach lazily on the first 3D payload; retain thereafter.

  const selected = useMemo(
    () => visualization?.viewer.structures.find((item) => item.conformer_id === conformerId),
    [conformerId, visualization?.viewer.structures],
  );

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.clear();
    if (selected) {
      viewer.addModel(molBlock(selected), "mol");
      viewer.setStyle({}, styleSpec(renderingStyle));
      viewer.zoomTo();
    }
    viewer.render();
  }, [renderingStyle, selected, visualization]);

  const elements = Array.from(new Set(selected?.atoms.map((atom) => atom.element) ?? []));

  function chooseMolecule(value: string) {
    setMoleculeId(value);
    setConformerId(visualization?.selectors.conformer_ids_by_molecule[value]?.[0] ?? "");
  }

  return (
    <section
      className={visualization ? "conformer-pane is-active" : "conformer-pane"}
      hidden={!visualization}
      aria-hidden={!visualization}
      role="group"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      <h2 id={titleId} className="sr-only">3D molecular conformer</h2>
      <p id={descriptionId} className="sr-only">
        Interactive molecular structure with molecule, conformer, and rendering-style controls.
      </p>
      <div className="viewer-controls">
        <label>
          Molecule
          <select value={moleculeId} onChange={(event) => chooseMolecule(event.target.value)}>
            {visualization?.selectors.molecule_ids.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </label>
        <label>
          Conformer
          <select value={conformerId} onChange={(event) => setConformerId(event.target.value)}>
            {availableConformers.map((id) => <option key={id} value={id}>{id}</option>)}
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
      <div className="molecule-stage">
        <div className="molecule-canvas" ref={attachViewerHost} aria-label="Interactive 3D molecular conformer" />
        {visualization?.viewer.xyz_triad && (
          <div className="xyz-triad" role="img" aria-label="XYZ orientation triad">
            <span className="axis-x" aria-label="X axis">X</span>
            <span className="axis-y" aria-label="Y axis">Y</span>
            <span className="axis-z" aria-label="Z axis">Z</span>
          </div>
        )}
      </div>
      {visualization?.viewer.atom_legend && (
        <div className="atom-legend" aria-label="Atom color legend">
          {elements.map((element) => (
            <span key={element}><i style={{ background: ELEMENT_COLORS[element] ?? "#aeb5be" }} />{element}</span>
          ))}
        </div>
      )}
      {visualization && <ScientificPlot graph={visualization.energy_plot} />}
    </section>
  );
}

export default function AdaptiveViewer({ visualization }: { visualization: Visualization | null }) {
  const conformers = visualization?.kind === "conformers" ? visualization : null;
  const graph = visualization && visualization.kind !== "conformers" ? visualization : null;
  return (
    <div className="adaptive-viewer">
      <PersistentConformerPane visualization={conformers} />
      {!visualization && (
      <div className="viewer-empty">
        <span aria-hidden="true">◈</span>
        <h2>Scientific viewer</h2>
        <p>Your latest bundled-data analysis will appear here.</p>
      </div>
      )}
      {graph && <ScientificPlot graph={graph} />}
    </div>
  );
}
