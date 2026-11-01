// Тесты чистых функций оболочки shell/quietline/logic/Models.js без Quickshell.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../shell/quietline/logic/Models.js'),'utf8').replace(/^\.pragma library\s*/, '');
const M=vm.createContext({}); vm.runInContext(source,M);
// Таблицы строк передаются функциям аргументом, как `Lang.s` в QML.
const stringsSource=fs.readFileSync(path.join(__dirname,'../../shell/quietline/logic/Strings.js'),'utf8').replace(/^\.pragma library\s*/, '');
const S=vm.createContext({}); vm.runInContext(stringsSource,S);
const ru=S.table('ru'), en=S.table('en');
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
  const response=M.decodeMessage(line(message),connection.revision,connection.fresh,ru);
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
 assert.match(M.stateError(seen[2].state,ru),/^Ошибка сервиса окон: mode switch failed/);
 assert.equal(M.stateError(seen[4].state,ru),'');
});
test('engine state fields drive the panel: local buttons, migrated workspace and foreign workspace',()=>{
 const current=protocol[0].result;
 assert.equal(M.validState(current),true);
 const dp=plain(M.workspaceItems(current,'DP-1',ru));
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
 assert.equal(plain(M.workspaceItems(after,'DP-1',ru))[3].active,true);
});
test('a restarted engine starts over at a lower revision and a fresh subscription accepts it',()=>{
 const {connection}=replay(protocol);
 const restarted={...protocol[0],result:{...protocol[0].result,revision:0}};
 assert.equal(M.decodeMessage(line(restarted),connection.revision,false,ru).kind,'ignore');
 const fresh=replay([restarted],{revision:-1,fresh:true,state:null});
 assert.equal(fresh.connection.revision,0);
 assert.equal(fresh.seen[0].kind,'state');
});
test('stale events are ignored on a live subscription but accepted on a fresh one',()=>{
 const event=line({event:'state',state});
 assert.equal(M.decodeMessage(event,12,false,ru).kind,'ignore');
 assert.equal(M.decodeMessage(event,12,true,ru).kind,'state');
 assert.equal(M.decodeMessage(event,9,false,ru).kind,'state');
 assert.equal(M.decodeMessage(line({id:3,result:state}),9,false,ru).kind,'ignore');
 assert.equal(M.decodeMessage(line({event:'other',state}),1,false,ru).kind,'ignore');
});
test('snapshot validation rejects malformed state without replacing confirmed state',()=>{
 assert.equal(M.decodeMessage(line({id:1,result:state}),8,false,ru).kind,'state');
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
  assert.equal(M.decodeMessage(line({id:1,result:bad}),8,false,ru).kind,'invalid');
  assert.equal(M.decodeMessage(line({event:'state',state:bad}),8,false,ru).kind,'invalid');
 }
 assert.equal(M.decodeMessage('not-json',8,false,ru).kind,'invalid');
 assert.equal(M.decodeMessage('[1]',8,false,ru).kind,'invalid');
});
test('request errors remain errors and never pretend to be state',()=>{
 const result=M.decodeMessage('{"id":7,"error":{"code":"unknown_method","message":"unknown method \'x\'"}}',9,false,ru);
 assert.equal(result.kind,'error'); assert.equal(result.id,7);
 assert.equal(result.message,"Сервис окон не знает эту команду: unknown method 'x'");
 assert.equal(M.decodeMessage('{"id":null,"error":{"code":"invalid_request","message":"bad"}}',9,false,ru).id,null);
 assert.equal(M.decodeMessage('{"id":8,"error":{}}',9,false,ru).message,'Команда не выполнена');
});
test('monitor labels follow the engine keys',()=>{
 assert.equal(M.monitorLabel('connector:DP-1'),'DP-1');
 assert.equal(M.monitorLabel('Dell Inc.|U2723QE|SN1'),'Dell Inc. U2723QE');
 assert.equal(M.monitorLabel('Dell Inc.|U2723QE|SN1|DP-2'),'Dell Inc. U2723QE (DP-2)');
 assert.equal(M.monitorLabel('||SN9'),'SN9');
});
test('workspace buttons use local keys and preserve disconnected ownership',()=>{
 const s={...state,monitors:[state.monitors[0]],workspaces:[state.workspaces[0],{...state.workspaces[1],display_monitor_key:'left'}]};
 const rows=plain(M.workspaceItems(s,'DP-1',ru));
 assert.equal(rows[0].monitor,'left');assert.equal(rows[0].number,1);assert.equal(rows[0].active,true);
 assert.equal(rows.filter(row=>row.migrated).length,1);
 assert.equal(rows.find(row=>row.migrated).monitor,'right');
 assert.equal(rows.find(row=>row.migrated).workspace_id,2);
 assert.equal(M.activeWorkspace(s,'DP-2'),null);
});
const entries=[{id:'org.kde.dolphin',name:'Файлы',icon:'system-file-manager',startupClass:'dolphin'},{id:'code',name:'Code',icon:'code',startupClass:'Code'}];
const windows=[{address:'0x1',appId:'dolphin',monitor:'DP-1',workspace_id:1,focusHistoryID:4},{address:'0x2',appId:'dolphin',monitor:'DP-1',workspace_id:3,focusHistoryID:0},{address:'0x3',appId:'dolphin',monitor:'DP-2',workspace_id:2,focusHistoryID:0}];
test('dock groups local windows and focuses most recent even on another workspace',()=>{
 const groups=plain(M.groupApps(windows,'DP-1',['org.kde.dolphin','code'],entries,ru));
 assert.equal(groups.length,2);assert.equal(groups[0].windows.length,2);assert.equal(groups[0].lastWindow.address,'0x2');
 assert.equal(groups[1].running,false);assert.equal(groups[1].name,'Code');
});
test('a foreign-monitor application is not treated as running locally',()=>{
 const groups=plain(M.groupApps(windows,'DP-3',['org.kde.dolphin','missing'],entries,ru));
 assert.equal(groups.length,1);
 assert.equal(groups[0].running,false);assert.equal(groups[0].lastWindow,null);
});
test('missing pinned app is hidden but running one stays',()=>{
 const none=[{id:'other',name:'Other',icon:'x'}];
 assert.deepEqual(plain(M.groupApps([],'DP-1',['org.kde.dolphin'],none,ru)),[]);
 const running=plain(M.groupApps([{address:'0x9',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:1}],'DP-1',['org.kde.dolphin'],none,ru));
 assert.equal(running.length,1);assert.equal(running[0].id,'org.kde.dolphin');assert.equal(running[0].pinned,true);
 assert.equal(running[0].running,true);assert.equal('available' in running[0],false);
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
 const keys=M.workspaceItems(s,'DP-1',ru).map(M.workspaceKey);
 assert.equal(new Set(keys).size,keys.length);
 assert.deepEqual(plain(keys.slice(0,4)),['left:1','left:2','left:3','right:2']);
 const renamed={...s,revision:10};
 assert.deepEqual(plain(M.workspaceItems(renamed,'DP-1',ru).map(M.workspaceKey)),plain(keys));
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
 assert.equal(M.layoutCode({active_keymap:'Russian (phonetic)',layout:'us,ru'},names,ru),'RU');
 assert.equal(M.layoutCode({active_keymap:'English (US)',layout:'us,ru'},names,ru),'US');
});
test('unknown keymap falls back to the active layout index, then to a placeholder',()=>{
 assert.equal(M.layoutCode({active_keymap:'Custom',layout:'us, de',active_layout_index:1},{},ru),'DE');
 assert.equal(M.layoutCode({active_keymap:'Custom',layout:'fr'},{},ru),'FR');
 assert.equal(M.layoutCode({active_keymap:'Custom',layout:'us,ru'},{},ru),'…');
 assert.equal(M.layoutCode(null,{},ru),'…');
});
const dockWindows=[
 {address:'0xa',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:1,activated:true,focusHistoryID:0},
 {address:'0xb',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:2,activated:false,focusHistoryID:2},
 {address:'0xc',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:1,activated:false,focusHistoryID:1},
 {address:'0xd',appId:'org.kde.dolphin',monitor:'DP-1',workspace_id:-98,activated:false,focusHistoryID:3},
];
const dockEntries=[{id:'org.kde.dolphin',name:'Dolphin',icon:'system-file-manager'}];
test('special workspaces are not shown as running applications in the dock',()=>{
 const group=plain(M.groupApps(dockWindows,'DP-1',[],dockEntries,ru))[0];
 assert.deepEqual(group.windows.map(w=>w.address),['0xa','0xc','0xb']);
});
test('clicking an active application moves to its next recent window',()=>{
 const group=plain(M.groupApps(dockWindows,'DP-1',[],dockEntries,ru))[0];
 assert.equal(M.clickTarget(group).address,'0xc');
 const inactive={...group,active:false,windows:group.windows.map(w=>({...w,activated:false}))};
 assert.equal(M.clickTarget(inactive).address,'0xa');
 assert.equal(M.clickTarget({windows:[]}),null);
});
test('wheel cycles the application windows in both directions',()=>{
 const group=plain(M.groupApps(dockWindows,'DP-1',[],dockEntries,ru))[0];
 assert.equal(M.cycleTarget(group,1).address,'0xc');
 assert.equal(M.cycleTarget(group,-1).address,'0xb');
 assert.equal(M.cycleTarget({windows:[]},1),null);
});
test('device label never claims a connection without one',()=>{
 assert.equal(M.deviceLabel({type:'ethernet',state:'connected',cable:true,addresses:[]},ru),'Подключение…');
 assert.equal(M.deviceLabel({type:'ethernet',state:'unavailable',cable:false,addresses:[]},ru),'Нет кабеля');
 assert.equal(M.deviceLabel({type:'ethernet',state:'connected',cable:false,addresses:['10.42.0.5/24']},ru),'Нет кабеля');
 assert.equal(M.deviceLabel({type:'ethernet',state:'connected',cable:true,addresses:['10.42.0.5/24']},ru),'Подключено');
 assert.equal(M.deviceLabel({type:'wifi',state:'connecting',cable:null,addresses:[]},ru),'Подключение…');
 assert.equal(M.deviceLabel({type:'wifi',state:'disconnected',cable:null,addresses:[]},ru),'Отключено');
 assert.equal(M.deviceLabel({type:'wifi',state:'unavailable',cable:null,addresses:[]},ru),'Недоступно');
});
test('countdown rounds up and stops at zero',()=>{
 assert.equal(M.secondsLeft(30000,0),30);
 assert.equal(M.secondsLeft(30000,29001),1);
 assert.equal(M.secondsLeft(30000,31000),0);
});
test('pendingCheckpoint survives shell restart',()=>{
 const status={pendingCheckpoints:['/org/freedesktop/NetworkManager/Checkpoint/3']};
 assert.deepEqual(plain(M.pendingFromStatus(status,null)),{checkpoint:'/org/freedesktop/NetworkManager/Checkpoint/3',deadline:null});
 const own={checkpoint:'/org/freedesktop/NetworkManager/Checkpoint/3',deadline:5000};
 assert.deepEqual(plain(M.pendingFromStatus(status,own)),own);
 assert.equal(M.pendingFromStatus({pendingCheckpoints:[]},own),null);
});
test('network errors are Russian with the helper detail',()=>{
 assert.equal(M.networkErrorText('save',{error:"address needs a network prefix, for example 10.42.0.5/24: '10.42.0.5'",field:'prefix'},ru),'Укажите префикс сети, например 10.42.0.5/24');
 assert.equal(M.networkErrorText('save',{error:'invalid DNS server address',field:'dns'},ru),'Некорректный адрес DNS');
 assert.equal(M.networkErrorText('apply',{error:'network adapter enx0 not found'},ru),'Конфигурация не применена: network adapter enx0 not found');
 assert.equal(M.networkErrorText('apply',{error:'x',field:'unknown'},ru),'Конфигурация не применена: x');
 assert.equal(M.networkErrorText('',{},ru),'Сетевое действие не выполнено');
});
test('brightness parse yields null without backlight',()=>{
 assert.equal(M.parseBrightness(''),null);
 assert.equal(M.parseBrightness('input3::capslock,leds,0,0%,1\n'),null);
 assert.deepEqual(plain(M.parseBrightness('intel_backlight,backlight,48000,50%,96000\n')),{device:'intel_backlight',percent:50});
});
test('brightness writes never carry an empty request',()=>{
 assert.deepEqual(plain(M.brightnessArgs('intel_backlight',40)),['brightnessctl','-c','backlight','-d','intel_backlight','set','40%']);
 assert.deepEqual(plain(M.brightnessArgs('intel_backlight',140)),['brightnessctl','-c','backlight','-d','intel_backlight','set','100%']);
 assert.equal(M.brightnessArgs('intel_backlight',-1),null);
 assert.equal(M.brightnessArgs('',40),null);
});
test('only built-in outputs get the backlight slider',()=>{
 for(const name of ['eDP-1','LVDS-1','DSI-1']) assert.equal(M.isBuiltinOutput(name),true,name);
 for(const name of ['HDMI-A-1','DP-2','']) assert.equal(M.isBuiltinOutput(name),false,name);
});
test('volume is clamped to the safe range',()=>{
 assert.equal(M.clampVolume(2),1.5);
 assert.equal(M.clampVolume(-1),0);
 assert.equal(M.clampVolume(0.42),0.42);
});
test('battery time reads in hours and minutes',()=>{
 assert.equal(M.formatDuration(4800,ru),'1 ч 20 мин');
 assert.equal(M.formatDuration(600,ru),'10 мин');
 assert.equal(M.formatDuration(30,ru),'1 мин');
});
test('binds are described in Russian with modifier names',()=>{
 const rows=plain(M.describeBinds([
  {modmask:64,key:'M',dispatcher:'exec',arg:'quietline-engine toggle'},
  {modmask:65,key:'1',dispatcher:'exec',arg:'quietline-engine move 1'},
  {modmask:64,key:'0',dispatcher:'exec',arg:'quietline-engine switch 10'},
  {modmask:64,key:'I',dispatcher:'exec',arg:"qs -c quietline ipc call quietline settings ''"},
  {modmask:12,key:'T',dispatcher:'exec',arg:'my-tool --flag'},
  {modmask:64,key:'L',dispatcher:'exec',arg:'quietline-shell lock'},
 ],ru));
 assert.deepEqual(rows[5],{keys:'Super+L',action:'Заблокировать сеанс'});
 assert.equal(M.bindAction('qs -c quietline ipc call quietline settings shortcuts',ru),'Памятка сочетаний клавиш');
 assert.equal(M.bindAction('dolphin',ru),'Открыть Dolphin');
 assert.deepEqual(rows[0],{keys:'Super+M',action:'Сменить режим «Окна / Тайлы»'});
 assert.deepEqual(rows[1],{keys:'Super+Shift+1',action:'Перенести окно на пространство 1'});
 assert.deepEqual(rows[2],{keys:'Super+0',action:'Открыть пространство 10'});
 assert.deepEqual(rows[3],{keys:'Super+I',action:'Открыть окно «Настройки»'});
 assert.deepEqual(rows[4],{keys:'Ctrl+Alt+T',action:'my-tool --flag'});
 assert.deepEqual(plain(M.describeBinds(null,ru)),[]);
});
test('binds to missing applications are not listed',()=>{
 const binds=[{modmask:64,key:'E',dispatcher:'exec',arg:'dolphin'},{modmask:64,key:'Return',dispatcher:'exec',arg:'ghostty'},{modmask:64,key:'M',dispatcher:'exec',arg:'quietline-engine toggle'}];
 const none=[{id:'other',name:'Other',icon:'x'}];
 assert.deepEqual(plain(M.describeBinds(binds,en,none)).map(r=>r.keys),['Super+M']);
 const rows=plain(M.describeBinds(binds,en,[{id:'org.kde.dolphin',name:'Dolphin',icon:'x'}]));
 assert.deepEqual(rows.map(r=>r.keys),['Super+E','Super+M']);
 assert.equal(rows[0].action,'Open Dolphin');
 const both=plain(M.describeBinds(binds,en,[{id:'com.mitchellh.ghostty',name:'Ghostty',icon:'x'},{id:'org.kde.dolphin',name:'Dolphin',icon:'x'}]));
 assert.equal(both.length,3);
});
test('wifi signal maps to bars',()=>{
 assert.deepEqual([100,75,74,50,49,25,24,0].map(M.wifiSymbol),
  ['signal_wifi_4_bar','signal_wifi_4_bar','network_wifi_3_bar','network_wifi_3_bar','network_wifi_2_bar','network_wifi_2_bar','network_wifi_1_bar','network_wifi_1_bar']);
});
test('lua binds are described by their description',()=>{
 const lua=(modmask,key,dispatcher,description)=>({modmask,key,dispatcher:`HL.Dispatcher(${dispatcher})`,arg:'17',description,has_description:!!description});
 const rows=plain(M.describeBinds([
  lua(64,'Return','exec_cmd','ghostty'),
  lua(64,'W','close','quietline:close'),
  lua(65,'Left','function','quietline:move-left'),
  lua(64,'mouse:272','drag','quietline:drag'),
  ...[1,2,3,4,5,6,7,8,9,10].map(n=>lua(64,String(n%10),'exec_cmd',`quietline-engine switch ${n}`)),
  ...[1,2,3,4,5,6,7,8,9,10].map(n=>lua(65,String(n%10),'exec_cmd',`quietline-engine move ${n}`)),
  lua(64,'M','exec_cmd','quietline-engine toggle'),
  lua(64,'K','exec_cmd',''),
  lua(64,'J','exec_cmd','quietline:unknown'),
 ],ru,[{id:'com.mitchellh.ghostty',name:'Ghostty',icon:'x'}]));
 assert.deepEqual(rows,[
  {keys:'Super+Enter',action:'Открыть терминал'},
  {keys:'Super+W',action:'Закрыть окно'},
  {keys:'Super+Shift+←',action:'Сдвинуть окно влево'},
  {keys:'Super+Левая кнопка мыши',action:'Перетащить окно'},
  {keys:'Super+1…0',action:'Открыть пространство 1–10'},
  {keys:'Super+Shift+1…0',action:'Перенести окно на пространство 1–10'},
  {keys:'Super+M',action:'Сменить режим «Окна / Тайлы»'},
  {keys:'Super+K',action:'Запустить команду'},
  {keys:'Super+J',action:'quietline:unknown'},
 ]);
 assert.equal(M.bindAction('quietline:float',en),'Take window out of its column or put it back');
 const gaps=plain(M.describeBinds([
  lua(64,'1','exec_cmd','quietline-engine switch 1'),lua(64,'2','exec_cmd','quietline-engine switch 2'),
  lua(64,'5','exec_cmd','quietline-engine switch 5'),lua(64,'W','close','quietline:close'),
  lua(64,'6','exec_cmd','quietline-engine switch 6'),
 ],ru)).map(r=>r.keys);
 assert.deepEqual(gaps,['Super+1…2','Super+5','Super+W','Super+6']);
});
test('session menu names the applications that did not quit',()=>{
 assert.equal(M.remainingText([{app:'code',title:'notes.md'},{app:'code',title:'todo.md'},{app:'Telegram',title:'Telegram'}],ru),
  'Не завершились: code (2), Telegram. Сохраните документы и повторите.');
 const entries=[{id:'com.mitchellh.ghostty',name:'Ghostty',startupClass:''},{id:'brave-browser',name:'Brave',startupClass:''}];
 assert.equal(M.remainingText([{app:'brave-browser',title:'Quietline'},{app:'com.mitchellh.ghostty',title:'a'},{app:'com.mitchellh.ghostty',title:'b'}],ru,entries),
  'Не завершились: Brave, Ghostty (2). Сохраните документы и повторите.');
 assert.equal(M.remainingText([],ru),'');
 assert.equal(M.remainingText([{app:'',title:''}],ru),'Не завершились: окно без названия. Сохраните документы и повторите.');
 assert.equal(M.sessionErrorText('poweroff','systemctl failed',ru),'Выключить не удалось: systemctl failed');
 assert.equal(M.sessionErrorText('x','',ru),'Действие сеанса не удалось');
 for(const action of M.SESSION_ACTIONS){ assert.ok(M.sessionLabel(action,ru)); assert.ok(M.sessionQuestion(action,ru)); assert.ok(M.sessionLabel(action,en)); }
 assert.equal(M.sessionLabel('poweroff',ru),'Выключить');
 assert.equal(M.sessionLabel('x',ru),'');
});
test('applications start in their own quietline scope',()=>{
 assert.equal(M.scopeUnit('org.kde.dolphin','a1b2c3'),'app-quietline-org.kde.dolphin-a1b2c3');
 assert.equal(M.scopeUnit('my app/../x','z!9'),'app-quietline-my_app_.._x-z9');
 assert.equal(M.scopeUnit('','1'),'app-quietline-app-1');
 assert.deepEqual(plain(M.launchCommand(['code','--new-window'],'app-quietline-code-1')),
  ['systemd-run','--user','--scope','--collect','--quiet','--unit=app-quietline-code-1','--','code','--new-window']);
 assert.equal(M.launchCommand([], 'u'),null);
});
test('notifications never cover the screen for long',()=>{
 assert.equal(M.notificationTimeout(-1,1),6000);
 assert.equal(M.notificationTimeout(0,1),6000);
 assert.equal(M.notificationTimeout(2.5,0),2500);
 assert.equal(M.notificationTimeout(60,1),6000);
 assert.equal(M.notificationTimeout(60,2),0);
});
test('clipboard search matches text and images',()=>{
 const entries=[{id:'3',kind:'text',preview:'Привет, мир'},{id:'2',kind:'image',preview:'[[ binary data 14 KiB png 120x80 ]]'},{id:'1',kind:'text',preview:'ssh host'}];
 assert.deepEqual(plain(M.clipboardMatches(entries,'',ru)).map(e=>e.id),['3','2','1']);
 assert.deepEqual(plain(M.clipboardMatches(entries,'МИР',ru)).map(e=>e.id),['3']);
 assert.deepEqual(plain(M.clipboardMatches(entries,'изобр',ru)).map(e=>e.id),['2']);
 assert.equal(M.clipboardImageLabel('[[ binary data 14 KiB png 120x80 ]]',ru),'Изображение PNG · 120×80');
 assert.equal(M.clipboardImageLabel('junk',ru),'Изображение');
});
test('search calculator is arithmetic only',()=>{
 assert.equal(M.calculate('(1+2)*3'),9);
 assert.equal(M.calculate('-2^2'),-4);
 assert.equal(M.calculate('2^3^2'),512);
 assert.equal(M.calculate('10 % 3'),1);
 assert.equal(M.calculate('1,5*2'),3);
 assert.equal(M.formatNumber(M.calculate('0.1+0.2')),'0.3');
 for(const text of ['constructor','1;alert(1)','2**1000','1/0','2^100000','(1+2','1 2','42','','1..2+1','this.x+1','__proto__+1','1e3+1'])
  assert.equal(M.calculate(text),null,text);
 assert.equal(M.calculate('1+'.repeat(60)+'1'),null);
});
test('search ranks apps, actions, settings and files',()=>{
 const apps=[{id:'org.kde.dolphin',name:'Dolphin'},{id:'code',name:'Visual Studio Code'},{id:'org.telegram.desktop',name:'Telegram'}];
 assert.deepEqual(plain(M.searchResults('',apps,[],'/home/k',undefined,ru)).map(r=>r.title),['Dolphin','Visual Studio Code','Telegram']);
 const code=plain(M.searchResults('code',apps,['/home/k/src/code.txt'],'/home/k',undefined,ru));
 assert.equal(code[0].title,'Visual Studio Code');
 assert.deepEqual(code[code.length-1],{kind:'file',id:'/home/k/src/code.txt',title:'code.txt',subtitle:'~/src',path:'/home/k/src/code.txt'});
 const lock=plain(M.searchResults('блок',apps,[],'/home/k',undefined,ru));
 assert.equal(lock[0].kind,'action'); assert.equal(lock[0].id,'lock');
 const wifi=plain(M.searchResults('wi-fi',apps,[],'/home/k',undefined,ru));
 assert.equal(wifi[0].kind,'settings'); assert.equal(wifi[0].id,'network');
 const calc=plain(M.searchResults('2+2',apps,[],'/home/k',undefined,ru));
 assert.deepEqual(calc[0],{kind:'calc',id:'calc',title:'= 4',value:'4',subtitle:'Enter — скопировать результат'});
 assert.equal(M.searchResults('a',apps.concat(Array.from({length:60},(_,i)=>({id:'a'+i,name:'App '+i}))),[],'',10,ru).length,10);
});
test('texts follow the English table',()=>{
 assert.equal(M.errorText({code:'invalid_number',message:'x'},en),'No such workspace: numbers 1 to 10');
 assert.equal(M.errorText({code:'unknown_method',message:"unknown method 'x'"},en),"The window service does not know this command: unknown method 'x'");
 assert.equal(M.errorText({},en),'Command failed');
 assert.equal(M.bindAction('quietline-engine toggle',en),'Switch “Windows / Tiles” mode');
 assert.equal(M.bindAction('quietline-engine move 3',en),'Move window to workspace 3');
 assert.equal(M.bindAction('my-tool --flag',en),'my-tool --flag');
 assert.equal(M.remainingText([{app:'code',title:'notes.md'},{app:'',title:''}],en),
  'Still running: code, untitled window. Save your documents and try again.');
 for(const query of ['сеть','network']){
  const rows=plain(M.searchResults(query,[],[],'/home/k',undefined,en));
  assert.equal(rows[0].kind,'settings',query); assert.equal(rows[0].id,'network',query);
  assert.equal(rows[0].title,'Network',query); assert.equal(rows[0].subtitle,'Settings',query);
 }
 const network=plain(M.searchResults('network',[],[],'/home/k',undefined,ru));
 assert.equal(network[0].id,'network'); assert.equal(network[0].title,'Сеть');
});

