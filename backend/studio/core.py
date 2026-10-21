"""Local-first durable state, validation and paths. SQLite is the source of truth."""
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

MODES = {'mock', 'real'}
KINDS = {'image', 'video', 'speech', 'music', 'ambience'}
TERMINAL = {'succeeded', 'failed', 'cancelled'}
STATES = {'waiting','running','cancel_requested','cancelled','succeeded','failed','unknown'}


def config():
    root = os.getenv('STUDIO_DATA_ROOT')
    if not root:
        raise RuntimeError('Set STUDIO_DATA_ROOT explicitly. Never fall back to the system drive.')
    path = Path(root).expanduser().resolve(strict=False)
    if not path.is_dir():
        raise RuntimeError(f'Configured data volume is missing: {path}')
    if not os.access(path, os.W_OK):
        raise RuntimeError('Configured data volume is not writable')
    mode = os.getenv('STUDIO_MODE', 'mock')
    if mode not in MODES:
        raise RuntimeError('STUDIO_MODE must be mock or real')
    for name, default in [('STUDIO_COMFY_URL','http://127.0.0.1:8188'),('STUDIO_WAN_URL','http://127.0.0.1:7866/mcp')]:
        u = urlparse(os.getenv(name, default))
        if u.scheme != 'http' or u.hostname not in {'127.0.0.1', 'localhost'} or u.username or u.password:
            raise RuntimeError(name+' must be a loopback http URL')
    return {'root':path,'mode':mode,'locale':os.getenv('STUDIO_LOCALE','fa'),
            'comfy':os.getenv('STUDIO_COMFY_URL','http://127.0.0.1:8188').rstrip('/'),
            'wan':os.getenv('STUDIO_WAN_URL','http://127.0.0.1:7866/mcp'),
            'reserve':int(os.getenv('STUDIO_RESERVE_GIB','0' if mode=='mock' else '60'))*1024**3,
            'ffmpeg':os.getenv('STUDIO_FFMPEG','ffmpeg'), 'ffprobe':os.getenv('STUDIO_FFPROBE','ffprobe')}


def secure_path(root:Path, candidate:Path) -> Path:
    """Reject traversal, Windows drive/UNC/device syntax, links escaping allowed root."""
    value = str(candidate)
    if value.startswith(('\\\\','//','\\?\\')) or '\\' in value or (len(value)>1 and value[1]==':') and os.name!='nt':
        raise ValueError('A local managed asset path is required')
    resolved = candidate.resolve(strict=False)
    base = root.resolve(strict=True)
    if os.path.commonpath([os.path.normcase(str(base)),os.path.normcase(str(resolved))]) != os.path.normcase(str(base)):
        raise ValueError('Asset path escapes its approved root')
    return resolved


def ensure_space(root:Path, required:int, reserve:int):
    if required < 0 or shutil.disk_usage(root).free - reserve < required:
        raise HTTPException(507, detail='Not enough storage above configured reserve. Adjust the data volume or reserve.')


def canonical_json(data): return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',',':'))

def uid(): return str(uuid.uuid4())

class Store:
    def __init__(self, root: Path):
        self.root = root
        for name in ['assets','staging','exports']:
            (root/name).mkdir(exist_ok=True)
        self.file = root/'studio.sqlite3'
        self.migrate()

    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.file, timeout=20, isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback(); raise
        finally: db.close()

    def migrate(self):
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
            INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,brief TEXT DEFAULT '',aspect TEXT DEFAULT '1:1',language TEXT DEFAULT 'fa',archived INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,kind TEXT NOT NULL,mode TEXT NOT NULL,engine TEXT NOT NULL,state TEXT NOT NULL,stage TEXT DEFAULT 'waiting',settings TEXT NOT NULL,payload_hash TEXT NOT NULL,request_id TEXT NOT NULL,external_id TEXT,context TEXT,progress REAL,detail TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,job_id TEXT,kind TEXT NOT NULL,origin TEXT NOT NULL,path TEXT,external_ref TEXT,meta TEXT DEFAULT '{}',created TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(project_id) REFERENCES projects(id));
            CREATE TABLE IF NOT EXISTS presets(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,settings TEXT NOT NULL,version INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,name TEXT NOT NULL,steps TEXT NOT NULL,state TEXT DEFAULT 'draft',created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS exports(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,state TEXT NOT NULL,spec TEXT NOT NULL,asset_id TEXT,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS admission(id INTEGER PRIMARY KEY CHECK(id=1),job_id TEXT);
            INSERT OR IGNORE INTO admission(id,job_id) VALUES(1,NULL);
            ''')

    def event(self, db, type_, obj):
        db.execute('INSERT INTO events(event) VALUES(?)',(canonical_json({'type':type_,'id':obj}),))

    def rows(self, sql, params=()):
        with self.tx() as db: return [dict(row) for row in db.execute(sql,params).fetchall()]

    def row(self, sql, params=()):
        rows=self.rows(sql,params)
        if not rows: raise HTTPException(404,'Not found')
        return rows[0]

    def update_job(self, job_id, state, stage=None, detail='', progress=None):
        with self.tx() as db:
            db.execute("UPDATE jobs SET state=?,stage=?,detail=?,progress=?,updated=CURRENT_TIMESTAMP WHERE id=?",
                (state,stage or state,detail,progress,job_id))
            self.event(db,'job',job_id)

    def admission(self):
        with self.tx() as db:
            row=db.execute('SELECT job_id FROM admission WHERE id=1').fetchone()
            return row['job_id']

    def acquire(self, job_id):
        with self.tx() as db:
            cur=db.execute('UPDATE admission SET job_id=? WHERE id=1 AND job_id IS NULL',(job_id,))
            if cur.rowcount: self.event(db,'admission',job_id)
            return bool(cur.rowcount)

    def release(self, job_id):
        with self.tx() as db:
            db.execute('UPDATE admission SET job_id=NULL WHERE id=1 AND job_id=?',(job_id,))
            self.event(db,'admission',job_id)

    def insert_asset(self, project_id, kind, origin, path=None, job_id=None, meta=None, external_ref=None):
        aid=uid()
        with self.tx() as db:
            db.execute('INSERT INTO assets(id,project_id,job_id,kind,origin,path,external_ref,meta) VALUES(?,?,?,?,?,?,?,?)',
                       (aid,project_id,job_id,kind,origin,str(path) if path else None,external_ref,canonical_json(meta or {})))
            self.event(db,'asset',aid)
        return aid

    def asset_path(self, asset):
        if not asset.get('path'): raise HTTPException(409,'External media reference must be materialized by its engine adapter')
        try: p=secure_path(self.root,Path(asset['path']))
        except ValueError: raise HTTPException(403,'Unauthorized media path')
        if not p.is_file(): raise HTTPException(404,'Referenced media is missing')
        return p
