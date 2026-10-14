"""离线核验全部分卷并还原完整ZIP；不启动任何策略、网络或服务。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore(manifest_path: Path, output: Path | None = None, verify_only: bool = False) -> dict:
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or not manifest.get('parts'):
        raise ValueError('unsupported/empty split manifest')
    names = [item['name'] for item in manifest['parts']]
    if len(set(names)) != len(names):
        raise ValueError('duplicate part names')
    for name in [manifest['zip'], *names]:
        if Path(name).name != name or name in {'.', '..'} or '/' in name or '\\' in name:
            raise ValueError('manifest filenames must be plain basenames')
    if sum(item['bytes'] for item in manifest['parts']) != manifest['bytes']:
        raise ValueError('manifest byte total mismatch')
    parts = []
    for item in manifest['parts']:
        part = root / item['name']
        if part.is_symlink() or not part.is_file() or part.stat().st_size != item['bytes']:
            raise ValueError(f"part missing/size invalid: {item['name']}")
        if digest(part) != item['sha256']:
            raise ValueError(f"part checksum invalid: {item['name']}")
        parts.append(part)
    if verify_only:
        return {'status': 'parts_verified', 'parts': len(parts), 'bytes': manifest['bytes']}
    output = output or root / manifest['zip']
    if output.is_symlink() or output.resolve() in {manifest_path, *(p.resolve() for p in parts)}:
        raise ValueError('output must not overwrite source or a symlink')
    if output.exists():
        if output.is_file() and output.stat().st_size == manifest['bytes'] and digest(output) == manifest['sha256']:
            with zipfile.ZipFile(output) as z:
                if z.testzip():
                    raise ValueError('existing ZIP CRC failed')
            return {'status': 'already_verified', 'zip': str(output), 'sha256': manifest['sha256']}
        raise ValueError('output already exists with different content; choose a fresh path')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.handoff-merge-', dir=output.parent, delete=False) as stream:
            temp = Path(stream.name)
            for part in parts:
                with part.open('rb') as source:
                    shutil.copyfileobj(source, stream, 1024 * 1024)
        if temp.stat().st_size != manifest['bytes'] or digest(temp) != manifest['sha256']:
            raise ValueError('combined ZIP checksum failed')
        with zipfile.ZipFile(temp) as z:
            if z.testzip():
                raise ValueError('combined ZIP CRC failed')
        # Do not replace another process/user's newly created file.
        with output.open('xb') as target, temp.open('rb') as source:
            shutil.copyfileobj(source, target, 1024 * 1024)
        return {'status': 'restored', 'zip': str(output), 'sha256': manifest['sha256'], 'crc': 'passed'}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('vnpy_handoff_20261014.manifest.json'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(restore(args.manifest, args.output, args.verify_only), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
