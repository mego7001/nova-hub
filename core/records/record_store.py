from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    mission_id: str
    intent_id: str
    operator_id: str
    decision_type: str
    decision_outcome: str
    recorded_at: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "decision_id": self.decision_id,
            "mission_id": self.mission_id,
            "intent_id": self.intent_id,
            "operator_id": self.operator_id,
            "decision_type": self.decision_type,
            "decision_outcome": self.decision_outcome,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    mission_id: str
    intent_id: str
    decision_id: str
    run_phase: str
    run_state: str
    started_at: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "run_id": self.run_id,
            "mission_id": self.mission_id,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "run_phase": self.run_phase,
            "run_state": self.run_state,
            "started_at": self.started_at,
        }


@dataclass(frozen=True)
class ArtifactManifest:
    run_id: str
    artifacts: List[str]
    recorded_at: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "artifacts": list(self.artifacts),
            "recorded_at": self.recorded_at,
        }


class RecordStore:
    def __init__(self, records_dir: str):
        self.records_dir = records_dir
        os.makedirs(self.records_dir, exist_ok=True)
        self._decisions: Dict[str, DecisionRecord] = {}
        self._runs: Dict[str, RunRecord] = {}
        self._artifacts: Dict[str, List[str]] = {}
        self._load()

    def add_decision(self, rec: DecisionRecord) -> None:
        self._decisions[rec.decision_id] = rec
        self._persist_decisions()

    def has_decision(self, decision_id: str) -> bool:
        return bool(decision_id) and decision_id in self._decisions

    def add_run(self, rec: RunRecord) -> None:
        self._runs[rec.run_id] = rec
        self._persist_runs()

    def has_run(self, run_id: str) -> bool:
        return bool(run_id) and run_id in self._runs

    def add_artifact(self, run_id: str, artifact_ref: str) -> None:
        if not run_id or not artifact_ref:
            return
        items = self._artifacts.get(run_id) or []
        if artifact_ref not in items:
            items.append(artifact_ref)
        self._artifacts[run_id] = items
        self._persist_artifacts()

    def has_artifact(self, run_id: str, artifact_ref: str) -> bool:
        if not run_id or not artifact_ref:
            return False
        return artifact_ref in (self._artifacts.get(run_id) or [])

    def _load(self) -> None:
        self._decisions = self._load_records("decision_records.json", DecisionRecord)
        self._runs = self._load_records("run_records.json", RunRecord)
        self._artifacts = self._load_artifacts()

    def _load_records(self, name: str, cls):
        path = os.path.join(self.records_dir, name)
        if not os.path.exists(path):
            return {}
        try:
            data = json.loads(open(path, "r", encoding="utf-8").read()) or []
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return {}
        out = {}
        for item in data:
            try:
                rec = cls(**item)
                key = getattr(rec, list(item.keys())[0])
                if hasattr(rec, "decision_id"):
                    key = rec.decision_id
                elif hasattr(rec, "run_id"):
                    key = rec.run_id
                out[key] = rec
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                continue
        return out

    def _load_artifacts(self) -> Dict[str, List[str]]:
        path = os.path.join(self.records_dir, "artifact_manifests.json")
        if not os.path.exists(path):
            return {}
        try:
            data = json.loads(open(path, "r", encoding="utf-8").read()) or []
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return {}
        out: Dict[str, List[str]] = {}
        for item in data:
            run_id = str(item.get("run_id") or "")
            artifacts = item.get("artifacts") or []
            if run_id:
                out[run_id] = [str(a) for a in artifacts if a]
        return out

    def _persist_decisions(self) -> None:
        self._write("decision_records.json", [d.to_dict() for d in self._decisions.values()])

    def _persist_runs(self) -> None:
        self._write("run_records.json", [r.to_dict() for r in self._runs.values()])

    def _persist_artifacts(self) -> None:
        payload = []
        for run_id, artifacts in self._artifacts.items():
            payload.append(
                ArtifactManifest(run_id=run_id, artifacts=artifacts, recorded_at=_now()).to_dict()
            )
        self._write("artifact_manifests.json", payload)

    def _write(self, name: str, payload: object) -> None:
        path = os.path.join(self.records_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

