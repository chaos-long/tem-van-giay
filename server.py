import base64
from contextlib import contextmanager
import functools
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from urllib.parse import urlsplit
import zipfile

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from matcher import ImageProblem, Sample, decode_image, encode_image, prepare, decide, features, build_analysis

FIELDS=['product_name','product_code','description','material_source','collection_date','maker','revenue_use','evidence_note']

class Database:
    def __init__(self,folder):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'tem_van_giay.sqlite3'
        self.lock=threading.RLock();self.cache={}
        with self.connection() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS products(
                id TEXT PRIMARY KEY, data TEXT NOT NULL, image BLOB NOT NULL,
                quality TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE IF NOT EXISTS scans(
                id INTEGER PRIMARY KEY, status TEXT NOT NULL, product_id TEXT,
                score REAL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            ''')
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def rows(self):
        with self.connection() as db:return db.execute('SELECT * FROM products ORDER BY created_at DESC,id').fetchall()
    def summary_rows(self):
        with self.connection() as db:return db.execute('SELECT id,data,quality,created_at FROM products ORDER BY created_at DESC,id').fetchall()
    def product(self,row):
        return {'id':row['id'],**json.loads(row['data']),'created_at':row['created_at'],'quality':json.loads(row['quality'])}
    def add(self,product_id,info,image,quality):
        with self.connection() as conn:
            conn.execute('INSERT INTO products(id,data,image,quality) VALUES(?,?,?,?)',(product_id,json.dumps(info,ensure_ascii=False),image,json.dumps(quality)))
    def update(self,product_id,info):
        with self.connection() as conn:return conn.execute('UPDATE products SET data=? WHERE id=?',(json.dumps(info,ensure_ascii=False),product_id)).rowcount
    def delete(self,product_id):
        with self.connection() as conn:return conn.execute('DELETE FROM products WHERE id=?',(product_id,)).rowcount
    def log_scan(self,status,product_id,score):
        with self.connection() as conn:conn.execute('INSERT INTO scans(status,product_id,score) VALUES(?,?,?)',(status,product_id,score))
    def export(self):
        with self.connection() as source:
            memory=sqlite3.connect(':memory:');source.backup(memory)
            snapshot=memory.serialize();memory.close()
        return 'tem_van_giay.sqlite3',snapshot
    def references(self):
        output=[]
        with self.lock:
            rows=self.rows();live={row['id'] for row in rows}
            self.cache={key:value for key,value in self.cache.items() if key in live}
            for row in rows:
                if row['id'] not in self.cache:
                    image=cv2.imdecode(np.frombuffer(row['image'],np.uint8),cv2.IMREAD_COLOR)
                    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)[45:403,64:576]
                    pts,desc=features(gray)
                    self.cache[row['id']]=Sample(image,gray,pts,desc,json.loads(row['quality']),[])
                output.append((row['id'],self.cache[row['id']]))
        return output

def create_app(data_dir=None,admin_token=None):
    folder=Path(data_dir or os.environ.get('TEM_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'TemVanGiay'))
    folder.mkdir(parents=True,exist_ok=True)
    if os.environ.get('SUPABASE_URL'):
        from cloud_database import CloudDatabase
        if not (admin_token or os.environ.get('TEM_ADMIN_TOKEN')):
            raise RuntimeError('Đặt TEM_ADMIN_TOKEN trên máy chủ trước khi dùng cơ sở dữ liệu trực tuyến.')
        db=CloudDatabase(os.environ['SUPABASE_URL'],os.environ.get('SUPABASE_SERVICE_KEY',''))
    else:db=Database(folder)
    config_path=folder/'settings.json'
    if config_path.exists():
        config=json.loads(config_path.read_text(encoding='utf-8'))
    else:
        config={'admin_token':secrets.token_urlsafe(32),'threshold':.64,'margin':.08}
        config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    token=admin_token or os.environ.get('TEM_ADMIN_TOKEN') or config['admin_token']
    static=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'web'
    app=Flask(__name__,static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=23_000_000,JSON_SORT_KEYS=False)
    app.json.ensure_ascii=False
    app.db=db;app.admin_token=token;app.tem_config=config
    app.match_lock=threading.Lock()
    app.registration_progress={'phase':'idle','started':time.monotonic()}
    def registration_phase(phase):
        app.registration_progress={'phase':phase,'started':time.monotonic()}
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store' if request.path.startswith('/api/') else 'no-cache'
        origin=request.headers.get('Origin','')
        try:parsed=urlsplit(origin)
        except ValueError:parsed=urlsplit('')
        allowed={item.strip().rstrip('/') for item in os.environ.get('TEM_ALLOWED_ORIGINS','').split(',') if item.strip()}
        if origin and (origin in allowed or (parsed.scheme in ['http','https'] and parsed.hostname in ['localhost','127.0.0.1'])):
            response.headers['Access-Control-Allow-Origin']=origin
            response.headers['Vary']='Origin'
            response.headers['Access-Control-Allow-Headers']='Content-Type, Authorization'
            response.headers['Access-Control-Allow-Methods']='GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Private-Network']='true'
        return response
    @app.errorhandler(ImageProblem)
    def image_problem(exc):
        result={'status':'quality_error','message':str(exc)}
        if exc.analysis is not None:result['analysis']=exc.analysis
        return jsonify(result),422
    @app.errorhandler(413)
    def too_large(exc):return jsonify(status='error',message='Ảnh quá lớn. Chọn ảnh dưới 12 MB.'),413
    @app.errorhandler(400)
    def bad_request(exc):return jsonify(status='error',message='Dữ liệu gửi lên không hợp lệ.'),400
    @app.errorhandler(Exception)
    def unexpected(exc):
        if isinstance(exc,HTTPException):
            return jsonify(status='error',message='Không tìm thấy chức năng hoặc yêu cầu không hợp lệ.'),exc.code
        logging.exception('Request failed')
        return jsonify(status='error',message='Có lỗi xử lý. Hãy thử lại hoặc xem nhật ký máy chủ.'),500
    def admin(function):
        @functools.wraps(function)
        def wrapped(*args,**kwargs):
            provided=request.headers.get('Authorization','').removeprefix('Bearer ')
            if not provided or not secrets.compare_digest(provided,token):
                return jsonify(status='unauthorized',message='Cần khóa quản lý để thực hiện thao tác này.'),401
            return function(*args,**kwargs)
        return wrapped
    def body():
        data=request.get_json()
        if not isinstance(data,dict):raise ImageProblem('Dữ liệu gửi lên không hợp lệ.')
        return data
    @app.get('/')
    def index():return send_from_directory(static,'index.html')
    @app.get('/<path:filename>')
    def assets(filename):return send_from_directory(static,filename)
    @app.get('/api/health')
    def health():
        return jsonify(status='ok',version='0.4.2',product_count=len(db.summary_rows()),threshold=config['threshold'],margin=config['margin'],busy=app.match_lock.locked())
    @app.post('/api/admin/login')
    @admin
    def login():return jsonify(status='ok')
    @app.get('/api/admin/diagnostics')
    @admin
    def diagnostics():
        progress=app.registration_progress
        return jsonify(phase=progress['phase'],phase_seconds=round(time.monotonic()-progress['started']),busy=app.match_lock.locked())
    @app.get('/api/products')
    @admin
    def products():return jsonify(products=[db.product(row) for row in db.summary_rows()])
    @app.post('/api/inspect')
    def inspect():
        data=body();explain=data.get('explain') is True
        sample=prepare(decode_image(data.get('image')),data.get('corners'),explain=explain)
        result={'status':'ready','preview':encode_image(sample.image),'quality':sample.quality,'corners':sample.corners}
        if explain:result['analysis']=build_analysis(sample)
        return jsonify(result)
    @app.post('/api/products')
    @admin
    def register():
        registration_phase('reading_image')
        data=body();info=data.get('product')
        if not isinstance(info,dict):return jsonify(message='Thiếu thông tin sản phẩm.'),400
        clean={field:str(info.get(field,'')).strip()[:3000] for field in FIELDS}
        if not clean['product_name'] or not clean['product_code']:
            return jsonify(message='Nhập tên và mã sản phẩm.'),400
        registration_phase('waiting')
        with app.match_lock:
            registration_phase('checking_database')
            existing_rows=db.summary_rows()
            if len(existing_rows)>=100:return jsonify(message='Bản thử nghiệm hỗ trợ tối đa 100 tem. Sao lưu dữ liệu trước khi mở rộng.'),409
            registration_phase('processing_image')
            sample=prepare(decode_image(data.get('image')),data.get('corners'))
            registration_phase('checking_duplicates')
            duplicate=decide(sample,db.references())
            if duplicate['status'] in ['matched','ambiguous']:
                return jsonify(message='Ảnh tem này đã có hoặc quá gần với một mẫu đã đăng ký. Dùng một chiếc tem khác.'),409
            for row in existing_rows:
                if json.loads(row['data'])['product_code'].casefold()==clean['product_code'].casefold():
                    return jsonify(message='Mã sản phẩm đã tồn tại. Chọn mã riêng cho sản phẩm này.'),409
            product_id=str(uuid.uuid4())
            image=cv2.imencode('.png',sample.image)[1].tobytes()
            registration_phase('saving')
            db.add(product_id,clean,image,sample.quality)
            with db.lock:db.cache[product_id]=sample
            row=next(row for row in db.summary_rows() if row['id']==product_id)
            registration_phase('saved')
            return jsonify(status='registered',product=db.product(row),preview=encode_image(sample.image)),201
    @app.post('/api/match')
    def match():
        if not app.match_lock.acquire(blocking=False):return jsonify(status='busy',message='Máy chủ đang xử lý ảnh khác. Thử lại sau vài giây.'),429
        try:
            data=body();explain=data.get('explain') is True
            sample=prepare(decode_image(data.get('image')),data.get('corners'),explain=explain)
            refs=db.references()
            if not refs:
                result={'status':'empty','message':'Chưa có tem nào trong cơ sở dữ liệu. Người quản lý cần đăng ký tem mẫu trước.'}
                if explain:result['analysis']=build_analysis(sample,decision=result,threshold=config['threshold'],margin=config['margin'])
                return jsonify(result)
            started=time.monotonic()
            result=decide(sample,refs,config['threshold'],config['margin'],diagnostics=explain)
            geometry=result.pop('_geometry',None)
            product_id=result.get('match',{}).get('product_id')
            if result['status']=='matched':
                row=next(row for row in db.summary_rows() if row['id']==product_id)
                result['product']=db.product(row)
            if explain:
                reference=next((ref for pid,ref in refs if pid==product_id),None)
                result['analysis']=build_analysis(sample,decision=result,reference=reference,geometry=geometry,threshold=config['threshold'],margin=config['margin'])
            result['preview']=encode_image(sample.image)
            result['elapsed_ms']=round((time.monotonic()-started)*1000)
            try:db.log_scan(result['status'],product_id,result.get('match',{}).get('score'))
            except Exception:logging.warning('Could not save scan metadata')
            return jsonify(result)
        finally:app.match_lock.release()
    @app.get('/api/products/<product_id>/image')
    @admin
    def product_image(product_id):
        row=next((row for row in db.rows() if row['id']==product_id),None)
        if row is None:return jsonify(message='Không tìm thấy tem.'),404
        return send_file(io.BytesIO(row['image']),mimetype='image/png')
    @app.delete('/api/products/<product_id>')
    @admin
    def delete_product(product_id):
        with app.match_lock:
            changed=db.delete(product_id)
            db.cache.pop(product_id,None)
        if not changed:return jsonify(message='Không tìm thấy tem.'),404
        return jsonify(status='deleted')
    @app.put('/api/products/<product_id>')
    @admin
    def update_product(product_id):
        info=body().get('product')
        if not isinstance(info,dict):return jsonify(message='Thiếu thông tin sản phẩm.'),400
        clean={field:str(info.get(field,'')).strip()[:3000] for field in FIELDS}
        if not clean['product_name'] or not clean['product_code']:return jsonify(message='Nhập tên và mã sản phẩm.'),400
        with app.match_lock:
            for row in db.summary_rows():
                if row['id']!=product_id and json.loads(row['data'])['product_code'].casefold()==clean['product_code'].casefold():
                    return jsonify(message='Mã sản phẩm đã tồn tại.'),409
            changed=db.update(product_id,clean)
        if not changed:return jsonify(message='Không tìm thấy tem.'),404
        return jsonify(status='updated')
    @app.get('/api/backup')
    @admin
    def backup():
        buffer=io.BytesIO()
        with app.match_lock:
            filename,snapshot=db.export()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(filename,snapshot)
                archive.writestr('README.txt','Bản sao lưu Tem Vân Giấy. Không chứa khóa quản lý. File SQLite: tắt máy chủ trước khi thay cơ sở dữ liệu. File JSON trực tuyến: bản xuất hồ sơ và ảnh mẫu, cần công cụ nhập phù hợp khi khôi phục.')
        buffer.seek(0)
        return send_file(buffer,mimetype='application/zip',as_attachment=True,download_name='Sao_luu_tem_van_giay.zip')
    @app.post('/api/demo')
    @admin
    def demo():
        demo_dir=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'demo'
        records=json.loads((demo_dir/'records.json').read_text(encoding='utf-8'))
        added=0
        with app.match_lock:
            existing={json.loads(row['data'])['product_code'] for row in db.summary_rows()}
            if len(existing)+len(records)>100:return jsonify(message='Không còn đủ chỗ cho mẫu minh họa.'),409
            for record in records:
                info=record['product']
                if info['product_code'] in existing:continue
                sample=prepare(cv2.imread(str(demo_dir/record['image'])))
                image=cv2.imencode('.png',sample.image)[1].tobytes()
                db.add(str(uuid.uuid4()),info,image,sample.quality)
                added+=1
        return jsonify(status='ok',added=added)
    return app

if __name__=='__main__':
    from waitress import serve
    app=create_app()
    serve(app,host=os.environ.get('TEM_HOST','127.0.0.1'),port=int(os.environ.get('PORT') or os.environ.get('TEM_PORT','8765')),threads=4)
