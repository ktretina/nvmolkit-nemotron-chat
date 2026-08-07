# Similarity Heatmap Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the 256 by 256 similarity matrix as a readable square heatmap with eight sparse ChEMBL ticks, a compact adjacent colorbar, and unchanged complete hover data.

**Architecture:** Keep scientific data and sparse-tick selection in the backend Plotly payload, where molecule ordering is authoritative. Let the existing frontend Plotly wrapper remain visualization-neutral, changing only its margin merge so graph-specific fields override generic defaults. Lock the payload contract with Python tests, the wrapper contract with Vitest, and actual label geometry with the production-CSS Playwright harness.

**Tech Stack:** Python 3.12, pytest, React 19, TypeScript 7, Plotly.js 3.7, Vitest 4, Playwright 1.62

---

## File map

- `backend/app/visualizations.py`: select sparse axis ticks and emit similarity-specific Plotly layout.
- `backend/app/main.py`: convert Plotly line breaks to spaces at the plain-text interpretation boundary.
- `tests/test_visualizations.py`: verify tick selection, complete data retention, square scaling, colorbar, and margins.
- `frontend/src/AdaptiveViewer.tsx`: merge backend margin fields over shared Plotly defaults.
- `frontend/src/AdaptiveViewer.test.tsx`: verify the field-level margin merge and updated accessible axis labels.
- `frontend/src/styles.css`: provide a definite responsive canvas height for similarity figures only.
- `frontend/e2e/live-ux.spec.ts`: exercise a 256 by 256 production-CSS heatmap and assert rendered geometry.
- `docs/superpowers/specs/2026-08-06-similarity-heatmap-readability-design.md`: approved behavioral source of truth; no further changes expected during implementation.

Because the approved specification requires a pause before committing, the usual per-task commits are replaced by explicit uncommitted checkpoints. Do not commit, push, publish, or modify Brev while executing this plan.

### Task 1: Lock and implement the backend heatmap payload

**Files:**
- Modify: `tests/test_visualizations.py:50-89`
- Modify: `backend/app/visualizations.py:38-89`
- Modify: `backend/app/visualizations.py:260-272`

- [ ] **Step 1: Replace the current similarity assertions and add large/small tick-contract tests**

In `tests/test_visualizations.py`, replace `test_similarity_heatmap_has_axes_scale_and_aligned_id_hover` and add the two following tests immediately after it:

