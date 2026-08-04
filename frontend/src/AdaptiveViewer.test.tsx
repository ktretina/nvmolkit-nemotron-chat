import { fireEvent, render, screen } from "@testing-library/react";

import AdaptiveViewer from "./AdaptiveViewer";

const { plotly, viewer } = vi.hoisted(() => ({
  plotly: vi.fn(({ layout }: { layout: { title?: { text?: string } } }) => ({ layout })),
  viewer: {
    removeAllModels: vi.fn(),
    addModel: vi.fn(),
    setStyle: vi.fn(),
    zoomTo: vi.fn(),
    render: vi.fn(),
    clear: vi.fn(),
  },
}));

vi.mock("react-plotly.js", async () => {
  const React = await import("react");
  return {
    default: (props: { layout: { title?: { text?: string } } }) => {
      plotly(props);
      return React.createElement("div", {
        role: "img",
        "aria-label": props.layout.title?.text ?? "Scientific graph",
        "data-testid": "plotly",
      });
    },
  };
});

vi.mock("3dmol", () => ({ createViewer: vi.fn(() => viewer) }));

const similarity = {
  kind: "similarity" as const,
  data: [{ type: "heatmap", z: [[1]], x: ["CHEMBL1"], y: ["CHEMBL1"] }],
  layout: {
    title: { text: "Pairwise molecular similarity" },
    xaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
    yaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
  },
};

const conformers = {
  kind: "conformers" as const,
  energy_plot: {
    kind: "plotly" as const,
    data: [{ type: "scatter", x: ["CHEMBL1:0", "CHEMBL1:1"], y: [0, 1.2] }],
    layout: {
      title: { text: "Sampled conformer energies" },
      xaxis: { title: { text: "Conformer ID" } },
      yaxis: { title: { text: "Relative MMFF94 energy (kcal/mol)" } },
    },
  },
  viewer: {
    kind: "3dmol" as const,
    atom_legend: true,
    xyz_triad: true,
    structures: [
      {
        molecule_id: "CHEMBL1",
        conformer_id: "CHEMBL1:0",
        conformer_index: 0,
        relative_energy_kcal_mol: 0,
        atoms: [{ index: 0, element: "C" }, { index: 1, element: "O" }],
        bonds: [{ begin: 0, end: 1, order: 1 }],
        coordinates: [[0, 0, 0], [1, 0, 0]],
      },
      {
        molecule_id: "CHEMBL1",
        conformer_id: "CHEMBL1:1",
        conformer_index: 1,
        relative_energy_kcal_mol: 1.2,
        atoms: [{ index: 0, element: "C" }, { index: 1, element: "O" }],
        bonds: [{ begin: 0, end: 1, order: 1 }],
        coordinates: [[0, 0, 0], [0, 1, 0]],
      },
    ],
  },
  selectors: {
    molecule_ids: ["CHEMBL1"],
    conformer_ids_by_molecule: { CHEMBL1: ["CHEMBL1:0", "CHEMBL1:1"] },
  },
  identities: [
    { molecule_id: "CHEMBL1", conformer_id: "CHEMBL1:0", conformer_index: 0 },
    { molecule_id: "CHEMBL1", conformer_id: "CHEMBL1:1", conformer_index: 1 },
  ],
};

beforeEach(() => {
  plotly.mockClear();
  Object.values(viewer).forEach((mock) => mock.mockClear());
});

it("passes labeled axes to Plotly for a two-dimensional result", () => {
  render(<AdaptiveViewer visualization={similarity} />);
  expect(plotly).toHaveBeenCalledWith(expect.objectContaining({
    layout: expect.objectContaining({
      xaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
      yaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
    }),
  }));
  expect(screen.queryByLabelText(/^conformer$/i)).not.toBeInTheDocument();
});

it("shows 3D controls and keeps the labeled energy graph for conformers", () => {
  render(<AdaptiveViewer visualization={conformers} />);
  expect(screen.getByLabelText(/molecule/i)).toHaveValue("CHEMBL1");
  expect(screen.getByLabelText(/^conformer$/i)).toHaveValue("CHEMBL1:0");
  expect(screen.getByLabelText(/rendering style/i)).toHaveValue("stick");
  expect(screen.getByText("C")).toBeInTheDocument();
  expect(screen.getByText("O")).toBeInTheDocument();
  const triad = screen.getByRole("img", { name: /xyz orientation triad/i });
  expect(triad).toBeInTheDocument();
  expect(screen.getByLabelText("X axis")).toBeInTheDocument();
  expect(screen.getByLabelText("Y axis")).toBeInTheDocument();
  expect(screen.getByLabelText("Z axis")).toBeInTheDocument();
  expect(plotly).toHaveBeenCalledWith(expect.objectContaining({
    layout: expect.objectContaining({
      xaxis: { title: { text: "Conformer ID" } },
      yaxis: { title: { text: "Relative MMFF94 energy (kcal/mol)" } },
    }),
  }));
});

it("omits the orientation triad when the validated payload disables it", () => {
  render(<AdaptiveViewer visualization={{
    ...conformers,
    viewer: { ...conformers.viewer, xyz_triad: false },
  }} />);
  expect(screen.queryByRole("img", { name: /xyz orientation triad/i })).not.toBeInTheDocument();
});

it("replaces the 3D model when the conformer selection changes", () => {
  render(<AdaptiveViewer visualization={conformers} />);
  expect(viewer.addModel).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText(/^conformer$/i), { target: { value: "CHEMBL1:1" } });
  expect(viewer.removeAllModels).toHaveBeenCalledTimes(2);
  expect(viewer.addModel).toHaveBeenCalledTimes(2);
  expect(viewer.addModel.mock.calls[1][0]).toContain("1.0000");
});

it.each(["fingerprint_density", "similarity", "clusters"] as const)(
  "renders %s in the 2D pane",
  (kind) => {
    render(<AdaptiveViewer visualization={{ ...similarity, kind }} />);
    expect(screen.getByTestId("plotly")).toBeInTheDocument();
  },
);
