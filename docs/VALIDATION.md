# Validation record / 验证记录

Date: 2026-11-12. Target: ArtInChip D213ECV-DEMO-V4-0, demo128-nand.

## Implemented and exercised locally

- Built upstream Kconfig/SCons minimal ELF with the SHA256-verified SiFive
  GCC-Metal 10.2.0-2020.12.8 archive. No SDK build environment or system GCC was
  used. Only committed RT-Thread source at the locked revision was exported.
- Upstream ELF checker: ELF64, RISC-V, RVC, double-float ABI, entry `_start`
  `0x40000000`, PLIC, trap vector `0x40000180`, valid BSS/percpu/heap layout;
  heap upper bound `0x47800000`. RT-Thread's actual pinned source is 5.4.0.
- Independent FIT checks: segment bytes versus ELF, load/entry, external data
  offsets and CRC32/MD5. Vendor `-E -B 0x800` equivalent FIT generation retained.
- Built full IMG locally using the locked, locally available original boot
  resources. This is authorized local use, not a redistribution claim.
- Independent full checks: BROM magic/version, checksums and MD5, exact loader
  bytes/addresses, PBP/private DDR data, redundant env CRC/size, IMG header/info
  CRC, 7 metadata entries, target partitions, payload CRCs and payload bounds.
- Eleven unittest cases passed with full local artifacts, covering malformed
  ELF/ABI/entry/DDR ranges, corrupted FIT load/hash, partition drift/overflow,
  unknown boot resources, environment overflow, IMG corruption, source hashes
  and full-image rejection by the public upload stage. Public-mode runs skip
  the hardware-resource-dependent full-image test and use inert synthetic IMG
  payloads to exercise the actual container writer and oversize rejection.

## Comparison with the original SDK packer

The original, unmodified `tools/scripts/mk_image.py` from the locally pinned
`jiachenin/luban-lite-jc` checkout was run separately against the same ELF,
config and resources. FIT timestamp was fixed to the already generated FIT's
value for this comparison. This reference-only experiment is not part of the
normal build and does not introduce an SDK runtime dependency.

| Artifact | Size (bytes) | Result |
| --- | ---: | --- |
| `env.bin` | 4,096 | byte-identical |
| `usbupg-ddr-init.aic` | 30,992 | byte-identical |
| `loader.aic` | 369,168 | byte-identical |
| `pbp_ext.aic` | 31,232 | byte-identical |
| `bootloader.aic` | 400,400 | byte-identical |
| `d21x_os.itb` | 65,536 | byte-identical |
| complete IMG | 914,944 | byte-identical |

This compares the migrated toolchain with the original packaging tool on one
specific input. It is not a comparison against an independently captured,
known-good hardware boot image, nor a proof of all possible format variants.
Only the unsigned D213 demo128 NAND contract is supported.

## Outstanding acceptance items

- **Remote repository creation/push:** pending. The requested GitHub repository
  could not be queried or created: `api.github.com` and `github.com` DNS failed
  in this execution environment. `gh auth status` could not validate the
  configured `boa-z` session; do not infer token validity from that failure.
- **Actual hosted Actions run / artifact download / Release:** pending. A
  workflow is implemented, but no run URL or successful remote result exists.
  Do not report the YAML or local tests as a hosted CI success.
- **Public complete IMG:** blocked on confirmation of Bootloader/PBP
  redistribution permission. Source commit/path/hash are recorded, binaries
  excluded. Public ELF/FIT mode and explicitly scoped tag release are ready.
- **Real board boot, UART, tick, interrupts, scheduling, reset/recovery:** not
  tested. No serial development board was available. Runtime readiness is a
  design target, not a claimed hardware result.
- **Prior known-good flashed image:** not independently established. The
  original SDK packer comparison above establishes format preservation only.
- **Other architectural example repositories:** could not be fetched in this
  environment. No claim is made of a source-level review of those projects.

The workspace's `.git` directory is mounted read-only and initially empty.
A separate publish checkout and source-only Git bundle are prepared under
`/tmp` / `out/` for handoff, without changing that mount or modifying upstream
repositories. Neither the bundle nor normal commits contain boot resources.

## Completing publication when GitHub access is restored

From the prepared source checkout (or a fresh clone of its source bundle):

```sh
gh auth status
gh repo view boa-z/d213-rtthread-firmware --json nameWithOwner,isEmpty,url
```

If it does not exist, create it with
`gh repo create boa-z/d213-rtthread-firmware --public --source . --remote origin --push`.
If it already exists, inspect its contents/history first; do not overwrite an
existing repository. Inspect the first main-push build using
`gh run list --repo boa-z/d213-rtthread-firmware` and `gh run view RUN_ID --log-failed`,
fix any failures, and download the resulting public artifact to verify it.
Create an initial `v0.1.0` tag only after the hosted build passes; its release
will explicitly contain ELF/FIT only until boot resource rights are resolved.