```python
def test_similarity_heatmap_has_axes_scale_and_aligned_id_hover() -> None:
    graph = build_similarity_heatmap(
        {"molecule_ids": ["CHEMBL1", "CHEMBL2"], "matrix": [[1.0, 0.4], [0.4, 1.0]]}
    )
    trace = graph["data"][0]
    layout = graph["layout"]

    assert graph["kind"] == "similarity"
    assert _layout_titles(graph) == (
        "Pairwise molecular similarity",
        "Bundled ChEMBL molecule",
        "Bundled ChEMBL molecule",
    )
    assert trace["x"] == ["CHEMBL1", "CHEMBL2"]
    assert trace["y"] == ["CHEMBL1", "CHEMBL2"]
    assert trace["z"] == [[1.0, 0.4], [0.4, 1.0]]
    assert (trace["zmin"], trace["zmax"]) == (0, 1)
    assert trace["colorbar"] == {
        "title": {"text": "Tanimoto<br>similarity", "side": "top"},
        "tickmode": "array",
        "tickvals": [0, 0.5, 1],
        "ticktext": ["0", "0.5", "1"],
        "x": 0.84,
        "xanchor": "left",
        "xpad": 8,
        "y": 0.5,
        "yanchor": "middle",
        "len": 0.76,
        "thickness": 18,
    }
    assert layout["xaxis"]["tickvals"] == ["CHEMBL1", "CHEMBL2"]
    assert layout["yaxis"]["tickvals"] == ["CHEMBL1", "CHEMBL2"]
    assert "%{x}" in trace["hovertemplate"] and "%{y}" in trace["hovertemplate"]


def test_similarity_heatmap_sparsifies_256_ticks_without_sparsifying_data() -> None:
    ids = [f"CHEMBL{index:04d}" for index in range(256)]
    matrix = [
        [1.0 if row == column else 0.2 for column in range(256)]
        for row in range(256)
    ]
    graph = build_similarity_heatmap({"molecule_ids": ids, "matrix": matrix})
    layout = graph["layout"]
    expected_ticks = [ids[round(index * 255 / 7)] for index in range(8)]

    assert layout["xaxis"] == {
        "title": {"text": "Bundled ChEMBL molecule"},
        "tickmode": "array",
        "tickvals": expected_ticks,
        "ticktext": expected_ticks,
        "tickangle": -45,
        "automargin": True,
        "constrain": "domain",
        "domain": [0, 0.8],
    }
    assert layout["yaxis"] == {
        "title": {"text": "Bundled ChEMBL molecule"},
        "tickmode": "array",
        "tickvals": expected_ticks,
        "ticktext": expected_ticks,
        "automargin": True,
        "scaleanchor": "x",
        "scaleratio": 1,
        "constrain": "domain",
    }
    assert layout["margin"] == {"l": 104, "r": 96, "t": 58, "b": 112, "pad": 4}
    assert graph["data"][0]["x"] == ids
    assert graph["data"][0]["y"] == ids
    assert graph["data"][0]["z"] == matrix


@pytest.mark.parametrize("count", range(1, 9))
def test_similarity_heatmap_keeps_every_tick_for_small_inputs(count: int) -> None:
    ids = [f"CHEMBL{index}" for index in range(count)]
    matrix = [
        [1.0 if row == column else 0.2 for column in range(count)]
        for row in range(count)
    ]
    graph = build_similarity_heatmap({"molecule_ids": ids, "matrix": matrix})

    assert graph["layout"]["xaxis"]["tickvals"] == ids
    assert graph["layout"]["yaxis"]["tickvals"] == ids
```

- [ ] **Step 2: Run the focused tests and verify the new contract fails**

Run from the repository root:

```bash
backend/.venv/bin/python -m pytest tests/test_visualizations.py -q
```

Expected: FAIL because the current payload has the old axis titles, no sparse tick arrays, no square-scale constraint, generic colorbar metadata, and no custom margin.

- [ ] **Step 3: Add deterministic tick selection and the approved similarity layout**

In `backend/app/visualizations.py`, add this helper immediately before `build_similarity_heatmap`:

```python
def _sparse_axis_ticks(identifiers: Sequence[str], *, maximum: int = 8) -> list[str]:
    """Return ordered, inclusive, evenly spaced labels for a categorical axis."""

    if len(identifiers) <= maximum:
        return list(identifiers)
    last_index = len(identifiers) - 1
    return [
        identifiers[round(tick_index * last_index / (maximum - 1))]
        for tick_index in range(maximum)
    ]
```

Inside `build_similarity_heatmap`, after `values` is populated, assign `tick_values = _sparse_axis_ticks(id_values)`. Replace the `_plotly_graph` call and post-process its layout as follows:

```python
    tick_values = _sparse_axis_ticks(id_values)
    graph = _plotly_graph(
        kind="similarity",
        title="Pairwise molecular similarity",
        x_title="Bundled ChEMBL molecule",
        y_title="Bundled ChEMBL molecule",
        trace={
            "type": "heatmap",
            "z": values,
            "x": id_values,
            "y": id_values,
            "zmin": 0,
            "zmax": 1,
            "colorbar": {
                "title": {"text": "Tanimoto<br>similarity", "side": "top"},
                "tickmode": "array",
                "tickvals": [0, 0.5, 1],
                "ticktext": ["0", "0.5", "1"],
                "x": 0.84,
                "xanchor": "left",
                "xpad": 8,
                "y": 0.5,
                "yanchor": "middle",
                "len": 0.76,
                "thickness": 18,
            },
            "hovertemplate": (
                "ChEMBL row %{y}<br>ChEMBL column %{x}<br>"
                "Tanimoto similarity: %{z:.3f}<extra></extra>"
            ),
        },
    )
    graph["layout"].update(
        margin={"l": 104, "r": 96, "t": 58, "b": 112, "pad": 4},
        xaxis={
            "title": {"text": "Bundled ChEMBL molecule"},
            "tickmode": "array",
            "tickvals": tick_values,
            "ticktext": tick_values,
            "tickangle": -45,
            "automargin": True,
            "constrain": "domain",
            "domain": [0, 0.8],
        },
        yaxis={
            "title": {"text": "Bundled ChEMBL molecule"},
            "tickmode": "array",
            "tickvals": tick_values,
            "ticktext": tick_values,
            "automargin": True,
            "scaleanchor": "x",
            "scaleratio": 1,
            "constrain": "domain",
        },
    )
```

