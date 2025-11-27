# Features 4-5: AI & Collaboration

## 4. AI Study Outline Generator

### Overview

Generate sermon outlines, discussion questions, or study guide structures using the existing RAG pipeline and LLM integration.

### Database Schema

```sql
CREATE TABLE study_outlines (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    osis_range VARCHAR(64) NOT NULL,            -- 'John.3.1-John.3.21'
    outline_type VARCHAR(32) NOT NULL,          -- 'sermon', 'study_guide', 'discussion'
    title VARCHAR(256),
    content JSONB NOT NULL,
    source_passages JSONB DEFAULT '[]',
    model_used VARCHAR(64),
    prompt_template_version VARCHAR(16),
    feedback_rating INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_outlines_user ON study_outlines(user_id);
CREATE INDEX ix_outlines_osis ON study_outlines(osis_range);

CREATE TABLE prompt_templates (
    id VARCHAR(36) PRIMARY KEY,
    template_type VARCHAR(32) NOT NULL,
    version VARCHAR(16) NOT NULL,
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(template_type, version)
);
```

### API Specification

**Endpoint:** `POST /ai/generate-outline`

```python
class GenerateOutlineRequest(BaseModel):
    osis_range: str
    outline_type: Literal["sermon", "study_guide", "discussion", "devotional"]
    audience: str | None = None
    emphasis: list[str] | None = None
    include_cross_references: bool = True
    include_commentary_insights: bool = True
    length: Literal["brief", "standard", "comprehensive"] = "standard"

class SermonPoint(BaseModel):
    number: int
    title: str
    verse_focus: str
    explanation: str
    sub_points: list[str]
    supporting_references: list[str]

class SermonOutline(BaseModel):
    title: str
    main_theme: str
    introduction: str
    points: list[SermonPoint]
    illustrations: list[str]
    applications: list[str]
    conclusion: str
    cross_references: list[str]

class StudyGuide(BaseModel):
    title: str
    overview: str
    context_section: str
    verse_analysis: list[dict]
    discussion_questions: list[dict]
    application_challenges: list[str]

@router.post("/generate-outline", response_model=StudyOutlineResponse)
async def generate_outline(
    request: GenerateOutlineRequest,
    current_user: User | None = Depends(get_optional_user),
    session: Session = Depends(get_session),
) -> StudyOutlineResponse:
    """Generate AI-powered study outline for a passage."""
```

### Application Service

**File:** `exegesis/application/ai/outline_generator.py`

```python
from exegesis.infrastructure.api.app.retrieval.retriever.hybrid import hybrid_search

class OutlineGeneratorService:
    def __init__(
        self,
        llm_client: LLMClient,
        verse_service: VerseService,
        template_repository: PromptTemplateRepository,
    ):
        self._llm = llm_client
        self._verse = verse_service
        self._templates = template_repository

    async def generate(
        self,
        osis_range: str,
        outline_type: str,
        options: OutlineOptions,
        session: Session,
    ) -> StudyOutline:
        # 1. Fetch passage text
        passage_text = self._verse.fetch_range(osis_range)

        # 2. RAG retrieval for commentary context
        context_results = hybrid_search(
            session=session,
            query=f"commentary analysis exegesis {osis_range}",
            collection="commentaries",
            top_k=8,
        )
        commentary_context = "\n\n".join([
            f"[{r.source}]: {r.snippet}" for r in context_results.results
        ])

        # 3. Get cross-references if requested
        cross_refs = ""
        if options.include_cross_references:
            refs = self._get_cross_references(osis_range, session)
            cross_refs = "\n".join([f"- {r.target}: {r.preview}" for r in refs])

        # 4. Build prompt
        template = self._templates.get_active(outline_type)
        prompt = template.user_prompt_template.format(
            osis_range=osis_range,
            passage_text=passage_text,
            commentary_context=commentary_context,
            cross_references=cross_refs,
            audience=options.audience or "general adult congregation",
            emphasis=", ".join(options.emphasis or ["application"]),
            length=options.length,
        )

        # 5. Generate with LLM
        response = await self._llm.generate(
            system=template.system_prompt,
            user=prompt,
            response_format={"type": "json_object"},
            max_tokens=self._get_max_tokens(options.length),
        )

        # 6. Parse and validate
        return self._parse_outline(response, outline_type)

    def _get_max_tokens(self, length: str) -> int:
        return {"brief": 1500, "standard": 3000, "comprehensive": 5000}[length]

    def _parse_outline(self, response: str, outline_type: str) -> StudyOutline:
        import json
        data = json.loads(response)

        if outline_type == "sermon":
            return SermonOutline(**data)
        elif outline_type == "study_guide":
            return StudyGuide(**data)
        elif outline_type == "discussion":
            return DiscussionGuide(**data)
        else:
            return DevotionalOutline(**data)
```

