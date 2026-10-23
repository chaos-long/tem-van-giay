const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const sandbox={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/camera.js'),'utf8'),sandbox);
const camera=sandbox.window.TemCamera;
function fixture(){
 let stopped=0;
 const track={stop(){stopped++;},getSettings(){return {deviceId:'back'};},getCapabilities(){return {focusMode:['continuous']};},async applyConstraints(){}};
 const stream={getTracks(){return [track];},getVideoTracks(){return [track];}};
 const video={srcObject:null,async play(){}};
 return {track,stream,video,stopped:()=>stopped};
}
test('working preview survives a blocked camera list and requests no microphone',async()=>{
 const f=fixture();let constraints;
 const mediaDevices={async getUserMedia(value){constraints=value;return f.stream;},async enumerateDevices(){throw new Error('enumeration blocked');}};
 const result=await camera.open({mediaDevices,video:f.video});
 assert.equal(result.stream,f.stream);assert.equal(result.devices.length,0);assert.equal(f.stopped(),0);
 assert.equal(constraints.audio,false);assert.equal(constraints.video.facingMode.ideal,'environment');
});
test('failed video playback releases camera and clears attached stream',async()=>{
 const f=fixture();f.video.play=async()=>{throw new Error('play failed');};
 await assert.rejects(camera.open({mediaDevices:{async getUserMedia(){return f.stream;}},video:f.video}),/play failed/);
 assert.equal(f.stopped(),1);assert.equal(f.video.srcObject,null);
});
test('unsupported focus controls do not stop a valid preview',async()=>{
 const f=fixture();f.track.applyConstraints=async()=>{throw new Error('focus not supported');};
 const result=await camera.open({mediaDevices:{async getUserMedia(){return f.stream;},async enumerateDevices(){return [];}},video:f.video});
 assert.equal(result.stream,f.stream);assert.equal(f.stopped(),0);
});
test('selected camera is respected',async()=>{
 const f=fixture();let constraints;
 await camera.open({mediaDevices:{async getUserMedia(value){constraints=value;return f.stream;},async enumerateDevices(){return [];}},video:f.video,deviceId:'selected-back'});
 assert.equal(constraints.video.deviceId.exact,'selected-back');assert.equal(constraints.video.facingMode,undefined);
});
test('permission error explains overlay possibility without claiming a definite cause',()=>{
 const message=camera.errorMessage({name:'NotAllowedError'});
 assert.match(message,/Nếu đã cấp quyền/);assert.match(message,/bong bóng/);assert.match(message,/Chụp bằng camera điện thoại/);
});
