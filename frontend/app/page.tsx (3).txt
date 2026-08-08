"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type Project = { id: string; title: string; status: string; platform: string };

export default function HomePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [title, setTitle] = useState("");
  const [script, setScript] = useState("");
  const [platform, setPlatform] = useState("youtube");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/projects`).then((r) => r.json()).then(setProjects).catch(() => {});
  }, []);

  async function createProject() {
    setCreating(true);
    try {
      const res = await fetch(`${API_URL}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, script, platform, target_length_seconds: 180 }),
      });
      const project = await res.json();
      router.push(`/project/${project.id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-4xl font-bold mb-2">AI Video OS</h1>
      <p className="text-neutral-400 mb-10">Direct a video. Don&apos;t edit one.</p>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 mb-12">
        <label className="block text-sm text-neutral-400 mb-2">Title</label>
        <input
          className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 mb-4 outline-none focus:border-accent"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="How the 2008 Crash Actually Happened"
        />

        <label className="block text-sm text-neutral-400 mb-2">Script</label>
        <textarea
          className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 mb-4 h-40 outline-none focus:border-accent"
          value={script}
          onChange={(e) => setScript(e.target.value)}
          placeholder="Paste your script. The Editor Agent will find the pacing for you."
        />

        <label className="block text-sm text-neutral-400 mb-2">Platform</label>
        <select
          className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 mb-6 outline-none focus:border-accent"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          <option value="youtube">YouTube (16:9)</option>
          <option value="tiktok">TikTok (9:16)</option>
          <option value="instagram">Instagram (9:16)</option>
        </select>

        <button
          onClick={createProject}
          disabled={!title || !script || creating}
          className="bg-accent text-white font-medium px-5 py-2.5 rounded-lg disabled:opacity-40"
        >
          {creating ? "Creating..." : "Start directing"}
        </button>
      </div>

      <h2 className="text-lg font-semibold mb-4">Projects</h2>
      <div className="space-y-2">
        {projects.map((p) => (
          <a
            key={p.id}
            href={`/project/${p.id}`}
            className="flex items-center justify-between bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-3 hover:border-neutral-700"
          >
            <span>{p.title}</span>
            <span className="text-xs uppercase tracking-wide text-neutral-500">{p.status}</span>
          </a>
        ))}
        {projects.length === 0 && <p className="text-neutral-600 text-sm">No projects yet.</p>}
      </div>
    </main>
  );
}
