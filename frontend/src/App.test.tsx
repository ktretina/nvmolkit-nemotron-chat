import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import App from "./App";

const { appCreateViewer, appViewer } = vi.hoisted(() => ({
  appCreateViewer: vi.fn(),
  appViewer: {
    clear: vi.fn(),
    addModel: vi.fn(),
    setStyle: vi.fn(),
    zoomTo: vi.fn(),
    render: vi.fn(),
  },
}));

vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="plotly" />,
}));

vi.mock("3dmol", () => ({ createViewer: appCreateViewer }));

const graph = {
  kind: "similarity",
  data: [{ type: "heatmap", z: [[1]], x: ["CHEMBL1"], y: ["CHEMBL1"] }],
  layout: {
    title: { text: "Pairwise molecular similarity" },
    xaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
    yaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
  },
  interpretation: "The bundled set contains one self-match.",
  interpretation_unavailable: false,
} as const;

const conformerGraph = {
  kind: "conformers",
  energy_plot: {
    kind: "plotly",
    data: [{ type: "scatter", x: ["CHEMBL1:0"], y: [0] }],
    layout: {
      title: { text: "Sampled conformer energies" },
      xaxis: { title: { text: "Conformer ID" } },
      yaxis: { title: { text: "Relative MMFF94 energy (kcal/mol)" } },
    },
  },
  viewer: {
    kind: "3dmol",
    atom_legend: true,
    xyz_triad: true,
    structures: [{
      molecule_id: "CHEMBL1",
      conformer_id: "CHEMBL1:0",
      conformer_index: 0,
      relative_energy_kcal_mol: 0,
      atoms: [{ index: 0, element: "C" }],
      bonds: [],
      coordinates: [[0, 0, 0]],
    }],
  },
  selectors: { molecule_ids: ["CHEMBL1"], conformer_ids_by_molecule: { CHEMBL1: ["CHEMBL1:0"] } },
  identities: [{ molecule_id: "CHEMBL1", conformer_id: "CHEMBL1:0", conformer_index: 0 }],
  interpretation: "One conformer is available.",
  interpretation_unavailable: false,
} as const;

const exactPrompts = [
  "Show the Morgan fingerprint density across the bundled molecules.",
  "Map structural similarity across the bundled dataset.",
  "Cluster the molecules by structural similarity and show the cluster sizes.",
  "Generate and compare optimized 3D conformers for representative molecules.",
];

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

function mockFetch(...responses: Response[]) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
    const next = responses.shift();
    if (!next) throw new Error("unexpected fetch");
    return next;
  });
}

beforeEach(() => {
  appCreateViewer.mockReset();
  appCreateViewer.mockReturnValue(appViewer);
  Object.values(appViewer).forEach((mock) => mock.mockClear());
});

it("requires a masked key before showing chat", async () => {
  mockFetch(response({ authenticated: false, visualization: null }));
  render(<App />);

  expect(await screen.findByLabelText(/nvidia api key/i)).toHaveAttribute("type", "password");
  expect(screen.queryByRole("button", { name: /map structural similarity/i })).not.toBeInTheDocument();
});

it("submits the key only to the backend, clears it, and never uses browser storage", async () => {
  const fetchMock = mockFetch(
    response({ authenticated: false, visualization: null }),
    response({ authenticated: true }),
  );
  const localSet = vi.spyOn(Storage.prototype, "setItem");
  render(<App />);
  const input = await screen.findByLabelText(/nvidia api key/i);
  fireEvent.change(input, { target: { value: "nvapi-test-secret" } });
  fireEvent.click(screen.getByRole("button", { name: /start session/i }));

  await screen.findAllByTestId("suggested-prompt");
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/session/key",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      body: JSON.stringify({ api_key: "nvapi-test-secret" }),
    }),
  );
  expect(screen.queryByDisplayValue("nvapi-test-secret")).not.toBeInTheDocument();
  expect(localSet).not.toHaveBeenCalled();
});

