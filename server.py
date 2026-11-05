import os, json, sqlite3, uuid, hashlib, secrets, datetime, csv, io
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
DB=os.environ.get('KITCHEN_DB','data/kitchen.sqlite3')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def init():
 Path(DB).parent.mkdir(parents=True,exist_ok=True)
 with connect() as c: c.executescript(Path('migrations/001.sql').read_text())
def password(p,s): return hashlib.scrypt(p.encode(),salt=s.encode(),n=16384,r=8,p=1).hex()
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args): pass
 def respond(self,data,status=200,cookie=None):
  body=json.dumps(data).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
  if cookie: self.send_header('Set-Cookie',cookie)
  self.end_headers(); self.wfile.write(body)
 def do_GET(self):
  if self.path.startswith('/api/'): return self.api()
  self.path='/static/index.html' if self.path=='/' else self.path
  if not self.path.startswith('/static/') or '..' in self.path: return self.send_error(404)
  return super().do_GET()
 def do_POST(self): self.api()
 def api(self):
  try:
   with connect() as c:
    data={}
    if self.command=='POST':
     origin=self.headers.get('Origin')
     if origin and origin.split('://')[-1]!=self.headers.get('Host'): return self.respond({'error':'Invalid origin'},403)
     length=int(self.headers.get('Content-Length',0))
     if length>100000: return self.respond({'error':'Request too large'},413)
     data=json.loads(self.rfile.read(length) or '{}')
    path=self.path.split('?')[0]; cookies=SimpleCookie(self.headers.get('Cookie','')); token=cookies.get('session'); token=token.value if token else ''
    user=c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(token,now())).fetchone()
    if path in ['/api/register','/api/login'] and self.command=='POST':
     email=data.get('email','').strip().lower(); p=data.get('password','')
     if '@' not in email or len(p)<10: raise ValueError('Enter an email and a password of at least 10 characters.')
     u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
     if path.endswith('register'):
      if u: raise ValueError('Account already exists. Sign in instead.')
      salt=secrets.token_hex(16); uid=str(uuid.uuid4()); c.execute('INSERT INTO users VALUES (?,?,?,?)',(uid,email,salt,password(p,salt)))
     else:
      if not u or not secrets.compare_digest(u['hash'],password(p,u['salt'])): return self.respond({'error':'Email or password is incorrect'},401)
      uid=u['id']
     t=secrets.token_urlsafe(32); expires=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=7)).isoformat(); c.execute('INSERT INTO sessions VALUES (?,?,?)',(t,uid,expires))
     secure='; Secure' if os.environ.get('COOKIE_SECURE')=='1' else ''
     return self.respond({'email':email},cookie=f'session={t}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800{secure}')
    if not user: return self.respond({'error':'Please sign in'},401)
    uid=user['id']
    if path=='/api/logout':
     c.execute('DELETE FROM sessions WHERE token=?',(token,)); return self.respond({},cookie='session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
    if self.command=='GET':
     batches=[dict(x) for x in c.execute('SELECT * FROM batches WHERE user_id=? ORDER BY acquired_at,id',(uid,))]
     events=[dict(x) for x in c.execute('SELECT * FROM events WHERE user_id=? ORDER BY occurred_at DESC,rowid DESC',(uid,))]
     shopping=[dict(x) for x in c.execute('SELECT * FROM shopping WHERE user_id=? ORDER BY rowid DESC',(uid,))]
     return self.respond({'email':user['email'],'batches':batches,'events':events,'shopping':shopping,'exported_at':now()})
    key=data.get('key')
    if not key: raise ValueError('Missing request identifier')
    old=c.execute('SELECT response FROM requests WHERE user_id=? AND key=?',(uid,key)).fetchone()
    if old: return self.respond(json.loads(old[0]))
    c.execute('BEGIN IMMEDIATE')
    if path=='/api/batches':
     name=str(data.get('name','')).strip(); qty=float(data.get('quantity',0)); unit=data.get('unit','pieces'); loc=data.get('location','Fridge')
     if not name or len(name)>120 or not 0<qty<=1000000: raise ValueError('Enter a food name and a positive quantity.')
     if unit not in ['pieces','g','kg','mL','L','packs','portions','cans','bags']: raise ValueError('Invalid unit')
     if loc not in ['Fridge','Freezer','Pantry']: raise ValueError('Invalid location')
     acquired=data.get('acquired_at') or now()[:10]; datetime.date.fromisoformat(acquired)
     printed=data.get('printed_date','');
     if printed: datetime.date.fromisoformat(printed)
     bid=str(uuid.uuid4()); stamp=now()
     c.execute('INSERT INTO batches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,uid,name,qty,unit,loc,acquired,data.get('source','Other'),data.get('condition','unknown'),printed,data.get('date_type','best_before'),data.get('notes',''),'frozen' if loc=='Freezer' else 'whole',stamp,stamp,1))
     previous=dict(c.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()); previous['quantity']=0
     self.event(c,uid,bid,'ADD',qty,previous,key)
    elif path=='/api/event':
     b=c.execute('SELECT * FROM batches WHERE id=? AND user_id=?',(data.get('id'),uid)).fetchone()
     if not b: raise ValueError('Batch not found')
     if data.get('version')!=b['version']: return self.respond({'error':'This batch changed. Refresh and try again.'},409)
     action=data.get('action'); state=dict(b); qty=b['quantity']; loc=b['location']; physical=b['state']
     if action in ['CONSUME','ADJUST','DISCARD']:
      amount=float(data.get('amount',0))
      if not 0<amount<=1000000: raise ValueError('Enter a positive amount')
      qty+=amount if action=='ADJUST' else -amount
     elif action in ['FREEZE','THAW','TRANSFER']:
      loc='Freezer' if action=='FREEZE' else data.get('location','Fridge')
      if loc not in ['Freezer','Fridge','Pantry']: raise ValueError('Invalid location')
      physical='frozen' if loc=='Freezer' else 'thawed' if b['state']=='frozen' else b['state']
     elif action=='UNDO':
      e=c.execute("SELECT * FROM events WHERE batch_id=? ORDER BY rowid DESC LIMIT 1",(b['id'],)).fetchone()
      if not e or not e['previous_state'] or e['action']=='UNDO': raise ValueError('No eligible action to undo')
      previous=json.loads(e['previous_state']); qty=previous['quantity']; loc=previous['location']; physical=previous['state']
     else: raise ValueError('Unknown action')
     if not 0<=qty<=1000000: raise ValueError('Not enough stock, or quantity too large')
     c.execute('UPDATE batches SET quantity=?,location=?,state=?,updated_at=?,version=version+1 WHERE id=?',(qty,loc,physical,now(),b['id']))
     self.event(c,uid,b['id'],action,qty-b['quantity'],state,key)
    elif path=='/api/shopping':
     if data.get('id'):
      row=c.execute('SELECT * FROM shopping WHERE id=? AND user_id=?',(data['id'],uid)).fetchone()
      if not row: raise ValueError('Shopping item not found')
      if data.get('delete'): c.execute('DELETE FROM shopping WHERE id=? AND user_id=?',(data['id'],uid))
      else: c.execute('UPDATE shopping SET purchased=? WHERE id=? AND user_id=?',(int(bool(data.get('purchased'))),data['id'],uid))
     else:
      name=data.get('name','').strip()
      if not name: raise ValueError('Enter an item')
      c.execute('INSERT INTO shopping VALUES (?,?,?,?,?)',(str(uuid.uuid4()),uid,name,data.get('amount',''),0))
    elif path=='/api/delete':
     for table in ['requests','events','batches','shopping']: c.execute(f'DELETE FROM {table} WHERE user_id=?',(uid,))
    else: return self.respond({'error':'Not found'},404)
    result={'ok':True}; c.execute('INSERT INTO requests VALUES (?,?,?)',(uid,key,json.dumps(result))); c.commit(); return self.respond(result)
  except (ValueError,TypeError,KeyError) as e: self.respond({'error':str(e)},422)
  except Exception: self.respond({'error':'Unable to save. Please retry.'},500)
 def event(self,c,uid,bid,action,delta,previous,key):
  c.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),uid,bid,action,delta,now(),json.dumps(previous) if previous else None,key,'UI'))
if __name__=='__main__':
 init(); ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','3000'))),Handler).serve_forever()