Keep the existing `return _validated_json(graph)` immediately after this block.

- [ ] **Step 4: Run focused backend tests and verify they pass**

```bash
backend/.venv/bin/python -m pytest tests/test_visualizations.py -q
```

Expected: all visualization tests PASS.

- [ ] **Step 5: Record the uncommitted backend checkpoint**

```bash
git diff --check
git status --short
```

Expected: the approved spec, this plan, `backend/app/visualizations.py`, and `tests/test_visualizations.py` are modified or untracked; there is no commit.

### Task 2: Preserve graph-specific margins in the Plotly wrapper

**Files:**
- Modify: `frontend/src/AdaptiveViewer.test.tsx:18-70`
- Modify: `frontend/src/AdaptiveViewer.tsx:1-53`

- [ ] **Step 1: Update the unit fixture and write the failing margin-merge assertion**

In the `similarity` fixture in `frontend/src/AdaptiveViewer.test.tsx`, use the corrected axis titles and add one partial graph margin:

```typescript
  layout: {
    title: { text: "Pairwise molecular similarity" },
    xaxis: { title: { text: "Bundled ChEMBL molecule" } },
    yaxis: { title: { text: "Bundled ChEMBL molecule" } },
    margin: { l: 104 },
  },
```

Update the existing `passes labeled axes` test to expect the corrected titles and accessible description. Then add:

```typescript
it("merges graph-specific margins over the shared Plotly defaults", () => {
  render(<AdaptiveViewer visualization={similarity} />);

  expect(plotly).toHaveBeenCalledWith(expect.objectContaining({
    layout: expect.objectContaining({
      margin: { l: 104, r: 32, t: 58, b: 72 },
    }),
  }));
});
```

- [ ] **Step 2: Run the focused frontend test and verify it fails**

```bash
npm --prefix frontend test -- --run src/AdaptiveViewer.test.tsx
```

Expected: FAIL because `ScientificPlot` currently replaces `margin.l` with `72`.

- [ ] **Step 3: Implement the field-level margin merge**

In `frontend/src/AdaptiveViewer.tsx`, import `Margin` and define the defaults near the element-color constant:

```typescript
import type { Data, Layout, Margin } from "plotly.js";

const DEFAULT_PLOT_MARGIN: Partial<Margin> = { l: 72, r: 32, t: 58, b: 72 };
```

At the start of `ScientificPlot`, derive the optional graph margin:

```typescript
  const graphMargin = (graph.layout.margin ?? {}) as Partial<Margin>;
```

Replace the fixed `margin` property passed to Plotly with:

```typescript
          margin: { ...DEFAULT_PLOT_MARGIN, ...graphMargin },
```

- [ ] **Step 4: Run the focused frontend test and typecheck**

```bash
npm --prefix frontend test -- --run src/AdaptiveViewer.test.tsx
npm --prefix frontend run typecheck
```

Expected: AdaptiveViewer tests PASS and TypeScript exits successfully.

- [ ] **Step 5: Record the uncommitted frontend checkpoint**

```bash
git diff --check
git status --short
```

Expected: the backend checkpoint plus `frontend/src/AdaptiveViewer.tsx` and `frontend/src/AdaptiveViewer.test.tsx` are modified; there is no commit.

### Task 3: Add a production-CSS geometry regression

**Files:**
- Modify: `frontend/src/AdaptiveViewer.test.tsx:103-140`
- Modify: `frontend/src/AdaptiveViewer.tsx:29-55`
- Modify: `frontend/src/styles.css:104-112`
- Modify: `frontend/e2e/live-ux.spec.ts:1-120`

