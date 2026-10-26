"""Frozen SetR supplement and separate, explicitly privileged reader diagnostics."""
from pathlib import Path
import math
import common98 as c
from core57 import render, pack_order
from reader59_frozen import check_prompt, answer_prompt, parse_stage
from method103 import setr_prompt, parse, cache_key, restricted, check_packet

ARMS = ('setr_iri_budget', 'full_context', 'annotation_reference')
REFERENCE_ARMS = ('plain_set', 'set_graph', 'strong_chain', 'joint', 'mmr')


def load_inputs(root, cfg, review=None):
    root = Path(root)
    rows = c.read(root/'data/inputs.json')
    plans = c.read(root/'data/plans.json')
    templates = c.read(root/'data/setr_prompts.json')
    reference = c.read(root/'data/reference_packets.json')
    if len(rows) != cfg['input_questions'] or len({r['qid'] for r in rows}) != len(rows):
        raise ValueError('Frozen question count differs')
    if set(plans) != {r['qid'] for r in rows} or set(reference) != set(plans):
        raise ValueError('Frozen question identities differ')
    for row in rows:
        if set(row) != {'qid','question','options','units','rank_order','rank_scores'}:
            raise ValueError('Unexpected field in inference input')
        ids = [u['id'] for u in row['units']]
        if ids != sorted(set(ids)) or sorted(row['rank_order']) != ids:
            raise ValueError('Candidate/rank identities differ')
        if len(row['rank_scores']) != len(ids) or not all(math.isfinite(x) for x in row['rank_scores']):
            raise ValueError('Invalid frozen ranking')
        for u in row['units']:
            if set(u) != {'id','text','tokens'} or type(u['id']) is not int or type(u['tokens']) is not int or u['tokens'] <= 0:
                raise ValueError('Invalid original source unit')
        p = plans[row['qid']]
        if set(p) != {'candidate_ids','candidate_cost'} or p['candidate_ids'] != ids:
            raise ValueError('The supplement must use every frozen candidate')
        if p['candidate_cost'] != sum(u['tokens'] for u in row['units']):
            raise ValueError('Candidate cost differs')
        check_packet(row, reference[row['qid']]['ids'], ids, p['candidate_cost'])
        p.update(mode='base', setr_templates=templates, reference_ids=reference[row['qid']]['ids'])
    if review is not None:
        accepted = validate_review(review, rows)
        historical = c.read(root/'history/packets105.json')
        for entry in review['entries']:
            known_packets = {c.digest(ids) for ids in historical[entry['qid']].values()}
            for pid, judgement in entry.get('packet_assessments',{}).items():
                if pid not in known_packets or judgement not in ('complete','incomplete','uncertain'):
                    raise ValueError('Unknown blinded historical packet or assessment')
        rows = [r for r in rows if r['qid'] in accepted]
        if not rows:
            raise ValueError('No complete, author-reviewed packets were submitted')
        plans = {r['qid']:dict(plans[r['qid']], mode='reviewed', review_entry=accepted[r['qid']]) for r in rows}
    rows.sort(key=lambda r:c.digest(['step106-fixed-question-order',r['qid']]))
    return rows, plans


def validate_review(review, rows):
    if review.get('schema') != 'step106-human-review-v1':
        raise ValueError('Unknown review format')
    if review.get('inputs_sha256') != c.digest(rows):
        raise ValueError('Review belongs to a different frozen cohort')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('A real reviewer name is required; automatic review is not human verification')
    if review.get('human_attestation') is not True:
        raise ValueError('Human review attestation is missing')
    byq = {r['qid']:r for r in rows}; accepted = {}; seen = set()
    if not isinstance(review.get('entries'), list):
        raise ValueError('Review entries must be a list')
    for entry in review['entries']:
        q = entry.get('qid')
        if q not in byq or q in seen:
            raise ValueError('Unknown or duplicate review question')
        seen.add(q)
        if entry.get('context_judgement') not in ('conflict','answerable','uncertain','invalid'):
            raise ValueError('Invalid source judgement')
        if type(entry.get('complete_packet')) is not bool or entry.get('reviewed') is not True:
            raise ValueError('A reviewed semantic-completeness judgement is required')
        ids = entry.get('ids'); known = [u['id'] for u in byq[q]['units']]
        if not isinstance(ids,list) or not ids or any(type(i) is not int for i in ids):
            raise ValueError('Review must select nonempty original integer source IDs')
        check_packet(byq[q], ids, known, sum(u['tokens'] for u in byq[q]['units']))
        if not isinstance(entry.get('note'),str) or not entry['note'].strip():
            raise ValueError('A brief evidence rationale is required')
        if entry['complete_packet'] and entry['context_judgement'] in ('conflict','answerable'):
            accepted[q] = entry
    return accepted