### Prompt Templates

**File:** `data/seeds/prompt_templates.yaml`

```yaml
prompt_templates:
  - template_type: sermon
    version: "1.0"
    system_prompt: |
      You are an expert biblical expositor and homiletics professor with deep knowledge
      of hermeneutics, systematic theology, and practical application.

      Generate sermon outlines that are:
      - Exegetically faithful to the original text and context
      - Structurally clear with 3-5 main points derived from the text
      - Rich in cross-references that illuminate the passage
      - Applicable to contemporary life with concrete examples
      - Theologically sound and balanced

      Always respond in valid JSON matching the SermonOutline schema exactly.
      Do not include markdown formatting in the JSON values.

    user_prompt_template: |
      Generate a sermon outline for: {osis_range}

      === PASSAGE TEXT ===
      {passage_text}

      === SCHOLARLY COMMENTARY CONTEXT ===
      {commentary_context}

      === CROSS-REFERENCES ===
      {cross_references}

      === PARAMETERS ===
      Target Audience: {audience}
      Emphasis Areas: {emphasis}
      Length: {length}

      Generate a {length} sermon outline with clear structure, practical applications,
      and faithful exegesis. Include relevant cross-references for each main point.

  - template_type: study_guide
    version: "1.0"
    system_prompt: |
      You are a Bible study curriculum developer creating materials for small group
      discussion. Your study guides should facilitate discovery, discussion, and
      life application.

      Create study guides that include:
      - Historical and literary context
      - Verse-by-verse analysis with key observations
      - Discussion questions at three levels: Observation, Interpretation, Application
      - Practical application challenges

      Always respond in valid JSON matching the StudyGuide schema exactly.

    user_prompt_template: |
      Create a study guide for: {osis_range}

      === PASSAGE TEXT ===
      {passage_text}

      === SCHOLARLY CONTEXT ===
      {commentary_context}

      === PARAMETERS ===
      Target Audience: {audience}
      Focus Areas: {emphasis}
      Depth: {length}

      Generate discussion questions that progress from observation to interpretation
      to application. Include at least 2 questions per category.

  - template_type: discussion
    version: "1.0"
    system_prompt: |
      You are a facilitator creating discussion questions for a Bible study group.
      Questions should be open-ended, thought-provoking, and lead to meaningful
      conversation about the text and its implications.

      Include questions that:
      - Help participants observe details in the text
      - Explore meaning and theological significance
      - Connect to personal experience and application
      - Address potential objections or difficulties

      Respond in valid JSON with a list of categorized questions.

    user_prompt_template: |
      Generate discussion questions for: {osis_range}

      {passage_text}

      Context: {commentary_context}

      Audience: {audience}
      Number of questions: {"5-7" if length == "brief" else "10-15" if length == "standard" else "15-20"}
```

### Frontend Components

**Directory:** `frontend/src/components/OutlineGenerator/`

