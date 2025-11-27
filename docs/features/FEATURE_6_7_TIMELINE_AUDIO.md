# Features 6-7: Timeline & Audio

## 6. Timeline & Chronology View

### Overview

Map biblical events onto a historical timeline, correlating with archaeological/historical evidence cards.

### Database Schema

```sql
CREATE TABLE timeline_events (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    description TEXT,
    event_type VARCHAR(32),                     -- 'biblical', 'archaeological', 'historical'

    -- Date handling (BCE uses negative years)
    date_start_year INTEGER,
    date_start_month INTEGER,
    date_start_day INTEGER,
    date_end_year INTEGER,
    date_end_month INTEGER,
    date_end_day INTEGER,
    date_precision VARCHAR(16),                 -- 'exact', 'year', 'decade', 'century'
    date_display VARCHAR(64),                   -- "c. 1446 BCE"

    -- Connections
    osis_refs JSONB DEFAULT '[]',
    evidence_card_ids JSONB DEFAULT '[]',
    location_refs JSONB DEFAULT '[]',

    -- Metadata
    sources JSONB DEFAULT '[]',
    confidence VARCHAR(16),                     -- 'certain', 'probable', 'disputed'
    scholarly_consensus TEXT,
    alternative_dating TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_timeline_date ON timeline_events(date_start_year);
CREATE INDEX ix_timeline_type ON timeline_events(event_type);

CREATE TABLE event_relationships (
    id VARCHAR(36) PRIMARY KEY,
    source_event_id VARCHAR(36) REFERENCES timeline_events(id),
    target_event_id VARCHAR(36) REFERENCES timeline_events(id),
    relationship_type VARCHAR(32),              -- 'causes', 'precedes', 'fulfills'
    notes TEXT
);

CREATE TABLE historical_periods (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    start_year INTEGER,
    end_year INTEGER,
    description TEXT,
    color VARCHAR(7)                            -- Hex color
);
```

### API Specification

```python
# GET /timeline/events
@router.get("/events", response_model=TimelineEventsResponse)
def timeline_events(
    start_year: int | None = Query(default=None),
    end_year: int | None = Query(default=None),
    event_types: list[str] | None = Query(default=None),
    osis: str | None = Query(default=None),
    confidence: list[str] | None = Query(default=None),
    session: Session = Depends(get_session),
) -> TimelineEventsResponse:
    """Return events within date range."""

# GET /timeline/events/{id}
@router.get("/events/{event_id}", response_model=TimelineEventDetailResponse)
def timeline_event_detail(
    event_id: str,
    include_related: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> TimelineEventDetailResponse:
    """Return full event with related evidence and verses."""

# GET /timeline/periods
@router.get("/periods", response_model=PeriodsResponse)
def historical_periods(
    session: Session = Depends(get_session),
) -> PeriodsResponse:
    """Return historical periods for timeline background."""
```

**Response Schemas:**

```python
class TimelineEvent(BaseModel):
    id: str
    title: str
    description: str | None
    event_type: str
    date_display: str
    date_start_year: int | None
    date_end_year: int | None
    date_precision: str
    confidence: str
    osis_refs: list[str]
    related_evidence_count: int

class TimelineEventDetail(TimelineEvent):
    scholarly_consensus: str | None
    alternative_dating: str | None
    sources: list[dict]
    evidence_cards: list[EvidenceCardSummary]
    related_verses: list[VerseSummary]
    related_events: list[RelatedEvent]

class HistoricalPeriod(BaseModel):
    id: str
    name: str
    start_year: int
    end_year: int
    description: str | None
    color: str

class TimelineEventsResponse(BaseModel):
    events: list[TimelineEvent]
    periods: list[HistoricalPeriod]
    date_range: tuple[int, int]
```

### Application Service

**File:** `exegesis/application/research/timeline_service.py`

