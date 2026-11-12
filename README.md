# D213 RT-Thread firmware

Standalone application and firmware packaging for the **ArtInChip
D213ECV-DEMO-V4-0**, C906 RV64GC/lp64d, 128 MiB DDR3 and 128 MiB SPI NAND.
UART0 console: **115200, 8N1**. Based on the fixed `demo128-nand` BSP in
[boa-z/rt-thread](https://github.com/boa-z/rt-thread/tree/bsp/artinchip-d213-dev).

**Status:** local minimal ELF, FIT and complete IMG have passed offline checks.
No development-board boot test has been performed. Public ELF/FIT builds have passed on GitHub-hosted Ubuntu 24.04
([verified run](https://github.com/boa-z/d213-rtthread-firmware/actions/runs/43231016766)); its artifact was downloaded and SHA256-checked. See [validation status](docs/VALIDATION.md).
Public CI is deliberately **ELF + FIT only**, not a complete flashable firmware
build: Bootloader/PBP redistribution permission is unconfirmed.

## Architecture

- `app/`: Hello World and `fw_info` MSH command with project/BSP/config versions.
- `profiles/minimal.config`: the pinned BSP's minimal Kconfig baseline.
- `deps.lock.json`: RT-Thread commit, toolchain version/archive SHA256, vendor
  tool provenance and hashes, external boot resource hashes.
- `tools/build.py`: fetch/export committed dependencies, prepare isolated BSP,
  invoke upstream Kconfig/SCons, verify ELF/FIT/IMG and generate the manifest.
- `vendor/artinchip/`: selected licensed Python image tools; no native binaries.
- `.github/workflows/firmware.yml`: PR, main push, manual and tag builds;
  artifact upload and tag release of public ELF/FIT assets only.

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

This default `--mode public` produces the minimal ELF and vendor-compatible
FIT, without downloading Bootloader or PBP. No system RISC-V GCC, SDK, `dtc`,
`mkimage` or `mkenvimage` installation is required. GCC/newlib are downloaded
from a versioned RT-Thread toolchains-ci release and verified against SHA256.
Python dependencies are locked with distribution hashes in `uv.lock`.

The minimal application provides FinSH/MSH, UART0, GPIO and the upstream basic
kernel setup. It does not add display, LVGL, networking, audio or CarPlay.
Only `minimal` is accepted today; unsupported profile names fail explicitly.
The existing upstream minimal config also selects some generic driver
frameworks and DMA support; it is retained without an unrelated config rewrite.

## Complete IMG with authorized boot resources

Read [third-party licensing](docs/THIRD_PARTY.md) first. Obtain the **exact**
`bootloader.bin` and `d21x.pbp` identified in `deps.lock.json` through an
authorized source. Store them outside Git; `.cache/local-boot/` is one ignored
local option. Unknown versions fail SHA256/size verification.

```sh
uv run --frozen python tools/build.py --profile minimal --mode full \
  --boot-resources /path/to/authorized/d213-boot
```

The normal build does not need the source SDK. There is no implicit SDK search
or local SDK fallback. Do not upload complete images until the boot resources'
redistribution terms permit it. The public upload stage rejects full manifests.

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
`manifest.json`, `SHA256SUMS` and license notices. Full mode additionally
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
manual builds upload only the public allowlist. Tags `v*` publish the same
ELF/FIT assets with an explicit **no complete IMG** release description.
Published versions are listed on the [Releases page](https://github.com/boa-z/d213-rtthread-firmware/releases). Release assets are explicitly scoped to public ELF/FIT.

- Download/DNS errors: restore HTTPS access to GitHub/PyPI, or supply the locked
  local clone/archive above. Do not replace a locked URL with `latest`.
- Wrong compiler / missing libc: use the locked complete toolchain, including
  newlib; a distro `gcc-riscv64-unknown-elf` alone may lack libc headers.
- Missing boot resources: use public mode or supply authorized, matching files;
  full mode never silently falls back to ELF-only success.
- Address/partition/hash rejection: check the input commit/config/resources;
  do not bypass the checks or substitute a vendor example partition table.
- Remove `.cache/work/` and `out/` to discard work products. Dependency updates
  require a reviewed lock/config change and rerun of all validation.

See [CONTRIBUTING.md](CONTRIBUTING.md), [third-party notices](docs/THIRD_PARTY.md)
and the Apache-2.0 [LICENSE](LICENSE). External boot binaries have separate,
currently unconfirmed redistribution rights.

## 中文说明

这是 D213 最小 RT-Thread 独立应用与镜像工程，正常构建不需要完整 Luban-Lite。
依赖固定到 Commit/版本及 SHA256；底层仍使用上游 BSP 的 SCons、Kconfig、HAL
和链接脚本。默认命令生成 ELF/FIT，完整 IMG 需要用户提供经授权的启动资源。

已完成本地 ELF/FIT/IMG 编译与静态验证，并与原始打包工具进行逐字节兼容性对比。
**尚未进行开发板启动验证。** 公开仓库已创建，[GitHub Actions 实际运行](https://github.com/boa-z/d213-rtthread-firmware/actions/runs/43231016766)已成功，产物已下载并通过 SHA256 校验。
Bootloader/PBP 的公开再分发权限未确认，因此公开 CI 和 Release 仅允许 ELF/FIT，
不会将它们称为完整烧录镜像。详细状态见 [验证记录](docs/VALIDATION.md)。
