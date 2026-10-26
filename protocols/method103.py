"""Label-blind, fixed-budget adaptations of public SetR-IRI and MMR methods."""
from pathlib import Path
import math,re
import common98 as c
from core57 import render,pack_order
from reader59_frozen import check_prompt,answer_prompt,parse_stage

ARMS=('setr_iri_budget','mmr')
REFERENCE_ARMS=('plain_set','set_graph','strong_chain','joint')
def cache_key(q,stage,prompt):return c.digest([q,stage,prompt])

def restricted(row,plan):
    keep=set(plan['candidate_ids']);scores=dict(zip(row['rank_order'],row['rank_scores']))
    rr=dict(row,units=[dict(u) for u in row['units'] if u['id'] in keep],rank_order=[i for i in row['rank_order'] if i in keep])
    rr['rank_scores']=[scores[i] for i in rr['rank_order']];return rr

def mmr_select(row,similarity,budget,lam=.5):
    """Greedy MMR over feasible remaining units; rejected units are never selected."""
    order=row['rank_order'];scores=dict(zip(order,row['rank_scores']));cost={u['id']:u['tokens'] for u in row['units']}
    index={i:j for j,i in enumerate(order)};selected=[];remaining=set(order);left=budget
    while True:
        feasible=[i for i in order if i in remaining and cost[i]<=left]
        if not feasible:break
        def value(i):return lam*scores[i]-(1-lam)*(max(similarity[index[i]][index[j]] for j in selected) if selected else 0.)
        chosen=max(feasible,key=lambda i:(value(i),-index[i],-i));selected.append(chosen);remaining.remove(chosen);left-=cost[chosen]
    return sorted(selected)

def load_inputs(root,cfg):
    import numpy as np
    root=Path(root);rows=c.read(root/'data/inputs.json');plans=c.read(root/'data/plans.json');templates=c.read(root/'data/setr_prompts.json')
    if cfg['source_budget_tokens']!=256 or cfg['mmr_lambda']!=.5 or cfg['new_arms']!=list(ARMS):raise ValueError('Frozen controls changed')
    if len(rows)!=cfg['input_questions'] or len({r['qid'] for r in rows})!=len(rows) or set(plans)!={r['qid'] for r in rows}:raise ValueError('Question/plan identities differ')
    with np.load(root/'data/mmr_vectors.npz',allow_pickle=False) as z:
        texts=z['texts'].tolist();vec=z['vectors'].astype(np.float64)
    if vec.shape!=(len(texts),384) or len(set(texts))!=len(texts) or not np.isfinite(vec).all():raise ValueError('Invalid MMR vectors')
    norms=np.linalg.norm(vec,axis=1,keepdims=True)
    if (norms<=0).any():raise ValueError('Empty MMR vector')
    vec/=norms;ix={s:i for i,s in enumerate(texts)}
    for row in rows:
        if set(row)!={'qid','question','options','units','rank_order','rank_scores'}:raise ValueError('Unexpected inference field')
        ids=[u['id'] for u in row['units']]
        if len(ids)!=len(set(ids)) or sorted(ids)!=sorted(row['rank_order']):raise ValueError('Unit/rank identity differs')
        if len(row['rank_scores'])!=len(ids) or any(not math.isfinite(x) for x in row['rank_scores']):raise ValueError('Invalid relevance scores')
        for u in row['units']:
            if set(u)!={'id','text','tokens'} or type(u['id']) is not int or type(u['tokens']) is not int or u['tokens']<=0:raise ValueError('Invalid source unit')
        p=plans[row['qid']];keep=p['candidate_ids']
        if set(p)!={'candidate_ids','candidate_cost'} or keep!=sorted(set(keep)) or not set(keep)<=set(ids) or not keep:raise ValueError('Invalid candidate plan')
        if p['candidate_cost']!=sum(u['tokens'] for u in row['units'] if u['id'] in keep):raise ValueError('Candidate cost differs')
        rr=restricted(row,p);p['setr_templates']=templates
        if p['candidate_cost']<=256:p['mmr_ids']=list(keep)
        else:
            unit={u['id']:u['text'] for u in rr['units']};v=vec[[ix[unit[i]] for i in rr['rank_order']]]
            similarity=v@v.T;p['mmr_ids']=mmr_select(rr,similarity,256,cfg['mmr_lambda'])
        check_packet(row,p['mmr_ids'],keep,256)
    rows.sort(key=lambda r:c.digest(['step103-public-controls-order',r['qid']]))
    return rows,plans

def check_packet(row,ids,candidates,budget):
    if ids!=sorted(set(ids)) or not set(ids)<=set(candidates):raise ValueError('Invalid source packet')
    if sum(u['tokens'] for u in row['units'] if u['id'] in ids)>budget:raise ValueError('Source cap exceeded')

