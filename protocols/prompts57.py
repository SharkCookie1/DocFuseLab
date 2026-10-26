"""Own prospective prompts; IRI-inspired adaptation, not official SetR reproduction."""
from core57 import render

def question(row):
    text='Question: '+row['question']
    if row['options']:text+='\nAnswer options: '+' | '.join(row['options'])
    return text

def answer_prompt(row,ids):
    return '''Answer using only the supplied evidence. Do not replace it with remembered world knowledge.
If the evidence does not support a complete answer, return UNKNOWN.
If the evidence supports incompatible answers to this same question and its conditions and does not resolve the discrepancy, return CONFLICT.
Different items in an explicitly requested list, or facts about different dates or conditions, are not automatically a conflict.
Otherwise return the short exact answer; if answer options are supplied, use the option text.
Output exactly one JSON object with the sole key "answer". Do not output explanations or Markdown.
'''+question(row)+'\nEvidence:\n'+render(row,ids)+'\nJSON answer:'

def iri_prompt(row,budget):
    return f'''Identify the information requirements of the question, then select evidence units that jointly satisfy them.
Use only the supplied evidence. Include the complementary facts needed for multi-hop reasoning.
Do not replace missing information with remembered facts. A mention alone may not establish the requested relation.
The final evidence budget is {budget} tokens. The cost beside each unit is its cost in the final evidence packet.
List the selected unit IDs in priority order, with the most necessary units first. Do not duplicate IDs.
Output exactly {{"needs":["brief requirement",...],"selected_ids":[1,2,...]}}.
Use 1 to 5 short needs. selected_ids may be empty if no useful evidence is present. No answer, explanations, or Markdown.
'''+question(row)+'\nEvidence units:\n'+render(row,[u['id'] for u in row['units']],True)+'\nJSON selection:'

def ledger_prompt(row,budget):
    return f'''Inspect which sets of evidence units support answers to the question. Use only the supplied text, even if it differs from remembered world knowledge.
A support set is a small set of unit IDs that JOINTLY supports a complete answer. Include every bridge relation required by a multi-hop question. Mere co-occurrence or an unsupported inference is insufficient.
Return up to 4 alternative minimal support sets, each with 1 to 6 IDs. Return an empty list when no complete answer is supported. Do not invent a support set merely to avoid an empty list.
A conflict pair contains TWO evidence sets that establish mutually incompatible answers to this SAME question, entity, relation, date and condition. Each side may need several units. A list question can have multiple correct members; distinct members are not a conflict. Paraphrases and aliases are not a conflict. Different times or scopes are not a conflict unless they contradict the question's requested scope.
Return up to 3 conflict pairs; each left/right list has 1 to 6 IDs and must establish its side from the supplied evidence. Shared bridge units are allowed. Missing evidence is NOT contradictory evidence.
The final evidence budget is {budget} tokens. Identify the minimal witnesses honestly even if their union exceeds that budget; do not omit a necessary bridge to make them fit. Code will pack the witnesses.
Output exactly {{"support_sets":[[1,2]],"conflict_pairs":[{{"left":[1,2],"right":[3,4]}}]}} using only actual unit IDs.
The displayed shape is not an example of the correct IDs. Do not output candidate answers, confidence, explanations, or Markdown.
'''+question(row)+'\nEvidence units:\n'+render(row,[u['id'] for u in row['units']],True)+'\nJSON witnesses:'
