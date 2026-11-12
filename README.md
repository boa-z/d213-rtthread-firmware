# D213 RT-Thread firmware

Standalone application and firmware packaging for the **ArtInChip
D213ECV-DEMO-V4-0**, C906 RV64GC/lp64d, 128 MiB DDR3 and 128 MiB SPI NAND.
UART0 console: **115200, 8N1**. Based on the fixed `demo128-nand` BSP in
[boa-z/rt-thread](https://github.com/boa-z/rt-thread/tree/bsp/artinchip-d213-dev).

**Status:** minimal ELF, FIT and complete ArtInChip IMG pass local offline checks.
Complete firmware builds have passed on GitHub-hosted Ubuntu 24.04
([verified run](https://github.com/boa-z/d213-rtthread-firmware/actions/runs/43233768689)); downloaded artifacts passed SHA256 and
independent FIT/IMG validation.
No development-board boot test has been performed. See
[validation status](docs/VALIDATION.md) and the
[Releases page](https://github.com/boa-z/d213-rtthread-firmware/releases).

## Architecture

- `app/`: Hello World and `fw_info` MSH command with project/BSP/config versions.
- `profiles/minimal.config`: the pinned BSP's minimal Kconfig baseline.
- `deps.lock.json`: RT-Thread commit, toolchain version/archive SHA256, vendor
  tool provenance and hashes, boot resource provenance and hashes.
- `tools/build.py`: fetch/export committed dependencies, prepare isolated BSP,
  invoke upstream Kconfig/SCons, verify ELF/FIT/IMG and generate the manifest.
- `vendor/artinchip/`: selected licensed Python image tools and SDK notice.
- `vendor/boot/`: unchanged, SHA256-locked D213 Bootloader/PBP resources.
- `.github/workflows/firmware.yml`: PR, main push, manual and tag builds;
  artifact upload and tag release of complete ELF/FIT/IMG firmware.

No RT-Thread fork is copied here. The top-level manager fetches a fixed commit
and exports its committed source into `.cache/`. It copies only the board into
an isolated work directory and supplies this project's application. The
original SCons build, linker script, HAL, interrupt code and RT-Thread kernel
remain upstream. Only the work copy's Kconfig root path is adjusted; no kernel
or BSP patch is required. Normal builds never read a Luban-Lite checkout.

The pinned RT-Thread source currently reports **5.4.0**. The actual source was
used rather than assuming the previously described 5.3 version.

## Linux quick start

Use x86_64 Linux (Ubuntu 24.04 is the CI target), Git, Python 3.11+ and uv.
Allow several GiB of free space for the toolchain. First build requires HTTPS
access to GitHub and PyPI; subsequent builds can use verified cached inputs.
For example, install the pinned uv with `python3 -m pip install uv==0.13.6`.

Clone and build:

```sh
git clone https://github.com/boa-z/d213-rtthread-firmware.git
cd d213-rtthread-firmware
uv sync --frozen
uv run --frozen python tools/build.py --profile minimal
uv run --frozen python -m unittest discover -s tests -v
(cd out/minimal && sha256sum -c SHA256SUMS)
```

The default `--mode full` produces ELF, FIT and a complete ArtInChip `.img`.
The exact Bootloader/PBP are included in `vendor/boot/` and verified before
building. No Luban-Lite checkout, system RISC-V GCC, `dtc`, `mkimage` or
`mkenvimage` installation is required. GCC/newlib are downloaded from a fixed
RT-Thread toolchains-ci release and verified against SHA256. Python dependencies
are locked with distribution hashes in `uv.lock`.

The minimal application provides FinSH/MSH, UART0, GPIO and the upstream basic
kernel setup. It does not add display, LVGL, networking, audio or CarPlay.
Only `minimal` is accepted today; unsupported profile names fail explicitly.
The existing upstream minimal config also selects some generic driver
frameworks and DMA support; it is retained without an unrelated config rewrite.

## Build modes and local inputs

The complete build uses the checked-in original D213 resources and preserves
their SDK redistribution notice. Sources, versions, SHA256 and modification
scope are documented in [third-party notices](docs/THIRD_PARTY.md).
The normal build does not need access to the original SDK repository.

For an ELF/FIT-only build, explicitly select `--mode public`:

```sh
uv run --frozen python tools/build.py --profile minimal --mode public
```

A local boot resource directory can be supplied with `--boot-resources DIR`;
the exact same SHA256 and size checks apply. Alternate resource versions fail.

To reuse existing **locked** dependencies without downloading again:

```sh
uv run --frozen python tools/build.py --profile minimal \
  --rt-thread /path/to/rt-thread \
  --toolchain-archive /path/to/riscv64-toolchain-10.2.0.tar.gz
```

The RT-Thread checkout must be at the exact locked commit. Only committed files
are exported; local modifications and credentials are excluded. An advanced
`--toolchain-bin DIR` option checks GCC version but cannot attest the archive
hash; manifests clearly record that limitation. Prefer the verified archive.

## Outputs and verification

`out/minimal/` contains `rtthread.elf`, `rtthread.bin`, `rtthread.map`,
`d21x_os.itb`, effective `rtconfig.h` and `config`, `image_cfg.json`,
`manifest.json`, `SHA256SUMS` and license notices. The default full mode also
produces `d213-minimal.img` and local boot/DDR/partition intermediates.

The manifest records project and RT-Thread commits, profile, toolchain version
and archive hash, boot resource hashes (full mode), config/profile/pack hashes,
validation results, artifact sizes/SHA256 and hardware-test status. A build
without project Git metadata records `uncommitted`. Hashes detect accidental
corruption; they do not authenticate a release. Build timestamps and debug
paths currently prevent a promise of byte-for-byte reproducible builds.

Checks cover ELF64/RISC-V/RVC/lp64d and `0x40000000` entry, upstream PLIC/vector/
BSS/heap rules, DDR bounds and the final 8 MiB Bootloader reservation, FIT
segment contents/load addresses/CRC32/MD5, and in full mode BROM headers,
Bootloader/PBP/private DDR resource contents, environment CRC, IMG header and
metadata bounds, component CRCs and partition limits. Tests mutate addresses,
ABIs, payloads and metadata and exercise synthetic IMG packing in public CI.

The BSP and packer use **the same upstream `pack/image_cfg.json`**. The
validated layout is pinned as an explicit safety contract. It is not replaced
with the stock SDK example. SPL is 1 MiB, env/env_r 256 KiB each, OS/OS_r 4 MiB
each, rodata/rodata_r 12 MiB each, data/data_r 40 MiB each, refresh 1 MiB.
The final unused NAND region remains unchanged. Bootloader load/entry stay
`0x47b80000`/`0x47b80100`; FIT load/entry stay `0x40000000`.

## Flashing and recovery

No build or test command flashes hardware. A public `.itb` alone is not a full
ArtInChip USB upgrade image. For full mode, use the board/vendor ArtInChip USB
burning procedure with the verified `.img`, matching D213 demo128 NAND geometry.
Back up the existing flash and board-specific data before trying a new image;
keep access to UART0 and the documented USB boot recovery mode. Do not use a
D12x, alternate-DDR or alternate-partition Bootloader. The image contains the
primary OS only and preserves the upstream A/B environment settings; this
project does not implement or validate OTA rollback.

On real hardware, first capture cold boot UART output, check the RT-Thread
banner and `fw_info`, then test MSH input, `list_thread`, scheduler/tick behavior,
reset and power-cycle recovery. Record the exact manifest and board revision.
None of those runtime results are claimed by the offline checks.

## CI, releases and troubleshooting

Workflow builds run on GitHub-hosted `ubuntu-24.04`, use pinned Actions commits,
Python/uv versions, locked Python dependencies, RT-Thread and GCC. PR/main/
manual builds generate and verify complete IMG firmware and upload an explicit
artifact allowlist. Tags `v*` repeat the build and publish ELF/BIN/FIT/IMG,
manifest, SHA256SUMS and license notices. Release notes clearly state the
hardware validation status. Raw packaging intermediates are not uploaded.

- Download/DNS errors: restore HTTPS access to GitHub/PyPI, or supply the locked
  local clone/archive above. Do not replace a locked URL with `latest`.
- Wrong compiler / missing libc: use the locked complete toolchain, including
  newlib; a distro `gcc-riscv64-unknown-elf` alone may lack libc headers.
- Missing boot resources: restore the tracked vendor files or supply matching files;
  full mode never silently falls back to ELF-only success.
- Address/partition/hash rejection: check the input commit/config/resources;
  do not bypass the checks or substitute a vendor example partition table.
- Remove `.cache/work/` and `out/` to discard work products. Dependency updates
  require a reviewed lock/config change and rerun of all validation.

See [CONTRIBUTING.md](CONTRIBUTING.md), [third-party notices](docs/THIRD_PARTY.md)
and the Apache-2.0 [LICENSE](LICENSE). Original boot resources retain the SDK
redistribution notice in `vendor/artinchip/SDK-NOTICE.txt`.

## 中文说明

这是 D213 最小 RT-Thread 独立应用与镜像工程，正常构建不需要完整 Luban-Lite。
依赖固定到 Commit/版本及 SHA256；底层仍使用上游 BSP 的 SCons、Kconfig、HAL
和链接脚本。默认命令生成 ELF/FIT 和完整 IMG，启动资源随工程固定管理并校验 SHA256。

已完成本地 ELF/FIT/IMG 编译与静态验证，并与原始打包工具进行逐字节兼容性对比。
**尚未进行开发板启动验证。** 公开仓库已创建，[GitHub Actions 实际运行](https://github.com/boa-z/d213-rtthread-firmware/actions/runs/43233768689)已成功，产物已下载并通过 SHA256 校验。
Bootloader/PBP 复用固定原始版本，并保留来源、哈希及 SDK 分发声明。
CI 和 Tag Release 均生成完整固件。详细状态见 [验证记录](docs/VALIDATION.md)。
