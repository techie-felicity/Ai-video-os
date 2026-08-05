"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type Shot = {
  id: string; order: number; duration_ms: number; camera_move: string;
  transition_in: string; asset_type: string | null; asset_spec: Record<string, any>;
};
type Scene = {
  id: string; order: number; script_text: string; topics: string[];
  emotion: string | null; tension_score: number;
  editorial_directives: Record<string, any>; shots: Shot[];
};
type Project = { id: string; title: string; script: string; status: string; platform: string };

const TABS = ["Script", "Storyboard", "Preview", "AI Suggestions", "Render"] as const;

export default function ProjectPage({ params }: { params: { id: string } }) {
  const [project, setProject] = useState<Project | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Script");
  const [renderStatus, setRenderStatus] = useState<string | null>(null);

  async function refresh() {
    const p = await fetch(`${API_URL}/projects/${params.id}`).then((r) => r.json());
    setProject(p);
    if (p.status !== "draft" && p.status !== "scripting") {
      const graph = await fetch(`${API_URL}/projects/${params.id}/scene-graph`).then((r) => r.json());
      setScenes(graph.scenes ?? []);
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  async function generate() {
    await fetch(`${API_URL}/projects/${params.id}/generate`, { method: "POST" });
    setTab("Storyboard");
    refresh();
  }

  async function startRender() {
    const job = await fetch(`${API_URL}/render/${params.id}`, { method: "POST" }).then((r) => r.json());
    setRenderStatus(job.status);
    const poll = setInterval(async () => {
      const j = await fetch(`${API_URL}/render/${job.id}`).then((r) => r.json());
      setRenderStatus(`${j.status} (${Math.round(j.progress * 100)}%)`);
      if (j.status === "done" || j.status === "failed") clearInterval(poll);
    }, 4000);
  }

  if (!project) return <main className="p-10 text-neutral-500">Loading...</main>;

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{project.title}</h1>
          <span className="text-xs uppercase tracking-wide text-neutral-500">{project.status}</span>
        </div>
        {project.status === "draft" && (
          <button onClick={generate} className="bg-accent px-4 py-2 rounded-lg font-medium">
            Generate scene graph
          </button>
        )}
      </div>

      <nav className="flex gap-1 mb-8 border-b border-neutral-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${
              tab === t ? "border-b-2 border-accent text-white" : "text-neutral-500"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      {tab === "Script" && (
        <pre className="whitespace-pre-wrap text-neutral-300 leading-relaxed">{project.script}</pre>
      )}

      {tab === "Storyboard" && (
        <div className="space-y-4">
          {scenes.length === 0 && (
            <p className="text-neutral-600 text-sm">
              No scene graph yet — generate it from the Script tab.
            </p>
          )}
          {scenes.map((scene) => (
            <div key={scene.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-xs bg-neutral-800 px-2 py-0.5 rounded">{scene.emotion}</span>
                <span className="text-xs text-neutral-500">
                  tension {Math.round(scene.tension_score * 100)}%
                </span>
                <span className="text-xs text-neutral-500">{scene.shots.length} shots</span>
              </div>
              <p className="text-sm text-neutral-300 mb-3">{scene.script_text}</p>
              <div className="flex gap-2 flex-wrap">
                {scene.shots.map((shot) => (
                  <div
                    key={shot.id}
                    className="text-xs bg-neutral-950 border border-neutral-800 rounded px-2 py-1"
                    title={JSON.stringify(shot.asset_spec)}
                  >
                    {shot.asset_type} · {shot.camera_move} · {(shot.duration_ms / 1000).toFixed(1)}s
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "Preview" && (
        <p className="text-neutral-600 text-sm">
          Wire this to a Remotion Player component (`@remotion/player`) pointed at the same
          Documentary composition used for rendering, fed the live scene graph as props.
        </p>
      )}

      {tab === "AI Suggestions" && (
        <div className="space-y-3">
          {scenes.map((scene) => (
            <div key={scene.id} className="text-sm text-neutral-400 border-l-2 border-accent pl-3">
              <strong className="text-neutral-200">Scene {scene.order + 1}:</strong>{" "}
              cadence {scene.editorial_directives?.cut_cadence_seconds}s/cut · music{" "}
              {scene.editorial_directives?.music_intensity}
              {scene.editorial_directives?.reveal_moment ? " · reveal moment" : ""}
            </div>
          ))}
        </div>
      )}

      {tab === "Render" && (
        <div>
          <button
            onClick={startRender}
            disabled={project.status !== "ready_to_render"}
            className="bg-accent px-4 py-2 rounded-lg font-medium disabled:opacity-40"
          >
            Render video
          </button>
          {renderStatus && <p className="mt-4 text-sm text-neutral-400">{renderStatus}</p>}
        </div>
      )}
    </main>
  );
}
