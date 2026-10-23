'use strict';
const $=id=>document.getElementById(id);
const isLocal=/^(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$/.test(location.hostname);
let base=localStorage.getItem('temServer')||window.TEM_CONFIG?.apiBase||(isLocal?location.origin:'');
let token=sessionStorage.getItem('temAdmin')||'';
let imageData=null,originalImage=null,corners=null,manual=false,clicks=[],stream=null,editing=null,products=[];
let imageGeneration=0,working=false,imageReady=false;
let activeAnalysis=null,analysisStep=0;
function message(id,text,error=false){$(id).textContent=text;$(id).classList.toggle('error',error);}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,4500);}
async function api(path,method='GET',body=null,auth=false){
 if(!base)throw new Error('Chưa có địa chỉ máy chủ. Mở mục Kết nối hoặc nhờ nhóm cấu hình máy chủ HTTPS.');
 const headers={};if(body)headers['Content-Type']='application/json';if(auth)headers.Authorization='Bearer '+token;
 const response=await fetch(base+path,{method,headers,body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(path==='/api/products'&&method==='POST'?120000:45000)});
 if(path==='/api/backup'){if(!response.ok)throw new Error('Không tải được bản sao lưu. Kiểm tra khóa quản lý.');return response.blob();}
 let data;try{data=await response.json();}catch{throw new Error('Địa chỉ không trả về dữ liệu của Tem Vân Giấy.');}
 if(!response.ok){const e=new Error(data.message||'Không thực hiện được yêu cầu.');e.status=response.status;e.analysis=data.analysis;throw e;}return data;
}
function connectionError(e){if(e.name==='TimeoutError')return 'Máy chủ phản hồi quá lâu. Kiểm tra kết nối và thử lại.';if(e instanceof TypeError)return 'Không kết nối được máy chủ. Kiểm tra địa chỉ và trạng thái máy chủ của nhóm.';return e.message;}
async function health(){try{const data=await api('/api/health');$('connectionStatus').textContent='Đã kết nối';$('connectionStatus').classList.remove('offline');$('sampleCount').textContent=data.product_count+' tem mẫu';return data;}catch(e){$('connectionStatus').textContent='Chưa kết nối';$('connectionStatus').classList.add('offline');throw e;}}
function showView(view){document.querySelectorAll('.view').forEach(el=>el.hidden=true);$(view+'View').hidden=false;document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.view===view));if(view==='manage'){showAdmin();if(token)loadProducts();}}
document.querySelectorAll('.nav').forEach(el=>el.onclick=()=>showView(el.dataset.view));
$('serverUrl').value=base;
$('connectButton').onclick=async()=>{let parsed;try{parsed=new URL($('serverUrl').value.trim());if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password||parsed.pathname!=='/')throw new Error();if(location.protocol==='https:'&&parsed.protocol!=='https:')throw new Error();}catch{message('connectMessage',location.protocol==='https:'?'Web HTTPS cần máy chủ HTTPS. Dùng địa chỉ https://ten-may-chu.':'Dùng địa chỉ http://192.168.1.10:8765 hoặc https://ten-may-chu.',true);return;}base=parsed.origin;localStorage.setItem('temServer',base);token='';sessionStorage.removeItem('temAdmin');try{const data=await health();message('connectMessage','Đã kết nối. Cơ sở dữ liệu có '+data.product_count+' tem.');}catch(e){message('connectMessage',connectionError(e),true);}};
function stopCamera(){if(stream)stream.getTracks().forEach(track=>track.stop());stream=null;$('video').srcObject=null;$('video').hidden=true;$('cameraControls').hidden=true;$('startCamera').textContent='Mở camera';if(originalImage){$('photoCanvas').hidden=false;drawPhoto();}else $('placeholder').hidden=false;}
async function startCamera(deviceId){try{stopCamera();if(!navigator.mediaDevices?.getUserMedia)throw new Error('Camera cần mở web tại localhost hoặc HTTPS. Bạn vẫn có thể chọn ảnh từ máy.');stream=await navigator.mediaDevices.getUserMedia({audio:false,video:deviceId?{deviceId:{exact:deviceId},width:{ideal:1920},height:{ideal:1080}}:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1080}}});$('video').srcObject=stream;await $('video').play();$('video').hidden=false;$('photoCanvas').hidden=true;$('placeholder').hidden=true;$('cameraControls').hidden=false;const devices=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='videoinput');$('cameraDevice').replaceChildren(...devices.map((d,i)=>{const o=document.createElement('option');o.value=d.deviceId;o.textContent=d.label||('Camera '+(i+1));return o;}));const current=stream.getVideoTracks()[0].getSettings().deviceId;if(current)$('cameraDevice').value=current;message('imageMessage','Giữ tem hình chữ nhật đủ bốn góc, rồi bấm “Chụp tem”.');}catch(e){message('imageMessage',e.name==='NotAllowedError'?'Chưa được cấp quyền camera. Cho phép camera trong trình duyệt hoặc chọn ảnh từ máy.':e.message,true);}}
$('startCamera').onclick=()=>startCamera();$('stopCamera').onclick=stopCamera;$('cameraDevice').onchange=()=>startCamera($('cameraDevice').value);
function drawPhoto(){if(!originalImage)return;const canvas=$('photoCanvas');canvas.width=originalImage.naturalWidth;canvas.height=originalImage.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(originalImage,0,0);const pts=manual?clicks:corners;if(pts?.length){ctx.strokeStyle='#4ce1a4';ctx.fillStyle='#1d6c4a';ctx.lineWidth=Math.max(3,canvas.width/220);ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p[0]*canvas.width,p[1]*canvas.height):ctx.moveTo(p[0]*canvas.width,p[1]*canvas.height));if(pts.length===4)ctx.closePath();ctx.stroke();pts.forEach((p,i)=>{ctx.beginPath();ctx.arc(p[0]*canvas.width,p[1]*canvas.height,Math.max(8,canvas.width/90),0,Math.PI*2);ctx.fill();ctx.fillStyle='#fff';ctx.font=`bold ${Math.max(12,canvas.width/65)}px Arial`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(i+1,p[0]*canvas.width,p[1]*canvas.height);ctx.fillStyle='#1d6c4a';});}}
function resetResult(){const r=$('result');r.className='result-empty';r.replaceChildren();const h=document.createElement('h3');h.textContent='Ảnh mới đã được chọn';const p=document.createElement('p');p.textContent='Kiểm tra vùng tem đã căn, rồi tìm sản phẩm khớp.';r.append(h,p);}
function clearAnalysis(text='Chọn ảnh hoặc chụp tem để xem ảnh đã căn thẳng, hai mức Gaussian, vân giấy và các điểm đặc trưng. Bước RANSAC xuất hiện khi tìm được một mẫu khớp duy nhất.',state='Chưa có ảnh'){
 activeAnalysis=null;analysisStep=0;$('analysisContent').hidden=true;$('analysisEmpty').hidden=false;$('analysisEmptyText').textContent=text;$('analysisState').textContent=state;$('analysisSteps').replaceChildren();$('analysisImage').removeAttribute('src');$('analysisImage').alt='';$('analysisMetrics').replaceChildren();$('analysisDecision').replaceChildren();$('analysisDecision').hidden=true;$('analysisAvailability').textContent='';$('analysisRansacMetrics').replaceChildren();$('analysisRansacNote').textContent='';$('analysisRansac').hidden=true;
}
function numberText(value,digits=0){return value!==null&&value!==undefined&&Number.isFinite(Number(value))?Number(value).toLocaleString('vi-VN',{minimumFractionDigits:digits,maximumFractionDigits:digits}):'Chưa đo';}
function analysisStageTitle(stage){return stage.title.replace(/^\s*\d{1,2}[.)]\s*/,'');}
function selectAnalysisStep(index){
 if(!activeAnalysis)return;analysisStep=Math.max(0,Math.min(index,activeAnalysis.stages.length-1));const stage=activeAnalysis.stages[analysisStep];
 const title=analysisStageTitle(stage);$('analysisImage').src='data:image/png;base64,'+stage.image;$('analysisImage').alt=title+' — ảnh từ lần xử lý hiện tại';
 $('analysisStepNumber').textContent='BƯỚC '+(analysisStep+1)+' / '+activeAnalysis.stages.length;$('analysisStepTitle').textContent=title;$('analysisDescription').textContent=stage.description||'';
 const dimensions=Number.isFinite(stage.width)&&Number.isFinite(stage.height)?stage.width+' × '+stage.height+' px · ':'';$('analysisCaption').textContent=dimensions+'Ảnh từ lần xử lý hiện tại; không phải hình minh họa dựng sẵn.';
 $('analysisSteps').querySelectorAll('button').forEach((button,i)=>{if(i===analysisStep)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');});
 $('analysisPrevious').disabled=analysisStep===0;$('analysisNext').disabled=analysisStep===activeAnalysis.stages.length-1;
 $('analysisRansac').hidden=!activeAnalysis.ransac||!['matches_raw','ransac','correspondences','aligned','difference'].includes(stage.id);
}
function renderAnalysis(analysis,afterMatch=false){
 const stages=analysis?.version===1&&Array.isArray(analysis.stages)?analysis.stages.filter(stage=>stage&&typeof stage.title==='string'&&typeof stage.image==='string'&&/^[A-Za-z0-9+/=\s]+$/.test(stage.image)).slice(0,16):[];
 if(!stages.length){clearAnalysis('Máy chủ chưa cung cấp ảnh từng bước cho lần xử lý này. Bạn vẫn có thể dùng chức năng so khớp nếu ảnh đạt yêu cầu.','Chưa có ảnh từng bước');return;}
 activeAnalysis={...analysis,stages};$('analysisEmpty').hidden=true;$('analysisContent').hidden=false;
 const decision=analysis.decision;const states={matched:'Đã đối chiếu',no_match:'Chưa khớp',ambiguous:'Chưa rõ một mẫu',empty:'Chưa có mẫu',quality_error:'Chưa đủ chi tiết'};
 $('analysisState').textContent=analysis.eligible===false?'Chưa đủ chi tiết':states[decision?.status]||'Ảnh đầu vào';
 $('analysisSteps').replaceChildren(...stages.map((stage,index)=>{const li=element('li');const button=element('button',null,'analysis-step');button.type='button';button.append(element('span',String(index+1).padStart(2,'0')),element('span',analysisStageTitle(stage)));button.onclick=()=>selectAnalysisStep(index);li.append(button);return li;}));
 const hasRansac=stages.some(stage=>stage.id==='ransac');const hasComparison=stages.some(stage=>['matches_raw','ransac','correspondences','aligned','difference'].includes(stage.id));
 $('analysisAvailability').textContent=hasRansac?'Các ảnh đối chiếu dùng mẫu đã được chấp nhận duy nhất. Mở bước RANSAC để xem cặp màu xanh được giữ và cặp màu đỏ bị loại.':hasComparison?'Máy chủ có ảnh đối chiếu với mẫu đã chấp nhận. Bản máy chủ này chưa cung cấp riêng ảnh trước và sau RANSAC.':analysis.eligible===false?'Đang xem các bước của ảnh vừa chụp. Ảnh chưa đạt chất lượng nên chưa có minh họa đối chiếu hai ảnh hay RANSAC.':decision?.status==='empty'?'Đang xem các bước của ảnh vừa chụp. Cơ sở dữ liệu chưa có mẫu để đối chiếu hai ảnh và hiển thị RANSAC.':decision?.status==='no_match'||decision?.status==='ambiguous'?'Đang xem các bước của ảnh vừa chụp. Chưa có một mẫu khớp được chấp nhận duy nhất, nên không hiển thị ảnh mẫu, các cặp điểm hay RANSAC.':'Đang xem các bước của ảnh vừa chụp. Bấm “Tìm sản phẩm khớp”; ảnh ghép điểm và RANSAC chỉ được hiển thị sau khi có một mẫu khớp được chấp nhận duy nhất.';
 const quality=analysis.quality||{};$('analysisMetrics').replaceChildren();
 for(const [label,value,digits] of [['Độ rõ (Laplacian)',quality.sharpness,1],['Độ biến thiên vân',quality.texture_detail,2],['Tổng điểm đặc trưng',quality.feature_count,0]]){const row=element('div');row.append(element('dt',label),element('dd',numberText(value,digits)));$('analysisMetrics').append(row);}
 const ransac=analysis.ransac;$('analysisRansacMetrics').replaceChildren();$('analysisRansacNote').textContent='';
 if(ransac){for(const [label,value,suffix] of [['Cặp điểm trước lọc',ransac.candidate_pairs,''],['Cặp được giữ',ransac.inliers,''],['Cặp bị loại',ransac.outliers,''],['Ngưỡng sai số chiếu',ransac.reprojection_threshold_px,' px'],['Giới hạn lượt thử',ransac.max_iterations,'']]){if(Number.isFinite(value)){const row=element('div');row.append(element('dt',label),element('dd',numberText(value)+suffix));$('analysisRansacMetrics').append(row);}}const notes=[];if(Number.isFinite(ransac.displayed_inliers)&&Number.isFinite(ransac.displayed_outliers))notes.push('Ảnh RANSAC vẽ '+numberText(ransac.displayed_inliers)+' cặp được giữ và '+numberText(ransac.displayed_outliers)+' cặp bị loại từ kết quả thực.');if(Number.isFinite(ransac.max_iterations))notes.push('Tối đa '+numberText(ransac.max_iterations)+' lượt thử là giới hạn cấu hình, không phải số lượt thực tế đã ghi lại.');$('analysisRansacNote').textContent=notes.join(' ');}
 const box=$('analysisDecision');box.replaceChildren();box.classList.toggle('quality-warning',analysis.eligible===false);box.hidden=!decision&&analysis.eligible!==false;
 if(analysis.eligible===false){box.append(element('strong','Cần chụp lại trước khi so khớp'),element('p',analysis.quality_message||'Ảnh chưa đạt điều kiện về độ rõ hoặc chi tiết vân.'));
 }else if(decision){box.append(element('strong',states[decision.status]||'Điều kiện đối chiếu'));if(decision.message)box.append(element('p',decision.message));if(Number.isFinite(decision.score))box.append(element('p','Điểm so khớp: '+numberText(decision.score,3)+(Number.isFinite(decision.inliers)?' · '+numberText(decision.inliers)+' cặp điểm phù hợp':'')+(Number.isFinite(decision.coverage_tiles)?' · '+numberText(decision.coverage_tiles)+'/9 ô có điểm':'')));if(Number.isFinite(decision.threshold)&&Number.isFinite(decision.margin))box.append(element('p','Ngưỡng thử nghiệm: '+numberText(decision.threshold,3)+'. Chênh lệch tối thiểu với mẫu gần thứ hai: '+numberText(decision.margin,3)+'.'));}
 const ransacIndex=stages.findIndex(stage=>stage.id==='ransac');const compareIndex=ransacIndex>=0?ransacIndex:stages.findIndex(stage=>stage.id==='correspondences');selectAnalysisStep(afterMatch&&compareIndex>=0?compareIndex:0);
}
$('analysisPrevious').onclick=()=>selectAnalysisStep(analysisStep-1);$('analysisNext').onclick=()=>selectAnalysisStep(analysisStep+1);
function invalidateImageWork(text='Đang đọc ảnh mới…',state='Đang xử lý'){
 imageGeneration++;working=false;imageReady=false;$('matchButton').disabled=true;$('matchButton').textContent='Tìm sản phẩm khớp';$('cropBlock').hidden=true;clearAnalysis(text,state);return imageGeneration;
}
async function useDataUrl(data,expectedGeneration=null){
 if(expectedGeneration!==null&&expectedGeneration!==imageGeneration)return;const generation=invalidateImageWork();imageData=null;corners=null;clicks=[];manual=false;$('photoCanvas').classList.remove('manual');$('selectionControls').hidden=false;resetResult();
 let loadedImage;try{loadedImage=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('Không đọc được ảnh.'));img.src=data;});}catch(e){if(generation===imageGeneration){message('imageMessage',e.message,true);clearAnalysis('Không đọc được ảnh. Chọn một ảnh khác để xem các bước.','Chưa xử lý được');}return;}if(generation!==imageGeneration)return;
 originalImage=loadedImage;imageData=data;stopCamera();$('photoCanvas').hidden=false;$('placeholder').hidden=true;drawPhoto();await inspect();
}
async function inspect(){
 if(!imageData)return;const generation=invalidateImageWork('Đang căn vùng giấy và tạo ảnh từng bước…');message('imageMessage','Đang tìm viền và kiểm tra độ rõ của vùng vân…');
 try{const data=await api('/api/inspect','POST',{image:imageData,corners:manual?corners:null,explain:true});if(generation!==imageGeneration)return;corners=data.corners;if(manual)clicks=data.corners;$('cropPreview').src='data:image/png;base64,'+data.preview;$('cropBlock').hidden=false;imageReady=data.analysis?.eligible!==false;$('matchButton').disabled=!imageReady;renderAnalysis(data.analysis);message('imageMessage',imageReady?'Ảnh đủ chi tiết để thử so khớp. Kiểm tra viền xanh có đúng chiếc tem không.':data.analysis.quality_message||'Ảnh chưa đủ chi tiết để so khớp.',!imageReady);message('cornerStatus',manual?'Đã chọn bốn góc':'Đã tìm viền');drawPhoto();
 }catch(e){if(generation!==imageGeneration)return;$('cropBlock').hidden=true;imageReady=false;if(e.analysis)renderAnalysis(e.analysis);else clearAnalysis('Chưa tạo được ảnh từng bước. Chọn đủ bốn góc hoặc chụp lại tem rõ hơn.','Chưa xử lý được');message('imageMessage',connectionError(e),true);}
}
$('capture').onclick=async()=>{const video=$('video');if(!video.videoWidth)return;const canvas=document.createElement('canvas');const scale=Math.min(1,2200/video.videoWidth);canvas.width=video.videoWidth*scale;canvas.height=video.videoHeight*scale;canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);await useDataUrl(canvas.toDataURL('image/jpeg',.97));};
$('imageUpload').onchange=async event=>{const file=event.target.files[0];if(!file)return;const generation=invalidateImageWork();imageData=null;corners=null;resetResult();if(file.size>12_000_000){message('imageMessage','Chọn ảnh dưới 12 MB.',true);clearAnalysis('Ảnh vượt giới hạn 12 MB. Chọn ảnh nhỏ hơn để xem các bước.','Chưa xử lý được');event.target.value='';return;}try{const bmp=await createImageBitmap(file,{imageOrientation:'from-image'});if(bmp.width*bmp.height>24_000_000){bmp.close();throw new Error('Ảnh quá lớn. Dùng ảnh tối đa 24 megapixel.');}const scale=Math.min(1,2400/Math.max(bmp.width,bmp.height));const canvas=document.createElement('canvas');canvas.width=bmp.width*scale;canvas.height=bmp.height*scale;canvas.getContext('2d').drawImage(bmp,0,0,canvas.width,canvas.height);bmp.close();await useDataUrl(canvas.toDataURL('image/jpeg',.97),generation);}catch(e){if(generation===imageGeneration){message('imageMessage',e.message||'Không đọc được ảnh.',true);clearAnalysis('Không đọc được ảnh. Chọn một ảnh JPEG, PNG hoặc WebP khác.','Chưa xử lý được');}}event.target.value='';};
$('manualCorners').onclick=()=>{if(!originalImage||!imageData)return;invalidateImageWork('Chọn bốn góc để xử lý lại đúng vùng tem.','Chờ chọn góc');manual=true;clicks=[];corners=null;$('photoCanvas').classList.add('manual');message('cornerStatus','Chọn 4 góc của cùng một tem');message('imageMessage','Bấm bốn góc trên ảnh. Không cần chọn theo thứ tự; web sẽ sắp xếp lại.');drawPhoto();};
$('autoCorners').onclick=()=>{manual=false;clicks=[];corners=null;$('photoCanvas').classList.remove('manual');drawPhoto();inspect();};
$('photoCanvas').onclick=async event=>{if(!manual||clicks.length>=4)return;const r=event.target.getBoundingClientRect();clicks.push([(event.clientX-r.left)/r.width,(event.clientY-r.top)/r.height]);drawPhoto();message('cornerStatus',clicks.length+'/4 góc');if(clicks.length===4){corners=clicks.slice();await inspect();}};
function element(tag,text,cls){const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;}
function renderResult(data){const r=$('result');r.replaceChildren();if(data.status!=='matched'){r.className='result-empty';r.append(element('span',data.status==='ambiguous'?'?':'○','result-symbol'),element('h3',data.status==='ambiguous'?'Chưa xác định được một mẫu duy nhất':data.status==='empty'?'Chưa có tem mẫu':'Chưa tìm được tem khớp'),element('p',data.message));return;}r.className='result-body';r.append(element('span','Ảnh tem khớp với mẫu đã đăng ký','badge'),element('h3',data.product.product_name),element('div',data.product.product_code,'product-code'));if(data.product.description)r.append(element('p',data.product.description,'result-description'));for(const [key,label] of [['material_source','Nguồn vật liệu / nơi thu gom'],['collection_date','Ngày thu gom'],['maker','Người hoặc nhóm làm'],['revenue_use','Sử dụng nguồn thu'],['evidence_note','Bằng chứng / ghi chú kiểm tra']]){const row=element('div',null,'detail-row');row.append(element('strong',label),element('p',data.product[key]||'Chưa được cung cấp'));r.append(row);}r.append(element('p','Thông tin do người đăng ký cung cấp. Đối chiếu bằng chứng để kiểm tra nguồn gốc vật liệu và cách sử dụng nguồn thu.','result-note'));const details=element('details');details.append(element('summary','Xem thông tin đối chiếu'));details.append(element('p',`Điểm so khớp: ${data.match.score.toFixed(3)} · ${data.match.inliers} chi tiết phù hợp · ${data.elapsed_ms} ms. Điểm này không phải xác suất sản phẩm thật.`));r.append(details);}
$('matchButton').onclick=async()=>{if(!imageData||!imageReady||working)return;working=true;const generation=++imageGeneration;$('matchButton').disabled=true;$('matchButton').textContent='Đang so khớp…';clearAnalysis('Đang so khớp vân và tạo ảnh đối chiếu của lần kiểm tra này…','Đang đối chiếu');try{const data=await api('/api/match','POST',{image:imageData,corners,explain:true});if(generation===imageGeneration){renderResult(data);renderAnalysis(data.analysis,true);}}catch(e){if(generation===imageGeneration){if(e.analysis){renderAnalysis(e.analysis);if(e.analysis.eligible===false)imageReady=false;}else clearAnalysis('Chưa nhận được ảnh đối chiếu. Kiểm tra kết nối rồi thử lại.','Chưa đối chiếu được');message('imageMessage',connectionError(e),true);}}finally{if(generation===imageGeneration){working=false;$('matchButton').textContent='Tìm sản phẩm khớp';$('matchButton').disabled=!imageReady;}}};
function showAdmin(){ $('loginPanel').hidden=!!token;$('adminContent').hidden=!token;}
$('loginButton').onclick=async()=>{token=$('adminKey').value.trim();try{await api('/api/admin/login','POST',{},true);sessionStorage.setItem('temAdmin',token);$('adminKey').value='';showAdmin();await loadProducts();}catch(e){token='';message('loginMessage',connectionError(e),true);}};
$('logoutButton').onclick=()=>{token='';sessionStorage.removeItem('temAdmin');showAdmin();};
function newProduct(){editing=null;$('productForm').reset();$('formTitle').textContent='Thông tin sản phẩm mới';$('saveProduct').textContent='Đăng ký ảnh tem hiện tại';message('registerMessage','');}
$('newProduct').onclick=newProduct;
let batchRecords=[],batchRunning=false,batchStop=false;
$('openBatch').onclick=()=>{$('batchPanel').hidden=!$('batchPanel').hidden;};
$('batchUpload').onchange=async event=>{
 const file=event.target.files[0];if(!file||batchRunning)return;
 batchRecords=[];$('startBatch').disabled=true;$('batchList').replaceChildren();
 try{
  if(file.size>160_000_000)throw new Error('Bộ mẫu quá lớn. Chia thành tệp dưới 160 MB.');
  const data=JSON.parse(await file.text());
  if(!Array.isArray(data.records)||!data.records.length||data.records.length>100)throw new Error('Tệp cần có từ 1 đến 100 mục trong records.');
  const codes=new Set();
  for(const record of data.records){
   if(!record||typeof record.file!=='string'||typeof record.image!=='string'||record.image.length>22_000_000||!record.product||typeof record.product!=='object')throw new Error('Một mục thiếu tên tệp, ảnh hoặc hồ sơ.');
   const product=record.product;
   if(typeof product.product_name!=='string'||!product.product_name.trim()||typeof product.product_code!=='string'||!product.product_code.trim())throw new Error('Mỗi hồ sơ cần tên và mã sản phẩm.');
   const code=product.product_code.trim().toLowerCase();if(codes.has(code))throw new Error('Bộ mẫu có mã sản phẩm lặp: '+product.product_code);codes.add(code);
  }
  batchRecords=data.records.map(record=>({...record,state:'pending'}));
  for(const record of batchRecords){record.row=element('li',record.file+' · '+record.product.product_code+' · '+record.product.product_name+' — Chờ đăng ký');$('batchList').append(record.row);}
  message('batchMessage','Đã đọc '+batchRecords.length+' hồ sơ. Kiểm tra tên và mã, rồi bấm Đăng ký bộ mẫu.');$('startBatch').disabled=false;
 }catch(e){batchRecords=[];$('batchList').replaceChildren();message('batchMessage',e.message||'Không đọc được bộ mẫu.',true);}
 event.target.value='';
};
$('stopBatch').onclick=()=>{batchStop=true;message('batchMessage','Sẽ dừng sau khi máy chủ xử lý xong ảnh hiện tại.');};
$('startBatch').onclick=async()=>{
 if(batchRunning||!token||!batchRecords.length)return;
 batchRunning=true;batchStop=false;$('startBatch').disabled=true;$('batchUpload').disabled=true;$('stopBatch').hidden=false;
 let saved=0,skipped=0,failed=0;
 try{
  message('batchMessage','Đang kiểm tra quyền quản lý và danh sách mã đã có…');
  await api('/api/admin/login','POST',{},true);
  const current=await api('/api/products','GET',null,true);
  const existing=new Set(current.products.map(product=>product.product_code.trim().toLowerCase()));
  for(let index=0;index<batchRecords.length&&!batchStop;index++){
   const record=batchRecords[index],label=record.file+' · '+record.product.product_code+' · '+record.product.product_name;
   if(record.state==='saved'||existing.has(record.product.product_code.trim().toLowerCase())){skipped++;record.row.textContent=label+' — Đã có mã, bỏ qua';continue;}
   record.row.textContent=label+' — Đang kiểm tra và đăng ký…';message('batchMessage','Đang xử lý '+(index+1)+'/'+batchRecords.length+'. Đã thêm '+saved+' mẫu.');
   const phaseNames={idle:'đang tải ảnh tới máy chủ',reading_image:'đang đọc ảnh',waiting:'đang chờ tác vụ trước',checking_database:'đang đọc cơ sở dữ liệu',processing_image:'đang xử lý vùng giấy',checking_duplicates:'đang kiểm tra trùng',saving:'đang lưu cơ sở dữ liệu',saved:'đã lưu, đang chờ phản hồi'};
   let progressBusy=false,progressActive=true;
   const progressTimer=setInterval(async()=>{if(progressBusy)return;progressBusy=true;try{const status=await api('/api/admin/diagnostics','GET',null,true);if(progressActive)message('batchMessage','Ảnh '+(index+1)+'/'+batchRecords.length+': '+(phaseNames[status.phase]||'đang xử lý')+'. Đã thêm '+saved+' mẫu.');}catch{}finally{progressBusy=false;}},10000);
   try{
    const result=await api('/api/products','POST',{image:record.image,product:record.product,...(record.corners?{corners:record.corners}:{})},true);
    record.state='saved';record.id=result.product.id;record.row.textContent=label+' — Đã lưu · '+result.product.id;saved++;existing.add(record.product.product_code.trim().toLowerCase());
   }catch(e){
    record.state='failed';record.row.textContent=label+' — '+connectionError(e);failed++;
    // A timeout may happen after the database commit. Stop and refresh before
    // another attempt; never blindly resubmit a possibly successful write.
    if(e.status===401||e.name==='TimeoutError'||e instanceof TypeError){batchStop=true;}
   }finally{progressActive=false;clearInterval(progressTimer);}
  }
  message('batchMessage',(batchStop?'Đã dừng. ':'Đã xử lý xong. ')+'Thêm '+saved+' mẫu; bỏ qua '+skipped+' mã đã có; '+failed+' mục lỗi. Xem kết quả từng ảnh bên dưới.',failed>0);
 }catch(e){message('batchMessage',connectionError(e),true);}
 finally{batchRunning=false;$('batchUpload').disabled=false;$('stopBatch').hidden=true;$('startBatch').disabled=false;await loadProducts();health().catch(()=>{});}
};
async function loadProducts(){try{const data=await api('/api/products','GET',null,true);products=data.products;$('registeredCount').textContent=products.length+' mẫu';$('productList').replaceChildren();if(!products.length)$('productList').append(element('p','Chưa có mẫu nào. Chọn ảnh tem và nhập thông tin để bắt đầu.','subtle'));for(const product of products){const item=element('article',null,'product-item');item.append(element('h3',product.product_name),element('p',product.product_code+' · '+(product.maker||'Chưa ghi người làm')));const edit=element('button','Sửa thông tin','button text');edit.onclick=()=>{editing=product.id;for(const input of $('productForm').elements){if(input.name)input.value=product[input.name]||'';}$('formTitle').textContent='Sửa thông tin sản phẩm';$('saveProduct').textContent='Lưu thông tin';message('registerMessage','Giữ nguyên ảnh tem đã đăng ký.');$('productForm').scrollIntoView({behavior:'smooth',block:'start'});};const del=element('button','Xóa mẫu','button text danger');del.onclick=async()=>{if(!confirm('Xóa mẫu tem của '+product.product_name+'?'))return;try{await api('/api/products/'+product.id,'DELETE',null,true);if(editing===product.id)newProduct();await loadProducts();await health();}catch(e){toast(connectionError(e));}};item.append(edit,del);$('productList').append(item);}}catch(e){if(e.status===401){token='';sessionStorage.removeItem('temAdmin');showAdmin();}else toast(connectionError(e));}}
$('productForm').onsubmit=async event=>{event.preventDefault();const product=Object.fromEntries(new FormData(event.target));if(!editing&&(!imageData||!corners||!imageReady)){message('registerMessage','Chọn ảnh tem rõ nét ở mục Kiểm tra tem trước khi đăng ký.',true);return;}$('saveProduct').disabled=true;try{await api(editing?'/api/products/'+editing:'/api/products',editing?'PUT':'POST',editing?{product}:{image:imageData,corners,product},true);message('registerMessage',editing?'Đã cập nhật thông tin.':'Đã đăng ký ảnh tem và thông tin sản phẩm.');await loadProducts();await health();newProduct();toast('Đã lưu vào cơ sở dữ liệu.');}catch(e){message('registerMessage',connectionError(e),true);}finally{$('saveProduct').disabled=false;}};
$('backupButton').onclick=async()=>{try{const blob=await api('/api/backup','GET',null,true);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='Sao_luu_tem_van_giay.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast(connectionError(e));}};
window.addEventListener('pagehide',stopCamera);
$('demoButton').onclick=async()=>{try{const data=await api('/api/demo','POST',{},true);await loadProducts();await health();toast('Đã nạp '+data.added+' mẫu mô phỏng. Đây không phải giấy hoặc sản phẩm thật.');}catch(e){toast(connectionError(e));}};
health().catch(e=>{if(!base)message('imageMessage',e.message,true);});showAdmin();
