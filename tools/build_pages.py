"""构建 GitHub Pages：更新静态列表，并适配仓库子路径。"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys


def build(site, base_path=''):
    site = Path(site).resolve()
    destination = site / '_site'
    if destination.exists():
        raise ValueError('输出目录 _site 已存在，请使用干净的工作目录构建。')
    base = '/' + base_path.strip('/') if base_path.strip('/') else ''
    if base and (not re.fullmatch(r'/[A-Za-z0-9._~/-]+', base) or '..' in base.split('/') or '//' in base):
        raise ValueError('GitHub Pages 路径格式不正确。')
    subprocess.run([sys.executable, str(site / 'tools' / 'update_content.py'), '--site', str(site)], check=True)
    destination.mkdir()
    for path in site.glob('*.html'):
        shutil.copyfile(path, destination / path.name)
    for directory in ('assets', 'columns'):
        shutil.copytree(site / directory, destination / directory)
    for name in ('CNAME', 'robots.txt', 'sitemap.xml', 'favicon.ico'):
        if (site / name).is_file():
            shutil.copyfile(site / name, destination / name)
    (destination / '.nojekyll').touch()
    if base:
        for path in destination.rglob('*.html'):
            text = path.read_bytes().decode('utf-8')
            # 只调整站内绝对路径，保留 // 外部地址、锚点和正文。
            text = re.sub(r'''(\b(?:href|src|poster|action)\s*=\s*["'])/(?!/)''', lambda m: m[1] + base + '/', text, flags=re.I)
            path.write_bytes(text.encode('utf-8'))
        for path in destination.rglob('*.css'):
            text = path.read_bytes().decode('utf-8')
            text = re.sub(r'''(url\(\s*["']?)/(?!/)''', lambda m: m[1] + base + '/', text, flags=re.I)
            path.write_bytes(text.encode('utf-8'))
    print(f'Built {destination}; Pages base path: {base or "/"}', flush=True)
    return destination


if __name__ == '__main__':
    build(Path(__file__).resolve().parents[1], os.environ.get('PAGES_BASE_PATH', ''))
