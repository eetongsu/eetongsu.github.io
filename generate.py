"""Generate portable, readable HTML from the author's verified bibliographic data."""
from pathlib import Path
import html, json, re
from urllib.parse import quote

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'docs'
BASE='https://eetongsu.github.io'
profile=json.loads((ROOT/'data/profile.json').read_text(encoding='utf-8'))
papers=json.loads((ROOT/'data/publications.json').read_text(encoding='utf-8'))
notes=json.loads((ROOT/'data/research-notes.json').read_text(encoding='utf-8'))
e=lambda x:html.escape(str(x or ''),quote=True)
bykey={p['key']:p for p in papers}
scholar=profile['scholar']

def fullnames(p):
    result=[]
    for name in p.get('author','').split(' and '):
        if name=='others':result.append('et al.');continue
        if ',' in name:
            family,given=name.split(',',1);name=given.strip()+' '+family.strip()
        result.append(name.strip())
    return result

def authors(p):
    return ', '.join('<strong>'+e(n)+'</strong>' if n in ('Tong Su','苏童') else e(n) for n in fullnames(p))

def venue(p):
    s=p.get('venue','')
    if p.get('volume'):s+=' '+p['volume']
    if p.get('number'):s+=' ('+p['number']+')'
    if p.get('pages'):s+=', '+p['pages'].replace('--','–').replace('-','–')
    return s

def topics(p):
    if p['key'] in notes:return notes[p['key']]['topics']
    t=p['title'].lower(); tags=[]
    if any(w in t for w in ['reinforcement','certification']):tags.append('Safe learning')
    if any(w in t for w in ['stability','inertia','simulator']):tags.append('Stability')
    if any(w in t for w in ['probabilistic','prediction','forecast','gaussian','chance-constrained','bayesian']):tags.append('Uncertainty')
    if any(w in t for w in ['rating','grid-enhancing','transmission','planning','energy management']):tags.append('Grid technologies')
    if any(w in t for w in ['review','survey','overview']):tags.append('Reviews')
    return tags or ['Other research']

def kind(p):
    return {'article':'Journal article','inproceedings':'Conference paper','report':'Report','preprint':'Preprint'}.get(p['type'],'Research output')

def bib(p):
    entrytype={'report':'techreport','preprint':'misc'}.get(p['type'],p['type'])
    if not p.get('year') and p['type']=='report':entrytype='misc'
    key=re.sub('[^a-zA-Z0-9_-]','',p['key']) or 'tong-su-'+p['slug']
    fields={'title':p['title'],'author':p.get('author','')}
    if p.get('year'):fields['year']=p['year']
    if p.get('venue'):
        fields['booktitle' if p['type']=='inproceedings' else 'institution' if p['type']=='report' else 'howpublished' if p['type']=='preprint' else 'journal']=p['venue']
    for k in ['volume','number','pages','doi','url']:
        if p.get(k):fields[k]=re.sub(r'[-–]+','--',p[k]) if k=='pages' else p[k]
    def esc(s):return str(s).replace('&',r'\&').replace('%',r'\%')
    return '@'+entrytype+'{'+key+',\n'+',\n'.join('  '+k+' = {'+esc(v)+'}' for k,v in fields.items())+'\n}\n'

def manuscript_label(p):
    return 'Preprint' if p['manuscript']['version'].startswith('Preprint') else 'Author manuscript'

def links(p,detail=True):
    items=[]
    if detail:items.append(('/publications/'+p['slug']+'/','Paper details'))
    if p.get('manuscript'):items.append((p['manuscript']['url'],manuscript_label(p)+' (PDF)'))
    if p.get('doi'):items.append(('https://doi.org/'+p['doi'],'DOI'))
    elif p.get('url'):items.append((p['url'],'Official report page' if p['type']=='report' else 'Source'))
    if p.get('arxiv'):items.append((p['arxiv'],'arXiv'))
    for resource in p.get('resources',[]):items.append((resource['url'],resource['label']))
    if p.get('researchgate'):items.append((p['researchgate'],'ResearchGate'))
    items.append(('/citations/'+p['slug']+'.bib','BibTeX'))
    return '<div class="paperlinks">'+''.join('<a href="'+e(url)+'"'+(' download' if url.endswith('.bib') else '')+'>'+label+'</a>' for url,label in items)+'</div>'

