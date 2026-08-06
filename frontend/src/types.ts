export type PromptId = "fingerprints" | "similarity" | "clusters" | "conformers";

export type ProviderStatus =
  | "unchecked"
  | "available"
  | "authentication_failed"
  | "rate_limited"
  | "provider_unavailable"
  | "model_unavailable"
  | "invalid_response";

export interface PlotlyTitle {
  text: string;
}

export interface PlotlyGraph {
  kind: "fingerprint_density" | "similarity" | "clusters" | "plotly";
  data: Array<Record<string, unknown>>;
  layout: {
    title: PlotlyTitle;
    xaxis: { title: PlotlyTitle };
    yaxis: { title: PlotlyTitle };
    [key: string]: unknown;
  };
  interpretation?: string | null;
  interpretation_unavailable?: boolean;
}

export type AnalysisPlotlyGraph = Omit<PlotlyGraph, "kind"> & {
  kind: "fingerprint_density" | "similarity" | "clusters";
};

export interface Atom {
  index: number;
  element: string;
}

export interface Bond {
  begin: number;
  end: number;
  order: number;
}

export interface ConformerStructure {
  molecule_id: string;
  conformer_id: string;
  conformer_index: number;
  relative_energy_kcal_mol: number;
  atoms: Atom[];
  bonds: Bond[];
  coordinates: Array<[number, number, number] | number[]>;
}

export interface ConformerVisualization {
  kind: "conformers";
  energy_plot: PlotlyGraph;
  viewer: {
    kind: "3dmol";
    structures: ConformerStructure[];
    atom_legend: boolean;
    xyz_triad: boolean;
  };
  selectors: {
    molecule_ids: string[];
    conformer_ids_by_molecule: Record<string, string[]>;
  };
  identities: Array<{
    molecule_id: string;
    conformer_id: string;
    conformer_index: number;
  }>;
  interpretation?: string | null;
  interpretation_unavailable?: boolean;
}

export type Visualization = AnalysisPlotlyGraph | ConformerVisualization;

export interface SessionResponse {
  authenticated: boolean;
  visualization: Visualization | null;
  provider_status: ProviderStatus;
}

export interface ChatResponse {
  visualization: Visualization;
  provider_status: ProviderStatus;
}

export interface StartWorkspaceResponse {
  authenticated: true;
  provider_status: ProviderStatus;
}

export interface WorkspaceResetResponse {
  authenticated: true;
  visualization: null;
  provider_status: "unchecked";
}
