#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage an explicit allowlist; never upload vendor boot resources or full IMG."""
import json
from pathlib import Path
import shutil
from verify import ROOT, require, sha


def stage(source, target):
    manifest = json.loads((source/'manifest.json').read_text())
    require(manifest['mode'] == 'public' and not manifest['complete_firmware'], 'only public builds may be uploaded')
    names = {'rtthread.elf','rtthread.bin','rtthread.map','d21x_os.itb','rtconfig.h','config','image_cfg.json',
             'LICENSE','NOTICE','THIRD_PARTY.md','RUNTIME_LICENSES.txt'}
    require(set(manifest['artifacts']) == names, 'unexpected public artifact set')
    for name in names:
        spec = manifest['artifacts'][name]
        require(sha(source/name) == spec['sha256'] and (source/name).stat().st_size == spec['size'], 'artifact changed: '+name)
    # Recompute checksum file so a stale file cannot pull in unlisted resources.
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in names | {'manifest.json'}: shutil.copyfile(source/name, target/name)
    (target/'SHA256SUMS').write_text(''.join(f'{sha(target/name)}  {name}\n' for name in sorted(names | {'manifest.json'})))


if __name__ == '__main__': stage(ROOT/'out/minimal', ROOT/'out/public')
