# Dataset Attribution

This repository uses the following dataset as its immutable source.

## Dataset

- **Title:** Android Malware Analysis (including the Drebin dataset as one of the curated sources)
- **Rights holder / publisher:** Md Sadman Haque, Md Sakhawat Hossain, Robiul Awoul Robin, Asma Sadia Tarisha, Suman Ahmmed, and Jannatun Noor Mukta (contributors to the Mendeley Data version); original Drebin dataset by Daniel Arp, Michael Spreitzenbarth, Malte Hubner, Hugo Gascon, and Konrad Rieck
- **Host:** Mendeley Data
- **Version:** 7
- **DOI:** https://doi.org/10.17632/bpkksc9v5s.7
- **URL:** https://data.mendeley.com/datasets/bpkksc9v5s/7
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **License URL:** https://creativecommons.org/licenses/by/4.0/

## Original research

If you use this dataset, cite the original DREBIN paper:

> Arp, D., Spreitzenbarth, M., Hubner, M., Gascon, H., Rieck, K. (2014).
> DREBIN: Effective and Explainable Detection of Android Malware in Your Pocket.
> Proceedings of the 2014 Network and Distributed System Security Symposium (NDSS).

Additionally, please cite the Mendeley Data version 7 dataset curated by Haque et al.:

> Haque, M. S., Hossain, M. S., Robin, R. A., Tarisha, A. S., Ahmmed, S., & Mukta, J. N. (2026). “Android Malware Analysis”, Mendeley Data, V7. https://doi.org/10.17632/bpkksc9v5s.7

## Modifications

- The raw CSV file (`data/source/drebin_dataset.csv`) is redistributed **unchanged**.
  Its identity is pinned by SHA-256 in `metadata/source_manifest.yml`.
- All cleaning, typing, deduplication decisions, and feature engineering are performed
  in code under `src/` and materialized into `data/staging/`, `data/curated/`,
  and `data/partitioned/`. These derived files are **not** part of the original dataset
  and are released under the license of this repository.

## Third-party content

No third-party content within the dataset is known to be separately licensed
beyond CC BY 4.0 at the time of writing. If any rights holder identifies any
component under a different license, that component is excluded from redistribution.

## How this license is honored in this repository

- Attribution is included in this file and referenced in `README.md`.
- A link to the CC BY 4.0 license is provided above.
- Modifications (if any) are indicated in the section above.
- No endorsement by the rights holder is implied.