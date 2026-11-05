CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),name TEXT,quantity REAL CHECK(quantity>=0),unit TEXT,location TEXT,acquired_at TEXT,source TEXT,condition TEXT,printed_date TEXT,date_type TEXT,notes TEXT,state TEXT,created_at TEXT,updated_at TEXT,version INTEGER);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),batch_id TEXT REFERENCES batches(id),action TEXT,delta REAL,occurred_at TEXT,previous_state TEXT,key TEXT,source TEXT);
CREATE TABLE IF NOT EXISTS shopping(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),name TEXT,amount TEXT,purchased INTEGER);
CREATE TABLE IF NOT EXISTS requests(user_id TEXT REFERENCES users(id),key TEXT,response TEXT,PRIMARY KEY(user_id,key));
