"""Outline regressions: textured light desks, shadows and imperfect paper edges."""
from pathlib import Path
import sys
import cv2
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matcher import detect_rectangle,ImageProblem

@pytest.mark.parametrize('paper,background',[
    ((110,134,145),(207,213,210)),
    ((228,228,228),(40,40,40)),
    ((95,95,95),(220,220,220)),
])
def test_paper_outline_on_textured_background_with_shadow(paper,background):
    rng=np.random.default_rng(21)
    image=np.full((900,700,3),background,np.uint8)
    for y in range(10,900,25):
        cv2.line(image,(0,y),(699,y+19),tuple(max(0,c-34) for c in background),3)
    expected=np.float32([[90,80],[580,65],[610,810],[70,825]])
    shadow=(expected+[22,11]).astype(np.int32)
    cv2.fillConvexPoly(image,shadow,tuple(max(0,c-45) for c in background))
    # Slightly bowed top edge and a small chipped bottom corner.
    outline=np.int32([[90,80],[340,84],[580,65],[610,800],[595,810],[70,825]])
    mask=np.zeros(image.shape[:2],np.uint8);cv2.fillPoly(mask,[outline],255)
    noise=rng.normal(0,10,image.shape[:2])[:,:,None]
    texture=np.clip(np.array(paper)[None,None,:]+noise,0,255).astype(np.uint8)
    image[mask>0]=texture[mask>0]
    result=detect_rectangle(image)
    actual=np.zeros_like(mask);cv2.fillConvexPoly(actual,result.astype(np.int32),255)
    target=np.zeros_like(mask);cv2.fillConvexPoly(target,expected.astype(np.int32),255)
    intersection=np.logical_and(actual,target).sum();union=np.logical_or(actual,target).sum()
    assert intersection/union>.90
    assert max(min(np.linalg.norm(p-q) for q in result) for p in expected)<50

def test_no_outline_is_reported_for_uniform_background():
    with pytest.raises(ImageProblem):detect_rectangle(np.full((700,900,3),180,np.uint8))
