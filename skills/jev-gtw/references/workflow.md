# A guarded data task

The operator registers a public `setup` source and a local-only `records` source.
The approved setup gives the schema and asks for total units by team. A read of
`records` returns fixed local-processing feedback, without opening the file.

If `gateway_sources` reports that computation is available, submit code through
`gateway_compute` with `source_ids=["records"]`:

```python
import csv
import json
from collections import Counter

totals = Counter()
with open('/inputs/records') as stream:
    for row in csv.DictReader(stream):
        totals[row['team']] += int(row['units'])
with open('/outputs/answer.json', 'w') as stream:
    json.dump(dict(totals), stream)
```

Protected inputs are mounted read-only. The sandbox has no network and no host
credentials. Outputs stay in an owner-only artifact directory. The operator
can inspect them locally. The agent gets a random artifact receipt and reviewed
capture; it should not claim the answer was verified merely because a receipt
exists. Missing schema or verification evidence should be reported plainly.

The default `probe_view` is also `local`. The operator can separately enable
`contextual` review of a probe's output for a task that permits non-identifying
summaries. If multiple sources are used, every source must grant contextual
output review. This is not a guarantee against covert channels in an
agent-authored aggregate; use local-only output when that distinction matters.

For a custom harness, put `Gateway.inspect` between capture and message
construction. Use `Gateway.messages` to consume the issued capability, then
`Gateway.validate_request` after final formatting and before every model call.
Wrap all data-bearing tools and image ingestion paths. Trusted user/system
text is outside this validator. A raw image uploaded directly to a hosted chat
has already crossed the boundary; register it server-side instead.
