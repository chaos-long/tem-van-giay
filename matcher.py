"""Experimental image registration and texture matching, not an authenticity certificate."""
import base64
from dataclasses import dataclass
import cv2
import numpy as np

cv2.setNumThreads(1)
WIDTH, HEIGHT = 640, 448
SIGMA_FINE, SIGMA_COARSE = .8, 4.0
RANSAC_ERROR_PX, RANSAC_MAX_ITERATIONS = 3.0, 2000

class ImageProblem(ValueError):
    def __init__(self, message, analysis=None):
        super().__init__(message)
        self.analysis = analysis

def decode_image(value):
    if not isinstance(value, str) or len(value) > 22_000_000:
        raise ImageProblem('Ảnh quá lớn. Hãy dùng ảnh JPG/PNG dưới 12 MB.')
    try:
        raw = base64.b64decode(value.split(',')[-1], validate=True)
        if len(raw) > 12_000_000:
            raise ValueError()
        # Bound dimensions BEFORE decompressing a potentially very large image.
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(raw)) as probe:
            if probe.width * probe.height > 24_000_000 or min(probe.size) < 160:
                raise ValueError()
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError()
    except Exception as exc:
        raise ImageProblem('Không đọc được ảnh. Dùng JPG/PNG rõ nét, tối đa 24 megapixel.') from exc
    # Browser upload path applies EXIF orientation before submitting; native uploads
    # use the same browser canvas path.
    return image

def encode_image(image):
    return base64.b64encode(cv2.imencode('.png', image)[1]).decode()

def ordered_corners(points):
    p = np.asarray(points, np.float32)
    if p.shape != (4, 2) or not np.isfinite(p).all():
        raise ImageProblem('Cần đúng bốn góc khác nhau của tem.')
    center = p.mean(axis=0)
    p = p[np.argsort(np.arctan2(p[:, 1]-center[1], p[:, 0]-center[0]))]
    p = np.roll(p, -int(np.argmin(p.sum(axis=1))), axis=0)
    if not cv2.isContourConvex(p.astype(np.int32)) or abs(cv2.contourArea(p)) < 200:
        raise ImageProblem('Bốn góc phải tạo thành một hình chữ nhật trong ảnh.')
    return p

def detect_rectangle(image):
    ih, iw = image.shape[:2]
    scale = min(1.0, 1200 / max(iw, ih))
    small = cv2.resize(image, None, fx=scale, fy=scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 35, 110)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3,3),np.uint8))
    # Large-scale smoothing suppresses fibers/background grain for OUTLINE search
    # only. Texture extraction below still receives the original sharp photograph.
    smooth = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (0,0), 4.5)
    light = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    masks = [light, cv2.bitwise_not(light)]
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    # Chroma helps distinguish brown paper from dark veins on a pale desk. Both
    # polarities are tested; this is not a rule that every paper must be brown.
    chroma = cv2.GaussianBlur(lab[:,:,2], (0,0), 4.5)
    use_chroma = float(np.percentile(chroma,95)-np.percentile(chroma,5)) >= 6
    if use_chroma:
        color = cv2.threshold(chroma,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        masks += [cv2.bitwise_and(a,b) for a in masks[:2]
                  for b in (color,cv2.bitwise_not(color))]
        masks += [color,cv2.bitwise_not(color)]
    masks = [cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8)) for mask in masks]
    candidates = []
    for binary in [edges]+masks:
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = abs(cv2.contourArea(contour))
            fraction = area / gray.size
            if not 0.08 <= fraction <= 0.94:
                continue
            for tolerance in (.012,.018,.022,.03,.04):
                poly = cv2.approxPolyDP(contour,tolerance*cv2.arcLength(contour,True),True)
                if len(poly)!=4 or not cv2.isContourConvex(poly):continue
                p = ordered_corners(poly[:,0,:])
                sides = [np.linalg.norm(p[(i+1)%4]-p[i]) for i in range(4)]
                ar = max((sides[0]+sides[2])/(sides[1]+sides[3]), (sides[1]+sides[3])/(sides[0]+sides[2]))
                fill=area/abs(cv2.contourArea(p))
                if not (1.1<=ar<=3.5 and min(sides)>=65 and .88<=fill<=1.12):continue
                contrasts=[]
                for j in range(4):
                    a,b=p[j],p[(j+1)%4];direction=(b-a)/sides[j]
                    normal=np.array([-direction[1],direction[0]])*6
                    points=a+(b-a)*np.linspace(.15,.85,45)[:,None]
                    inside=np.rint(points+normal).astype(int);outside=np.rint(points-normal).astype(int)
                    for positions in (inside,outside):
                        positions[:,0]=np.clip(positions[:,0],0,small.shape[1]-1)
                        positions[:,1]=np.clip(positions[:,1],0,small.shape[0]-1)
                    delta=lab[inside[:,1],inside[:,0]].astype(float)-lab[outside[:,1],outside[:,0]].astype(float)
                    contrast=np.median(delta,axis=0)
                    if use_chroma:contrast[0]*=.25
                    contrasts.append(float(np.linalg.norm(contrast)))
                # A huge quadrilateral with one side lying on the background
                # should lose to a paper outline supported on all four sides.
                support=min(1.,min(contrasts)/(8 if use_chroma else 12))
                score=area*(.15+.85*support)*(1-min(.12,abs(1-fill)))
                candidates.append((score,p/scale))
                break
    if not candidates:
        raise ImageProblem('Chưa tìm được viền tem. Đặt tem trên nền tối hoặc chọn bốn góc thủ công.')
    candidates.sort(key=lambda item:item[0], reverse=True)
    return candidates[0][1]

