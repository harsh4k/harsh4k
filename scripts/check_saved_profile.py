"""Verify saved-data rendering without changing the checked-in images."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def main():
    expected = {path.name: path.read_text(encoding='utf-8')
                for path in (ROOT / 'assets').glob('*.svg')}
    assert expected, 'No committed profile SVGs were found.'
    with tempfile.TemporaryDirectory(prefix='profile-check-') as folder:
        sandbox = Path(folder)
        shutil.copytree(ROOT / 'src', sandbox / 'src')
        (sandbox / 'assets').mkdir()
        shutil.copyfile(ROOT / 'assets/github.json', sandbox / 'assets/github.json')
        (sandbox / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/build.py', sandbox / 'scripts/build.py')
        data = (sandbox / 'assets/github.json').read_bytes()
        env = os.environ.copy()
        env.pop('GITHUB_TOKEN', None)
        subprocess.run([sys.executable, 'scripts/build.py'], cwd=sandbox,
                       env=env, check=True, timeout=60)
        assert (sandbox / 'assets/github.json').read_bytes() == data, (
            'Saved-data rendering changed the GitHub snapshot.')
        assert {path.name for path in (sandbox / 'assets').glob('*.svg')} == set(expected), (
            'The generated SVG set differs from the committed profile images.')
        for name, committed in expected.items():
            path = sandbox / 'assets' / name
            root = ET.parse(path).getroot()
            assert root.tag == '{http://www.w3.org/2000/svg}svg', name
            assert path.read_text(encoding='utf-8') == committed, (
                f'{name} differs from a saved-data redraw. Regenerate and review the images.')
        print(f'saved-data generator: {len(expected)} unchanged, valid SVGs')


if __name__ == '__main__':
    main()