def recognition(p):
    if not p.get('recognition'):return ''
    badges='<ul class="recognition" aria-label="Publication recognition">'+''.join('<li title="'+e(r['detail'])+'">'+e(r['label'])+'</li>' for r in p['recognition'])+'</ul>'
    if p.get('recognition_note'):badges+='<p class="recognition-note">'+e(p['recognition_note'])+'</p>'
    return badges

def additional_report(r):
    return '<article class="record"><h3><a href="'+e(r['url'])+'">'+e(r['title'])+'</a></h3><p>'+e(r['number'])+' · '+e(r['date'])+'</p><div class="paperlinks"><a href="'+e(r['url'])+'">Official report page</a><a href="https://doi.org/'+e(r['doi'])+'">DOI</a></div></article>'

def pub(p,summary=False):
    tags=topics(p);n=notes.get(p['key'],{})
    return '<article class="pub" data-publication data-kind="'+e(kind(p))+'" data-topics="'+e('|'.join(tags))+'"><div class="pubyear">'+e(p.get('year') or '—')+'</div><div><h3><a href="/publications/'+p['slug']+'/">'+e(p['title'])+'</a></h3><p class="authors">'+authors(p)+'</p><p class="venue">'+e(venue(p))+'</p>'+recognition(p)+('<p class="pubdesc">'+e(n['summary'])+'</p>' if summary and n.get('summary') else '')+links(p)+'</div></article>'

def header(active):
    items=[('About','/'),('Research','/research/'),('Publications','/publications/'),('CV','/cv/'),('Contact','/#contact')]
    return '<a class="skip" href="#main">Skip to content</a><header class="topbar"><div class="wrap nav"><a class="brand" href="/">Tong Su<span>Dartmouth College</span></a><nav class="navlinks" aria-label="Main navigation">'+''.join('<a href="'+url+'"'+(' aria-current="page"' if label==active else '')+'>'+label+'</a>' for label,url in items)+'</nav></div></header>'

def footer():
    return '<footer class="footer" id="contact"><div class="wrap"><div class="footmain"><div><h2>Let’s connect.</h2><p>Research on reliable, renewable-rich power systems.</p><a href="mailto:'+profile['email']+'">'+profile['email']+'</a></div><div class="footlinks"><a href="'+scholar+'">Google Scholar</a><a href="'+profile['advisor']+'">CREATE Lab</a><a href="/cv/">CV</a></div></div><div class="footbottom"><span>© 2026 Tong Su</span><span>Updated October 2026 · Dartmouth College</span></div></div></footer>'

ICON="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='10' fill='%2307553b'/%3E%3Ctext x='32' y='43' text-anchor='middle' font-family='Georgia' font-size='33' fill='white'%3ETS%3C/text%3E%3C/svg%3E"
def page(path,title,description,body,active='',extra='',structured=None):
    dest=OUT/path.lstrip('/')/'index.html';dest.parent.mkdir(parents=True,exist_ok=True)
    if path == '/' and profile.get('google_site_verification'):
        extra += '<meta name="google-site-verification" content="'+e(profile['google_site_verification'])+'">'
    if structured is None:structured={'@context':'https://schema.org','@type':'WebPage','name':title,'url':BASE+path}
    raw=json.dumps(structured,ensure_ascii=False).replace('</','<\\/')
    doc='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(title)+'</title><meta name="description" content="'+e(description)+'"><link rel="canonical" href="'+BASE+path+'"><meta property="og:title" content="'+e(title)+'"><meta property="og:description" content="'+e(description)+'"><meta property="og:type" content="website"><meta property="og:url" content="'+BASE+path+'"><link rel="icon" type="image/svg+xml" href="'+ICON+'"><link rel="stylesheet" href="/assets/site.css"><script src="/assets/site.js" defer></script><script type="application/ld+json">'+raw+'</script>'+extra+'</head><body>'+header(active)+'<main id="main" class="wrap">'+body+'</main>'+footer()+'</body></html>'
    dest.write_text(doc,encoding='utf-8')

