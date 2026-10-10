placeholder

### Reproducibility note

The exact package versions used to reproduce the baseline are pinned in
`requirements.txt`. The baseline notebook was executed with scikit-learn 1.9.1, 
which emits `FutureWarning` for the deprecated `penalty=`
argument. This is expected and does not affect results. Future scikit-learn
releases will remove `penalty=`, at which point `src/train.py` will need to
migrate to `l1_ratio=` and the pin will need to be updated.

`PYTHONHASHSEED` must be set to `246112165` before running training:

    PYTHONHASHSEED=246112165 python -m src.train

## Dataset and License

The source dataset is the DREBIN subset (Mendeley Data, DOI
[10.17632/bpkksc9v5s.7](https://doi.org/10.17632/bpkksc9v5s.7)), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The raw file is committed unchanged at `data/source/drebin_dataset.csv`.
Its identity is pinned by SHA-256 in `metadata/source_manifest.yml`. See
[`ATTRIBUTION.md`](ATTRIBUTION.md) for full attribution and modification notes.

All derived data products and code in this repository are the work of the
individual student and are released under the repository's own license.