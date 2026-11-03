// Тесты правил polkit config/polkit/50-quietline-network.rules и 50-quietline-time.rules с поддельным объектом polkit.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function loadRule(name='50-quietline-network.rules'){
 const source=fs.readFileSync(path.join(__dirname,'../../config/polkit',name),'utf8');
 const rules=[];
 const polkit={Result:{YES:'yes',NO:'no'},addRule:fn=>rules.push(fn)};
 vm.runInContext(source,vm.createContext({polkit}));
 assert.equal(rules.length,1);
 return (id,subject)=>rules[0]({id},subject);
}
const subject=(o={})=>({local:true,active:true,isInGroup:g=>g==='wheel',...o});
test('wheel user in an active local session may control networking and rollback',()=>{
 const rule=loadRule();
 for(const id of ['network-control','settings.modify.system','checkpoint-rollback','enable-disable-wifi'])
  assert.equal(rule('org.freedesktop.NetworkManager.'+id,subject()),'yes',id);
 assert.equal(rule('org.freedesktop.NetworkManager.checkpoint-rollback',subject({active:false})),undefined);
 assert.equal(rule('org.freedesktop.NetworkManager.checkpoint-rollback',subject({local:false})),undefined);
 assert.equal(rule('org.freedesktop.NetworkManager.checkpoint-rollback',subject({isInGroup:()=>false})),undefined);
 assert.equal(rule('org.freedesktop.login1.power-off',subject()),undefined);
});
test('wheel user in an active local session may set the time zone and network time',()=>{
 const rule=loadRule('50-quietline-time.rules');
 for(const id of ['set-timezone','set-ntp'])
  assert.equal(rule('org.freedesktop.timedate1.'+id,subject()),'yes',id);
 assert.equal(rule('org.freedesktop.timedate1.set-time',subject()),undefined);
 assert.equal(rule('org.freedesktop.timedate1.set-timezone',subject({active:false})),undefined);
 assert.equal(rule('org.freedesktop.timedate1.set-timezone',subject({local:false})),undefined);
 assert.equal(rule('org.freedesktop.timedate1.set-timezone',subject({isInGroup:()=>false})),undefined);
});