def hero():
    return '<section class="hero"><div><p class="eyebrow">Power systems · Machine learning · Control</p><h1>Tong <span>Su</span></h1><p class="role">Ph.D. Candidate & Research Assistant</p><p class="affiliation">Dartmouth College · CREATE Lab</p><p class="intro">My research focuses on power system stability and control, with an emphasis on renewable energy integration.</p><p class="subintro">My research spans transient stability, safe reinforcement learning, probabilistic grid operation, and grid-enhancing technologies. My Ph.D. advisor is <a href="'+profile['advisor']+'">Prof. Junbo Zhao</a>.</p><div class="actions"><a class="button primary" href="/publications/">Explore publications</a><a class="button" href="'+scholar+'">Google Scholar</a><a class="button" href="/cv/">View CV</a></div></div><figure class="portrait"><img src="/assets/tong-su.jpg" width="256" height="256" alt="Tong Su"><figcaption><strong>Dartmouth College</strong>Electrical Engineering<br>Power system dynamics & stability</figcaption></figure></section>'

themes=[
 ('safe-learning','Safe & certified learning','Reinforcement learning and neural network certification for stability-constrained control.',['su2025review','su2025neural','su2025safe']),
 ('probabilistic-operation','Probabilistic grid operation','Uncertainty-aware models, Gaussian processes, and chance-constrained optimization.',['tan2026gaussian','su2023deep','su2024analytic','su2023probabilistic']),
 ('grid-technologies','Grid-enhancing technologies','Dynamic line ratings and operational flexibility for renewable energy integration.',['su2025grid','su2026multi','su2024dynamic'])]
focus='<section class="section"><div class="sectionhead"><h2>Research focus</h2><a href="/research/">Research & projects</a></div><div class="focusgrid">'+''.join('<article class="focusitem"><div class="n">0'+str(i+1)+'</div><h3><a href="/research/#'+id+'">'+title+'</a></h3><p>'+desc+'</p></article>' for i,(id,title,desc,keys) in enumerate(themes))+'</div></section>'
selected='<section class="section"><div class="sectionhead"><h2>Selected publications</h2><a href="/publications/">All research records</a></div>'+''.join(pub(bykey[k],True) for k in ['su2025review','su2025grid','su2025neural','su2026multi'])+'</section>'
metric='<div class="metricbar"><div class="metrics"><div class="metric"><strong>744</strong><span>Citations</span></div><div class="metric"><strong>14</strong><span>h-index</span></div><div class="metric"><strong>17</strong><span>i10-index</span></div></div><div class="metricsource"><a href="'+scholar+'">Google Scholar</a><br>Snapshot · October 1, 2026</div></div>'
person={'@context':'https://schema.org','@type':'ProfilePage','name':'Tong Su · Power Systems & AI','url':BASE+'/', 'mainEntity':{'@type':'Person','@id':BASE+'/#person','name':'Tong Su','email':profile['email'],'jobTitle':'Ph.D. Candidate and Research Assistant','affiliation':{'@type':'CollegeOrUniversity','name':'Dartmouth College'},'sameAs':[scholar],'knowsAbout':['Power system transient stability','Safe reinforcement learning','Uncertainty quantification','Grid-enhancing technologies']}}
page('/','Tong Su · Power Systems & AI','Tong Su, Ph.D. candidate and research assistant at Dartmouth College. Research in power system stability, safe learning, uncertainty, and grid-enhancing technologies.',hero()+focus+selected+metric,'About',structured=person)

