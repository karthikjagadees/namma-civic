# Namma Civic glossary

| Term | Plain-language meaning in this project |
|---|---|
| Complaint | One citizen's original report and evidence. The complaint remains separate even when grouped with other reports. |
| Incident | The shared operational record for one real-world civic issue. |
| ReportLink | A versioned association from one complaint to an incident, including score/evidence and who or what decided it. |
| Work order | The unit of municipal work attached to an incident. The database allows at most one active work order per incident. |
| Reporter | The citizen who submitted a complaint. An incident's reporters are derived from its active report links. |
| Channel | The route through which a report arrived, such as web, mobile, voice, or WhatsApp. |
| Canonical report | A normalized representation of a channel payload with shared fields such as text, time, location, media, and source. |
| Candidate retrieval | The database query that narrows which existing incidents the duplicate engine should compare. |
| Spatial prefilter | A geographic bounding-box query that limits candidates around a report before exact scoring. |
| Signal | One piece of duplicate evidence, such as distance, category agreement, text similarity, photo similarity, time, or place-name overlap. |
| pHash | Perceptual hash: a compact representation of an image used to estimate whether two images look similar after modest visual changes. It does not identify objects. |
| Hamming distance | The count of differing bit positions between two hashes. Fewer differing bits indicate more similar hashes. |
| Token Jaccard | Shared unique words divided by all unique words across two texts. It is a simple lexical overlap score. |
| Character n-gram | A short, overlapping run of characters. Comparing these runs can tolerate some spelling variation, but does not understand meaning. |
| Fused score | A weighted average of available duplicate signals, renormalized when some signals are missing. |
| Threshold | A configured score boundary used to decide whether to link automatically, ask an officer, or create a separate incident. |
| Auto-link | The duplicate outcome that attaches a report to a likely matching active incident without a case-by-case officer decision. |
| Officer review | Human decision path for uncertain, conflicting, failed, or potentially bridging matches. |
| New incident | The outcome when no eligible candidate is similar enough to link. |
| Recurrence | A new report matching a previously resolved issue. The new incident points to the resolved one through `recurrence_of_incident_id`. |
| Cluster bridge | A report that appears to connect two existing incidents. It is sent to officer review because choosing one automatically could merge distinct work. |
| False merge | Two different real-world issues are incorrectly grouped together. It can hide a real job and corrupt follow-up, so the system handles conflicting evidence conservatively. |
| False split | Reports about the same issue remain separate, causing duplicate attention or work orders. |
| Synthetic dataset | Artificially authored examples used for repeatable tests or evaluation. It is not real citizen data. |
| Hard negative | A deliberately difficult non-duplicate pair, such as separate nearby potholes or different issue categories on one street. |
| Precision | Of the pairs called duplicates, the fraction that are actually duplicates in the labeled evaluation set. |
| Recall | Of the labeled duplicate pairs, the fraction found by the resolver at the chosen operating point. |
| F1 | The harmonic mean of precision and recall; it summarizes both but does not replace the underlying values. |
| Ablation | An evaluation that removes one scoring signal to see how the measured result changes on that dataset. |
| LangGraph | The workflow library used to pass shared state through named graph nodes and pause at an approval gate. |
| Node | One graph step. A node may call a service or apply deterministic logic; it need not be a separate AI model or process. |
| Human-in-the-loop (HITL) | A point where a report pauses until an authorized officer approves or rejects the next action. |
| Checkpointer | Storage for LangGraph execution state. Namma Civic currently uses in-memory `MemorySaver`, so paused state is lost when the process exits. |
| Idempotency key | A caller-supplied stable value that lets the API recognize a replay of the same request and return the earlier complaint. |
| SLA | Service-level target used to estimate a deadline and identify at-risk or overdue work. Current policies are prototype rules. |
| Fan-out notification | One incident event being sent to the linked reporters, subject to their channel preferences. |
| MCP-style tool adapter | The project's in-process tool registry and invocation interface. Automated tests replace external side effects with local fakes. |
| Mock provider | A deterministic local AI implementation used for offline tests and demos. |
| Mock tool | A deterministic test replacement for notification or dispatch behavior. It records test results without contacting a real provider. |
| Immutable evidence | The original citizen-submitted report fields and media references, retained as evidence rather than rewritten during triage. |
| Bounding box | A rectangular latitude/longitude range used to make the first candidate search spatially selective. |
| Location uncertainty | Metadata about how approximate a report's coordinates may be, used to avoid treating an imprecise point as exact. |
