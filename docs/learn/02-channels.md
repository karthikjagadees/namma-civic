# Phase 2: Channel normalization

## What this phase adds

The backend now has a small adapter layer that turns supported channel payloads into one `CanonicalReport`. It supports the existing channel values `web`, `mobile`, `voice`, and `whatsapp`; it does not add a new channel or change the complaint database schema.

The adapter is a pure boundary between channel-specific request shapes and the rest of the application. It is available at `backend/app/channels/` and is not yet called by the complaints API or the LangGraph pipeline. Wiring it to persistence and the graph is later work.

## Canonical report fields

| Field | Meaning |
|---|---|
| `text` | Citizen wording. Web/mobile title and description are joined with a newline; voice and WhatsApp text is kept as supplied. No translation or language detection is attempted. |
| `latitude`, `longitude` | A validated coordinate pair, supplied by the channel or returned by geocoding. |
| `address`, `landmark` | Address or rough place text supplied by the reporter; a geocoder's formatted address can fill `address`. |
| `photos` | Photo references extracted from `photos`, `media`, or `attachments`; non-image media is skipped. Missing photos become an empty list. |
| `language` | Optional language label supplied by the source payload. |
| `reporter_id`, `reporter_contact` | Optional identity/contact. Anonymous reports remain possible; a phone-only report has contact but no reporter ID. |
| `channel`, `reported_at` | Existing channel enum and provided timestamp, or current UTC time when absent. |
| `location_confidence`, `location_accuracy_m` | Returned only when the geocoder provides those values; the adapter does not make up an accuracy radius. |
| `normalization_warnings` | Partial coordinates or geocoding failures are surfaced while preserving the report text and other fields. |

Coordinates must be both present or both absent, and latitude/longitude ranges are validated. An address or landmark is geocoded only when a complete coordinate pair is missing. If the provider cannot resolve it or errors, the address/landmark stays in the canonical report, coordinates stay unknown, and a warning explains why.

## Example payloads (synthetic)

These examples illustrate the adapter contract; they are synthetic and are not claimed to come from production traffic.

**Web**

```json
{"title":"Streetlight","description":"Light is out near gate","latitude":12.97,"longitude":77.59,"media":[{"file_url":"/uploads/lamp.jpg","media_type":"image"}]}
```

**Mobile**

```json
{"title":"Road damage","description":"Pothole beside the school","address":"School Road","photos":["/uploads/road.jpg"],"language":"en"}
```

**Voice transcript**

```json
{"transcript":"Yahan bada gaddha hai","landmark":"Central Park gate","phone":"+919900000001"}
```

**WhatsApp**

```json
{"message":{"text":"குப்பை அகற்றப்படவில்லை","timestamp":"2026-01-02T03:04:05Z"},"from":"+919900000002"}
```

The adapter preserves mixed-language and transliterated text as evidence. It does not infer a translation, category, reporter identity, or missing location. The geocoder is an injected async dependency in tests, allowing deterministic offline checks; the default integration delegates to the existing GIS service, which may call its configured external geocoding provider.

## Teaching walkthrough

1. `normalize_report(channel, payload)` selects field conventions for the chosen channel.
2. It reads message, contact, timestamps, and photo references from the channel payload and builds one text field.
3. It accepts a complete coordinate pair as-is after range validation. If location is only an address or landmark, it asks the geocoder for coordinates.
4. It records provider confidence/accuracy only if actually returned. A lookup failure becomes a warning rather than guessed coordinates or a dropped report.
5. Pydantic validates the final `CanonicalReport`, including requiring coordinates to be a pair.

We chose an explicit async adapter with an injectable geocoder instead of changing the complaint schema or making each channel call the database directly. This keeps normalization testable and lets later phases decide how canonical data maps to persisted complaints. The trade-off is that language, contact, and geocoding metadata are not persisted by this phase.

## Limitations and next work

- The source payload formats are adapters' accepted shapes; no live webhook or mobile SDK integration is added here.
- Speech transcription itself remains the responsibility of the existing voice/transcription path. This adapter receives transcript text.
- Language is copied only when supplied. There is no automatic language detection or translation.
- The existing geocoder returns confidence for some providers but does not consistently provide an accuracy radius. In that case `location_accuracy_m` stays `null`.
- No database migration is needed because this phase adds a DTO/adaptation layer only. Persistence mapping and API/graph integration remain open.
