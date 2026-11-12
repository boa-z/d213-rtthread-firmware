# Third-party sources and redistribution / 第三方来源与再分发

Project code (`app/`, `tools/`, tests, configuration and documentation) is
Apache-2.0, copyright 2026 boa-z, except retained third-party notices.
The root LICENSE contains the Apache-2.0 text. This does not relicense external
components or grant rights to firmware blobs.

| Component | Source / version | License and treatment |
| --- | --- | --- |
| RT-Thread kernel, components, BSP | `boa-z/rt-thread`, commit `a4ecc4a7e36cf3c727c136f7aa0fea2504af78ff` | Root Apache-2.0 and file-specific notices. Fetched, never copied into this repository. The actual pinned kernel identifies as **5.4.0**, despite the earlier 5.3 project description. |
| ArtInChip HAL and D21x port | Same RT-Thread commit, `bsp/artinchip/libraries/` | Selected source files retain ArtInChip copyright and Apache-2.0 SPDX notices; other optional components retain their own notices. Minimal does not enable multimedia/network stacks. |
| Board image configuration, environment, DDR parameters | Same BSP commit, `d213-demo128-nand/pack/` | Source configuration reused from BSP; no second partition definition in the application. DDR parameters are source configuration, separate from PBP executable code. |
| Image tools | `jiachenin/luban-lite-jc`, commit `22fdca3473de01076e35bf424f283ec7d9ff5571`, `tools/scripts/` | Selected Python sources have explicit Apache-2.0 notices; retain those notices and root LICENSE/NOTICE. Vendored source SHA256 values are recorded in `deps.lock.json`. |
| Python fdt | Same SDK commit, `tools/scripts/fdt/`, version 0.3.3 | Copyright 2017 Martin Olejar, Apache-2.0 headers retained in every source file. |
| Bootloader | Same SDK commit, `target/d21x/demo128-nand/pack/bootloader.bin` | **Redistribution unconfirmed.** Not included, downloaded, or published by the public workflow. Only authorized user-supplied input is accepted. |
| PBP | Same SDK commit, `bsp/artinchip/sys/d21x/d21x.pbp` | **Redistribution unconfirmed.** Same restriction. Public availability is not treated as redistribution permission. |
| GCC/newlib/libgcc | SiFive GCC-Metal 10.2.0-2020.12.8, RT-Thread toolchains-ci v1.4 archive | GCC/binutils GPL-family, libgcc runtime exception, newlib file-specific permissive licenses. Build tool fetched externally with SHA256; not vendored. Firmware links newlib/libgcc. See `docs/RUNTIME_LICENSES.txt` for notices retained with redistributed artifacts. |
| Python build dependencies | SCons 4.11.1, kconfiglib 14.1.0 | SCons MIT; kconfiglib ISC. Versions and distribution hashes locked in `uv.lock`; build-time only. |

## Local changes to the image tools

Only `vendor/artinchip/mk_image.py` differs from its locked upstream source:
unconditional third-party crypto imports were replaced with `hashlib.md5` for
unsigned boot images. Secure-operation placeholders raise an explicit error.
The project additionally rejects `signature`/`encryption` configurations before
packaging. Secure boot, signing and encrypted profiles are not supported.
No executable tools, bundled crypto packages, SDK credentials or key material
were imported. `tools/mkenvimage` independently implements the little-endian
redundant U-Boot environment encoding, including CRC and size rejection.
The original source hashes and the checked-in source hashes are both recorded.

## Authorized local complete images

Acquire Bootloader/PBP through a source you are authorized to use. Place the two
files in a directory outside version control and pass `--boot-resources DIR`.
Their exact sizes, source paths, commits and SHA256 are in `deps.lock.json`.
The build rejects unknown binaries before compiling. It does not fetch binary
resources from the public repository on your behalf.

The full local IMG contains these binary resources, so the IMG itself must not
be publicly uploaded until their redistribution rights are confirmed. The CI
upload stage rejects full-mode manifests and uses an explicit file allowlist.
This is a release blocker for **complete IMG publication**, not an assertion
that a complete firmware has been publicly built or released.

需取得 Bootloader/PBP 的适用授权后自行提供资源。公开 CI 仅上传 ELF/FIT，
不会自动获取、上传或再分发启动二进制，也不会把 ELF/FIT 标记为完整烧录固件。
