# Similarity Heatmap Readability Design

**Date:** 2026-08-06  
**Status:** Visual design approved in conversation; written-spec review pending  
**Repository:** `ktretina/nvmolkit-nemotron-chat`  
**Source baseline:** `0ff487f1726669241ae4f6317d44efec7ca6e3f0`  
**Local branch:** `codex/fix-live-nvmolkit-ux-20260806`

## 1. Objective

Make the 256 by 256 pairwise Tanimoto-similarity heatmap readable in the existing responsive viewer without changing the similarity matrix, molecule ordering, hover fidelity, analysis execution, or scientific claim boundary.

The approved treatment is **Sparse ChEMBL IDs**: show a small, deterministic sample of full molecule identifiers as orientation ticks while retaining all identifiers and scores in the Plotly trace for exact hover inspection.

## 2. Evidence and root cause

The live browser result establishes that the similarity workflow now completes, produces a narrative, renders a heatmap, and returns the workspace to `Ready`. The remaining defect is presentation:

1. The backend supplies all 256 ChEMBL identifiers as categorical `x` and `y` coordinates but provides no tick policy.
2. Plotly therefore attempts to render all 256 identifiers on both axes. The labels overlap each other and the plot.
3. The generic frontend Plotly wrapper replaces any graph-specific margin with one fixed margin, so the similarity figure cannot reserve layout space independently of the histogram, cluster chart, or energy plot.
4. The heatmap has no fixed x-to-y scale relationship, allowing the symmetric matrix to render as a wide rectangle.
5. The colorbar title is one long horizontal string. Its default placement is visually detached from the colorbar and consumes excess horizontal space.
6. Browser geometry testing showed that the Plotly element's `height: 100%` resolves to Plotly's roughly 450-pixel fallback because its figure parent has only `min-height`. After margins, the square matrix is only about 280 pixels wide. Eight angled IDs therefore overlap, and a colorbar positioned against the full paper domain sits far from the compressed matrix.

The computation and data alignment are not implicated. The matrix, diagonal, range, hover values, narrative, and request lifecycle are functioning.

## 3. Approved presentation

### 3.1 Sparse axis ticks

For a result containing `n` molecule IDs:

- Show at most eight tick labels per axis.
- If `n <= 8`, show every ID.
- If `n > 8`, select eight indices evenly across the inclusive range `0` through `n - 1`.
- Always include the first and last IDs.
- Use the same selected indices and labels on both axes.
- Keep the complete ordered ID arrays in trace `x` and `y`; do not downsample or rewrite the heatmap data.

For `n > 8`, compute each selected index as `round(i * (n - 1) / 7)` for `i` from `0` through `7`. The tick-selection helper must be deterministic, preserve order, and return unique indices for every valid nonempty input size.

### 3.2 Labels and orientation

- Rename both axis titles from the inaccurate `Molecule index — bundled ChEMBL set` to `Bundled ChEMBL molecule`.
- Render x-axis tick labels at `-45` degrees.
- Keep y-axis tick labels horizontal.
- Show the complete selected ChEMBL IDs rather than shortening them in the payload.
- Enable Plotly automatic margin accommodation on both axes.

Every exact row ID, column ID, and similarity value remains available in the existing hover template.

### 3.3 Matrix geometry

Link the categorical y-axis scale to the x-axis with a 1:1 scale ratio and constrain the axis domain. Reserve x-axis domain `[0, 0.8]` for the matrix and its labels. The rendered matrix cells must therefore remain square as the viewer resizes.

Give similarity figures a dedicated CSS class with a desktop `aspect-ratio` of `1.25` and no inherited `min-height`. This supplies a definite responsive canvas height from the available viewer width, while avoiding a fixed pixel width or horizontal page scrolling. Other Plotly figures keep the existing shared frame behavior.

### 3.4 Colorbar

Use a compact vertical colorbar immediately beside the matrix:

- Title: `Tanimoto<br>similarity`
- Tick values and labels: `0`, `0.5`, and `1`
- `x = 0.84`, `xanchor = left`, `xpad = 8`, and vertical midpoint `y = 0.5`
- `len = 0.76` and `thickness = 18`
- No redundant prose stating the range; the labeled endpoints communicate it

The similarity score remains unitless. The colorbar does not imply a scientific threshold or classification boundary.

### 3.5 Margins

The backend similarity layout supplies `{l: 104, r: 96, t: 58, b: 112, pad: 4}` for the angled x ticks, horizontal y ticks, title, and compact colorbar. The frontend wrapper must merge graph-specific margin fields over its current defaults rather than replacing them.

This merge is field-level. If a graph specifies only one margin field, the other generic defaults remain intact. Existing fingerprint, cluster, and conformer-energy plots retain their current default margins unless their payload explicitly overrides a field.

## 4. Component boundaries

The implementation remains focused in these existing modules:

