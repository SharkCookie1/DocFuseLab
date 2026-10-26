"""Label-blind evidence packing and strict response contracts."""
import itertools
import json
import math


def strict_json(raw):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    obj=json.loads(raw,object_pairs_hook=unique,
                   parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if not isinstance(obj,dict): raise ValueError('Expected JSON object')
    return obj


def root_boundary(text):
    start=len(text)-len(text.lstrip())
    if start==len(text): return 'incomplete'
    if text[start]!='{': return 'invalid_prefix'
    stack=[];quoted=False;escaped=False
    for ch in text[start:]:
        if quoted:
            if escaped: escaped=False
            elif ch=='\\': escaped=True
            elif ch=='"': quoted=False
            continue
        if ch=='"': quoted=True
        elif ch in '{[': stack.append(ch)
        elif ch in '}]':
            if not stack or (stack[-1],ch) not in (('{','}'),('[',']')): return 'invalid_structure'
            stack.pop()
            if not stack:return 'closed'
    return 'incomplete'


def check_ids(ids,known,maximum=48,empty=False):
    if not isinstance(ids,list) or not (0 if empty else 1)<=len(ids)<=maximum:
        raise ValueError('Invalid ID list size')
    if any(type(i) is not int or i not in known for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('Unknown, repeated, or noninteger ID')
    return ids


def parse_selection(raw,row):
    o=strict_json(raw)
    if set(o)!={'needs','selected_ids'}:raise ValueError('Selection keys differ')
    if not isinstance(o['needs'],list) or not 1<=len(o['needs'])<=5 or any(not isinstance(s,str) or not s.strip() or len(s)>180 for s in o['needs']):
        raise ValueError('Invalid needs')
    check_ids(o['selected_ids'],{u['id'] for u in row['units']},empty=True)
    return o


def parse_ledger(raw,row):
    o=strict_json(raw);known={u['id'] for u in row['units']}
    if set(o)!={'support_sets','conflict_pairs'}:raise ValueError('Ledger keys differ')
    if not isinstance(o['support_sets'],list) or len(o['support_sets'])>4:raise ValueError('Too many support sets')
    seen=set()
    for s in o['support_sets']:
        check_ids(s,known,maximum=6)
        key=tuple(sorted(s))
        if key in seen:raise ValueError('Duplicate support set')
        seen.add(key)
    if not isinstance(o['conflict_pairs'],list) or len(o['conflict_pairs'])>3:raise ValueError('Too many conflict pairs')
    seen=set()
    for p in o['conflict_pairs']:
        if not isinstance(p,dict) or set(p)!={'left','right'}:raise ValueError('Conflict pair keys differ')
        for side in ('left','right'):check_ids(p[side],known,maximum=6)
        if set(p['left'])==set(p['right']):raise ValueError('Identical witnesses cannot conflict')
        key=tuple(sorted((tuple(sorted(p['left'])),tuple(sorted(p['right'])))))
        if key in seen:raise ValueError('Duplicate conflict pair')
        seen.add(key)
    return o


def parse_answer(raw,row=None):
    o=strict_json(raw)
    if set(o)!={'answer'} or not isinstance(o['answer'],str) or not o['answer'].strip() or len(o['answer'])>600:
        raise ValueError('Invalid answer object')
    return o


def render(row,ids,costs=False):
    selected=set(ids)
    return '\n'.join((f"[{u['id']}; cost={u['tokens']}] " if costs else f"[{u['id']}] ")+u['text']
                     for u in row['units'] if u['id'] in selected)


def pack_order(row,order,budget):
    by={u['id']:u for u in row['units']};selected=[];used=0
    for i in order:
        if i not in by:raise ValueError('Unknown pack ID')
        if i not in selected and used+by[i]['tokens']<=budget:
            selected.append(i);used+=by[i]['tokens']
    return sorted(selected)


def choose_bundles(row,ledger,budget,guard):
    """Enumerate witness unions (<=1024), then greedily fill: not a global set optimum.

    Guard forbids retaining exactly one complete witness of a predicted conflict.
    This symbolic condition is conditional on the extracted witnesses being valid.
    It does not establish semantic faithfulness by itself.
    """
    by={u['id']:u for u in row['units']};ranking=row['rank_order']
    supports=[frozenset(s) for s in ledger['support_sets']]
    pairs=[(frozenset(p['left']),frozenset(p['right'])) for p in ledger['conflict_pairs']]
    atoms=list(dict.fromkeys(supports+[s for p in pairs for s in p]))
    if len(atoms)>10:raise ValueError('Enumeration cap exceeded')
    def cost(s):return sum(by[i]['tokens'] for i in s)
    def feasible(s):return cost(s)<=budget and (not guard or all((a<=s)==(b<=s) for a,b in pairs))
    rr={i:1.0/(k+1) for k,i in enumerate(ranking)}
    def score(s):
        return ((sum(a<=s and b<=s for a,b in pairs) if guard else 0),
                int(any(a<=s for a in supports)),sum(rr[i] for i in s),-cost(s),
                tuple(-i for i in sorted(s)))
    seeds={frozenset()}
    for a in atoms:seeds|={s|a for s in tuple(seeds) if cost(s|a)<=budget}
    candidates=set()
    for seed in seeds:
        if not feasible(seed):continue
        s=set(seed)
        for i in ranking:
            if i not in s and feasible(s|{i}):s.add(i)
        candidates.add(frozenset(s))
    best=max(candidates,key=score)
    return {'ids':sorted(best),'tokens':cost(best),'seed_count':len(seeds),
            'candidate_count':len(candidates),'complete_support_sets':sum(s<=best for s in supports),
            'retained_conflict_pairs':sum(a<=best and b<=best for a,b in pairs),
            'one_sided_conflict_pairs':sum((a<=best)!=(b<=best) for a,b in pairs),
            'guard':guard}


def derived_contexts(row,selection,ledger,budget):
    ranked=pack_order(row,row['rank_order'],budget)
    selected=(pack_order(row,selection['selected_ids']+row['rank_order'],budget)
              if selection is not None else ranked)
    if ledger is None:
        a={'ids':ranked,'fallback':'invalid_ledger'};g=dict(a)
    else:
        a=choose_bundles(row,ledger,budget,False);g=choose_bundles(row,ledger,budget,True)
    return {'rank':ranked,'iri':selected,'bundle':a['ids'],'guard':g['ids'],
            'diagnostic':{'bundle':a,'guard':g,'iri_fallback':selection is None,
                          'guard_changes_context':a['ids']!=g['ids']}}
