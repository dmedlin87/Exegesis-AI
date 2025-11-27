# Features 1-3: Core Research Capabilities

## 1. Parallel Translation Viewer

### Overview

Side-by-side comparison of 2-4 Bible translations with synchronized scrolling and diff highlighting for textual variants.

### Database Schema

```sql
CREATE TABLE translations (
    id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,        -- 'ESV', 'NIV', 'KJV'
    name VARCHAR(128) NOT NULL,
    language VARCHAR(8) DEFAULT 'en',
    copyright_notice TEXT,
    is_public_domain BOOLEAN DEFAULT FALSE,
    word_for_word_score FLOAT,               -- 1.0=literal, 0.0=paraphrase
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE verses ADD COLUMN translation_id VARCHAR(36) REFERENCES translations(id);
CREATE INDEX ix_verses_osis_translation ON verses(osis_ref, translation_id);
```

### API Specification

**Endpoint:** `GET /verses/parallel`

```python
@router.get("/parallel", response_model=ParallelVerseResponse)
def parallel_verses(
    osis: str = Query(..., description="OSIS reference (e.g., 'John.3.16')"),
    translations: list[str] = Query(default=["ESV", "NIV"], max_length=4),
    include_diff: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> ParallelVerseResponse:
    """Return verse text across multiple translations with optional diff."""
```

**Response Schema:**

```python
class TranslationVerse(BaseModel):
    translation_code: str
    translation_name: str
    text: str
    word_tokens: list[str]

class VerseVariant(BaseModel):
    word_index: int
    variants: dict[str, str]  # translation_code -> word

class ParallelVerseResponse(BaseModel):
    osis: str
    reference_display: str
    translations: list[TranslationVerse]
    variants: list[VerseVariant]
    alignment_matrix: list[list[int | None]]
```

### Application Service

**File:** `exegesis/application/canon/parallel_service.py`

```python
class ParallelTranslationService:
    def __init__(self, verse_repository: VerseRepository):
        self._verse_repo = verse_repository

    def fetch_parallel(
        self, osis: str, translation_codes: list[str]
    ) -> list[TranslationVerse]:
        """Fetch verse text from multiple translations."""
        results = []
        for code in translation_codes:
            verse = self._verse_repo.get_by_osis_and_translation(osis, code)
            if verse:
                results.append(TranslationVerse(
                    translation_code=code,
                    translation_name=verse.translation.name,
                    text=verse.text,
                    word_tokens=self._tokenize(verse.text),
                ))
        return results

    def compute_word_alignment(
        self, verses: list[TranslationVerse]
    ) -> tuple[list[VerseVariant], list[list[int | None]]]:
        """
        Use Needleman-Wunsch sequence alignment to align words
        and identify textual variants.
        """
        if len(verses) < 2:
            return [], []

        # Build alignment matrix using dynamic programming
        base_tokens = verses[0].word_tokens
        alignment_matrix = []
        variants = []

        for i, base_word in enumerate(base_tokens):
            row = [i]  # Position in base translation
            word_variants = {}

            for other in verses[1:]:
                aligned_idx = self._find_aligned_word(
                    base_word, i, other.word_tokens
                )
                row.append(aligned_idx)
                if aligned_idx is not None:
                    other_word = other.word_tokens[aligned_idx]
                    if other_word.lower() != base_word.lower():
                        word_variants[other.translation_code] = other_word

            alignment_matrix.append(row)
            if word_variants:
                word_variants[verses[0].translation_code] = base_word
                variants.append(VerseVariant(word_index=i, variants=word_variants))

        return variants, alignment_matrix

    def _tokenize(self, text: str) -> list[str]:
        """Split text into word tokens, preserving punctuation."""
        import re
        return re.findall(r'\b\w+\b|[^\w\s]', text)

    def _find_aligned_word(
        self, target: str, target_idx: int, candidates: list[str]
    ) -> int | None:
        """Find best matching word in candidate list."""
        # Simple heuristic: look within ±3 positions first
        search_range = range(
            max(0, target_idx - 3),
            min(len(candidates), target_idx + 4)
        )
        for i in search_range:
            if candidates[i].lower() == target.lower():
                return i
        return None
```

### Frontend Components

**Directory:** `exegesis/services/web/app/components/ParallelViewer/`

