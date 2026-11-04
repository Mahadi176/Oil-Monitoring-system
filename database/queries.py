from __future__ import annotations
import hashlib, hmac, os, re
from datetime import datetime, timezone
import pandas as pd
from .db_connection import connection


def _hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', pin.encode(), bytes.fromhex(salt), 240_000).hex()

def create_user(username: str, pin: str):
    username = username.strip()
    if not username or len(username) > 60: return False, 'Enter a username (1–60 characters).'
    if not re.fullmatch(r'\d{5}', pin or ''): return False, 'PIN must contain exactly five digits.'
    salt = os.urandom(16).hex()
    try:
        with connection() as c: c.execute('INSERT INTO users(username,password_hash,salt) VALUES(?,?,?)',(username,_hash(pin,salt),salt))
        return True, 'Account created. You can now sign in.'
    except Exception as e:
        if 'UNIQUE' in str(e): return False, 'That username already exists.'
        raise

def authenticate(username: str, pin: str):
    with connection() as c:
        row=c.execute('SELECT * FROM users WHERE username=?',(username.strip(),)).fetchone()
        if not row: return None
        if row['locked_until']:
            try:
                if datetime.fromisoformat(row['locked_until']).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc): return None
            except ValueError: pass
        if not re.fullmatch(r'\d{5}', pin or ''): return None
        if hmac.compare_digest(row['password_hash'],_hash(pin,row['salt'])):
            c.execute('UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?',(row['id'],)); return row['id']
        attempts=row['failed_attempts']+1
        c.execute('UPDATE users SET failed_attempts=?, locked_until=CASE WHEN ?>=5 THEN datetime(\'now\',\'+5 minutes\') ELSE locked_until END WHERE id=?',(attempts,attempts,row['id']))
        return None

def username_for(user_id):
    with connection() as c:
        r=c.execute('SELECT username FROM users WHERE id=?',(int(user_id),)).fetchone()
    if not r: raise ValueError('User no longer exists')
    return r['username']

def organisations(user_id):
    with connection() as c: rows=c.execute('SELECT id,name FROM organisations WHERE user_id=? ORDER BY name',(int(user_id),)).fetchall()
    return [dict(r) for r in rows]

def import_records(user_id: int, company: str, df: pd.DataFrame, source_file: str, replace_existing=False):
    imported=skipped=0
    with connection() as c:
        c.execute('INSERT OR IGNORE INTO organisations(user_id,name) VALUES(?,?)',(int(user_id),company.strip()))
        org=c.execute('SELECT id FROM organisations WHERE user_id=? AND name=?',(int(user_id),company.strip())).fetchone()['id']
        for r in df.to_dict('records'):
            vals=(org,str(pd.Timestamp(r['Date']).date()),float(r['TotalCost']),float(r['Litres']),float(r['Oil Rate']),float(r['Oil Cost']),float(r['Oil Cost %']),float(r['Employee Cost']),float(r['Transportation Cost']),float(r['Other Costs']),
                  _nullable(r.get('Production Output')),_nullable(r.get('Operating Hours')),_nullable(r.get('Number of Employees')),_nullable(r.get('Number of Vehicles')),_nullable(r.get('Distance Travelled')),_nullable(r.get('Electricity Consumption')),source_file)
            exists=c.execute('SELECT id FROM daily_records WHERE organisation_id=? AND record_date=?',(org,vals[1])).fetchone()
            if exists and not replace_existing: skipped+=1; continue
            if exists:
                c.execute('''UPDATE daily_records SET total_cost=?,litres=?,oil_rate=?,oil_cost=?,oil_cost_pct=?,employee_cost=?,transportation_cost=?,other_costs=?,production_output=?,operating_hours=?,number_of_employees=?,number_of_vehicles=?,distance_travelled=?,electricity_consumption=?,source_file=?,imported_at=CURRENT_TIMESTAMP WHERE organisation_id=? AND record_date=?''',vals[2:]+(org,vals[1]))
                imported+=1
            else:
                c.execute('''INSERT INTO daily_records(organisation_id,record_date,total_cost,litres,oil_rate,oil_cost,oil_cost_pct,employee_cost,transportation_cost,other_costs,production_output,operating_hours,number_of_employees,number_of_vehicles,distance_travelled,electricity_consumption,source_file) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',vals)
                imported+=1
        c.execute('INSERT INTO import_history(user_id,file_name,organisation_name,imported_count,skipped_count,status) VALUES(?,?,?,?,?,?)',(int(user_id),source_file,company,imported,skipped,'completed'))
    return {'imported':imported,'skipped':skipped}

def _nullable(v):
    if v is None or pd.isna(v) or str(v).strip()=='': return None
    return float(v)

def load_records(user_id: int):
    with connection() as c:
        rows=c.execute('''SELECT r.*,o.name AS Company FROM daily_records r JOIN organisations o ON o.id=r.organisation_id WHERE o.user_id=? ORDER BY r.record_date,o.name''',(int(user_id),)).fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def log_import_error(user_id, filename, company, errors):
    with connection() as c: c.execute('INSERT INTO import_history(user_id,file_name,organisation_name,error_count,status,details) VALUES(?,?,?,?,?,?)',(user_id,filename,company,len(errors),'validation_failed','; '.join(map(str,errors))[:3000]))

def import_history(user_id):
    with connection() as c: rows=c.execute('SELECT * FROM import_history WHERE user_id=? ORDER BY imported_at DESC LIMIT 30',(user_id,)).fetchall()
    return pd.DataFrame([dict(r) for r in rows])
