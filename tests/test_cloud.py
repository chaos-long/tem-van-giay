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
