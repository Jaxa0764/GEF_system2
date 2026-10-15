export function haversine(a,b){const r=Math.PI/180,p=Math.sin((b[0]-a[0])*r/2)**2+Math.cos(a[0]*r)*Math.cos(b[0]*r)*Math.sin((b[1]-a[1])*r/2)**2;return 6371000*2*Math.atan2(Math.sqrt(Math.min(1,p)),Math.sqrt(Math.max(0,1-p)))}
export function geometryProgress(origin,coordinates){
 const latScale=111320,lonScale=111320*Math.cos(origin.latitude*Math.PI/180);
 let minimum=Infinity,nearest=0,remaining=0,projection=0;
 for(let i=0;i<coordinates.length-1;i++){
  const a=coordinates[i],b=coordinates[i+1];const ax=(a[0]-origin.longitude)*lonScale,ay=(a[1]-origin.latitude)*latScale,bx=(b[0]-origin.longitude)*lonScale,by=(b[1]-origin.latitude)*latScale;
  const dx=bx-ax,dy=by-ay,k=Math.max(0,Math.min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy||1))),d=Math.hypot(ax+k*dx,ay+k*dy);
  if(d<minimum){minimum=d;nearest=i;projection=k}
 }
 for(let i=nearest;i<coordinates.length-1;i++)remaining+=haversine([coordinates[i][1],coordinates[i][0]],[coordinates[i+1][1],coordinates[i+1][0]])*(i===nearest?1-projection:1);
 return {offRoute:minimum,remaining_m:remaining,index:nearest};
}
