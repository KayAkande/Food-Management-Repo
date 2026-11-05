import unittest,tempfile,os,sys,json,subprocess,time,urllib.request,urllib.error,http.cookiejar
class AppTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); cls.proc=subprocess.Popen([sys.executable,'server.py'],env={**os.environ,'PORT':'3011','KITCHEN_DB':cls.tmp.name+'/test.db'})
  for _ in range(40):
   try: urllib.request.urlopen('http://localhost:3011/'); break
   except OSError: time.sleep(.1)
 @classmethod
 def tearDownClass(cls): cls.proc.terminate();cls.proc.wait();cls.tmp.cleanup()
 def client(self): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(self,c,path,data=None):
  r=urllib.request.Request('http://localhost:3011/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
  try:
   with c.open(r) as x:return x.status,json.load(x)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_full_workflow(self):
  c=self.client(); other=self.client()
  self.assertEqual(self.call(c,'state')[0],401)
  self.assertEqual(self.call(c,'register',{'email':'one@example.com','password':'verylongpassword'})[0],200)
  self.assertEqual(self.call(c,'state')[1]['batches'],[])
  add={'key':'add-one','name':'Bananas','quantity':6,'unit':'pieces','location':'Pantry','acquired_at':'2026-11-05'}
  self.assertEqual(self.call(c,'batches',add)[0],200);self.call(c,'batches',add)
  batches=self.call(c,'state')[1]['batches']; self.assertEqual(len(batches),1);b=batches[0]
  use={'key':'use-one','id':b['id'],'version':1,'action':'CONSUME','amount':1}
  self.call(c,'event',use);self.call(c,'event',use)
  s=self.call(c,'state')[1];self.assertEqual(s['batches'][0]['quantity'],5);self.assertEqual(len(s['events']),2)
  self.assertEqual(self.call(c,'event',{**use,'key':'stale'})[0],409)
  self.assertEqual(self.call(c,'event',{**use,'key':'negative','version':2,'amount':9})[0],422)
  self.call(c,'event',{'key':'undo','id':b['id'],'version':2,'action':'UNDO'})
  self.assertEqual(self.call(c,'state')[1]['batches'][0]['quantity'],6)
  self.call(c,'batches',{**add,'key':'next-week','quantity':3});self.assertEqual(len(self.call(c,'state')[1]['batches']),2)
  self.call(c,'event',{'key':'freeze','id':b['id'],'version':3,'action':'FREEZE'})
  self.assertEqual(next(x for x in self.call(c,'state')[1]['batches'] if x['id']==b['id'])['state'],'frozen')
  self.call(c,'shopping',{'key':'shop','name':'Eggs','amount':'12 pieces'})
  shop=self.call(c,'state')[1]['shopping'][0]
  self.call(c,'shopping',{'key':'purchase','id':shop['id'],'purchased':True})
  self.assertEqual(len(self.call(c,'state')[1]['batches']),2)
  self.call(other,'register',{'email':'two@example.com','password':'verylongpassword'})
  self.assertEqual(self.call(other,'state')[1]['batches'],[])
  self.assertEqual(self.call(other,'event',{'key':'attack','id':b['id'],'version':4,'action':'CONSUME','amount':1})[0],422)
  self.call(c,'delete',{'key':'delete'});self.assertEqual(self.call(c,'state')[1]['batches'],[])
if __name__=='__main__': unittest.main()
