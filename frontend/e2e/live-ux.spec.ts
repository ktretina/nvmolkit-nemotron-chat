import { expect, test, type Page } from "@playwright/test";

const similarity = {
  kind: "similarity",
  data: [{
    type: "heatmap",
    z: [[1, 0.42], [0.42, 1]],
    x: ["CHEMBL1", "CHEMBL2"],
    y: ["CHEMBL1", "CHEMBL2"],
    colorbar: { title: { text: "Tanimoto similarity (unitless)" } },
  }],
  layout: {
    title: { text: "Pairwise molecular similarity" },
    xaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
    yaxis: { title: { text: "Molecule index — bundled ChEMBL set" } },
  },
  interpretation: "The bundled set contains two self-matches.",
  interpretation_unavailable: false,
};

const conformers = {
  kind: "conformers",
  energy_plot: {
    kind: "plotly",
    data: [{
      type: "scatter",
      x: ["CHEMBL1:0", "CHEMBL1:1", "CHEMBL2:0"],
      y: [0, 1.2, 0.4],
    }],
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
  interpretation: "Three bounded conformers are available.",
  interpretation_unavailable: false,
};

const prompts = {
  similarity: "Map structural similarity across the bundled dataset.",
  conformers: "Generate and compare optimized 3D conformers for representative molecules.",
};

async function mockApi(page: Page) {
  let authenticated = true;
  let visualization: typeof similarity | typeof conformers | null = null;

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    let body: unknown;

    if (url.pathname === "/api/session" && request.method() === "GET") {
      body = { authenticated, visualization, provider_status: "unchecked" };
    } else if (url.pathname === "/api/session/reset" && request.method() === "POST") {
      visualization = null;
      body = { authenticated: true, visualization: null, provider_status: "unchecked" };
    } else if (url.pathname === "/api/session" && request.method() === "DELETE") {
      authenticated = false;
      visualization = null;
      body = { authenticated: false };
    } else if (url.pathname === "/api/chat" && request.method() === "POST") {
      const input = request.postDataJSON() as { prompt_id?: string; message?: string };
      visualization = input.prompt_id === "conformers" ? conformers : similarity;
      body = { visualization, provider_status: "available" };
    } else {
      await route.abort("failed");
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function openValidatedAnalyses(page: Page) {
  const menu = page.locator("details.compact-prompt-menu");
  if (!(await menu.evaluate((element) => (element as HTMLDetailsElement).open))) {
    await menu.locator("summary").click();
  }
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("keeps the composer and a 2D figure inside the desktop viewport", async ({ page }) => {
  await page.setViewportSize({ width: 1563, height: 1103 });
  await page.goto("/");

  await expect(page.getByLabel("Ask about the bundled molecules")).toBeInViewport();
  await page.getByRole("button", { name: prompts.similarity }).click();

  await expect(page.getByRole("figure", {
    name: /Pairwise molecular similarity/,
  })).toBeInViewport();
  await expect(page.getByRole("combobox", {
    name: "Molecule",
    exact: true,
  })).toHaveCount(0);
  await expect(page.locator(".conformer-pane")).toHaveCSS("display", "none");
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
});

test("keeps one conformer pane through transitions and separates workspace actions", async ({ page }) => {
  await page.setViewportSize({ width: 1563, height: 1103 });
  await page.goto("/");
  await page.getByRole("button", { name: prompts.conformers }).click();

  const molecule = page.getByRole("combobox", { name: "Molecule", exact: true });
  await expect(molecule.locator("option")).toHaveCount(2);
  await molecule.selectOption("CHEMBL2");
  await expect(page.getByRole("combobox", {
    name: "Conformer",
    exact: true,
  })).toHaveValue("CHEMBL2:0");
  const renderingStyle = page.getByRole("combobox", { name: "Rendering style" });
  await renderingStyle.selectOption("sphere");
  await expect(renderingStyle).toHaveValue("sphere");
  await expect(page.getByLabel("Interactive 3D molecular conformer")).toBeVisible();
  await expect(page.getByRole("figure", { name: /Sampled conformer energies/ })).toBeVisible();
  await page.evaluate(() => {
    (window as unknown as { conformerCanvas: Element | null }).conformerCanvas =
      document.querySelector(".molecule-canvas");
  });

  await openValidatedAnalyses(page);
  await page.getByRole("button", { name: prompts.similarity }).click();
  await expect(page.locator(".conformer-pane")).toHaveCSS("display", "none");
  await openValidatedAnalyses(page);
  await page.getByRole("button", { name: prompts.conformers }).click();
  expect(await page.evaluate(() => (
    (window as unknown as { conformerCanvas: Element | null }).conformerCanvas
      === document.querySelector(".molecule-canvas")
  ))).toBe(true);

  await page.getByRole("button", { name: "New analysis" }).click();
  await expect(page.getByLabel("NVIDIA API key")).toHaveCount(0);
  await expect(page.getByRole("figure")).toHaveCount(0);
  await page.getByRole("button", { name: "End session" }).click();
  await expect(page.getByLabel("NVIDIA API key")).toBeVisible();
});

test("keeps the mobile composer visible and scrolls to a 2D result", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByLabel("Ask about the bundled molecules")).toBeInViewport();
  await page.getByRole("button", { name: prompts.similarity }).click();
  const viewer = page.getByRole("region", { name: "Scientific visualization" });
  await viewer.scrollIntoViewIfNeeded();
  await expect(page.getByRole("figure", { name: /Pairwise molecular similarity/ })).toBeVisible();
  await expect(page.getByRole("combobox", {
    name: "Molecule",
    exact: true,
  })).toHaveCount(0);
});
