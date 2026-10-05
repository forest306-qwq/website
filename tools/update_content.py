"""从文章文件生成静态索引。仅使用 Python 标准库。"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import time


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def text(self):
        return ''.join(child.text() if isinstance(child, Element) else child for child in self.children)

    def find(self, tag=None, cls=None):
        for child in self.children:
            if isinstance(child, Element):
                if (tag is None or child.tag == tag) and (cls is None or cls in child.attrs.get('class', '').split()):
                    yield child
                yield from child.find(tag, cls)


class Document(HTMLParser):
    voids = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Element('document')
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Element(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.voids:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.voids:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def plain(node):
    return re.sub(r'\s+', ' ', node.text()).strip() if node else ''


def parse_date(value):
    match = re.search(r'(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})', value)
    return date(*map(int, match.groups())).isoformat() if match else None


def first(node, tag=None, cls=None):
    return next(node.find(tag, cls), None)


def ordered(entries):
    return sorted(entries, key=lambda entry: (entry['date'], entry['category'] != 'diary', entry['href']), reverse=True)


def collect(site):
    entries = []
    for path in sorted((site / 'columns').rglob('*.html')):
        if path.relative_to(site / 'columns').as_posix() in {'code.html', 'song.html'}:
            continue
        doc = Document(path.read_text(encoding='utf-8-sig')).root
        meta = {node.attrs.get('name', node.attrs.get('property', '')): node.attrs.get('content', '') for node in doc.find('meta')}
        if meta.get('article:draft', '').lower() in {'true', '1', 'yes'}:
            continue
        main = first(doc, 'main')
        title = plain(first(main, 'h1')) if main else ''
        if not title:
            continue  # 空文件/未完成的文章暂不发布。
        category = meta.get('article:category') or ('song' if path.stem.startswith('song-') else 'code')
        if category not in {'code', 'song'}:
            raise ValueError(f'{path.name}: article:category 只支持 code / song')
        filename_date = re.search(r'(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)', path.stem)
        stamp = parse_date(meta.get('article:date', ''))
        if not stamp and filename_date:
            yy, mm, dd = map(int, filename_date.groups())
            stamp = date(2000 + yy, mm, dd).isoformat()
        if not stamp:
            eyebrow = first(main, cls='eyebrow')
            stamp = parse_date(plain(eyebrow))
        if not stamp:
            stamp = next((parse_date(node.attrs.get('datetime', '')) for node in main.find('time') if parse_date(node.attrs.get('datetime', ''))), None)
        if not stamp:
            raise ValueError(f'{path.name}: 请使用 261003.html / song-261003.html，或填写 article:date')
        summary = meta.get('article:summary') or plain(first(main, cls='lead')) or plain(first(main, 'p'))
        entries.append(dict(title=title, date=stamp, category=category, summary=summary, href='/' + path.relative_to(site).as_posix()))
    diary = Document((site / 'diary.html').read_text(encoding='utf-8-sig')).root
    for node in diary.find('article', 'diary-item'):
        title = plain(first(node, 'h3'))
        stamp = parse_date(plain(first(node, cls='date')))
        anchor = node.attrs.get('id')
        if title and stamp and anchor:
            entries.append(dict(title=title, date=stamp, category='diary', summary='', href='/diary.html#' + anchor))
    return ordered(entries)


def replace_region(text, name, content, initial):
    start, end = f'<!-- AUTO:{name}:START -->', f'<!-- AUTO:{name}:END -->'
    newline = '\r\n' if '\r\n' in text else '\n'
    content = content.replace('\n', newline)
    block = start + newline + content + newline + '    ' + end
    if start in text or end in text:
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError(f'自动区域 {name} 标记不完整；未写入页面')
        a, b = text.index(start), text.index(end) + len(end)
        if b <= a:
            raise ValueError(f'自动区域 {name} 标记顺序错误')
        return text[:a] + block + text[b:]
    match = re.search(initial, text, re.S)
    if not match:
        raise ValueError(f'找不到 {name} 更新位置；未写入页面')
    return text[:match.start()] + block + text[match.end():]


def render_list(entries):
    if not entries:
        return '    <p class="note">还没有发布文章。</p>'
    return '\n\n'.join(
        '    <article class="diary-item">\n'
        f'      <div class="date"><time datetime="{e["date"]}">{e["date"].replace("-", " / ")}</time></div>\n'
        f'      <h3><a href="{escape(e["href"], quote=True)}">{escape(e["title"])}</a></h3>\n'
        f'      <a href="{escape(e["href"], quote=True)}">{escape(e["summary"])}</a>\n'
        '    </article>' for e in entries)


def manual_list_hrefs(text, region):
    """保留自动区域外的手动条目，避免再次生成同一篇文章。"""
    start, end = f'<!-- AUTO:{region}:START -->', f'<!-- AUTO:{region}:END -->'
    if text.count(start) != 1 or text.count(end) != 1:
        return set()
    outside = text[:text.index(start)] + text[text.index(end) + len(end):]
    main = first(Document(outside).root, 'main')
    hrefs = set()
    if main:
        for article in main.find('article', 'diary-item'):
            heading = first(article, 'h3')
            link = first(heading, 'a') if heading else None
            if link:
                hrefs.add(link.attrs.get('href', ''))
    return hrefs


def sync(site):
    entries = collect(site)
    labels = {'code': '计算机学习', 'song': '每日一歌', 'diary': '日记'}
    latest = '\n'.join(
        f'      <a class="latest-link" href="{escape(e["href"], quote=True)}"><span class="latest-title">{escape(e["title"])}</span><span class="latest-date">{labels[e["category"]]} · {e["date"]}</span></a>' for e in entries[:3])
    if not latest:
        latest = '      <p class="note">还没有发布内容。</p>'
    # 先完成所有解析、生成和校验，再写入；错误时保留原页面。
    updates = {}
    def load(relative):
        return (site / relative).read_bytes().decode('utf-8')
    updates['index.html'] = replace_region(load('index.html'), 'LATEST', latest,
        r'<a class="latest-link"[^>]*>.*?</a>(?:\s*<a class="latest-link"[^>]*>.*?</a>)*')
    counts = {}
    for category in ('code', 'song'):
        selected = [e for e in entries if e['category'] == category]
        counts[category] = len(selected)
        relative = f'columns/{category}.html'
        text = load(relative)
        region = category.upper() + '-LIST'
        manual = manual_list_hrefs(text, region)
        generated = [entry for entry in selected if entry['href'] not in manual]
        updates[relative] = replace_region(text, region, render_list(generated),
            r'<article class="diary-item"[^>]*>.*?</article>(?:\s*<article class="diary-item"[^>]*>.*?</article>)*(?:\s*<!-- 添加.*?-->)?')
    text = load('columns.html')
    for category, unit, suffix in [('code', '篇', 'Notes'), ('song', '首', 'Songs')]:
        pattern = rf'(<a class="cat-item" href="/columns/{category}\.html">.*?<span class="cat-meta">).*?(</span>)'
        text, matched = re.subn(pattern, lambda m: m[1] + f'{counts[category]} {unit} · {suffix}' + m[2], text, count=1, flags=re.S)
        if matched != 1:
            raise ValueError(f'找不到 {category} 数量位置；未写入页面')
    updates['columns.html'] = text
    changed = []
    for relative, text in updates.items():
        path = site / relative
        content = text.encode('utf-8')
        if path.read_bytes() != content:
            temporary = path.with_suffix(path.suffix + '.sync-tmp')
            temporary.write_bytes(content)
            temporary.replace(path)
            changed.append(relative)
    return {'counts': counts, 'latest': entries[:3], 'changed': changed}


def signature(site):
    paths = [site / 'diary.html'] + [p for p in (site / 'columns').rglob('*.html') if p.name not in {'code.html', 'song.html'}]
    result = []
    for path in sorted(paths):
        try:
            stat = path.stat()
            result.append((str(path), stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            pass
    return tuple(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--watch', action='store_true', help='保存文章后自动更新，Ctrl+C 停止')
    parser.add_argument('--stop', action='store_true', help='停止此网站正在运行的自动监听')
    args = parser.parse_args()
    site = args.site.resolve()
    stop_file = site / 'tools' / '.content-sync-stop'
    if args.stop:
        stop_file.write_text('stop', encoding='ascii')
        print('Stop requested. The watcher will stop within one second.', flush=True)
        return
    lock = None
    if args.watch:
        lock = (site / 'tools' / '.content-sync.lock').open('a+b')
        if os.fstat(lock.fileno()).st_size == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock.close()
            print('Auto-update is already running for this website.', flush=True)
            return
        stop_file.unlink(missing_ok=True)
    def run():
        try:
            result = sync(site)
            print(f'Updated: {result["counts"]["code"]} notes, {result["counts"]["song"]} songs; {len(result["changed"])} files changed.', flush=True)
            return True
        except (ValueError, OSError) as error:
            print(f'Update failed: {error}', flush=True)
            return False
    successful = run()
    if not args.watch:
        raise SystemExit(0 if successful else 1)
    print('Watching article files and diary.html. Press Ctrl+C to stop.', flush=True)
    previous = signature(site)
    try:
        while True:
            time.sleep(1)
            if stop_file.exists():
                stop_file.unlink(missing_ok=True)
                break
            current = signature(site)
            if current != previous:
                time.sleep(0.6)  # 等编辑器完成写入/重命名。
                stable = signature(site)
                if stable == current:
                    run()
                    previous = stable
    except KeyboardInterrupt:
        print('Stopped.', flush=True)
    finally:
        lock.close()


if __name__ == '__main__':
    main()
