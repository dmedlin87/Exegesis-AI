# Features 8-10: Engagement & UX

## 8. Reading Progress & Streaks

### Overview

Track chapters read, set daily goals, earn streak badges, visualize annual reading coverage.

### Database Schema

```sql
CREATE TABLE reading_history (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    osis VARCHAR(32) NOT NULL,                  -- Chapter OSIS, e.g., 'Gen.1'
    read_at TIMESTAMP DEFAULT NOW(),
    duration_seconds INTEGER,
    completion_percentage FLOAT DEFAULT 1.0,
    source VARCHAR(32),                         -- 'manual', 'audio', 'study'
    UNIQUE(user_id, osis, DATE(read_at))
);

CREATE INDEX ix_reading_user_date ON reading_history(user_id, read_at);
CREATE INDEX ix_reading_user_osis ON reading_history(user_id, osis);

CREATE TABLE reading_goals (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    goal_type VARCHAR(32) NOT NULL,             -- 'daily_chapters', 'daily_minutes', 'annual_bible'
    target_value INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_streaks (
    user_id VARCHAR(36) PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_read_date DATE,
    streak_start_date DATE,
    total_days_read INTEGER DEFAULT 0,
    total_chapters_read INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE badges (
    id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256),
    icon_url VARCHAR(256),
    category VARCHAR(32),                       -- 'streak', 'completion', 'milestone'
    criteria JSONB NOT NULL,                    -- {"type": "streak", "days": 7}
    rarity VARCHAR(16) DEFAULT 'common'         -- 'common', 'rare', 'epic', 'legendary'
);

CREATE TABLE user_badges (
    user_id VARCHAR(36) NOT NULL,
    badge_id VARCHAR(36) REFERENCES badges(id),
    earned_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, badge_id)
);
```

### API Specification

```python
# POST /reading/log
class LogReadingRequest(BaseModel):
    osis: str                                   # Chapter OSIS
    duration_seconds: int | None = None
    completion_percentage: float = 1.0
    source: Literal["manual", "audio", "study"] = "manual"

class ReadingLogResponse(BaseModel):
    logged: bool
    streak_updated: bool
    current_streak: int
    new_badges: list[Badge]

@router.post("/log", response_model=ReadingLogResponse)
def log_reading(
    request: LogReadingRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReadingLogResponse:
    """Log chapter read, update streaks, check badges."""

# GET /reading/stats
class ReadingStatsResponse(BaseModel):
    current_streak: int
    longest_streak: int
    total_days_read: int
    total_chapters_read: int
    chapters_this_week: int
    chapters_this_month: int
    completion_by_book: dict[str, float]        # book -> percentage
    recent_chapters: list[str]

@router.get("/stats", response_model=ReadingStatsResponse)
def get_reading_stats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReadingStatsResponse:
    """Get user's reading statistics."""

# GET /reading/heatmap
class HeatmapResponse(BaseModel):
    year: int
    data: dict[str, int]                        # date string -> chapters read

@router.get("/heatmap", response_model=HeatmapResponse)
def get_reading_heatmap(
    year: int = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> HeatmapResponse:
    """Get reading activity heatmap data for calendar visualization."""

# GET /reading/coverage
class CoverageResponse(BaseModel):
    total_chapters: int
    chapters_read: int
    percentage: float
    by_testament: dict[str, dict]               # OT/NT -> {total, read, percentage}
    by_book: list[BookCoverage]

@router.get("/coverage", response_model=CoverageResponse)
def get_bible_coverage(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CoverageResponse:
    """Get Bible reading coverage breakdown."""

# GET /reading/badges
@router.get("/badges", response_model=BadgesResponse)
def get_badges(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BadgesResponse:
    """Get user's earned badges and available badges."""
```

### Application Service

**File:** `exegesis/application/engagement/progress_service.py`