```python
class TimelineService:
    def __init__(
        self,
        event_repository: TimelineEventRepository,
        period_repository: HistoricalPeriodRepository,
        evidence_service: EvidenceService,
    ):
        self._event_repo = event_repository
        self._period_repo = period_repository
        self._evidence = evidence_service

    def get_events(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
        event_types: list[str] | None = None,
        osis: str | None = None,
        confidence: list[str] | None = None,
    ) -> list[TimelineEvent]:
        query = self._event_repo.query()

        if start_year is not None:
            query = query.filter(TimelineEventModel.date_start_year >= start_year)
        if end_year is not None:
            query = query.filter(TimelineEventModel.date_start_year <= end_year)
        if event_types:
            query = query.filter(TimelineEventModel.event_type.in_(event_types))
        if confidence:
            query = query.filter(TimelineEventModel.confidence.in_(confidence))
        if osis:
            # Filter events that reference this verse
            query = query.filter(
                TimelineEventModel.osis_refs.contains([osis])
            )

        return query.order_by(TimelineEventModel.date_start_year).all()

    def get_event_detail(self, event_id: str) -> TimelineEventDetail:
        event = self._event_repo.get(event_id)
        if not event:
            raise NotFoundError(f"Event {event_id} not found")

        # Fetch related evidence cards
        evidence_cards = []
        for card_id in event.evidence_card_ids:
            card = self._evidence.get_card(card_id)
            if card:
                evidence_cards.append(card)

        # Fetch related events
        related = self._event_repo.get_related(event_id)

        return TimelineEventDetail(
            **event.dict(),
            evidence_cards=evidence_cards,
            related_events=related,
        )

    def get_events_for_verse(self, osis: str) -> list[TimelineEvent]:
        return self._event_repo.query().filter(
            TimelineEventModel.osis_refs.contains([osis])
        ).all()

    def get_periods(self) -> list[HistoricalPeriod]:
        return self._period_repo.all()

    def calculate_pixel_positions(
        self,
        events: list[TimelineEvent],
        view_start: int,
        view_end: int,
        pixel_width: int,
    ) -> list[dict]:
        """Calculate x positions for timeline rendering."""
        year_range = view_end - view_start
        pixels_per_year = pixel_width / year_range if year_range else 1

        positions = []
        for event in events:
            if event.date_start_year is None:
                continue

            x = (event.date_start_year - view_start) * pixels_per_year
            width = pixels_per_year  # Default single year

            if event.date_end_year and event.date_end_year != event.date_start_year:
                width = (event.date_end_year - event.date_start_year) * pixels_per_year

            positions.append({
                "event_id": event.id,
                "x": max(0, x),
                "width": max(10, width),  # Minimum visible width
            })

        return positions
```

### Frontend Components

**Directory:** `exegesis/services/web/app/components/Timeline/`

