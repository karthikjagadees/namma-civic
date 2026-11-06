# Phase 3: Duplicate detection

## What it does

The duplicate resolver ranks likely existing **incidents** for a new report. It can return `auto_link`, `officer_review`, or `new_incident`. It does not yet finish the end-to-end pipeline action; Phase 4 will connect the result to incident linking, work-order idempotency, and notifications.

The database candidate repository and pure scoring engine are separate. `app/deduplication/repository.py` retrieves a bounded candidate set; `app/deduplication/engine.py` scores candidates without database or LangGraph dependencies. The graph node records ranked evidence and failures, and routing sends review outcomes to the existing officer approval pause.

## Candidate retrieval and safety

For a report with coordinates, SQL filters active (`open`, `in_progress`) and recently resolved incidents to a bounding box around the location. The maximum box radius is the category-specific base radius plus capped report uncertainty and one additional base radius for capped candidate uncertainty. Latitude and longitude are indexed in the current schema. Exact Haversine distance is calculated only after this database prefilter. The result is capped at 250 candidates; if more candidates are found, the outcome is officer review because the search was truncated.

Only incidents with activity in the previous 365 days are considered (`updated_at` for database retrieval and latest linked report time in the pure engine). A resolved incident is never auto-linked. A strong match creates a new incident and references the resolved incident with `recurrence_of_incident_id`; ambiguous recurrence candidates go to review. If multiple distinct active incidents are plausible, the result is review because the new report could bridge them. Closed incidents are not considered candidates.

Reports without a usable coordinate pair go to officer review even if their text matches. There is deliberately no text-only auto-link. If database retrieval fails or a signal cannot be computed, the failure is returned in the result and the graph routes it to review instead of treating the report as unique.

### Strong same-photo match among nearby candidates

When exactly one candidate has the same category, a location within 20 m, and a near-identical pHash (similarity at least `0.95`), that match can take precedence over weaker nearby candidates. If the strong match is active, the report links to that incident. If it is resolved, the resolver creates a separate recurrence incident that references it; it does not add the new reporter to the resolved incident. If two candidates both have near-identical photo evidence, including an active and a resolved incident, the resolver keeps the report in officer review because the image does not distinguish which incident is correct. This rule still depends on accurate location/category data and can fail for generic or reused photos; pHash is evidence, not identity.

The pHash migration also adds nullable location confidence and accuracy fields to complaints and incidents. Accuracy is copied into graph state and candidate evidence when available. Unknown accuracy remains unknown; it is not assigned a guessed default.

## Signals and fusion math

Each candidate gets a per-signal score from 0 to 1, or `null` when that evidence is absent:

| Signal | Calculation | What it contributes | Main limitation |
|---|---|---|---|
| Distance | Category radius: pothole 100 m, garbage 60 m, water leakage 80 m, streetlight 45 m, drainage 75 m, traffic signal 60 m, encroachment 80 m, other 75 m. Let `d` be Haversine distance, `r` the category radius, `u` the sum of each reported accuracy capped at `r`, and `q` the product of available provider confidence values (or 1 when none were supplied): `max(0, 1 - max(0, d-u)/r) * r/(r+u) * q`. | Nearby locations get stronger evidence, with a different search radius by issue type. Uncertainty can make overlap plausible but also lowers certainty. | GPS/geocoder errors can place an issue outside the radius; nearby separate defects can still be close. |
| Category | Exact category = 1; cautious related categories = 0.20 or 0.25; other category combinations = 0. | Helps avoid combining unlike civic work. | Reports and model classification can use the wrong category; category mismatch is not proof that reports are separate. |
| Token similarity | Jaccard overlap of normalized word sets. | Rewards shared issue words and is easy to explain. | It ignores word order and meaning; synonyms and different languages may share few tokens. |
| Character n-gram similarity | Cosine similarity over counts of normalized 3-, 4-, and 5-character substrings. | Can retain some overlap across small spelling variations and transliterations in the same script. | Similar-looking words can be unrelated; different scripts or heavy paraphrasing can have little overlap. |
| Image pHash | `1 - HammingDistance / 64` over 64-bit ImageHash perceptual hashes. For multiple photos, the best pairwise similarity is used. | Detects some resized, recompressed, or mildly adjusted copies without sending photos to an AI service. | A crop, changed viewpoint, occlusion, lighting, or two visually similar road surfaces can break or fool the match. It is not object recognition. |
| Time | `max(0, 1 - days_since_last_report / 180)`. | Recent reports are more plausible matches than stale ones. | Old unresolved defects may still be the same issue; recent reports can also describe a different nearby defect. |
| Address/landmark | Exact normalized address/landmark overlap = 1; otherwise word-token Jaccard overlap. | Adds explicit place evidence to the score. | Common street or landmark names are weak evidence. Without coordinates this signal cannot trigger auto-linking. |

The fused score uses fixed, documented starting weights and renormalizes over signals that are actually present:

```text
score = sum(weight[i] * signal[i] for available signals)
        / sum(weight[i] for available signals)

distance .24 | category .16 | token .12 | character n-gram .14
image pHash .18 | time .06 | address/landmark .10
```