test('settings: region replaces keyboard and keyboard is an alias',()=>{
 assert.equal(M.SETTINGS_SECTIONS.some(item=>item.id==='keyboard'),false);
 assert.equal(M.SETTINGS_SECTIONS.some(item=>item.id==='region'),true);
 assert.equal(M.resolveSection('keyboard'),'region');
 assert.equal(M.resolveSection('region'),'region');
 assert.equal(M.resolveSection('network'),'network');
 assert.equal(M.resolveSection('constructor'),'constructor');
 for(const [query,table] of [['раскладка',ru],['keyboard',en],['язык',en],['language',ru]]){
  const rows=plain(M.searchResults(query,[],[],'/home/k',undefined,table));
  assert.ok(rows.some(row=>row.kind==='settings'&&row.id==='region'),query);
 }
 assert.equal(ru[M.SETTINGS_SECTIONS.find(item=>item.id==='region').label],'Язык и регион');
 assert.equal(en[M.SETTINGS_SECTIONS.find(item=>item.id==='region').label],'Language and region');
});
test('search actions are found by a word of either language',()=>{
 for(const [query,id] of [['заблокировать','lock'],['выйти','logout'],['перезагрузить','reboot'],['выключить','poweroff'],['о системе','about']]){
  for(const table of [ru,en]){
   const rows=plain(M.searchResults(query,[],[],'/home/k',undefined,table));
   assert.ok(rows.some(row=>row.id===id),`${query} ${id}`);
  }
 }
 for(const [query,id] of [['lock','lock'],['log out','logout'],['restart','reboot'],['shut down','poweroff'],['about','about']]){
  const rows=plain(M.searchResults(query,[],[],'/home/k',undefined,ru));
  assert.ok(rows.some(row=>row.id===id),`${query} ${id}`);
 }
});
test('toggle labels follow the chosen shortcut',()=>{
 assert.equal(M.toggleLabel('grp:lalt_lshift_toggle',ru),'Левые Alt+Shift');
 assert.equal(M.toggleLabel('grp:lalt_lshift_toggle',en),'Left Alt+Shift');
 assert.equal(M.toggleLabel('grp:alt_shift_toggle',en),'Alt+Shift');
 assert.equal(M.toggleLabel('grp:ctrl_shift_toggle',ru),'Ctrl+Shift');
 assert.equal(M.toggleLabel('grp:caps_toggle',en),'Caps Lock');
 assert.equal(M.toggleLabel('unknown',en),'unknown');
 assert.equal(M.toggleLabel('constructor',en),'constructor');
 assert.equal(en.barLayoutHint.replace('{0}','Caps Lock'),'Switch layout · Caps Lock');
 assert.match(ru.keyboardToggleNote,/\{0\}/);
});
test('indicator shows volume, brightness and layout values',()=>{
 assert.deepEqual(plain(M.osdView('volume',1.2,false)).fill,1);
 assert.equal(M.osdView('volume',1.2,false).text,'120%');
 const muted=M.osdView('volume',0.35,true), loud=M.osdView('volume',0.35,false);
 assert.equal(muted.fill,0.35);
 assert.notEqual(muted.icon,loud.icon);
 assert.notEqual(M.osdView('mic',0.5,true).icon,M.osdView('mic',0.5,false).icon);
 assert.equal(M.osdView('brightness',0.05,false).text,'5%');
 assert.deepEqual(plain(M.osdView('layout','RU',false)),{icon:M.osdView('layout','EN',false).icon,fill:-1,text:'RU'});
 assert.equal(M.osdView('volume',-0.2,false).fill,0);
});
test('indicator skips changes made by the shell itself',()=>{
 assert.equal(M.OSD_HIDE_MS,1500);
 assert.equal(M.OSD_LOCAL_MS,600);
 assert.equal(M.osdSuppressed(1600,1000),true);
 assert.equal(M.osdSuppressed(1600,1600),false);
 assert.equal(M.osdSuppressed(0,1000),false);
});
test('volume and brightness keys are described in the shortcuts list',()=>{
 const rows=plain(M.describeBinds([
  {modmask:0,key:'XF86AudioRaiseVolume',dispatcher:'exec',arg:'wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+'},
  {modmask:0,key:'XF86AudioLowerVolume',dispatcher:'exec',arg:'wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-'},
  {modmask:0,key:'XF86AudioMute',dispatcher:'exec',arg:'wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle'},
  {modmask:0,key:'XF86AudioMicMute',dispatcher:'exec',arg:'wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle'},
  {modmask:0,key:'XF86MonBrightnessUp',dispatcher:'exec',arg:'brightnessctl -c backlight --min-value=1 set 5%+ && qs -c quietline ipc call quietline osd brightness'},
  {modmask:0,key:'XF86MonBrightnessDown',dispatcher:'exec',arg:'brightnessctl -c backlight --min-value=1 set 5%- && qs -c quietline ipc call quietline osd brightness'},
 ],ru));
 assert.deepEqual(rows.map(r=>r.action),['Громче','Тише','Выключить или включить звук','Выключить или включить микрофон','Ярче','Темнее']);
 assert.deepEqual(rows.map(r=>r.keys),['Громкость +','Громкость −','Звук','Микрофон','Яркость +','Яркость −']);
 assert.equal(plain(M.describeBinds([{modmask:0,key:'XF86AudioMute',arg:'wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle'}],en))[0].keys,'Mute');
});
test('battery warnings fire once per threshold crossed while discharging',()=>{
 assert.deepEqual(plain(M.BATTERY_LEVELS),[20,10,5]);
 assert.equal(M.BATTERY_CRITICAL,5);
 assert.equal(M.batteryWarning(null,20,true),20);
 assert.equal(M.batteryWarning(20,19,true),null);
 assert.equal(M.batteryWarning(20,9,true),10);
 assert.equal(M.batteryWarning(null,8,true),10);
 assert.equal(M.batteryWarning(10,4,true),5);
 assert.equal(M.batteryWarning(null,15,false),null);
 assert.equal(M.batteryWarning(null,50,true),null);
 assert.equal(M.batteryWarning(null,0,true),null);
});
test('battery level bouncing around a threshold warns only once until charging',()=>{
 let warned=null; const fired=[];
 for(const percent of [21,20,21,20]){
  const level=M.batteryWarning(warned,percent,true);
  if(level!==null){warned=level;fired.push(level);}
 }
 assert.deepEqual(fired,[20]);
 assert.equal(M.batteryWarning(warned,25,false),null);
 warned=null;
 assert.equal(M.batteryWarning(warned,20,true),20);
});
test('do not disturb lets only critical cards through, the open centre none',()=>{
 assert.equal(M.popupAllowed(2,true,false),true);
 assert.equal(M.popupAllowed(1,true,false),false);
 assert.equal(M.popupAllowed(2,false,true),false);
 assert.equal(M.popupAllowed(1,false,false),true);
 assert.equal(M.popupAllowed(0,false,false),true);
});
test('notification age is now, minutes, today or earlier',()=>{
 const at=(d,h,m,s=0)=>new Date(2026,9,d,h,m,s).getTime();
 assert.deepEqual(plain(M.notificationAge(at(30,12,0,0),at(30,12,0,30))),{kind:'now',minutes:0});
 assert.deepEqual(plain(M.notificationAge(at(30,12,0),at(30,12,5))),{kind:'minutes',minutes:5});
 assert.deepEqual(plain(M.notificationAge(at(29,23,50),at(30,0,20))),{kind:'minutes',minutes:30});
 assert.equal(M.notificationAge(at(30,9,0),at(30,12,0)).kind,'today');
 assert.equal(M.notificationAge(at(29,22,0),at(30,1,0)).kind,'earlier');
});
test('history keeps at most a hundred notifications',()=>{
 assert.equal(M.NOTIFICATION_HISTORY_LIMIT,100);
 assert.equal(M.notificationsToDrop(100),0);
 assert.equal(M.notificationsToDrop(101),1);
 assert.equal(M.notificationsToDrop(0),0);
 assert.equal(M.bindAction('qs -c quietline ipc call quietline notifications',ru),'Уведомления');
});
test('a transient notification without a visible card is expired at once',()=>{
 assert.equal(M.transientExpires(true,false),true);
 assert.equal(M.transientExpires(true,true),false);
 assert.equal(M.transientExpires(false,false),false);
});
test('bar shows only existing workspaces: busy, current and migrated',()=>{
 const items=[{number:1,workspace_id:1,active:false,migrated:false},{number:2,workspace_id:null,active:false,migrated:false},
  {number:3,workspace_id:7,active:true,migrated:false},{number:4,workspace_id:null,active:false,migrated:false},
  {number:2,workspace_id:9,active:false,migrated:true}];
 assert.deepEqual(plain(M.barWorkspaces(items)).map(item=>item.number),[1,3,2]);
 assert.deepEqual(plain(M.barWorkspaces([])),[]);
 assert.deepEqual(plain(M.barWorkspaces([{number:1,workspace_id:null,active:true,migrated:false}])).length,1);
});
test('bar names the active application of its monitor by desktop entry',()=>{
 const entries=[{id:'com.mitchellh.ghostty',name:'Ghostty',startupClass:''},{id:'org.telegram.desktop',name:'Telegram',startupClass:'TelegramDesktop'}];
 const windows=[{monitor:'eDP-1',activated:false,appId:'org.telegram.desktop',className:'org.telegram.desktop',title:'Telegram'},
  {monitor:'eDP-1',activated:true,appId:'com.mitchellh.ghostty',className:'com.mitchellh.ghostty',title:'~'},
  {monitor:'DP-1',activated:true,appId:'TelegramDesktop',className:'TelegramDesktop',title:'Chat'}];
 assert.equal(M.activeAppName(windows,'eDP-1',entries),'Ghostty');
 assert.equal(M.activeAppName(windows,'DP-1',entries),'Telegram');
 assert.equal(M.activeAppName(windows,'HDMI-A-1',entries),'');
 assert.equal(M.activeAppName([{monitor:'eDP-1',activated:true,appId:'',className:'',title:'Untitled'}],'eDP-1',entries),'Untitled');
 assert.equal(M.activeAppName([{monitor:'eDP-1',activated:true,appId:'org.quickshell',className:'org.quickshell',title:'Settings'}],'eDP-1',entries),'Settings');
});
test('minimized windows stay in the dock with a hollow mark',()=>{
 const entries=[{id:'com.mitchellh.ghostty',name:'Ghostty',startupClass:''}];
 const windows=[{address:'0x1',appId:'com.mitchellh.ghostty',monitor:'eDP-1',workspace_id:-1,minimized:true,focusHistoryID:2},
  {address:'0x2',appId:'scratch',monitor:'eDP-1',workspace_id:-1,minimized:false}];
 const groups=plain(M.groupApps(windows,'eDP-1',[],entries,ru));
 assert.deepEqual(groups.map(group=>group.id),['com.mitchellh.ghostty']);
 assert.equal(groups[0].running,true);
 assert.equal(groups[0].minimized,true);
 const mixed=plain(M.groupApps([...windows,{address:'0x3',appId:'com.mitchellh.ghostty',monitor:'eDP-1',workspace_id:1,focusHistoryID:0}],'eDP-1',[],entries,ru));
 assert.equal(mixed[0].minimized,false);
 assert.equal(M.MINIMIZED_WORKSPACE,'special:quietline-minimized');
});
test('dock shows itself only in windows mode and when wanted',()=>{
 assert.equal(M.dockRevealed({available:false,hovered:true,empty:true}),false);
 assert.equal(M.dockRevealed({available:true}),false);
 for(const key of ['hovered','menuOpen','dragging','keyboard','empty'])
  assert.equal(M.dockRevealed({available:true,[key]:true}),true,key);
});
test('a workspace without shown windows counts as empty',()=>{
 const windows=[{monitor:'eDP-1',workspace_id:1,hidden:false,mapped:true},{monitor:'eDP-1',workspace_id:2,hidden:true,mapped:true},
  {monitor:'DP-1',workspace_id:3,hidden:false,mapped:true}];
 assert.equal(M.workspaceEmpty(windows,'eDP-1',1),false);
 assert.equal(M.workspaceEmpty(windows,'eDP-1',2),true);
 assert.equal(M.workspaceEmpty(windows,'eDP-1',3),true);
 assert.equal(M.workspaceEmpty([],'eDP-1',1),true);
});
test('search results are grouped into sections with a top hit',()=>{
 const results=[{kind:'app',id:'tg',title:'Telegram'},{kind:'file',id:'/h/t.txt',title:'t.txt'},{kind:'settings',id:'region',title:'Region'},
  {kind:'app',id:'code',title:'Code'},{kind:'action',id:'lock',title:'Lock'}];
 const rows=plain(M.searchSections(results,'te',ru));
 assert.deepEqual(rows.map(r=>r.header?'#'+r.title:r.index),['#'+ru.searchBest,0,'#'+ru.searchApps,3,'#'+ru.searchActions,2,4,'#'+ru.searchFiles,1]);
 const calc=plain(M.searchSections([{kind:'calc',id:'calc',title:'= 4'},{kind:'app',id:'a',title:'A'}],'2+2',en));
 assert.deepEqual(calc.map(r=>r.header?'#'+r.title:r.index),['#'+en.searchBest,0,'#'+en.searchApps,1]);
 const empty=plain(M.searchSections([{kind:'app',id:'a',title:'A'},{kind:'app',id:'b',title:'B'}],'',ru));
 assert.deepEqual(empty.map(r=>r.header?'#'+r.title:r.index),['#'+ru.searchApps,0,1]);
 assert.deepEqual(plain(M.searchSections([],'x',ru)),[]);
});
test('search rows get a symbol by kind',()=>{
 assert.equal(M.searchSymbol({kind:'calc'}),'calculate');
 assert.equal(M.searchSymbol({kind:'action',id:'lock'}),'lock');
 assert.equal(M.searchSymbol({kind:'file',title:'photo.JPG'}),'image');
 assert.equal(M.searchSymbol({kind:'file',title:'notes.md'}),'description');
 assert.equal(M.searchSymbol({kind:'settings',id:'network'}),'settings');
});
test('clipboard entries are shown as text, link or image',()=>{
 assert.equal(M.clipboardKind({kind:'image',preview:'x'}),'image');
 assert.equal(M.clipboardKind({kind:'text',preview:' https://quickshell.org/docs '}),'link');
 assert.equal(M.clipboardKind({kind:'text',preview:'see https://a.b and more'}),'text');
 assert.equal(M.clipboardSymbol({kind:'text',preview:'file:///home/k/a.txt'}),'link');
 assert.equal(M.clipboardKindLabel({kind:'text',preview:'hello'},ru),ru.clipboardText);
 assert.equal(M.clipboardKindLabel(null,en),en.clipboardText);
});
test('notification history is stacked by application in recency order',()=>{
 const history=[{app:'tg',id:1},{app:'vpn',id:2},{app:'tg',id:3},{app:'ql',id:4}];
 const groups=plain(M.notificationGroups(history,entry=>entry.app));
 assert.deepEqual(groups.map(g=>[g.key,g.entries.map(e=>e.id)]),[['tg',[1,3]],['vpn',[2]],['ql',[4]]]);
 assert.deepEqual(plain(M.notificationGroups([],e=>e.app)),[]);
});
test('month grid starts the week on the locale day and marks today',()=>{
 // Ноябрь 2026: 1-е — воскресенье.
 const monday=plain(M.monthGrid(2026,10,1,{year:2026,month:10,day:1}));
 assert.equal(monday.length,42);
 assert.deepEqual(monday.slice(0,7).map(c=>c.day),[26,27,28,29,30,31,1]);
 assert.deepEqual(monday.slice(0,7).map(c=>c.current),[false,false,false,false,false,false,true]);
 assert.equal(monday.filter(c=>c.today).length,1);
 assert.equal(monday[6].today,true);
 const sunday=plain(M.monthGrid(2026,10,0,null));
 assert.equal(sunday[0].day,1);
 assert.equal(sunday[0].current,true);
 assert.equal(sunday.filter(c=>c.today).length,0);
 assert.equal(sunday[41].current,false);
});
