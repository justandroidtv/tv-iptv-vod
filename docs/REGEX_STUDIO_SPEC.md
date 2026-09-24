# Regex Studio Specification

## Philosophy

Regex is a power tool.

The UI provides two modes:

### Safe mode

Guided recipes with explanations, examples and preview.

### Expert mode

Free-form Python-compatible regular expressions and replacement expressions.

Every rule exposes:
- name
- description
- scope
- pattern
- replacement
- flags
- order
- enabled state
- stop-processing flag
- example input
- example output
- expected risk

## Supported scopes

- movie title
- series title
- episode title
- category name
- display alias
- generated filename

Provider/raw title and canonical title are separate scopes.

## Pipeline

input -> rule 1 -> rule 2 -> rule N -> normalization -> output

A rule may stop processing.

## Safety

- maximum synchronous pattern length: 256 characters
- maximum synchronous batch: 500 rows
- larger jobs run in background
- reject obvious nested catastrophic quantifiers
- show match count before write
- show representative old/new pairs
- require explicit confirmation
- snapshot before write
- optimistic rollback checks
- never log full provider URLs

## Recipe families

### Title cleanup

- provider prefix removal
- release-group removal
- resolution removal
- codec removal
- source tag removal
- language tag cleanup
- bracket normalization
- dash normalization
- separator normalization
- whitespace cleanup
- invisible Unicode cleanup

### Metadata extraction

- year
- season
- episode
- part/volume
- edition

### Arabic normalization

- Arabic-Indic digit normalization
- Persian digit normalization
- Arabic punctuation normalization
- Arabic season/episode phrases
- common provider prefix cleanup

### Filename normalization

- filesystem-invalid characters
- trailing periods
- excessive length
- Windows reserved names

### Identity normalization

- TMDB tag normalization
- year normalization
- season/episode normalization
- duplicate-title handling

## Anti-rules

The system warns before broad expressions such as dot-star and broad suffix deletion.

A rule capable of erasing an entire title requires expert confirmation.

## Rule packs

JSON rule packs contain:
- name
- version
- author
- scope
- ordered rules
- compatibility note
- examples
- migration note

Suggested packs:
- arabic-vod-cleanup
- english-release-cleanup
- tmdb-normalization
- series-season-episode
- filesystem-safe
- provider-prefix-cleanup

## Alias-first policy

Normal path:
raw -> normalized -> alias

Canonical database mutation is an explicit expert operation.

## Preview

Show:
- scanned
- matched
- changed
- unchanged
- invalid
- conflicts

Show at least ten representative changes and paginate the complete result.

## Rollback

Restore a row only when its current value equals the value written by the original job.

Otherwise mark it as a conflict and do not overwrite it.
