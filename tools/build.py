#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pinned standalone D213 build. No Luban-Lite checkout is used."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.request

from verify import ROOT, boot_images, config, elf, fit, image, layout, require, resources, sha

LOCK = json.loads((ROOT/'deps.lock.json').read_text())
VERSION = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
BSP = 'bsp/artinchip/d213-demo128-nand'


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.check_output(list(map(str, args)), text=True, **kwargs)


def command(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def download(spec, path):
    if not path.exists() or sha(path) != spec['sha256']:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.partial')
        urllib.request.urlretrieve(spec['url'], tmp)
        require(sha(tmp) == spec['sha256'], 'download SHA256 mismatch')
        tmp.replace(path)
    return path


def extract(archive, target):
    with tarfile.open(archive) as tar:
        base = target.resolve()
        for m in tar.getmembers():
            require((base/m.name).resolve().is_relative_to(base), 'unsafe archive path')
            if m.issym() or m.islnk():
                link = (base/m.name).parent/m.linkname if m.issym() else base/m.linkname
                require(link.resolve().is_relative_to(base), 'unsafe archive link')
            require(m.isfile() or m.isdir() or m.issym() or m.islnk(), 'unsafe archive entry')
        tar.extractall(target)


def source(local):
    spec = LOCK['rt_thread']
    checkout = Path(local).resolve() if local else ROOT/'.cache/rt-thread-git'
    if local:
        require(run(['git','-C',checkout,'rev-parse','HEAD']).strip() == spec['commit'], 'RT-Thread commit does not match lock')
    else:
        if not checkout.exists(): command(['git', 'init', '--bare', checkout])
        exists = subprocess.run(['git','-C',str(checkout),'cat-file','-e',spec['commit']+'^{commit}'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if exists.returncode:
            command(['git','-C',checkout,'fetch','--depth=1',spec['url'],spec['commit']])
    # Export committed files, never local modifications or developer credentials.
    dest = ROOT/'.cache/sources'/spec['commit']
    if not (dest/'.complete').exists():
        dest.mkdir(parents=True, exist_ok=True)
        archive = ROOT/'.cache/rtt-source.tar'
        command(['git','-C',checkout,'archive','--format=tar','-o',archive,spec['commit'],
                 'src','include','libcpu','components','tools','Kconfig','LICENSE','bsp/artinchip'])
        extract(archive, dest)
        (dest/'.complete').write_text(spec['commit'])
    return dest


def toolchain(local, archive):
    spec = LOCK['toolchain']
    if local:
        bindir = Path(local).resolve()
    else:
        target = ROOT/'.cache/toolchain'
        bindir = target/spec['directory']/'bin'
        package = Path(archive).resolve() if archive else download(spec, ROOT/'.cache/downloads/toolchain.tar.gz')
        require(sha(package) == spec['sha256'], 'toolchain SHA256 mismatch')
        if not bindir.exists():
            target.mkdir(parents=True, exist_ok=True)
            extract(package, target)
    version = run([bindir/'riscv64-unknown-elf-gcc','-dumpfullversion']).strip()
    require(version == spec['version'], 'toolchain version differs from lock: ' + version)
    return bindir, version


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', choices=['minimal'], default='minimal')
    p.add_argument('--mode', choices=['public','full'], default='public', help='public = ELF+FIT; full requires licensed local boot resources')
    p.add_argument('--rt-thread', help='existing clone at locked commit (committed files only)')
    p.add_argument('--toolchain-bin', help='existing locked GCC bin directory; archive hash is not attested')
    p.add_argument('--toolchain-archive', help='local SHA256-verified toolchain archive')
    p.add_argument('--boot-resources', help='directory containing authorized bootloader.bin and d21x.pbp')
    p.add_argument('-j', '--jobs', type=int, default=min(os.cpu_count() or 2, 8))
    args = p.parse_args()
    for name, digest in LOCK['vendor']['local_files'].items():
        require(sha(ROOT/name) == digest, 'vendored tool differs from lock: ' + name)
    if args.mode == 'full':
        require(args.boot_resources is not None, '--mode full requires --boot-resources; redistribution permission unconfirmed')
        resources(args.boot_resources, LOCK)
    src = source(args.rt_thread)
    bindir, ccversion = toolchain(args.toolchain_bin, args.toolchain_archive)
    workroot = ROOT/'.cache/work'/args.profile
    if workroot.exists(): shutil.rmtree(workroot)
    board = workroot/'artinchip/d213-demo128-nand'
    shutil.copytree(src/BSP, board)
    for name in ['libraries', 'tools']:
        (board.parent/name).symlink_to(src/'bsp/artinchip'/name, target_is_directory=True)
    shutil.rmtree(board/'applications')
    shutil.copytree(ROOT/'app', board/'applications')
    # Resolve the upstream Kconfig root without changing the dependency checkout.
    kpath = board/'Kconfig'
    kpath.write_text(kpath.read_text().replace('RTT_DIR := ../../..', 'RTT_DIR := ' + str(src)))
    shutil.copyfile(ROOT/f'profiles/{args.profile}.config', board/'.config')
    env = os.environ.copy()
    for key in ['AIC_SDK_DIR','LUBAN_LITE_DIR','RTT_CC','RTT_CC_PREFIX','RTT_ROOT','RTT_EXEC_PATH','RTT_BUILD','SCONSFLAGS','PYTHONPATH','PYTHONHOME']:
        env.pop(key, None)
    env.update(RTT_ROOT=str(src), RTT_EXEC_PATH=str(bindir), RTT_CC_PREFIX='riscv64-unknown-elf-')
    env['PATH'] = str(bindir) + os.pathsep + str(ROOT/'tools') + os.pathsep + env['PATH']
    command([sys.executable,'-m','SCons','--pyconfig-silent'], cwd=board, env=env)
    project_commit = 'uncommitted'
    project_dirty = None
    try:
        project_commit = run(['git','-C',ROOT,'rev-parse','HEAD'], stderr=subprocess.DEVNULL).strip()
        project_dirty = bool(run(['git','-C',ROOT,'status','--porcelain'], stderr=subprocess.DEVNULL).strip())
    except subprocess.CalledProcessError: pass
    config_hash = sha(board/'rtconfig.h')
    effective = (board/'rtconfig.h').read_text()
    for symbol in ['RT_USING_FINSH','RT_USING_MSH','BSP_USING_UART0','BSP_USING_GPIO',
                   'RT_USING_HEAP','RT_USING_RISCV_NEW_COMMON']:
        require(f'#define {symbol}\n' in effective, 'minimal config missing ' + symbol)
    for symbol in ['BSP_USING_DISPLAY','RT_USING_LWIP','BSP_USING_AUDIO','RT_USING_WIFI']:
        require(f'#define {symbol}\n' not in effective, 'unexpected minimal feature ' + symbol)
    macros = {'FW_VERSION':VERSION,'FW_COMMIT':project_commit+('-dirty' if project_dirty else ''),'FW_BSP_COMMIT':LOCK['rt_thread']['commit'], 'FW_CONFIG_HASH':config_hash}
    (board/'applications/firmware_version.h').write_text('\n'.join(f'#define {k} {json.dumps(v)}' for k,v in macros.items())+'\n')
    cfg = config(board/'pack/image_cfg.json')
    layout(cfg)
    command([sys.executable,'-m','SCons',f'-j{args.jobs}'], cwd=board, env=env)
    command([sys.executable,src/'bsp/artinchip/tools/check_elf.py','--elf',board/'rtthread.elf',
             '--map',board/'rtthread.map','--xlen','64','--entry','0x40000000','--intc','plic',
             '--require-symbol','fw_info','--require-string','Hello from ArtInChip D213'], env=env)
    elf(board/'rtthread.elf')
    # A success manifest is written only after all requested packaging checks pass.
    out = ROOT/'out'/args.profile
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in ['rtthread.elf','rtthread.bin','rtthread.map','rtconfig.h','.config']:
        shutil.copyfile(board/name, out/name.lstrip('.'))
    for name in ['image_cfg.json','env.txt','ddr_init.json']:
        shutil.copyfile(board/'pack'/name, out/name)
    sys.path.insert(0, str(ROOT/'vendor/artinchip'))
    from elf2image import elf2its
    from itbimage import build_itb
    its = out/'d21x_os.its'
    elf2its(str(out/'rtthread.elf'), '1.0.0', str(its), hash_algos=['crc32','md5'])
    build_itb(str(its), str(out/'d21x_os.itb'), external_data=True, block_align=0x800)
    checks = {'fit':fit(out/'d21x_os.itb', out/'rtthread.elf')}
    boot = None
    if args.mode == 'full':
        for name in LOCK['boot_resources']: shutil.copyfile(Path(args.boot_resources)/name, out/name)
        vendor = ROOT/'vendor/artinchip'
        command([sys.executable,vendor/'gen_partition_table.py','-c',out/'image_cfg.json','-o',out/'partition_table.h','-j',out/'partition.json'], env=env)
        command([sys.executable,vendor/'mk_private_resource.py','-l',f'{out}/ddr_init.json,{out}/partition.json','-o',out/'ddr_init.bin'], env=env)
        command([sys.executable,vendor/'mk_image.py','-c',out/'image_cfg.json','-d',str(out)+os.sep], env=env)
        boot_images(out)
        img = out/'d21x_d213_demo128_page_2k_block_128k_v1.0.0.img'
        checks['img'] = image(img, cfg, out)
        checks['boot_headers_and_env'] = 'pass'
        checks['fit'] = fit(out/'d21x_os.itb', out/'rtthread.elf')
        img.rename(out/'d213-minimal.img')
        boot = LOCK['boot_resources']
    # Boot/DDR inputs and processed bootloaders are kept local; never upload them by default.
    deliver = ['rtthread.elf','rtthread.bin','rtthread.map','d21x_os.itb','rtconfig.h','config','image_cfg.json']
    if args.mode == 'full': deliver += ['d213-minimal.img']
    for source_name, output_name in [('LICENSE','LICENSE'), ('NOTICE','NOTICE'),
            ('docs/THIRD_PARTY.md','THIRD_PARTY.md'), ('docs/RUNTIME_LICENSES.txt','RUNTIME_LICENSES.txt')]:
        shutil.copyfile(ROOT/source_name, out/output_name)
        deliver.append(output_name)
    artifact_hashes = {name:{'size':(out/name).stat().st_size,'sha256':sha(out/name)} for name in deliver}
    manifest = {'schema':1,'project_version':VERSION,'project_commit':project_commit,'project_dirty':project_dirty,
        'rt_thread_commit':LOCK['rt_thread']['commit'],'profile':args.profile,'mode':args.mode,
        'complete_firmware':args.mode=='full','hardware_tested':False,
        'toolchain':{'version':ccversion,'archive_sha256':LOCK['toolchain']['sha256'] if not args.toolchain_bin else None},
        'boot_resources':boot,'full_image_blocker':None if boot else 'Bootloader/PBP redistribution permission unconfirmed; authorized local inputs required',
        'config_sha256':config_hash,'profile_sha256':sha(ROOT/'profiles/minimal.config'),
        'pack_config_sha256':sha(out/'image_cfg.json'),'checks':checks,'artifacts':artifact_hashes}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    deliver += ['manifest.json']
    (out/'SHA256SUMS').write_text(''.join(f'{sha(out/n)}  {n}\n' for n in deliver))
    (out/'publish-files.txt').write_text('\n'.join(deliver+['SHA256SUMS'])+'\n')
    print(f'PASS: {args.mode} build in {out}; hardware NOT tested')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