it("renders all four suggested prompts after authentication", async () => {
  mockFetch(response({ authenticated: true, visualization: null }));
  render(<App />);
  const prompts = await screen.findAllByTestId("suggested-prompt");
  expect(prompts.map((prompt) => prompt.textContent)).toEqual(exactPrompts);
});

it("moves the guaranteed prompts into a compact menu once chat begins", async () => {
  const fetchMock = mockFetch(
    response({ authenticated: true, visualization: null }),
    response({ visualization: graph }),
    response({ visualization: graph }),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: exactPrompts[1] }));

  expect(screen.queryAllByTestId("suggested-prompt")).toHaveLength(0);
  const menu = await screen.findByText(/validated analyses/i);
  expect(menu.closest("details")).toBeInTheDocument();
  fireEvent.click(menu);
  fireEvent.click(screen.getByRole("button", { name: exactPrompts[2] }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toEqual({ prompt_id: "clusters" });
});

it("sends a suggested prompt ID directly and a free-form message separately", async () => {
  const fetchMock = mockFetch(
    response({ authenticated: true, visualization: null }),
    response({ visualization: graph }),
    response({ visualization: graph }),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: exactPrompts[1] }));
  await screen.findByText(/one self-match/i);
  expect(screen.getByRole("heading", { name: "analyze_similarity_map" })).toBeInTheDocument();
  expect(screen.getByText(`Result for: “${exactPrompts[1]}”`)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/ask about the bundled molecules/i), {
    target: { value: "Show molecular groups" },
  });
  fireEvent.click(screen.getByRole("button", { name: /send message/i }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({ prompt_id: "similarity" });
  expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toEqual({ message: "Show molecular groups" });
});

it("keeps the latest figure visible when a later request fails", async () => {
  mockFetch(
    response({ authenticated: true, visualization: null }),
    response({ visualization: graph }),
    response({ detail: "Chemistry runtime is unavailable." }, false, 503),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: exactPrompts[1] }));
  expect(await screen.findByRole("figure", { name: /pairwise molecular similarity/i })).toBeInTheDocument();
  fireEvent.click(screen.getByText(/validated analyses/i));
  fireEvent.click(screen.getByRole("button", { name: exactPrompts[2] }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/chemistry runtime is unavailable/i);
  expect(screen.getByRole("figure", { name: /pairwise molecular similarity/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "analyze_similarity_map" })).toBeInTheDocument();
  expect(screen.getByText(/retained from the earlier successful request/i)).toHaveTextContent(exactPrompts[1]);
  expect(screen.getByText(/latest request failed/i)).toHaveTextContent(exactPrompts[2]);
});

it("clears the ephemeral session on logout", async () => {
  const fetchMock = mockFetch(
    response({ authenticated: true, visualization: graph }),
    response({ authenticated: false }),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /clear session/i }));

  expect(await screen.findByLabelText(/nvidia api key/i)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/session",
    expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
  );
});

it("retains one 3D viewer through logout and reauthentication", async () => {
  mockFetch(
    response({ authenticated: true, visualization: conformerGraph }),
    response({ authenticated: false }),
    response({ authenticated: true }),
    response({ visualization: conformerGraph }),
  );
  render(<App />);
  await screen.findByRole("group", { name: /3d molecular conformer/i });
  expect(appCreateViewer).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: /clear session/i }));
  const key = await screen.findByLabelText(/nvidia api key/i);
  expect(appViewer.clear).toHaveBeenCalled();
  fireEvent.change(key, { target: { value: "nvapi-new-session" } });
  fireEvent.click(screen.getByRole("button", { name: /start session/i }));
  fireEvent.click(await screen.findByRole("button", { name: exactPrompts[3] }));
  await screen.findByText(/one conformer is available/i);

  expect(appCreateViewer).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(appViewer.addModel).toHaveBeenCalledTimes(2));
});

it("exposes accessible status and responsive layout hooks", async () => {
  mockFetch(response({ authenticated: true, visualization: null }));
  render(<App />);
  expect(await screen.findByRole("main")).toHaveClass("app-shell");
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  expect(screen.getByRole("region", { name: /scientific visualization/i })).toBeInTheDocument();
});
