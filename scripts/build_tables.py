"""Rebuild manuscript tables from the retained experiment summaries (no inference)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((ROOT / 'data' / (name + '.json')).read_text(encoding='utf-8'))
def write(name, text):
    (ROOT / 'tables' / (name + '.tex')).write_text(text + '\n', encoding='utf-8')
def table(caption, label, spec, header, rows):
    return '\n'.join([r'\begin{table}[pos=H]', r'\caption{' + caption + r'}\label{tab:' + label + '}',
        r'\centering\small', r'\setlength{\tabcolsep}{6pt}', r'\begin{tabular}{' + spec + '}',
        r'\toprule', header + r' \\', r'\midrule', *rows, r'\bottomrule', r'\end{tabular}',
        r'\end{table}'])

NAMES = {'plain_set':'Plain set', 'set_graph':'Same-graph set', 'strong_chain':'Chain closure',
         'joint':'Joint preservation', 'mmr':'MMR', 'setr_iri_budget':'SetR-IRI (adapted)'}
ORDER = ['plain_set','setr_iri_budget','mmr','set_graph','strong_chain','joint']
S = read('summary106')
C, O = S['groups']['conflict']['arms'], S['groups']['clean']['arms']
assert C['joint']['correct'] == 46 and C['plain_set']['correct'] == 30
assert O['joint']['correct'] == 67 and S['complete']
rows=[]
for a in ORDER:
    c,o=C[a],O[a]
    rows.append(f"{NAMES[a]} & {c['correct']:.0f}/200 & {100*c['accuracy']:.1f} & {100*o['accuracy']:.1f} & {100*o['mean_f1']:.1f} & {o['false_conflicts']}" + r' \\')
write('confirmation',table('Confirmation results at a 256-token source budget.',
 'confirmation','lrrrrr',r'Selector & Correct conflicts & Conflict (\%) & EM (\%) & F1 (\%) & False conflicts',rows))

D=read('baseline101'); P=read('baseline103')
D4=D['baseline4b_groups']['all350']['tables']
D8=P['groups']['all350']['tables8b']
rows=[]
for a in ORDER:
    c4=D4['hotpot_conflict'].get(a); o4=D4['hotpot_clean'].get(a)
    c8=D8['hotpot_conflict'][a];o8=D8['hotpot_clean'][a]
    cells=[NAMES[a],f"{100*c4['em']:.1f}" if c4 else '--', f"{100*o4['em']:.1f}" if o4 else '--',f"{100*c8['em']:.1f}",f"{100*o8['em']:.1f}",f"{100*o8['f1']:.1f}"]
    rows.append(' & '.join(cells)+r' \\')
write('development',table('Development results with two reader configurations.',
 'development','lrrrrr',r'& \multicolumn{2}{c}{4B reader} & \multicolumn{3}{c}{8B reader} \\ \cmidrule(lr){2-3}\cmidrule(lr){4-6} Selector & Conflict (\%) & EM (\%) & Conflict (\%) & EM (\%) & F1 (\%)',rows))

T=read('conflict_types')['groups']
rows=[]
labels=[('entity_category_relation','Entity, category, or relation'),('non_temporal_quantity_or_rank','Non-temporal quantity or rank'),('all_temporal','Temporal attribute or comparison'),('answer_type_unclear','Unresolved answer type'),('all150','All questions')]
for key,label in labels:
    g=T[key];r4=g['readers']['4B']['correct'];r8=g['readers']['8B']['correct']
    rows.append(f"{label} & {g['n']} & {r4['plain_set']:.0f} & {r4['joint']:.0f} & {r8['plain_set']:.0f} & {r8['joint']:.0f}"+r' \\')
write('types',table('Conflict identification by requested answer attribute.',
 'types','lrrrrr',r'& & \multicolumn{2}{c}{4B reader} & \multicolumn{2}{c}{8B reader} \\ \cmidrule(lr){3-4}\cmidrule(lr){5-6} Attribute & $n$ & Plain set & Joint & Plain set & Joint',rows))

rows=[]
for a,label in [('joint','Joint preservation'),('full_context','Full context'),('annotation_reference','Annotation reference')]:
    c,o=C[a],O[a]
    rows.append(f"{label} & {c['correct']:.0f}/200 & {c['mean_source_tokens']:.1f} & {o['correct']:.0f}/100 & {o['mean_source_tokens']:.1f}"+r' \\')
write('reference',table('Reader outcomes under three source-input conditions.',
 'reference','lrrrr',r'& \multicolumn{2}{c}{Conflict questions} & \multicolumn{2}{c}{Ordinary questions} \\ \cmidrule(lr){2-3}\cmidrule(lr){4-5} Input condition & Correct & Mean tokens & Correct & Mean tokens',rows))

rows=[]
comparisons=[('Confirmation, 8B','Plain set',read('summary105')['primary'],'source_cluster_bootstrap95'),
 ('Confirmation, 8B','SetR-IRI',S['groups']['conflict']['supplemental_joint_vs_setr'],'bootstrap95'),
 ('Development, 4B','Plain set',D['baseline4b_groups']['all350']['paired_comparisons']['hotpot_conflict']['joint_vs_plain_set'],'percentile95'),
 ('Development, 8B','Plain set',D['groups']['all350']['selector_comparisons8b']['hotpot_conflict']['joint_vs_plain_set'],'percentile95'),
 ('Development, 8B','SetR-IRI',P['groups']['all350']['selector_comparisons8b']['hotpot_conflict']['joint_vs_setr_iri_budget'],'percentile95')]
for cohort,comp,r,ik in comparisons:
    delta=r.get('difference',r.get('delta'));lo,hi=r[ik]
    rows.append(f"{cohort} & {comp} & {r['wins']}/{r['losses']}/{r['ties']} & {100*delta:.1f} & [{100*lo:.1f}, {100*hi:.1f}]"+r' \\')
write('paired',table('Paired differences in conflict identification.',
 'paired','llrrr',r'Cohort and reader & Comparator & Wins/losses/ties & Difference & 95\% interval',rows))

B=read('baseline102');rows=[]
for b in [128,256,512]:
    for a in ['plain_set','set_graph','strong_chain','joint']:
        c=B['groups'][str(b)]['tables']['hotpot_conflict'][a];o=B['groups'][str(b)]['tables']['hotpot_clean'][a]
        rows.append(f"{b} & {NAMES[a]} & {c['correct']:.0f}/146 & {c['automatic_graph_both_sides_retained_questions']} & {100*o['em']:.1f} & {o['conflict_count']}"+r' \\')
write('budget',table('Results across source-token budgets.',
 'budget','rlrrrr',r'Budget & Selector & Correct conflicts & Both sides & Ordinary EM (\%) & False conflicts',rows))

rows=[]
for a in ORDER:
    vals=[S['groups'][g]['arms'][a]['logical_pipeline_llm_cost'] for g in ['conflict','clean']]
    z={k:sum(v[k] for v in vals) for k in vals[0]}
    rows.append(f"{NAMES[a]} & {z['calls']:,} & {z['input_tokens']/1e6:.3f} & {z['output_tokens']/1e6:.3f} & {z['seconds']/3600:.2f}"+r' \\')
write('cost',table('Model computation across selection methods.',
 'cost','lrrrr',r'Selector & Calls & Input tokens (M) & Output tokens (M) & Model time (h)',rows))

R=read('summary106c')['groups'];rows=[]
for g,label in [('conflict','Conflict'),('clean','Ordinary')]:
    r=R[g];p=r['prior_correct_same_questions']
    rows.append(f"{label} & {r['n']} & {p['plain_set']:.0f} & {p['joint']:.0f} & {p['setr_iri_budget']:.0f} & {p['full_context']:.0f} & {r['reference_correct']:.0f}"+r' \\')
write('source_reference',table('Reader outcomes on inspected reference cases.',
 'source-reference','lrrrrrr',r'Group & $n$ & Plain set & Joint & SetR-IRI & Full context & Reference',rows))
print('Built 8 data-derived tables.')
