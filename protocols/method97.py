"""One fixed deletion intervention; all language prompts remain byte-frozen.

Only the supplied packet is observed. Every proper single-unit deletion is read
with the same reader. Different answers are hypotheses, never conflict labels.
This changes the common reader, not the evidence selector.
"""
from pathlib import Path
import itertools,json,math
from core57 import render
from reader59_frozen import check_prompt,answer_prompt,parse_stage
from semantic61_frozen import digest,normalize,support_prompt,relation_prompt,parse as semantic_parse

def parse(stage,raw,row=None):
    return parse_stage(stage,raw) if stage in ('check','answer') else semantic_parse(stage,raw,row)

def cache_key(q,stage,prompt):return digest([q,stage,prompt])

def load_inputs(root,cfg):
    root=Path(root);read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    rows=read(root/'data/inputs.json');plans=read(root/'data/packets.json')
    if len(rows)!=cfg['input_questions'] or len({r['qid'] for r in rows})!=len(rows):raise ValueError('Question count/IDs differ')
    if set(plans)!={r['qid'] for r in rows}:raise ValueError('Plan IDs differ')
    for row in rows:
        if set(row)!={'qid','question','options','units','rank_order','rank_scores'}:raise ValueError('Unexpected inference field')
        known={u['id'] for u in row['units']}
        if len(known)!=len(row['units']) or sorted(known)!=sorted(row['rank_order']):raise ValueError('Unit/rank IDs differ')
        if len(row['rank_scores'])!=len(known) or any(not math.isfinite(s) for s in row['rank_scores']):raise ValueError('Rank scores differ')
        for u in row['units']:
            if set(u)!={'id','text','tokens'} or type(u['id']) is not int or type(u['tokens']) is not int or u['tokens']<=0:raise ValueError('Invalid unit')
        for ids in plans[row['qid']]['packets'].values():
            if not ids or ids!=sorted(set(ids)) or not set(ids)<=known:raise ValueError('Invalid packet')
            if sum(u['tokens'] for u in row['units'] if u['id'] in ids)>cfg['source_budget_tokens']:raise ValueError('Packet over budget')
    rows.sort(key=lambda r:digest(['step97-fixed-deletion-schedule',r['qid']]))
    return rows,plans

def call(row,key,stage,prompt,ids,parents):
    return {'kind':'call','qid':row['qid'],'row':row,'key':key,'stage':stage,'prompt':prompt,
            'source_ids':list(ids),'parents':dict(parents),'phase':'common_reader_deletion'}

def deletion_views(ids):
    # One sentence is not split or rewritten. Empty views are not queried.
    return [list(ids)]+[[j for j in ids if j!=i] for i in ids if len(ids)>1]

def candidates_from_views(views,costs,cap):
    by_answer={}
    for v in views:
        if not v['valid']:continue
        name=normalize(v['answer'])
        if not name or name in ('unknown','conflict'):continue
        by_answer.setdefault(name,[]).append(v)
    candidates=[]
    # Admission follows fixed full-view then ascending deletion-ID order.
    # Within an answer use the shortest available view, with stable ID ties.
    for name,vv in list(by_answer.items())[:cap]:
        best=min(vv,key=lambda v:(sum(costs[i] for i in v['ids']),v['ids']))
        candidates.append({'answer':best['answer'],'evidence_ids':best['ids'],
                           'answer_record_sha256':best['answer_record_sha256']})
    return candidates,len(by_answer)>cap

