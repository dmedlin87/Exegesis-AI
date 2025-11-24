"""Detailed unit tests for TheologicalTermTracker logic."""
from typing import Optional

import pytest

from theo.domain.biblical_texts import (
    BiblicalBook,
    BiblicalVerse,
    BibleVersion,
    Language,
    MorphologicalTag,
    POS,
    Reference,
    TextContent,
    TheologicalTermTracker,
)


@pytest.fixture
def verse_factory():
    def _create_verse(tags: list[MorphologicalTag], verse_id: str = "1:1") -> BiblicalVerse:
        return BiblicalVerse(
            reference=Reference("Gen", 1, 1, "gen", f"Gen.{verse_id}"),
            language=Language.HEBREW,
            text=TextContent("raw", "normalized"),
            morphology=tags,
        )
    return _create_verse


@pytest.fixture
def version_factory():
    def _create_version(verses: list[BiblicalVerse]) -> BibleVersion:
        verse_map = {f"1:{i+1}": v for i, v in enumerate(verses)}
        book = BiblicalBook(
            id="gen",
            name="Genesis",
            native_name="Bereshit",
            language=Language.HEBREW,
            chapter_count=1,
            verses=verse_map,
        )
        return BibleVersion(
            name="Test Version",
            abbreviation="TV",
            language=Language.HEBREW,
            license="Public",
            source_url=None,
            version="1.0",
            description="Test",
            books={"gen": book},
        )
    return _create_version


def make_tag(
    word="test",
    lemma="test",
    pos=POS.NOUN,
    number: Optional[str] = None,
    person: Optional[int] = None,
    theological_notes: Optional[list[str]] = None,
) -> MorphologicalTag:
    return MorphologicalTag(
        word=word,
        lemma=lemma,
        root=None,
        pos=pos,
        number=number,
        person=person,
        theological_notes=theological_notes or [],
    )


class TestTheologicalTermTracker:
    def test_finds_elohim_with_singular_verb(self, verse_factory, version_factory):
        """Should match when Elohim (plural) appears with a 3rd person singular verb."""
        tags = [
            make_tag(lemma="אלהים", number="plural", pos=POS.NOUN),
            make_tag(lemma="ברא", number="singular", person=3, pos=POS.VERB),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert len(results) == 1
        assert results[0] == verse

    def test_ignores_elohim_with_plural_verb(self, verse_factory, version_factory):
        """Should NOT match when Elohim appears with a plural verb."""
        tags = [
            make_tag(lemma="אלהים", number="plural", pos=POS.NOUN),
            make_tag(lemma="דברו", number="plural", person=3, pos=POS.VERB),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert results == []

    def test_ignores_singular_verb_without_elohim(self, verse_factory, version_factory):
        """Should NOT match when singular verb exists but no Elohim."""
        tags = [
            make_tag(lemma="איש", number="singular", pos=POS.NOUN),
            make_tag(lemma="אמר", number="singular", person=3, pos=POS.VERB),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert results == []

    def test_ignores_elohim_without_verb(self, verse_factory, version_factory):
        """Should NOT match when Elohim exists but no verb."""
        tags = [
            make_tag(lemma="אלהים", number="plural", pos=POS.NOUN),
            make_tag(lemma="טוב", number="singular", pos=POS.ADJECTIVE),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert results == []

    def test_matches_divine_name_note_as_elohim(self, verse_factory, version_factory):
        """Should match if lemma is not explicitly 'אלהים' but has 'divine_name' note."""
        tags = [
            make_tag(
                lemma="unknown_divine",
                number="plural",
                pos=POS.NOUN,
                theological_notes=["divine_name"]
            ),
            make_tag(lemma="created", number="singular", person=3, pos=POS.VERB),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert len(results) == 1
        assert results[0] == verse

    def test_handles_none_values_gracefully(self, verse_factory, version_factory):
        """Should not crash when optional fields are None."""
        tags = [
            make_tag(lemma=None, number=None, pos=None), # type: ignore
            make_tag(lemma="אלהים", number="plural", pos=POS.NOUN),
            make_tag(lemma="verb", number="singular", person=3, pos=POS.VERB),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        # Should succeed despite the first tag having None values
        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert len(results) == 1

    def test_case_insensitivity_normalization(self, verse_factory, version_factory):
        """Should handle loose string matching for 'singular'/'plural'."""
        tags = [
            make_tag(lemma="אלהים", number="PLURAL", pos=POS.NOUN),
            make_tag(lemma="verb", number="Singular", person=3, pos=POS.VERB),
        ]
        verse = verse_factory(tags)
        version = version_factory([verse])

        results = TheologicalTermTracker.find_elohim_singular_verbs(version)
        assert len(results) == 1
