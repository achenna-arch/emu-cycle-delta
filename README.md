# Instruction-count deltas against cycle deltas on a Cortex-M4

Replication package of the article *Blind to Layout: Do Instruction-Count Deltas Predict Cycle Deltas for RTOS Kernel Commits on a Cortex-M4?* (under review).

The study runs the same Zephyr kernel benchmark image on an nRF52840 DK board of FIT IoT-LAB, where the DWT counter gives cycles, and in Renode 1.17.0, where the same register gives executed instructions. It compares the two deltas between parent and child commits for 17 kernel operations, uses padding shifts and link-time placebos to separate the effect of the code from the effect of layout, and checks QEMU 10.0.2 in icount mode against Renode.

## Contents

| Folder | Content |
|---|---|
| `protocol/` | The protocol, written before the campaign, with every amendment dated (in French) |
| `fw/` | The Zephyr benchmark firmware |
| `campaign/` | Pair selection, image builds, placebos, Renode and QEMU runs, FIT IoT-LAB scripts, log parser |
| `analysis/` | Criteria of the protocol, determinism checks, exploratory analyses, tests |
| `results/` | Pair lists, build failures, screening, parsed tables, image manifest |
| `results/raw/` | Raw serial logs of every board, Renode and QEMU run |
| `article/` | Scripts that rebuild every number, table and figure of the article from `results/` |
| `images/` | The ELF images of the campaign, as compressed archives, with `SHA256SUMS.txt` |

The images are split into six archives: the board and Renode images of the frozen pairs (`elf_nrf52840_frozen_pairs_1` and `_2`), of the extension pairs (`elf_nrf52840_extension_pairs`) and of the controls, that is mutants, placebos and base images (`elf_nrf52840_controls`), each with its `.config`; the QEMU control images (`elf_mps2_an385`); and the first placebo draw, archived as the protocol requires (`elf_first_draw`). Release v1.0 carries the same nRF52840 images as a single archive.

## Reproducing the analysis

Python 3.12 with the packages of `requirements.txt` is enough. From the root of the repository:

```bash
pip install -r requirements.txt
python -m pytest -q analysis/test_analysis.py
python article/make_fills.py
python article/make_figures.py
```

`make_fills.py` writes every number of the article to `article/manuscript/fills_auto.json` and the generated tables to `article/tables/`. `make_figures.py` writes the figures to `article/figures/`. Both read only the tables in `results/`. The bootstrap uses 2,000 resamples of whole pairs with the seed fixed in `analysis/delta_metrics.py`, so the intervals repeat exactly.

The tables come from the raw logs through `campaign/parse_log.py`, for example:

```bash
python campaign/parse_log.py results/raw/silicon_ext/logs/n1/*.log --platform silicon --out results/campaign_ext_silicon_n1.csv
```

## Reproducing the measurements

The measurement chain ran on Windows with free tools only:

1. `campaign/setup_tools.ps1` and `campaign/setup_zephyr.ps1` fetch Zephyr SDK 1.0.1, Renode 1.17.0 and a Zephyr tree limited to the modules the firmware needs, into `_tools/`.
2. `campaign/select_pairs.py` draws the pairs by the rule of protocol section 4, `campaign/build_matrix.py` builds the images, and `campaign/extend_sample.py` runs the extension of protocol section 15.
3. `campaign/run_emulators.py` runs the images under Renode or QEMU.
4. `campaign/make_lists.py` writes the lists of images for the board, and `campaign/run_saclay.sh` runs them on the FIT IoT-LAB frontend of Saclay, on nodes 1, 2 and 3.

Board time on FIT IoT-LAB requires a free account.

## Notes on the published files

- The published ELF files have their debug sections removed, because these sections record the absolute paths of the build host. `results/image_manifest.csv` gives, for every image, the SHA-256 of the loaded bytes of the image that was measured and of the published file; the loaded bytes are identical.
- In the `.config` files, the host path of the Zephyr tree is replaced by `<WEST_TOPDIR>` in the comment lines that name the modules. No setting is changed.
- Build logs of the host are not included.

## License

Code is released under the MIT License (see `LICENSE`). Data, logs and figures are released under the Creative Commons Attribution 4.0 International License.
