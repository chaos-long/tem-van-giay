from pathlib import Path
import cv2
import numpy as np
import pytest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matcher import prepare,decide,encode_image,ImageProblem
from server import create_app

def make_paper(seed):
    rng=np.random.default_rng(seed)
    noise=rng.normal(0,1,(500,700)).astype(np.float32)
    fibers=cv2.GaussianBlur(noise,(0,0),1.3)
    gray=np.clip(221+fibers*38,0,255).astype(np.uint8)
    for _ in range(400):
        x,y=rng.integers(40,660),rng.integers(35,465)
        x2,y2=x+rng.integers(-17,18),y+rng.integers(-9,10)
        cv2.line(gray,(int(x),int(y)),(int(x2),int(y2)),int(rng.integers(167,219)),1,cv2.LINE_AA)
    gray=cv2.GaussianBlur(gray,(3,3),.35)
    image=cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)
    cv2.rectangle(image,(5,5),(694,494),(45,45,45),3)
    return image

def scene(tag,changed=False):
    canvas=np.full((760,1080,3),55,np.uint8)
    source=np.float32([[0,0],[699,0],[699,499],[0,499]])
    target=np.float32([[150,90],[902,133],[870,644],[110,610]]) if changed else np.float32([[160,100],[860,100],[860,600],[160,600]])
    h=cv2.getPerspectiveTransform(source,target)
    transformed=cv2.warpPerspective(tag,h,(1080,760))
    mask=cv2.warpPerspective(np.ones((500,700),np.uint8),h,(1080,760))>0
    canvas[mask]=transformed[mask]
    if changed:canvas=np.clip(canvas.astype(np.float32)*.88+18,0,255).astype(np.uint8)
    return canvas

def payload(img):return {'image':encode_image(img)}

@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path,admin_token='test-key');app.testing=True
    return app.test_client()

def register(client,img,code='SP-001',name='Sản phẩm thử'):
    return client.post('/api/products',headers={'Authorization':'Bearer test-key'},json={**payload(img),'product':{'product_name':name,'product_code':code,'maker':'Nhóm thử nghiệm','material_source':'Dữ liệu mô phỏng, không phải giấy thật','revenue_use':'Chưa có giao dịch thực'}})

def test_same_paper_changed_perspective_and_light():
    a=prepare(scene(make_paper(12)));q=prepare(scene(make_paper(12),True));other=prepare(scene(make_paper(72)))
    result=decide(q,[('right',a),('wrong',other)])
    assert result['status']=='matched' and result['match']['product_id']=='right'

def test_different_paper_same_border_rejected():
    a=prepare(scene(make_paper(12)));q=prepare(scene(make_paper(72),True))
    assert decide(q,[('wrong',a)])['status']=='no_match'

def test_ambiguous_reference_does_not_return_product():
    a=prepare(scene(make_paper(12)))
    assert decide(a,[('a',a),('b',a)])['status']=='ambiguous'

def test_blank_and_blurred_rejected():
    for tag in [np.full((500,700,3),225,np.uint8),cv2.GaussianBlur(make_paper(12),(61,61),14)]:
        with pytest.raises(ImageProblem):prepare(scene(tag))

def test_roundtrip_persistence_and_product_info(client,tmp_path):
    first=register(client,scene(make_paper(12)));assert first.status_code==201,first.json
    reopened=create_app(tmp_path,admin_token='test-key').test_client()
    result=reopened.post('/api/match',json=payload(scene(make_paper(12),True)))
    assert result.status_code==200 and result.json['status']=='matched'
    assert result.json['product']['maker']=='Nhóm thử nghiệm'
    unknown=reopened.post('/api/match',json=payload(scene(make_paper(72))))
    assert unknown.json['status']=='no_match' and 'product' not in unknown.json

def test_admin_write_protection(client):
    assert client.post('/api/products',json={}).status_code==401
    assert client.get('/api/products').status_code==401
    assert client.delete('/api/products/anything').status_code==401
    assert client.get('/api/backup').status_code==401

def test_duplicate_reference_and_edit_delete(client):
    first=register(client,scene(make_paper(12)));assert first.status_code==201
    pid=first.json['product']['id'];auth={'Authorization':'Bearer test-key'}
    assert register(client,scene(make_paper(12)),code='OTHER').status_code==409
    assert register(client,scene(make_paper(72)),code='SP-001').status_code==409
    edited=client.put('/api/products/'+pid,headers=auth,json={'product':{'product_name':'Tên đã sửa','product_code':'SP-001'}})
    assert edited.status_code==200
    found=client.post('/api/match',json=payload(scene(make_paper(12))))
    assert found.json['product']['product_name']=='Tên đã sửa'
    assert client.get('/api/backup',headers=auth).status_code==200
    assert client.delete('/api/products/'+pid,headers=auth).status_code==200
    assert client.get('/api/health').json['product_count']==0

def test_bad_images_and_corners(client):
    assert client.post('/api/match',json={'image':'not-an-image'}).status_code==422
    bad={**payload(scene(make_paper(12))),'corners':[[0,0],[1,0],[2,1],[0,1]]}
    assert client.post('/api/inspect',json=bad).status_code==422
    assert client.get('/api/not-found').status_code==404

def test_manual_corners_fallback(client):
    data={**payload(make_paper(12)),'corners':[[0,0],[1,0],[1,1],[0,1]]}
    response=client.post('/api/inspect',json=data)
    assert response.status_code==200,response.json

def test_pages_cors_allowlist(client,monkeypatch):
    monkeypatch.setenv('TEM_ALLOWED_ORIGINS','https://chaos-long.github.io')
    allowed=client.options('/api/match',headers={'Origin':'https://chaos-long.github.io','Access-Control-Request-Method':'POST'})
    assert allowed.headers['Access-Control-Allow-Origin']=='https://chaos-long.github.io'
    denied=client.get('/api/health',headers={'Origin':'https://untrusted.example'})
    assert 'Access-Control-Allow-Origin' not in denied.headers