```tsx
// index.tsx
import { useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TimelineCanvas } from './TimelineCanvas';
import { EventDetailPanel } from './EventDetailPanel';
import { FilterPanel } from './FilterPanel';
import { ZoomControls } from './ZoomControls';

export function Timeline() {
  const [viewRange, setViewRange] = useState({ start: -2000, end: 100 });
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);
  const [filters, setFilters] = useState<TimelineFilters>({});

  const { data } = useQuery({
    queryKey: ['timeline-events', viewRange, filters],
    queryFn: () => fetchTimelineEvents({
      start_year: viewRange.start,
      end_year: viewRange.end,
      ...filters,
    }),
  });

  const handleZoom = (direction: 'in' | 'out') => {
    const range = viewRange.end - viewRange.start;
    const center = (viewRange.start + viewRange.end) / 2;
    const factor = direction === 'in' ? 0.5 : 2;
    const newRange = range * factor;

    setViewRange({
      start: Math.round(center - newRange / 2),
      end: Math.round(center + newRange / 2),
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center p-4 border-b">
        <h1 className="text-xl font-bold">Biblical Timeline</h1>
        <div className="flex gap-2">
          <FilterPanel filters={filters} onChange={setFilters} />
          <ZoomControls onZoom={handleZoom} />
        </div>
      </div>

      <div className="flex-1 flex">
        <TimelineCanvas
          events={data?.events || []}
          periods={data?.periods || []}
          viewRange={viewRange}
          onViewRangeChange={setViewRange}
          onEventClick={setSelectedEvent}
        />

        {selectedEvent && (
          <EventDetailPanel
            eventId={selectedEvent}
            onClose={() => setSelectedEvent(null)}
          />
        )}
      </div>
    </div>
  );
}

// TimelineCanvas.tsx
interface TimelineCanvasProps {
  events: TimelineEvent[];
  periods: HistoricalPeriod[];
  viewRange: { start: number; end: number };
  onViewRangeChange: (range: { start: number; end: number }) => void;
  onEventClick: (eventId: string) => void;
}

export function TimelineCanvas({
  events,
  periods,
  viewRange,
  onViewRangeChange,
  onEventClick,
}: TimelineCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, range: viewRange });

  const yearToX = (year: number) => {
    const width = containerRef.current?.clientWidth || 1000;
    const range = viewRange.end - viewRange.start;
    return ((year - viewRange.start) / range) * width;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, range: viewRange });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;

    const dx = e.clientX - dragStart.x;
    const width = containerRef.current?.clientWidth || 1000;
    const range = viewRange.end - viewRange.start;
    const yearDelta = (dx / width) * range;

    onViewRangeChange({
      start: Math.round(dragStart.range.start - yearDelta),
      end: Math.round(dragStart.range.end - yearDelta),
    });
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.1 : 0.9;
    const range = viewRange.end - viewRange.start;
    const center = (viewRange.start + viewRange.end) / 2;
    const newRange = range * factor;

    onViewRangeChange({
      start: Math.round(center - newRange / 2),
      end: Math.round(center + newRange / 2),
    });
  };

  return (
    <div
      ref={containerRef}
      className="flex-1 relative overflow-hidden cursor-grab"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={() => setIsDragging(false)}
      onMouseLeave={() => setIsDragging(false)}
      onWheel={handleWheel}
    >
      {/* Period backgrounds */}
      {periods.map((period) => (
        <div
          key={period.id}
          className="absolute h-full opacity-20"
          style={{
            left: yearToX(period.start_year),
            width: yearToX(period.end_year) - yearToX(period.start_year),
            backgroundColor: period.color,
          }}
        >
          <span className="absolute top-2 left-2 text-xs font-medium">
            {period.name}
          </span>
        </div>
      ))}

      {/* Date ruler */}
      <DateRuler viewRange={viewRange} yearToX={yearToX} />

      {/* Event markers */}
      <div className="absolute top-16 bottom-0 w-full">
        {events.map((event) => (
          <EventMarker
            key={event.id}
            event={event}
            x={yearToX(event.date_start_year!)}
            onClick={() => onEventClick(event.id)}
          />
        ))}
      </div>
    </div>
  );
}

// EventMarker.tsx
const EVENT_COLORS = {
  biblical: '#2563EB',
  archaeological: '#92400E',
  historical: '#6B7280',
};

const CONFIDENCE_STYLES = {
  certain: 'border-solid',
  probable: 'border-dashed',
  disputed: 'border-dotted',
};

interface EventMarkerProps {
  event: TimelineEvent;
  x: number;
  onClick: () => void;
}

export function EventMarker({ event, x, onClick }: EventMarkerProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div
      className="absolute cursor-pointer"
      style={{ left: x, transform: 'translateX(-50%)' }}
      onClick={onClick}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div
        className={`w-4 h-4 rounded-full border-2 ${CONFIDENCE_STYLES[event.confidence]}`}
        style={{
          backgroundColor: EVENT_COLORS[event.event_type],
          borderColor: EVENT_COLORS[event.event_type],
        }}
      />

      {showTooltip && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-white shadow-lg rounded p-2 w-48 z-10">
          <p className="font-medium text-sm">{event.title}</p>
          <p className="text-xs text-gray-500">{event.date_display}</p>
          {event.osis_refs.length > 0 && (
            <p className="text-xs text-blue-600">{event.osis_refs[0]}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

### Data Seeding

**File:** `data/seeds/timeline_events.yaml`

```yaml
events:
  - title: "Creation"
    event_type: biblical
    date_display: "Beginning"
    date_precision: traditional
    osis_refs: ["Gen.1.1", "Gen.2.1"]
    confidence: traditional

  - title: "The Flood"
    event_type: biblical
    date_display: "c. 2350 BCE (traditional)"
    date_start_year: -2350
    date_precision: disputed
    osis_refs: ["Gen.6.1", "Gen.7.1"]
    confidence: disputed

  - title: "Call of Abraham"
    event_type: biblical
    date_display: "c. 2091 BCE"
    date_start_year: -2091
    date_precision: estimated
    osis_refs: ["Gen.12.1"]
    confidence: probable

  - title: "Exodus from Egypt"
    event_type: biblical
    date_display: "c. 1446 BCE (early) or c. 1260 BCE (late)"
    date_start_year: -1446
    date_precision: disputed
    osis_refs: ["Exod.12.31", "Exod.14.21"]
    confidence: disputed
    scholarly_consensus: "Dating remains debated between early (1446 BCE) and late (1260 BCE) chronologies"
    alternative_dating: "Late date of c. 1260 BCE based on archaeological evidence at Raamses"
    sources:
      - "Kitchen, K.A. On the Reliability of the Old Testament"
      - "Hoffmeier, J.K. Israel in Egypt"

  - title: "Fall of Jerusalem"
    event_type: biblical
    date_display: "586 BCE"
    date_start_year: -586
    date_precision: year
    osis_refs: ["2Kgs.25.1", "Jer.39.1"]
    confidence: certain

  - title: "Birth of Jesus"
    event_type: biblical
    date_display: "c. 6-4 BCE"
    date_start_year: -6
    date_end_year: -4
    date_precision: estimated
    osis_refs: ["Matt.2.1", "Luke.2.1"]
    confidence: probable

  - title: "Crucifixion of Jesus"
    event_type: biblical
    date_display: "c. 30-33 CE"
    date_start_year: 30
    date_end_year: 33
    date_precision: estimated
    osis_refs: ["Matt.27.35", "Mark.15.24", "Luke.23.33", "John.19.18"]
    confidence: probable