```
ParallelViewer/
├── index.tsx                    # Main container
├── TranslationColumn.tsx        # Single translation pane
├── SyncScrollProvider.tsx       # Synchronized scroll context
├── VariantHighlight.tsx         # Diff highlighting
├── TranslationSelector.tsx      # Add/remove translations
└── hooks/
    ├── useParallelVerses.ts
    └── useSyncScroll.ts
```

**Key Component: SyncScrollProvider.tsx**

```tsx
import { createContext, useContext, useRef, useCallback } from 'react';

interface SyncScrollContextValue {
  registerColumn: (id: string, ref: HTMLDivElement) => void;
  handleScroll: (sourceId: string, scrollTop: number) => void;
}

const SyncScrollContext = createContext<SyncScrollContextValue | null>(null);

export function SyncScrollProvider({ children }: { children: React.ReactNode }) {
  const columnsRef = useRef<Map<string, HTMLDivElement>>(new Map());
  const isScrollingRef = useRef(false);

  const registerColumn = useCallback((id: string, ref: HTMLDivElement) => {
    columnsRef.current.set(id, ref);
  }, []);

  const handleScroll = useCallback((sourceId: string, scrollTop: number) => {
    if (isScrollingRef.current) return;
    isScrollingRef.current = true;

    columnsRef.current.forEach((el, id) => {
      if (id !== sourceId) {
        el.scrollTop = scrollTop;
      }
    });

    requestAnimationFrame(() => {
      isScrollingRef.current = false;
    });
  }, []);

  return (
    <SyncScrollContext.Provider value={{ registerColumn, handleScroll }}>
      {children}
    </SyncScrollContext.Provider>
  );
}

export const useSyncScroll = () => useContext(SyncScrollContext);
```

### Testing

```python
# tests/application/canon/test_parallel_service.py

def test_fetch_parallel_returns_all_translations(parallel_service, sample_verses):
    result = parallel_service.fetch_parallel("John.3.16", ["ESV", "NIV", "KJV"])
    assert len(result) == 3
    assert all(v.text for v in result)

def test_word_alignment_detects_variants(parallel_service):
    verses = [
        TranslationVerse(code="ESV", text="For God so loved the world"),
        TranslationVerse(code="KJV", text="For God so loved the world"),
    ]
    variants, matrix = parallel_service.compute_word_alignment(verses)
    assert len(matrix) == 6  # 6 words

def test_word_alignment_handles_insertions(parallel_service):
    verses = [
        TranslationVerse(code="A", text="the quick fox"),
        TranslationVerse(code="B", text="the very quick brown fox"),
    ]
    variants, _ = parallel_service.compute_word_alignment(verses)
    # Should detect "very" and "brown" as variants
    assert len(variants) >= 1
```

---

## 2. Original Language Toolkit

### Overview

Hebrew/Greek morphology parsing, interlinear display, and Strong's concordance integration.

### Database Schema

```sql
CREATE TABLE lexicon_entries (
    id VARCHAR(36) PRIMARY KEY,
    strongs_number VARCHAR(10) UNIQUE NOT NULL,  -- 'H1234', 'G5678'
    language VARCHAR(8) NOT NULL,                 -- 'hebrew', 'greek'
    lemma VARCHAR(64) NOT NULL,
    transliteration VARCHAR(64),
    pronunciation VARCHAR(128),
    short_definition VARCHAR(256),
    full_definition TEXT,
    usage_notes TEXT,
    semantic_domain VARCHAR(128),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE verse_words (
    id VARCHAR(36) PRIMARY KEY,
    verse_id VARCHAR(36) REFERENCES verses(id),
    word_position INTEGER NOT NULL,
    surface_form VARCHAR(64) NOT NULL,
    lemma VARCHAR(64),
    strongs_id VARCHAR(36) REFERENCES lexicon_entries(id),
    morphology_code VARCHAR(32),                 -- 'V-AAI-3S'
    transliteration VARCHAR(64),
    gloss VARCHAR(128),
    UNIQUE(verse_id, word_position)
);

CREATE INDEX ix_verse_words_strongs ON verse_words(strongs_id);
CREATE INDEX ix_verse_words_lemma ON verse_words(lemma);

CREATE TABLE morphology_codes (
    code VARCHAR(32) PRIMARY KEY,
    language VARCHAR(8) NOT NULL,
    part_of_speech VARCHAR(32),
    tense VARCHAR(32),
    voice VARCHAR(32),
    mood VARCHAR(32),
    person VARCHAR(16),
    number VARCHAR(16),
    gender VARCHAR(16),
    case_type VARCHAR(16),
    description VARCHAR(256)
);
```

