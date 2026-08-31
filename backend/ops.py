"""Operational controls: workload, SLA, prompts, incidents, shadow mode and policies."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx

from database import get_connection


def _rows(rows):
    return [dict(r) for r in rows]


# --------------------------- Moderator workload ---------------------------

def workload(admin_id: int | None = None):
    con = get_connection()
    if admin_id is None:
        rows = con.execute("""
            SELECT w.*, p.full_name, p.position, p.status
            FROM moderator_workload w
            LEFT JOIN employee_profiles p ON p.admin_id=w.admin_id
            ORDER BY w.active_tasks ASC, w.last_assigned_at NULLS FIRST, w.admin_id
        """).fetchall()
    else:
        rows = con.execute("SELECT * FROM moderator_workload WHERE admin_id=?", (admin_id,)).fetchall()
    con.close()
    return rows


def _ensure_workload_rows(con):
    ids = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    for admin_id in ids:
        con.execute("""
            INSERT INTO moderator_workload(admin_id,max_tasks,weight,enabled)
            VALUES(?,10,1,true) ON CONFLICT(admin_id) DO NOTHING
        """, (admin_id,))


def choose_moderator() -> int | None:
    con = get_connection()
    try:
        _ensure_workload_rows(con)
        rows = con.execute("""
            SELECT w.admin_id
            FROM moderator_workload w
            LEFT JOIN employee_profiles p ON p.admin_id=w.admin_id
            WHERE w.enabled=true AND w.active_tasks < w.max_tasks
              AND COALESCE(p.status,'employee') <> 'fired'
            ORDER BY (w.active_tasks::float / GREATEST(w.max_tasks,1)) / GREATEST(w.weight,0.1),
                     w.last_assigned_at NULLS FIRST, w.admin_id
            LIMIT 1
        """).fetchall()
        return int(rows[0][0]) if rows else None
    finally:
        con.close()


def assign_workload(dialog_id: int) -> int | None:
    con = get_connection()
    try:
        _ensure_workload_rows(con)
        row = con.execute("""
            SELECT w.admin_id
            FROM moderator_workload w
            LEFT JOIN employee_profiles p ON p.admin_id=w.admin_id
            WHERE w.enabled=true AND w.active_tasks < w.max_tasks
              AND COALESCE(p.status,'employee') <> 'fired'
            ORDER BY (w.active_tasks::float / GREATEST(w.max_tasks,1)) / GREATEST(w.weight,0.1),
                     w.last_assigned_at NULLS FIRST, w.admin_id
            LIMIT 1
        """).fetchone()
        if not row:
            return None
        admin_id = int(row[0])
        cur = con.execute("""
            UPDATE support_dialogs
            SET assigned_admin_id=?, support_status='in_progress', updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='open' AND assigned_admin_id IS NULL
        """, (admin_id, dialog_id))
        if cur.rowcount:
            con.execute("UPDATE moderator_workload SET active_tasks=active_tasks+1,last_assigned_at=CURRENT_TIMESTAMP WHERE admin_id=?", (admin_id,))
        con.commit()
        return admin_id if cur.rowcount else None
    finally:
        con.close()


def release_workload(admin_id: int):
    con = get_connection()
    con.execute("UPDATE moderator_workload SET active_tasks=GREATEST(active_tasks-1,0) WHERE admin_id=?", (admin_id,))
    con.commit(); con.close()


# --------------------------- SLA dashboard ---------------------------

def sla_dashboard():
    con = get_connection()
    try:
        summary = con.execute("""
            SELECT
              COUNT(*) FILTER (WHERE d.status='open') AS open_dialogs,
              COUNT(*) FILTER (WHERE d.status='open' AND d.support_status='new') AS waiting,
              COUNT(*) FILTER (WHERE d.status='open' AND s.first_response_due_at < CURRENT_TIMESTAMP AND d.support_status='new') AS breached,
              COALESCE(AVG(EXTRACT(EPOCH FROM (d.first_response_at-d.created_at))) FILTER (WHERE d.first_response_at IS NOT NULL),0) AS avg_first_response_seconds,
              COALESCE(AVG(EXTRACT(EPOCH FROM (d.resolved_at-d.created_at))) FILTER (WHERE d.resolved_at IS NOT NULL),0) AS avg_resolution_seconds
            FROM support_dialogs d LEFT JOIN support_sla s ON s.dialog_id=d.id
        """).fetchone()
        by_priority = con.execute("""
            SELECT COALESCE(s.priority,'normal') AS priority,
                   COUNT(*) FILTER (WHERE d.status='open') AS open,
                   COUNT(*) FILTER (WHERE d.status='open' AND s.first_response_due_at < CURRENT_TIMESTAMP AND d.support_status='new') AS breached
            FROM support_dialogs d LEFT JOIN support_sla s ON s.dialog_id=d.id
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        return {"summary": dict(summary) if summary else {}, "by_priority": _rows(by_priority)}
    finally:
        con.close()