sortpapers=sorted(papers,key=lambda p:(-(int(p.get('year') or 0)),p['title'].lower()))
options=''.join('<option>'+t+'</option>' for t in ['Safe learning','Stability','Uncertainty','Grid technologies','Reviews','Other research'])
types=''.join('<option>'+t+'</option>' for t in ['Journal article','Conference paper','Report','Preprint'])
library='<div class="pagehead"><p class="eyebrow">Research output</p><h1>Publications</h1><p>Journal articles, conference papers, and other research outputs in power systems and machine learning.</p><div class="actions"><a class="button" href="/citations/tong-su-publications.bib" download>Download bibliography</a><a class="button" href="'+scholar+'">Google Scholar</a></div></div><div class="toolbar" role="search" aria-label="Filter publications"><div class="field"><label for="publication-search">Search publications</label><input id="publication-search" type="search" placeholder="Title, author, year, or journal"></div><div class="field"><label for="publication-topic">Research topic</label><select id="publication-topic"><option value="">All topics</option>'+options+'</select></div><div class="field"><label for="publication-kind">Publication type</label><select id="publication-kind"><option value="">All types</option>'+types+'</select></div></div><p id="result-count" class="resultcount" aria-live="polite">'+str(len(papers))+' research records</p><div>'+''.join(pub(p) for p in sortpapers)+'</div><p id="empty-results" class="empty" hidden>No matching publications. Try a different keyword or clear the filters.</p>'
library+='<section class="section"><h2>Additional technical report</h2>'+''.join(additional_report(r) for r in profile['additional_reports'])+'</section>'
page('/publications/','Publications · Tong Su','Publications by Tong Su: journal articles, conference papers, reports, DOI links, research summaries, and BibTeX citations.',library,'Publications')

research='<div class="pagehead"><p class="eyebrow">Methods, systems & applications</p><h1>Research</h1><p>Connecting learning-based models with the physical and operational constraints of renewable-rich power systems.</p><div class="researchindex">'+''.join('<a href="#'+id+'">'+title+'</a>' for id,title,desc,keys in themes)+'<a href="#projects">Research projects</a></div></div>'
themeprose={
 'safe-learning':'My work examines how learning-based controllers and surrogate models can incorporate safety constraints. I study safe reinforcement learning for power system control and neural network certification for transient stability-constrained optimization.',
 'probabilistic-operation':'Renewable generation, loads, and incomplete measurements create uncertainty in grid operation. My research combines probabilistic learning models with chance-constrained optimization for transient stability, voltage prediction, and voltage regulation.',
 'grid-technologies':'I study how dynamic line ratings and other grid-enhancing technologies can support clean energy integration. My work connects transmission capacity with system security and load margin, including applications involving offshore wind.'}
for id,title,desc,keys in themes:
    research+='<section class="section" id="'+id+'"><div class="twocol"><div class="sidelabel">'+title+'</div><div><h2>'+title+'</h2><p>'+themeprose[id]+'</p>'+''.join(pub(bykey[k],False) for k in keys)+'</div></div></section>'
research+='<section class="section" id="projects"><h2>Research projects</h2><p class="subintro">Selected collaborative projects, with links to public project information.</p>'
for p in profile['projects']:
    research+='<article class="project"><h3>'+e(p['title'])+'</h3>'+('<p>'+e(p['subtitle'])+'</p>' if p.get('subtitle') else '')+'<p>'+e(p['summary'])+'</p><p class="funding">Funding: '+e(p['funding'])+'</p>'
    if p.get('partners'):
        research+='<p class="funding">Collaborating institutions: '+e(p['partners'])+'</p>'
    research+='<div class="paperlinks">'+''.join('<a href="'+e(s['url'])+'">'+e(s['label'])+'</a>' for s in p['sources'])+'</div></article>'
research+='</section>'
page('/research/','Research & Projects · Tong Su','Research themes and collaborative projects in safe learning, probabilistic grid operation, dynamic line rating, and renewable integration.',research,'Research')

cv='<div class="pagehead"><p class="eyebrow">Curriculum vitae</p><h1>Tong Su</h1><p>Ph.D. Candidate & Research Assistant · Dartmouth College<br><a href="mailto:'+profile['email']+'">'+profile['email']+'</a></p><div class="cvactions"><button class="button primary" data-print>Print / save as PDF</button><a class="button" href="/publications/">Complete publication list</a></div></div>'
for field,title in [('education','Education'),('experience','Research experience')]:
    cv+='<section class="section twocol"><h2>'+title+'</h2><div>'
    for r in profile[field]:cv+='<article class="record"><p class="date">'+e(r['dates'])+'</p><h3>'+e(r['title'])+'</h3><strong>'+e(r['institution'])+'</strong><p>'+e(r['description'])+'</p></article>'
    cv+='</div></section>'
