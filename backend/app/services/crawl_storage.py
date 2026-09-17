import os
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("locallift.storage")

BASE_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"

class CrawlStorage:
    """
    Multi-tenant, transactional crawl storage engine.
    Guarantees strict project-level directory isolation:
    storage/projects/{project_id}/crawls/{session_id}/
    
    Validates artifact completeness:
    - metadata.json
    - pages.json
    - issues.json
    - internal_links.json
    - external_links.json
    - broken_links.json
    - link_records.json
    - summary.json
    """

    REQUIRED_ARTIFACTS = [
        "metadata.json",
        "pages.json",
        "issues.json",
        "internal_links.json",
        "external_links.json",
        "broken_links.json",
        "link_records.json",
        "summary.json",
    ]

    @classmethod
    def get_project_storage_dir(cls, project_id: int, session_id: Optional[int] = None) -> Path:
        if not isinstance(project_id, int) or project_id <= 0:
            raise ValueError(f"SECURITY_VIOLATION: Invalid project_id '{project_id}'")
        
        proj_dir = BASE_STORAGE_DIR / "projects" / str(project_id)
        proj_dir.mkdir(parents=True, exist_ok=True)
        
        if session_id:
            if not isinstance(session_id, int) or session_id <= 0:
                raise ValueError(f"SECURITY_VIOLATION: Invalid session_id '{session_id}'")
            session_dir = proj_dir / "crawls" / str(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            return session_dir
        
        return proj_dir

    @classmethod
    def save_crawl_session_artifacts(
        cls,
        project_id: int,
        session_id: int,
        metadata: Dict[str, Any],
        pages: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
        internal_links: List[Dict[str, Any]],
        external_links: List[Dict[str, Any]],
        broken_links: List[Dict[str, Any]],
        link_records: List[Dict[str, Any]],
        summary: Dict[str, Any],
    ) -> Tuple[bool, str]:
        session_dir = cls.get_project_storage_dir(project_id, session_id)
        
        artifacts_data = {
            "metadata.json": metadata,
            "pages.json": pages,
            "issues.json": issues,
            "internal_links.json": internal_links,
            "external_links.json": external_links,
            "broken_links.json": broken_links,
            "link_records.json": link_records,
            "summary.json": summary,
        }

        try:
            # Atomic write using temporary files
            for filename, data in artifacts_data.items():
                file_path = session_dir / filename
                tmp_path = session_dir / f".tmp_{filename}"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                shutil.move(tmp_path, file_path)

            # Validate all written artifacts exist and are readable JSON
            validation_ok, val_err = cls.validate_crawl_artifacts(project_id, session_id)
            if not validation_ok:
                return False, f"Artifact validation failed after write: {val_err}"

            # Save latest pointers strictly inside project directory
            latest_file = cls.get_project_storage_dir(project_id) / "latest.json"
            tmp_latest = cls.get_project_storage_dir(project_id) / ".tmp_latest.json"
            with open(tmp_latest, "w", encoding="utf-8") as f:
                json.dump({
                    "project_id": project_id,
                    "latest_session_id": session_id,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
            shutil.move(tmp_latest, latest_file)

            # Enforce snapshot retention per project
            cls.cleanup_old_snapshots(project_id, max_snapshots=10)

            return True, "All crawl artifacts saved and validated successfully."
        except Exception as e:
            logger.error(f"Failed to save crawl storage artifacts for project {project_id} session {session_id}: {e}")
            return False, f"Storage Exception: {str(e)}"

    @classmethod
    def validate_crawl_artifacts(cls, project_id: int, session_id: int) -> Tuple[bool, str]:
        try:
            session_dir = cls.get_project_storage_dir(project_id, session_id)
            for artifact_name in cls.REQUIRED_ARTIFACTS:
                file_path = session_dir / artifact_name
                if not file_path.exists():
                    return False, f"Missing required artifact '{artifact_name}'"
                if file_path.stat().st_size == 0:
                    return False, f"Artifact '{artifact_name}' is empty (0 bytes)"
                with open(file_path, "r", encoding="utf-8") as f:
                    json.load(f)
            return True, "VALID"
        except Exception as e:
            return False, f"Artifact validation error: {str(e)}"

    @classmethod
    def load_latest_artifact(cls, project_id: int, artifact_name: str) -> Optional[Any]:
        try:
            proj_dir = cls.get_project_storage_dir(project_id)
            latest_file = proj_dir / "latest.json"
            if not latest_file.exists():
                return None
            with open(latest_file, "r", encoding="utf-8") as f:
                latest_meta = json.load(f)
            
            session_id = latest_meta.get("latest_session_id")
            if not session_id:
                return None

            artifact_path = proj_dir / "crawls" / str(session_id) / artifact_name
            if not artifact_path.exists():
                return None

            with open(artifact_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load artifact '{artifact_name}' for project {project_id}: {e}")
            return None

    @classmethod
    def cleanup_old_snapshots(cls, project_id: int, max_snapshots: int = 10):
        try:
            crawls_dir = cls.get_project_storage_dir(project_id) / "crawls"
            if not crawls_dir.exists():
                return
            
            session_dirs = [d for d in crawls_dir.iterdir() if d.is_dir() and d.name.isdigit()]
            session_dirs.sort(key=lambda d: int(d.name), reverse=True)

            if len(session_dirs) > max_snapshots:
                for old_dir in session_dirs[max_snapshots:]:
                    logger.info(f"Cleaning up old crawl snapshot for project {project_id}: {old_dir}")
                    shutil.rmtree(old_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Error during snapshot cleanup for project {project_id}: {e}")