- [ ] **Step 1: Lock a kind-specific figure class before changing responsive geometry**

Add this assertion to the existing two-dimensional result test in `frontend/src/AdaptiveViewer.test.tsx`:

```typescript
  expect(screen.getByRole("figure", { name: /pairwise molecular similarity/i }))
    .toHaveClass("plot-frame--similarity");
```

Run `npm --prefix frontend test -- --run src/AdaptiveViewer.test.tsx`. Expected: FAIL because the figure currently has only `plot-frame`.

Change the figure opening tag in `ScientificPlot` to:

```tsx
    <figure
      className={`plot-frame plot-frame--${graph.kind}`}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
```

Add this rule immediately after the shared `.plot-frame` rule in `frontend/src/styles.css`:

```css
.plot-frame--similarity { min-height: 0; aspect-ratio: 1.25; }
```

Rerun the focused unit test. Expected: all AdaptiveViewer tests PASS.

- [ ] **Step 2: Replace the two-cell similarity fixture with a representative 256-cell-axis fixture**

Immediately before the `similarity` fixture in `frontend/e2e/live-ux.spec.ts`, add:

```typescript
const similarityIds = Array.from({ length: 256 }, (_, index) => `CHEMBL${String(index).padStart(4, "0")}`);
const similarityTicks = Array.from(
  { length: 8 },
  (_, index) => similarityIds[Math.round(index * 255 / 7)],
);
const similarityMatrix = similarityIds.map((_, row) => similarityIds.map((__, column) => (
  row === column
    ? 1
    : Number((0.08 + 0.24 * Math.exp(-Math.abs(row - column) / 24)).toFixed(3))
)));
```

Replace the similarity trace and layout with the approved payload:

```typescript
const similarity = {
  kind: "similarity",
  data: [{
    type: "heatmap",
    z: similarityMatrix,
    x: similarityIds,
    y: similarityIds,
    zmin: 0,
    zmax: 1,
    colorbar: {
      title: { text: "Tanimoto<br>similarity", side: "top" },
      tickmode: "array",
      tickvals: [0, 0.5, 1],
      ticktext: ["0", "0.5", "1"],
      x: 0.84,
      xanchor: "left",
      xpad: 8,
      y: 0.5,
      yanchor: "middle",
      len: 0.76,
      thickness: 18,
    },
  }],
  layout: {
    title: { text: "Pairwise molecular similarity" },
    margin: { l: 104, r: 96, t: 58, b: 112, pad: 4 },
    xaxis: {
      title: { text: "Bundled ChEMBL molecule" },
      tickmode: "array",
      tickvals: similarityTicks,
      ticktext: similarityTicks,
      tickangle: -45,
      automargin: true,
      constrain: "domain",
      domain: [0, 0.8],
    },
    yaxis: {
      title: { text: "Bundled ChEMBL molecule" },
      tickmode: "array",
      tickvals: similarityTicks,
      ticktext: similarityTicks,
      automargin: true,
      scaleanchor: "x",
      scaleratio: 1,
      constrain: "domain",
    },
  },
  interpretation: "The bundled set contains 256 compounds with exact pairwise scores.",
  interpretation_unavailable: false,
};
```

- [ ] **Step 3: Add geometry helpers and the failing browser assertions**

Add this type and helper after the prompts constant:

```typescript
type Box = { x: number; y: number; width: number; height: number };

function boxesOverlap(first: Box, second: Box): boolean {
  return first.x < second.x + second.width
    && first.x + first.width > second.x
    && first.y < second.y + second.height
    && first.y + first.height > second.y;
}
```

Change the desktop 2D test signature to receive `testInfo`, then add these assertions after the figure becomes visible:

