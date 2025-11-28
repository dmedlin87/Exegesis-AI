# Exegesis AI Feature Roadmap

> Implementation plan for 10 new features spanning core research capabilities, engagement mechanics, and UX improvements.

**Document Version:** 1.1
**Created:** 2025-11-27
**Updated:** 2025-11-27
**Status:** Planning

---

## Summary

| # | Feature | Priority | Effort | Dependencies |
|---|---------|----------|--------|--------------|
| 1 | Parallel Translation Viewer | Must-Have | ~10 days | Canon service, verse repository (Phase 0) |
| 2 | Original Language Toolkit | Must-Have | ~18 days | OSHB/SBLGNT data (free), lexicon ingestion |
| 3 | Cross-Reference Graph | Must-Have | ~15 days | D3.js, OpenBible cross-ref data (free) |
| 4 | AI Study Outline Generator | High | ~15 days | RAG pipeline, LLM integration |
| 5 | Collaborative Annotations | High | ~17 days | User auth system (Phase 0), WebSocket |
| 6 | Timeline & Chronology View | Medium-High | ~15 days | Evidence cards |
| 7 | Verse-Level Audio Sync | Medium | ~15 days | Audio CDN, timing data |
| 8 | Reading Progress & Streaks | Medium | ~10 days | User auth system (Phase 0) |
| 9 | Keyboard-First Navigation | UX | ~6 days | Frontend only |
| 10 | Customizable Split Layouts | UX | ~8 days | Frontend state management |

**Total Estimated Effort:** ~129 days (~6.5 months with 1 developer)
**With Phase 0 Prerequisites:** ~165 days (~8 months total)

---

## Architecture Integration Points

Based on existing control flow (see codemap):

```text
┌─────────────────────────────────────────────────────────────────┐
│                      NEW FEATURES MAP                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  API Routes (exegesis/infrastructure/api/app/routes/)           │
│  ├── verses.py ──────── [1] Parallel, [2] Interlinear          │
│  ├── search.py ──────── [3] Cross-ref graph queries            │
│  ├── ai.py ─────────── [4] Outline generator                   │
│  ├── workspaces.py ──── [5] Collaboration (NEW)                │
│  ├── timeline.py ────── [6] Timeline events (NEW)              │
│  ├── audio.py ───────── [7] Audio recordings (NEW)             │
│  └── progress.py ────── [8] Reading progress (NEW)             │
│                                                                 │
│  Application Services (exegesis/application/)                   │
│  ├── canon/ ─────────── [1] ParallelService, [2] InterlinearSvc│
│  ├── research/ ──────── [3] CrossRefService, [6] TimelineService│
│  ├── ai/ ────────────── [4] OutlineGeneratorService            │
│  ├── collaboration/ ─── [5] WorkspaceService (NEW)             │
│  ├── audio/ ─────────── [7] AudioService (NEW)                 │
│  └── engagement/ ────── [8] ProgressService (NEW)              │
│                                                                 │
│  Frontend (exegesis/services/web/app/components/)               │
│  ├── ParallelViewer/ ── [1]                                    │
│  ├── Interlinear/ ───── [2]                                    │
│  ├── CrossRefGraph/ ─── [3]                                    │
│  ├── OutlineGenerator/  [4]                                    │
│  ├── Collaboration/ ─── [5]                                    │
│  ├── Timeline/ ──────── [6]                                    │
│  ├── AudioPlayer/ ───── [7]                                    │
│  ├── Progress/ ──────── [8]                                    │
│  ├── CommandPalette/ ── [9]                                    │
│  └── SplitLayout/ ───── [10]                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Sources (Free & Open)

### Biblical Language Resources

- **OSHB (Open Scriptures Hebrew Bible)**: <https://github.com/openscriptures/morphhb>
  - Westminster Leningrad Codex with morphology
  - Fully tagged Hebrew text with Strong's numbers

- **SBLGNT (SBL Greek NT)**: <https://github.com/LogosBible/SBLGNT>
  - Morphologically tagged Greek text
  - Free for personal use

- **Berean Interlinear**: <https://berean.bible/downloads.htm>
  - Public domain interlinear data

### Lexicons

- **Strong's Concordance**: <https://github.com/openscriptures/strongs> (Public domain)
- **Abbott-Smith Greek Lexicon**: Public domain
- **BDB Hebrew Lexicon**: Public domain

### Cross-References

- **OpenBible.info**: <https://github.com/openbibleinfo/Bible-Cross-Reference-Data>
  - 63,000+ cross-references (CC BY license)

### Translations (Public Domain)

- KJV, ASV, WEB, YLT

---

## Detailed Feature Specifications

See individual feature documents:

- [Feature 1-3: Core Research](./features/FEATURE_1_3_CORE_RESEARCH.md)
- [Feature 4-5: AI & Collaboration](./features/FEATURE_4_5_AI_COLLAB.md)
- [Feature 6-7: Timeline & Audio](./features/FEATURE_6_7_TIMELINE_AUDIO.md)
- [Feature 8-10: Engagement & UX](./features/FEATURE_8_10_ENGAGEMENT_UX.md)

---

## Implementation Phases

### Phase 0: Prerequisites (Weeks 1-6)

**Goal:** Build foundational infrastructure required by core features.

#### 0.1 Canon Service Layer (7 days)

- Create `exegesis/application/canon/` service structure
- Build `VerseRepository` interface and PostgreSQL adapter
- Implement OSIS verse lookup and normalization
- Seed initial translations (KJV, WEB public domain texts)

#### 0.2 Multi-User Authentication (10 days)

- User registration and login endpoints
- JWT token generation and validation
- User table and database migrations
- Basic role-based access control (RBAC)
- **Blocks:** Features 5, 8

#### 0.3 Biblical Language Data Ingestion (14 days)

- Download and parse OSHB (Hebrew) and SBLGNT (Greek)
- Ingest Strong's lexicon data
- Load OpenBible cross-references
- Create database schemas for lexicon and cross-refs
- Build ingestion scripts for repeatable setup
- **Blocks:** Features 2, 3

#### 0.4 Database Schema Audit (5 days)

- Document existing schema
- Plan migration strategy for new tables
- Ensure backward compatibility
- Create database seeding script for dev/test

**Phase 0 Total:** ~36 days (~7 weeks)

### Phase 1: Foundation (Weeks 7-12)

- **[9] Keyboard Navigation** — Low risk, high daily-use impact
- **[10] Split Layouts** — Enables multi-pane features
- **[1] Parallel Translation Viewer** — Core research, builds on existing verse service

### Phase 2: Research Core (Weeks 7-14)

- **[2] Original Language Toolkit** — Requires data seeding
- **[3] Cross-Reference Graph** — D3 visualization complexity

### Phase 3: AI & Social (Weeks 15-22)

- **[4] AI Study Outline Generator** — Leverages existing RAG
- **[5] Collaborative Annotations** — Requires WebSocket infrastructure

### Phase 4: Engagement (Weeks 23-28)

- **[6] Timeline & Chronology**
- **[7] Audio Sync**
- **[8] Reading Progress & Streaks**

---

## Database Schema Summary

### New Tables Required

```sql
-- Feature 1: Parallel Translations
translations (id, code, name, language, is_public_domain, word_for_word_score)