- `backend/app/visualizations.py`
  - Add a small deterministic sparse-tick helper.
  - Add similarity-specific axis, colorbar, scale, and margin layout fields.
  - Preserve full trace coordinates and matrix values.
- `backend/app/main.py`
  - Normalize Plotly line-break markup to spaces when deriving plain-text interpretation metadata.
- `tests/test_visualizations.py`
  - Lock the sparse-tick contract and complete hover coordinates.
  - Lock the square-scale, label, colorbar, and margin contract.
- `frontend/src/AdaptiveViewer.tsx`
  - Merge graph-provided margin fields over generic defaults.
  - Add a graph-kind modifier class to the existing figure element.
- `frontend/src/AdaptiveViewer.test.tsx`
  - Establish that a partial graph margin is preserved without losing unspecified defaults.
- `frontend/src/styles.css`
  - Give only similarity plots a definite responsive aspect ratio.

No API endpoint, session state, Nemotron routing, nvMolKit computation, dataset, Docker dependency, or 3D viewer behavior changes.

## 5. Verification design

### 5.1 Backend tests

Tests must establish:

- A 256-ID heatmap exposes exactly eight x ticks and eight y ticks.
- The selected x and y tick arrays are identical, ordered, unique, and include IDs at indices `0` and `255`.
- Inputs containing one through eight IDs show every ID exactly once.
- The trace still contains all 256 ordered IDs on both axes and the complete 256 by 256 matrix.
- The axis titles, x tick angle, automatic margins, 1:1 scale constraint, colorbar title, and colorbar ticks match the approved contract.
- Existing rejection of nonfinite, misaligned, nonsquare, and out-of-range similarity inputs remains intact.
- The visual colorbar title remains multiline while Nemotron receives the plain label `Tanimoto similarity` without Plotly markup.

### 5.2 Frontend tests

Tests must establish:

- Similarity layout fields reach Plotly without being replaced.
- A graph-specific partial margin overrides the corresponding default field.
- Unspecified margin fields retain the existing generic defaults.
- Similarity figures receive the kind-specific frame class; other graph kinds retain their own modifier classes without style changes.
- Existing accessible title and axis descriptions remain accurate after the axis-title change.
- Fingerprint, cluster, similarity, conformer, and retained-viewer tests continue to pass.

### 5.3 Local gates

Before any publication or Brev modification:

1. Run the focused backend visualization tests.
2. Run the focused frontend adaptive-viewer tests.
3. Run the complete backend test suite.
4. Run the complete frontend test suite, typecheck, and production build.
5. Inspect the generated Plotly payload for a synthetic 256-ID matrix.
6. Use the existing local browser harness or a direct local browser capture at the desktop acceptance viewport. Confirm that labels do not overlap, the matrix is square, and the colorbar is adjacent.

Passing unit tests alone proves the layout contract, not the final rendered appearance. A browser screenshot is required before calling the visual defect locally resolved.

## 6. Acceptance criteria

The local repair is accepted when:

- No static axis label overlaps another label at the desktop acceptance viewport.
- Eight full ChEMBL IDs or fewer are visible on each axis.
- The first and last molecule IDs are represented on both axes.
- The heatmap matrix is visually square.
- The compact colorbar sits directly beside the matrix and shows `0`, `0.5`, and `1`.
- Hover still reports the exact full row ID, column ID, and Tanimoto score for every cell.
- Other Plotly and 3D visualizations show no layout regression.
- All scoped local gates pass.

## 7. Alternatives considered

### Numeric indices

This would create the cleanest static axes, but it would hide molecular identity until hover. It was not selected because visible ChEMBL context is useful in a scientific explorer.

### Hover-only labels

This would maximize matrix area, but it would remove all static orientation. It was not selected because the user explicitly preferred sparse ChEMBL IDs.

### Render all IDs at a smaller font

This does not solve the information-density problem at 256 categories and would make the labels technically present but functionally unreadable. It is rejected.

## 8. Publication and live boundary

This specification authorizes local code, tests, builds, and local browser validation only. After local acceptance, stop and request explicit approval before committing, pushing, publishing an image, replacing the Brev container, changing the Launchable, or creating a new deployment.

## 9. Self-review outcome

The written design was checked against the current backend visualization builder, frontend Plotly wrapper, frontend payload types, unit tests, and prior live-UX acceptance boundary.

- The axis-title correction is semantic only and keeps accessible descriptions aligned with visible labels.
- The existing `PlotlyGraph.layout` contract already permits additional Plotly layout fields, so this repair does not require a public payload-type expansion.
- Field-level margin merging avoids changing plots that do not opt into custom margins.
- The browser gate is mandatory because payload assertions cannot prove non-overlap or final colorbar placement.
- The work remains local and reversible until the separate publication approval gate.

Implementation-time browser evidence amended the design after the initial self-review: preserving eight full labels requires a definite responsive canvas height, and adjacent colorbar placement requires a reserved x-axis domain. These additions preserve the selected visual treatment and do not change scientific data or remote scope.
