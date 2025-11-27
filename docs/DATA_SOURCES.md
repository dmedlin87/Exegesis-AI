# Free Biblical Language Data Sources

> Quick reference for obtaining free, open biblical language resources for personal use.

**Last Updated:** 2025-11-27

---

## Hebrew Old Testament

### OSHB (Open Scriptures Hebrew Bible)
**License:** CC BY 4.0 (Public Domain)
**Repository:** https://github.com/openscriptures/morphhb
**Format:** XML, JSON

**What's Included:**
- Full Westminster Leningrad Codex (WLC) text
- Morphological tagging for every word
- Strong's numbers
- Lemma forms
- Part of speech tags
- Verb tense, person, number, gender information

**Download:**
```bash
git clone https://github.com/openscriptures/morphhb.git
cd morphhb
# Files: wlc/*.xml (one file per book)
```

**Sample Entry (Genesis 1:1):**
```xml
<w lemma="7225" morph="He,Ncfsa" strong="b/H7225">בְּרֵאשִׁית</w>
<w lemma="1254 a" morph="He,Vqp3ms" strong="H1254">בָּרָא</w>
<w lemma="430" morph="He,Ncmpa" strong="H0430">אֱלֹהִים</w>
```

---

## Greek New Testament

### SBLGNT (SBL Greek New Testament)
**License:** CC BY 4.0 (Free for personal use)
**Repository:** https://github.com/LogosBible/SBLGNT
**Format:** Plain text with morphology

**What's Included:**
- Full Greek NT text (NA28-based)
- Morphological codes
- Lemmas
- Strong's numbers (via separate mapping)

**Download:**
```bash
git clone https://github.com/LogosBible/SBLGNT.git
cd SBLGNT/data/sblgnt/text
# Files: one .txt file per book
```

**Sample Entry (John 1:1):**
```
010101 N- ----NSF- Ἀρχή ἀρχή
010101 P- -------- ἦν εἰμί
010101 RA ----NSM- ὁ ὁ
010101 N- ----NSM- λόγος λόγος
```

### Berean Interlinear Bible
**License:** Public Domain
**Website:** https://berean.bible/downloads.htm
**Format:** TSV, JSON

**What's Included:**
- Greek text with English glosses
- Strong's numbers
- Transliteration
- Morphology codes

**Download:**
- Direct download from website
- Files available in CSV/TSV format

---

## Lexicons

### Strong's Concordance
**License:** Public Domain (1890)
**Repository:** https://github.com/openscriptures/strongs
**Format:** XML, JSON

**What's Included:**
- Hebrew dictionary (H1-H8674)
- Greek dictionary (G1-G5624)
- Definitions, pronunciation, etymology
- King James Version word mappings

**Download:**
```bash
git clone https://github.com/openscriptures/strongs.git
cd strongs
# Files: hebrew.xml, greek.xml
```

**Sample Entry:**
```xml
<entry id="H430">
  <w>אֱלֹהִים</w>
  <pron>elohim</pron>
  <def>gods, God, judges, angels</def>
  <deriv>Plural of H433</deriv>
</entry>
```

### Abbott-Smith Greek Lexicon
**License:** Public Domain
**Source:** https://github.com/translatable-exegetical-tools/Abbott-Smith
**Format:** XML

**What's Included:**
- Comprehensive Greek-English lexicon
- Classical usage notes
- LXX (Septuagint) references

### BDB Hebrew Lexicon
**License:** Public Domain
**Source:** https://github.com/openscriptures/HebrewLexicon
**Format:** XML

**What's Included:**
- Brown-Driver-Briggs Hebrew lexicon
- Etymology, definitions, usage notes
- Comprehensive classical Hebrew dictionary

---

## Cross-References

### OpenBible.info Cross-References
**License:** CC BY 4.0
**Repository:** https://github.com/openbibleinfo/Bible-Cross-Reference-Data
**Format:** TSV

**What's Included:**
- 63,779 cross-references
- Confidence scores (vote-based)
- Categorized by type

**Download:**
```bash
git clone https://github.com/openbibleinfo/Bible-Cross-Reference-Data.git
cd Bible-Cross-Reference-Data
# File: cross_references.txt
```

**Sample Format:**
```tsv
Gen.1.1	John.1.1	38	Genesis 1:1 → John 1:1 (38 votes)
Gen.1.26	Gen.3.22	14	Genesis 1:26 → Genesis 3:22 (14 votes)
```

---

## English Translations (Public Domain)

### King James Version (KJV)
**Year:** 1611 (public domain)
**Format:** Widely available in plain text, XML, JSON
**Source:** https://github.com/scrollmapper/bible_databases

### American Standard Version (ASV)
**Year:** 1901 (public domain)
**Format:** Plain text, XML

### World English Bible (WEB)
**License:** Public domain
**Website:** https://worldenglish.bible/
**Format:** USFM, OSIS, plain text

### Young's Literal Translation (YLT)
**Year:** 1898 (public domain)
**Format:** Plain text

---

## Ingestion Scripts

### Recommended Data Processing Pipeline

