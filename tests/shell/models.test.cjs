// Тесты чистых функций оболочки shell/quietline/logic/Models.js без Quickshell.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../shell/quietline/logic/Models.js'),'utf8').replace(/^\.pragma library\s*/, '');
const M=vm.createContext({}); vm.runInContext(source,M);
const plain=value=>JSON.parse(JSON.stringify(value));
// Строки сокета движка из test_engine_protocol.py: подписка, отказы, события и ответы.
const protocol=require('./engine-protocol.json').lines;
const line=message=>JSON.stringify(message);
const state={revision:9,error:null,
 monitors:[{key:'left',name:'DP-1',focused:true,active_workspace_id:1,active_number:1,mode:'windows'},
           {key:'right',name:'DP-2',focused:false,active_workspace_id:2,active_number:1,mode:'tiles'}],
 workspaces:[{monitor_key:'left',display_monitor_key:'left',number:1,workspace_id:1,mode:'windows'},
             {monitor_key:'right',display_monitor_key:'right',number:1,workspace_id:2,mode:'tiles'}]};

// Повторяет приём строк в EngineClient.qml: новое соединение принимает первое состояние при любой ревизии.
function replay(lines,connection={revision:-1,fresh:true,state:null}){
 const seen=[];
 for(const message of lines){
  const response=M.decodeMessage(line(message),connection.revision,connection.fresh);
  seen.push(response);
  if(response.kind==='state'){connection.state=response.state;connection.revision=response.state.revision;connection.fresh=false;}
 }
 return {seen:plain(seen),connection};
}

