"""Natural-text extraction and selection; hash-bound dependent resume, separate scoring."""
from pathlib import Path
import argparse,contextlib,datetime,itertools,json,math,os,sys,threading,time,traceback,zipfile
import method73 as m
from evaluate73 import summarize
HERE=Path(__file__).resolve().parent
WORK=HERE/'_local/run'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def stamp():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
def save(p,o):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp')
    with t.open('w',encoding='utf-8',newline='\n') as f:json.dump(o,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)
@contextlib.contextmanager
def heartbeat(label):
    event=threading.Event();start=time.monotonic()
    def beat():
        while not event.wait(30):print(f'[RUNNING] {label}; {time.monotonic()-start:.0f}s',flush=True)
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:yield
    finally:event.set();t.join(timeout=1)
def verify_files():
    from runtime73 import file_sha
    manifest=read(HERE/'manifest.json');seen=set()
    for e in manifest['files']:
        p=HERE/e['path']
        if e['path'] in seen or not p.resolve().is_relative_to(HERE.resolve()):raise RuntimeError('Unsafe manifest path')
        seen.add(e['path'])
        if not p.is_file() or p.stat().st_size!=e['bytes'] or file_sha(p)!=e['sha256']:raise RuntimeError('Package file changed: '+e['path'])
    return m.digest(manifest)
def call(row,key,stage,prompt,ids,parents,phase):
    return {'kind':'call','qid':row['qid'],'row':row,'key':key,'stage':stage,'prompt':prompt,'source_ids':ids,'parents':parents,'phase':phase}
def load_inputs(root,cfg):
    rows=read(root/'data/inputs.json')
    if len(rows)!=cfg['input_questions'] or len({r['qid'] for r in rows})!=len(rows):raise RuntimeError('Frozen input counts differ')
    for row in rows:
        if set(row)!={'qid','question','options','units','rank_order','rank_scores'}:raise RuntimeError('Unexpected selector input field')
        known=[]
        for u in row['units']:
            if set(u)!={'id','text','tokens'} or type(u['id']) is not int or type(u['tokens']) is not int or u['tokens']<=0:raise RuntimeError('Invalid visible unit')
            known.append(u['id'])
        if len(known)!=len(set(known)) or sorted(row['rank_order'])!=sorted(known):raise RuntimeError('Source/rank IDs differ')
    return {'rows':rows},rows
def make_identity(manifest,cfg,tasks,rows):
    return {'manifest_sha256':manifest,'protocol_sha256':m.digest(cfg),'tasks_sha256':m.digest(tasks),
            'inputs_sha256':m.digest(rows),'schedule_sha256':m.digest([r['qid'] for r in rows])}