### API Specification

**Endpoint:** `GET /verses/{osis}/interlinear`

```python
@router.get("/{osis}/interlinear", response_model=InterlinearVerseResponse)
def interlinear_verse(
    osis: str,
    include_morphology: bool = Query(default=True),
    include_strongs: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> InterlinearVerseResponse:
    """Return word-by-word breakdown with morphology and Strong's."""
```

**Endpoint:** `GET /lexicon/{strongs_number}`

```python
@router.get("/{strongs_number}", response_model=LexiconEntryResponse)
def lexicon_entry(
    strongs_number: str = Path(..., pattern=r"^[HG]\d{1,5}$"),
    include_occurrences: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> LexiconEntryResponse:
    """Return full lexicon entry."""
```

**Response Schemas:**

```python
class InterlinearWord(BaseModel):
    position: int
    surface_form: str
    transliteration: str
    lemma: str
    strongs_number: str | None
    gloss: str
    morphology: MorphologyBreakdown | None

class MorphologyBreakdown(BaseModel):
    code: str
    part_of_speech: str
    tense: str | None
    voice: str | None
    mood: str | None
    person: str | None
    number: str | None
    gender: str | None
    case_type: str | None
    description: str

class InterlinearVerseResponse(BaseModel):
    osis: str
    reference_display: str
    language: str
    words: list[InterlinearWord]
    english_translation: str

class LexiconEntryResponse(BaseModel):
    strongs_number: str
    language: str
    lemma: str
    transliteration: str
    pronunciation: str | None
    short_definition: str
    full_definition: str
    usage_notes: str | None
    semantic_domain: str | None
    occurrence_count: int
    sample_verses: list[str] | None
```

### Application Service

**File:** `exegesis/application/canon/morphology_parser.py`

```python
HEBREW_MORPHOLOGY = {
    "parts": {"V": "Verb", "N": "Noun", "A": "Adjective", "P": "Pronoun", ...},
    "stems": {"Q": "Qal", "N": "Niphal", "P": "Piel", "Pu": "Pual", "H": "Hiphil", ...},
    "conjugations": {"p": "Perfect", "i": "Imperfect", "w": "Consecutive", ...},
    "persons": {"1": "1st", "2": "2nd", "3": "3rd"},
    "numbers": {"s": "Singular", "p": "Plural", "d": "Dual"},
    "genders": {"m": "Masculine", "f": "Feminine", "c": "Common"},
}

GREEK_MORPHOLOGY = {
    "parts": {"V": "Verb", "N": "Noun", "A": "Adjective", "D": "Adverb", ...},
    "tenses": {"P": "Present", "I": "Imperfect", "F": "Future", "A": "Aorist", ...},
    "voices": {"A": "Active", "M": "Middle", "P": "Passive"},
    "moods": {"I": "Indicative", "S": "Subjunctive", "O": "Optative", ...},
    "cases": {"N": "Nominative", "G": "Genitive", "D": "Dative", "A": "Accusative"},
}

def parse_morphology(code: str, language: str) -> MorphologyBreakdown:
    """Parse morphology code into human-readable breakdown."""
    schema = HEBREW_MORPHOLOGY if language == "hebrew" else GREEK_MORPHOLOGY

    result = MorphologyBreakdown(code=code)

    # Parse based on language-specific format
    if language == "greek":
        # Format: V-PAI-3S (Part-Tense/Mood/Voice-Person/Number)
        parts = code.split("-")
        if len(parts) >= 1:
            result.part_of_speech = schema["parts"].get(parts[0], parts[0])
        if len(parts) >= 2:
            result.tense = schema["tenses"].get(parts[1][0], None)
            result.voice = schema["voices"].get(parts[1][1], None) if len(parts[1]) > 1 else None
            result.mood = schema["moods"].get(parts[1][2], None) if len(parts[1]) > 2 else None
        if len(parts) >= 3:
            result.person = schema.get("persons", {}).get(parts[2][0], None)
            result.number = schema.get("numbers", {}).get(parts[2][1], None) if len(parts[2]) > 1 else None

    # Build description
    result.description = " ".join(filter(None, [
        result.tense, result.voice, result.mood,
        result.person, result.number, result.part_of_speech
    ]))

    return result
```

