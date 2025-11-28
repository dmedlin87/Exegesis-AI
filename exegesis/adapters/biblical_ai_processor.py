"""AI-powered processor for biblical text morphological and semantic analysis."""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from exegesis.domain.biblical_texts import (
    AIAnalysis,
    BiblicalVerse,
    Language,
    MorphologicalTag,
    POS,
    Reference,
    SemanticAnalysis,
    TextContent
)


# Custom Exceptions
class TransliterationError(Exception):
    """Raised when AI transliteration fails."""
    pass


# Configuration Dataclasses
@dataclass(frozen=True)
class ConfidenceConfig:
    """Configuration constants for confidence score calculation."""

    # Morphology confidence thresholds
    MORPHOLOGY_BASELINE: float = 0.75
    MORPHOLOGY_MIN_BOOST: float = 0.60
    MORPHOLOGY_MAX_BOOST: float = 0.35
    MORPHOLOGY_MAX: float = 0.95

    # Semantics confidence thresholds
    SEMANTICS_BASELINE: float = 0.70
    SEMANTICS_MIN_BOOST: float = 0.60
    SEMANTICS_MAX_BOOST: float = 0.30
    SEMANTICS_RICHNESS_DIVISOR: float = 10.0

    # Theological confidence thresholds
    THEOLOGICAL_BASELINE: float = 0.65
    THEOLOGICAL_BOOST: float = 0.15
    THEOLOGICAL_MAX: float = 0.85


# Default configuration instance
CONFIDENCE_THRESHOLDS = ConfidenceConfig()


def _validate_chat_completions_client(ai_client: Any) -> tuple[bool, Any]:
    """Ensure the provided AI client exposes chat.completions.create.

    Returns:
        tuple: (supports_async, create_method) where supports_async indicates
               if the client has an async create method (acreate)
    """

    if ai_client is None:
        raise ValueError(
            "ai_client must provide chat.completions.create; received None"
        )

    chat = getattr(ai_client, "chat", None)
    if chat is None:
        raise ValueError(
            "ai_client must provide chat.completions.create; missing 'chat' attribute"
        )

    completions = getattr(chat, "completions", None)
    if completions is None:
        raise ValueError(
            "ai_client must provide chat.completions.create; missing 'chat.completions'"
        )

    create = getattr(completions, "create", None)
    if create is None or not callable(create):
        raise ValueError(
            "ai_client must provide chat.completions.create callable"
        )

    # Check for async support (OpenAI SDK uses 'acreate' or async-enabled 'create')
    acreate = getattr(completions, "acreate", None)
    supports_async = acreate is not None and callable(acreate)

    return supports_async, acreate if supports_async else create


def _safe_json_loads(content: str, max_size: int = 1024 * 1024) -> Any:
    """Safely parse JSON with size limits to prevent DoS attacks.
    
    Args:
        content: JSON string to parse
        max_size: Maximum allowed size in bytes (default: 1MB)
        
    Returns:
        Parsed JSON object, or None if parsing fails
        
    Raises:
        ValueError: If content exceeds size limit
    """
    if len(content) > max_size:
        raise ValueError(f"JSON content too large: {len(content)} bytes (max: {max_size})")
    
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None