```python
from datetime import date, timedelta
from typing import NamedTuple

class StreakUpdate(NamedTuple):
    streak_updated: bool
    current_streak: int
    is_new_record: bool

class ProgressService:
    # Total chapters in Protestant Bible
    TOTAL_CHAPTERS = 1189

    CHAPTERS_BY_BOOK = {
        "Gen": 50, "Exod": 40, "Lev": 27, "Num": 36, "Deut": 34,
        # ... all 66 books
        "Rev": 22,
    }

    def __init__(
        self,
        history_repository: ReadingHistoryRepository,
        streak_repository: UserStreakRepository,
        badge_repository: BadgeRepository,
        user_badge_repository: UserBadgeRepository,
    ):
        self._history_repo = history_repository
        self._streak_repo = streak_repository
        self._badge_repo = badge_repository
        self._user_badge_repo = user_badge_repository

    def log_reading(
        self,
        user_id: str,
        osis: str,
        duration_seconds: int | None = None,
        completion_percentage: float = 1.0,
        source: str = "manual",
    ) -> tuple[StreakUpdate, list[Badge]]:
        # Log the reading
        self._history_repo.add(ReadingHistory(
            user_id=user_id,
            osis=osis,
            duration_seconds=duration_seconds,
            completion_percentage=completion_percentage,
            source=source,
        ))

        # Update streak
        streak_update = self._update_streak(user_id)

        # Check for new badges
        new_badges = self._check_badges(user_id)

        return streak_update, new_badges

    def _update_streak(self, user_id: str) -> StreakUpdate:
        today = date.today()
        streak = self._streak_repo.get(user_id)

        if not streak:
            # First reading ever
            streak = UserStreak(
                user_id=user_id,
                current_streak=1,
                longest_streak=1,
                last_read_date=today,
                streak_start_date=today,
                total_days_read=1,
                total_chapters_read=1,
            )
            self._streak_repo.add(streak)
            return StreakUpdate(True, 1, True)

        if streak.last_read_date == today:
            # Already read today, just increment chapters
            streak.total_chapters_read += 1
            self._streak_repo.update(streak)
            return StreakUpdate(False, streak.current_streak, False)

        yesterday = today - timedelta(days=1)
        is_new_record = False

        if streak.last_read_date == yesterday:
            # Continuing streak
            streak.current_streak += 1
            if streak.current_streak > streak.longest_streak:
                streak.longest_streak = streak.current_streak
                is_new_record = True
        elif streak.last_read_date < yesterday:
            # Streak broken, start new
            streak.current_streak = 1
            streak.streak_start_date = today

        streak.last_read_date = today
        streak.total_days_read += 1
        streak.total_chapters_read += 1
        self._streak_repo.update(streak)

        return StreakUpdate(True, streak.current_streak, is_new_record)

    def _check_badges(self, user_id: str) -> list[Badge]:
        streak = self._streak_repo.get(user_id)
        earned = self._user_badge_repo.get_earned(user_id)
        earned_codes = {b.code for b in earned}

        all_badges = self._badge_repo.all()
        new_badges = []

        for badge in all_badges:
            if badge.code in earned_codes:
                continue

            if self._check_badge_criteria(badge, streak, user_id):
                self._user_badge_repo.add(UserBadge(
                    user_id=user_id,
                    badge_id=badge.id,
                ))
                new_badges.append(badge)

        return new_badges

    def _check_badge_criteria(
        self,
        badge: Badge,
        streak: UserStreak,
        user_id: str,
    ) -> bool:
        criteria = badge.criteria

        if criteria["type"] == "streak":
            return streak.current_streak >= criteria["days"]

        elif criteria["type"] == "total_days":
            return streak.total_days_read >= criteria["days"]

        elif criteria["type"] == "total_chapters":
            return streak.total_chapters_read >= criteria["chapters"]

        elif criteria["type"] == "book_complete":
            book = criteria["book"]
            chapters_in_book = self.CHAPTERS_BY_BOOK[book]
            read_chapters = self._history_repo.count_distinct_chapters(
                user_id, book
            )
            return read_chapters >= chapters_in_book

        elif criteria["type"] == "testament_complete":
            testament = criteria["testament"]
            # Check all books in testament
            # ...

        return False

    def get_heatmap(self, user_id: str, year: int) -> dict[str, int]:
        """Get reading counts by date for heatmap visualization."""
        start = date(year, 1, 1)
        end = date(year, 12, 31)

        readings = self._history_repo.get_by_date_range(user_id, start, end)

        heatmap = {}
        for reading in readings:
            date_str = reading.read_at.date().isoformat()
            heatmap[date_str] = heatmap.get(date_str, 0) + 1

        return heatmap

    def get_coverage(self, user_id: str) -> dict:
        """Get Bible reading coverage statistics."""
        read_chapters = set(
            self._history_repo.get_distinct_chapters(user_id)
        )

        by_book = []
        ot_read = nt_read = 0
        ot_total = nt_total = 0

        for book, total in self.CHAPTERS_BY_BOOK.items():
            read = sum(
                1 for ch in range(1, total + 1)
                if f"{book}.{ch}" in read_chapters
            )

            is_ot = book in self.OT_BOOKS
            if is_ot:
                ot_read += read
                ot_total += total
            else:
                nt_read += read
                nt_total += total

            by_book.append({
                "book": book,
                "total": total,
                "read": read,
                "percentage": (read / total) * 100 if total else 0,
            })

        return {
            "total_chapters": self.TOTAL_CHAPTERS,
            "chapters_read": len(read_chapters),
            "percentage": (len(read_chapters) / self.TOTAL_CHAPTERS) * 100,
            "by_testament": {
                "OT": {"total": ot_total, "read": ot_read, "percentage": (ot_read/ot_total)*100},
                "NT": {"total": nt_total, "read": nt_read, "percentage": (nt_read/nt_total)*100},
            },
            "by_book": by_book,
        }
```

