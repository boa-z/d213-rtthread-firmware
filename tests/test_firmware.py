# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from verify import boot_images, config, elf, fit, image, layout, resources
from stage_public import stage


class Contracts(unittest.TestCase):
    def test_synthetic_img_without_vendor_binaries(self):
        """Exercise the real container writer in public CI using inert payloads."""
        import mk_image
        parts = dict(zip(['spl','env','env_r','os','os_r','rodata','rodata_r','data','data_r','refresh'],
                         ['1m','256k','256k','4m','4m','12m','12m','40m','40m','1m']))
        cfg = {'spi-nand': {'size':'128m','partitions':{k:{'size':v} for k,v in parts.items()}},
            'pre-process': {'aicimage': {'loader.aic': {'loader': {
                'load address':'0x47b80000','entry point':'0x47b80100'}}}},
            'image': {'bootcfg':'bootcfg.txt','part_table':'image_part_table.bin','info': {'platform':'d21x','product':'d213_demo128_page_2k_block_128k','version':'1.0.0',
                'media': {'type':'spi-nand','device_id':0,'array_organization':[{'page':'2k','block':'128k','oob':'64'}]}},
                'updater': {'ddr': {'file':'fake-ddr','attr':['required','run'],'ram':'0x00103000'}},
                'target': {'os': {'file':'fake-fit','attr':['mtd','required'],'part':['os']}}}}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            (path/'fake-ddr').write_bytes(b'inert synthetic DDR test payload')
            (path/'fake-fit').write_bytes(b'inert synthetic OS test payload')
            self.assertEqual(mk_image.build_firmware_image(copy.deepcopy(cfg),d+'/',d+'/'), 0)
            img=next(path.glob('*.img'))
            image(img,cfg,path)
            original=img.read_bytes()
            corrupted=bytearray(original);corrupted[-2048]^=1;img.write_bytes(corrupted)
            with self.assertRaises(ValueError): image(img,cfg,path)
            (path/'fake-fit').write_bytes(b'x'*(4194304+1))
            self.assertNotEqual(mk_image.build_firmware_image(copy.deepcopy(cfg),d+'/',d+'/'),0)

    def test_vendor_source_integrity(self):
        lock = json.loads((ROOT/'deps.lock.json').read_text())
        for name, digest in lock['vendor']['local_files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)

    def test_reject_unknown_bootloader(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'bootloader.bin').write_bytes(b'unknown binary')
            with self.assertRaisesRegex(ValueError, 'unrecognized boot'):
                resources(d, json.loads((ROOT/'deps.lock.json').read_text()))

    def test_environment_encoding_and_overflow(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/'env.txt', Path(d)/'env.bin'
            source.write_text('# comment\na=b\nx=y\n')
            cmd = [sys.executable, str(ROOT/'tools/mkenvimage'), '-r', '-s', '32', '-o', str(target), str(source)]
            subprocess.run(cmd, check=True)
            data = target.read_bytes()
            self.assertEqual(len(data),32)
            self.assertEqual(data[4:14],b'\x01a=b\0x=y\0\0')
            self.assertEqual(struct.unpack_from('<I',data)[0], zlib.crc32(data[5:]))
            source.write_text('a='+'b'*100)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_reject_malformed_elf(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.elf';p.write_bytes(b'not an ELF')
            with self.assertRaises(ValueError): elf(p)


@unittest.skipUnless((ROOT/'out/minimal/rtthread.elf').exists(), 'build artifacts not available yet')
class BuiltFirmware(unittest.TestCase):
    directory = ROOT/'out/minimal'

    def test_valid_elf_and_fit(self):
        elf(self.directory/'rtthread.elf')
        fit(self.directory/'d21x_os.itb',self.directory/'rtthread.elf')

    def test_partition_and_address_rejections(self):
        cfg = config(self.directory/'image_cfg.json')
        layout(cfg)
        for modify in [lambda c:c['spi-nand']['partitions']['os'].update(size='200m'),
                       lambda c:c['spi-nand']['partitions']['spl'].update(size='2m'),
                       lambda c:c['pre-process']['aicimage']['loader.aic']['loader'].update({'entry point':'0x40000000'}),
                       lambda c:c['pre-process']['aicimage']['loader.aic'].update(signature={'algo':'rsa,2048'})]:
            changed = copy.deepcopy(cfg);modify(changed)
            with self.assertRaises(ValueError): layout(changed)

    def test_elf_rejects_bad_abi_entry_and_memory(self):
        original = (self.directory/'rtthread.elf').read_bytes()
        phoff = struct.unpack_from('<Q',original,32)[0]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.elf'
            for offset, fmt, value in [(24,'<Q',0x40000100),(48,'<I',1),(18,'<H',62),
                    (phoff+40,'<Q',0x8000000)]:
                data=bytearray(original);struct.pack_into(fmt,data,offset,value);p.write_bytes(data)
                with self.assertRaises(ValueError): elf(p)

    def test_fit_rejects_load_and_hash_corruption(self):
        import fdt
        original = (self.directory/'d21x_os.itb').read_bytes()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.itb'
            for mutate, error in [(lambda n:n.set_property('load',0x41000000), 'FIT load'),
                           (lambda n:n.nodes[0].set_property('value', b'\0'*4), 'FIT hash')]:
                tree=fdt.parse_dtb(original);mutate(tree.get_node('/images').nodes[0])
                dtb=tree.to_dtb(version=17)
                oldbase=(struct.unpack_from('>I',original,4)[0]+2047)&~2047
                p.write_bytes(dtb.ljust(oldbase,b'\0')+original[oldbase:])
                with self.assertRaisesRegex(ValueError,error): fit(p,self.directory/'rtthread.elf')

    def test_public_stage_rejects_full(self):
        manifest = self.directory/'manifest.json'
        if not manifest.exists(): self.skipTest('no successful build manifest')
        with tempfile.TemporaryDirectory() as d:
            if json.loads(manifest.read_text())['mode']=='full':
                with self.assertRaises(ValueError):stage(self.directory,Path(d)/'public')
            else:
                stage(self.directory,Path(d)/'public')
                self.assertFalse(list((Path(d)/'public').glob('*.img')))

    def test_full_image_and_corruption(self):
        img=self.directory/'d213-minimal.img'
        if not img.exists(): self.skipTest('full IMG requires authorized local boot resources')
        cfg=config(self.directory/'image_cfg.json');boot_images(self.directory);image(img,cfg,self.directory)
        original=img.read_bytes();fo=struct.unpack_from('<I',original,340)[0]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.img'
            for offset in [0,340,2048+144,fo+1]:
                data=bytearray(original);data[offset]^=0xff;p.write_bytes(data)
                with self.assertRaises(ValueError): image(p,cfg,self.directory)


if __name__ == '__main__': unittest.main()