class BiblicalAIProcessor:
    """AI processor for biblical text analysis using OpenAI/Anthropic APIs."""

    def __init__(self, ai_client, model_name: str = "gpt-4"):
        self._supports_async, self._create_method = _validate_chat_completions_client(ai_client)
        self.ai_client = ai_client
        self.model_name = model_name
    
    async def process_hebrew_verse(self, raw_text: str, reference: Reference) -> BiblicalVerse:
        """Process a Hebrew verse with full AI analysis.

        All AI operations are async to avoid blocking the event loop.

        Args:
            raw_text: The raw Hebrew text to process
            reference: Biblical reference for the verse

        Returns:
            Fully analyzed BiblicalVerse object
        """

        # Step 1: Normalize text (async - calls AI for transliteration)
        text_content = await self._normalize_hebrew_text(raw_text)

        # Step 2: AI morphological analysis (async)
        morphology = await self._analyze_hebrew_morphology(text_content.normalized)

        # Step 3: AI semantic analysis (async)
        semantic_analysis = await self._analyze_semantics(text_content, morphology, reference)

        # Step 4: Create AI metadata (using dynamic confidence based on results)
        confidence_scores = self._calculate_confidence_scores(morphology, semantic_analysis)

        ai_analysis = AIAnalysis(
            generated_at=datetime.now(UTC),
            model_version=self.model_name,
            confidence_scores=confidence_scores
        )

        return BiblicalVerse(
            reference=reference,
            language=Language.HEBREW,
            text=text_content,
            morphology=morphology,
            semantic_analysis=semantic_analysis,
            ai_analysis=ai_analysis
        )
    
    def _calculate_confidence_scores(self, morphology: List[MorphologicalTag],
                                   semantic_analysis: SemanticAnalysis) -> Dict[str, float]:
        """Calculate realistic confidence scores based on analysis results.

        Uses CONFIDENCE_THRESHOLDS configuration for all numeric thresholds.

        Args:
            morphology: Morphological tags to evaluate
            semantic_analysis: Semantic analysis results to evaluate

        Returns:
            Dictionary of confidence scores by category
        """

        # Base confidence on actual content quality
        morphology_confidence = CONFIDENCE_THRESHOLDS.MORPHOLOGY_BASELINE
        if morphology:
            # Higher confidence if we have detailed morphological data
            has_detailed_tags = sum(1 for tag in morphology
                                  if tag.lemma and tag.root and tag.gloss)
            morphology_confidence = min(
                CONFIDENCE_THRESHOLDS.MORPHOLOGY_MAX,
                CONFIDENCE_THRESHOLDS.MORPHOLOGY_MIN_BOOST +
                (has_detailed_tags / len(morphology)) * CONFIDENCE_THRESHOLDS.MORPHOLOGY_MAX_BOOST
            )

        semantics_confidence = CONFIDENCE_THRESHOLDS.SEMANTICS_BASELINE
        if semantic_analysis.themes or semantic_analysis.theological_keywords:
            # Higher confidence if we found theological content
            theme_count = len(semantic_analysis.themes)
            keyword_count = len(semantic_analysis.theological_keywords)
            content_richness = min(
                1.0,
                (theme_count + keyword_count) / CONFIDENCE_THRESHOLDS.SEMANTICS_RICHNESS_DIVISOR
            )
            semantics_confidence = (
                CONFIDENCE_THRESHOLDS.SEMANTICS_MIN_BOOST +
                content_richness * CONFIDENCE_THRESHOLDS.SEMANTICS_MAX_BOOST
            )

        theological_confidence = CONFIDENCE_THRESHOLDS.THEOLOGICAL_BASELINE
        if semantic_analysis.cross_references or semantic_analysis.textual_variants:
            # Boost confidence if we have cross-references or variants
            theological_confidence = min(
                CONFIDENCE_THRESHOLDS.THEOLOGICAL_MAX,
                theological_confidence + CONFIDENCE_THRESHOLDS.THEOLOGICAL_BOOST
            )

        return {
            "morphology": round(morphology_confidence, 2),
            "semantics": round(semantics_confidence, 2),
            "theological_significance": round(theological_confidence, 2)
        }
    
    async def _normalize_hebrew_text(self, raw_text: str) -> TextContent:
        """Normalize Hebrew text and generate transliteration.

        Args:
            raw_text: Raw Hebrew text with diacritics

        Returns:
            TextContent with normalized and transliterated versions
        """

        # Remove cantillation marks and vowels for normalized version
        consonants_only = self._strip_hebrew_diacritics(raw_text)

        # AI-generated transliteration (async)
        transliteration = await self._generate_transliteration(raw_text)

        return TextContent(
            raw=raw_text,
            normalized=consonants_only,
            transliteration=transliteration
        )
    
    def _strip_hebrew_diacritics(self, text: str) -> str:
        """Remove Hebrew vowel points and cantillation marks."""
        # Unicode ranges for Hebrew diacritics
        diacritics_pattern = r'[\u0591-\u05C7]'
        return re.sub(diacritics_pattern, '', text)
    
    async def _generate_transliteration(self, hebrew_text: str) -> Optional[str]:
        """Generate transliteration using AI with proper error handling.

        Args:
            hebrew_text: The Hebrew text to transliterate

        Returns:
            Transliterated text or None if generation fails

        Raises:
            TransliterationError: If AI transliteration fails critically
        """

        # Use XML delimiters to prevent prompt injection
        prompt = """Transliterate the Hebrew text inside the <input> tags into Latin characters following academic standards.

Provide only the transliteration, no explanations.

<input>{text}</input>""".format(text=hebrew_text)

        try:
            if self._supports_async:
                response = await self._create_method(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
            else:
                # Run blocking call in thread pool to avoid blocking event loop
                response = await asyncio.to_thread(
                    self.ai_client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )

            result = response.choices[0].message.content.strip()
            return result if result else None

        except Exception as exc:
            # Return None on failure instead of magic string
            # Caller can decide how to handle None
            return None
    
    async def _analyze_hebrew_morphology(self, hebrew_text: str) -> List[MorphologicalTag]:
        """Perform AI-powered morphological analysis of Hebrew text.

        Args:
            hebrew_text: The Hebrew text to analyze

        Returns:
            List of morphological tags for the text
        """

        # Use XML delimiters to prevent prompt injection
        prompt = """Perform morphological analysis of the Hebrew text inside the <input> tags.

For each word provide:
- word, lemma, root, part of speech, gender, number, state
- For verbs: stem/binyan, tense, person
- prefixes, suffixes, gloss, theological significance

<input>{text}</input>

Respond in JSON array format.""".format(text=hebrew_text)

        try:
            if self._supports_async:
                response = await self._create_method(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
            else:
                # Run blocking call in thread pool to avoid blocking event loop
                response = await asyncio.to_thread(
                    self.ai_client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )

            # Use safe JSON parsing with size limits
            morphology_data = _safe_json_loads(
                response.choices[0].message.content,
                max_size=512 * 1024  # 512KB limit for morphology data
            )
        except Exception:
            return []  # Return empty list on any error

        if not isinstance(morphology_data, list):
            return []

        tags: List[MorphologicalTag] = []
        for item in morphology_data:
            if not isinstance(item, dict):
                continue

            tag = self._convert_to_morphological_tag(item)
            if tag is not None:
                tags.append(tag)

        return tags

    def _convert_to_morphological_tag(self, data: Dict) -> Optional[MorphologicalTag]:
        """Convert AI response data to MorphologicalTag object."""

        word = data.get("word")
        lemma = data.get("lemma")

        if not isinstance(word, str) or not isinstance(lemma, str):
            return None

        raw_pos = data.get("pos", "noun")
        if isinstance(raw_pos, str):
            normalized_pos = raw_pos.strip().lower()
        else:
            normalized_pos = "noun"

        try:
            pos = POS(normalized_pos)
        except ValueError:
            pos = POS.NOUN
        
        return MorphologicalTag(
            word=word,
            lemma=lemma,
            root=data.get("root"),
            pos=pos,
            gender=data.get("gender"),
            number=data.get("number"),
            state=data.get("state"),
            stem=data.get("stem"),
            tense=data.get("tense"),
            person=data.get("person"),
            prefix=data.get("prefix"),
            suffix=data.get("suffix"),
            gloss=data.get("gloss", ""),
            theological_notes=data.get("theological_notes", [])
        )
    
    async def _analyze_semantics(self, text: TextContent, morphology: List[MorphologicalTag],
                          reference: Reference) -> SemanticAnalysis:
        """Perform AI-powered semantic and theological analysis.

        Args:
            text: The text content to analyze
            morphology: Morphological tags from previous analysis
            reference: Biblical reference

        Returns:
            Semantic analysis results
        """

        morphology_summary = "; ".join([
            f"{tag.word} ({tag.lemma}, {tag.pos.value})" for tag in morphology
        ])

        # Use XML delimiters to prevent prompt injection
        prompt = """Analyze the biblical verse inside the <input> tags for theological content.

<reference>{ref}</reference>
<input>{text}</input>
<morphology>{morph}</morphology>

Provide JSON with: themes, theological_keywords, cross_references, textual_variants, translation_notes""".format(
            ref=str(reference),
            text=text.raw,
            morph=morphology_summary
        )

        try:
            if self._supports_async:
                response = await self._create_method(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )
            else:
                # Run blocking call in thread pool to avoid blocking event loop
                response = await asyncio.to_thread(
                    self.ai_client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )

            # Use safe JSON parsing with size limits
            raw_semantic_data = _safe_json_loads(
                response.choices[0].message.content,
                max_size=256 * 1024  # 256KB limit for semantic data
            )
        except Exception:
            raw_semantic_data = None

        if not isinstance(raw_semantic_data, dict):
            return SemanticAnalysis(
                themes=[],
                theological_keywords=[],
                cross_references=[],
                textual_variants=[]
            )

        return SemanticAnalysis(
            themes=self._safe_string_list(raw_semantic_data.get("themes", [])),
            theological_keywords=self._safe_string_list(raw_semantic_data.get("theological_keywords", [])),
            cross_references=self._safe_string_list(raw_semantic_data.get("cross_references", [])),
            textual_variants=self._safe_string_list(raw_semantic_data.get("textual_variants", [])),
            translation_notes=self._safe_dict(raw_semantic_data.get("translation_notes", {}))
        )

    @staticmethod
    def _safe_string_list(candidate: Optional[List[str]]) -> List[str]:
        """Return a list of strings, discarding malformed AI payloads."""
        if not isinstance(candidate, list):
            return []
        # Limit list size and string length to prevent abuse
        safe_list = []
        for item in candidate[:50]:  # Max 50 items
            if isinstance(item, str) and len(item) <= 500:  # Max 500 chars per item
                safe_list.append(item)
        return safe_list

    @staticmethod
    def _safe_dict(candidate: Optional[Dict]) -> Dict:
        """Ensure translation notes are a safe dictionary."""
        if not isinstance(candidate, dict):
            return {}
        
        # Limit dictionary size and key/value lengths
        safe_dict = {}
        for key, value in list(candidate.items())[:20]:  # Max 20 entries
            if isinstance(key, str) and len(key) <= 100:  # Max 100 chars for keys
                if isinstance(value, str) and len(value) <= 1000:  # Max 1000 chars for values
                    safe_dict[key] = value
        return safe_dict


class CrossLanguageComparator:
    """AI-powered cross-language comparison for Hebrew/Greek texts."""

    def __init__(self, ai_client, model_name: str = "gpt-4"):
        self._supports_async, self._create_method = _validate_chat_completions_client(ai_client)
        self.ai_client = ai_client
        self.model_name = model_name

    async def compare_hebrew_lxx(self, hebrew_verse: BiblicalVerse,
                          lxx_verse: BiblicalVerse) -> Dict[str, any]:
        """Compare Hebrew and LXX versions with AI analysis.

        Args:
            hebrew_verse: Hebrew version of the verse
            lxx_verse: LXX (Greek) version of the verse

        Returns:
            Dictionary containing comparison analysis
        """

        # Use XML delimiters to prevent prompt injection
        prompt = """Compare the Hebrew and Greek (LXX) versions inside the tags below.

<reference>{ref}</reference>
<hebrew>{heb}</hebrew>
<greek>{grk}</greek>

Analyze translation differences, theological implications, semantic shifts.
Provide JSON analysis.""".format(
            ref=str(hebrew_verse.reference),
            heb=hebrew_verse.text.raw,
            grk=lxx_verse.text.raw
        )

        try:
            if self._supports_async:
                response = await self._create_method(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )
            else:
                # Run blocking call in thread pool to avoid blocking event loop
                response = await asyncio.to_thread(
                    self.ai_client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )

            # Use safe JSON parsing with size limits
            result = _safe_json_loads(
                response.choices[0].message.content,
                max_size=128 * 1024  # 128KB limit for comparison data
            )
            return result if isinstance(result, dict) else {"error": "Failed to parse AI response"}
        except Exception as exc:
            return {"error": f"Analysis failed: {str(exc)}"}


class TheologicalDebateAnalyzer:
    """AI analyzer for theological debate contexts."""

    def __init__(self, ai_client, model_name: str = "gpt-4"):
        self._supports_async, self._create_method = _validate_chat_completions_client(ai_client)
        self.ai_client = ai_client
        self.model_name = model_name

    async def analyze_trinity_passages(self, verses: List[BiblicalVerse]) -> Dict[str, any]:
        """Analyze passages for trinity doctrine evidence.

        Args:
            verses: List of biblical verses to analyze

        Returns:
            Dictionary containing theological analysis
        """

        verses_summary = "\n".join([
            f"{v.reference}: {v.text.raw}" for v in verses
        ])

        # Use XML delimiters to prevent prompt injection
        prompt = """Analyze the passages inside the <input> tags for trinity doctrine evidence.

<input>
{verses}
</input>

Cover: grammatical evidence, divine names, plurality/unity patterns,
historical interpretation, modern consensus, counter-arguments.

Provide comprehensive JSON analysis.""".format(verses=verses_summary)

        try:
            if self._supports_async:
                response = await self._create_method(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
            else:
                # Run blocking call in thread pool to avoid blocking event loop
                response = await asyncio.to_thread(
                    self.ai_client.chat.completions.create,
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )

            # Use safe JSON parsing with size limits
            result = _safe_json_loads(
                response.choices[0].message.content,
                max_size=256 * 1024  # 256KB limit for theological analysis
            )
            return result if isinstance(result, dict) else {"error": "Failed to parse AI response"}
        except Exception as exc:
            return {"error": f"Analysis failed: {str(exc)}"}
