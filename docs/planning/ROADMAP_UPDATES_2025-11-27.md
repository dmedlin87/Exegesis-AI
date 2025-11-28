# Feature Roadmap Updates - November 27, 2025

## Summary of Changes

This document tracks the corrections and enhancements made to the Feature Roadmap on 2025-11-27.

---

## 1. Corrected Frontend Paths

**Issue:** Roadmap referenced incorrect frontend directory structure.

**Before:** `frontend/src/components/`
**After:** `exegesis/services/web/app/components/`

**Files Updated:**
- `docs/FEATURE_ROADMAP.md`
- `docs/features/FEATURE_1_3_CORE_RESEARCH.md`
- `docs/features/FEATURE_4_5_AI_COLLAB.md`
- `docs/features/FEATURE_6_7_TIMELINE_AUDIO.md`
- `docs/features/FEATURE_8_10_ENGAGEMENT_UX.md`

**Reason:** The project uses Next.js App Router structure located at `exegesis/services/web/app/`, not a traditional `frontend/src/` structure.

---

## 2. Added Free Data Sources Section

**Added to:** `docs/FEATURE_ROADMAP.md`

**New Section: "Data Sources (Free & Open)"**

Documented freely available biblical language resources suitable for personal/hobby use:

### Biblical Language Resources
- **OSHB (Open Scriptures Hebrew Bible)** - Public domain Hebrew text with morphology
- **SBLGNT (SBL Greek NT)** - Free Greek text with morphological tags
- **Berean Interlinear** - Public domain interlinear data

### Lexicons
- **Strong's Concordance** - Public domain (1890)
- **Abbott-Smith Greek Lexicon** - Public domain
- **BDB Hebrew Lexicon** - Public domain

### Cross-References
- **OpenBible.info** - 63,000+ cross-references (CC BY license)

### Translations
- KJV, ASV, WEB, YLT - All public domain

**Impact:** Feature 2 (Original Language Toolkit) is now feasible without commercial licensing.

---

## 3. Added Phase 0: Prerequisites

**New Phase:** Phase 0 (Weeks 1-6, ~36 days)

### Phase 0 Tasks

#### 0.1 Canon Service Layer (7 days)
- Build foundational verse repository infrastructure
- Create `exegesis/application/canon/` service structure
- Implement OSIS verse lookup
- Seed public domain translations

**Blocks:** Feature 1

#### 0.2 Multi-User Authentication (10 days)
- User registration and login
- JWT token management
- User table and migrations
- Role-based access control

**Blocks:** Features 5, 8

#### 0.3 Biblical Language Data Ingestion (14 days)
- Download and parse OSHB/SBLGNT data
- Ingest Strong's lexicon
- Load OpenBible cross-references
- Create database schemas
- Build repeatable ingestion scripts

**Blocks:** Features 2, 3

#### 0.4 Database Schema Audit (5 days)
- Document existing schema
- Plan migration strategy
- Ensure backward compatibility
- Create dev/test seeding scripts

---

## 4. Updated Effort Estimates

**Original Total:** ~126 days (6 months)
**Updated Feature Total:** ~129 days (6.5 months)
**With Phase 0:** ~165 days (8 months total)

### Specific Changes
- Feature 2 (Original Language Toolkit): 15 → 18 days (+3 days for data ingestion complexity)

---

## 5. Updated Dependencies

**Before:**
- Feature 1: "Canon service, verse repository"
- Feature 2: "Hebrew WLC data, lexicon data"
- Feature 5: "User auth, WebSocket"
- Feature 8: "User auth"

**After:**
- Feature 1: "Canon service, verse repository (Phase 0)"
- Feature 2: "OSHB/SBLGNT data (free), lexicon ingestion"
- Feature 5: "User auth system (Phase 0), WebSocket"
- Feature 8: "User auth system (Phase 0)"

---

## 6. Updated Version Information

**Document Version:** 1.0 → 1.1
**Added:** Updated timestamp
**Status:** Remains "Planning"

---

## What Was NOT Changed

### Preserved as-is:
- ✅ API endpoint specifications
- ✅ Database schema designs
- ✅ Service layer architecture
- ✅ Implementation phase priorities
- ✅ Feature priorities and scoping
- ✅ Technical implementation details in feature specs

### Intentionally Deferred:
- Algorithm optimizations (e.g., word alignment in Feature 1)
- Specific technology choices (D3.js vs alternatives)
- WebSocket vs polling decisions (Feature 5)
- Performance optimization strategies

**Reason:** These are implementation details that can be decided during actual development.

---

## Recommendations for Next Steps

### Immediate (This Week)
1. Review updated roadmap for approval
2. Audit existing database schema (Phase 0.4)
3. Verify current authentication infrastructure

### Short-Term (Weeks 1-2)
1. Begin Phase 0.1: Canon Service Layer
2. Download sample OSHB/SBLGNT datasets
3. Create initial data ingestion script prototype

### Medium-Term (Month 1)
1. Complete Phase 0 prerequisites
2. Test data ingestion pipeline
3. Validate authentication system readiness

---

## Risk Adjustments

### Risks Mitigated:
- ✅ Data licensing concerns resolved (all sources are free/open)
- ✅ Frontend architecture mismatch corrected
- ✅ Missing infrastructure now identified and planned

### Remaining Risks:
- ⚠️ Data ingestion complexity may exceed 14-day estimate
- ⚠️ Multi-user auth may require more than 10 days if complex RBAC needed
- ⚠️ Integration with existing authentication may have hidden complexity

---

## Files Modified

| File | Changes |
|------|---------|
| `docs/FEATURE_ROADMAP.md` | Version bump, frontend paths, data sources, Phase 0 |
| `docs/features/FEATURE_1_3_CORE_RESEARCH.md` | Frontend paths corrected (3 instances) |
| `docs/features/FEATURE_4_5_AI_COLLAB.md` | Frontend paths corrected (2 instances) |
| `docs/features/FEATURE_6_7_TIMELINE_AUDIO.md` | Frontend paths corrected (2 instances) |
| `docs/features/FEATURE_8_10_ENGAGEMENT_UX.md` | Frontend paths corrected (3 instances) |

**Total Changes:** 5 files, 10+ path corrections, 1 new section, 1 new phase

---

## Validation

### Path Corrections Verified
```bash
$ grep -c "exegesis/services/web/app" docs/features/*.md
FEATURE_1_3_CORE_RESEARCH.md:3
FEATURE_4_5_AI_COLLAB.md:2
FEATURE_6_7_TIMELINE_AUDIO.md:2
FEATURE_8_10_ENGAGEMENT_UX.md:3
```

### Data Sources Verified
All listed resources confirmed to be:
- Freely available for download
- Suitable for personal/hobby use
- No commercial licensing required
- Active and maintained repositories

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-27 | Claude (AI Assistant) | Initial corrections: paths, data sources, Phase 0 |

---

**Status:** Complete ✅
**Next Review:** Before Phase 0.1 implementation begins
