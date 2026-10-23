"""Server-only Supabase REST adapter. No Supabase secret reaches the browser."""
import base64,json,threading
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import cv2,numpy as np
from matcher import Sample,features

class CloudDatabase:
    def __init__(self,url,key):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or not key:
            raise RuntimeError('Cần SUPABASE_URL HTTPS và SUPABASE_SERVICE_KEY trên máy chủ.')
        self.url=url.rstrip('/')+'/rest/v1';self.key=key
        self.lock=threading.RLock();self.cache={}
    def request(self,table,method='GET',body=None,params=None):
        suffix='?'+urlencode(params) if params else ''
        headers={'apikey':self.key,'Content-Type':'application/json','Prefer':'return=representation'}
        if method=='POST':headers['Prefer']='return=minimal'
        # Supports both Supabase secret API keys and the legacy JWT service_role.
        if self.key.count('.')==2:headers['Authorization']='Bearer '+self.key
        req=Request(self.url+'/'+table+suffix,method=method,headers=headers,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None)
        try:
            with urlopen(req,timeout=20) as response:
                raw=response.read();return json.loads(raw) if raw else []
        except (HTTPError,URLError,TimeoutError) as exc:
            # Never include API response bodies or secret headers in user-facing errors.
            raise RuntimeError('Không truy cập được cơ sở dữ liệu trực tuyến. Kiểm tra bảng dữ liệu và cấu hình máy chủ.') from None
    def rows(self):
        records=self.request('tem_products',params={'select':'*','order':'created_at.desc,id.asc','limit':'100'})
        return [{'id':r['id'],'data':json.dumps(r['data'],ensure_ascii=False),'image':base64.b64decode(r['image_base64']),'quality':json.dumps(r['quality']),'created_at':r['created_at']} for r in records]
    def summary_rows(self):
        records=self.request('tem_products',params={'select':'id,data,quality,created_at','order':'created_at.desc,id.asc','limit':'100'})
        return [{'id':r['id'],'data':json.dumps(r['data'],ensure_ascii=False),'quality':json.dumps(r['quality']),'created_at':r['created_at']} for r in records]
    def product(self,row):return {'id':row['id'],**json.loads(row['data']),'created_at':row['created_at'],'quality':json.loads(row['quality'])}
    def add(self,product_id,info,image,quality):
        return self.request('tem_products','POST',{'id':product_id,'data':info,'image_base64':base64.b64encode(image).decode(),'quality':quality})
    def update(self,product_id,info):return len(self.request('tem_products','PATCH',{'data':info},params={'id':'eq.'+product_id}))
    def delete(self,product_id):return len(self.request('tem_products','DELETE',params={'id':'eq.'+product_id}))
    def log_scan(self,status,product_id,score):
        self.request('tem_scans','POST',{'status':status,'product_id':product_id,'score':score})
    def references(self):
        output=[]
        with self.lock:
            rows=self.summary_rows();live={r['id'] for r in rows}
            self.cache={key:value for key,value in self.cache.items() if key in live}
            missing=[row['id'] for row in rows if row['id'] not in self.cache]
            images={}
            if missing:
                records=self.request('tem_products',params={'select':'id,image_base64','id':'in.('+','.join(missing)+')','limit':'100'})
                images={record['id']:base64.b64decode(record['image_base64']) for record in records}
            for row in rows:
                if row['id'] not in self.cache:
                    if row['id'] not in images:continue
                    image=cv2.imdecode(np.frombuffer(images[row['id']],np.uint8),cv2.IMREAD_COLOR)
                    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)[45:403,64:576]
                    pts,desc=features(gray)
                    self.cache[row['id']]=Sample(image,gray,pts,desc,json.loads(row['quality']),[])
                output.append((row['id'],self.cache[row['id']]))
        return output
    def export(self):
        rows=self.request('tem_products',params={'select':'*','limit':'100'})
        return 'tem_products.json',json.dumps({'format':'tem-van-giay-v1','products':rows},ensure_ascii=False,indent=2).encode()