```tsx
// index.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { PassageSelector } from './PassageSelector';
import { OptionsPanel } from './OptionsPanel';
import { OutlineViewer } from './OutlineViewer';
import { generateOutline } from '@/api/ai';

export function OutlineGenerator() {
  const [osisRange, setOsisRange] = useState('');
  const [options, setOptions] = useState<OutlineOptions>({
    outline_type: 'sermon',
    audience: '',
    emphasis: [],
    include_cross_references: true,
    length: 'standard',
  });

  const mutation = useMutation({
    mutationFn: () => generateOutline({ osis_range: osisRange, ...options }),
  });

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl font-bold">AI Study Outline Generator</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-1 space-y-4">
          <PassageSelector value={osisRange} onChange={setOsisRange} />
          <OptionsPanel options={options} onChange={setOptions} />
          <button
            onClick={() => mutation.mutate()}
            disabled={!osisRange || mutation.isPending}
            className="w-full btn btn-primary"
          >
            {mutation.isPending ? 'Generating...' : 'Generate Outline'}
          </button>
        </div>

        <div className="md:col-span-2">
          {mutation.isPending && <GeneratingIndicator />}
          {mutation.data && <OutlineViewer outline={mutation.data} />}
          {mutation.error && <ErrorDisplay error={mutation.error} />}
        </div>
      </div>
    </div>
  );
}

// OutlineViewer.tsx
interface OutlineViewerProps {
  outline: SermonOutline | StudyGuide;
}

export function OutlineViewer({ outline }: OutlineViewerProps) {
  if ('points' in outline) {
    return <SermonOutlineView outline={outline} />;
  }
  return <StudyGuideView outline={outline} />;
}

function SermonOutlineView({ outline }: { outline: SermonOutline }) {
  return (
    <div className="prose max-w-none">
      <h2>{outline.title}</h2>
      <p className="text-lg text-gray-600">{outline.main_theme}</p>

      <section>
        <h3>Introduction</h3>
        <p>{outline.introduction}</p>
      </section>

      {outline.points.map((point) => (
        <section key={point.number} className="border-l-4 border-blue-500 pl-4">
          <h3>{point.number}. {point.title}</h3>
          <p className="text-sm text-gray-500">Focus: {point.verse_focus}</p>
          <p>{point.explanation}</p>
          {point.sub_points.length > 0 && (
            <ul>
              {point.sub_points.map((sp, i) => <li key={i}>{sp}</li>)}
            </ul>
          )}
          {point.supporting_references.length > 0 && (
            <p className="text-sm">
              <strong>Cross-references:</strong> {point.supporting_references.join(', ')}
            </p>
          )}
        </section>
      ))}

      <section>
        <h3>Application</h3>
        <ul>
          {outline.applications.map((app, i) => <li key={i}>{app}</li>)}
        </ul>
      </section>

      <section>
        <h3>Conclusion</h3>
        <p>{outline.conclusion}</p>
      </section>
    </div>
  );
}
```

---

## 5. Collaborative Annotations & Workspaces

### Overview

Share annotation layers with study groups, view others' highlights/notes with permission controls.

### Database Schema

```sql
CREATE TABLE workspaces (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    owner_id VARCHAR(36) NOT NULL,
    visibility VARCHAR(16) DEFAULT 'private',   -- 'private', 'invite', 'public'
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workspace_members (
    workspace_id VARCHAR(36) REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id VARCHAR(36) NOT NULL,
    role VARCHAR(16) DEFAULT 'member',          -- 'owner', 'admin', 'member', 'viewer'
    joined_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE workspace_invitations (
    id VARCHAR(36) PRIMARY KEY,
    workspace_id VARCHAR(36) REFERENCES workspaces(id) ON DELETE CASCADE,
    email VARCHAR(256) NOT NULL,
    role VARCHAR(16) DEFAULT 'member',
    token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    accepted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Extend existing annotations table
ALTER TABLE document_annotations
    ADD COLUMN workspace_id VARCHAR(36) REFERENCES workspaces(id),
    ADD COLUMN visibility VARCHAR(16) DEFAULT 'private',
    ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE;

CREATE INDEX ix_annotations_workspace ON document_annotations(workspace_id);
CREATE INDEX ix_annotations_visibility ON document_annotations(visibility);

CREATE TABLE annotation_reactions (
    id VARCHAR(36) PRIMARY KEY,
    annotation_id VARCHAR(36) REFERENCES document_annotations(id) ON DELETE CASCADE,
    user_id VARCHAR(36) NOT NULL,
    reaction_type VARCHAR(16) NOT NULL,         -- 'like', 'insightful', 'question'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(annotation_id, user_id, reaction_type)
);

CREATE TABLE annotation_replies (
    id VARCHAR(36) PRIMARY KEY,
    annotation_id VARCHAR(36) REFERENCES document_annotations(id) ON DELETE CASCADE,
    user_id VARCHAR(36) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### API Specification

#### Workspace Endpoints

```python
# POST /workspaces
class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str | None = None
    visibility: Literal["private", "invite", "public"] = "private"

