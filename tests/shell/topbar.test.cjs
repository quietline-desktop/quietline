// Тесты функций верхней панели из shell/quietline/logic/Models.js: значки Wi‑Fi и звука, колесо по
// пространствам, номера меню окна, уровень батареи и индикатор микрофона.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../shell/quietline/logic/Models.js'),'utf8').replace(/^\.pragma library\s*/, '');
const M=vm.createContext({}); vm.runInContext(source,M);
const plain=value=>JSON.parse(JSON.stringify(value));

test('bar wifi symbol follows signal strength and falls back to the plain icon', () => {
  assert.equal(M.barWifiSymbol(null), 'wifi');
  assert.equal(M.barWifiSymbol(undefined), 'wifi');
  assert.equal(M.barWifiSymbol(80), 'signal_wifi_4_bar');
  assert.equal(M.barWifiSymbol(60), 'network_wifi_3_bar');
  assert.equal(M.barWifiSymbol(10), 'network_wifi_1_bar');
});

test('volume symbol shows mute, silence and level', () => {
  assert.equal(M.volumeSymbol(0.8, true), 'volume_off');
  assert.equal(M.volumeSymbol(0, false), 'volume_mute');
  assert.equal(M.volumeSymbol(0.3, false), 'volume_down');
  assert.equal(M.volumeSymbol(0.5, false), 'volume_up');
});

const items=[
  {number:1, active:false, migrated:false},
  {number:3, active:true, migrated:false},
  {number:4, active:false, migrated:true},
  {number:5, active:false, migrated:false},
];

test('wheel moves to the neighbouring own workspace without wrapping', () => {
  assert.equal(M.wheelWorkspace(items, 1).number, 5);
  assert.equal(M.wheelWorkspace(items, -1).number, 1);
  assert.equal(M.wheelWorkspace(items.map(item => ({...item, active: item.number === 5})), 1), null);
  assert.equal(M.wheelWorkspace([], 1), null);
});

test('move targets go one past the highest own workspace, up to ten', () => {
  assert.deepEqual(plain(M.moveTargets(items)), [1, 2, 3, 4, 5, 6]);
  assert.deepEqual(plain(M.moveTargets([{number: 1, migrated: false}])), [1, 2]);
  assert.equal(M.moveTargets([{number: 10, migrated: false}]).length, 10);
  assert.deepEqual(plain(M.moveTargets([])), [1]);
});

test('battery level warns at 20 and 10 percent unless charging', () => {
  assert.equal(M.batteryLevel(21, false), 'normal');
  assert.equal(M.batteryLevel(20, false), 'low');
  assert.equal(M.batteryLevel(10, false), 'critical');
  assert.equal(M.batteryLevel(5, true), 'normal');
});

test('microphone users skip the shell and repeats', () => {
  assert.deepEqual(plain(M.micUsers([
    {'application.name': 'Chromium', 'node.name': 'chromium-input'},
    {'application.name': 'Chromium'},
    {'application.name': 'Quickshell'},
    {'node.name': 'peak', 'application.process.binary': 'qs'},
    {'node.name': 'obs-mic'},
    null,
  ])), ['Chromium', 'obs-mic']);
});
