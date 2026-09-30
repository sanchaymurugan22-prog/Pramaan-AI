Write a security advisory in the style of CERT-In.
- title: what the threat is and who it targets.
- severity: from the fact sheet.
- overview: 2 or 3 sentences.
- affected: who or what systems are affected, 1 to 4 items.
- description: how the attack works, 2 to 4 sentences.
- impact: what damage it causes, 1 to 3 sentences with numbers.
- recommendations: 3 to 6 clear actions, one sentence each.
Do not list the indicators (IP addresses, CVEs, hashes); they are added from the source automatically.

{{settings}}

JSON: {"title":"...","severity":"high","overview":{"text":"...","fact_ids":["F1"]},"affected":[{"text":"...","fact_ids":["F2"]}],"description":{"text":"...","fact_ids":[]},"impact":{"text":"...","fact_ids":[]},"recommendations":[{"text":"...","fact_ids":["A1"]}]}