@router.post("/", response_model=WorkspaceResponse)
def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkspaceResponse:
    ...

# GET /workspaces
@router.get("/", response_model=WorkspaceListResponse)
def list_workspaces(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkspaceListResponse:
    """List workspaces user owns or is member of."""
    ...

# POST /workspaces/{id}/invite
class InviteMemberRequest(BaseModel):
    email: str
    role: Literal["admin", "member", "viewer"] = "member"

@router.post("/{workspace_id}/invite", response_model=InvitationResponse)
def invite_member(
    workspace_id: str,
    request: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> InvitationResponse:
    ...

# POST /workspaces/join/{token}
@router.post("/join/{token}", response_model=WorkspaceResponse)
def join_workspace(
    token: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkspaceResponse:
    ...
```

#### Shared Annotation Endpoints

```python
# GET /annotations/shared
@router.get("/shared", response_model=SharedAnnotationsResponse)
def get_shared_annotations(
    workspace_id: str | None = Query(default=None),
    osis: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SharedAnnotationsResponse:
    """Get annotations visible to current user."""
    ...

# PATCH /annotations/{id}/visibility
@router.patch("/{annotation_id}/visibility")
def update_annotation_visibility(
    annotation_id: str,
    visibility: Literal["private", "workspace", "public"],
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AnnotationResponse:
    ...

# POST /annotations/{id}/reactions
class ReactionRequest(BaseModel):
    reaction_type: Literal["like", "insightful", "question", "disagree"]

@router.post("/{annotation_id}/reactions")
def add_reaction(
    annotation_id: str,
    reaction: ReactionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReactionResponse:
    ...

# POST /annotations/{id}/replies
class ReplyRequest(BaseModel):
    body: str

@router.post("/{annotation_id}/replies")
def add_reply(
    annotation_id: str,
    reply: ReplyRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReplyResponse:
    ...
```

### Application Services

**File:** `exegesis/application/collaboration/workspace_service.py`

```python
import secrets
from datetime import datetime, timedelta

class WorkspaceService:
    def __init__(
        self,
        workspace_repository: WorkspaceRepository,
        member_repository: WorkspaceMemberRepository,
        invitation_repository: InvitationRepository,
    ):
        self._workspace_repo = workspace_repository
        self._member_repo = member_repository
        self._invitation_repo = invitation_repository

    def create_workspace(
        self,
        owner_id: str,
        name: str,
        description: str | None = None,
        visibility: str = "private",
    ) -> Workspace:
        workspace = Workspace(
            name=name,
            description=description,
            owner_id=owner_id,
            visibility=visibility,
        )
        self._workspace_repo.add(workspace)

        # Add owner as member
        self._member_repo.add(WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role="owner",
        ))

        return workspace

    def invite_member(
        self,
        workspace_id: str,
        inviter_id: str,
        email: str,
        role: str = "member",
    ) -> Invitation:
        # Verify inviter has permission
        inviter_membership = self._member_repo.get(workspace_id, inviter_id)
        if not inviter_membership or inviter_membership.role not in ("owner", "admin"):
            raise PermissionError("Only owners and admins can invite members")

        # Generate invitation
        invitation = WorkspaceInvitation(
            workspace_id=workspace_id,
            email=email,
            role=role,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        self._invitation_repo.add(invitation)

        # TODO: Send email notification

        return invitation

    def accept_invitation(self, token: str, user_id: str) -> Workspace:
        invitation = self._invitation_repo.get_by_token(token)

        if not invitation:
            raise ValueError("Invalid invitation token")
        if invitation.expires_at < datetime.utcnow():
            raise ValueError("Invitation has expired")
        if invitation.accepted_at:
            raise ValueError("Invitation already used")

        # Add member
        self._member_repo.add(WorkspaceMember(
            workspace_id=invitation.workspace_id,
            user_id=user_id,
            role=invitation.role,
        ))

        # Mark invitation as accepted
        invitation.accepted_at = datetime.utcnow()
        self._invitation_repo.update(invitation)

        return self._workspace_repo.get(invitation.workspace_id)

    def get_user_workspaces(self, user_id: str) -> list[Workspace]:
        memberships = self._member_repo.get_by_user(user_id)
        return [
            self._workspace_repo.get(m.workspace_id)
            for m in memberships
        ]

    def check_permission(
        self,
        workspace_id: str,
        user_id: str,
        required_role: str,
    ) -> bool:
        membership = self._member_repo.get(workspace_id, user_id)
        if not membership:
            return False

        role_hierarchy = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}
        return role_hierarchy.get(membership.role, 0) >= role_hierarchy.get(required_role, 0)
```

**File:** `exegesis/application/collaboration/shared_annotation_service.py`

```python
class SharedAnnotationService:
    def __init__(
        self,
        annotation_repository: AnnotationRepository,
        workspace_service: WorkspaceService,
    ):
        self._annotation_repo = annotation_repository
        self._workspace_service = workspace_service

    def get_visible_annotations(
        self,
        user_id: str,
        filters: AnnotationFilters,
    ) -> list[Annotation]:
        # Get user's workspace memberships
        user_workspaces = self._workspace_service.get_user_workspaces(user_id)
        workspace_ids = [w.id for w in user_workspaces]

        # Build query conditions
        conditions = []

        # Own annotations (any visibility)
        conditions.append({"user_id": user_id})

        # Public annotations
        conditions.append({"visibility": "public"})

        # Workspace annotations where user is member
        if workspace_ids:
            conditions.append({
                "visibility": "workspace",
                "workspace_id": {"$in": workspace_ids}
            })

        return self._annotation_repo.query(
            or_conditions=conditions,
            osis=filters.osis,
            document_id=filters.document_id,
        )

    def share_to_workspace(
        self,
        annotation_id: str,
        user_id: str,
        workspace_id: str,
    ) -> Annotation:
        annotation = self._annotation_repo.get(annotation_id)

        # Verify ownership
        if annotation.user_id != user_id:
            raise PermissionError("Can only share own annotations")

        # Verify workspace membership
        if not self._workspace_service.check_permission(workspace_id, user_id, "member"):
            raise PermissionError("Must be workspace member to share")

        # Update annotation
        annotation.workspace_id = workspace_id
        annotation.visibility = "workspace"
        self._annotation_repo.update(annotation)

        return annotation
```

### Frontend Components

**Directory:** `frontend/src/components/Collaboration/`

```tsx
// WorkspaceList.tsx
export function WorkspaceList() {
  const { data: workspaces } = useQuery({
    queryKey: ['workspaces'],
    queryFn: fetchWorkspaces,
  });

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">My Workspaces</h2>
        <CreateWorkspaceButton />
      </div>

      {workspaces?.map((ws) => (
        <WorkspaceCard key={ws.id} workspace={ws} />
      ))}
    </div>
  );
}

// SharedAnnotationLayer.tsx
interface SharedAnnotationLayerProps {
  osis: string;
  workspaceId?: string;
}

export function SharedAnnotationLayer({ osis, workspaceId }: SharedAnnotationLayerProps) {
  const { data: annotations } = useQuery({
    queryKey: ['shared-annotations', osis, workspaceId],
    queryFn: () => fetchSharedAnnotations({ osis, workspace_id: workspaceId }),
  });

  const groupedByUser = useMemo(() => {
    return groupBy(annotations || [], 'user_id');
  }, [annotations]);

  return (
    <div className="relative">
      {Object.entries(groupedByUser).map(([userId, userAnnotations]) => (
        <UserAnnotationLayer
          key={userId}
          userId={userId}
          annotations={userAnnotations}
          color={getUserColor(userId)}
        />
      ))}
    </div>
  );
}

// AnnotationThread.tsx
interface AnnotationThreadProps {
  annotation: Annotation;
}

export function AnnotationThread({ annotation }: AnnotationThreadProps) {
  const [showReplies, setShowReplies] = useState(false);
  const addReaction = useMutation({ mutationFn: postReaction });
  const addReply = useMutation({ mutationFn: postReply });

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-start gap-3">
        <UserAvatar userId={annotation.user_id} />
        <div className="flex-1">
          <p className="font-medium">{annotation.user_name}</p>
          <p className="text-gray-700">{annotation.body}</p>

          <div className="flex gap-2 mt-2">
            {['like', 'insightful', 'question'].map((type) => (
              <ReactionButton
                key={type}
                type={type}
                count={annotation.reactions?.[type] || 0}
                active={annotation.user_reactions?.includes(type)}
                onClick={() => addReaction.mutate({
                  annotation_id: annotation.id,
                  reaction_type: type,
                })}
              />
            ))}
            <button
              onClick={() => setShowReplies(!showReplies)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {annotation.reply_count} replies
            </button>
          </div>
        </div>
      </div>

      {showReplies && (
        <RepliesSection
          annotationId={annotation.id}
          onReply={(body) => addReply.mutate({
            annotation_id: annotation.id,
            body,
          })}
        />
      )}
    </div>
  );
}
```

### Real-Time Updates (WebSocket)

**File:** `exegesis/infrastructure/api/app/websocket/collaboration.py`

```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set

class ConnectionManager:
    def __init__(self):
        self.workspace_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, workspace_id: str):
        await websocket.accept()
        if workspace_id not in self.workspace_connections:
            self.workspace_connections[workspace_id] = set()
        self.workspace_connections[workspace_id].add(websocket)

    def disconnect(self, websocket: WebSocket, workspace_id: str):
        self.workspace_connections.get(workspace_id, set()).discard(websocket)

    async def broadcast_to_workspace(self, workspace_id: str, message: dict):
        connections = self.workspace_connections.get(workspace_id, set())
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/ws/workspace/{workspace_id}")
async def workspace_websocket(
    websocket: WebSocket,
    workspace_id: str,
    token: str = Query(...),
):
    # Verify token and get user
    user = await verify_ws_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    # Verify workspace membership
    # ...

    await manager.connect(websocket, workspace_id)
    try:
        while True:
            data = await websocket.receive_json()

            # Handle different message types
            if data["type"] == "annotation_created":
                await manager.broadcast_to_workspace(workspace_id, {
                    "type": "annotation_created",
                    "annotation": data["annotation"],
                    "user_id": user.id,
                })
            elif data["type"] == "reaction_added":
                await manager.broadcast_to_workspace(workspace_id, {
                    "type": "reaction_added",
                    "annotation_id": data["annotation_id"],
                    "reaction": data["reaction"],
                    "user_id": user.id,
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, workspace_id)
```

### Testing

```python
# tests/application/collaboration/test_workspace_service.py

def test_create_workspace_adds_owner_as_member(service, user):
    workspace = service.create_workspace(user.id, "Test Group")
    members = service.get_workspace_members(workspace.id)
    assert len(members) == 1
    assert members[0].user_id == user.id
    assert members[0].role == "owner"

def test_invite_member_generates_valid_token(service, workspace, admin_user):
    invitation = service.invite_member(
        workspace.id, admin_user.id, "newuser@example.com"
    )
    assert invitation.token
    assert len(invitation.token) > 20
    assert invitation.expires_at > datetime.utcnow()

def test_accept_invitation_adds_member(service, invitation, new_user):
    workspace = service.accept_invitation(invitation.token, new_user.id)
    assert service.check_permission(workspace.id, new_user.id, "member")

def test_expired_invitation_rejected(service, expired_invitation, user):
    with pytest.raises(ValueError, match="expired"):
        service.accept_invitation(expired_invitation.token, user.id)

# tests/application/collaboration/test_shared_annotation_service.py

def test_get_visible_annotations_includes_own(service, user, own_annotation):
    annotations = service.get_visible_annotations(user.id, AnnotationFilters())
    assert own_annotation.id in [a.id for a in annotations]

def test_get_visible_annotations_includes_workspace(service, member, workspace_annotation):
    annotations = service.get_visible_annotations(member.id, AnnotationFilters())
    assert workspace_annotation.id in [a.id for a in annotations]

def test_get_visible_annotations_excludes_other_workspace(service, user, other_workspace_annotation):
    annotations = service.get_visible_annotations(user.id, AnnotationFilters())
    assert other_workspace_annotation.id not in [a.id for a in annotations]
```