### Frontend Components

**Directory:** `exegesis/services/web/app/components/Interlinear/`

```tsx
// WordCard.tsx
interface WordCardProps {
  word: InterlinearWord;
  onStrongsClick: (strongs: string) => void;
}

export function WordCard({ word, onStrongsClick }: WordCardProps) {
  return (
    <div className="flex flex-col items-center p-2 border rounded hover:bg-gray-50">
      <span className="text-xl font-hebrew">{word.surface_form}</span>
      <span className="text-sm text-gray-500">{word.transliteration}</span>
      {word.strongs_number && (
        <button
          onClick={() => onStrongsClick(word.strongs_number!)}
          className="text-xs text-blue-600 hover:underline"
        >
          {word.strongs_number}
        </button>
      )}
      {word.morphology && (
        <Tooltip content={word.morphology.description}>
          <span className="text-xs bg-gray-100 px-1 rounded">
            {word.morphology.code}
          </span>
        </Tooltip>
      )}
      <span className="text-sm font-medium">{word.gloss}</span>
    </div>
  );
}
```

---

## 3. Cross-Reference Graph

### Overview

Interactive visualization showing verse cross-references with expandable nodes.

### Database Schema

```sql
CREATE TABLE cross_references (
    id VARCHAR(36) PRIMARY KEY,
    source_osis VARCHAR(32) NOT NULL,
    target_osis VARCHAR(32) NOT NULL,
    reference_type VARCHAR(32) NOT NULL,        -- 'quotation', 'allusion', 'echo'
    confidence FLOAT DEFAULT 1.0,
    direction VARCHAR(16) DEFAULT 'forward',
    source VARCHAR(64),                         -- 'treasury', 'user', 'ai'
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_cross_refs_source ON cross_references(source_osis);
CREATE INDEX ix_cross_refs_target ON cross_references(target_osis);

CREATE TABLE thematic_clusters (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    theme_tags JSONB DEFAULT '[]'
);

CREATE TABLE cluster_verses (
    cluster_id VARCHAR(36) REFERENCES thematic_clusters(id),
    osis VARCHAR(32) NOT NULL,
    relevance_score FLOAT DEFAULT 1.0,
    PRIMARY KEY (cluster_id, osis)
);
```

### API Specification

**Endpoint:** `GET /graph/verse-network`

```python
@router.get("/verse-network", response_model=VerseNetworkResponse)
def verse_network(
    center_osis: str = Query(...),
    radius: int = Query(default=2, ge=1, le=4),
    max_nodes: int = Query(default=50, le=200),
    reference_types: list[str] | None = Query(default=None),
    min_confidence: float = Query(default=0.5),
    session: Session = Depends(get_session),
) -> VerseNetworkResponse:
    """Return graph data for D3 visualization."""
```

**Response Schema:**

```python
class GraphNode(BaseModel):
    id: str                      # OSIS reference
    label: str                   # "John 3:16"
    book: str
    chapter: int
    verse: int
    testament: str               # 'OT' or 'NT'
    preview_text: str
    connection_count: int

class GraphEdge(BaseModel):
    source: str
    target: str
    reference_type: str
    confidence: float
    direction: str

class VerseNetworkResponse(BaseModel):
    center: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[dict]
```

### Application Service

**File:** `exegesis/application/research/cross_reference_service.py`

```python
from collections import deque

class CrossReferenceService:
    def __init__(self, cross_ref_repository: CrossReferenceRepository):
        self._repo = cross_ref_repository

    def build_network_graph(
        self,
        center_osis: str,
        radius: int,
        max_nodes: int,
        min_confidence: float = 0.5,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Build subgraph using BFS from center verse."""
        visited = set()
        nodes = []
        edges = []
        queue = deque([(center_osis, 0)])

        while queue and len(nodes) < max_nodes:
            current_osis, depth = queue.popleft()

            if current_osis in visited:
                continue
            visited.add(current_osis)

            # Add node
            verse_info = self._get_verse_info(current_osis)
            nodes.append(GraphNode(
                id=current_osis,
                label=verse_info.display_reference,
                book=verse_info.book,
                chapter=verse_info.chapter,
                verse=verse_info.verse,
                testament=verse_info.testament,
                preview_text=verse_info.text[:100],
                connection_count=0,  # Updated later
            ))

            # Get references if within radius
            if depth < radius:
                refs = self._repo.get_references(
                    current_osis,
                    min_confidence=min_confidence,
                )
                for ref in refs:
                    target = ref.target_osis if ref.source_osis == current_osis else ref.source_osis

                    edges.append(GraphEdge(
                        source=ref.source_osis,
                        target=ref.target_osis,
                        reference_type=ref.reference_type,
                        confidence=ref.confidence,
                        direction=ref.direction,
                    ))

                    if target not in visited:
                        queue.append((target, depth + 1))

        # Update connection counts
        connection_counts = {}
        for edge in edges:
            connection_counts[edge.source] = connection_counts.get(edge.source, 0) + 1
            connection_counts[edge.target] = connection_counts.get(edge.target, 0) + 1

        for node in nodes:
            node.connection_count = connection_counts.get(node.id, 0)

        return nodes, edges
```

