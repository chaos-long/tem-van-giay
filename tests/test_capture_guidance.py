import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matcher import compare,prepare,decide
from test_app import make_paper,scene,payload,client,register

def test_recording_rejection_reason_does_not_change_comparison():
    query=prepare(scene(make_paper(12),True));reference=prepare(scene(make_paper(12)))
    reasons=[];plain=compare(query,reference);explained=compare(query,reference,failure_reasons=reasons)
    assert plain==explained and not reasons

def test_different_paper_reports_failure_without_exposing_candidate(client):
    assert register(client,scene(make_paper(12))).status_code==201
    response=client.post('/api/match',json={**payload(scene(make_paper(72))),'explain':True})
    data=response.json
    assert data['status']=='no_match'
    assert data['reason_code'] in {'features','geometry','coverage','overlap','texture'}
    assert data['capture_hint'] and data['analysis']['decision']['message']==data['capture_hint']
    assert 'product' not in data and 'match' not in data
    assert len(data['analysis']['stages'])==6

def test_acceptance_and_ambiguity_rules_unchanged_with_guidance():
    query=prepare(scene(make_paper(12),True));reference=prepare(scene(make_paper(12)))
    accepted=decide(query,[('one',reference)])
    ambiguous=decide(query,[('one',reference),('two',reference)])
    assert accepted['status']=='matched' and 'capture_hint' not in accepted
    assert ambiguous['status']=='ambiguous' and 'product' not in ambiguous
