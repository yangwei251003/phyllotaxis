"""Fetch the small, version-locked official source subset for offline builds.

No connected-device operation. Existing mismatched repositories are never reset.
First lock recording is an explicit maintainer action; normal runs verify hashes.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess, urllib.request

ROOT = Path(__file__).resolve().parent
LOCK = ROOT / 'sources.lock.json'
REPOS = {
    'stm32f4xx-hal-driver': ('v1.8.5', 'b6f0ed3829f3829eb358a2e7417d80bba1a42db7'),
    'cmsis-device-f4': ('v2.6.11', '0fa0e489e053fa1ca7790bb40b4d76458f64c55d'),
}
FILES = ['Include/cmsis_compiler.h', 'Include/cmsis_gcc.h',
         'Include/cmsis_version.h', 'Include/core_cm4.h',
         'Include/mpu_armv7.h', 'LICENSE.txt']

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--record-lock', action='store_true')
    args = p.parse_args()
    if not LOCK.exists() and not args.record_lock:
        raise SystemExit('sources.lock.json missing; do not fetch unverified sources')
    old = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    record = {'provider': 'STMicroelectronics official GitHub repositories',
              'cube_reference': 'v1.28.3', 'repositories': {}, 'files': {}}
    for name, (tag, commit) in REPOS.items():
        dst = ROOT / 'vendor' / name
        url = f'https://github.com/STMicroelectronics/{name}.git'
        if not dst.exists():
            subprocess.run(['git', 'clone', '--depth', '1', '--branch', tag, url, str(dst)], check=True)
        actual = subprocess.check_output(['git', '-C', str(dst), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != commit:
            raise SystemExit(f'{name}: unexpected commit {actual}; left untouched')
        if subprocess.check_output(['git', '-C', str(dst), 'status', '--porcelain'], text=True).strip():
            raise SystemExit(f'{name}: source checkout is modified; left untouched')
        record['repositories'][name] = {'url': url, 'tag': tag, 'commit': commit}
    for rel in FILES:
        dst = ROOT / 'vendor' / 'cmsis-core' / rel
        url = f'https://raw.githubusercontent.com/STMicroelectronics/STM32CubeF4/v1.28.3/Drivers/CMSIS/{rel}'
        if not dst.exists():
            content = urllib.request.urlopen(url, timeout=45).read()
            if not args.record_lock and hashlib.sha256(content).hexdigest() != old['files'][rel]['sha256']:
                raise SystemExit(f'{rel}: download checksum differs from lock')
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)
        sha = hashlib.sha256(dst.read_bytes()).hexdigest()
        if not args.record_lock and sha != old['files'][rel]['sha256']:
            raise SystemExit(f'{rel}: existing checksum differs from lock')
        record['files'][rel] = {'url': url, 'sha256': sha, 'bytes': dst.stat().st_size}
    if args.record_lock:
        LOCK.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'verified_repositories': len(REPOS), 'verified_core_files': len(FILES)}))

if __name__ == '__main__':
    main()