### Frontend Components

**Directory:** `exegesis/services/web/app/components/Progress/`

```tsx
// index.tsx - Dashboard
export function ProgressDashboard() {
  const { data: stats } = useQuery({
    queryKey: ['reading-stats'],
    queryFn: fetchReadingStats,
  });

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Reading Progress</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Current Streak"
          value={stats?.current_streak || 0}
          suffix="days"
          icon={<FlameIcon />}
          highlight={stats?.current_streak >= 7}
        />
        <StatCard
          title="Longest Streak"
          value={stats?.longest_streak || 0}
          suffix="days"
          icon={<TrophyIcon />}
        />
        <StatCard
          title="This Week"
          value={stats?.chapters_this_week || 0}
          suffix="chapters"
          icon={<BookIcon />}
        />
        <StatCard
          title="Total Read"
          value={stats?.total_chapters_read || 0}
          suffix="chapters"
          icon={<CheckIcon />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ReadingHeatmap />
        <BibleCoverageChart />
      </div>

      <BadgeShowcase />
    </div>
  );
}

// ReadingHeatmap.tsx
import CalendarHeatmap from 'react-calendar-heatmap';

export function ReadingHeatmap() {
  const [year, setYear] = useState(new Date().getFullYear());
  const { data } = useQuery({
    queryKey: ['reading-heatmap', year],
    queryFn: () => fetchHeatmap(year),
  });

  const values = Object.entries(data?.data || {}).map(([date, count]) => ({
    date,
    count,
  }));

  return (
    <div className="bg-white rounded-lg p-4 shadow">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Reading Activity</h2>
        <YearSelector value={year} onChange={setYear} />
      </div>

      <CalendarHeatmap
        startDate={new Date(year, 0, 1)}
        endDate={new Date(year, 11, 31)}
        values={values}
        classForValue={(value) => {
          if (!value || value.count === 0) return 'color-empty';
          if (value.count >= 5) return 'color-scale-4';
          if (value.count >= 3) return 'color-scale-3';
          if (value.count >= 2) return 'color-scale-2';
          return 'color-scale-1';
        }}
        tooltipDataAttrs={(value) => ({
          'data-tip': value?.date
            ? `${value.date}: ${value.count} chapter${value.count !== 1 ? 's' : ''}`
            : 'No reading',
        })}
      />
    </div>
  );
}

// BibleCoverageChart.tsx
export function BibleCoverageChart() {
  const { data: coverage } = useQuery({
    queryKey: ['reading-coverage'],
    queryFn: fetchCoverage,
  });

  return (
    <div className="bg-white rounded-lg p-4 shadow">
      <h2 className="text-lg font-semibold mb-4">Bible Coverage</h2>

      <div className="flex items-center gap-4 mb-4">
        <div className="flex-1">
          <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 transition-all"
              style={{ width: `${coverage?.percentage || 0}%` }}
            />
          </div>
        </div>
        <span className="font-bold">{Math.round(coverage?.percentage || 0)}%</span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <TestamentProgress
          label="Old Testament"
          data={coverage?.by_testament?.OT}
          color="amber"
        />
        <TestamentProgress
          label="New Testament"
          data={coverage?.by_testament?.NT}
          color="blue"
        />
      </div>

      <div className="max-h-64 overflow-y-auto">
        {coverage?.by_book?.map((book) => (
          <BookProgressRow key={book.book} book={book} />
        ))}
      </div>
    </div>
  );
}

// BadgeShowcase.tsx
export function BadgeShowcase() {
  const { data } = useQuery({
    queryKey: ['badges'],
    queryFn: fetchBadges,
  });

  return (
    <div className="bg-white rounded-lg p-4 shadow">
      <h2 className="text-lg font-semibold mb-4">Achievements</h2>

      <div className="grid grid-cols-4 md:grid-cols-8 gap-4">
        {data?.earned?.map((badge) => (
          <BadgeIcon key={badge.id} badge={badge} earned />
        ))}
        {data?.available?.map((badge) => (
          <BadgeIcon key={badge.id} badge={badge} earned={false} />
        ))}
      </div>
    </div>
  );
}

function BadgeIcon({ badge, earned }: { badge: Badge; earned: boolean }) {
  return (
    <Tooltip content={`${badge.name}: ${badge.description}`}>
      <div
        className={`
          w-12 h-12 rounded-full flex items-center justify-center
          ${earned ? 'bg-yellow-100' : 'bg-gray-100 opacity-40'}
        `}
      >
        <img src={badge.icon_url} alt={badge.name} className="w-8 h-8" />
      </div>
    </Tooltip>
  );
}
```

