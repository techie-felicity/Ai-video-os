"""
Scene Graph schema.

Design principle: the scene graph is the product. Every agent reads/writes
here, and every write is what a human editor could also make by hand later
(so the frontend can eventually let users edit any of this directly).
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Float, ForeignKey, DateTime, Enum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    scripting = "scripting"
    storyboarding = "storyboarding"
    asset_planning = "asset_planning"
    ready_to_render = "ready_to_render"
    rendering = "rendering"
    rendered = "rendered"
    failed = "failed"


class Platform(str, enum.Enum):
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    script = Column(Text, nullable=False)
    platform = Column(Enum(Platform), default=Platform.youtube)
    target_length_seconds = Column(Integer, default=180)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.draft)
    brand_kit_id = Column(UUID(as_uuid=False), ForeignKey("brand_kits.id"), nullable=True)
    voice_profile_id = Column(UUID(as_uuid=False), ForeignKey("voice_profiles.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan", order_by="Scene.order")
    brand_kit = relationship("BrandKit")
    voice_profile = relationship("VoiceProfile")


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    primary_color = Column(String, default="#111111")
    secondary_color = Column(String, default="#F5F5F5")
    accent_color = Column(String, default="#FF4D00")
    font_heading = Column(String, default="Inter")
    font_body = Column(String, default="Inter")
    logo_asset_uri = Column(String, nullable=True)


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    provider = Column(String, default="elevenlabs")
    provider_voice_id = Column(String, nullable=False)
    style_params = Column(JSON, default=dict)


class Scene(Base):
    """One narrative beat, produced by ScriptAgent, annotated by EditorAgent."""
    __tablename__ = "scenes"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False)
    order = Column(Integer, nullable=False)
    script_text = Column(Text, nullable=False)
    topics = Column(JSON, default=list)       # ["conflict", "product launch"]
    entities = Column(JSON, default=list)      # named entities detected
    emotion = Column(String, nullable=True)    # e.g. "tension", "curiosity", "relief"
    tension_score = Column(Float, default=0.0) # 0-1, from EditorAgent
    editorial_directives = Column(JSON, default=dict)  # cut cadence, pause points, etc.

    project = relationship("Project", back_populates="scenes")
    shots = relationship("Shot", back_populates="scene", cascade="all, delete-orphan", order_by="Shot.order")


class Shot(Base):
    """One concrete shot, produced by StoryboardAgent + Visual/Motion/Audio/Subtitle agents."""
    __tablename__ = "shots"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    scene_id = Column(UUID(as_uuid=False), ForeignKey("scenes.id"), nullable=False)
    order = Column(Integer, nullable=False)
    duration_ms = Column(Integer, default=2500)
    camera_move = Column(String, default="static")      # static, push_in, pan_left, ...
    transition_in = Column(String, default="cut")        # cut, crossfade, glitch, whip_pan
    asset_type = Column(String, nullable=True)            # stock, ai_image, chart, map, ui_mockup...
    asset_spec = Column(JSON, default=dict)                # prompt/query used to source the asset
    asset_id = Column(UUID(as_uuid=False), ForeignKey("assets.id"), nullable=True)
    motion_params = Column(JSON, default=dict)             # zoom, parallax depth, blur, etc.
    audio_cues = Column(JSON, default=dict)                 # music/sfx triggers for this shot
    subtitle_params = Column(JSON, default=dict)            # style/animation for captions in this shot

    scene = relationship("Scene", back_populates="shots")
    asset = relationship("Asset")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    type = Column(String, nullable=False)       # image, video, chart, audio
    provider = Column(String, nullable=True)     # pexels, flux, suno, elevenlabs...
    uri = Column(String, nullable=False)
    asset_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False)
    status = Column(String, default="queued")   # queued, running, done, failed
    progress = Column(Float, default=0.0)
    output_uri = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentRun(Base):
    """Audit log of every agent call — doubles as your future fine-tuning dataset."""
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False)
    agent_name = Column(String, nullable=False)
    model_used = Column(String, nullable=True)
    input_payload = Column(JSON, default=dict)
    output_payload = Column(JSON, default=dict)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