def normalize(image, corners=None):
    ih, iw = image.shape[:2]
    if corners is None:
        corners = detect_rectangle(image)
    else:
        if not isinstance(corners, list) or len(corners) != 4:
            raise ImageProblem('Cần chọn bốn góc tem.')
        try:
            corners = ordered_corners([[float(q[0])*iw,float(q[1])*ih] for q in corners])
        except (ValueError, TypeError, IndexError) as exc:
            raise ImageProblem('Tọa độ góc tem không hợp lệ.') from exc
        if np.any(corners < 0) or np.any(corners[:,0] > iw) or np.any(corners[:,1] > ih):
            raise ImageProblem('Các góc phải nằm trong ảnh.')
        if abs(cv2.contourArea(corners))/(iw*ih) < .04:
            raise ImageProblem('Tem quá nhỏ trong ảnh. Hãy chụp gần hơn.')
    p = ordered_corners(corners)
    if np.linalg.norm(p[1]-p[0]) < np.linalg.norm(p[2]-p[1]):
        p = np.roll(p,-1,axis=0)
    # Never enlarge a tiny input into a misleadingly detailed reference.
    if min(np.linalg.norm(p[(i+1)%4]-p[i]) for i in range(4)) < 140:
        raise ImageProblem('Tem có quá ít điểm ảnh. Chụp gần hơn và lấy nét vào vùng giấy.')
    destination = np.float32([[0,0],[WIDTH-1,0],[WIDTH-1,HEIGHT-1],[0,HEIGHT-1]])
    matrix = cv2.getPerspectiveTransform(p, destination)
    normalized = cv2.warpPerspective(image,matrix,(WIDTH,HEIGHT))
    # Use only the blank inner area; omit the shared frame and orientation marker.
    gray = cv2.cvtColor(normalized,cv2.COLOR_BGR2GRAY)[45:403,64:576]
    return normalized, gray, (p / np.float32([iw,ih])).tolist()

def gaussian_layers(gray):
    g = gray.astype(np.float32)/255
    return (cv2.GaussianBlur(g,(0,0),SIGMA_FINE),
            cv2.GaussianBlur(g,(0,0),SIGMA_COARSE))


def texture(gray):
    fine,coarse=gaussian_layers(gray)
    return fine-coarse

def features(gray):
    band = texture(gray)
    contrast = cv2.normalize(band,None,0,255,cv2.NORM_MINMAX).astype(np.uint8)
    sift = cv2.SIFT_create(nfeatures=1600,contrastThreshold=.018,edgeThreshold=12,sigma=1.2)
    kp, descriptors = sift.detectAndCompute(contrast,None)
    return np.float32([k.pt for k in kp]).reshape(-1,2),descriptors

@dataclass
class Sample:
    image: np.ndarray
    gray: np.ndarray
    points: np.ndarray
    descriptors: np.ndarray
    quality: dict
    corners: list

