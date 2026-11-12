# Third-party sources and redistribution / 第三方来源与再分发

Project code (`app/`, `tools/`, tests, configuration and documentation) is
Apache-2.0, copyright 2026 boa-z, except retained third-party notices.
The root LICENSE contains the Apache-2.0 text. This does not relicense external
components. Original boot resource terms are retained separately below.

| Component | Source / version | License and treatment |
| --- | --- | --- |
| RT-Thread kernel, components, BSP | `boa-z/rt-thread`, commit `a4ecc4a7e36cf3c727c136f7aa0fea2504af78ff` | Root Apache-2.0 and file-specific notices. Fetched, never copied into this repository. The actual pinned kernel identifies as **5.4.0**, despite the earlier 5.3 project description. |
| ArtInChip HAL and D21x port | Same RT-Thread commit, `bsp/artinchip/libraries/` | Selected source files retain ArtInChip copyright and Apache-2.0 SPDX notices; other optional components retain their own notices. Minimal does not enable multimedia/network stacks. |
| Board image configuration, environment, DDR parameters | Same BSP commit, `d213-demo128-nand/pack/` | Source configuration reused from BSP; no second partition definition in the application. DDR parameters are source configuration, separate from PBP executable code. |
| Image tools | `jiachenin/luban-lite-jc`, commit `22fdca3473de01076e35bf424f283ec7d9ff5571`, `tools/scripts/` | Selected Python sources have explicit Apache-2.0 notices; retain those notices and root LICENSE/NOTICE. Vendored source SHA256 values are recorded in `deps.lock.json`. |
| Python fdt | Same SDK commit, `tools/scripts/fdt/`, version 0.3.3 | Copyright 2017 Martin Olejar, Apache-2.0 headers retained in every source file. |
| Bootloader | SDK v1.3.2 import `c5807f9e7d18292f920dafaa018b8174635085c4`, `target/d21x/demo128-nand/pack/bootloader.bin` | Redistributed unchanged with project-owner authorization and the SDK redistribution grant reproduced in `SDK-NOTICE.txt`. Source/path/SHA256 locked; included in `vendor/boot/` and complete IMG. |
| PBP | Same SDK v1.3.2 import, `bsp/artinchip/sys/d21x/d21x.pbp` | Same SDK redistribution notice and unchanged-resource treatment. Source/path/SHA256 locked; included in `vendor/boot/` and complete IMG. |
| GCC/newlib/libgcc | SiFive GCC-Metal 10.2.0-2020.12.8, RT-Thread toolchains-ci v1.4 archive | GCC/binutils GPL-family, libgcc runtime exception, newlib file-specific permissive licenses. Build tool fetched externally with SHA256; not vendored. Firmware links newlib/libgcc. See `docs/RUNTIME_LICENSES.txt` for upstream newlib 4.1.0 notices, GCC runtime exception and GPLv3 text retained with redistributed artifacts. Their source revisions/hashes are recorded in the lock file. |
| Python build dependencies | SCons 4.11.1, kconfiglib 14.1.0 | SCons MIT; kconfiglib ISC. Versions and distribution hashes locked in `uv.lock`; build-time only. |

## Local changes to the image tools

Only `vendor/artinchip/mk_image.py` differs from its locked upstream source:
unconditional third-party crypto imports were replaced with `hashlib.md5` for
unsigned boot images. Secure-operation placeholders raise an explicit error.
The project additionally rejects `signature`/`encryption` configurations before
packaging. Secure boot, signing and encrypted profiles are not supported.
No vendor host executables, bundled crypto packages, SDK credentials or key
material were imported. `tools/mkenvimage` independently implements the little-endian
redundant U-Boot environment encoding, including CRC and size rejection.
The original source hashes and the checked-in source hashes are both recorded.

## Bootloader/PBP resource management

The project owner has authorized redistribution and direct use of the original
Bootloader/PBP. The SDK README's “授权与使用条件” explicitly permits use, copying,
modification, merging and distribution, subject to preserving original
copyright/author information and declaring changes. The original README and
source revision are reproduced in `vendor/artinchip/SDK-NOTICE.txt`, included
with firmware artifacts alongside LICENSE and NOTICE.

Only the two fixed D213 resources are included in `vendor/boot/`. Their bytes
are unchanged; the source version, path, size, SHA256 and notice reference are
recorded in `deps.lock.json`. They match the previously verified resources
byte-for-byte. A complete IMG embeds them using the original BROM/Bootloader
addresses, DDR parameters and partition layout. The application and packaging
integration changes are this project's work; the vendor boot code is unmodified.

Some source SDK revisions are local development commits or require repository
access. Normal builds use the checked-in, hash-verified tool/resource snapshots
and the public RT-Thread dependency; access to the original SDK is unnecessary.
The firmware publishing allowlist includes the final IMG and its notices;
intermediate/raw resource copies are not uploaded as duplicate release assets.

Bootloader/PBP 按项目所有者授权直接使用和分发原始版本；保留 SDK 原始分发声明、
版权、来源、版本及 SHA256。默认本地构建、公开 CI 和 Release 均包含完整 IMG。