def call(row, stage, prompt, ids, parents, phase):
    return {'kind':'call','key':cache_key(row['qid'],stage,prompt)+'__'+stage,
            'qid':row['qid'],'stage':stage,'phase':phase,'row':row,'source_ids':ids,
            'prompt':prompt,'parents':parents,'source_cap_tokens':None}


def layout(row, plan, cfg, records):
    q = row['qid']; cap = cfg['source_budget_tokens']; selector = None
    parents = {'input_sha256':c.digest(row)}
    if plan['mode'] == 'reviewed':
        packets = {'human_reference':plan['review_entry']['ids']}
        diagnostic = {'source':'author-reviewed original units','review_sha256':c.digest(plan['review_entry'])}
    else:
        rr = restricted(row, plan)
        if plan['candidate_cost'] <= cap:
            selected_packet = list(plan['candidate_ids'])
            diagnostic = {'selection':'all_candidates_fit'}
        else:
            prompt = setr_prompt(rr, plan['setr_templates'], cap)
            spec = call(rr, 'setr', prompt, plan['candidate_ids'], parents, 'frozen_setr_iri_budget')
            yield spec
            selector = spec['key']; record = records[selector]
            selected = record['parsed']['selected_ids'] if record['valid'] else []
            selected_packet = pack_order(rr, selected + rr['rank_order'], cap)
            unfilled = sum(u['tokens'] for u in rr['units'] if u['id'] in selected)
            diagnostic = {'selection':'parsed_selection_then_rank_fill' if record['valid'] else 'invalid_selection_rank_fallback',
                          'selected_ids':selected,'selected_unpacked_cost':unfilled,'budget_clipped':unfilled > cap}
        check_packet(row, selected_packet, plan['candidate_ids'], cap)
        packets = {'setr_iri_budget':selected_packet,'full_context':list(plan['candidate_ids']),
                   'annotation_reference':list(plan['reference_ids'])}
        diagnostic['annotation_reference_status'] = 'unreviewed annotation-derived diagnostic, not a semantic oracle'
    decisions = {}
    for packet in sorted({tuple(ids) for ids in packets.values()}):
        ids = list(packet); pid = c.digest(ids)
        spec = call(row,'check',check_prompt(row,ids),ids,dict(parents,packet_sha256=pid),'original_reader8')
        yield spec
        note = records[spec['key']]; keys = [spec['key']]; answer = None
        if note['valid']:
            spec = call(row,'answer',answer_prompt(row,ids,note['parsed']['check']),ids,
                        dict(parents,packet_sha256=pid,check=note['record_sha256']),'original_reader8')
            yield spec
            answer = records[spec['key']]; keys.append(spec['key'])
        valid = bool(note['valid'] and answer and answer['valid'])
        decisions[pid] = {'ids':ids,'valid':valid,'answer':answer['parsed']['answer'] if valid else None,'record_keys':keys}
    yield {'kind':'contexts','qid':q,'packets':packets,'decisions':decisions,
           'packet_mapping':{a:c.digest(ids) for a,ids in packets.items()},'selector_key':selector,
           'diagnostics':diagnostic,'mode':plan['mode']}
    yield {'kind':'question_done','qid':q}
