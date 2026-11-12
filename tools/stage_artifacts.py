#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify and stage the selected firmware mode using an explicit file allowlist."""
import argparse
import json
from pathlib import Path
import shutil
from verify import ROOT, require, sha


def stage(source, target, mode='full'):
    manifest = json.loads((source/'manifest.json').read_text())
    require(mode in ('public', 'full') and manifest['mode'] == mode
            and manifest['complete_firmware'] == (mode == 'full'), 'artifact mode mismatch')
    names = {'rtthread.elf','rtthread.bin','rtthread.map','d21x_os.itb','rtconfig.h','config','image_cfg.json',
             'LICENSE','NOTICE','THIRD_PARTY.md','RUNTIME_LICENSES.txt','SDK-NOTICE.txt'}
    if mode == 'full': names.add('d213-minimal.img')
    require(set(manifest['artifacts']) == names, 'unexpected artifact set')
    for name in names:
        spec = manifest['artifacts'][name]
        require(sha(source/name) == spec['sha256'] and (source/name).stat().st_size == spec['size'], 'artifact changed: '+name)
    # Recompute checksum file so a stale file cannot pull in unlisted resources.
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in names | {'manifest.json'}: shutil.copyfile(source/name, target/name)
    (target/'SHA256SUMS').write_text(''.join(f'{sha(target/name)}  {name}\n' for name in sorted(names | {'manifest.json'})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['public','full'], default='full')
    args = parser.parse_args()
    stage(ROOT/'out/minimal', ROOT/'out/release', args.mode)
