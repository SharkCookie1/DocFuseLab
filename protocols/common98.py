"""Frozen schedule, strict native-output parsing, and auditable resume."""
from pathlib import Path
import contextlib, datetime, hashlib, json, math, os, threading, time
from core57 import render, parse_answer
from reader59_frozen import answer_prompt
from semantic61_frozen import digest
from method97 import load_inputs

HERE=Path(__file__).resolve().parent
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def stamp():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(8*1024*1024),b''):h.update(part)
    return h.hexdigest()
def save(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def signed(obj,key='record_sha256'):
    out=dict(obj);out[key]=digest(out);return out
def check_signed(obj,key='record_sha256'):
    if obj.get(key)!=digest({k:v for k,v in obj.items() if k!=key}):raise ValueError('Record hash mismatch')

@contextlib.contextmanager
def heartbeat(label):
    event=threading.Event();start=time.monotonic()
    def beat():
        while not event.wait(30):print(f'[RUNNING] {label}; elapsed {time.monotonic()-start:.0f}s',flush=True)
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:yield
    finally:event.set();t.join(timeout=1)

@contextlib.contextmanager
def exclusive(work):
    work=Path(work);work.mkdir(parents=True,exist_ok=True);f=(work/'run.lock').open('a+b')
    if f.tell()==0:f.write(b'0');f.flush()
    f.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        f.close();raise RuntimeError('Another run/export/download is active in this folder.')
    try:yield
    finally:
        try:
            f.seek(0)
            if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
        finally:f.close()

def verify_files(root=HERE):
    root=Path(root);manifest=read(root/'manifest.json');seen=set()
    for e in manifest['files']:
        p=root/e['path']
        if e['path'] in seen or not p.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe manifest')
        seen.add(e['path'])
        if not p.is_file() or p.stat().st_size!=e['bytes'] or sha(p)!=e['sha256']:raise ValueError('Package changed: '+e['path'])
    return digest(manifest)

class TokenAudit:
    def __init__(self,root=HERE):
        from tokenizers import Tokenizer
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        root=Path(root);self.tok=Tokenizer.from_file(str(root/'model_assets/tokenizer.json'))
        template=read(root/'model_assets/tokenizer_config.json')['chat_template']
        self.template=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True).from_string(template)
    def input_ids(self,prompt):
        text=self.template.render(messages=[{'role':'user','content':prompt}],add_generation_prompt=True)
        return self.tok.encode(text,add_special_tokens=False).ids
    def cost(self,text):return len(self.tok.encode(text,add_special_tokens=False).ids)
    def decode(self,ids):return self.tok.decode(ids,skip_special_tokens=True)

def schedule(rows,plans,cfg,audit):
    jobs=[];mapping={}
    for row in rows:
        q=row['qid'];mapping[q]={}
        for ids_tuple in sorted({tuple(v) for v in plans[q]['packets'].values()}):
            ids=list(ids_tuple);prompt=answer_prompt(row,ids,'')
            key=digest([q,prompt]);native=audit.input_ids(prompt)
            source_tokens=audit.cost(render(row,ids))
            if source_tokens>cfg['source_budget_tokens']:raise ValueError('Source budget exceeded')
            if len(native)>cfg['generation']['max_input_tokens']:raise ValueError('Input cap exceeded; no truncation')
            seed=int(digest(['step98-native-thinking-single-seed',q])[:8],16)
            job={'key':key,'qid':q,'source_ids':ids,'prompt':prompt,'seed':seed,
                 'prompt_sha256':digest(prompt),'input_ids_sha256':digest(native),
                 'input_tokens':len(native),'rendered_source_tokens':source_tokens,
                 'row_sha256':digest(row),'plan_sha256':digest(plans[q])}
            jobs.append(job)
            for arm,selected in plans[q]['packets'].items():
                if selected==ids:mapping[q][arm]=key
    if len(jobs)!=cfg['unique_packets'] or len({j['key'] for j in jobs})!=len(jobs):raise ValueError('Unique packet count differs')
    if sum(len(m) for m in mapping.values())!=cfg['logical_arms']:raise ValueError('Logical arm count differs')
    return jobs,mapping

