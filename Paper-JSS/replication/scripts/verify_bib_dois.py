"""Verify every DOI in manuscript/jss-bib.bib against authoritative metadata.

For each entry with a ``doi`` field this resolves the DOI to Crossref (or to
DataCite for ``10.48550/arXiv.*`` identifiers) and compares the registered
title / first-author family name / year against the bib entry, flagging any
mismatch. Entries without a DOI are listed for separate manual verification.

This is the reproducible backbone of the citation-verification policy:
a reviewer can re-run it to confirm no DOI points to the wrong paper.

Usage (from the Paper-JSS/ root)::

    python3 replication/scripts/verify_bib_dois.py

Requires only the Python standard library and outbound HTTPS to
api.crossref.org / api.datacite.org. Benign auto-flags (LaTeX-accent and
HTML-tag normalization artifacts, preprint-vs-published year differences) are
documented in references/JSS-reference-hardening-ledger.md.
"""
import re, json, urllib.request, urllib.parse, time, html, sys

MAILTO="brycew6m@stanford.edu"

def parse_bib(path):
    txt=open(path,encoding='utf-8').read()
    txt=re.sub(r'(?<!\\)%.*','',txt)
    entries=[]
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,]+),',txt):
        etype=m.group(1).lower(); key=m.group(2).strip()
        b=txt.index('{',m.start()); d=0; i=b
        while i<len(txt):
            if txt[i]=='{':d+=1
            elif txt[i]=='}':
                d-=1
                if d==0:break
            i+=1
        body=txt[b+1:i]
        def field(name):
            fm=re.search(r'\b'+name+r'\s*=\s*',body)
            if not fm:return None
            j=fm.end()
            if body[j]=='{':
                dd=0;k=j
                while k<len(body):
                    if body[k]=='{':dd+=1
                    elif body[k]=='}':
                        dd-=1
                        if dd==0:break
                    k+=1
                return body[j+1:k]
            if body[j]=='"':
                k=j+1
                while k<len(body) and body[k]!='"':k+=1
                return body[j+1:k]
            k=j
            while k<len(body) and body[k] not in ',\n':k+=1
            return body[j:k]
        entries.append(dict(key=key,etype=etype,doi=field('doi'),title=field('title'),
                            author=field('author'),year=field('year')))
    return entries

def norm(s):
    if not s:return ''
    s=html.unescape(s)
    s=re.sub(r'<[^>]+>','',s)
    s=re.sub(r'[{}\\]','',s)
    s=re.sub(r'[^a-z0-9 ]',' ',s.lower())
    return re.sub(r'\s+',' ',s).strip()

def first_family(author):
    if not author:return ''
    a=author.split(' and ')[0]
    a=re.sub(r'[{}\\]','',a)
    if ',' in a: fam=a.split(',')[0]
    else: fam=a.split()[-1] if a.split() else ''
    return norm(fam)

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'StatsPAI-refcheck (mailto:%s)'%MAILTO})
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.load(r)

def check(e):
    doi=e['doi'].strip()
    bt=norm(e['title']); bf=first_family(e['author']); by=(e['year'] or '').strip()
    try:
        if doi.lower().startswith('10.48550/arxiv') or 'arxiv' in doi.lower():
            d=fetch('https://api.datacite.org/dois/'+urllib.parse.quote(doi))['data']['attributes']
            ct=norm((d.get('titles') or [{}])[0].get('title'))
            creators=d.get('creators') or []
            cf=norm((creators[0].get('familyName') or creators[0].get('name','').split(',')[0]) if creators else '')
            cy=str(d.get('publicationYear') or '')
            src='DataCite'
        else:
            d=fetch('https://api.crossref.org/works/'+urllib.parse.quote(doi)+'?mailto='+MAILTO)['message']
            ct=norm(' '.join(d.get('title') or []))
            auth=d.get('author') or []
            cf=norm(auth[0].get('family','')) if auth else ''
            cy=''
            for f in ('published-print','published-online','issued','created'):
                if d.get(f,{}).get('date-parts'):
                    cy=str(d[f]['date-parts'][0][0]);break
            src='Crossref'
    except Exception as ex:
        return ('RESOLVE_FAIL',doi,str(ex)[:60],'','')
    # compare
    a=set(bt.split()); b=set(ct.split())
    jac=len(a&b)/len(a|b) if a and b else 0
    title_ok = jac>=0.55 or bt in ct or ct in bt
    author_ok = (bf in cf or cf in bf) if (bf and cf) else None
    year_ok = (by==cy) if (by and cy) else None
    flags=[]
    if not title_ok: flags.append(f"TITLE(jac={jac:.2f}) bib='{bt[:45]}' doi='{ct[:45]}'")
    if author_ok is False: flags.append(f"AUTHOR bib='{bf}' doi='{cf}'")
    if year_ok is False: flags.append(f"YEAR bib={by} doi={cy}")
    return ('OK' if not flags else 'MISMATCH', doi, '; '.join(flags), src, f"jac={jac:.2f}")

# Verify the full reference corpus: submission subset (jss-bib.bib) plus the
# orphan entries split out into jss-bib-archival.bib. Moving an entry to the
# archival file must not drop it from DOI re-verification.
import os as _os
entries=parse_bib('manuscript/jss-bib.bib')
if _os.path.exists('manuscript/jss-bib-archival.bib'):
    entries+=parse_bib('manuscript/jss-bib-archival.bib')
withdoi=[e for e in entries if e['doi']]
nodoi=[e for e in entries if not e['doi']]
print(f"Total {len(entries)} | with DOI {len(withdoi)} | no DOI {len(nodoi)}\n"+"="*72)
bad=[]
for e in withdoi:
    status,doi,detail,src,extra=check(e)
    if status!='OK':
        bad.append((e['key'],status,detail))
        print(f"[{status}] {e['key']}  ({src})\n    {detail}")
    time.sleep(0.15)
print("="*72)
print(f"\nVERIFIED OK: {len(withdoi)-len(bad)}/{len(withdoi)}   |   FLAGGED: {len(bad)}")
print("\nNO-DOI entries (verify separately):")
for e in nodoi: print(f"  {e['key']} ({e['etype']})")