cv+='<section class="section twocol"><h2>Honors & awards</h2><div>'
for date,title,detail in profile['honors']:cv+='<article class="record"><p class="date">'+e(date)+'</p><h3>'+e(title)+'</h3>'+('<p>'+e(detail)+'</p>' if detail else '')+'</article>'
cv+='</div></section><section class="section twocol"><h2>Academic service</h2><div><h3>Peer review</h3><ul class="service">'+''.join('<li>'+e(x)+'</li>' for x in profile['reviewing'])+'</ul></div></section>'
cv+='<section class="section twocol"><h2>Technical reports</h2><div>'+''.join(additional_report(r) for r in profile['additional_reports'])+'<article class="record"><h3>Application of Spatio-Temporal Data-Driven and Machine Learning Algorithms for Security Assessment</h3><p>PES-TR104 · November 2022</p>'+recognition(bykey['segundo2022application'])+'<a href="https://resourcecenter.ieee-pes.org/publications/technical-reports/pes_tp_tr104_amps_112122">Official report page</a></article></div></section>'
cv+='<section class="section"><div class="sectionhead"><h2>Publications</h2><a href="/citations/tong-su-publications.bib" download>Download BibTeX</a></div>'+''.join(pub(p) for p in sortpapers)+'</section>'
page('/cv/','CV · Tong Su','Education, research experience, honors, academic service, and publications of Tong Su at Dartmouth College.',cv,'CV')

