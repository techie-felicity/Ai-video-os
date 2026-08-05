from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    script: str
    platform: str = "youtube"
    target_length_seconds: int = 180
    brand_kit_id: Optional[str] = None
    voice_profile_id: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    title: str
    script: str
    platform: str
    target_length_seconds: int
    status: str

    class Config:
        from_attributes = True


class ShotOut(BaseModel):
    id: str
    order: int
    duration_ms: int
    camera_move: str
    transition_in: str
    asset_type: Optional[str]
    asset_spec: Dict[str, Any]
    motion_params: Dict[str, Any]
    audio_cues: Dict[str, Any]
    subtitle_params: Dict[str, Any]

    class Config:
        from_attributes = True


class SceneOut(BaseModel):
    id: str
    order: int
    script_text: str
    topics: List[str]
    entities: List[str]
    emotion: Optional[str]
    tension_score: float
    editorial_directives: Dict[str, Any]
    shots: List[ShotOut] = []

    class Config:
        from_attributes = True


class SceneGraphOut(BaseModel):
    project: ProjectOut
    scenes: List[SceneOut]


class RenderJobOut(BaseModel):
    id: str
    project_id: str
    status: str
    progress: float
    output_uri: Optional[str]
    error: Optional[str]

    class Config:
        from_attributes = True
