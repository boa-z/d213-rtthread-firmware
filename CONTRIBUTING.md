# Contributing

Keep kernel/HAL fixes in `boa-z/rt-thread`; this repository owns application,
configuration, dependency pins and firmware delivery. Submit an isolated BSP
patch upstream if a new application hook is necessary; never rewrite its
branch history. No BSP patch is required by the current minimal application.

Run `uv sync --frozen`, the full build, and
`uv run --frozen python -m unittest discover -s tests -v` before submitting.
Tests before building exercise tooling only; after building they also mutate
real ELF/FIT inputs. CI uses the fixed vendor boot resources and runs full-image tests. Synthetic
IMG payloads additionally exercise oversize and corruption rejection.

Review lock updates against original copyright/SPDX notices, preserve vendor
headers, record source/local hashes and tool changes, and rerun the full
format comparison when possible. Keep the two approved, unchanged boot resources pinned by SHA256; do not add
unrelated SDK binaries, keys, credentials, private files or generated images. Report board tests separately from build tests,
including board revision, artifact SHA256, UART log and observed failures.