### Badge Definitions

**File:** `data/seeds/badges.yaml`

```yaml
badges:
  # Streak badges
  - code: streak_7
    name: "Week Warrior"
    description: "Read for 7 days in a row"
    category: streak
    criteria: { type: streak, days: 7 }
    rarity: common

  - code: streak_30
    name: "Monthly Master"
    description: "Read for 30 days in a row"
    category: streak
    criteria: { type: streak, days: 30 }
    rarity: rare

  - code: streak_100
    name: "Century Reader"
    description: "Read for 100 days in a row"
    category: streak
    criteria: { type: streak, days: 100 }
    rarity: epic

  - code: streak_365
    name: "Year of Dedication"
    description: "Read for 365 days in a row"
    category: streak
    criteria: { type: streak, days: 365 }
    rarity: legendary

  # Completion badges
  - code: book_genesis
    name: "In the Beginning"
    description: "Complete the book of Genesis"
    category: completion
    criteria: { type: book_complete, book: Gen }
    rarity: common

  - code: gospels_complete
    name: "Gospel Scholar"
    description: "Complete all four Gospels"
    category: completion
    criteria: { type: books_complete, books: [Matt, Mark, Luke, John] }
    rarity: rare

  - code: nt_complete
    name: "New Testament Master"
    description: "Complete the entire New Testament"
    category: completion
    criteria: { type: testament_complete, testament: NT }
    rarity: epic

  - code: bible_complete
    name: "Scripture Scholar"
    description: "Read the entire Bible"
    category: completion
    criteria: { type: bible_complete }
    rarity: legendary

  # Milestone badges
  - code: chapters_100
    name: "Centurion"
    description: "Read 100 chapters total"
    category: milestone
    criteria: { type: total_chapters, chapters: 100 }
    rarity: common

  - code: chapters_500
    name: "Half Millennium"
    description: "Read 500 chapters total"
    category: milestone
    criteria: { type: total_chapters, chapters: 500 }
    rarity: rare
```

