from database import get_connection, get_admin_role, set_admin_role, log_admin_action

def ensure_employee(admin_id, full_name=None, position=None, status=None):
 c=get_connection(); r=c.execute("SELECT admin_id FROM employee_profiles WHERE admin_id=?",(admin_id,)).fetchone()
 if not r: c.execute("INSERT INTO employee_profiles(admin_id,full_name,position,status,work_started_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",(admin_id,full_name,position or 'moderator',status or 'trainee'))
 else: c.execute("UPDATE employee_profiles SET full_name=COALESCE(?,full_name),position=COALESCE(?,position),status=COALESCE(?,status),updated_at=CURRENT_TIMESTAMP WHERE admin_id=?",(full_name,position,status,admin_id))
 c.commit(); c.close()
def employees():
 c=get_connection(); r=c.execute("SELECT p.*,r.role FROM employee_profiles p LEFT JOIN admin_roles r ON r.user_id=p.admin_id ORDER BY p.admin_id").fetchall(); c.close(); return r
def employee(admin_id):
 c=get_connection(); r=c.execute("SELECT p.*,r.role FROM employee_profiles p LEFT JOIN admin_roles r ON r.user_id=p.admin_id WHERE p.admin_id=?",(admin_id,)).fetchone(); c.close(); return r
def permissions(admin_id):
 c=get_connection(); r=c.execute("SELECT permission,enabled FROM employee_permissions WHERE admin_id=? ORDER BY permission",(admin_id,)).fetchall(); c.close(); return r
def role_history(admin_id):
 c=get_connection(); r=c.execute("SELECT * FROM employee_role_history WHERE admin_id=? ORDER BY created_at DESC",(admin_id,)).fetchall(); c.close(); return r
def promotion_history(admin_id):
 c=get_connection(); r=c.execute("SELECT * FROM employee_promotion_history WHERE admin_id=? ORDER BY created_at DESC",(admin_id,)).fetchall(); c.close(); return r
def violations(admin_id=None):
 c=get_connection(); r=c.execute("SELECT * FROM employee_violations WHERE (? IS NULL OR admin_id=?) ORDER BY created_at DESC",(admin_id,admin_id)).fetchall(); c.close(); return r
def change_role(admin_id,role,changed_by,reason=''):
 old=get_admin_role(admin_id); set_admin_role(admin_id,role); c=get_connection(); c.execute("INSERT INTO employee_role_history(admin_id,old_role,new_role,changed_by,reason) VALUES(?,?,?,?,?)",(admin_id,old,role,changed_by,reason)); c.commit(); c.close(); log_admin_action(changed_by,'employee_role_change',user_id=admin_id,details=f'{old}->{role}:{reason}')
def set_status(admin_id,status,changed_by,reason=''):
 if status not in {'trainee','employee','senior','leader','fired'}: raise ValueError('Недопустимый статус')
 old=employee(admin_id); old_status=old['status'] if old else None; ensure_employee(admin_id,status=status); c=get_connection(); c.execute("UPDATE employee_profiles SET status=?,fired_at=CASE WHEN ?='fired' THEN CURRENT_TIMESTAMP ELSE NULL END,updated_at=CURRENT_TIMESTAMP WHERE admin_id=?",(status,status,admin_id)); c.execute("INSERT INTO employee_promotion_history(admin_id,old_status,new_status,changed_by,reason) VALUES(?,?,?,?,?)",(admin_id,old_status,status,changed_by,reason)); c.commit(); c.close(); log_admin_action(changed_by,'employee_status_change',user_id=admin_id,details=f'{old_status}->{status}:{reason}')
def set_permission(admin_id,permission,enabled,changed_by):
 c=get_connection()
 if enabled:
  required = c.execute(
   "SELECT id,title FROM lms_courses WHERE required_for_permission=? AND active=true ORDER BY id LIMIT 1",
   (permission,),
  ).fetchone()
  if required:
   passed = c.execute(
    """
    SELECT 1 FROM lms_assignments
    WHERE admin_id=? AND course_id=? AND status='completed'
    LIMIT 1
    """,
    (admin_id, required["id"]),
   ).fetchone()
   if not passed:
    c.close()
    raise PermissionError(f"Сначала нужно завершить обязательный курс: {required['title']}")
 c.execute("INSERT INTO employee_permissions(admin_id,permission,enabled,updated_by,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(admin_id,permission) DO UPDATE SET enabled=EXCLUDED.enabled,updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP",(admin_id,permission,bool(enabled),changed_by))
 c.commit(); c.close()
 log_admin_action(changed_by,'employee_permission_change',user_id=admin_id,details=f'{permission}={enabled}')
def courses(position=None):
 c=get_connection(); r=c.execute("SELECT * FROM lms_courses WHERE active=true AND (? IS NULL OR position IS NULL OR position=?) ORDER BY id",(position,position)).fetchall(); c.close(); return r
def assignments(admin_id=None):
 c=get_connection(); r=c.execute("SELECT a.*,c.title FROM lms_assignments a JOIN lms_courses c ON c.id=a.course_id WHERE (? IS NULL OR a.admin_id=?) ORDER BY a.id",(admin_id,admin_id)).fetchall(); c.close(); return r
def assign_course(admin_id,course_id,due_at=None):
 c=get_connection(); c.execute("INSERT INTO lms_assignments(admin_id,course_id,due_at) VALUES(?,?,?) ON CONFLICT DO NOTHING",(admin_id,course_id,due_at)); c.commit(); c.close()
def update_assignment(assignment_id,status,progress,score=None):
 c=get_connection(); c.execute("UPDATE lms_assignments SET status=?,progress=?,completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END WHERE id=?",(status,int(progress),status,assignment_id));
 if score is not None: c.execute("INSERT INTO lms_attempts(assignment_id,score,passed) VALUES(?,?,?)",(assignment_id,float(score),float(score)>=70))
 c.commit(); c.close()
def kpi(days=30):
 c=get_connection(); r=c.execute("SELECT admin_id,SUM(moderated) moderated,SUM(published) published,SUM(errors) errors,SUM(dangerous) dangerous,SUM(support_responses) support_responses,SUM(response_seconds) response_seconds,SUM(moderation_seconds) moderation_seconds,SUM(post_corrections) post_corrections FROM moderator_kpi_daily WHERE day >= (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - (?::int) GROUP BY admin_id ORDER BY published DESC",(days,)).fetchall(); c.close(); return r
def leaderboard(days=30):
 out=[]
 for r in kpi(days):
  m=float(r['moderated'] or 0); p=float(r['published'] or 0); e=float(r['errors'] or 0); c=float(r['post_corrections'] or 0); ms=float(r['moderation_seconds'] or 0)
  quality=max(0,100-e/max(m,1)*100-c/max(p,1)*50); speed=100 if not m else max(0,100-min(100,ms/max(m,1)/600*100)); score=round(quality*.65+speed*.25+min(100,p)*.10,2); out.append({**dict(r),'score':score})
 return out
