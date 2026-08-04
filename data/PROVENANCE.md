# Sample molecule provenance

- Source repository: https://github.com/ktretina/nvmolkit-brev-notebook
- Accepted source commit: `dd27240e67dfe906412258dd6fafd2262eebd26e`
- Source path: `data/sample_molecules.csv`
- Pinned source URL: https://github.com/ktretina/nvmolkit-brev-notebook/blob/dd27240e67dfe906412258dd6fafd2262eebd26e/data/sample_molecules.csv
- Adaptation: exact-content copy of the source CSV at the accepted commit
- Data rows: 256 (excluding the header)
- Columns: `molecule_id`, `smiles`

## Upstream dataset provenance

The accepted source repository's `data/PROVENANCE.md` records the upstream ChEMBL provenance as follows:

- Approved and successful retrieval URL: https://www.ebi.ac.uk/chembl/api/data/molecule.json?limit=1000&offset=0
- Retrieval date: 2026-07-31 UTC (HTTP response date: Fri, 31 Jul 2026 21:35:24 GMT)
- Raw response SHA-256: `8bd9308a97851d57f31e497102fcacc0a2a9b971b5e1ff4b932a8f40c3322252`
- [ChEMBL data licensing information](https://chembl.gitbook.io/chembl-interface-documentation/about#data-licensing)

The response contained 1,000 molecule records. In the returned order, the source sample retained the first 256 records with a nonempty `molecule_chembl_id` and a nonempty `molecule_structures.canonical_smiles` value that RDKit parses. Each retained structure was canonicalized with `Chem.MolToSmiles(molecule, canonical=True)` and written with only its molecule ID and canonical SMILES.

This sample is provided only for a molecular-analysis software demonstration. It is not a scientifically validated dataset and must not be used for clinical diagnosis, treatment decisions, or other scientific conclusions.