```typescript
  const figure = page.getByRole("figure", { name: /Pairwise molecular similarity/ });
  const xTicks = figure.locator(".xaxislayer-above .xtick text");
  const yTicks = figure.locator(".yaxislayer-above .ytick text");
  await expect(xTicks).toHaveCount(8);
  await expect(yTicks).toHaveCount(8);
  await expect(xTicks).toHaveText(similarityTicks);
  await expect(yTicks).toHaveText(similarityTicks);

  const xTickBoxes = await xTicks.evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect();
    return { x: box.x, y: box.y, width: box.width, height: box.height };
  }));
  const yTickBoxes = await yTicks.evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect();
    return { x: box.x, y: box.y, width: box.width, height: box.height };
  }));
  for (let index = 1; index < xTickBoxes.length; index += 1) {
    expect(boxesOverlap(xTickBoxes[index - 1], xTickBoxes[index])).toBe(false);
    expect(boxesOverlap(yTickBoxes[index - 1], yTickBoxes[index])).toBe(false);
  }

  const matrixBox = await figure.locator(".heatmaplayer image").first().boundingBox();
  const colorbarBox = await figure.locator("g.colorbar .cbfill").first().boundingBox();
  expect(matrixBox).not.toBeNull();
  expect(colorbarBox).not.toBeNull();
  expect(Math.abs(matrixBox!.width - matrixBox!.height)).toBeLessThanOrEqual(3);
  expect(colorbarBox!.x).toBeGreaterThanOrEqual(matrixBox!.x + matrixBox!.width);
  expect(colorbarBox!.x - (matrixBox!.x + matrixBox!.width)).toBeLessThanOrEqual(120);

  const screenshotPath = testInfo.outputPath("similarity-heatmap-desktop.png");
  await figure.screenshot({ path: screenshotPath });
  await testInfo.attach("similarity-heatmap-desktop", {
    path: screenshotPath,
    contentType: "image/png",
  });
```

- [ ] **Step 4: Run the focused browser test**

```bash
npm --prefix frontend run build
npm --prefix frontend exec -- playwright test e2e/live-ux.spec.ts --grep "keeps the composer and a 2D figure"
```

Expected before backend/layout fixture completion: FAIL on dense tick count or geometry. Expected after the approved fixture and frontend margin merge: PASS with one screenshot attachment.

- [ ] **Step 5: Inspect the screenshot attachment**

List the generated artifact:

```bash
rg --files frontend/test-results | rg 'similarity-heatmap-desktop|\.png$'
```

Open the returned PNG with the workspace image viewer. Confirm visually that all eight x labels and eight y labels are readable, the matrix is square, the colorbar is adjacent, and no label is clipped.

- [ ] **Step 6: Record the uncommitted browser checkpoint**

```bash
git diff --check
git status --short
```

Expected: `frontend/e2e/live-ux.spec.ts` joins the existing local changes; generated `frontend/test-results` artifacts remain ignored; there is no commit.

### Task 4: Run the complete local acceptance gate

**Files:**
- Verify only; do not modify publication or Brev files.

- [ ] **Step 1: Run the full backend suite**

If `test_interpreter_receives_textual_metadata_only_not_artifact` exposes visual `<br>` markup in interpretation metadata, keep the visual title unchanged and normalize only the metadata extractor:

```python
import re

_PLOTLY_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)

# Inside _textual_metadata.title:
if not isinstance(value, str):
    return None
normalized = " ".join(_PLOTLY_LINE_BREAK.sub(" ", value).split())
return normalized or None
```

```bash
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
```

Expected: all non-GPU backend tests PASS; the GPU acceptance test remains explicitly deselected or skipped unless `RUN_GPU_TESTS=1` is supplied.

- [ ] **Step 2: Run the full frontend unit, type, and build gates**

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Expected: all Vitest tests PASS, TypeScript exits successfully, and Vite completes a production build.

- [ ] **Step 3: Run the complete production-CSS browser suite**

```bash
npm --prefix frontend run test:e2e
```

Expected: all desktop and mobile Playwright tests PASS, including the new 256 by 256 similarity geometry checks.

- [ ] **Step 4: Inspect final scope and whitespace**

```bash
git diff --check
git status --short
git diff --stat
```

Expected: changes are limited to the approved design, this plan, the backend visualization builder/test, the frontend Plotly wrapper/test, and the browser regression test.

- [ ] **Step 5: Stop at the publication gate**

Report the exact test counts, screenshot evidence, changed files, and remaining uncertainty. Request explicit approval before committing, pushing, publishing an image, replacing the Brev service, changing the Launchable, or creating another deployment.
