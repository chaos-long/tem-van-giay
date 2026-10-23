/* Camera preview is optional. Native photo capture uses a separate file input. */
(function(root){
 'use strict';
 function stop(stream){if(stream)for(const track of stream.getTracks())track.stop();}
 function errorMessage(error){
  if(error?.name==='NotAllowedError'||error?.name==='SecurityError')return 'Trình duyệt đang chặn camera. Nếu đã cấp quyền, hãy đóng bong bóng chat, cửa sổ nổi hoặc ứng dụng lọc màu màn hình rồi thử lại. Bạn cũng có thể chọn “Chụp bằng camera điện thoại” hoặc tải ảnh có sẵn.';
  if(error?.name==='NotFoundError')return 'Không tìm thấy camera. Hãy chọn ảnh có sẵn hoặc dùng camera của điện thoại.';
  if(error?.name==='NotReadableError'||error?.name==='AbortError')return 'Không mở được camera lúc này. Đóng ứng dụng khác đang dùng camera, rồi thử lại hoặc chụp bằng camera điện thoại.';
  if(error?.name==='OverconstrainedError')return 'Camera đã chọn không còn sẵn sàng. Thử camera khác hoặc dùng ảnh có sẵn.';
  return error?.message||'Không mở được camera. Bạn có thể chụp bằng camera điện thoại hoặc chọn ảnh có sẵn.';
 }
 async function open({mediaDevices,video,deviceId}){
  if(!mediaDevices?.getUserMedia)throw new Error('Camera xem trước cần HTTPS hoặc localhost. Bạn vẫn có thể dùng nút chụp bằng camera điện thoại hoặc chọn ảnh.');
  const videoConstraints={width:{ideal:2560},height:{ideal:1920}};
  if(deviceId)videoConstraints.deviceId={exact:deviceId};else videoConstraints.facingMode={ideal:'environment'};
  const stream=await mediaDevices.getUserMedia({audio:false,video:videoConstraints});
  try{
   const track=stream.getVideoTracks()[0];
   try{if(track?.getCapabilities?.().focusMode?.includes('continuous'))await track.applyConstraints({advanced:[{focusMode:'continuous'}]});}catch{}
   video.srcObject=stream;await video.play();
   let devices=[];
   // Some mobile browsers deny enumeration even after opening the camera.
   // A failed camera list must not discard a working preview.
   try{devices=(await mediaDevices.enumerateDevices()).filter(device=>device.kind==='videoinput');}catch{}
   return {stream,devices,deviceId:track?.getSettings?.().deviceId||''};
  }catch(error){stop(stream);if(video.srcObject===stream)video.srcObject=null;throw error;}
 }
 root.TemCamera={open,stop,errorMessage};
})(window);
