import base64,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cloud_database import CloudDatabase
import pytest

def test_cloud_validates_https_and_secret():
    with pytest.raises(RuntimeError):CloudDatabase('http://project.example','secret')
    with pytest.raises(RuntimeError):CloudDatabase('https://project.example','')

def test_cloud_record_roundtrip_and_no_secret_in_export():
    db=CloudDatabase('https://project.example','server-only-secret')
    record={'id':'abc','data':{'product_name':'Mẫu','product_code':'M-1'},'image_base64':base64.b64encode(b'png-test').decode(),'quality':{'feature_count':40},'created_at':'2026-10-14'}
    with patch.object(db,'request',return_value=[record]):
        row=db.rows()[0]
        assert row['image']==b'png-test' and db.product(row)['product_name']=='Mẫu'
        name,raw=db.export()
        assert name.endswith('.json') and b'server-only-secret' not in raw

def test_cloud_add_passes_base64_image_and_json_data():
    db=CloudDatabase('https://project.example','server-only-secret')
    with patch.object(db,'request',return_value=[]) as request:
        db.add('abc',{'product_name':'Mẫu'},b'png-test',{'feature_count':40})
        args=request.call_args.args
        assert args[0]=='tem_products' and args[1]=='POST'
        assert base64.b64decode(args[2]['image_base64'])==b'png-test'

def test_cloud_startup_creates_fresh_state_directory(tmp_path,monkeypatch):
    from server import create_app
    monkeypatch.setenv('SUPABASE_URL','https://project.example')
    monkeypatch.setenv('SUPABASE_SERVICE_KEY','server-only-secret')
    state=tmp_path/'new-cloud-state'
    app=create_app(state,admin_token='test-key')
    assert isinstance(app.db,CloudDatabase)
    assert (state/'settings.json').is_file()

def test_summary_reads_do_not_request_images():
    db=CloudDatabase('https://project.example','server-only-secret')
    row={'id':'abc','data':{'product_code':'M-1'},'quality':{},'created_at':'2026-10-23'}
    with patch.object(db,'request',return_value=[row]) as request:
        assert 'image' not in db.summary_rows()[0]
        assert 'image_base64' not in request.call_args.kwargs['params']['select']

def test_cached_references_only_read_metadata_and_remove_deleted_samples():
    db=CloudDatabase('https://project.example','server-only-secret')
    reference=object();db.cache={'abc':reference,'removed':object()}
    row={'id':'abc','data':'{}','quality':'{}','created_at':'2026-10-23'}
    with patch.object(db,'summary_rows',return_value=[row]),patch.object(db,'request') as request:
        assert db.references()==[('abc',reference)]
        assert 'removed' not in db.cache
        request.assert_not_called()

def test_cold_reference_cache_fetches_images_once():
    import cv2
    from test_app import make_paper
    db=CloudDatabase('https://project.example','server-only-secret')
    raw=cv2.imencode('.png',make_paper(92))[1].tobytes()
    row={'id':'abc','data':'{}','quality':'{}','created_at':'2026-10-23'}
    image={'id':'abc','image_base64':base64.b64encode(raw).decode()}
    with patch.object(db,'summary_rows',return_value=[row]),patch.object(db,'request',return_value=[image]) as request:
        first=db.references();second=db.references()
        assert first[0][0]=='abc' and first[0][1] is second[0][1]
        assert first[0][1].descriptors is not None
        request.assert_called_once()
        assert request.call_args.kwargs['params']['select']=='id,image_base64'
