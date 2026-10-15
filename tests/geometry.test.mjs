import test from 'node:test';
import assert from 'node:assert/strict';
import {haversine,geometryProgress} from '../static/js/geometry.js';

test('distance is symmetric and zero at identical coordinates',()=>{
 const a=[41.3,69.2],b=[41.31,69.25];assert.equal(haversine(a,a),0);assert.ok(Math.abs(haversine(a,b)-haversine(b,a))<1e-6);assert.ok(haversine(a,b)>4000);
});
test('route progress projects onto road segments, not only vertices',()=>{
 const route=[[69.2,41.3],[69.24,41.3],[69.24,41.34]];
 const middle=geometryProgress({latitude:41.3,longitude:69.22},route);
 assert.ok(middle.offRoute<.1);assert.equal(middle.index,0);assert.ok(middle.remaining_m>5000);
 const end=geometryProgress({latitude:41.34,longitude:69.24},route);
 assert.ok(end.remaining_m<.1);assert.ok(end.offRoute<.1);
});
test('off-route detection measures perpendicular displacement',()=>{
 const value=geometryProgress({latitude:41.31,longitude:69.22},[[69.2,41.3],[69.24,41.3]]);
 assert.ok(value.offRoute>1000&&value.offRoute<1200);
});
