"""Frozen union candidate; all methods see the same fallible automatic graph."""
import method69 as base
import method70 as sources
from method72_frozen import select as union_select

canonical=base.canonical
digest=base.digest
render=base.render
parse=base.parse
semantic=base.semantic
predicted_graph=base.predicted_graph
selection_prompt=base.selection_prompt
witness_prompt=base.witness_prompt
support_prompt=base.support_prompt
relation_prompt=base.relation_prompt
graph_parts=base.graph_parts
source_blocks=sources.source_blocks
merge_first_witnesses=sources.merge_first_witnesses
METHODS=('rank','set_graph','set_graph_fill','chain','joint','union_chain','union_joint','full')


def derive(row,graph,selection,budget):
    result=base.derive(row,graph,selection,budget)
    for mode in ('chain','joint'):
        d=union_select(row,graph,selection,budget,mode)
        result['diagnostics']['union_'+mode]=d
        result['contexts']['union_'+mode]=d['ids']
    result['contexts']={name:result['contexts'][name] for name in METHODS}
    return result