(OUT/'citations').mkdir(exist_ok=True)
for p in papers:
    n=notes.get(p['key'],{});url='/publications/'+p['slug']+'/'
    citation=bib(p);(OUT/'citations'/(p['slug']+'.bib')).write_text(citation,encoding='utf-8')
    summary=n.get('summary') or (p['title']+'. '+venue(p)+('. '+p['year'] if p.get('year') else ''))
    body='<div class="pagehead paperhead"><div class="breadcrumbs"><a href="/publications/">Publications</a> / '+e(p.get('year') or 'Research output')+'</div><p class="eyebrow">'+e(kind(p))+'</p><h1>'+e(p['title'])+'</h1><p class="authors">'+authors(p)+'</p><p class="venue">'+e(venue(p))+'</p>'+recognition(p)+links(p,False)+'</div>'
    middle=''
    if n.get('overview') or n.get('summary'):
        middle+='<h2>Research summary</h2><p>'+e(n.get('overview') or n['summary'])+'</p>'
    if n.get('questions'):middle+='<h2>Questions this work addresses</h2><ul>'+''.join('<li>'+e(q)+'</li>' for q in n['questions'])+'</ul>'
    if p.get('alternateTitle'):middle+='<p>Original Chinese title: <span lang="zh">'+e(p['alternateTitle'])+'</span>.</p>'
    if not middle:middle='<h2>About this publication</h2><p>This page provides the publication record and citation for this work.</p><p><a href="'+e(p.get('url') or scholar)+'">Read the source record</a> for the article and its publication details.</p>'
    if n.get('source'):middle+='<p class="note">Related reading: <a href="'+e(n['source'])+'">'+('arXiv abstract and manuscript' if 'arxiv.org' in n['source'] else 'Source publication or project page')+'</a>.</p>'
    if p.get('resources'):
        middle+='<section class="themeblock"><h2>Updated review resources</h2>'+''.join('<p>'+e(r['description'])+'</p><a href="'+e(r['url'])+'">'+e(r['label'])+'</a>' for r in p['resources'])+'</section>'
    if p.get('manuscript'):
        m=p['manuscript']
        middle+='<section class="section"><h2>Read the manuscript</h2><p><a class="button primary" href="'+e(m['url'])+'">Download '+manuscript_label(p).lower()+' (PDF)</a></p><p class="note">'+e(m['version'])+' with a citation and rights sheet. Please cite the published article using the DOI above.</p><p class="note">'+e(m['notice'])+' <a href="'+e(m['policy'])+'">'+('License and reuse' if m.get('license') else 'Publisher sharing policy')+'</a>.</p></section>'
    middle+='<section class="section"><h2>Cite this work</h2><div class="actions"><button class="button" data-copy="citation">Copy BibTeX</button><a class="button" href="/citations/'+p['slug']+'.bib" download>Download .bib</a><span id="copy-status" class="copymsg" role="status"></span></div><pre id="citation">'+e(citation)+'</pre></section>'
    aside='<p><strong>Publication year</strong>'+e(p.get('year') or 'Not listed in source record')+'</p><p><strong>Publication type</strong>'+e(kind(p))+'</p>'
    if p.get('doi'):aside+='<p><strong>DOI</strong><a href="https://doi.org/'+e(p['doi'])+'">'+e(p['doi'])+'</a></p>'
    if n.get('keywords'):aside+='<p><strong>Keywords</strong>'+', '.join(e(k) for k in n['keywords'])+'</p>'
    if p.get('arxiv'):aside+='<p><strong>Open manuscript</strong><a href="'+p['arxiv']+'">Read on arXiv</a></p>'
    if p.get('manuscript'):aside+='<p><strong>Manuscript PDF</strong><a href="'+e(p['manuscript']['url'])+'">'+e(p['manuscript']['version'])+'</a><br>'+str(p['manuscript']['pages'])+' manuscript pages</p>'
    aside+='<p><strong>Author profile</strong><a href="'+scholar+'">Tong Su on Google Scholar</a></p>'
    body+='<section class="section paperbody"><div class="prose">'+middle+'</div><aside>'+aside+'</aside></section>'
    fields=[('citation_title',p['title'])]+[('citation_author',name) for name in fullnames(p) if name!='et al.']
    if p.get('year'):fields.append(('citation_publication_date',p['year']))
    if p.get('manuscript'):fields.append(('citation_pdf_url',BASE+p['manuscript']['url']))
    if p.get('venue') and p['type'] in ['article','inproceedings']:fields.append(('citation_journal_title' if p['type']=='article' else 'citation_conference_title',p['venue']))
    for k,tag in [('volume','citation_volume'),('number','citation_issue'),('doi','citation_doi')]:
        if p.get(k):fields.append((tag,p[k]))
    if p.get('pages'):
        pp=re.split(r'[-–]+',p['pages']);fields.append(('citation_firstpage',pp[0]))
        if len(pp)>1:fields.append(('citation_lastpage',pp[-1]))
    extra=''.join('<meta name="'+tag+'" content="'+e(value)+'">' for tag,value in fields)
    schema={'@context':'https://schema.org','@type':'ScholarlyArticle','headline':p['title'],'url':BASE+url,'author':[{'@type':'Person','name':name} for name in fullnames(p) if name!='et al.'],'description':summary}
    if p.get('year'):schema['datePublished']=p['year']
    if p.get('doi'):schema['identifier']={'@type':'PropertyValue','propertyID':'DOI','value':p['doi']};schema['sameAs']='https://doi.org/'+p['doi']
    if p.get('venue'):schema['isPartOf']={'@type':'CreativeWork','name':p['venue']}
    awards=[r['detail'] for r in p.get('recognition',[]) if r['category']=='award']
    if awards:schema['award']=awards
    if p.get('resources'):schema['subjectOf']=[{'@type':'CreativeWork','name':r['label'],'url':r['url'],'description':r['description']} for r in p['resources']]
    if p.get('manuscript'):schema['encoding']={'@type':'MediaObject','contentUrl':BASE+p['manuscript']['url'],'encodingFormat':'application/pdf','name':p['manuscript']['version'],'contentSize':str(p['manuscript']['bytes'])+' bytes'}
    page(url,p['title']+' · Tong Su',summary,body,'Publications',extra,schema)

(OUT/'citations/tong-su-publications.bib').write_text('\n'.join(bib(p) for p in sortpapers),encoding='utf-8')
routes=['/','/research/','/publications/','/cv/']+['/publications/'+p['slug']+'/' for p in papers]
(OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+e(BASE+r)+'</loc><lastmod>2026-10-01</lastmod></url>' for r in routes)+'</urlset>',encoding='utf-8')
(OUT/'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: '+BASE+'/sitemap.xml\n',encoding='utf-8')
(OUT/'404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Page not found · Tong Su</title><link rel="stylesheet" href="/assets/site.css"><main class="wrap pagehead"><h1>Page not found</h1><p>The page may have moved.</p><a class="button" href="/">Return to Tong Su’s homepage</a></main></html>',encoding='utf-8')
print(json.dumps({'pages':len(routes),'paper_pages':len(papers),'bibliographies':len(papers)+1,'doi_records':sum(bool(p.get('doi')) for p in papers)}))
