You are reading an Indian electricity regulatory order for Regulatory Studio. A legal
reviewer will check everything you return against the order before anything is published,
so precision matters more than completeness.

Extract:
- parties: each party named in the cause title with its role (petitioner, respondent, appellant, intervenor).
- issue: the question the commission had to decide, in one or two sentences.
- outcome: what the commission decided, in one or two sentences.
- summary: 120 to 200 words in plain English for power-sector professionals. Cover the
  issue, the commission's reasoning and the outcome. No adjectives about the decision's
  importance. No legal advice. Do not state anything the order does not say.
- references: every regulation clause, regulation, Electricity Act section, or earlier
  order or judgment that the order relies on, interprets, relaxes, follows or distinguishes.
  For each:
  - citation_text: the citation exactly as written in the order.
  - link_type: applies | interprets | relaxes | follows | distinguishes | appealed_in |
    upholds | sets_aside | remands.
  - target_kind: clause | regulation | act_section | document.
  - target_id: the id from the REGISTRY or ACT SECTIONS lists below that the citation
    refers to. If you are not certain it is the same provision, use null. Never construct
    an id that is not in the lists.
  - pid: the id of the paragraph where the order relies on it, for example "p3.12".
  - excerpt: a short passage copied word for word from that paragraph that shows the
    reliance (under 300 characters).

Return ONLY a JSON object matching this schema, with no other text:
{schema}

Commission: {commission}
Document title as listed: {title}

REGISTRY (clause ids you may use as target_id; format: id | heading):
{registry}

ACT SECTIONS (ids you may use as target_id):
{act_sections}

ORDER TEXT (each paragraph starts with its id in brackets):
{text}
