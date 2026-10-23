'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

function chinaDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'}).format(now);
}

function readRanking(uid) {
  // Read the user's public recent-week ranking directly from NetEase.
  const url = 'https://music.163.com/api/v1/play/record?' + new URLSearchParams({uid, type: '1'});
  let raw;
  try {
    raw = execFileSync(process.platform === 'win32' ? 'curl.exe' : 'curl', [
      '--silent', '--show-error', '--fail', '--max-time', '25',
      '--retry', '2', '--retry-all-errors', '--retry-delay', '2',
      '--user-agent', 'Mozilla/5.0', '--referer', 'https://music.163.com/', url,
    ], {encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  } catch {
    throw new Error('网易云周榜读取失败，请稍后重试；已有内容保持不变。');
  }
  try {return JSON.parse(raw);} catch {throw new Error('网易云返回格式异常。');}
}

function normalizeSong(raw) {
  const album = raw?.al, artists = raw?.ar;
  const validId = id => Number.isSafeInteger(id) && id > 0;
  const name = value => typeof value === 'string' && value.trim();
  const cover = String(album?.picUrl || '').replace(/^http:/, 'https:');
  if (!validId(raw?.id) || !name(raw.name) || !validId(album?.id) || !name(album.name)
      || !Array.isArray(artists) || !artists.length || artists.some(a => !validId(a.id) || !name(a.name))
      || !/^https:\/\/[^/\s]+\//.test(cover)) throw new Error('周榜榜首歌曲的资料不完整，未改选其他歌曲。');
  return {id: raw.id, name: raw.name, artists: artists.map(a => ({id: a.id, name: a.name})),
    album: {id: album.id, name: album.name, cover}};
}

function selectWinner(response) {
  if (response?.code !== 200 || !Array.isArray(response.weekData)) {
    throw new Error('无法读取公开周榜，请确认网易云听歌排行仍对外可见。');
  }
  const rows = response.weekData;
  if (!rows.length) return null;
  if (rows.some(row => !Number.isFinite(row.score) || row.score < 0)) throw new Error('网易云周榜排序数据异常。');
  // Anonymous responses mask playCount as 0. Use the ranking score, not those zeroes.
  // Equal scores retain the order returned by NetEase.
  const winner = rows.reduce((best, row) => row.score > best.score ? row : best);
  return normalizeSong(winner.song);
}

function run(site, api = readRanking, now = new Date()) {
  const read = file => JSON.parse(fs.readFileSync(path.join(site, file), 'utf8').replace(/^\uFEFF/, ''));
  const config = read('data/music-sync.json');
  if (config.enabled === false) return {status: 'disabled'};
  if (config.enabled !== true || !/^[1-9]\d*$/.test(String(config.netease_uid))) throw new Error('网易云账号配置不正确。');
  const stamp = chinaDate(now);
  const state = read('data/daily-song-state.json');
  if (Object.hasOwn(state, stamp)) return {status: 'unchanged', date: stamp};
  const song = selectWinner(api(String(config.netease_uid)));
  return song ? {status: 'ok', date: stamp, song} : {status: 'empty', date: stamp};
}

if (require.main === module) {
  try {
    const args = process.argv.slice(2);
    if (args.length !== 2 || args[0] !== '--output') throw new Error('需要指定输出文件。');
    const payload = run(path.resolve(__dirname, '..'));
    fs.writeFileSync(args[1], JSON.stringify(payload, null, 2) + '\n');
    console.log(payload.status === 'ok' ? '已读取 ' + payload.date + ' 的周榜榜首：' + payload.song.name : '周榜读取状态：' + payload.status);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = {chinaDate, normalizeSong, selectWinner, run};