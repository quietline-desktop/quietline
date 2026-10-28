// Тесты таблиц строк shell/quietline/logic/Strings.js без Quickshell.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../shell/quietline/logic/Strings.js'),'utf8').replace(/^\.pragma library\s*/, '');
function load(){ const S=vm.createContext({}); vm.runInContext(source,S); return S; }
const S=load();
const placeholders=text=>[...new Set(String(text).match(/\{\d+\}/g)||[])].sort();

test('both languages have the same keys and placeholders',()=>{
 const ru=Object.keys(S.STRINGS.ru).sort(), en=Object.keys(S.STRINGS.en).sort();
 assert.deepEqual(ru,en);
 for(const key of ru){
  assert.equal(typeof S.STRINGS.ru[key],'string',key);
  assert.equal(typeof S.STRINGS.en[key],'string',key);
  assert.deepEqual(placeholders(S.STRINGS.ru[key]),placeholders(S.STRINGS.en[key]),key);
 }
});
test('unknown language falls back to english',()=>{
 assert.equal(S.table('de').clockTitle,S.table('en').clockTitle);
 assert.equal(S.table('de').engineInvalidNumber,S.STRINGS.en.engineInvalidNumber);
 assert.equal(S.table('ru').engineInvalidNumber,S.STRINGS.ru.engineInvalidNumber);
 const copy=load();
 delete copy.STRINGS.ru.engineInvalidNumber;
 assert.equal(copy.table('ru').engineInvalidNumber,copy.STRINGS.en.engineInvalidNumber);
 assert.equal(S.localeName('ru'),'ru_RU');
 assert.equal(S.localeName('en'),'en_US');
 assert.equal(S.localeName('de'),'en_US');
});
test('formats match the spec',()=>{
 assert.equal(S.timeFormat('24h'),'HH:mm');
 assert.equal(S.timeFormat('12h'),'h:mm AP');
 assert.equal(S.dateFormat('dmy'),'dd.MM.yyyy');
 assert.equal(S.dateFormat('ymd'),'yyyy-MM-dd');
 assert.equal(S.dateFormat('mdy'),'MM/dd/yyyy');
});
test('format substitutes in order',()=>{
 assert.equal(S.format('{0} из {1}',[1,2]),'1 из 2');
 assert.equal(S.format('{1}-{0}-{1}',['a','b']),'b-a-b');
 assert.equal(S.format('{0} и {2}',['x']),'x и {2}');
});
// Строковый литерал ('…' или "…") с кириллицей вне комментария `//`.
function cyrillicLiterals(file){
 const found=[];
 fs.readFileSync(file,'utf8').split('\n').forEach((line,index)=>{
  let quote=null, i=0;
  while(i<line.length){
   const c=line[i];
   if(quote){
    if(c==='\\'){ i+=2; continue; }
    if(c===quote){ quote=null; }
    else if(/[Ѐ-ӿ]/.test(c)){ found.push(`${path.relative(root,file)}:${index+1}`); break; }
   } else if(c==='"'||c==="'"){ quote=c; }
   else if(c==='/'&&line[i+1]==='/'){ break; }
   i++;
  }
 });
 return found;
}
const root=path.join(__dirname,'../..');
function walk(dir){
 return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entry=>{
  const full=path.join(dir,entry.name);
  return entry.isDirectory()?walk(full):[full];
 });
}
test('qml and models have no cyrillic string literals',()=>{
 const base=path.join(root,'shell/quietline');
 const files=walk(base).filter(f=>f.endsWith('.qml')||f.endsWith('logic/Models.js'));
 const found=files.flatMap(cyrillicLiterals);
 assert.deepEqual(found,[]);
});
test('every Lang.s key used in QML exists in Strings',()=>{
 const base=path.join(root,'shell/quietline');
 const used=new Map();
 for(const file of walk(base).filter(f=>f.endsWith('.qml'))){
  for(const match of fs.readFileSync(file,'utf8').matchAll(/Lang\.s\.(\w+)/g)){
   if(!used.has(match[1])) used.set(match[1],path.relative(root,file));
  }
 }
 assert.ok(used.size>0);
 for(const language of ['en','ru']){
  const table=S.table(language);
  const missing=[...used].filter(([key])=>typeof table[key]!=='string').map(([key,file])=>`${key} (${file})`);
  assert.deepEqual(missing,[],language);
 }
});
