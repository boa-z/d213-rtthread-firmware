# SPDX-License-Identifier: Apache-2.0
"""Independent fail-closed checks for the supported D213 image contract."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/artinchip'))
import fdt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def config(path):
    return json.loads(re.sub(r'//[^\n]*', '', Path(path).read_text()))


def size(value):
    value = str(value).lower()
    return int(value[:-1]) * {'k': 1024, 'm': 1024**2}[value[-1]] if value[-1] in 'km' else int(value, 0)


def layout(cfg):
    parts = {}
    offset = 0
    for name, part in cfg['spi-nand']['partitions'].items():
        length = size(part['size'])
        require(length > 0 and length % 131072 == 0, 'unaligned partition')
        parts[name] = (offset, length)
        offset += length
    require(offset <= size(cfg['spi-nand']['size']), 'NAND partition overflow')
    require(parts == {'spl': (0, 1048576), 'env': (1048576, 262144),
        'env_r': (1310720, 262144), 'os': (1572864, 4194304),
        'os_r': (5767168, 4194304), 'rodata': (9961472, 12582912),
        'rodata_r': (22544384, 12582912), 'data': (35127296, 41943040),
        'data_r': (77070336, 41943040), 'refresh': (119013376, 1048576)},
        'D213 verified partition contract changed')
    require(cfg['image']['info']['media'] == {'type': 'spi-nand', 'device_id': 0,
        'array_organization': [{'page': '2k', 'block': '128k', 'oob': '64'}]}, 'NAND geometry changed')
    loader = cfg['pre-process']['aicimage']['loader.aic']['loader']
    require(int(loader['load address'], 0) == 0x47b80000 and
            int(loader['entry point'], 0) == 0x47b80100, 'Bootloader address changed')
    def unsigned(obj):
        if isinstance(obj, dict):
            require(not ({'signature', 'encryption'} & obj.keys()), 'secure profiles unsupported')
            for value in obj.values(): unsigned(value)
        elif isinstance(obj, list):
            for value in obj: unsigned(value)
    unsigned(cfg)
    return parts


def elf(path):
    data = Path(path).read_bytes()
    require(data[:6] == b'\x7fELF\x02\x01', 'expected little-endian ELF64')
    require(struct.unpack_from('<H', data, 18)[0] == 243, 'expected RISC-V')
    require(struct.unpack_from('<I', data, 48)[0] & 7 == 5, 'expected RVC/lp64d ABI')
    require(struct.unpack_from('<Q', data, 24)[0] == 0x40000000, 'wrong ELF entry')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    entsize, count = struct.unpack_from('<HH', data, 54)
    segments = []
    for i in range(count):
        ptype, flags, off, va, pa, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', data, phoff+i*entsize)
        if ptype != 1: continue
        require(filesz <= memsz and off+filesz <= len(data), 'invalid ELF segment')
        require(va == pa and 0x40000000 <= va < va+memsz <= 0x47800000,
                'ELF overlaps bootloader reservation or exceeds DDR')
        if filesz:
            segments.append((va, data[off:off+filesz], memsz))
    require(segments and segments[0][0] == 0x40000000, 'missing entry segment')
    return segments


def propbytes(prop):
    if isinstance(prop, fdt.PropBytes): return bytes(prop.data)
    if isinstance(prop, fdt.PropWords): return b''.join(struct.pack('>I', v) for v in prop.data)
    raise ValueError('expected binary FDT property')


def fit(path, elf_path):
    data = Path(path).read_bytes()
    require(len(data) <= 4194304, 'FIT exceeds OS partition')
    tree = fdt.parse_dtb(data)
    images = tree.get_node('/images')
    segments = elf(elf_path)
    nodes = list(images.nodes)
    require(len(nodes) == len(segments), 'FIT/ELF segment count mismatch')
    confs = tree.get_node('/configurations')
    default = confs.get_property('default')[0]
    conf = tree.get_node('/configurations/' + default)
    require(list(conf.get_property('firmware').data) == [n.name for n in nodes], 'FIT firmware order mismatch')
    for i, (node, (addr, payload, memsz)) in enumerate(zip(nodes, segments)):
        get = node.get_property
        require(get('load')[0] == addr, 'FIT load differs from ELF')
        require(get('entry')[0] == 0x40000000, 'wrong FIT entry')
        require(get('arch')[0] == 'riscv' and get('os')[0] == 'artinchip', 'wrong FIT platform')
        if get('data') is not None:
            actual = propbytes(get('data'))
        else:
            total = struct.unpack_from('>I', data, 4)[0]
            base = (total+2047) & ~2047
            start, length = get('data-position')[0], get('data-size')[0]
            require(start == base + get('data-offset')[0] and start >= base and start % 2048 == 0
                    and start+length <= len(data), 'FIT external data bounds')
            actual = data[start:start+length]
        # Vendor extraction skips NOBITS; permit trailing zero alignment only.
        require(actual[:len(payload)] == payload and not any(actual[len(payload):])
                and len(payload) <= len(actual) <= memsz, 'FIT payload differs from ELF')
        hashes = {n.get_property('algo')[0]: propbytes(n.get_property('value')) for n in node.nodes}
        expected = {'crc32': struct.pack('>I', zlib.crc32(actual)), 'md5': hashlib.md5(actual).digest()}
        require(hashes == expected, 'FIT hash mismatch')
    return {'segments': len(nodes), 'size': len(data), 'sha256': sha(path)}


def resources(directory, lock):
    for name, spec in lock['boot_resources'].items():
        path = Path(directory) / name
        require(path.is_file() and path.stat().st_size == spec['size'] and sha(path) == spec['sha256'],
                'unrecognized boot resource: ' + name)


def boot_images(directory):
    directory = Path(directory)
    for name in ['loader.aic', 'pbp_ext.aic', 'usbupg-ddr-init.aic']:
        data = (directory/name).read_bytes()
        require(data[:4] == b'AIC ', 'wrong BROM header magic')
        version, length = struct.unpack_from('<II', data, 8)
        require(version == 0x10001 and 256 <= length <= len(data), 'wrong BROM version/length')
        raw = data[:length]
        require(sum(int.from_bytes(raw[i:i+4], 'little') for i in range(0,length,4)) & 0xffffffff == 0xffffffff, 'BROM checksum mismatch')
        require(hashlib.md5(raw[8:-16]).digest() == raw[-16:], 'BROM MD5 mismatch')
        privoff, privlen, pbpoff, pbplen = struct.unpack_from('<IIII', data, 64)
        require(raw[privoff:privoff+privlen] == (directory/'ddr_init.bin').read_bytes(), 'DDR/partition private resource mismatch')
        if name == 'loader.aic':
            loaderlen, load, entry = struct.unpack_from('<III', raw, 20)
            require((load,entry) == (0x47b80000,0x47b80100), 'wrong BROM loader addresses')
            require(raw[256:256+loaderlen] == (directory/'bootloader.bin').read_bytes(), 'BROM loader payload mismatch')
        else:
            require(raw[pbpoff:pbpoff+pbplen] == (directory/'d21x.pbp').read_bytes(), 'BROM PBP payload mismatch')
    require((directory/'bootloader.aic').read_bytes() == (directory/'pbp_ext.aic').read_bytes() + (directory/'loader.aic').read_bytes(), 'boot concatenation mismatch')
    env = (directory/'env.bin').read_bytes()
    require(len(env) == 4096 and env[4] == 1 and struct.unpack_from('<I', env)[0] == zlib.crc32(env[5:]), 'redundant environment CRC/size mismatch')


def image(path, cfg, directory):
    data = Path(path).read_bytes()
    parts = layout(cfg)
    require(data[:8] == b'AIC.FW\0\0', 'wrong ArtInChip IMG magic')
    require(data[8:72].rstrip(b'\0') == b'd21x' and data[72:136].rstrip(b'\0') == b'd213_demo128_page_2k_block_128k', 'wrong IMG board')
    require(data[136:200].rstrip(b'\0') == b'1.0.0' and data[200:264].rstrip(b'\0') == b'spi-nand'
            and data[264:268] == b'\0'*4 and data[268:332].rstrip(b'\0') == b'P=2K,B=128K', 'wrong IMG version/media/geometry')
    mo, ms, fo, fs = struct.unpack_from('<IIII', data, 332)
    require(mo == 2048 and ms % 512 == 0 and fo == mo+ms and fo+fs == len(data), 'IMG header bounds')
    expected = {f'image.{section}.{name}': spec for section in ('updater', 'target') for name, spec in cfg['image'][section].items()}
    expected['image.info'] = None
    found = set()
    ranges = []
    for offset in range(mo, mo+ms, 512):
        meta = data[offset:offset+512]
        if meta[:4] != b'META':
            require(not any(meta), 'invalid IMG metadata padding')
            continue
        string = lambda a,b: meta[a:b].split(b'\0')[0].decode()
        name, part = string(8,72), string(72,104)
        require(name in expected and name not in found, 'unexpected/duplicate IMG component')
        found.add(name)
        spec = expected[name]
        po, ps = struct.unpack_from('<II', meta, 104)
        dev = string(112,132)
        did, start, length, crc, ram = struct.unpack_from('<IIIII', meta, 132)
        if name == 'image.info':
            require((start, length, po, ps, dev, did, ram) == (0, 2048, 0, 0, 'ram', 0, 0xffffffff), 'IMG info metadata mismatch')
            require(zlib.crc32(data[:2048]) == crc and string(216,280) == 'info.bin' and string(152,216) == 'required', 'IMG header CRC mismatch')
            continue
        require(start >= fo and (start-fo) % 2048 == 0 and start+length <= len(data), 'IMG component bounds')
        payload = data[start:start+length]
        require(zlib.crc32(payload) == crc, 'IMG component CRC mismatch')
        require(payload == (Path(directory)/spec['file']).read_bytes(), 'IMG payload differs from input')
        require(string(216,280) == spec['file'] and string(152,216) == ';'.join(spec['attr']), 'IMG component metadata mismatch')
        if name.startswith('image.target.'):
            require(part == spec['part'][0] and (po,ps) == parts[part] and length <= ps,
                    'IMG partition mismatch/overflow')
            require(dev == 'spi-nand' and did == 0 and ram == 0xffffffff, 'IMG target device mismatch')
        else:
            require(dev == 'ram' and ram == int(spec['ram'], 0), 'IMG updater RAM address mismatch')
        ranges.append((start, start+length))
    require(found == set(expected), 'missing required IMG components')
    ranges.sort()
    require(all(a[1] <= b[0] for a,b in zip(ranges,ranges[1:])), 'IMG payload overlap')
    return {'components': len(found), 'size': len(data), 'sha256': sha(path)}
