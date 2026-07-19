document.documentElement.classList.add('js');
const stages = [...document.querySelectorAll('[data-stage]')];
let current = 0;
function get(data, path){return path.split('.').reduce((value,key)=>value && value[key], data) ?? '';}
function show(index){current = Math.max(0, Math.min(index, stages.length - 1));stages.forEach((stage,i)=>stage.classList.toggle('is-active', i === current));stages[current].querySelector('button,a')?.focus({preventScroll:true});stages[current].scrollIntoView({block:'start',behavior:'smooth'});}
function hydrate(data){document.querySelectorAll('[data-field]').forEach(el=>{el.textContent = get(data, el.dataset.field);});document.querySelectorAll('[data-code]').forEach(el=>{el.textContent = get(data, el.dataset.code);});}
fetch('showcase-data.json').then(r=>r.json()).then(hydrate).catch(()=>{});
document.addEventListener('click', event=>{if(event.target.matches('[data-next]')) show(current + 1);if(event.target.matches('[data-replay]')) show(0);});
stages.forEach((stage,i)=>stage.classList.toggle('is-active', i === 0));
