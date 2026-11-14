import { useEffect, useState } from "react";
import { api, KbChunk } from "../api";
import Modal from "./Modal";

const AUTHORITY: Record<KbChunk["authority_level"], string> = {
  regulation: "Regulation (binding)",
  official_guidance: "Official guidance (HHS)",
  supporting_guidance: "Supporting guidance (NIST)",
};

export function AuthorityBadge({ level }: { level: KbChunk["authority_level"] }) {
  return <span className={`badge ${level === "regulation" ? "accent" : "neutral"}`}>{AUTHORITY[level]}</span>;
}

export default function KbChunkModal({ chunkId, onClose }: { chunkId: string; onClose: () => void }) {
  const [chunk, setChunk] = useState<KbChunk | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.kbChunk(chunkId).then(setChunk).catch((e) => setError(e.message));
  }, [chunkId]);
  return (
    <Modal title={chunk?.heading ?? chunkId} onClose={onClose}>
      {error && <div className="error">{error}</div>}
      {!chunk && !error && <span className="spinner" />}
      {chunk && (
        <div className="stack" style={{ gap: 8 }}>
          <div className="row">
            <AuthorityBadge level={chunk.authority_level} />
            <span className="faint">{chunk.citation}</span>
          </div>
          <div className="faint">{chunk.heading_path.join(" › ")}</div>
          <div className="faint">Tagged controls: {chunk.control_ids.length ? chunk.control_ids.join(", ") : "none"}</div>
          <p className="chunk-text">{chunk.text}</p>
        </div>
      )}
    </Modal>
  );
}