# --------------------------- Prompt version control ---------------------------

def prompts(name: str | None = None):
    con = get_connection()
    if name:
        rows = con.execute("SELECT * FROM prompt_versions WHERE name=? ORDER BY version DESC", (name,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM prompt_versions ORDER BY name,version DESC").fetchall()
    con.close(); return rows


def active_prompt(name: str, default: str) -> str:
    con = get_connection()
    row = con.execute("SELECT prompt_text FROM prompt_versions WHERE name=? AND active=true ORDER BY version DESC LIMIT 1", (name,)).fetchone()
    con.close()
    return str(row[0]) if row and row[0] else default


def save_prompt(name: str, prompt_text: str, created_by: int, activate: bool = True):
    con = get_connection()
    version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM prompt_versions WHERE name=?", (name,)).fetchone()[0]
    if activate:
        con.execute("UPDATE prompt_versions SET active=false WHERE name=?", (name,))
    con.execute("INSERT INTO prompt_versions(name,version,prompt_text,active,created_by) VALUES(?,?,?,?,?)", (name,int(version),prompt_text,bool(activate),created_by))
    con.commit(); row=con.execute("SELECT * FROM prompt_versions WHERE name=? AND version=?",(name,int(version))).fetchone(); con.close(); return row


def activate_prompt(prompt_id: int, admin_id: int):
    con=get_connection(); row=con.execute("SELECT name,version FROM prompt_versions WHERE id=?",(prompt_id,)).fetchone()
    if not row: con.close(); raise ValueError("Prompt not found")
    con.execute("UPDATE prompt_versions SET active=false WHERE name=?",(row['name'],))
    con.execute("UPDATE prompt_versions SET active=true WHERE id=?",(prompt_id,))
    con.commit(); con.close()


# --------------------------- Policies ---------------------------

def policies():
    con=get_connection(); rows=con.execute("SELECT * FROM policy_rules ORDER BY key").fetchall(); con.close(); return rows


def set_policy(key: str, title: str, config: dict[str,Any], enabled: bool, admin_id: int):
    con=get_connection()
    con.execute("""
        INSERT INTO policy_rules(key,title,config_json,enabled,updated_by,updated_at)
        VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET title=EXCLUDED.title,config_json=EXCLUDED.config_json,
          enabled=EXCLUDED.enabled,updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP
    """, (key,title,json.dumps(config,ensure_ascii=False),bool(enabled),admin_id))
    con.commit(); con.close()


def policy_config(key: str, default: dict[str,Any] | None=None):
    con=get_connection(); row=con.execute("SELECT config_json,enabled FROM policy_rules WHERE key=?",(key,)).fetchone(); con.close()
    if not row: return default or {}
    try: cfg=json.loads(row['config_json'] or '{}')
    except Exception: cfg=default or {}
    cfg['_enabled']=bool(row['enabled'])
    return cfg


# --------------------------- AI shadow mode ---------------------------

def log_shadow_run(story_id, stage, model, result, latency_ms=0, error=None):
    con=get_connection()
    con.execute("INSERT INTO ai_shadow_runs(story_id,stage,model,result,latency_ms,error,created_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (story_id,stage,model,result,latency_ms,error))
    con.commit(); con.close()


def shadow_runs(limit=100):
    con=get_connection(); rows=con.execute("SELECT * FROM ai_shadow_runs ORDER BY created_at DESC LIMIT ?",(int(limit),)).fetchall(); con.close(); return rows


# --------------------------- Incident center / rollback ---------------------------

def create_incident(service: str, severity: str, title: str, details: str = "", deployment_id: str | None = None):
    con=get_connection()
    cur=con.execute("INSERT INTO incidents(service,severity,title,details,deployment_id,status) VALUES(?,?,?,?,?,'open') RETURNING id",(service,severity,title,details,deployment_id))
    incident_id=cur.fetchone()[0]; con.commit(); con.close(); return incident_id


def incidents(limit=100, status=None):
    con=get_connection()
    if status:
        rows=con.execute("SELECT * FROM incidents WHERE status=? ORDER BY created_at DESC LIMIT ?",(status,int(limit))).fetchall()
    else:
        rows=con.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?",(int(limit),)).fetchall()
    con.close(); return rows


def resolve_incident(incident_id:int, admin_id:int, note=""):
    con=get_connection(); con.execute("UPDATE incidents SET status='resolved',resolved_at=CURRENT_TIMESTAMP,resolution_note=? WHERE id=?",(note,incident_id)); con.commit(); con.close()


async def railway_rollback(target_deployment_id: str):
    token=os.getenv("RAILWAY_API_TOKEN","").strip() or os.getenv("RAILWAY_TOKEN","").strip()
    if not token: return {"ok":False,"error":"RAILWAY_API_TOKEN/RAILWAY_TOKEN не задан"}
    query="mutation deploymentRollback($id: String!) { deploymentRollback(id: $id) { id } }"
    async with httpx.AsyncClient(timeout=20) as client:
        r=await client.post("https://backboard.railway.com/graphql/v2",headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json={"query":query,"variables":{"id":target_deployment_id}})
        data=r.json()
    if data.get("errors"):
        return {"ok":False,"error":data["errors"]}
    return {"ok":True,"deployment":data.get("data",{}).get("deploymentRollback")}


def record_rollback(incident_id, service, target_deployment_id, status, details=""):
    con=get_connection(); con.execute("INSERT INTO rollback_actions(incident_id,service,target_deployment_id,status,details) VALUES(?,?,?,?,?)",(incident_id,service,target_deployment_id,status,details)); con.commit(); con.close()


async def automatic_rollback_if_enabled(service: str, reason: str, severity: str = "critical"):
    if os.getenv("AUTO_ROLLBACK_ENABLED", "0").strip() != "1":
        return {"ok": False, "skipped": True, "reason": "disabled"}
    if severity.lower() != "critical":
        return {"ok": False, "skipped": True, "reason": "severity"}
    target = os.getenv("RAILWAY_ROLLBACK_DEPLOYMENT_ID", "").strip()
    if not target:
        return {"ok": False, "skipped": True, "reason": "RAILWAY_ROLLBACK_DEPLOYMENT_ID not set"}
    incident_id = create_incident(service, severity, "Automatic rollback", reason, target)
    result = await railway_rollback(target)
    record_rollback(incident_id, service, target, "success" if result.get("ok") else "failed", json.dumps(result, ensure_ascii=False))
    return {"incident_id": incident_id, **result}


# --------------------------- Seed ---------------------------

def ensure_ops_defaults():
    con=get_connection()
    _ensure_workload_rows(con)
    defaults=[
        ("ai_shadow_mode","AI Shadow Mode",{"enabled":False,"model":os.getenv("AI_SHADOW_MODEL","")},False),
        ("auto_rollback","Automatic rollback",{"enabled":False,"severity":"critical"},False),
        ("safety_policy","Safety policy",{"manual_review_risk":0.75,"reject_risk":0.95,"require_second_opinion":True},True),
        ("sla_policy","SLA policy",{"critical_minutes":15,"high_minutes":30,"normal_minutes":120,"low_minutes":480},True),
    ]
    for key,title,cfg,enabled in defaults:
        con.execute("INSERT INTO policy_rules(key,title,config_json,enabled) VALUES(?,?,?,?) ON CONFLICT(key) DO NOTHING",(key,title,json.dumps(cfg,ensure_ascii=False),enabled))
    con.commit(); con.close()
