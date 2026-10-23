"""在构建时读取网易云歌曲信息，页面无需调用跨域接口。"""
from html import escape
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen


def automated_entries(site, manual_entries):
    """自动选歌只保存日期和歌曲编号，页面仍使用同一套歌曲卡片。"""
    path = Path(site) / 'data' / 'daily-songs.json'
    if not path.is_file():
        return []
    archive = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(archive, dict):
        raise ValueError('自动选歌记录格式错误')
    manual_dates = {e['date'] for e in manual_entries if e['category'] == 'song'}
    selected = []
    for stamp, identifier in archive.items():
        if date.fromisoformat(stamp).isoformat() != stamp or not isinstance(identifier, str) or not identifier.isdecimal() or int(identifier) <= 0:
            raise ValueError('自动选歌日期或编号错误')
        if stamp not in manual_dates:
            selected.append((stamp, identifier))
    catalog = load_catalog(site, [identifier for _, identifier in selected])
    return [dict(date=stamp, title=catalog[identifier]['name'], song_id=identifier,
                 category='song', summary='', automatic=True,
                 href='/columns/song-auto-' + stamp.replace('-', '') + '.html')
            for stamp, identifier in selected]


def song_id(main, meta):
    explicit = meta.get('music:song-id', '')
    if explicit:
        if not explicit.isdecimal():
            raise ValueError('music:song-id 必须是网易云歌曲编号')
        return str(int(explicit))
    for link in main.find('a'):
        url = urlsplit(link.attrs.get('href', ''))
        if url.hostname != 'music.163.com':
            continue
        route = urlsplit(url.fragment) if url.fragment else url
        if route.path.rstrip('/') == '/song':
            identifier = parse_qs(route.query).get('id', [''])[0]
            if identifier.isdecimal():
                return str(int(identifier))
    raise ValueError('每日一歌文章需要填写网易云歌曲链接，或 music:song-id')


def validate(item, identifier):
    if str(item.get('id')) != identifier or not item.get('name'):
        raise ValueError(f'歌曲 {identifier} 的名称或编号不完整')
    artists = item.get('artists', [])
    if not artists or any(not str(a.get('id', '')).isdecimal() or not a.get('name') for a in artists):
        raise ValueError(f'歌曲 {identifier} 缺少艺人信息')
    album = item.get('album', {})
    if not str(album.get('id', '')).isdecimal() or not album.get('name'):
        raise ValueError(f'歌曲 {identifier} 缺少专辑信息')
    cover = urlsplit(album.get('cover', ''))
    if cover.scheme != 'https' or not cover.hostname:
        raise ValueError(f'歌曲 {identifier} 缺少 HTTPS 专辑封面')
    return item


def load_catalog(site, identifiers):
    path = Path(site) / 'assets' / 'song-catalog.json'
    catalog = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    missing = sorted(set(identifiers) - set(catalog))
    if missing:
        url = 'https://music.163.com/api/song/detail/?ids=' + quote(json.dumps([int(i) for i in missing]))
        request = Request(url, headers={'Referer': 'https://music.163.com/', 'User-Agent': 'Mozilla/5.0'})
        try:
            with urlopen(request, timeout=12) as response:
                result = json.load(response)
            if result.get('code') != 200:
                raise ValueError('网易云返回的状态异常')
            for raw in result.get('songs', []):
                identifier = str(raw['id'])
                if identifier not in missing:
                    continue
                album = raw.get('album', {})
                item = {'id': raw['id'], 'name': raw['name'],
                        'artists': [{'id': a['id'], 'name': a['name']} for a in raw.get('artists', [])],
                        'album': {'id': album.get('id'), 'name': album.get('name'),
                                  'cover': str(album.get('picUrl', '')).replace('http://', 'https://', 1)}}
                catalog[identifier] = validate(item, identifier)
            if any(identifier not in catalog for identifier in missing):
                raise ValueError('部分歌曲没有返回信息')
        except Exception as error:
            raise ValueError('新歌曲信息读取失败，请检查网易云歌曲编号；已有歌曲使用已保存的信息。') from error
    for identifier in identifiers:
        validate(catalog[identifier], identifier)
    if missing:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.json.sync-tmp')
        temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        temporary.replace(path)
    return catalog


def anchor(entry):
    path = entry['href'].removeprefix('/columns/').removesuffix('.html')
    return re.sub(r'[^A-Za-z0-9_-]', '-', path)


def entry_href(entry):
    return '/columns/song.html#' + anchor(entry) if entry['category'] == 'song' else entry['href']


def netease(kind, identifier):
    return f'https://music.163.com/#/{kind}?id={int(identifier)}'


def render_songs(entries, catalog):
    if not entries:
        return '    <p class="note">还没有分享歌曲。</p>'
    cards = []
    for entry in entries:
        item = catalog[entry['song_id']]
        album = item['album']
        album_name = escape(album['name'], quote=True)
        cover = album['cover'] + ('&' if '?' in album['cover'] else '?') + 'param=320y320'
        artists = ' / '.join(f'<a href="{netease("artist", a["id"])}" target="_blank" rel="noopener noreferrer">{escape(a["name"])}</a>' for a in item['artists'])
        note = f'        <p class="song-note">{escape(entry["summary"])}</p>\n' if entry['summary'] else ''
        cards.append(
            f'    <article class="song-entry" id="{anchor(entry)}">\n'
            f'      <a class="song-cover" href="{netease("album", album["id"])}" target="_blank" rel="noopener noreferrer" aria-label="在网易云打开《{album_name}》专辑（新窗口）">\n'
            f'        <img src="{escape(cover, quote=True)}" alt="《{album_name}》专辑封面" width="320" height="320" loading="lazy" decoding="async">\n'
            '      </a>\n'
            '      <div class="song-info">\n'
            f'        <div class="date"><time datetime="{entry["date"]}">{entry["date"].replace("-", " / ")}</time></div>\n'
            f'        <h3><a href="{netease("song", item["id"])}" target="_blank" rel="noopener noreferrer">{escape(item["name"])}</a></h3>\n'
            f'        <p class="song-artists"><span class="song-label">艺人</span>{artists}</p>\n'
            f'        <p class="song-album"><span class="song-label">专辑</span><a href="{netease("album", album["id"])}" target="_blank" rel="noopener noreferrer">{escape(album["name"])}</a></p>\n'
            + note + '      </div>\n    </article>')
    return '\n\n'.join(cards)