-- Feature 2: Original Languages
lexicon_entries (id, strongs_number, language, lemma, transliteration, definition)
verse_words (id, verse_id, word_position, surface_form, lemma, strongs_id, morphology_code)
morphology_codes (code, language, part_of_speech, tense, voice, mood, person, number, gender)

-- Feature 3: Cross-References
cross_references (id, source_osis, target_osis, reference_type, confidence, direction)
thematic_clusters (id, name, description)

-- Feature 4: AI Outlines
study_outlines (id, user_id, osis_range, outline_type, content, model_used)
prompt_templates (id, template_type, version, system_prompt, user_prompt_template)

-- Feature 5: Collaboration
workspaces (id, name, owner_id, visibility, settings)
workspace_members (workspace_id, user_id, role)
workspace_invitations (id, workspace_id, email, token)
annotation_reactions (id, annotation_id, user_id, reaction_type)
annotation_replies (id, annotation_id, user_id, body)

-- Feature 6: Timeline
timeline_events (id, title, date_start_year, date_precision, osis_refs, confidence)
historical_periods (id, name, start_year, end_year, color)

-- Feature 7: Audio
audio_recordings (id, translation_code, narrator, book_osis, chapter, audio_url)
audio_word_timings (id, recording_id, verse_osis, word_index, start_ms, end_ms)

-- Feature 8: Progress
reading_history (id, user_id, osis, read_at, duration_seconds)
reading_goals (id, user_id, goal_type, target_value)
user_streaks (user_id, current_streak, longest_streak)
badges (id, code, name, criteria)
user_badges (user_id, badge_id, earned_at)
```

---

## API Endpoints Summary

### New Route Files

| File | Endpoints | Feature |
|------|-----------|---------|
| `verses.py` (extend) | `GET /verses/parallel`, `GET /verses/{osis}/interlinear` | 1, 2 |
| `lexicon.py` (new) | `GET /lexicon/{strongs}`, `GET /lexicon/{strongs}/occurrences` | 2 |
| `graph.py` (new) | `GET /graph/verse-network`, `GET /verses/{osis}/cross-references` | 3 |
| `ai.py` (extend) | `POST /ai/generate-outline`, `GET /ai/outlines` | 4 |
| `workspaces.py` (new) | CRUD `/workspaces`, `/workspaces/{id}/invite`, `/workspaces/join/{token}` | 5 |
| `annotations.py` (extend) | `GET /annotations/shared`, `POST /annotations/{id}/reactions` | 5 |
| `timeline.py` (new) | `GET /timeline/events`, `GET /timeline/periods` | 6 |
| `audio.py` (new) | `GET /audio/recordings`, `GET /audio/recordings/{id}/timings` | 7 |
| `progress.py` (new) | `POST /reading/log`, `GET /reading/stats`, `GET /reading/streaks` | 8 |