periods:
  - name: "Patriarchal Period"
    start_year: -2100
    end_year: -1800
    color: "#D97706"

  - name: "Egyptian Sojourn"
    start_year: -1800
    end_year: -1446
    color: "#059669"

  - name: "Conquest & Judges"
    start_year: -1446
    end_year: -1050
    color: "#7C3AED"

  - name: "United Monarchy"
    start_year: -1050
    end_year: -930
    color: "#2563EB"

  - name: "Divided Kingdom"
    start_year: -930
    end_year: -586
    color: "#DC2626"

  - name: "Exile"
    start_year: -586
    end_year: -538
    color: "#6B7280"

  - name: "Second Temple"
    start_year: -538
    end_year: 70
    color: "#0891B2"
```

---

## 7. Verse-Level Audio Sync

### Overview

Audio Bible integration with word-level highlighting during playback.

### Database Schema

```sql
CREATE TABLE audio_recordings (
    id VARCHAR(36) PRIMARY KEY,
    translation_code VARCHAR(16) NOT NULL,
    narrator VARCHAR(128),
    book_osis VARCHAR(16) NOT NULL,
    chapter INTEGER NOT NULL,
    audio_url VARCHAR(512) NOT NULL,
    duration_ms INTEGER NOT NULL,
    format VARCHAR(16) DEFAULT 'mp3',
    bitrate INTEGER,
    is_dramatized BOOLEAN DEFAULT FALSE,
    license_info TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(translation_code, narrator, book_osis, chapter)
);

CREATE TABLE audio_word_timings (
    id VARCHAR(36) PRIMARY KEY,
    recording_id VARCHAR(36) REFERENCES audio_recordings(id) ON DELETE CASCADE,
    verse_osis VARCHAR(32) NOT NULL,
    word_index INTEGER NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    UNIQUE(recording_id, verse_osis, word_index)
);

CREATE INDEX ix_audio_timings_recording ON audio_word_timings(recording_id);
CREATE INDEX ix_audio_timings_verse ON audio_word_timings(verse_osis);