def prepare(image,corners=None,explain=False):
    normalized,gray,quad = normalize(image,corners)
    points,descriptors = features(gray)
    sharpness = float(cv2.Laplacian(gray,cv2.CV_32F).var())
    detail = float(texture(gray).std()*255)
    quality={'sharpness':round(sharpness,2),'texture_detail':round(detail,2),'feature_count':len(points)}
    sample = Sample(normalized,gray,points,descriptors,quality,quad)
    if sharpness < 7 or detail < 1.0 or descriptors is None or len(points) < 18:
        message='Vùng giấy chưa đủ chi tiết để so khớp. Tăng ánh sáng, chụp gần và lấy nét; không dùng ảnh bị làm trắng nền.'
        raise ImageProblem(message,build_analysis(sample,eligible=False,quality_message=message) if explain else None)
    return sample

def correlation(a,b):
    a=a.astype(np.float32).ravel();b=b.astype(np.float32).ravel()
    a-=a.mean();b-=b.mean()
    denom=float(np.linalg.norm(a)*np.linalg.norm(b))
    return float(np.dot(a,b)/denom) if denom>1e-8 else 0.0

def compare(query,reference,diagnostics=False,failure_reasons=None):
    def reject(reason):
        if failure_reasons is not None:failure_reasons.append(reason)
        return None
    matcher=cv2.BFMatcher(cv2.NORM_L2)
    pairs=matcher.knnMatch(query.descriptors,reference.descriptors,k=2)
    good=[a for pair in pairs if len(pair)==2 for a,b in [pair] if a.distance < .72*b.distance]
    # One-to-one correspondence avoids inflating inlier counts on repeated print.
    unique={}
    for m in sorted(good,key=lambda m:m.distance):
        unique.setdefault(m.trainIdx,m)
    good=list(unique.values())
    if len(good)<14:return reject('features')
    source=np.float32([query.points[m.queryIdx] for m in good])
    target=np.float32([reference.points[m.trainIdx] for m in good])
    homography,inlier_mask=cv2.findHomography(source,target,cv2.RANSAC,RANSAC_ERROR_PX,maxIters=RANSAC_MAX_ITERATIONS)
    if homography is None or inlier_mask is None or not np.isfinite(homography).all():return reject('geometry')
    flags=inlier_mask.ravel().astype(bool);inliers=int(flags.sum())
    if inliers<14 or inliers/len(good)<.45:return reject('geometry')
    h,w=reference.gray.shape
    rect=np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
    mapped=cv2.perspectiveTransform(rect,homography)[:,0,:]
    area=abs(cv2.contourArea(mapped))
    if not cv2.isContourConvex(mapped.astype(np.int32)) or not .55*w*h<area<1.7*w*h:return reject('geometry')
    coverage=len({(min(2,int(p[0]/w*3)),min(2,int(p[1]/h*3))) for p in target[flags]})
    if coverage<4:return reject('coverage')
    aligned=cv2.warpPerspective(query.gray,homography,(w,h))
    mask=cv2.warpPerspective(np.ones(query.gray.shape,np.uint8),homography,(w,h))>0
    mask[:12]=False;mask[-12:]=False;mask[:,:12]=False;mask[:,-12:]=False
    if float(mask.mean())<.55:return reject('overlap')
    a=texture(aligned);b=texture(reference.gray)
    values=[]
    for y in range(3):
        for x in range(3):
            sl=(slice(y*h//3,(y+1)*h//3),slice(x*w//3,(x+1)*w//3))
            valid=mask[sl]
            if valid.mean()>.70:values.append(correlation(a[sl][valid],b[sl][valid]))
    if len(values)<6:return reject('overlap')
    median=float(np.median(values));overall=correlation(a[mask],b[mask])
    score=.7*median+.3*overall
    result={'score':round(max(0,score),4),'inliers':inliers,'coverage_tiles':coverage,'median_texture':round(median,4)}
    if diagnostics:
        # These are the geometry and accepted points from THIS comparison, not a
        # second reconstruction or an invented illustration. Never JSON-encode them.
        result['_geometry']={'source':source[flags],'target':target[flags],
                             'all_source':source,'all_target':target,'inlier_flags':flags,
                             'aligned':aligned,'mask':mask}
    return result

def decide(query,records,threshold=.64,margin=.08,diagnostics=False):
    candidates=[]
    failure_reasons=[]
    best_geometry=None;best_score=-1.0
    for product_id,reference in records:
        result=compare(query,reference,diagnostics=diagnostics,failure_reasons=failure_reasons)
        if result:
            geometry=result.pop('_geometry',None)
            if result['score']>best_score:
                best_score=result['score'];best_geometry=geometry
            candidates.append({'product_id':product_id,**result})
    candidates.sort(key=lambda item:item['score'],reverse=True)
    if not candidates or candidates[0]['score']<threshold:
        order={'features':0,'geometry':1,'coverage':2,'overlap':3,'texture':4}
        reason='texture' if candidates else max(failure_reasons,key=lambda code:order[code],default='features')
        hints={
            'features':'Chưa tìm đủ chi tiết ảnh tương ứng. Chụp đúng cùng mặt giấy đã đăng ký, gần hơn, lấy nét vào vân và dùng ánh sáng đều.',
            'geometry':'Các cặp chi tiết chưa cho phép căn ảnh ổn định. Đặt giấy phẳng, giữ đủ bốn góc và tránh chụp quá nghiêng.',
            'coverage':'Các điểm phù hợp chỉ nằm trên một vùng quá nhỏ. Chụp rõ toàn vùng giấy, tránh che khuất hoặc chỉ lấy một góc.',
            'overlap':'Các vùng sau căn chưa chồng lên nhau đủ. Kiểm tra viền xanh; chọn lại bốn góc nếu viền đang bám vào nền hoặc bóng.',
            'texture':'Đã căn được ít nhất một ứng viên nhưng vân sau căn chưa đủ giống. Chụp cùng mặt giấy, đặt phẳng, tránh lóa và giữ ảnh chụp lại để nhóm kiểm tra.'}
        return {'status':'no_match','message':'Chưa tìm thấy ảnh tem khớp trong cơ sở dữ liệu.',
                'reason_code':reason,'capture_hint':hints[reason],'quality':query.quality}
    best=candidates[0]
    if len(candidates)>1 and best['score']-candidates[1]['score']<margin:
        return {'status':'ambiguous','message':'Có nhiều mẫu gần giống nhau. Chưa đủ căn cứ để trả thông tin sản phẩm.','quality':query.quality}
    result={'status':'matched','message':'Tìm thấy tem đã đăng ký.','match':best,'quality':query.quality}
    if diagnostics:result['_geometry']=best_geometry
    return result


def _stage(stage_id,title,description,image):
    height,width=image.shape[:2]
    # Lossless compression keeps multi-stage explanations practical on mobile.
    png=cv2.imencode('.png',image,[cv2.IMWRITE_PNG_COMPRESSION,3])[1]
    return {'id':stage_id,'title':title,'description':description,
            'image':base64.b64encode(png).decode(),'width':width,'height':height}


def _visible_texture(gray):
    """Only a display mapping: recognition continues using the original float DoG."""
    band=texture(gray)
    scale=float(np.percentile(np.abs(band),99))
    if scale<1e-8:return np.full(gray.shape,127,np.uint8)
    return np.clip(127.5+band/scale*110,0,255).astype(np.uint8)


def _pair_indices(flags,limit=60):
    """The same bounded selection is drawn before/after RANSAC; never invent pairs."""
    if len(flags)<=limit:return np.arange(len(flags))
    kept=np.flatnonzero(flags);rejected=np.flatnonzero(~flags)
    rejected_count=min(len(rejected),limit//3)
    kept_count=min(len(kept),limit-rejected_count)
    rejected_count=min(len(rejected),limit-kept_count)
    def take(values,count):
        return values[np.linspace(0,len(values)-1,count,dtype=int)] if count else np.array([],dtype=int)
    return np.sort(np.concatenate([take(kept,kept_count),take(rejected,rejected_count)]))


def _pair_view(query_gray,reference_gray,source,target,selected,flags=None):
    view=np.hstack([cv2.cvtColor(query_gray,cv2.COLOR_GRAY2BGR),
                    cv2.cvtColor(reference_gray,cv2.COLOR_GRAY2BGR)])
    offset=query_gray.shape[1]
    for index in selected:
        color=(210,140,40) if flags is None else ((70,200,50) if flags[index] else (60,65,220))
        a=tuple(np.rint(source[index]).astype(int))
        b=tuple(np.rint(target[index]+[offset,0]).astype(int))
        cv2.line(view,a,b,color,1,cv2.LINE_AA)
        cv2.circle(view,a,3,color,1,cv2.LINE_AA)
        cv2.circle(view,b,3,color,1,cv2.LINE_AA)
    return view


def build_analysis(sample,eligible=True,quality_message=None,decision=None,
                   reference=None,geometry=None,threshold=.64,margin=.08):
    """Ephemeral images for explanation; no raw uploads or diagnostics are saved.

    Reference details are included ONLY for a unique accepted match. A near miss
    must not reveal any stored reference or candidate identity.
    """
    stage1=_stage('rectified','1. Căn thẳng tem',
        'Ảnh tem sau khi dùng bốn góc để căn về 640 × 448 pixel. Khoảng 10% mỗi mép sẽ được bỏ khi đọc vân.',sample.image)
    stage2=_stage('gray','2. Chọn vùng vân',
        'Vùng giữa 512 × 358 pixel được chuyển sang xám. Chữ và viền ở mép nằm ngoài vùng này.',sample.gray)
    enhanced=_visible_texture(sample.gray)
    fine,coarse=gaussian_layers(sample.gray)
    gaussian_fine=_stage('gaussian_fine','3. Gaussian nhẹ (σ = 0,8)',
        'Làm mờ có trọng số: điểm gần tâm được tính nhiều hơn. Sigma 0,8 giữ lại nhiều chi tiết nhỏ. Đây là một trong hai ảnh số thực được dùng để lấy hiệu; ảnh xem được làm tròn về 8 bit, chưa tăng tương phản.',np.rint(np.clip(fine,0,1)*255).astype(np.uint8))
    gaussian_coarse=_stage('gaussian_coarse','4. Gaussian mạnh (σ = 4)',
        'Cùng vùng giấy nhưng làm mờ rộng hơn với sigma 4, nên nền sáng tối lớn còn lại rõ hơn các chi tiết nhỏ. So với bước trước sẽ thấy ảnh mượt hơn. Phép lấy hiệu dùng giá trị số thực, không dùng hai ảnh xem đã làm tròn.',np.rint(np.clip(coarse,0,1)*255).astype(np.uint8))
    stage3=_stage('texture','5. Hiệu hai ảnh Gaussian (DoG)',
        'Lấy chênh lệch hai ảnh làm mờ Gaussian (sigma 0,8 và 4). Ảnh xem đã tăng tương phản theo từng ảnh để dễ quan sát; không tạo thêm chi tiết hay chứng minh đây là sợi giấy.',enhanced)
    points_view=cv2.cvtColor(enhanced,cv2.COLOR_GRAY2BGR)
    displayed=min(350,len(sample.points))
    for point in sample.points[:displayed]:
        cv2.circle(points_view,tuple(np.rint(point).astype(int)),3,(90,220,70),1,cv2.LINE_AA)
    stage4=_stage('features','6. Tìm điểm đặc trưng SIFT',
        f'Tìm được {len(sample.points)} điểm SIFT. Hình khoanh {displayed} điểm có thật (hiển thị tối đa 350); đây là chi tiết ảnh để đối chiếu, không phải phân đoạn từng sợi giấy.',points_view)
    analysis={'version':1,'stages':[stage1,stage2,gaussian_fine,gaussian_coarse,stage3,stage4],
              'quality':sample.quality,'eligible':eligible,'quality_message':quality_message}
    if decision is not None:
        status=decision['status']
        summary={'status':status,'threshold':threshold,'margin':margin}
        if decision.get('capture_hint'):summary['message']=decision['capture_hint']
        if status=='matched':
            summary.update({k:decision['match'][k] for k in ['score','inliers','coverage_tiles']})
        analysis['decision']=summary
    else:status=None
    if status!='matched' or reference is None or geometry is None:return analysis

    all_source,all_target=geometry['all_source'],geometry['all_target']
    inlier_flags=geometry['inlier_flags']
    selected_pairs=_pair_indices(inlier_flags)
    kept=int(inlier_flags.sum());rejected=int(len(inlier_flags)-kept)
    shown_kept=int(inlier_flags[selected_pairs].sum());shown_rejected=int(len(selected_pairs)-shown_kept)
    analysis['ransac']={'candidate_pairs':len(inlier_flags),'inliers':kept,'outliers':rejected,
                        'displayed_inliers':shown_kept,'displayed_outliers':shown_rejected,
                        'max_iterations':RANSAC_MAX_ITERATIONS,'reprojection_threshold_px':RANSAC_ERROR_PX}
    analysis['stages'].append(_stage('matches_raw','7. Ghép cặp trước RANSAC',
        f'Trái là ảnh chụp, phải là mẫu khớp. Có {len(inlier_flags)} cặp ứng viên sau so mô tả SIFT, lọc tỷ lệ 0,72 và giữ một cặp cho mỗi điểm mẫu. Vẽ {len(selected_pairs)} cặp thực, tối đa 60; màu xanh lam chưa nói cặp đó phù hợp hình học. Bước sau dùng đúng các cặp đang vẽ để phân loại.',
        _pair_view(sample.gray,reference.gray,all_source,all_target,selected_pairs)))
    analysis['stages'].append(_stage('ransac','8. RANSAC giữ và loại cặp điểm',
        f'RANSAC thử các nhóm điểm để tìm một phép biến đổi phối cảnh được nhiều cặp cùng tuân theo. Mặt nạ kết quả của chính lần so này giữ {kept} cặp và loại {rejected} cặp. Trên hình: {shown_kept} cặp xanh lá được giữ, {shown_rejected} cặp đỏ bị loại. Ngưỡng sai số 3 pixel; 2.000 là giới hạn vòng thử, không phải số vòng đã ghi nhận. Không dựng lại các vòng thử bên trong thư viện.',
        _pair_view(sample.gray,reference.gray,all_source,all_target,selected_pairs,inlier_flags)))

    left=cv2.cvtColor(sample.gray,cv2.COLOR_GRAY2BGR)
    right=cv2.cvtColor(reference.gray,cv2.COLOR_GRAY2BGR)
    correspondences=np.hstack([left,right]);offset=sample.gray.shape[1]
    source,target=geometry['source'],geometry['target']
    selected=np.linspace(0,len(source)-1,min(60,len(source)),dtype=int)
    for index in selected:
        a=tuple(np.rint(source[index]).astype(int))
        b=tuple(np.rint(target[index]+[offset,0]).astype(int))
        cv2.line(correspondences,a,b,(90,210,50),1,cv2.LINE_AA)
        cv2.circle(correspondences,a,3,(30,150,20),1,cv2.LINE_AA)
        cv2.circle(correspondences,b,3,(30,150,20),1,cv2.LINE_AA)
    analysis['stages'].append(_stage('correspondences','9. Các cặp được giữ',
        f'Trái: ảnh bạn chụp. Phải: mẫu được nhận khớp. Có {len(source)} điểm phù hợp hình học sau RANSAC; hình nối {len(selected)} cặp có thật, tối đa 60 cặp. Ảnh mẫu chỉ hiện khi đã nhận khớp duy nhất.',correspondences))
    aligned=geometry['aligned'];mask=geometry['mask']
    aligned_view=cv2.cvtColor(aligned,cv2.COLOR_GRAY2BGR)
    aligned_view[~mask]=(72,72,72)
    analysis['stages'].append(_stage('aligned','10. Căn hai vùng để đối chiếu',
        'Trái: ảnh chụp đã căn theo mẫu. Phải: ảnh mẫu. Phần xám đậm bên trái nằm ngoài vùng được so. Điểm so khớp dùng tương quan vân trên vùng hợp lệ.',np.hstack([aligned_view,right])))
    diff=np.abs(texture(aligned)-texture(reference.gray))
    scale=float(np.percentile(diff[mask],99))
    display=np.clip(diff/max(scale,1e-8)*255,0,255).astype(np.uint8)
    heatmap=cv2.applyColorMap(display,cv2.COLORMAP_INFERNO);heatmap[~mask]=(72,72,72)
    analysis['stages'].append(_stage('difference','11. Quan sát phần khác nhau',
        'Ảnh phụ minh họa độ chênh tuyệt đối giữa hai vùng vân đã căn: màu sáng hơn là chênh lớn hơn trong ảnh này; vùng xám nằm ngoài phép so. Màu đã tăng tương phản tương đối, không phải xác suất thật/giả và không thay công thức NCC đang ra quyết định.',heatmap))
    return analysis
