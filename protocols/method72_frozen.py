"""One label-blind conservative alternative-chain ablation; no I/O."""
from method60 import select_families


def select(row, graph, selection, budget, mode):
    if mode not in ('chain', 'joint'):
        raise ValueError('Unknown mode')
    families = {f['family_id']: [frozenset().union(*(frozenset(w) for w in f['chains']))]
                for f in graph['families']}
    priority = list(dict.fromkeys((selection['selected_ids'] if selection else []) + row['rank_order']))
    return select_families(row, families, [tuple(p) for p in graph['conflicts']], budget, priority, mode)