def setr_prompt(row,templates,budget):
    units={u['id']:u for u in row['units']};order=row['rank_order']
    context='\n\n\n'.join(re.sub(r'\n+',' ',f'[{j+1}] {units[i]["text"].strip()}') for j,i in enumerate(order))
    core=templates['selection_IRI_prompt']
    if core.count('Number of passages is unlimited.')!=1:raise ValueError('Official prompt anchor changed')
    core=core.replace('Number of passages is unlimited.',f'The selected passages must have a total source evidence cost of at most {budget} tokens. Use the exact costs supplied below to choose a complete, informative set within this budget.')
    prompt=core.format(num=len(order),question=row['question'],context=context)
    prompt+='\n\nSource evidence costs (passage identifier: tokens): '+', '.join(f'[{j+1}]: {units[i]["tokens"]}' for j,i in enumerate(order))+'.'
    prompt+='\nThese costs include the original source identifiers and separators. The token budget applies to the selected source evidence, not to your explanation.'
    return [{'role':'system','content':[{'type':'text','text':templates['selection_sys_prompt']}]},
            {'role':'user','content':[{'type':'text','text':prompt}]}]

def parse(stage,raw,row=None):
    if stage!='setr':return parse_stage(stage,raw)
    # Official converter reads bracketed IDs after its last '## Final' marker.
    # Require that marker so rationale citations cannot masquerade as selection.
    if '## Final' not in raw:raise ValueError('Missing official final-selection marker')
    segment=raw.rsplit('## Final',1)[1]
    values=[int(v) for v in re.findall(r'\[(\d+)\]',segment)]
    if not values and not re.search(r'\[\s*\]',segment):raise ValueError('No final selection list')
    if any(i<1 or i>len(row['rank_order']) for i in values):raise ValueError('Selected identifier is outside candidate pool')
    # Duplicates are idempotent set membership; common pack_order also deduplicates.
    values=list(dict.fromkeys(values))
    return {'selected_ids':[row['rank_order'][i-1] for i in values],'display_ids':values}

def call(row,stage,prompt,ids,parents,phase,cap):
    return {'kind':'call','key':cache_key(row['qid'],stage,prompt)+'__'+stage,'qid':row['qid'],'stage':stage,
        'phase':phase,'row':row,'source_ids':ids,'prompt':prompt,'parents':parents,'source_cap_tokens':cap}

def layout(row,plan,cfg,records):
    q=row['qid'];rr=restricted(row,plan);cap=cfg['source_budget_tokens']
    parents={'input_sha256':c.digest(row),'plan_sha256':c.digest(plan)};selector=None;diagnostic={}
    if plan['candidate_cost']<=cap:
        packets={arm:list(plan['candidate_ids']) for arm in ARMS};diagnostic['selection']='all_candidates_fit'
    else:
        spec=call(rr,'setr',setr_prompt(rr,plan['setr_templates'],cap),plan['candidate_ids'],parents,'public_setr_iri_budget',None)
        yield spec
        selector=spec['key'];r=records[selector];selected=r['parsed']['selected_ids'] if r['valid'] else []
        packets={'setr_iri_budget':pack_order(rr,selected+rr['rank_order'],cap),'mmr':plan['mmr_ids']}
        diagnostic={'selection':'parsed_selection_then_rank_fill' if r['valid'] else 'invalid_selection_rank_fallback',
            'selected_ids':selected,'selected_unpacked_cost':sum(u['tokens'] for u in rr['units'] if u['id'] in selected),
            'budget_clipped':sum(u['tokens'] for u in rr['units'] if u['id'] in selected)>cap,
            'mmr_lambda':cfg['mmr_lambda']}
    for ids in packets.values():check_packet(row,ids,plan['candidate_ids'],cap)
    decisions={};read_parents=dict(parents,selector_record=records[selector]['record_sha256'] if selector else None)
    for packet in sorted({tuple(ids) for ids in packets.values()}):
        ids=list(packet);pid=c.digest(ids)
        spec=call(row,'check',check_prompt(row,ids),ids,dict(read_parents,packet_sha256=pid),'fixed_reader8',cap)
        yield spec
        note=records[spec['key']];keys=[spec['key']];answer=None
        if note['valid']:
            spec=call(row,'answer',answer_prompt(row,ids,note['parsed']['check']),ids,
                dict(read_parents,packet_sha256=pid,check=note['record_sha256']),'fixed_reader8',cap)
            yield spec
            answer=records[spec['key']];keys.append(spec['key'])
        valid=bool(note['valid'] and answer and answer['valid'])
        decisions[pid]={'ids':ids,'valid':valid,'answer':answer['parsed']['answer'] if valid else None,'record_keys':keys}
    yield {'kind':'contexts','qid':q,'candidate_cost':plan['candidate_cost'],'all_fit':plan['candidate_cost']<=cap,
        'packets':packets,'diagnostics':diagnostic,'selector_key':selector,'decisions':decisions,
        'packet_mapping':{a:c.digest(ids) for a,ids in packets.items()}}
    yield {'kind':'question_done','qid':q}