def layout(tasks,rows,cfg,records):
    for row in rows:
        q=row['qid'];budget=cfg['source_budget_tokens'];allids=[u['id'] for u in row['units']]
        wk=q+'__witness'
        yield call(row,wk,'witness',m.witness_prompt(row),allids,{},'whole_source_proposals')
        wr=records[wk];whole=wr['parsed']['witnesses'] if wr['valid'] else []
        proposal_parents={wk:wr['record_sha256']};block_outputs=[];block_valid=[]
        blocks=m.source_blocks(row)[:cfg['max_source_blocks']]
        for i,block in enumerate(blocks,1):
            key=q+'__block_witness_'+str(i);ids=[u['id'] for u in block['units']]
            yield call(block,key,'witness',m.witness_prompt(block),ids,dict(proposal_parents),'source_block_proposals')
            r=records[key];proposal_parents[key]=r['record_sha256'];block_valid.append(r['valid'])
            block_outputs.append(r['parsed']['witnesses'] if r['valid'] else [])
        witnesses,added=m.merge_first_witnesses(whole,block_outputs)
        if len(witnesses)>cfg['max_merged_witnesses']:raise RuntimeError('Merged witness cap exceeded')
        parents=dict(proposal_parents);accepted=[];support_valid={}
        for i,w in enumerate(witnesses,1):
            key=q+'__support_'+str(i)
            yield call(row,key,'support',m.support_prompt(row,w),sorted(w['evidence_ids']),
                       dict(proposal_parents),'automatic_support')
            r=records[key];parents[key]=r['record_sha256'];support_valid[str(i)]=r['valid']
            if r['valid'] and r['parsed']['supported']:accepted.append(i)
        relations=[];relation_valid={}
        for a,b in itertools.combinations(accepted,2):
            key=q+'__relation_'+str(a)+'_'+str(b)
            pp=dict(proposal_parents)
            for i in (a,b):pp[q+'__support_'+str(i)]=parents[q+'__support_'+str(i)]
            ids=sorted(set(witnesses[a-1]['evidence_ids']+witnesses[b-1]['evidence_ids']))
            yield call(row,key,'relation',m.relation_prompt(row,witnesses[a-1],witnesses[b-1]),ids,pp,'automatic_relation')
            r=records[key];parents[key]=r['record_sha256'];relation_valid[str(a)+'_'+str(b)]=r['valid']
            if r['valid']:relations.append({'left':a,'right':b,'relation':r['parsed']['relation']})
        graph=m.predicted_graph(witnesses,accepted,relations)
        pp=dict(parents,predicted_graph_sha256=m.digest(graph));key=q+'__set_graph'
        yield call(row,key,'set_graph',m.selection_prompt(row,budget,graph),allids,pp,'same_graph_ordinary_selection')
        r=records[key];derived=m.derive(row,graph,r['parsed'] if r['valid'] else None,budget)
        yield {'kind':'contexts','qid':q,'derived':derived,'predicted_graph':graph,
               'prediction':{'witness_schema_valid':wr['valid'] and all(block_valid),'witnesses':witnesses,
                  'accepted_witness_numbers':accepted,'support_schema_valid':support_valid,
                  'relations':relations,'relation_schema_valid':relation_valid},
               'predicted_graph_sha256':m.digest(graph),'selection_record_sha256':r['record_sha256'],
               'block_witness_schema_valid':block_valid,'new_witness_numbers':added,
               'source_strategy':'unchanged_Step70_first_witness_per_source_plus_whole'}
        yield {'kind':'question_done','qid':q}
def parse_result(spec,raw):
    try:return m.parse(spec['stage'],raw,spec['row']),None
    except (ValueError,TypeError,KeyError) as exc:return None,str(exc)
def metadata(spec,identity):
    return {'job_key':spec['key'],'qid':spec['qid'],'stage':spec['stage'],'phase':spec['phase'],'identity':identity,
            'prompt_sha256':m.digest(spec['prompt']),'parent_hashes':spec['parents'],'evidence_ids':spec['source_ids']}
def check_record(spec,r,identity,cfg):
    if any(r.get(k)!=v for k,v in metadata(spec,identity).items()):raise RuntimeError('Cached prompt/parent/identity differs: '+spec['key'])
    if m.digest({k:v for k,v in r.items() if k!='record_sha256'})!=r.get('record_sha256'):raise RuntimeError('Cached record hash differs')
    cap=cfg['generation'][spec['stage']+'_max_new_tokens']
    if r['max_new_tokens']!=cap or not 0<r['output_tokens']<=cap:raise RuntimeError('Cached output cap differs')
    if len(r['input_ids'])!=r['input_tokens'] or r['input_tokens']>cfg['generation']['max_input_tokens'] or len(r['output_token_ids'])!=r['output_tokens'] or r['criterion_calls']!=r['output_tokens']:raise RuntimeError('Cached token accounting differs')
    if not math.isfinite(r['seconds']) or r['seconds']<0:raise RuntimeError('Cached seconds invalid')
    obj,error=parse_result(spec,r['raw_text'])
    if obj!=r['parsed'] or error!=r['parse_error'] or (obj is not None)!=r['valid']:raise RuntimeError('Cached parsing differs')
def reconstruct(tasks,rows,cfg,records,identity=None,validate=False):
    seen=set();done=[];specs={};contexts={}
    for spec in layout(tasks,rows,cfg,records):
        if spec['kind']=='call':
            key=spec['key'];specs[key]=spec
            if key not in records:break
            if validate:check_record(spec,records[key],identity,cfg)
            seen.add(key)
        elif spec['kind']=='contexts':contexts[spec['qid']]=spec
        elif spec['kind']=='question_done':done.append(spec['qid'])
    if validate and seen!=set(records):raise RuntimeError('Cache is not a prefix of the frozen dependent schedule')
    return done,specs,{'contexts':contexts}
