import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import App from "./App";

vi.mock("react-plotly.js", () => ({
  default: ({ layout }: { layout: { title?: { text?: string } } }) => (
    <div role="img" aria-label={layout.title?.text ?? "Scientific graph"} />
  ),
}));

vi.mock("3dmol", () => ({ createViewer: vi.fn() }));

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
  expect(await screen.findAllByTestId("suggested-prompt")).toHaveLength(4);
});

it("sends a suggested prompt ID directly and a free-form message separately", async () => {
  const fetchMock = mockFetch(
    response({ authenticated: true, visualization: null }),
    response({ visualization: graph }),
    response({ visualization: graph }),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /map structural similarity/i }));
  await screen.findByText(/one self-match/i);
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
  fireEvent.click(await screen.findByRole("button", { name: /map structural similarity/i }));
  expect(await screen.findByRole("img", { name: /pairwise molecular similarity/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /find molecular clusters/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/chemistry runtime is unavailable/i);
  expect(screen.getByRole("img", { name: /pairwise molecular similarity/i })).toBeInTheDocument();
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

it("exposes accessible status and responsive layout hooks", async () => {
  mockFetch(response({ authenticated: true, visualization: null }));
  render(<App />);
  expect(await screen.findByRole("main")).toHaveClass("app-shell");
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  expect(screen.getByRole("region", { name: /scientific visualization/i })).toBeInTheDocument();
});