CREATE TABLE user_audio_state (
    user_id VARCHAR(36) PRIMARY KEY,
    last_recording_id VARCHAR(36) REFERENCES audio_recordings(id),
    last_position_ms INTEGER,
    playback_speed FLOAT DEFAULT 1.0,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### API Specification

```python
# GET /audio/recordings
@router.get("/recordings", response_model=AudioRecordingsResponse)
def list_recordings(
    translation: str | None = Query(default=None),
    book: str | None = Query(default=None),
    chapter: int | None = Query(default=None),
    narrator: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> AudioRecordingsResponse:
    """List available audio recordings."""

# GET /audio/recordings/{id}/timings
@router.get("/recordings/{recording_id}/timings", response_model=WordTimingsResponse)
def get_word_timings(
    recording_id: str,
    verse_start: str | None = Query(default=None),
    verse_end: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> WordTimingsResponse:
    """Return word-level timing data."""

# POST /audio/playback-state
@router.post("/playback-state")
def save_playback_state(
    state: PlaybackStateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Save user's playback position."""

# GET /audio/playback-state
@router.get("/playback-state", response_model=PlaybackStateResponse)
def get_playback_state(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PlaybackStateResponse:
    """Get user's last playback position."""
```

**Response Schemas:**

```python
class AudioRecording(BaseModel):
    id: str
    translation_code: str
    narrator: str
    book_osis: str
    chapter: int
    audio_url: str
    duration_ms: int
    is_dramatized: bool

class WordTiming(BaseModel):
    verse_osis: str
    word_index: int
    start_ms: int
    end_ms: int

class WordTimingsResponse(BaseModel):
    recording_id: str
    timings: list[WordTiming]
    # Grouped by verse for efficient lookup
    by_verse: dict[str, list[WordTiming]]

class PlaybackStateRequest(BaseModel):
    recording_id: str
    position_ms: int
    playback_speed: float = 1.0

class PlaybackStateResponse(BaseModel):
    recording_id: str | None
    position_ms: int | None
    playback_speed: float
    recording: AudioRecording | None
```

### Application Service

**File:** `exegesis/application/audio/audio_service.py`

```python
class AudioService:
    def __init__(
        self,
        recording_repository: AudioRecordingRepository,
        timing_repository: AudioTimingRepository,
        state_repository: UserAudioStateRepository,
    ):
        self._recording_repo = recording_repository
        self._timing_repo = timing_repository
        self._state_repo = state_repository

    def get_recordings(
        self,
        translation: str | None = None,
        book: str | None = None,
        chapter: int | None = None,
        narrator: str | None = None,
    ) -> list[AudioRecording]:
        query = self._recording_repo.query()

        if translation:
            query = query.filter_by(translation_code=translation)
        if book:
            query = query.filter_by(book_osis=book)
        if chapter:
            query = query.filter_by(chapter=chapter)
        if narrator:
            query = query.filter_by(narrator=narrator)

        return query.all()

    def get_timings(
        self,
        recording_id: str,
        verse_start: str | None = None,
        verse_end: str | None = None,
    ) -> WordTimingsResponse:
        timings = self._timing_repo.get_for_recording(recording_id)

        # Filter by verse range if specified
        if verse_start or verse_end:
            timings = self._filter_verse_range(timings, verse_start, verse_end)

        # Group by verse for efficient frontend lookup
        by_verse = {}
        for timing in timings:
            if timing.verse_osis not in by_verse:
                by_verse[timing.verse_osis] = []
            by_verse[timing.verse_osis].append(timing)

        return WordTimingsResponse(
            recording_id=recording_id,
            timings=timings,
            by_verse=by_verse,
        )

    def find_verse_at_timestamp(
        self,
        recording_id: str,
        timestamp_ms: int,
    ) -> str | None:
        """Binary search for verse at timestamp."""
        timings = self._timing_repo.get_for_recording(recording_id)

        left, right = 0, len(timings) - 1
        while left <= right:
            mid = (left + right) // 2
            timing = timings[mid]

            if timing.start_ms <= timestamp_ms <= timing.end_ms:
                return timing.verse_osis
            elif timing.start_ms > timestamp_ms:
                right = mid - 1
            else:
                left = mid + 1

        return None

    def save_playback_state(
        self,
        user_id: str,
        recording_id: str,
        position_ms: int,
        playback_speed: float = 1.0,
    ) -> None:
        state = self._state_repo.get(user_id)
        if state:
            state.last_recording_id = recording_id
            state.last_position_ms = position_ms
            state.playback_speed = playback_speed
            self._state_repo.update(state)
        else:
            self._state_repo.add(UserAudioState(
                user_id=user_id,
                last_recording_id=recording_id,
                last_position_ms=position_ms,
                playback_speed=playback_speed,
            ))

    def get_playback_state(self, user_id: str) -> PlaybackStateResponse:
        state = self._state_repo.get(user_id)
        if not state:
            return PlaybackStateResponse(
                recording_id=None,
                position_ms=None,
                playback_speed=1.0,
                recording=None,
            )

        recording = self._recording_repo.get(state.last_recording_id)
        return PlaybackStateResponse(
            recording_id=state.last_recording_id,
            position_ms=state.last_position_ms,
            playback_speed=state.playback_speed,
            recording=recording,
        )
```

### Frontend Components

**Directory:** `exegesis/services/web/app/components/AudioPlayer/`

```tsx
// index.tsx
import { useRef, useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { PlayerControls } from './PlayerControls';
import { ProgressBar } from './ProgressBar';
import { useWordSync } from './hooks/useWordSync';

interface AudioPlayerProps {
  recordingId: string;
  onVerseChange?: (osis: string) => void;
  onWordHighlight?: (verseOsis: string, wordIndex: number) => void;
}

export function AudioPlayer({
  recordingId,
  onVerseChange,
  onWordHighlight,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);

  const { data: recording } = useQuery({
    queryKey: ['audio-recording', recordingId],
    queryFn: () => fetchRecording(recordingId),
  });

  const { data: timings } = useQuery({
    queryKey: ['audio-timings', recordingId],
    queryFn: () => fetchTimings(recordingId),
  });

  const saveState = useMutation({
    mutationFn: (position: number) => savePlaybackState({
      recording_id: recordingId,
      position_ms: position,
      playback_speed: playbackSpeed,
    }),
  });

  // Word synchronization
  const currentWord = useWordSync(audioRef, timings?.timings || []);

  useEffect(() => {
    if (currentWord && onWordHighlight) {
      onWordHighlight(currentWord.verse_osis, currentWord.word_index);
    }
  }, [currentWord, onWordHighlight]);

  // Save state periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (audioRef.current && isPlaying) {
        saveState.mutate(audioRef.current.currentTime * 1000);
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [isPlaying]);

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime * 1000);
    }
  };

  const handleSeek = (timeMs: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = timeMs / 1000;
      setCurrentTime(timeMs);
    }
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
    }
  };

  if (!recording) return null;

  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <audio
        ref={audioRef}
        src={recording.audio_url}
        onTimeUpdate={handleTimeUpdate}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />

      <div className="flex items-center gap-4">
        <PlayerControls
          isPlaying={isPlaying}
          playbackSpeed={playbackSpeed}
          onPlay={() => audioRef.current?.play()}
          onPause={() => audioRef.current?.pause()}
          onSkipBack={() => handleSeek(Math.max(0, currentTime - 10000))}
          onSkipForward={() => handleSeek(currentTime + 10000)}
          onSpeedChange={handleSpeedChange}
        />

        <div className="flex-1">
          <ProgressBar
            currentTime={currentTime}
            duration={recording.duration_ms}
            timings={timings?.timings || []}
            onSeek={handleSeek}
          />
        </div>

        <div className="text-sm text-gray-500">
          {formatTime(currentTime)} / {formatTime(recording.duration_ms)}
        </div>
      </div>

      <div className="mt-2 text-sm text-gray-600">
        {recording.narrator} • {recording.translation_code}
      </div>
    </div>
  );
}

// hooks/useWordSync.ts
import { useState, useEffect, RefObject } from 'react';

export function useWordSync(
  audioRef: RefObject<HTMLAudioElement>,
  timings: WordTiming[],
): WordTiming | null {
  const [currentWord, setCurrentWord] = useState<WordTiming | null>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !timings.length) return;

    let animationFrameId: number;

    const updateCurrentWord = () => {
      const currentMs = audio.currentTime * 1000;

      // Binary search for current word
      const word = findWordAtTime(timings, currentMs);

      if (word?.verse_osis !== currentWord?.verse_osis ||
          word?.word_index !== currentWord?.word_index) {
        setCurrentWord(word);
      }

      if (!audio.paused) {
        animationFrameId = requestAnimationFrame(updateCurrentWord);
      }
    };

    audio.addEventListener('play', () => {
      animationFrameId = requestAnimationFrame(updateCurrentWord);
    });

    audio.addEventListener('timeupdate', updateCurrentWord);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [timings]);

  return currentWord;
}

function findWordAtTime(timings: WordTiming[], timeMs: number): WordTiming | null {
  let left = 0;
  let right = timings.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const timing = timings[mid];

    if (timing.start_ms <= timeMs && timeMs <= timing.end_ms) {
      return timing;
    } else if (timing.start_ms > timeMs) {
      right = mid - 1;
    } else {
      left = mid + 1;
    }
  }

  return null;
}

// SyncHighlighter.tsx - Overlay component for verse display
interface SyncHighlighterProps {
  verseOsis: string;
  currentWord: { verse_osis: string; word_index: number } | null;
  children: React.ReactNode;
}

export function SyncHighlighter({ verseOsis, currentWord, children }: SyncHighlighterProps) {
  const isCurrentVerse = currentWord?.verse_osis === verseOsis;
  const currentWordIndex = isCurrentVerse ? currentWord?.word_index : null;

  // Split children into words and highlight current
  const words = React.Children.toArray(children);

  return (
    <span className={isCurrentVerse ? 'bg-yellow-50' : ''}>
      {words.map((word, index) => (
        <span
          key={index}
          className={index === currentWordIndex ? 'bg-yellow-300 rounded' : ''}
        >
          {word}
        </span>
      ))}
    </span>
  );
}
```

### Audio Data Processing

**Script:** `scripts/process_audio_timings.py`

```python
"""
Process audio files to generate word-level timing data.
Uses Whisper or Gentle for forced alignment.
"""

import json
from pathlib import Path
from typing import Iterator

def generate_timings_whisper(
    audio_path: Path,
    transcript: str,
) -> list[dict]:
    """Use OpenAI Whisper for word-level timestamps."""
    import whisper

    model = whisper.load_model("base")
    result = model.transcribe(
        str(audio_path),
        word_timestamps=True,
    )

    timings = []
    for segment in result["segments"]:
        for word_data in segment.get("words", []):
            timings.append({
                "word": word_data["word"].strip(),
                "start_ms": int(word_data["start"] * 1000),
                "end_ms": int(word_data["end"] * 1000),
            })

    return timings

def align_timings_to_verses(
    timings: list[dict],
    verse_texts: dict[str, str],  # osis -> text
) -> Iterator[dict]:
    """Align timing data to verse/word positions."""
    timing_idx = 0

    for osis, verse_text in verse_texts.items():
        words = verse_text.split()

        for word_idx, word in enumerate(words):
            if timing_idx >= len(timings):
                break

            timing = timings[timing_idx]

            # Match word (fuzzy)
            if similar(word, timing["word"]):
                yield {
                    "verse_osis": osis,
                    "word_index": word_idx,
                    "start_ms": timing["start_ms"],
                    "end_ms": timing["end_ms"],
                }
                timing_idx += 1

def similar(a: str, b: str) -> bool:
    """Check if words are similar enough to match."""
    a = a.lower().strip(".,;:!?\"'")
    b = b.lower().strip(".,;:!?\"'")
    return a == b or a.startswith(b) or b.startswith(a)

def process_chapter(
    audio_path: Path,
    book_osis: str,
    chapter: int,
    translation: str,
    output_path: Path,
):
    """Process a chapter audio file and save timing data."""
    # Get verse texts
    verse_texts = fetch_verse_texts(book_osis, chapter, translation)

    # Generate raw timings
    transcript = " ".join(verse_texts.values())
    raw_timings = generate_timings_whisper(audio_path, transcript)

    # Align to verses
    aligned = list(align_timings_to_verses(raw_timings, verse_texts))

    # Save
    output_path.write_text(json.dumps(aligned, indent=2))
    print(f"Saved {len(aligned)} word timings to {output_path}")
```

### Testing

```python
# tests/application/audio/test_audio_service.py

def test_find_verse_at_timestamp(service, recording_with_timings):
    # Timing: Gen.1.1 word 0 = 0-500ms, word 1 = 500-1000ms
    verse = service.find_verse_at_timestamp(recording_with_timings.id, 250)
    assert verse == "Gen.1.1"

def test_find_verse_at_timestamp_boundary(service, recording_with_timings):
    # At exact boundary, should return the word that starts there
    verse = service.find_verse_at_timestamp(recording_with_timings.id, 500)
    assert verse == "Gen.1.1"

def test_get_timings_groups_by_verse(service, recording_with_timings):
    response = service.get_timings(recording_with_timings.id)
    assert "Gen.1.1" in response.by_verse
    assert len(response.by_verse["Gen.1.1"]) > 0

def test_save_and_restore_playback_state(service, user, recording):
    service.save_playback_state(user.id, recording.id, 12345, 1.5)
    state = service.get_playback_state(user.id)
    assert state.recording_id == recording.id
    assert state.position_ms == 12345
    assert state.playback_speed == 1.5
```
