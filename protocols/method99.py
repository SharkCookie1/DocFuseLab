"""One frozen intervention: native-thinking whole-source witness proposal.

This module reads inference inputs only. Labels and previous QA answers do not
participate in proposal, graph construction, packet choice or the call order.
"""
from pathlib import Path
import math
import common98 as c
import method73 as frozen
from core57 import render, pack_order, parse_selection, parse_answer
from prompts57 import iri_prompt
from reader59_frozen import answer_prompt

ARMS=('plain_set','set_graph','strong_chain','joint')

def load_inputs(root,cfg):
    rows=c.read(Path(root)/'data/inputs.json');plans=c.read(Path(root)/'data/plans.json')
    if len(rows)!=cfg['input_questions'] or set(plans)!={r['qid'] for r in rows}:raise ValueError('Input count/IDs differ')
    if len({r['qid'] for r in rows})!=len(rows):raise ValueError('Duplicate question')
    for r in rows:
        if set(r)!={'qid','question','options','units','rank_order','rank_scores'}:raise ValueError('Unexpected inference field')
        ids=[u['id'] for u in r['units']]
        if len(ids)!=len(set(ids)) or sorted(ids)!=sorted(r['rank_order']):raise ValueError('Invalid IDs/rank')
        if len(r['rank_scores'])!=len(ids) or any(not math.isfinite(x) for x in r['rank_scores']):raise ValueError('Invalid scores')
        for u in r['units']:
            if set(u)!={'id','text','tokens'} or type(u['tokens']) is not int or u['tokens']<=0:raise ValueError('Invalid source unit')
        p=plans[r['qid']];keep=p['candidate_ids']
        if set(p)!={'candidate_ids','candidate_cost'} or keep!=sorted(set(keep)) or not keep or not set(keep)<=set(ids):raise ValueError('Invalid candidate pool')
        if p['candidate_cost']!=sum(u['tokens'] for u in r['units'] if u['id'] in keep):raise ValueError('Candidate cost differs')
    if sum(p['candidate_cost']>cfg['source_budget_tokens'] for p in plans.values())!=cfg['native_proposal_questions']:raise ValueError('Proposal count differs')
    rows.sort(key=lambda r:c.digest(['step99-frozen-order',r['qid']]))
    return rows,plans

def restricted(row,plan):
    keep=set(plan['candidate_ids']);scores=dict(zip(row['rank_order'],row['rank_scores']))
    rr=dict(row,units=[dict(u) for u in row['units'] if u['id'] in keep],rank_order=[i for i in row['rank_order'] if i in keep])
    rr['rank_scores']=[scores[i] for i in rr['rank_order']]
    return rr

def native_job(row,ids,stage,parents,audit,cfg):
    if stage not in ('proposal','reader'):raise ValueError('Unknown native stage')
    ids=sorted(ids)
    if stage=='proposal':
        if ids!=[u['id'] for u in row['units']]:raise ValueError('Whole-source proposal lost input')
        prompt=frozen.witness_prompt(row);seed=int(c.digest(['step99-whole-witness',row['qid']])[:8],16)
    else:
        prompt=answer_prompt(row,ids,'');seed=int(c.digest(['step98-native-thinking-single-seed',row['qid']])[:8],16)
    native=audit.input_ids(prompt);source=audit.cost(render(row,ids))
    if len(native)>cfg['native_generation']['max_input_tokens']:raise ValueError('Input cap exceeded; no truncation')
    if stage=='reader' and source>cfg['source_budget_tokens']:raise ValueError('Source cap exceeded')
    return {'key':c.digest([row['qid'],stage,prompt]),'qid':row['qid'],'stage':stage,'row':row,'source_ids':ids,
        'prompt':prompt,'seed':seed,'parents':parents,'prompt_sha256':c.digest(prompt),
        'input_ids_sha256':c.digest(native),'input_tokens':len(native),'rendered_source_tokens':source,
        'row_sha256':c.digest(row),'plan_sha256':c.digest(parents)}

def proposal_jobs(rows,plans,cfg,audit):
    return [native_job(restricted(r,plans[r['qid']]),plans[r['qid']]['candidate_ids'],'proposal',
            {'candidate_plan':c.digest(plans[r['qid']])},audit,cfg)
        for r in rows if plans[r['qid']]['candidate_cost']>cfg['source_budget_tokens']]

def parse_old(stage,raw,row):
    return parse_selection(raw,row) if stage=='set_plain' else frozen.parse(stage,raw,row)

