"""Natural-text automatic graph shared by ordinary, strong-chain and joint selection.

This module has no filesystem or reference access. Semantic prompts are byte-frozen
Step61; structural optimizers are byte-frozen Step60. Predictions remain fallible.
"""
import itertools
import semantic61_frozen as semantic
from core57 import render,pack_order,parse_selection
from method60 import equivalence_groups,select_families
from method62 import selection_prompt as base_selection_prompt
canonical=semantic.canonical
digest=semantic.digest
METHODS=('rank','set_graph','set_graph_fill','chain','joint','full')
witness_prompt=semantic.witness_prompt
support_prompt=semantic.support_prompt
relation_prompt=semantic.relation_prompt

def parse(stage,raw,row):
    return parse_selection(raw,row) if stage=='set_graph' else semantic.parse(stage,raw,row)

def predicted_graph(witnesses,accepted,relations):
    """Only supported witnesses enter. Contradictory relation predictions fail closed.

    Identical normalized answer strings are one family, not a conflict. Explicit
    equivalent relations add aliases. An intra-family conflict invalidates the
    whole predicted graph for ALL methods; raw predictions are never repaired.
    """
    accepted=sorted(accepted)
    equivalents=[(a,b) for a,b in itertools.combinations(accepted,2)
                 if semantic.normalize(witnesses[a-1]['answer'])==semantic.normalize(witnesses[b-1]['answer'])]
    equivalents += [(r['left'],r['right']) for r in relations if r['relation']=='equivalent']
    groups=equivalence_groups(accepted,equivalents)
    conflict=[(r['left'],r['right']) for r in relations if r['relation']=='conflict']
    bad=any(groups[a]==groups[b] for a,b in conflict)
    if bad:
        return {'families':[],'conflicts':[],'inconsistent_predictions':True,
                'status':'equivalence_conflict_collision_shared_empty_graph'}
    fs={}
    for i in accepted:
        g=groups[i];w=witnesses[i-1]
        f=fs.setdefault(g,{'family_id':g,'answers':[],'chains':[],'witness_numbers':[]})
        f['answers'].append(w['answer']);f['chains'].append(sorted(w['evidence_ids']));f['witness_numbers'].append(i)
    for f in fs.values():
        f['answers']=sorted(set(f['answers']));f['chains']=[list(ids) for ids in sorted({tuple(x) for x in f['chains']})]
    return {'families':[fs[k] for k in sorted(fs)],
            'conflicts':[list(p) for p in sorted({tuple(sorted((groups[a],groups[b]))) for a,b in conflict})],
            'inconsistent_predictions':False,'status':'fallible_automatic_prediction'}

def selection_prompt(row,budget,graph):
    base=base_selection_prompt(row,budget,None)
    assert base.endswith('\nJSON selection:')
    return base[:-len('\nJSON selection:')]+'''\nAdditional FALLIBLE source-structure predictions, supplied equally to this ordinary selector and the structural optimizers:
Each family predicts alternative sufficient source-ID sets for an answer. The conflicts array predicts incompatible families. These are automatic model judgments, not reference labels or facts guaranteed to be correct. Check them against the original text. Make your own ordinary selection under the same budget; no particular optimizer or path-closure rule is required.
'''+canonical(graph)+'\nJSON selection:'

def graph_parts(graph):
    return {f['family_id']:[frozenset(p) for p in f['chains']] for f in graph['families']},[tuple(p) for p in graph['conflicts']]

def derive(row,graph,selection,budget):
    rank=row['rank_order'];chosen=selection['selected_ids'] if selection is not None else rank
    priority=list(dict.fromkeys(chosen+rank))
    families,conflicts=graph_parts(graph)
    contexts={'rank':pack_order(row,rank,budget),'set_graph':pack_order(row,chosen,budget),
              'set_graph_fill':pack_order(row,priority,budget),'full':[u['id'] for u in row['units']]}
    diagnostics={}
    for mode in ('chain','joint'):
        diagnostics[mode]=select_families(row,families,conflicts,budget,priority,mode)
        contexts[mode]=diagnostics[mode]['ids']
    for name,ids in contexts.items():
        if name!='full' and sum(u['tokens'] for u in row['units'] if u['id'] in ids)>budget:raise ValueError('Source budget exceeded')
    return {'contexts':{k:contexts[k] for k in METHODS},'diagnostics':diagnostics,
            'ordinary_fill_policy':'Model selected priority then fixed MiniLM rank; no path closure or conflict balancing.',
            'shared_graph_sha256':digest(graph)}