```python
# Example: Ingest OSHB Hebrew data
import xml.etree.ElementTree as ET
from pathlib import Path

def parse_oshb_xml(file_path: Path):
    """Parse OSHB XML and extract verse words with morphology."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    for verse in root.findall('.//verse'):
        verse_id = verse.get('osisID')  # e.g., "Gen.1.1"

        for word in verse.findall('.//w'):
            yield {
                'verse_osis': verse_id,
                'surface_form': word.text,
                'lemma': word.get('lemma'),
                'morphology': word.get('morph'),
                'strongs': word.get('strong'),
            }

# Usage:
for book_file in Path('morphhb/wlc/').glob('*.xml'):
    for word_data in parse_oshb_xml(book_file):
        # Insert into database
        pass
```

### Cross-Reference Import

```python
def parse_openbible_crossrefs(file_path: Path):
    """Parse OpenBible cross-reference TSV."""
    with open(file_path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                yield {
                    'source_osis': parts[0],
                    'target_osis': parts[1],
                    'votes': int(parts[2]),
                    'confidence': int(parts[2]) / 100.0,  # Normalize
                }
```

---

## Database Schema Recommendations

### Verse Words Table
```sql
CREATE TABLE verse_words (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verse_osis VARCHAR(32) NOT NULL,
    word_position INT NOT NULL,
    surface_form VARCHAR(64) NOT NULL,
    lemma VARCHAR(64),
    strongs_number VARCHAR(16),
    morphology_code VARCHAR(32),
    language VARCHAR(2) CHECK (language IN ('he', 'gr')),

    UNIQUE (verse_osis, word_position, language),
    INDEX idx_verse_words_osis (verse_osis),
    INDEX idx_verse_words_strongs (strongs_number)
);
```

### Lexicon Entries Table
```sql
CREATE TABLE lexicon_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strongs_number VARCHAR(16) UNIQUE NOT NULL,
    language VARCHAR(2) NOT NULL CHECK (language IN ('he', 'gr')),
    lemma VARCHAR(64) NOT NULL,
    transliteration VARCHAR(128),
    short_definition TEXT,
    long_definition TEXT,
    derivation TEXT,

    INDEX idx_lexicon_strongs (strongs_number),
    INDEX idx_lexicon_lemma (lemma)
);
```

### Cross-References Table
```sql
CREATE TABLE cross_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_osis VARCHAR(32) NOT NULL,
    target_osis VARCHAR(32) NOT NULL,
    reference_type VARCHAR(32) DEFAULT 'general',
    confidence FLOAT,
    votes INT,
    direction VARCHAR(16) DEFAULT 'bidirectional',

    INDEX idx_crossref_source (source_osis),
    INDEX idx_crossref_target (target_osis),
    UNIQUE (source_osis, target_osis)
);
```

---

## Licensing Summary

| Resource | License | Commercial Use | Attribution Required | Redistribution Allowed |
|----------|---------|----------------|----------------------|------------------------|
| OSHB | CC BY 4.0 | Yes | Yes | Yes |
| SBLGNT | CC BY 4.0 | Personal use | Yes | With permission |
| Strong's | Public Domain | Yes | No | Yes |
| OpenBible Cross-Refs | CC BY 4.0 | Yes | Yes | Yes |
| KJV, ASV, WEB, YLT | Public Domain | Yes | No | Yes |
| Berean Interlinear | Public Domain | Yes | No | Yes |

**Note:** For hobby/personal use, all of these resources are completely free and unrestricted. Attribution is good practice even when not required.

---

## Data Size Estimates

| Resource | Compressed Size | Uncompressed | Database Size |
|----------|----------------|--------------|---------------|
| OSHB (Hebrew OT) | ~15 MB | ~60 MB | ~150 MB (with indexes) |
| SBLGNT (Greek NT) | ~2 MB | ~8 MB | ~25 MB |
| Strong's Lexicon | ~3 MB | ~12 MB | ~20 MB |
| OpenBible Cross-Refs | ~2 MB | ~5 MB | ~15 MB |
| KJV Text | ~4 MB | ~5 MB | ~10 MB |
| **Total Estimate** | **~26 MB** | **~90 MB** | **~220 MB** |

**With all translations and lexicons:** ~500 MB - 1 GB total database size

---

## Quick Start Commands

### One-Liner Download All Resources
```bash
#!/bin/bash
# Download all free biblical language resources

mkdir -p data/biblical-languages
cd data/biblical-languages

# Hebrew OT
git clone --depth 1 https://github.com/openscriptures/morphhb.git

# Greek NT
git clone --depth 1 https://github.com/LogosBible/SBLGNT.git

# Lexicons
git clone --depth 1 https://github.com/openscriptures/strongs.git

# Cross-references
git clone --depth 1 https://github.com/openbibleinfo/Bible-Cross-Reference-Data.git

echo "Download complete! All resources in $(pwd)"
```

---

## Further Reading

### Documentation
- OSHB Format Guide: https://hb.openscriptures.org/
- SBLGNT Morphology Codes: https://github.com/morphgnt/sblgnt/blob/master/README.md
- Strong's Number System: https://en.wikipedia.org/wiki/Strong%27s_Concordance

### Community
- Open Scriptures Project: https://openscriptures.org/
- Bible Technologies Group: https://bibleteach.com/

---

**Last Verified:** 2025-11-27
**Next Review:** Check for repository updates quarterly
