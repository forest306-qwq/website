'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chinaDate, selectWinner, run} = require('./fetch_daily_song.cjs');

const song = id => ({id, name: 'Song ' + id, ar: [{id: 3, name: 'Artist'}],
  al: {id: 4, name: 'Album', picUrl: 'http://p1.music.126.net/cover.jpg'}});
const ranking = rows => ({code: 200, weekData: rows});

test('北京时间跨日正确', () => {
  assert.equal(chinaDate(new Date('2026-10-23T15:59:59Z')), '2026-10-23');
  assert.equal(chinaDate(new Date('2026-10-23T16:00:00Z')), '2026-10-24');
});
test('匿名播放次数被隐藏时按周榜分值选歌，并保留全部链接资料', () => {
  const winner = selectWinner(ranking([{score: 68, playCount: 0, song: song(1)}, {score: 100, playCount: 0, song: song(2)}]));
  assert.equal(winner.id, 2);
  assert.deepEqual(winner.artists, [{id: 3, name: 'Artist'}]);
  assert.deepEqual(winner.album, {id: 4, name: 'Album', cover: 'https://p1.music.126.net/cover.jpg'});
});
test('并列保持网易云顺序；空榜不产生歌曲', () => {
  assert.equal(selectWinner(ranking([{score: 100, song: song(1)}, {score: 100, song: song(2)}])).id, 1);
  assert.equal(selectWinner(ranking([])), null);
});
test('隐私限制或不完整资料报错，不擅自替换为第二名', () => {
  assert.throws(() => selectWinner({code: 403, weekData: []}));
  assert.throws(() => selectWinner({code: 200}));
  assert.throws(() => selectWinner(ranking([{score: '100', song: song(1)}])));
  assert.throws(() => selectWinner(ranking([{score: 100, song: {id: 1}}, {score: 50, song: song(2)}])));
});
test('账号接入、当天重跑和禁用状态', () => {
  const site = fs.mkdtempSync(path.join(__dirname, '.weekly-test-'));
  try {
    fs.mkdirSync(path.join(site, 'data'));
    const write = (name, data) => fs.writeFileSync(path.join(site, 'data', name), JSON.stringify(data));
    write('music-sync.json', {enabled: true, netease_uid: '1821006895'});
    write('daily-song-state.json', {});
    const now = new Date('2026-10-23T12:00:00Z');
    let calls = 0;
    const api = uid => {calls++; assert.equal(uid, '1821006895'); return ranking([{score: 100, song: song(1)}]);};
    assert.equal(run(site, api, now).song.id, 1);
    assert.equal(calls, 1);
    write('daily-song-state.json', {'2026-10-23': '1'});
    assert.equal(run(site, api, now).status, 'unchanged');
    assert.equal(calls, 1);
    write('music-sync.json', {enabled: false});
    assert.equal(run(site, api, now).status, 'disabled');
    assert.equal(calls, 1);
  } finally {
    const relative = path.relative(__dirname, site);
    if (!relative.startsWith('.weekly-test-') || relative.includes(path.sep)) throw new Error('Unexpected test directory');
    fs.rmSync(site, {recursive: true});
  }
});
