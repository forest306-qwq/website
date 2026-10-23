"""保存每日周榜榜首，跳过与前一天重复的歌曲，并同步页面与数量。"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys

from song_metadata import validate
from update_content import collect, sync


def read_map(path):
    value = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    if not isinstance(value, dict):
        raise ValueError('自动选歌数据格式错误')
    for stamp, identifier in value.items():
        if date.fromisoformat(stamp).isoformat() != stamp or not isinstance(identifier, str) or not identifier.isdecimal() or int(identifier) <= 0:
            raise ValueError('自动选歌日期或编号错误')
    return value


def save_winner(site, payload):
    site = Path(site)
    stamp = payload.get('date', '')
    today = date.fromisoformat(stamp)
    if today.isoformat() != stamp:
        raise ValueError('日期格式不正确')
    if payload.get('status') == 'empty':
        return '周榜暂无记录，保留已有内容。'
    if payload.get('status') != 'ok':
        raise ValueError('歌曲数据状态不正确')
    song = payload.get('song', {})
    identifier = str(song.get('id', ''))
    if not identifier.isdecimal() or int(identifier) <= 0:
        raise ValueError('歌曲编号不正确')
    validate(song, identifier)
    archive_path = site / 'data' / 'daily-songs.json'
    state_path = site / 'data' / 'daily-song-state.json'
    catalog_path = site / 'assets' / 'song-catalog.json'
    archive, state = read_map(archive_path), read_map(state_path)
    if stamp in state or stamp in archive:
        return '当天已经处理过，保留当天的选择。'
    manual = [e for e in collect(site) if e['category'] == 'song' and not e.get('automatic')]
    yesterday = (today - timedelta(days=1)).isoformat()
    previous = {state.get(yesterday), archive.get(yesterday)}
    previous.update(e['song_id'] for e in manual if e['date'] == yesterday)
    state[stamp] = identifier  # 跳过发布的日期也记住榜首，避免连续相同榜首隔天反复出现。
    updates = {state_path: state}
    publish = False
    if any(e['date'] == stamp for e in manual):
        message = '当天已有手动选歌，保留手动内容。'
    elif identifier in previous:
        message = f'{stamp} 的榜首与前一天重复，跳过新增。'
    else:
        archive[stamp] = identifier
        catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
        catalog[identifier] = song
        updates.update({archive_path: archive, catalog_path: catalog})
        publish = True
        message = f'已同步 {stamp} 的每日一歌。'
    # 若生成器失败，连同生成页面一起恢复，绝不提交半完成的结果。
    affected = set(updates)
    if publish:
        affected.update(site / name for name in ('index.html', 'columns.html', 'columns/song.html', 'columns/code.html'))
    before = {p: p.read_bytes() if p.exists() else None for p in affected}
    try:
        for p, data in updates.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        if publish:
            sync(site)
    except Exception:
        for p, old in before.items():
            if old is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(old)
        raise
    return message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
        if payload.get('status') in ('disabled', 'unchanged'):
            print('未启用自动选歌，或当天已处理；保留原网页。')
            return
        print(save_winner(args.site, payload))
    except (ValueError, OSError, KeyError, TypeError):
        print('每日一歌同步失败；请检查歌曲信息或生成器。未发布更改。', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()