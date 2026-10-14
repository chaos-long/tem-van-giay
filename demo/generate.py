"""Synthetic examples for software testing. These are not photos of real paper."""
from pathlib import Path
import cv2,json,numpy as np
ROOT=Path(__file__).resolve().parent
def paper(seed):
    rng=np.random.default_rng(seed)
    noise=rng.normal(0,1,(500,700)).astype(np.float32)
    gray=np.clip(221+cv2.GaussianBlur(noise,(0,0),1.3)*38,0,255).astype(np.uint8)
    for _ in range(400):
        x,y=rng.integers(40,660),rng.integers(35,465)
        cv2.line(gray,(int(x),int(y)),(int(x+rng.integers(-17,18)),int(y+rng.integers(-9,10))),int(rng.integers(167,219)),1,cv2.LINE_AA)
    image=cv2.cvtColor(cv2.GaussianBlur(gray,(3,3),.35),cv2.COLOR_GRAY2BGR)
    cv2.rectangle(image,(5,5),(694,494),(45,45,45),3)
    return image
def scene(tag,changed=False):
    out=np.full((760,1080,3),55,np.uint8)
    src=np.float32([[0,0],[699,0],[699,499],[0,499]])
    dst=np.float32([[150,90],[902,133],[870,644],[110,610]]) if changed else np.float32([[160,100],[860,100],[860,600],[160,600]])
    h=cv2.getPerspectiveTransform(src,dst)
    image=cv2.warpPerspective(tag,h,(1080,760));mask=cv2.warpPerspective(np.ones((500,700),np.uint8),h,(1080,760))>0
    out[mask]=image[mask]
    return np.clip(out.astype(np.float32)*.88+18,0,255).astype(np.uint8) if changed else out
if __name__=='__main__':
    for i,seed in enumerate([12,72,131],1):
        cv2.imwrite(str(ROOT/f'mau_mo_phong_{i}.png'),scene(paper(seed)))
        cv2.imwrite(str(ROOT/f'kiem_tra_mo_phong_{i}.jpg'),scene(paper(seed),True),[cv2.IMWRITE_JPEG_QUALITY,96])
    cv2.imwrite(str(ROOT/'mau_khong_co_trong_database.jpg'),scene(paper(777),True))