---

## 9. Keyboard-First Navigation

### Overview

Vim-style shortcuts, command palette (`Ctrl+K`), and power-user navigation.

### No Backend Changes Required

This is a frontend-only feature.

### Frontend Implementation

**Directory:** `exegesis/services/web/app/components/CommandPalette/`

```tsx
// CommandPalette.tsx
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import { useHotkeys } from 'react-hotkeys-hook';

interface CommandItem {
  id: string;
  label: string;
  shortcut?: string;
  category: string;
  action: () => void;
  icon?: React.ReactNode;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const navigate = useNavigate();

  // Toggle with Ctrl+K or Cmd+K
  useHotkeys('mod+k', (e) => {
    e.preventDefault();
    setOpen((o) => !o);
  }, { enableOnFormTags: true });

  // Close on Escape
  useHotkeys('escape', () => setOpen(false), { enabled: open });

  const commands: CommandItem[] = useMemo(() => [
    // Navigation
    { id: 'nav-search', label: 'Search Bible', shortcut: '/', category: 'Navigation', action: () => navigate('/search'), icon: <SearchIcon /> },
    { id: 'nav-parallel', label: 'Parallel View', shortcut: 'p', category: 'Navigation', action: () => navigate('/parallel') },
    { id: 'nav-timeline', label: 'Timeline', shortcut: 't', category: 'Navigation', action: () => navigate('/timeline') },
    { id: 'nav-progress', label: 'Reading Progress', category: 'Navigation', action: () => navigate('/progress') },

    // Actions
    { id: 'action-annotate', label: 'Add Annotation', shortcut: 'a', category: 'Actions', action: () => openAnnotationModal() },
    { id: 'action-bookmark', label: 'Bookmark Passage', shortcut: 'b', category: 'Actions', action: () => addBookmark() },
    { id: 'action-generate', label: 'Generate Study Outline', shortcut: 'g', category: 'Actions', action: () => navigate('/ai/generate') },

    // Go to verse
    { id: 'goto-verse', label: 'Go to Verse...', shortcut: 'g v', category: 'Navigation', action: () => openVerseJump() },

    // Settings
    { id: 'settings-theme', label: 'Toggle Dark Mode', category: 'Settings', action: () => toggleTheme() },
    { id: 'settings-font', label: 'Adjust Font Size', category: 'Settings', action: () => openFontSettings() },
  ], [navigate]);

  const filtered = useMemo(() => {
    if (!search) return commands;
    const lower = search.toLowerCase();
    return commands.filter(
      (c) => c.label.toLowerCase().includes(lower) ||
             c.category.toLowerCase().includes(lower)
    );
  }, [commands, search]);

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
    >
      <div className="fixed inset-0 bg-black/50" onClick={() => setOpen(false)} />

      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg overflow-hidden">
        <Command.Input
          value={search}
          onValueChange={setSearch}
          placeholder="Type a command or search..."
          className="w-full px-4 py-3 text-lg border-b outline-none"
        />

        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="p-4 text-center text-gray-500">
            No results found.
          </Command.Empty>

          {['Navigation', 'Actions', 'Settings'].map((category) => (
            <Command.Group key={category} heading={category}>
              {filtered
                .filter((c) => c.category === category)
                .map((command) => (
                  <Command.Item
                    key={command.id}
                    value={command.label}
                    onSelect={() => {
                      command.action();
                      setOpen(false);
                    }}
                    className="flex items-center gap-3 px-3 py-2 rounded cursor-pointer hover:bg-gray-100"
                  >
                    {command.icon}
                    <span className="flex-1">{command.label}</span>
                    {command.shortcut && (
                      <kbd className="px-2 py-1 bg-gray-100 rounded text-xs">
                        {command.shortcut}
                      </kbd>
                    )}
                  </Command.Item>
                ))}
            </Command.Group>
          ))}
        </Command.List>
      </div>
    </Command.Dialog>
  );
}

// hooks/useKeyboardNavigation.ts
export function useKeyboardNavigation() {
  const navigate = useNavigate();

  // Global shortcuts
  useHotkeys('/', (e) => {
    e.preventDefault();
    document.getElementById('search-input')?.focus();
  });

  useHotkeys('g v', () => {
    // Open verse jump dialog
  });

  useHotkeys('a', () => {
    // Open annotation modal
  });

  useHotkeys('b', () => {
    // Toggle bookmark
  });

  // Vim-style navigation for verse lists
  useHotkeys('j', () => {
    // Move to next verse/item
  });

  useHotkeys('k', () => {
    // Move to previous verse/item
  });

  useHotkeys('enter', () => {
    // Select/open current item
  });

  useHotkeys('h', () => {
    // Go back / collapse
  });

  useHotkeys('l', () => {
    // Go forward / expand
  });
}

// VerseJumpDialog.tsx
export function VerseJumpDialog() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const navigate = useNavigate();

  useHotkeys('g v', () => setOpen(true));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const osis = parseReference(input);
    if (osis) {
      navigate(`/verses/${osis}`);
      setOpen(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogTitle>Jump to Verse</DialogTitle>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g., John 3:16, Gen 1:1, Rom 8"
            className="w-full px-4 py-2 border rounded"
            autoFocus
          />
          <div className="mt-2 text-sm text-gray-500">
            Press Enter to navigate
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

### Keyboard Shortcut Reference

```
Global Shortcuts:
  Ctrl/Cmd + K     Open command palette
  /                Focus search
  g v              Jump to verse
  a                Add annotation (when viewing passage)
  b                Toggle bookmark

