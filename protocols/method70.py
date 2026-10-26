"""One development change: add the first witness from each explicit source block.

No prompts, binary support rules or selection optimizers are changed. Same graph
and priorities for every graph-informed selector. No reference access here.
"""
import method69 as base
canonical=base.canonical
digest=base.digest
render=base.render
parse=base.parse
predicted_graph=base.predicted_graph
derive=base.derive
selection_prompt=base.selection_prompt
witness_prompt=base.witness_prompt
support_prompt=base.support_prompt
relation_prompt=base.relation_prompt
METHODS=base.METHODS

def source_blocks(row):
    """Partition only on existing literal Document: boundaries, preserving IDs/text.

    A leading prefix belongs to the first block. Paragraph/title markers are not
    extra documents. Sources lacking at least two boundaries are not subdivided.
    """
    starts=[i for i,u in enumerate(row['units']) if u['text'].startswith('Document:')]
    if len(starts)<2:return []
    bounds=[0]+starts[1:]+[len(row['units'])];blocks=[]
    for a,b in zip(bounds,bounds[1:]):
        us=row['units'][a:b];known={u['id'] for u in us}
        rr=[(i,s) for i,s in zip(row['rank_order'],row['rank_scores']) if i in known]
        blocks.append({'qid':row['qid'],'question':row['question'],'options':row['options'],
                       'units':us,'rank_order':[i for i,s in rr],'rank_scores':[s for i,s in rr]})
    return blocks

def signature(w):return base.semantic.normalize(w['answer']),tuple(sorted(w['evidence_ids']))

def merge_first_witnesses(whole,blocks):
    """Keep all whole-input proposals, then the first valid proposal per block.

    No answer-dependent choosing among block alternatives, no replacement after
    support rejection. Unused block outputs remain available in raw records.
    """
    result=list(whole);seen={signature(w) for w in result};added=[]
    for block in blocks:
        if block:
            w=block[0]
            if signature(w) not in seen:
                seen.add(signature(w));result.append(w);added.append(len(result))
    return result,added

def lookup_key(q,stage,prompt,ids):return digest([q,stage,digest(prompt),ids])

def parent_index(records):
    out={}
    for key,r in sorted(records.items()):
        k=digest([r['qid'],r['stage'],r['prompt_sha256'],r['evidence_ids']])
        if k in out:raise ValueError('Ambiguous exact parent prompt cache')
        out[k]=r
    return out