### Frontend Components

**File:** `exegesis/services/web/app/components/CrossRefGraph/ForceGraph.tsx`

```tsx
import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface ForceGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick: (node: GraphNode) => void;
  onNodeHover: (node: GraphNode | null) => void;
}

export function ForceGraph({ nodes, edges, onNodeClick, onNodeHover }: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !nodes.length) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Clear previous
    svg.selectAll('*').remove();

    // Create simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges as any)
        .id((d: any) => d.id)
        .distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2));

    // Draw edges
    const link = svg.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', d => getEdgeColor(d.reference_type))
      .attr('stroke-width', d => d.confidence * 2)
      .attr('stroke-dasharray', d =>
        d.reference_type === 'allusion' ? '5,5' :
        d.reference_type === 'echo' ? '2,2' : 'none'
      );

    // Draw nodes
    const node = svg.append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', d => 5 + Math.sqrt(d.connection_count) * 3)
      .attr('fill', d => d.testament === 'OT' ? '#D97706' : '#2563EB')
      .attr('cursor', 'pointer')
      .on('click', (event, d) => onNodeClick(d))
      .on('mouseenter', (event, d) => onNodeHover(d))
      .on('mouseleave', () => onNodeHover(null))
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Labels
    const label = svg.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text(d => d.label)
      .attr('font-size', 10)
      .attr('dx', 12)
      .attr('dy', 4);

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
      label.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y);
    });

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => simulation.stop();
  }, [nodes, edges]);

  return <svg ref={svgRef} className="w-full h-full" />;
}

function getEdgeColor(type: string): string {
  switch (type) {
    case 'quotation': return '#DC2626';
    case 'allusion': return '#F59E0B';
    case 'echo': return '#9CA3AF';
    default: return '#6B7280';
  }
}
```

### Data Seeding

**File:** `data/seeds/cross_references.yaml`

```yaml
# Treasury of Scripture Knowledge (public domain)
cross_references:
  - source: Gen.1.1
    targets:
      - osis: John.1.1
        type: allusion
        confidence: 0.95
      - osis: Heb.11.3
        type: thematic
        confidence: 0.9
      - osis: Ps.33.6
        type: thematic
        confidence: 0.85

  - source: Matt.5.17
    targets:
      - osis: Rom.3.31
        type: thematic
        confidence: 0.9
      - osis: Rom.10.4
        type: thematic
        confidence: 0.85
      - osis: Gal.3.24
        type: thematic
        confidence: 0.8
```

### Testing

```python
# tests/application/research/test_cross_reference_service.py

def test_build_network_respects_radius(service, populated_refs):
    nodes, edges = service.build_network_graph("John.3.16", radius=1, max_nodes=100)
    # All nodes should be at most 1 hop from center
    center_refs = {e.target for e in edges if e.source == "John.3.16"}
    center_refs |= {e.source for e in edges if e.target == "John.3.16"}
    for node in nodes:
        if node.id != "John.3.16":
            assert node.id in center_refs

def test_build_network_respects_max_nodes(service, large_ref_graph):
    nodes, _ = service.build_network_graph("Gen.1.1", radius=4, max_nodes=20)
    assert len(nodes) <= 20

def test_build_network_no_cycles(service, cyclic_refs):
    nodes, edges = service.build_network_graph("A", radius=10, max_nodes=100)
    # Should not hang or duplicate nodes
    assert len(nodes) == len(set(n.id for n in nodes))
```