def load_cache(tasks,rows,cfg,identity):
    records={p.stem:read(p) for p in (WORK/'records').glob('*.json')}
    done,specs,gate=reconstruct(tasks,rows,cfg,records,identity,True);partials=[]
    for p in sorted((WORK/'partials').glob('*.json')):
        r=read(p);key=r.get('job_key')
        if key not in specs or any(r.get(k)!=v for k,v in metadata(specs[key],identity).items()):raise RuntimeError('Partial attempt identity differs')
        if m.digest({k:v for k,v in r.items() if k!='partial_sha256'})!=r.get('partial_sha256'):raise RuntimeError('Partial attempt hash differs')
        if not math.isfinite(r['seconds']) or r['seconds']<0:raise RuntimeError('Invalid partial time')
        partials.append(r)
    return records,partials,done,gate
def spent(records,partials):return math.fsum(r['seconds'] for r in list(records.values())+partials)
def export(status,tasks,rows,cfg,records,partials,error=None,export_only=False):
    done,specs,gate=reconstruct(tasks,rows,cfg,records)
    save(WORK/'state.json',{'status':status,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'successful_calls':len(records),'failed_attempts':len(partials),'completed_questions':len(done),
        'planned_questions':len(rows),'error':error,'export_only':export_only,
        'paper_main_adopted':False,'main_hypothesis_proven':False})
    try:
        save(WORK/'summary.json',summarize(HERE,cfg,records,partials,done,gate))
        if (WORK/'evaluation_error.json').exists():(WORK/'evaluation_error.json').unlink()
    except Exception as exc:
        save(WORK/'evaluation_error.json',{'error':repr(exc)});save(WORK/'summary.json',{'evaluation_error':repr(exc),'paper_main_adopted':False})
    path=HERE/('step73_union_review_'+stamp()+'.zip')
    pending=path.with_suffix('.zip.tmp')
    with pending.open('wb') as stream:
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            for e in read(HERE/'manifest.json')['files']:z.write(HERE/e['path'],'source/'+e['path'])
            z.write(HERE/'manifest.json','source/manifest.json')
            for p in sorted(WORK.rglob('*')):
                if p.is_file() and not p.name.endswith('.tmp'):z.write(p,'run/'+p.relative_to(WORK).as_posix())
        stream.flush();os.fsync(stream.fileno())
    os.replace(pending,path)
    print('\n[EXPORT] '+str(path),flush=True);print('[STATUS] '+status+'; upload this ZIP. Natural-text selection diagnostic only; no final-answer generation.',flush=True)
    return path
