"""Read frozen Step100 packets; selection and inference never read gold labels."""
from pathlib import Path
import math
import common98 as c
from core57 import render
from reader59_frozen import check_prompt,answer_prompt,parse_stage

ARMS=('plain_set','set_graph','strong_chain','joint')

def parse(stage,raw,row=None):return parse_stage(stage,raw)
def cache_key(q,stage,prompt):return c.digest([q,stage,prompt])

def load_inputs(root,cfg):
    root=Path(root);rows=c.read(root/'data/inputs.json');plans=c.read(root/'data/packets.json')
    if len(rows)!=cfg['input_questions'] or len({r['qid'] for r in rows})!=len(rows):raise ValueError('Question identity/count differs')
    if set(plans)!={r['qid'] for r in rows}:raise ValueError('Plan IDs differ')
    for row in rows:
        if set(row)!={'qid','question','options','units','rank_order','rank_scores'}:raise ValueError('Unexpected inference field')
        ids=[u['id'] for u in row['units']]
        if len(ids)!=len(set(ids)) or sorted(ids)!=sorted(row['rank_order']):raise ValueError('Unit/rank identity differs')
        if len(row['rank_scores'])!=len(ids) or any(not math.isfinite(x) for x in row['rank_scores']):raise ValueError('Rank scores differ')
        for u in row['units']:
            if set(u)!={'id','text','tokens'} or type(u['id']) is not int or type(u['tokens']) is not int or u['tokens']<=0:raise ValueError('Invalid source unit')
        plan=plans[row['qid']]
        if set(plan)!={'packets'} or set(plan['packets'])!=set(ARMS):raise ValueError('Method packet identity differs')
        for selected in plan['packets'].values():
            if selected!=sorted(set(selected)) or not set(selected)<=set(ids):raise ValueError('Invalid packet')
            if sum(u['tokens'] for u in row['units'] if u['id'] in selected)>cfg['source_budget_tokens']:raise ValueError('Source cap exceeded')
    if sum(len({tuple(x) for x in p['packets'].values()}) for p in plans.values())!=cfg['unique_packets']:raise ValueError('Deduplicated packet count differs')
    if sum(len(p['packets']) for p in plans.values())!=cfg['logical_arms']:raise ValueError('Arm count differs')
    rows.sort(key=lambda r:c.digest(['step101-fixed-reader-order',r['qid']]))
    return rows,plans

def layout(row,plan,cfg,records):
    q=row['qid'];decisions={};parents={'input_sha256':c.digest(row),'plan_sha256':c.digest(plan)}
    for selected in sorted({tuple(ids) for ids in plan['packets'].values()}):
        ids=list(selected);pid=c.digest(ids);prompt=check_prompt(row,ids)
        key=cache_key(q,'check',prompt)+'__check'
        yield {'kind':'call','key':key,'qid':q,'stage':'check','phase':'fixed_packet_reader8','row':row,
               'source_ids':ids,'prompt':prompt,'parents':dict(parents,packet_sha256=pid)}
        note=records[key];keys=[key];answer=None
        if note['valid']:
            prompt=answer_prompt(row,ids,note['parsed']['check']);key=cache_key(q,'answer',prompt)+'__answer'
            yield {'kind':'call','key':key,'qid':q,'stage':'answer','phase':'fixed_packet_reader8','row':row,
                   'source_ids':ids,'prompt':prompt,'parents':dict(parents,packet_sha256=pid,check=note['record_sha256'])}
            answer=records[key];keys.append(key)
        valid=bool(note['valid'] and answer and answer['valid'])
        decisions[pid]={'ids':ids,'valid':valid,'answer':answer['parsed']['answer'] if valid else None,'record_keys':keys}
    yield {'kind':'contexts','qid':q,'packets':plan['packets'],'decisions':decisions,
           'packet_mapping':{a:c.digest(ids) for a,ids in plan['packets'].items()}}
    yield {'kind':'question_done','qid':q}
