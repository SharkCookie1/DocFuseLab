"""Frozen annotated evidence-retention diagnostics. Never feeds the call schedule.

References are assistant annotations, not independent human gold. Unknown rows
have no required family and are excluded from evidence-retention accuracy.
"""
from pathlib import Path
from collections import Counter,defaultdict
import json,math
import method69 as m

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def present(ids,families):
    ids=set(ids)
    return {f['family_id']:any(set(p)<=ids for p in f['chains']) for f in families}

def score(row,ids,ref):
    if len(ids)!=len(set(ids)) or not set(ids)<={u['id'] for u in row['units']}:raise ValueError('Unknown/repeated source IDs')
    z=present(ids,ref['families']);required=len(z);got=sum(z.values())
    return {'ids':ids,'source_tokens':sum(u['tokens'] for u in row['units'] if u['id'] in ids),
            'required_family_count':required,'retained_family_count':got,
            'retained_family_ids':[k for k,v in z.items() if v],
            'all_reference_families_retained':got==required if required else None,
            'both_conflict_sides_retained':all(z[a] and z[b] for a,b in ref['conflicts']) if ref['conflicts'] else None,
            'one_sided_reference_conflict':any(z[a]!=z[b] for a,b in ref['conflicts']),
            'no_reference_path_retained':not got}

def comparison(details,a,b,valid_only=False,conflict_only=False,feasible_only=False):
    wins=losses=ties=0;groups=defaultdict(int);qids=[]
    for q,d in details.items():
        if not d['reference_has_complete_path']:continue
        if valid_only and not d['selector_format_valid']:continue
        if conflict_only and d['variant']!='conflict':continue
        if feasible_only and not d['all_families_fit_budget']:continue
        x=int(d['methods'][a]['all_reference_families_retained'])-int(d['methods'][b]['all_reference_families_retained'])
        wins+=x>0;losses+=x<0;ties+=x==0;groups[d['source_group']]+=x;qids.append(q)
    return {'rows':len(qids),'source_groups':len(groups),'wins':wins,'losses':losses,'ties':ties,'net':wins-losses,
            'group_net':dict(sorted(groups.items())),'scope':'Descriptive curated development sample; no significance or generalization claim.'}

def totals(rs):
    return {'calls':len(rs),'seconds':math.fsum(r['seconds'] for r in rs),
            'input_tokens':sum(r.get('input_tokens',0) for r in rs),
            'output_tokens':sum(r.get('output_tokens',len(r.get('output_token_ids',[]))) for r in rs)}

def prediction_diagnostic(entry,ref):
    pred=entry['prediction'];graph=entry['predicted_graph'];families=ref['families']
    accepted=[pred['witnesses'][i-1] for i in pred['accepted_witness_numbers']]
    active=[p for f in graph['families'] for p in f['chains']]
    proposed=[w['evidence_ids'] for w in pred['witnesses']]
    def available(paths):
        return {f['family_id']:any(any(set(p)<=set(w) for p in f['chains']) for w in paths) for f in families}
    proposal_coverage=available(proposed);accepted_coverage=available([w['evidence_ids'] for w in accepted]);active_coverage=available(active)
    union=set().union(*map(set,active)) if active else set();union_coverage=present(union,families)
    # Map predicted family evidence to reference families; no exact answer strings are needed for source retention.
    mapped={f['family_id']:{k for k,v in available(f['chains']).items() if v} for f in graph['families']}
    reference_conflict_visible=any((a in mapped[x] and b in mapped[y]) or (b in mapped[x] and a in mapped[y])
        for a,b in ref['conflicts'] for x,y in graph['conflicts']) if ref['conflicts'] else None
    expected_answers={m.semantic.normalize(f['answer']) for f in families}
    return {'proposed_witness_count':len(pred['witnesses']),'accepted_witness_count':len(accepted),
        'active_family_count':len(graph['families']),'active_conflict_count':len(graph['conflicts']),
        'inconsistent_graph_discarded':graph['inconsistent_predictions'],
        'proposal_individual_path_reference_coverage':{str(k):v for k,v in proposal_coverage.items()},
        'accepted_individual_path_reference_coverage':{str(k):v for k,v in accepted_coverage.items()},
        'active_individual_path_reference_coverage':{str(k):v for k,v in active_coverage.items()},
        'active_union_reference_coverage':{str(k):v for k,v in union_coverage.items()},
        'all_reference_families_in_individual_accepted_paths':all(accepted_coverage.values()) if families else None,
        'all_reference_families_in_active_individual_paths':all(active_coverage.values()) if families else None,
        'all_reference_families_in_active_union':all(union_coverage.values()) if families else None,
        'reference_conflict_edge_covered_by_predicted_evidence':reference_conflict_visible,
        'false_conflict_on_nonconflict_reference':bool(graph['conflicts']) and not bool(ref['conflicts']),
        'false_accepted_witness_on_unknown':bool(accepted) if not families else None,
        'accepted_exact_reference_answer_strings':sum(m.semantic.normalize(w['answer']) in expected_answers for w in accepted),
        'answer_string_check_scope':'Exact normalized strings only; aliases/paraphrases may be missed. Evidence coverage alone does not certify the proposed answer or semantic relation.'}