Navigation (Vim-style):
  j / ↓            Next item
  k / ↑            Previous item
  h / ←            Go back / collapse
  l / →            Go forward / expand
  Enter            Select / open
  Escape           Close / cancel

Reading View:
  Space            Scroll down
  Shift + Space    Scroll up
  n                Next chapter
  p                Previous chapter

Audio Player:
  Space            Play / pause
  ← / →            Skip back / forward 10s
  Shift + ← / →    Skip back / forward 30s
  [ / ]            Decrease / increase speed
```

---

## 10. Customizable Split Layouts

### Overview

Drag-and-drop pane system for simultaneous viewing of multiple content types.

### No Backend Changes Required

This is a frontend-only feature with optional layout persistence.

### Database Schema (Optional Persistence)

```sql
CREATE TABLE user_layouts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(64) NOT NULL,
    layout JSONB NOT NULL,                      -- Layout configuration
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Frontend Implementation

**Directory:** `exegesis/services/web/app/components/SplitLayout/`

```tsx
// SplitLayout.tsx
import { useState, useCallback } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { DndContext, DragEndEvent } from '@dnd-kit/core';

interface PaneConfig {
  id: string;
  type: 'passage' | 'parallel' | 'interlinear' | 'commentary' | 'notes' | 'audio' | 'timeline';
  props: Record<string, unknown>;
}

interface LayoutConfig {
  direction: 'horizontal' | 'vertical';
  panes: (PaneConfig | LayoutConfig)[];
  sizes?: number[];
}

const DEFAULT_LAYOUT: LayoutConfig = {
  direction: 'horizontal',
  panes: [
    { id: 'main', type: 'passage', props: { osis: 'John.1' } },
  ],
};

export function SplitLayout() {
  const [layout, setLayout] = useState<LayoutConfig>(DEFAULT_LAYOUT);
  const [activePaneId, setActivePaneId] = useState<string | null>(null);

  const addPane = useCallback((type: PaneConfig['type'], position: 'left' | 'right' | 'top' | 'bottom') => {
    const newPane: PaneConfig = {
      id: `pane-${Date.now()}`,
      type,
      props: {},
    };

    // Add logic to insert pane at position
    setLayout((prev) => {
      // ... layout manipulation logic
      return prev;
    });
  }, []);

  const removePane = useCallback((paneId: string) => {
    setLayout((prev) => {
      // Remove pane and restructure layout
      return filterPanes(prev, paneId);
    });
  }, []);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      // Reorder panes
      setLayout((prev) => reorderPanes(prev, active.id as string, over.id as string));
    }
  }, []);

  return (
    <DndContext onDragEnd={handleDragEnd}>
      <div className="h-full flex flex-col">
        <LayoutToolbar
          onAddPane={addPane}
          onSaveLayout={() => saveLayout(layout)}
          onLoadLayout={(saved) => setLayout(saved)}
        />

        <div className="flex-1">
          <LayoutRenderer
            layout={layout}
            activePaneId={activePaneId}
            onPaneSelect={setActivePaneId}
            onPaneRemove={removePane}
          />
        </div>
      </div>
    </DndContext>
  );
}

// LayoutRenderer.tsx
interface LayoutRendererProps {
  layout: LayoutConfig;
  activePaneId: string | null;
  onPaneSelect: (id: string) => void;
  onPaneRemove: (id: string) => void;
}

function LayoutRenderer({ layout, activePaneId, onPaneSelect, onPaneRemove }: LayoutRendererProps) {
  return (
    <PanelGroup direction={layout.direction}>
      {layout.panes.map((pane, index) => (
        <>
          {index > 0 && (
            <PanelResizeHandle className="w-1 bg-gray-200 hover:bg-blue-400 transition-colors" />
          )}
          <Panel
            key={'id' in pane ? pane.id : `group-${index}`}
            defaultSize={layout.sizes?.[index] || 100 / layout.panes.length}
          >
            {'type' in pane ? (
              <PaneWrapper
                pane={pane}
                isActive={pane.id === activePaneId}
                onSelect={() => onPaneSelect(pane.id)}
                onRemove={() => onPaneRemove(pane.id)}
              />
            ) : (
              <LayoutRenderer
                layout={pane}
                activePaneId={activePaneId}
                onPaneSelect={onPaneSelect}
                onPaneRemove={onPaneRemove}
              />
            )}
          </Panel>
        </>
      ))}
    </PanelGroup>
  );
}

// PaneWrapper.tsx
interface PaneWrapperProps {
  pane: PaneConfig;
  isActive: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

function PaneWrapper({ pane, isActive, onSelect, onRemove }: PaneWrapperProps) {
  const Component = PANE_COMPONENTS[pane.type];

  return (
    <div
      className={`h-full flex flex-col ${isActive ? 'ring-2 ring-blue-500' : ''}`}
      onClick={onSelect}
    >
      <div className="flex items-center justify-between px-2 py-1 bg-gray-100 border-b">
        <span className="text-sm font-medium">{PANE_TITLES[pane.type]}</span>
        <div className="flex gap-1">
          <PaneMenu paneId={pane.id} />
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(); }}
            className="p-1 hover:bg-gray-200 rounded"
          >
            <XIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <Component {...pane.props} />
      </div>
    </div>
  );
}

const PANE_COMPONENTS: Record<PaneConfig['type'], React.ComponentType<any>> = {
  passage: PassageView,
  parallel: ParallelViewer,
  interlinear: InterlinearView,
  commentary: CommentaryPanel,
  notes: NotesPanel,
  audio: AudioPlayer,
  timeline: TimelineMini,
};

const PANE_TITLES: Record<PaneConfig['type'], string> = {
  passage: 'Passage',
  parallel: 'Parallel Translations',
  interlinear: 'Interlinear',
  commentary: 'Commentary',
  notes: 'Notes',
  audio: 'Audio',
  timeline: 'Timeline',
};

// LayoutToolbar.tsx
interface LayoutToolbarProps {
  onAddPane: (type: PaneConfig['type'], position: 'left' | 'right' | 'top' | 'bottom') => void;
  onSaveLayout: () => void;
  onLoadLayout: (layout: LayoutConfig) => void;
}

function LayoutToolbar({ onAddPane, onSaveLayout, onLoadLayout }: LayoutToolbarProps) {
  const [savedLayouts] = useQuery({
    queryKey: ['saved-layouts'],
    queryFn: fetchSavedLayouts,
  });

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Pane
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Add pane type</DropdownMenuLabel>
          {Object.entries(PANE_TITLES).map(([type, title]) => (
            <DropdownMenuItem
              key={type}
              onClick={() => onAddPane(type as PaneConfig['type'], 'right')}
            >
              {title}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <Button variant="outline" size="sm" onClick={onSaveLayout}>
        <SaveIcon className="w-4 h-4 mr-1" />
        Save Layout
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <LayoutIcon className="w-4 h-4 mr-1" />
            Layouts
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Presets</DropdownMenuLabel>
          <DropdownMenuItem onClick={() => onLoadLayout(PRESET_STUDY)}>
            Study View (Passage + Commentary + Notes)
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => onLoadLayout(PRESET_COMPARE)}>
            Compare (2 Translations)
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => onLoadLayout(PRESET_RESEARCH)}>
            Research (Passage + Interlinear + Timeline)
          </DropdownMenuItem>

          {savedLayouts?.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Saved</DropdownMenuLabel>
              {savedLayouts.map((saved) => (
                <DropdownMenuItem
                  key={saved.id}
                  onClick={() => onLoadLayout(saved.layout)}
                >
                  {saved.name}
                </DropdownMenuItem>
              ))}
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

// Preset layouts
const PRESET_STUDY: LayoutConfig = {
  direction: 'horizontal',
  sizes: [50, 50],
  panes: [
    { id: 'passage', type: 'passage', props: {} },
    {
      direction: 'vertical',
      sizes: [60, 40],
      panes: [
        { id: 'commentary', type: 'commentary', props: {} },
        { id: 'notes', type: 'notes', props: {} },
      ],
    },
  ],
};

const PRESET_COMPARE: LayoutConfig = {
  direction: 'horizontal',
  sizes: [50, 50],
  panes: [
    { id: 'left', type: 'passage', props: { translation: 'ESV' } },
    { id: 'right', type: 'passage', props: { translation: 'NIV' } },
  ],
};

const PRESET_RESEARCH: LayoutConfig = {
  direction: 'horizontal',
  sizes: [40, 30, 30],
  panes: [
    { id: 'passage', type: 'passage', props: {} },
    { id: 'interlinear', type: 'interlinear', props: {} },
    { id: 'timeline', type: 'timeline', props: {} },
  ],
};
```