class BudgetStop(Exception):pass
def run(args):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    mh=verify_files();cfg=read(HERE/'protocol73.json');tasks,rows=load_inputs(HERE,cfg)
    identity=make_identity(mh,cfg,tasks,rows)
    if (WORK/'identity.json').exists() and read(WORK/'identity.json')!=identity:raise RuntimeError('Existing run identity differs; use a fresh extraction')
    records,partials,done,gate=load_cache(tasks,rows,cfg,identity);save(WORK/'identity.json',identity)
    if len(done)==len(rows):export('complete_cached',tasks,rows,cfg,records,partials,export_only=args.export_only);return 'complete_cached'
    if args.export_only:export('partial_export',tasks,rows,cfg,records,partials,export_only=True);return 'partial_export'
    if spent(records,partials)+cfg['generation']['max_seconds_per_call']>cfg['generation']['max_total_inference_seconds']:
        export('budget_stop',tasks,rows,cfg,records,partials,'Cumulative inference cap includes failed attempts');return 'budget_stop'
    start=time.monotonic();status='error';error=None;launch=stamp();started=datetime.datetime.now(datetime.timezone.utc).isoformat();old=len(records);oldp=len(partials)
    try:
        from runtime73 import load,generate,text_inputs
        with heartbeat('verify cached model and load'):scorer=load(Path(args.step50),lambda n,o:save(WORK/n,o))
        tok=scorer.processor.tokenizer
        for row in rows:
            for u in row['units']:
                if len(tok.encode(f"[{u['id']}] {u['text']}\n",add_special_tokens=False))!=u['tokens']:raise RuntimeError('Frozen source token cost differs')
        for spec in layout(tasks,rows,cfg,records):
            if spec['kind']=='contexts':
                row=next(r for r in rows if r['qid']==spec['qid'])
                for arm,ids in spec['derived']['contexts'].items():
                    actual=len(tok.encode(m.render(row,ids),add_special_tokens=False))
                    declared=sum(u['tokens'] for u in row['units'] if u['id'] in set(ids))
                    if arm!='full' and not actual<=declared<=cfg['source_budget_tokens']:raise RuntimeError('Rendered source cap exceeded')
                save(WORK/'contexts'/(spec['qid']+'.json'),spec)
                continue
            if spec['kind']=='question_done':print('[QUESTION COMPLETE] '+spec['qid'],flush=True);continue
            key=spec['key']
            if key in records:continue
            if len(records)>=cfg['max_successful_generation_calls']:raise BudgetStop('Generation call count cap')
            if spent(records,partials)+cfg['generation']['max_seconds_per_call']>cfg['generation']['max_total_inference_seconds']:raise BudgetStop('Cumulative inference cap including failed attempts')
            if time.monotonic()-start>cfg['generation']['max_wall_seconds_per_launch']:raise BudgetStop('Launch wall cap')
            cap=cfg['generation'][spec['stage']+'_max_new_tokens'];text_inputs(scorer.processor,spec['prompt'],cfg['generation']['max_input_tokens'])
            attempt=key+'_'+stamp();attempt_start=time.monotonic();written=False
            def partial(obj):
                nonlocal written
                if written:return
                r=dict(obj,**metadata(spec,identity),attempt_id=attempt);r['partial_sha256']=m.digest(r);save(WORK/'partials'/(attempt+'.json'),r);partials.append(r);written=True
            print(f"[CALL {len(records)+1}; {spec['phase']}; {spec['stage']}] {spec['qid']}",flush=True)
            try:
                with heartbeat(key):r=generate(scorer,spec['prompt'],cap,cfg['generation'],partial)
            except BaseException as exc:
                if not written:partial({'error_type':type(exc).__name__,'raw_text':'','output_token_ids':[],'input_tokens':0,'criterion_calls':0,'seconds':time.monotonic()-attempt_start,'accounting_note':'Elapsed failed attempt time charged.'})
                raise
            r['rendered_source_tokens']=len(tok.encode(m.render(spec['row'],spec['source_ids']),add_special_tokens=False))
            obj,err=parse_result(spec,r['raw_text']);r.update(metadata(spec,identity));r.update(parsed=obj,valid=obj is not None,parse_error=err);r['record_sha256']=m.digest(r)
            save(WORK/'records'/(key+'.json'),r);records[key]=r
            print(f"[SAVED] valid={r['valid']}; tokens={r['input_tokens']}+{r['output_tokens']}; seconds={r['seconds']:.1f}",flush=True)
        else:status='complete'
    except BudgetStop as exc:status='budget_stop';error=str(exc)
    except KeyboardInterrupt:status='interrupted';error='Interrupted; completed records remain cached.'
    except BaseException as exc:
        status='error';error=type(exc).__name__+': '+str(exc);save(WORK/'error.json',{'error':error,'traceback':traceback.format_exc()})
    finally:
        save(WORK/'launches'/(launch+'.json'),{'started_utc':started,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'wall_seconds_including_model_loading':time.monotonic()-start,
             'status':status,'new_successful_calls':len(records)-old,'new_failed_attempts':len(partials)-oldp})
        export(status,tasks,rows,cfg,records,partials,error)
    return status
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--step50',default=r'C:\DocFuseLab\step50_8b_ready\step50_8b');ap.add_argument('--export-only',action='store_true')
    try:result=run(ap.parse_args())
    except Exception as exc:print('[STOP] '+type(exc).__name__+': '+str(exc),flush=True);sys.exit(1)
    if result=='error':sys.exit(1)
