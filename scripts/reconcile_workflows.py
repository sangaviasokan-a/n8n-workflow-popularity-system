"""Merge duplicate workflow rows created by older matcher versions.

Run after upgrading the application:
    python scripts/reconcile_workflows.py

The script preserves every Source and Metric row. It only moves sources from
an obsolete duplicate workflow to the selected canonical workflow, recalculates
its summary, and then deletes the now-empty duplicate workflow.
"""
from __future__ import annotations

from sqlalchemy import select

from app.database.database import SessionLocal, create_tables
from app.models import Workflow
from app.processors.workflow_matcher import find_best_workflow_match
from app.database.repository import _calculate_workflow_summary


def main() -> None:
    create_tables()
    db = SessionLocal()
    try:
        workflows = db.scalars(select(Workflow).order_by(Workflow.id.asc())).all()
        merged = 0
        for workflow in list(workflows):
            if db.get(Workflow, workflow.id) is None:
                continue
            candidates = [w for w in workflows if w.id != workflow.id and db.get(Workflow, w.id) is not None]
            canonical, score = find_best_workflow_match(candidates, workflow.workflow_key)
            if canonical is None or score < 0.80:
                continue
            # Keep the oldest workflow as canonical.
            if canonical.id > workflow.id:
                continue
            for source in list(workflow.sources):
                source.workflow_id = canonical.id
            if not canonical.description and workflow.description:
                canonical.description = workflow.description
            db.flush()
            _calculate_workflow_summary(db, canonical)
            db.delete(workflow)
            merged += 1
            print(f"Merged workflow {workflow.id} -> {canonical.id} ({score:.2f})")
        db.commit()
        print(f"Reconciliation complete. Merged {merged} duplicate workflow(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