These weights are explicit policy choices, not trained model parameters. Missing photos remove the photo term from both sums; they do not count as evidence against a match. Invalid pHash or any other computation failure sends the candidate set to review.

## pHash and text similarity in plain language

**pHash:** ImageHash shrinks and transforms a picture into a 64-bit summary of its broad light/dark structure. Similar summaries have a small Hamming distance (few bits differ). This often survives a resize or ordinary compression, unlike a file checksum, which changes when even one byte changes. It can fail when the camera angle or crop changes the scene, and two different potholes can have similar dark/light shapes. The hash is a clue, never proof.

**Token Jaccard:** Turn each report into a set of words, then divide the number of shared words by the number of distinct words across both reports. It is clear and deterministic, but “road hole” and “crater” have no shared issue word.

**Character n-grams:** Slide a 3–5 character window across normalized text and compare the resulting substring counts. “pothole” and “potholee” retain many overlapping pieces, so minor spelling changes can still score. This is still lexical matching, not understanding: unrelated words may share substrings, and a phrase in a different writing system may have none.

## Threshold selection and synthetic evaluation

The reproducible dataset at `backend/data/synthetic_duplicate_pairs.json` contains **200 labeled synthetic report pairs**: 100 positive wording/channel variants and 100 hard negatives, including nearby distinct potholes, different issue categories on one street, and similar reports far apart. These are generated examples, not production reports.

The deterministic split is stratified by label: 160 pairs select thresholds and 40 separate pairs are held out for final metrics. The review threshold is the highest calibration threshold retaining at least 98% recall; the auto-link threshold is selected above it for best calibration F1 subject to at least 95% precision. Resulting thresholds are **auto-link ≥ 0.66** and **review ≥ 0.58**. These values are derived from this synthetic calibration set and have not been validated on real municipal data.

Held-out synthetic test results (40 pairs: 20 positive and 20 negative):

| Signal | Precision | Recall | F1 |
|---|---:|---:|---:|
| Distance | 1.000 | 0.800 | 0.889 |
| Category | 0.571 | 1.000 | 0.727 |
| Token similarity | 0.750 | 0.750 | 0.750 |
| Character n-grams | 0.800 | 1.000 | 0.889 |
| Image pHash | 1.000 | 0.750 | 0.857 |
| Time | 0.500 | 0.450 | 0.474 |
| Address/landmark | 0.500 | 1.000 | 0.667 |
| Fused score at auto-link threshold | 1.000 | 0.850 | 0.919 |

At the review threshold, held-out candidate recall was 0.900, precision 0.545, and F1 0.679. That means the example operating point catches most synthetic duplicates for human review, while producing a substantial review queue.

Leave-one-signal-out held-out F1:

| Removed signal | Precision | Recall | F1 |
|---|---:|---:|---:|
| Distance | 0.762 | 0.800 | 0.780 |
| Category | 1.000 | 1.000 | 1.000 |
| Token similarity | 1.000 | 0.800 | 0.889 |
| Character n-grams | 1.000 | 0.800 | 0.889 |
| Image pHash | 1.000 | 0.850 | 0.919 |
| Time | 1.000 | 0.850 | 0.919 |
| Address/landmark | 1.000 | 0.850 | 0.919 |

The synthetic ablation says this particular generated set does not demonstrate gains from every signal: removing category improves the measured score, and removing several weaker signals slightly improves recall. This is a warning about the synthetic dataset and hand-set weights, not evidence that those signals should be removed. Real labeled officer decisions are needed before production threshold claims.

Run the same deterministic evaluation and regenerate the synthetic JSON file from `backend/`:

```powershell
& "$env:TEMP\civicfix-phase0-venv\Scripts\python.exe" scripts\evaluate_duplicate_detection.py
```

## Migration, recurrence and limits

Alembic revision `0003_duplicate_detection` adds a nullable 16-character pHash to image media, nullable location confidence/accuracy to reports and incidents, and the self-reference `incidents.recurrence_of_incident_id`. It backfills pHash for legacy image files that are still accessible under the local uploads directory. Missing, remote, unreadable, or removed files remain `NULL`; the migration does not fabricate hashes.

New local image media gets pHash during complaint creation. The recurrence service creates a fresh incident, points it to the prior resolved incident, and supersedes the report's provisional link so the original link decision remains auditable. The duplicate node currently reports the recurrence target; full automatic application of every resolver outcome to intake and work orders is Phase 4 integration.

The current evaluation is small, synthetic, and hand-authored. pHash is not vision understanding, n-grams are not semantic embeddings, and the geographic/category policy has not been calibrated on actual local complaint data. Do not use these synthetic numbers as a claim of production accuracy.

The project’s `requirements-vercel.txt` describes a 50 MB deployment limit. ImageHash depends on numerical/image packages including SciPy; the Vercel bundle size has not been measured after adding this dependency. Verify the deployment artifact before release, because the approved pHash dependency may require a deployment packaging change.
