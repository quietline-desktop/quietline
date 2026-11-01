// Глифы значков оболочки: только из набора Font Awesome 4 в Nerd Fonts 3 (U+F000–U+F2E0).
// Значки Font Awesome 5 и новее (например, U+F6A9, U+F796) в шрифте отсутствуют и рисуются квадратом.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'../../shell/quietline');
const FIRST=0xf000, LAST=0xf2e0;

function files(dir){
 return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entry=>{
  const full=path.join(dir,entry.name);
  if(entry.isDirectory()) return files(full);
  return /\.(qml|js)$/.test(entry.name)?[full]:[];
 });
}
// Символы личной области Unicode: литералом в тексте и экранированием `\uXXXX`.
function glyphs(text){
 const found=[];
 for(const ch of text){
  const code=ch.codePointAt(0);
  if((code>=0xe000&&code<=0xf8ff)||code>=0xf0000) found.push(code);
 }
 for(const match of text.matchAll(/\\u([0-9a-fA-F]{4})/g)){
  const code=parseInt(match[1],16);
  if(code>=0xe000&&code<=0xf8ff) found.push(code);
 }
 return found;
}

test('icon glyphs come from the Font Awesome 4 range of Nerd Fonts',()=>{
 const wrong=[];
 for(const file of files(root)){
  for(const code of glyphs(fs.readFileSync(file,'utf8'))){
   if(code<FIRST||code>LAST) wrong.push(`${path.relative(root,file)}: U+${code.toString(16).toUpperCase()}`);
  }
 }
 assert.deepEqual(wrong,[]);
});