def decode_result(ids,audit,spec):
    """Require a real native thinking end. Never extract a guessed JSON span."""
    end=spec['think_end_token_id'];start=spec['think_start_token_id'];ends=[i for i,t in enumerate(ids) if t==end]
    out={'raw_text':audit.decode(ids),'thinking_tokens':len(ids),'final_tokens':0,
         'final_text':None,'thinking_complete':False,'parsed':None,'valid':False,'parse_error':None}
    if len(ends)!=1:
        out['parse_error']='missing_native_thinking_end' if not ends else 'multiple_native_thinking_ends';return out
    cut=ends[0]+1;tail=ids[cut:]
    out.update(thinking_tokens=cut,final_tokens=len(tail),thinking_complete=True,final_text=audit.decode(tail))
    if start in tail:
        out['parse_error']='thinking_reopened_in_final';return out
    # Only terminal EOS tokens may disappear when decoding; do not hide injected control tokens.
    payload=list(tail)
    if payload and payload[-1] in spec['eos_token_ids']:payload.pop()
    special={i for i,t in audit.tok.get_added_tokens_decoder().items() if t.special}
    if any(t in special for t in payload):out['parse_error']='unexpected_control_token_in_final';return out
    try:out['parsed']=parse_answer(out['final_text']);out['valid']=True
    except (ValueError,TypeError,KeyError) as exc:out['parse_error']=str(exc)
    return out

def metadata(job,identity):
    return dict(identity=identity,job_key=job['key'],**{k:job[k] for k in ('qid','source_ids','seed','prompt_sha256','input_ids_sha256','input_tokens','rendered_source_tokens','row_sha256','plan_sha256')})

def validate_record(job,r,identity,cfg,audit,spec,partial=False):
    check_signed(r,'partial_sha256' if partial else 'record_sha256')
    if any(r.get(k)!=v for k,v in metadata(job,identity).items()):raise ValueError('Cached prompt, seed, budget or identity differs')
    ids=r['output_token_ids']
    if not isinstance(ids,list) or any(type(t) is not int or not 0<=t<audit.tok.get_vocab_size() for t in ids):raise ValueError('Invalid native output IDs')
    if not math.isfinite(r['seconds']) or r['seconds']<0:raise ValueError('Invalid elapsed time')
    if r['output_tokens']!=len(ids) or r['criterion_calls']!=len(ids):raise ValueError('Output accounting differs')
    if len(ids)>cfg['generation']['max_new_tokens']:raise ValueError('Output cap exceeded')
    if partial:
        if r['raw_text']!=audit.decode(ids):raise ValueError('Partial native text differs')
    else:
        if not ids or r['max_new_tokens']!=cfg['generation']['max_new_tokens']:raise ValueError('Missing generation/cap')
        expected=decode_result(ids,audit,spec)
        if any(r.get(k)!=v for k,v in expected.items()):raise ValueError('Output parsing replay differs')

def load_cache(work,jobs,identity,cfg,audit,spec):
    work=Path(work);known={j['key']:j for j in jobs};records={};partials=[]
    for p in sorted((work/'records').glob('*.json')):
        if p.stem not in known:raise ValueError('Unknown cached job')
        r=read(p);validate_record(known[p.stem],r,identity,cfg,audit,spec);records[p.stem]=r
    order=[j['key'] for j in jobs]
    if set(order[:len(records)])!=set(records):raise ValueError('Cache is not a prefix of the frozen schedule')
    permitted=set(order[:min(len(records)+1,len(order))])
    for p in sorted((work/'partials').glob('*.json')):
        r=read(p);key=r.get('job_key')
        if key not in permitted:raise ValueError('Orphan partial attempt')
        validate_record(known[key],r,identity,cfg,audit,spec,partial=True);partials.append(r)
    return records,partials
