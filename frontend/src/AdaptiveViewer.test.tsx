import { fireEvent, render, screen, within } from "@testing-library/react";
import { StrictMode } from "react";

import AdaptiveViewer from "./AdaptiveViewer";

const { createViewerMock, plotly, viewer } = vi.hoisted(() => ({
  createViewerMock: vi.fn(),
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
        "data-testid": "plotly",
      });
    },
  };
});

vi.mock("3dmol", () => ({ createViewer: createViewerMock }));

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
    data: [{ type: "scatter", x: ["CHEMBL1:0", "CHEMBL1:1", "CHEMBL2:0"], y: [0, 1.2, 0.4] }],
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
      {
        molecule_id: "CHEMBL2",
        conformer_id: "CHEMBL2:0",
        conformer_index: 0,
        relative_energy_kcal_mol: 0.4,
        atoms: [{ index: 0, element: "N" }, { index: 1, element: "C" }],
        bonds: [{ begin: 0, end: 1, order: 1 }],
        coordinates: [[0, 0, 0], [2, 0, 0]],
      },
    ],
  },
  selectors: {
    molecule_ids: ["CHEMBL1", "CHEMBL2"],
    conformer_ids_by_molecule: {
      CHEMBL1: ["CHEMBL1:0", "CHEMBL1:1"],
      CHEMBL2: ["CHEMBL2:0"],
    },
  },
  identities: [
    { molecule_id: "CHEMBL1", conformer_id: "CHEMBL1:0", conformer_index: 0 },
    { molecule_id: "CHEMBL1", conformer_id: "CHEMBL1:1", conformer_index: 1 },
    { molecule_id: "CHEMBL2", conformer_id: "CHEMBL2:0", conformer_index: 0 },
  ],
};

beforeEach(() => {
  createViewerMock.mockReset();
  createViewerMock.mockReturnValue(viewer);
  plotly.mockClear();
  Object.values(viewer).forEach((mock) => mock.mockClear());
});

it("passes labeled axes to Plotly for a two-dimensional result", () => {
  render(<AdaptiveViewer visualization={similarity} />);
  const pane = document.querySelector(".conformer-pane");
  expect(pane).toHaveAttribute("hidden");
  expect(pane).not.toHaveClass("is-active");
  expect(plotly).toHaveBeenCalledWith(expect.objectContaining({
    layout: expect.objectContaining({
      xaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
      yaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
    }),
  }));
  expect(screen.getByRole("figure", { name: /pairwise molecular similarity/i })).toHaveAccessibleDescription(
    "X axis: Molecule index — bundled ChEMBL set. Y axis: Molecule index — bundled ChEMBL set.",
  );
  expect(screen.queryByRole("combobox", { name: /^conformer$/i })).not.toBeInTheDocument();
});

it("shows 3D controls and keeps the labeled energy graph for conformers", () => {
  render(<AdaptiveViewer visualization={conformers} />);
  expect(document.querySelector(".conformer-pane")).toHaveClass("is-active");
  expect(screen.getByLabelText(/molecule/i)).toHaveValue("CHEMBL1");
  expect(screen.getByLabelText(/^conformer$/i)).toHaveValue("CHEMBL1:0");
  expect(screen.getByLabelText(/rendering style/i)).toHaveValue("stick");
  expect(screen.getByRole("group", { name: /3d molecular conformer/i })).toHaveAccessibleDescription(
    /interactive molecular structure/i,
  );
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

it("populates and applies every conformer control", () => {
  render(<AdaptiveViewer visualization={conformers} />);
  const molecule = screen.getByLabelText(/molecule/i);
  expect(within(molecule).getAllByRole("option")).toHaveLength(2);

  fireEvent.change(molecule, { target: { value: "CHEMBL2" } });

  expect(screen.getByLabelText(/^conformer$/i)).toHaveValue("CHEMBL2:0");
  expect(viewer.addModel).toHaveBeenLastCalledWith(expect.stringContaining("2.0000"), "mol");
  fireEvent.change(screen.getByLabelText(/rendering style/i), {
    target: { value: "sphere" },
  });
  expect(viewer.setStyle).toHaveBeenLastCalledWith(
    {},
    { sphere: { colorscheme: "Jmol", scale: 0.32 } },
  );
});

it("reuses one page viewer across 3D to 2D to 3D transitions", () => {
  const { rerender } = render(<AdaptiveViewer visualization={conformers} />);
  expect(createViewerMock).toHaveBeenCalledTimes(1);
  expect(viewer.addModel).toHaveBeenCalledTimes(1);

  rerender(<AdaptiveViewer visualization={similarity} />);
  expect(createViewerMock).toHaveBeenCalledTimes(1);
  expect(viewer.clear).toHaveBeenCalled();

  rerender(<AdaptiveViewer visualization={conformers} />);
  expect(createViewerMock).toHaveBeenCalledTimes(1);
  expect(viewer.addModel).toHaveBeenCalledTimes(2);
});

it("creates exactly one live viewer under React StrictMode", () => {
  render(<StrictMode><AdaptiveViewer visualization={conformers} /></StrictMode>);
  expect(createViewerMock).toHaveBeenCalledTimes(1);
});

it("clears the retained viewer for an empty or logged-out state", () => {
  const { rerender } = render(<AdaptiveViewer visualization={conformers} />);
  viewer.clear.mockClear();

  rerender(<AdaptiveViewer visualization={null} />);

  expect(createViewerMock).toHaveBeenCalledTimes(1);
  expect(viewer.clear).toHaveBeenCalledTimes(1);
  expect(viewer.render).toHaveBeenCalled();
  expect(document.querySelector(".conformer-pane")).not.toBeVisible();
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
  expect(viewer.clear).toHaveBeenCalledTimes(2);
  expect(viewer.addModel).toHaveBeenCalledTimes(2);
  expect(viewer.addModel.mock.calls[1][0]).toContain("1.0000");
});

it.each(["fingerprint_density", "similarity", "clusters"] as const)(
  "renders %s in the 2D pane",
  (kind) => {
    render(<AdaptiveViewer visualization={{ ...similarity, kind }} />);
    expect(screen.getByTestId("plotly")).toBeInTheDocument();
    expect(screen.getByRole("figure")).toBeInTheDocument();
  },
);