test('every message the engine sends is understood by the shell',()=>{
 const {seen,connection}=replay(protocol);
 assert.deepEqual(seen.map(r=>r.kind),['state','error','state','error','state','ignore']);
 assert.deepEqual(seen.map(r=>r.id),[1,2,null,3,null,4]);
 assert.equal(seen[1].code,'invalid_number');
 assert.equal(seen[1].message,'Нет такого пространства: номера от 1 до 10');
 assert.equal(seen[3].code,'command_failed');
 assert.match(seen[3].message,/^Сервис окон не выполнил команду: mode switch failed/);
 assert.equal(connection.revision,5);
 assert.equal(connection.state.error,null);
});
test('an event with the same revision carries a new error text and a later one clears it',()=>{
 const {seen}=replay(protocol);
 assert.equal(seen[2].state.revision,seen[0].state.revision);
 assert.match(M.stateError(seen[2].state),/^Ошибка сервиса окон: mode switch failed/);
 assert.equal(M.stateError(seen[4].state),'');
});
test('engine state fields drive the panel: local buttons, migrated workspace and foreign workspace',()=>{
 const current=protocol[0].result;
 assert.equal(M.validState(current),true);
 const dp=plain(M.workspaceItems(current,'DP-1'));
 assert.deepEqual(dp.map(r=>r.label),['1','2','3','3 · Dell Inc. U2723QE']);
 assert.deepEqual(dp.map(r=>r.active),[true,false,false,false]);
 assert.equal(dp[3].monitor,'Dell Inc.|U2723QE|SN2');
 assert.equal(plain(M.activeWorkspace(current,'HDMI-A-1')).mode,'tiles');
 assert.equal(M.activeWorkspace(current,'eDP-1'),null);
 assert.equal(M.monitorKey(current,'HDMI-A-1'),'connector:HDMI-A-1');
 assert.equal(M.monitorKey(current,'connector:HDMI-A-1'),'connector:HDMI-A-1');
 assert.equal(M.monitorKey(current,'DP-9'),'');
 const after=replay(protocol).connection.state;
 assert.equal(plain(M.activeWorkspace(after,'DP-1')).workspace_id,1003);
 assert.equal(plain(M.workspaceItems(after,'DP-1'))[3].active,true);
});
test('a restarted engine starts over at a lower revision and a fresh subscription accepts it',()=>{
 const {connection}=replay(protocol);
 const restarted={...protocol[0],result:{...protocol[0].result,revision:0}};
 assert.equal(M.decodeMessage(line(restarted),connection.revision,false).kind,'ignore');
 const fresh=replay([restarted],{revision:-1,fresh:true,state:null});
 assert.equal(fresh.connection.revision,0);
 assert.equal(fresh.seen[0].kind,'state');
});
test('stale events are ignored on a live subscription but accepted on a fresh one',()=>{
 const event=line({event:'state',state});
 assert.equal(M.decodeMessage(event,12,false).kind,'ignore');
 assert.equal(M.decodeMessage(event,12,true).kind,'state');
 assert.equal(M.decodeMessage(event,9,false).kind,'state');
 assert.equal(M.decodeMessage(line({id:3,result:state}),9,false).kind,'ignore');
 assert.equal(M.decodeMessage(line({event:'other',state}),1,false).kind,'ignore');
});
test('snapshot validation rejects malformed state without replacing confirmed state',()=>{
 assert.equal(M.decodeMessage(line({id:1,result:state}),8,false).kind,'state');
 const broken=[
  {...state,workspaces:[{...state.workspaces[0],mode:'unknown'}]},
  {...state,workspaces:[{...state.workspaces[0],number:11}]},
  {...state,workspaces:[state.workspaces[0],{...state.workspaces[0],workspace_id:3}]},
  {...state,workspaces:[{monitor:'left',display_monitor:'left',number:1,workspace_id:1,mode:'windows'}]},
  {...state,monitors:[{...state.monitors[0],focused:'yes'}]},
  {...state,monitors:[{...state.monitors[0],mode:'floating'}]},
  {...state,monitors:[{...state.monitors[0],active_number:0}]},
  {...state,monitors:[state.monitors[0],state.monitors[0]]},
  {...state,error:3},
  {...state,revision:-1},
 ];
 for(const bad of broken){
  assert.equal(M.decodeMessage(line({id:1,result:bad}),8,false).kind,'invalid');
  assert.equal(M.decodeMessage(line({event:'state',state:bad}),8,false).kind,'invalid');
 }
 assert.equal(M.decodeMessage('not-json',8,false).kind,'invalid');
 assert.equal(M.decodeMessage('[1]',8,false).kind,'invalid');
});
test('request errors remain errors and never pretend to be state',()=>{
 const result=M.decodeMessage('{"id":7,"error":{"code":"unknown_method","message":"unknown method \'x\'"}}',9,false);
 assert.equal(result.kind,'error'); assert.equal(result.id,7);
 assert.equal(result.message,"Сервис окон не знает эту команду: unknown method 'x'");
 assert.equal(M.decodeMessage('{"id":null,"error":{"code":"invalid_request","message":"bad"}}',9,false).id,null);
 assert.equal(M.decodeMessage('{"id":8,"error":{}}',9,false).message,'Команда не выполнена');
});
test('monitor labels follow the engine keys',()=>{
 assert.equal(M.monitorLabel('connector:DP-1'),'DP-1');
 assert.equal(M.monitorLabel('Dell Inc.|U2723QE|SN1'),'Dell Inc. U2723QE');
 assert.equal(M.monitorLabel('Dell Inc.|U2723QE|SN1|DP-2'),'Dell Inc. U2723QE (DP-2)');
 assert.equal(M.monitorLabel('||SN9'),'SN9');
});
test('workspace buttons use local keys and preserve disconnected ownership',()=>{
 const s={...state,monitors:[state.monitors[0]],workspaces:[state.workspaces[0],{...state.workspaces[1],display_monitor_key:'left'}]};
 const rows=plain(M.workspaceItems(s,'DP-1'));
 assert.equal(rows[0].monitor,'left');assert.equal(rows[0].number,1);assert.equal(rows[0].active,true);
 assert.equal(rows.filter(row=>row.migrated).length,1);
 assert.equal(rows.find(row=>row.migrated).monitor,'right');
 assert.equal(rows.find(row=>row.migrated).workspace_id,2);
 assert.equal(M.activeWorkspace(s,'DP-2'),null);
});
const entries=[{id:'org.kde.dolphin',name:'Файлы',icon:'system-file-manager',startupClass:'dolphin'},{id:'code',name:'Code',icon:'code',startupClass:'Code'}];
const windows=[{address:'0x1',appId:'dolphin',monitor:'DP-1',workspace_id:1,focusHistoryID:4},{address:'0x2',appId:'dolphin',monitor:'DP-1',workspace_id:3,focusHistoryID:0},{address:'0x3',appId:'dolphin',monitor:'DP-2',workspace_id:2,focusHistoryID:0}];
test('dock groups local windows and focuses most recent even on another workspace',()=>{
 const groups=plain(M.groupApps(windows,'DP-1',['org.kde.dolphin','code'],entries));
 assert.equal(groups.length,2);assert.equal(groups[0].windows.length,2);assert.equal(groups[0].lastWindow.address,'0x2');
 assert.equal(groups[1].running,false);assert.equal(groups[1].available,true);
});
test('a foreign-monitor application is not treated as running locally',()=>{
 const groups=plain(M.groupApps(windows,'DP-3',['org.kde.dolphin','missing'],entries));
 assert.equal(groups[0].running,false);assert.equal(groups[0].lastWindow,null);
 assert.equal(groups[1].available,false);
});
test('fullscreen hides dock only on the affected active workspace and output',()=>{
 const ws=[{monitor:'DP-1',workspace_id:1,fullscreen:2},{monitor:'DP-2',workspace_id:2,fullscreen:1}];
 assert.equal(M.fullscreenOn(ws,'DP-1',1),true);
 assert.equal(M.fullscreenOn(ws,'DP-1',3),false);
 assert.equal(M.fullscreenOn(ws,'DP-2',2),false);
});
test('CPU parsing excludes guest double-counting and handles resets',()=>{
 assert.deepEqual(plain(M.parseCpu('cpu  10 2 5 80 3 0 0 0 10 0\ncpu0 1 2')), {total:100,idle:83});
 assert.equal(M.cpuUsage({total:100,idle:80},{total:200,idle:130},null),50);
 assert.equal(M.cpuUsage({total:200,idle:130},{total:100,idle:80},null),null);
 assert.equal(M.cpuUsage({total:100,idle:80},{total:200,idle:130},20),30.5);
});
test('memory uses MemAvailable and reports unavailable instead of invented values',()=>{
 assert.deepEqual(plain(M.parseMemory('MemTotal: 8388608 kB\nMemAvailable: 2097152 kB\nMemFree: 10 kB')), {used:6442450944,total:8589934592});
 assert.equal(M.parseMemory('MemFree: 10 kB'),null);
});
test('pin reorder is immutable and rejects invalid indices',()=>{
 const pins=['a','b','c'];
 assert.deepEqual(plain(M.movePin(pins,0,2)),['b','c','a']);assert.deepEqual(pins,['a','b','c']);
 assert.deepEqual(plain(M.movePin(pins,-1,2)),pins);
});
test('Lua dispatch accepts only literal compositor addresses',()=>{
 assert.equal(M.windowSelector('0xabc'), 'address:0xabc');
 assert.equal(M.windowSelector('abc'), 'address:0xabc');
 assert.equal(M.windowSelector('0x1\"); os.execute(\"bad\")'),null);
});
test('stable keys let delegates survive snapshot and title refreshes',()=>{
 const s={...state,workspaces:[...state.workspaces,{monitor_key:'right',display_monitor_key:'left',number:2,workspace_id:5,mode:'windows'}]};
 const keys=M.workspaceItems(s,'DP-1').map(M.workspaceKey);
 assert.equal(new Set(keys).size,keys.length);
 assert.deepEqual(plain(keys.slice(0,4)),['left:1','left:2','left:3','right:2']);
 const renamed={...s,revision:10};
 assert.deepEqual(plain(M.workspaceItems(renamed,'DP-1').map(M.workspaceKey)),plain(keys));
 const groups=[{id:'code',name:'Code'},{id:'ghostty',name:'Ghostty'}];
 const map=M.keyed(groups,group=>group.id);
 assert.equal(map.code.name,'Code');
 assert.equal(map.missing,undefined);
});
const rules=`! model
  pc105           Generic 105-key PC

! layout
  us              English (US)
  ru              Russian
  de              German

! variant
  phonetic        ru: Russian (phonetic)
  intl            us: English (US, intl., with dead keys)
`;
test('keyboard layout code comes from the XKB rule descriptions',()=>{
 const names=plain(M.parseXkbRules(rules));
 assert.equal(names['Russian'],'ru');
 assert.equal(names['Russian (phonetic)'],'ru');
 assert.equal(names['Generic 105-key PC'],undefined);
 assert.equal(M.layoutCode({active_keymap:'Russian (phonetic)',layout:'us,ru'},names),'RU');
 assert.equal(M.layoutCode({active_keymap:'English (US)',layout:'us,ru'},names),'US');
});
test('unknown keymap falls back to the active layout index, then to a placeholder',()=>{
 assert.equal(M.layoutCode({active_keymap:'Custom',layout:'us, de',active_layout_index:1},{}),'DE');
 assert.equal(M.layoutCode({active_keymap:'Custom',layout:'fr'},{}),'FR');
 assert.equal(M.layoutCode({active_keymap:'Custom',layout:'us,ru'},{}),'…');
 assert.equal(M.layoutCode(null,{}),'…');
});
const dockWindows=[
 {address:'0xa',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:1,activated:true,focusHistoryID:0},
 {address:'0xb',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:2,activated:false,focusHistoryID:2},
 {address:'0xc',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:1,activated:false,focusHistoryID:1},
 {address:'0xd',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:-98,activated:false,focusHistoryID:3},
];
const dockEntries=[{id:'org.kde.dolphin',name:'Dolphin',icon:'system-file-manager'}];
test('special workspaces are not shown as running applications in the dock',()=>{
 const group=plain(M.groupApps(dockWindows,'DP-1',[],dockEntries))[0];
 assert.deepEqual(group.windows.map(w=>w.address),['0xa','0xc','0xb']);
});
test('clicking an active application moves to its next recent window',()=>{
 const group=plain(M.groupApps(dockWindows,'DP-1',[],dockEntries))[0];
 assert.equal(M.clickTarget(group).address,'0xc');
 const inactive={...group,active:false,windows:group.windows.map(w=>({...w,activated:false}))};
 assert.equal(M.clickTarget(inactive).address,'0xa');
 assert.equal(M.clickTarget({windows:[]}),null);
});
test('wheel cycles the application windows in both directions',()=>{
 const group=plain(M.groupApps(dockWindows,'DP-1',[],dockEntries))[0];
 assert.equal(M.cycleTarget(group,1).address,'0xc');
 assert.equal(M.cycleTarget(group,-1).address,'0xb');
 assert.equal(M.cycleTarget({windows:[]},1),null);
});
