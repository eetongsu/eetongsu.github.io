document.documentElement.classList.add('js');
const search=document.getElementById('publication-search');
if(search){
  const topic=document.getElementById('publication-topic');
  const kind=document.getElementById('publication-kind');
  const rows=[...document.querySelectorAll('[data-publication]')];
  const count=document.getElementById('result-count');
  const empty=document.getElementById('empty-results');
  const filter=()=>{let n=0;const q=search.value.toLocaleLowerCase().trim();for(const row of rows){const ok=(!q||row.textContent.toLocaleLowerCase().includes(q))&&(!topic.value||row.dataset.topics.split('|').includes(topic.value))&&(!kind.value||row.dataset.kind===kind.value);row.hidden=!ok;if(ok)n++;}count.textContent=`${n} of ${rows.length} research records`;empty.hidden=n!==0;};
  search.addEventListener('input',filter);topic.addEventListener('change',filter);kind.addEventListener('change',filter);filter();
}
for(const button of document.querySelectorAll('[data-copy]'))button.addEventListener('click',async()=>{const text=document.getElementById(button.dataset.copy).textContent;const status=document.getElementById('copy-status');try{await navigator.clipboard.writeText(text);status.textContent='Citation copied.';}catch{status.textContent='Select the citation below, or download the BibTeX file.';}});
document.querySelector('[data-print]')?.addEventListener('click',()=>window.print());