### Testing

```typescript
// SplitLayout.test.tsx
describe('SplitLayout', () => {
  it('renders default single pane', () => {
    render(<SplitLayout />);
    expect(screen.getByText('Passage')).toBeInTheDocument();
  });

  it('adds new pane when clicking Add Pane', async () => {
    render(<SplitLayout />);
    await userEvent.click(screen.getByText('Add Pane'));
    await userEvent.click(screen.getByText('Commentary'));
    expect(screen.getByText('Commentary')).toBeInTheDocument();
  });

  it('removes pane when clicking X', async () => {
    render(<SplitLayout initialLayout={PRESET_STUDY} />);
    const closeButtons = screen.getAllByRole('button', { name: /close/i });
    await userEvent.click(closeButtons[0]);
    expect(screen.queryByText('Passage')).not.toBeInTheDocument();
  });

  it('resizes panes via drag', async () => {
    render(<SplitLayout initialLayout={PRESET_COMPARE} />);
    const handle = screen.getByRole('separator');
    // Simulate drag
    fireEvent.mouseDown(handle);
    fireEvent.mouseMove(handle, { clientX: 300 });
    fireEvent.mouseUp(handle);
    // Check sizes updated
  });

  it('loads preset layout', async () => {
    render(<SplitLayout />);
    await userEvent.click(screen.getByText('Layouts'));
    await userEvent.click(screen.getByText('Study View'));
    expect(screen.getByText('Commentary')).toBeInTheDocument();
    expect(screen.getByText('Notes')).toBeInTheDocument();
  });
});
```

---

## Implementation Summary

| Feature | Backend Days | Frontend Days | Total |
|---------|--------------|---------------|-------|
| 8. Progress & Streaks | 3-4 | 4-5 | ~10 |
| 9. Keyboard Navigation | 0 | 4-5 | ~5 |
| 10. Split Layouts | 0-1 | 5-6 | ~7 |

**Combined Total for Features 8-10:** ~22 days