def graph_events(row,plan,cfg,proposal,records):
    """Delegate the entire graph/optimizer pipeline to the frozen Step73 code."""
    rr=restricted(row,plan);q=row['qid'];budget=cfg['source_budget_tokens']
    if plan['candidate_cost']<=budget:
        yield {'kind':'contexts','qid':q,'packets':{a:list(plan['candidate_ids']) for a in ARMS},
            'all_fit':True,'candidate_cost':plan['candidate_cost'],'predicted_graph':{'families':[],'conflicts':[],'status':'all_candidates_fit'},
            'prediction':None,'diagnostics':{},'graph_record_keys':[],'plain_record_key':None,'proposal_key':None}
        return
    if proposal is None:raise ValueError('Missing whole-source proposal')
    from selection_run73_frozen import layout
    # Only this one frozen call is substituted; all dependent call specifications
    # and their parent hashes still come from the original implementation.
    wrapped=dict(records);whole_key=q+'__witness';wrapped[whole_key]=proposal
    entry=None;keys=[]
    generator=layout({'rows':[rr]},[rr],cfg,wrapped)
    for event in generator:
        if event['kind']=='call':
            key=event['key']
            if key==whole_key:
                if event['prompt']!=frozen.witness_prompt(rr):raise ValueError('Frozen witness prompt changed')
                continue
            yield event
            if key not in records:raise ValueError('Graph caller did not supply record')
            wrapped[key]=records[key];keys.append(key)
        elif event['kind']=='contexts':entry=event
    if entry is None:raise ValueError('Frozen graph did not complete')
    pk=q+'__set_plain'
    yield {'kind':'call','qid':q,'row':rr,'key':pk,'stage':'set_plain','prompt':iri_prompt(rr,budget),
        'source_ids':plan['candidate_ids'],'parents':{'row_sha256':c.digest(rr)},'phase':'independent_plain_set'}
    pr=records[pk];priority=(pr['parsed']['selected_ids'] if pr['valid'] else [])+rr['rank_order']
    d=entry['derived'];packets={'plain_set':pack_order(rr,priority,budget),'set_graph':d['contexts']['set_graph_fill'],
        'strong_chain':d['contexts']['union_chain'],'joint':d['contexts']['union_joint']}
    for ids in packets.values():
        if ids!=sorted(set(ids)) or not set(ids)<=set(plan['candidate_ids']):raise ValueError('Invalid selected packet')
        if sum(u['tokens'] for u in rr['units'] if u['id'] in ids)>budget:raise ValueError('Selected packet exceeds budget')
    yield {'kind':'contexts','qid':q,'packets':packets,'all_fit':False,'candidate_cost':plan['candidate_cost'],
        'predicted_graph':entry['predicted_graph'],'prediction':entry['prediction'],'diagnostics':d['diagnostics'],
        'graph_record_keys':keys,'plain_record_key':pk,'proposal_key':proposal['job_key']}

def reader_jobs(rows,contexts,cfg,audit):
    jobs=[];mapping={}
    for row in rows:
        q=row['qid']
        if q not in contexts:continue
        ctx=contexts[q];mapping[q]={}
        for ids in sorted({tuple(v) for v in ctx['packets'].values()}):
            j=native_job(row,list(ids),'reader',{'context_sha256':c.digest(ctx)},audit,cfg);jobs.append(j)
            for a,selected in ctx['packets'].items():
                if selected==list(ids):mapping[q][a]=j['key']
    return jobs,mapping

def decode_native(ids,audit,spec,job):
    # Identical native-frame requirements to Step98, with the appropriate frozen
    # final JSON schema (witnesses versus answer). No span extraction or repair.
    ends=[i for i,t in enumerate(ids) if t==spec['think_end_token_id']]
    out={'raw_text':audit.decode(ids),'thinking_tokens':len(ids),'final_tokens':0,'final_text':None,
        'thinking_complete':False,'parsed':None,'valid':False,'parse_error':None}
    if len(ends)!=1:
        out['parse_error']='missing_native_thinking_end' if not ends else 'multiple_native_thinking_ends';return out
    cut=ends[0]+1;tail=ids[cut:]
    out.update(thinking_tokens=cut,final_tokens=len(tail),thinking_complete=True,final_text=audit.decode(tail))
    if spec['think_start_token_id'] in tail:out['parse_error']='thinking_reopened_in_final';return out
    payload=list(tail)
    if payload and payload[-1] in spec['eos_token_ids']:payload.pop()
    special={i for i,t in audit.tok.get_added_tokens_decoder().items() if t.special}
    if any(t in special for t in payload):out['parse_error']='unexpected_control_token_in_final';return out
    try:
        out['parsed']=parse_answer(out['final_text']) if job['stage']=='reader' else frozen.parse('witness',out['final_text'],job['row'])
        out['valid']=True
    except (ValueError,TypeError,KeyError) as e:out['parse_error']=str(e)
    return out
