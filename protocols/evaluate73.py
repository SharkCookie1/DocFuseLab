"""Independent fresh-cohort check of frozen72; references never enter selection."""
import evaluate69 as base
score=base.score
prediction_diagnostic=base.prediction_diagnostic


def summarize(root,cfg,records,partials,done,meta):
    result=base.summarize(root,cfg,records,partials,done,meta)
    details=result['details']
    for name in ('union_chain','union_joint'):
        answerable=[d for d in details.values() if d['reference_has_complete_path']]
        conflicts=[d for d in details.values() if d['variant']=='conflict']
        result['methods'][name]={
            'answerable_rows_retained':sum(d['methods'][name]['all_reference_families_retained'] for d in answerable),
            'feasible_answerable_rows_retained':sum(d['methods'][name]['all_reference_families_retained'] for d in answerable if d['all_families_fit_budget']),
            'both_conflict_sides_retained':sum(d['methods'][name]['both_conflict_sides_retained'] for d in conflicts),
            'one_sided_reference_conflicts':sum(d['methods'][name]['one_sided_reference_conflict'] for d in conflicts),
            'by_variant_retained':{v:sum(d['methods'][name]['all_reference_families_retained'] for d in answerable if d['variant']==v) for v in ('clean','counterfactual','conflict')},
            'answerable_source_tokens':sum(d['methods'][name]['source_tokens'] for d in answerable),
            'total_source_tokens':sum(d['methods'][name]['source_tokens'] for d in details.values())}
    result['original_joint_comparisons']=result['comparisons']
    comparisons={}
    for other in ('set_graph_fill','chain','joint','union_chain','rank'):
        comparisons['union_joint_vs_'+other]={
            'primary_answerable':base.comparison(details,'union_joint',other),
            'valid_selector_answerable':base.comparison(details,'union_joint',other,valid_only=True),
            'conflict':base.comparison(details,'union_joint',other,conflict_only=True),
            'feasible_answerable':base.comparison(details,'union_joint',other,feasible_only=True)}
    main=comparisons['union_joint_vs_set_graph_fill']
    conditions={'cohort_complete':len(done)==cfg['input_questions'],
        'positive_primary_net':main['primary_answerable']['net']>0,
        'positive_valid_selector_net':main['valid_selector_answerable']['net']>0,
        'positive_conflict_net':main['conflict']['net']>0,
        'no_clean_counterfactual_loss':not any(d['variant'] in ('clean','counterfactual') and
            d['methods']['set_graph_fill']['all_reference_families_retained'] and
            not d['methods']['union_joint']['all_reference_families_retained'] for d in details.values())}
    result.update(experiment='Step73 fresh natural-text cohort, frozen conservative union candidate',
        primary_candidate='union_joint',primary_comparator='set_graph_fill',comparisons=comparisons,
        original_joint_signal_conditions=result['signal_conditions'],signal_conditions=conditions,
        automatic_selection_signal_observed=all(conditions.values()) if conditions['cohort_complete'] else None,
        union_chain_joint_identical_packets=sum(d['methods']['union_chain']['ids']==d['methods']['union_joint']['ids'] for d in details.values()),
        independent_new_questions=True,independent_human_gold=False,
        frozen_step70_results_changed=False,
        scope='New questions excluded from all staged Step69 candidates and prior57/60/alignment inputs by exact and lexical checks. Frozen72 optimizer; unchanged70 proposal policy and61 prompts. Same graph and ordinary priority for every arm. Assistant source annotations before outputs, not independent human gold. Retention is not generated-answer accuracy. A union_chain tie prevents unique conflict-objective attribution. No automatic main-proof claim even after a small-cohort pass.')
    return result