def summarize(root,cfg,records,partials,done,meta):
    rows={r['qid']:r for r in read(root/'data/inputs.json')};refs={r['qid']:r for r in read(root/'evaluation/references.json')}
    if set(rows)!=set(refs):raise ValueError('Reference IDs differ')
    details={};budget=cfg['source_budget_tokens']
    for q in done:
        row=rows[q];ref=refs[q];entry=meta['contexts'][q];record=records[q+'__set_graph']
        methods={name:score(row,ids,ref) for name,ids in entry['derived']['contexts'].items()}
        original=methods['set_graph']['source_tokens']
        matched=m.derive(row,entry['predicted_graph'],record['parsed'] if record['valid'] else None,original)
        for name in ('set_graph_fill','chain','joint'):
            methods['matched_'+name]=score(row,matched['contexts'][name],ref)
            if methods['matched_'+name]['source_tokens']>original:raise ValueError('Matched source cap exceeded')
        if any(d['source_tokens']>budget for name,d in methods.items() if name!='full'):raise ValueError('Source cap exceeded')
        if ref['families'] and not methods['full']['all_reference_families_retained']:raise ValueError('Reference path absent from full input')
        details[q]={'source_group':ref['source_group'],'source_id':ref['source_id'],'variant':ref['variant'],
            'reference_has_complete_path':bool(ref['families']),'minimum_complete_family_union_tokens':ref['minimum_complete_union_tokens'],
            'all_families_fit_budget':ref['minimum_complete_union_tokens']<=budget,
            'selector_format_valid':record['valid'],'witness_format_valid':entry['prediction']['witness_schema_valid'],
            'chain_joint_identical':methods['chain']['ids']==methods['joint']['ids'],
            'matched_original_usage_cap':original,'methods':methods,'prediction':prediction_diagnostic(entry,ref)}
    denominators={'all':len(done),'answerable':sum(d['reference_has_complete_path'] for d in details.values()),
        'conflict':sum(d['variant']=='conflict' for d in details.values()),
        'missing_bridge':sum(d['variant']=='missing_bridge' for d in details.values()),
        'feasible_answerable':sum(d['reference_has_complete_path'] and d['all_families_fit_budget'] for d in details.values()),
        'infeasible_answerable':sum(d['reference_has_complete_path'] and not d['all_families_fit_budget'] for d in details.values())}
    methods={}
    for name in m.METHODS:
        answerable=[d for d in details.values() if d['reference_has_complete_path']]
        conflicts=[d for d in details.values() if d['variant']=='conflict']
        methods[name]={'answerable_rows_retained':sum(d['methods'][name]['all_reference_families_retained'] for d in answerable),
            'feasible_answerable_rows_retained':sum(d['methods'][name]['all_reference_families_retained'] for d in answerable if d['all_families_fit_budget']),
            'both_conflict_sides_retained':sum(d['methods'][name]['both_conflict_sides_retained'] for d in conflicts),
            'one_sided_reference_conflicts':sum(d['methods'][name]['one_sided_reference_conflict'] for d in conflicts),
            'by_variant_retained':{v:sum(d['methods'][name]['all_reference_families_retained'] for d in answerable if d['variant']==v) for v in ('clean','counterfactual','conflict')},
            'answerable_source_tokens':sum(d['methods'][name]['source_tokens'] for d in answerable),
            'total_source_tokens':sum(d['methods'][name]['source_tokens'] for d in details.values())}
    comparisons={}
    for other in ('set_graph_fill','set_graph','chain','rank'):
        comparisons['joint_vs_'+other]={
            'primary_answerable':comparison(details,'joint',other),
            'valid_selector_answerable':comparison(details,'joint',other,valid_only=True),
            'conflict':comparison(details,'joint',other,conflict_only=True),
            'feasible_answerable':comparison(details,'joint',other,feasible_only=True)}
    main=comparisons['joint_vs_set_graph_fill'];complete=len(done)==cfg['input_questions']
    losses=sum(d['variant'] in ('clean','counterfactual') and d['methods']['set_graph_fill']['all_reference_families_retained'] and not d['methods']['joint']['all_reference_families_retained'] for d in details.values())
    conditions={'cohort_complete':complete,'positive_primary_net':main['primary_answerable']['net']>0,
        'positive_valid_selector_net':main['valid_selector_answerable']['net']>0,'positive_conflict_net':main['conflict']['net']>0,
        'no_clean_or_counterfactual_loss':losses==0}
    successful=list(records.values());stages=sorted({r['stage'] for r in successful+partials})
    return {'experiment':'Step69 source-reviewed natural-text automatic selection diagnostic',
        'generated_answer_calls':0,'generated_answer_accuracy':None,'main_hypothesis_proven':False,'paper_main_adopted':False,
        'previous_reader_gates_reopened':False,'completed_rows':len(done),'planned_rows':cfg['input_questions'],'cohort_complete':complete,
        'denominators':denominators,'primary_comparator':'set_graph_fill',
        'selector_format_valid':sum(d['selector_format_valid'] for d in details.values()),
        'witness_format_valid':sum(d['witness_format_valid'] for d in details.values()),
        'chain_joint_identical_packets':sum(d['chain_joint_identical'] for d in details.values()),
        'automatic_selection_signal_observed':all(conditions.values()) if complete else None,'signal_conditions':conditions,
        'methods':methods,'comparisons':comparisons,
        'actual_usage_cap_controls':{'joint_vs_filled':comparison(details,'matched_joint','matched_set_graph_fill'),
            'joint_vs_chain':comparison(details,'matched_joint','matched_chain'),
            'scope':'Secondary replay capped at each original short set actual declared spend, not a replacement of the primary256 cap.'},
        'extraction':{
            'answerable_all_families_in_individual_accepted_paths':sum(d['prediction']['all_reference_families_in_individual_accepted_paths'] is True for d in details.values()),
            'answerable_all_families_in_active_individual_paths':sum(d['prediction']['all_reference_families_in_active_individual_paths'] is True for d in details.values()),
            'answerable_all_families_in_active_union':sum(d['prediction']['all_reference_families_in_active_union'] is True for d in details.values()),
            'conflict_rows_with_evidence_covered_predicted_edge':sum(d['prediction']['reference_conflict_edge_covered_by_predicted_evidence'] is True for d in details.values()),
            'nonconflict_rows_with_false_conflict':sum(d['prediction']['false_conflict_on_nonconflict_reference'] for d in details.values()),
            'unknown_rows_with_false_accepted_witness':sum(d['prediction']['false_accepted_witness_on_unknown'] is True for d in details.values()),
            'inconsistent_graph_rows_discarded':sum(d['prediction']['inconsistent_graph_discarded'] for d in details.values())},
        'cost':{'successful':totals(successful),'failed':totals(partials),
            'by_stage':{s:{'successful':totals([r for r in successful if r['stage']==s]),'failed':totals([r for r in partials if r['stage']==s])} for s in stages},
            'cumulative_inference_seconds':math.fsum(r['seconds'] for r in successful+partials),
            'allocation':'Extraction/support/relation/ordinary calls shared by all graph-informed arms; count each actual call once. No final-answer generation or claim of lower total joint compute.'},
        'scope':'Frozen assistant-annotated small natural-text development cohort. Primary score is reference source-path retention, not QA correctness. Full is uncapped. Same source cap does not mean identical actual token spend or total compute. A chain tie blocks attribution to the conflict objective. No independent gold, population, publication or reopened earlier-reader claim.',
        'details':details}