def layout(row,plan,cfg,records):
    q=row['qid'];scheduled={};baseparents={'input_sha256':digest(row),'plan_sha256':digest(plan)}
    costs={u['id']:u['tokens'] for u in row['units']}
    def request(stage,prompt,ids,parents):
        key=cache_key(q,stage,prompt)+'__'+stage
        if key not in scheduled:
            spec=call(row,key,stage,prompt,ids,dict(baseparents,**parents));scheduled[key]=spec
            yield spec
        return key,records[key]
    def read_view(ids):
        keys=[];ck,note=yield from request('check',check_prompt(row,ids),ids,{'packet_sha256':digest(ids)})
        keys.append(ck);ans=None
        if note['valid']:
            ak,ans=yield from request('answer',answer_prompt(row,ids,note['parsed']['check']),ids,
                                     {'packet_sha256':digest(ids),'check':note['record_sha256']})
            keys.append(ak)
        valid=bool(note['valid'] and ans and ans['valid'])
        return {'ids':list(ids),'valid':valid,'answer':ans['parsed']['answer'] if valid else None,
                'answer_record_sha256':ans['record_sha256'] if ans else None,'record_keys':keys}
    # Packet enumeration does not depend on arm names or labels.
    packetids=sorted({tuple(ids) for ids in plan['packets'].values()})
    decisions={};mapping={a:digest(list(ids)) for a,ids in plan['packets'].items()}
    for t in packetids:
        ids=list(t);pid=digest(ids);pooled=yield from read_view(ids);views=[pooled]
        keys=list(pooled['record_keys']);candidates=[];support=[];relations=[];cap_hit=False
        result={'valid':pooled['valid'],'answer':pooled['answer'],'reason':'pooled_reader_retained'}
        # Invalid baseline outputs stay invalid; the intervention does not repair
        # malformed JSON. Existing CONFLICT decisions are not flipped.
        if pooled['valid'] and normalize(pooled['answer'])!='conflict' and len(ids)>1:
            for sub in deletion_views(ids)[1:]:
                view=yield from read_view(sub);views.append(view);keys.extend(view['record_keys'])
            candidates,cap_hit=candidates_from_views(views,costs,cfg['candidate_cap'])
            if len(candidates)>=2:
                for i,c in enumerate(candidates):
                    witness={'answer':c['answer'],'evidence_ids':c['evidence_ids']}
                    key,rec=yield from request('support',support_prompt(row,witness),witness['evidence_ids'],
                                              {'candidate_answer':c['answer_record_sha256']})
                    keys.append(key)
                    support.append({'candidate':i,'accepted':bool(rec['valid'] and rec['parsed']['supported']),
                                    'record_key':key,'record_sha256':rec['record_sha256']})
                accepted=[v['candidate'] for v in support if v['accepted']]
                for i,j in itertools.combinations(accepted,2):
                    a,b=candidates[i],candidates[j]
                    left={k:a[k] for k in ('answer','evidence_ids')};right={k:b[k] for k in ('answer','evidence_ids')}
                    union=sorted(set(left['evidence_ids']+right['evidence_ids']))
                    key,rec=yield from request('relation',relation_prompt(row,left,right),union,
                        {'support_a':support[i]['record_sha256'],'support_b':support[j]['record_sha256']})
                    keys.append(key);relations.append({'left':i,'right':j,'relation':rec['parsed']['relation'] if rec['valid'] else 'invalid','record_key':key})
                parent={i:i for i in accepted}
                def root(i):
                    while parent[i]!=i:i=parent[i]
                    return i
                for rel in relations:
                    if rel['relation']=='equivalent':parent[root(rel['right'])]=root(rel['left'])
                conflicts=[r for r in relations if r['relation']=='conflict']
                collision=any(root(r['left'])==root(r['right']) for r in conflicts)
                if conflicts and not collision:result={'valid':True,'answer':'CONFLICT','reason':'two_complete_deletion_views_verified_incompatible'}
                elif collision:result['reason']='inconsistent_relations_pooled_retained'
        decisions[pid]={'packet_ids':ids,'pooled':pooled,'intervention':result,'views':views,
                        'candidates':candidates,'candidate_cap_hit':cap_hit,'support':support,'relations':relations,
                        'logical_record_keys':sorted(set(keys))}
        if any(not set(v['ids'])<=set(ids) for v in views):raise ValueError('Deletion introduced hidden evidence')
    yield {'kind':'contexts','qid':q,'packets':plan['packets'],'packet_mapping':mapping,
           'decisions':decisions,'plan_sha256':digest(plan)}
    yield {'kind':'question_done','qid':q}
