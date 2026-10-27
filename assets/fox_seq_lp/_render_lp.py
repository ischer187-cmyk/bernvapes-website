
import bpy, math
HDRI='/Applications/Blender.app/Contents/Resources/4.5/datafiles/studiolights/world/city.exr'
s=bpy.context.scene; old=bpy.data.objects['Fox_Head']
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath='/Users/L5/Downloads/Meshy_AI__1013135403_model-edit.glb')
new=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in new: o.select_set(True)
bpy.context.view_layer.objects.active=new[0]
if len(new)>1: bpy.ops.object.join()
fox=bpy.context.view_layer.objects.active; fox.name='Fox_LP'; fox.matrix_world=old.matrix_world.copy()
rm=fox.modifiers.new('R','REMESH'); rm.mode='VOXEL'; rm.voxel_size=0.02; bpy.ops.object.modifier_apply(modifier='R')
import mathutils
xs=[v.co.x for v in fox.data.vertices]; zs=[v.co.z for v in fox.data.vertices]
hw=max(abs(min(xs)),abs(max(xs))); z0,z1=min(zs),max(zs); H=z1-z0
vg=fox.vertex_groups.new(name='cheek')
for v in fox.data.vertices:
    r=abs(v.co.x)/hw; zz=(v.co.z-z0)/H
    if r>0.62 and 0.22<zz<0.50:
        w=min(1.0,(r-0.62)/0.2)*min(1.0,(0.50-zz)/0.08,(zz-0.22)/0.08); vg.add([v.index],w,'REPLACE')
sm=fox.modifiers.new('S','SMOOTH'); sm.factor=0.9; sm.iterations=8; sm.vertex_group='cheek'; bpy.ops.object.modifier_apply(modifier='S')
n0=len(fox.data.polygons)
ZF=z0+0.31*H; EX=0.0  # Stirn
d=fox.modifiers.new('D','DECIMATE'); d.decimate_type='COLLAPSE'; d.ratio=900/n0; d.use_collapse_triangulate=True; d.use_symmetry=True; d.symmetry_axis='X'
bpy.ops.object.modifier_apply(modifier='D'); print('LP_FACES',len(fox.data.polygons))
for p in fox.data.polygons: p.use_smooth=False
# ---------- Material: gebürsteter Stahl, Rost, Kratzer ----------
m=bpy.data.materials.new('FoxMetal'); m.use_nodes=True; nt=m.node_tree; nodes=nt.nodes; links=nt.links
bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
tc=nodes.new('ShaderNodeTexCoord')
nRust=nodes.new('ShaderNodeTexNoise'); nRust.inputs['Scale'].default_value=5.0; nRust.inputs['Detail'].default_value=6.0; nRust.inputs['Roughness'].default_value=0.7
links.new(tc.outputs['Object'],nRust.inputs['Vector'])
ramp=nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=0.46; ramp.color_ramp.elements[1].position=0.60
links.new(nRust.outputs['Fac'],ramp.inputs['Fac'])
mixCol=nodes.new('ShaderNodeMix'); mixCol.data_type='RGBA'
mixCol.inputs[6].default_value=(0.17,0.18,0.21,1)     # Stahl
mixCol.inputs[7].default_value=(0.20,0.085,0.035,1)     # Rost
links.new(ramp.outputs['Color'],mixCol.inputs[0]); links.new(mixCol.outputs[2],bsdf.inputs['Base Color'])
mixMet=nodes.new('ShaderNodeMix'); mixMet.data_type='FLOAT'; mixMet.inputs[2].default_value=1.0; mixMet.inputs[3].default_value=0.25
links.new(ramp.outputs['Color'],mixMet.inputs[0]); links.new(mixMet.outputs[0],bsdf.inputs['Metallic'])
nRough=nodes.new('ShaderNodeTexNoise'); nRough.inputs['Scale'].default_value=9.0; nRough.inputs['Detail'].default_value=8.0
links.new(tc.outputs['Object'],nRough.inputs['Vector'])
mr=nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value=0.3; mr.inputs['From Max'].default_value=0.7; mr.inputs['To Min'].default_value=0.16; mr.inputs['To Max'].default_value=0.40
links.new(nRough.outputs['Fac'],mr.inputs['Value'])
mixRough=nodes.new('ShaderNodeMix'); mixRough.data_type='FLOAT'; mixRough.inputs[3].default_value=0.85
links.new(ramp.outputs['Color'],mixRough.inputs[0]); links.new(mr.outputs['Result'],mixRough.inputs[2]); links.new(mixRough.outputs[0],bsdf.inputs['Roughness'])
# Kratzer: gestreckte Noise-Streifen (zwei Richtungen), steile Ramp → vereinzelte dünne Linien; Bump + rauer
def streak(scale_vec, rot, thr):
    mp=nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value=scale_vec; mp.inputs['Rotation'].default_value=rot
    links.new(tc.outputs['Object'],mp.inputs['Vector'])
    nz=nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value=6.0; nz.inputs['Detail'].default_value=3.0; nz.inputs['Roughness'].default_value=0.5
    links.new(mp.outputs['Vector'],nz.inputs['Vector'])
    rp=nodes.new('ShaderNodeValToRGB'); rp.color_ramp.elements[0].position=thr; rp.color_ramp.elements[1].position=thr+0.04
    links.new(nz.outputs['Fac'],rp.inputs['Fac']); return rp
r1=streak((1.0,22.0,22.0),(0.0,0.0,0.35),0.66)
r2=streak((1.0,30.0,30.0),(0.0,0.0,-0.9),0.69)
mx=nodes.new('ShaderNodeMath'); mx.operation='MAXIMUM'; links.new(r1.outputs['Color'],mx.inputs[0]); links.new(r2.outputs['Color'],mx.inputs[1])
bump=nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=0.5; bump.inputs['Distance'].default_value=0.01; bump.invert=True
links.new(mx.outputs['Value'],bump.inputs['Height']); links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
addR=nodes.new('ShaderNodeMath'); addR.operation='MULTIPLY_ADD'; addR.inputs[1].default_value=0.3
links.new(mx.outputs['Value'],addR.inputs[0]); links.new(mixRough.outputs[0],addR.inputs[2])
for l in list(bsdf.inputs['Roughness'].links): links.remove(l)
links.new(addR.outputs['Value'],bsdf.inputs['Roughness'])
# starke Frassstellen: grosses Noise, dunkler Rost, pittiges Relief
nBig=nodes.new('ShaderNodeTexNoise'); nBig.inputs['Scale'].default_value=2.2; nBig.inputs['Detail'].default_value=5.0; nBig.inputs['Roughness'].default_value=0.75
links.new(tc.outputs['Object'],nBig.inputs['Vector'])
rBig=nodes.new('ShaderNodeValToRGB'); rBig.color_ramp.elements[0].position=0.585; rBig.color_ramp.elements[1].position=0.68; links.new(nBig.outputs['Fac'],rBig.inputs['Fac'])
mixCol2=nodes.new('ShaderNodeMix'); mixCol2.data_type='RGBA'; mixCol2.inputs[7].default_value=(0.11,0.045,0.02,1)
links.new(rBig.outputs['Color'],mixCol2.inputs[0]); links.new(mixCol.outputs[2],mixCol2.inputs[6])
for l in list(bsdf.inputs['Base Color'].links): links.remove(l)
links.new(mixCol2.outputs[2],bsdf.inputs['Base Color'])
mixMet2=nodes.new('ShaderNodeMix'); mixMet2.data_type='FLOAT'; mixMet2.inputs[3].default_value=0.1
links.new(rBig.outputs['Color'],mixMet2.inputs[0]); links.new(mixMet.outputs[0],mixMet2.inputs[2])
for l in list(bsdf.inputs['Metallic'].links): links.remove(l)
links.new(mixMet2.outputs[0],bsdf.inputs['Metallic'])
# Rauheit: Frassstellen matt
mixR2=nodes.new('ShaderNodeMix'); mixR2.data_type='FLOAT'; mixR2.inputs[3].default_value=0.92
links.new(rBig.outputs['Color'],mixR2.inputs[0]); links.new(addR.outputs['Value'],mixR2.inputs[2])
for l in list(bsdf.inputs['Roughness'].links): links.remove(l)
links.new(mixR2.outputs[0],bsdf.inputs['Roughness'])
# Relief: Rostmaske (beide) x feines Noise → zusaetzliche Bump-Hoehe
pit=nodes.new('ShaderNodeTexNoise'); pit.inputs['Scale'].default_value=60.0; pit.inputs['Detail'].default_value=6.0; links.new(tc.outputs['Object'],pit.inputs['Vector'])
rm_=nodes.new('ShaderNodeMath'); rm_.operation='MAXIMUM'; links.new(ramp.outputs['Color'],rm_.inputs[0]); links.new(rBig.outputs['Color'],rm_.inputs[1])
pm=nodes.new('ShaderNodeMath'); pm.operation='MULTIPLY'; links.new(rm_.outputs['Value'],pm.inputs[0]); links.new(pit.outputs['Fac'],pm.inputs[1])
hsum=nodes.new('ShaderNodeMath'); hsum.operation='MULTIPLY_ADD'; hsum.inputs[1].default_value=1.6
links.new(pm.outputs['Value'],hsum.inputs[0]); links.new(mx.outputs['Value'],hsum.inputs[2])
for l in list(bump.inputs['Height'].links): links.remove(l)
links.new(hsum.outputs['Value'],bump.inputs['Height'])
fox.data.materials.clear(); fox.data.materials.append(m)
# ---------- Welt: HDRI für Reflexionen ----------
w=s.world or bpy.data.worlds.new('W'); s.world=w; w.use_nodes=True; wn=w.node_tree
bg=next(n for n in wn.nodes if n.type=='BACKGROUND')
if HDRI:
    env=wn.nodes.new('ShaderNodeTexEnvironment'); env.image=bpy.data.images.load(HDRI); wn.links.new(env.outputs['Color'],bg.inputs['Color']); bg.inputs['Strength'].default_value=0.75
for ln in ('Key','Fill'):
    o=bpy.data.objects.get(ln)
    if o: o.data.energy*=0.45
# ---------- Bruchstück-Loch (Voronoi-Zellen) ----------
ng=bpy.data.node_groups.new('ChunkHole','GeometryNodeTree'); I=ng.interface
I.new_socket('Geometry',in_out='INPUT',socket_type='NodeSocketGeometry'); I.new_socket('Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
rs=I.new_socket('Radius',in_out='INPUT',socket_type='NodeSocketFloat'); cs=I.new_socket('Center',in_out='INPUT',socket_type='NodeSocketVector')
N=ng.nodes; L=ng.links
gi=N.new('NodeGroupInput'); go=N.new('NodeGroupOutput'); pos=N.new('GeometryNodeInputPosition')
vor=N.new('ShaderNodeTexVoronoi'); vor.voronoi_dimensions='3D'; vor.feature='F1'; vor.inputs['Scale'].default_value=2.1; vor.inputs['Randomness'].default_value=0.9
eod=N.new('GeometryNodeFieldOnDomain'); eod.domain='FACE'; eod.data_type='FLOAT_VECTOR'; L.new(pos.outputs['Position'],eod.inputs[0]); L.new(eod.outputs[0],vor.inputs['Vector'])
sub=N.new('ShaderNodeVectorMath'); sub.operation='SUBTRACT'; L.new(vor.outputs['Position'],sub.inputs[0]); L.new(gi.outputs['Center'],sub.inputs[1])
mul=N.new('ShaderNodeVectorMath'); mul.operation='MULTIPLY'; mul.inputs[1].default_value=(1,0,1); L.new(sub.outputs['Vector'],mul.inputs[0])
d1=N.new('ShaderNodeVectorMath'); d1.operation='LENGTH'; L.new(mul.outputs['Vector'],d1.inputs[0])
mir=N.new('ShaderNodeVectorMath'); mir.operation='MULTIPLY'; mir.inputs[1].default_value=(-1,1,1); L.new(gi.outputs['Center'],mir.inputs[0])
sub2=N.new('ShaderNodeVectorMath'); sub2.operation='SUBTRACT'; L.new(vor.outputs['Position'],sub2.inputs[0]); L.new(mir.outputs['Vector'],sub2.inputs[1])
mul2=N.new('ShaderNodeVectorMath'); mul2.operation='MULTIPLY'; mul2.inputs[1].default_value=(1,0,1); L.new(sub2.outputs['Vector'],mul2.inputs[0])
d2=N.new('ShaderNodeVectorMath'); d2.operation='LENGTH'; L.new(mul2.outputs['Vector'],d2.inputs[0])
ln_=N.new('ShaderNodeMath'); ln_.operation='MINIMUM'; L.new(d1.outputs['Value'],ln_.inputs[0]); L.new(d2.outputs['Value'],ln_.inputs[1])
jit=N.new('ShaderNodeMath'); jit.operation='MULTIPLY_ADD'; jit.inputs[1].default_value=0.10; L.new(vor.outputs['Distance'],jit.inputs[0]); L.new(ln_.outputs['Value'],jit.inputs[2])
# t = wie weit das Zentrum der Zelle schon "innerhalb" des Radius liegt → Flugweite
tt=N.new('ShaderNodeMath'); tt.operation='SUBTRACT'; L.new(gi.outputs['Radius'],tt.inputs[0]); L.new(jit.outputs['Value'],tt.inputs[1])
tc_=N.new('ShaderNodeMath'); tc_.operation='MAXIMUM'; tc_.inputs[1].default_value=0.0; L.new(tt.outputs['Value'],tc_.inputs[0])
tp=N.new('ShaderNodeMath'); tp.operation='POWER'; tp.inputs[1].default_value=1.3; L.new(tc_.outputs['Value'],tp.inputs[0])
# Richtung: radial vom Zentrum (XZ) + kräftig nach oben + Zufall pro Zelle
nrm=N.new('ShaderNodeVectorMath'); nrm.operation='NORMALIZE'; L.new(mul.outputs['Vector'],nrm.inputs[0])
rnd=N.new('ShaderNodeVectorMath'); rnd.operation='SUBTRACT'; rnd.inputs[1].default_value=(0.5,0.5,0.5); L.new(vor.outputs['Color'],rnd.inputs[0])
rnd2=N.new('ShaderNodeVectorMath'); rnd2.operation='SCALE'; rnd2.inputs['Scale'].default_value=0.9; L.new(rnd.outputs['Vector'],rnd2.inputs[0])
dir1=N.new('ShaderNodeVectorMath'); dir1.operation='ADD'; dir1.inputs[1].default_value=(0.0,-0.35,1.6); L.new(nrm.outputs['Vector'],dir1.inputs[0])
dir2=N.new('ShaderNodeVectorMath'); dir2.operation='ADD'; L.new(dir1.outputs['Vector'],dir2.inputs[0]); L.new(rnd2.outputs['Vector'],dir2.inputs[1])
off=N.new('ShaderNodeVectorMath'); off.operation='SCALE'; L.new(dir2.outputs['Vector'],off.inputs[0]); L.new(tp.outputs['Value'],off.inputs['Scale'])
offs=N.new('ShaderNodeVectorMath'); offs.operation='SCALE'; offs.inputs['Scale'].default_value=0.95; L.new(off.outputs['Vector'],offs.inputs[0])
# Rotation der Bruchstücke um die Zellmitte
ax=N.new('ShaderNodeVectorMath'); ax.operation='NORMALIZE'; L.new(rnd.outputs['Vector'],ax.inputs[0])
angm=N.new('ShaderNodeMath'); angm.operation='MULTIPLY'; angm.inputs[1].default_value=2.2; L.new(tc_.outputs['Value'],angm.inputs[0])
rel=N.new('ShaderNodeVectorMath'); rel.operation='SUBTRACT'; L.new(pos.outputs['Position'],rel.inputs[0]); L.new(vor.outputs['Position'],rel.inputs[1])
rot=N.new('FunctionNodeRotateVector') if hasattr(bpy.types,'FunctionNodeRotateVector') else None
if rot:
    ar=N.new('FunctionNodeAxisAngleToRotation'); L.new(ax.outputs['Vector'],ar.inputs['Axis']); L.new(angm.outputs['Value'],ar.inputs['Angle'])
    L.new(rel.outputs['Vector'],rot.inputs['Vector']); L.new(ar.outputs['Rotation'],rot.inputs['Rotation'])
    back=N.new('ShaderNodeVectorMath'); back.operation='ADD'; L.new(rot.outputs['Vector'],back.inputs[0]); L.new(vor.outputs['Position'],back.inputs[1])
    newpos=N.new('ShaderNodeVectorMath'); newpos.operation='ADD'; L.new(back.outputs['Vector'],newpos.inputs[0]); L.new(offs.outputs['Vector'],newpos.inputs[1])
else:
    newpos=N.new('ShaderNodeVectorMath'); newpos.operation='ADD'; L.new(pos.outputs['Position'],newpos.inputs[0]); L.new(offs.outputs['Vector'],newpos.inputs[1])
sel=N.new('FunctionNodeCompare'); sel.data_type='FLOAT'; sel.operation='GREATER_THAN'; sel.inputs['B'].default_value=0.0; L.new(tc_.outputs['Value'],sel.inputs['A'])
spl=N.new('GeometryNodeSplitEdges'); L.new(gi.outputs['Geometry'],spl.inputs['Mesh'])
sp=N.new('GeometryNodeSetPosition'); L.new(spl.outputs['Mesh'],sp.inputs['Geometry']); L.new(sel.outputs['Result'],sp.inputs['Selection']); L.new(newpos.outputs['Vector'],sp.inputs['Position'])
# weit geflogene Stücke löschen
far=N.new('FunctionNodeCompare'); far.data_type='FLOAT'; far.operation='GREATER_THAN'; far.inputs['B'].default_value=1.15; L.new(tc_.outputs['Value'],far.inputs['A'])
dl=N.new('GeometryNodeDeleteGeometry'); dl.domain='FACE'; L.new(sp.outputs['Geometry'],dl.inputs['Geometry']); L.new(far.outputs['Result'],dl.inputs['Selection']); L.new(dl.outputs['Geometry'],go.inputs['Geometry'])
gm=fox.modifiers.new('Hole','NODES'); gm.node_group=ng
rid=next(it.identifier for it in I.items_tree if getattr(it,'in_out','')=='INPUT' and it.name=='Radius'); cid=next(it.identifier for it in I.items_tree if getattr(it,'in_out','')=='INPUT' and it.name=='Center')
oc=old.modifiers['Hole']; 
gm[cid]=(EX,0.0,ZF)
for f,r in [(1,0.0),(26,0.0),(60,0.22),(100,0.55),(135,0.95),(158,1.5),(170,2.4)]:
    gm[rid]=r; gm.keyframe_insert(data_path='["%s"]'%rid,frame=f)
for fc in fox.animation_data.action.fcurves:
    for kp in fc.keyframe_points: kp.interpolation='LINEAR'
cam=bpy.data.objects['FoxCam']; s.frame_set(1)
loc=cam.matrix_world.to_translation().copy(); rot=cam.matrix_world.to_euler().copy()
cam.animation_data_clear(); cam.location=loc; cam.rotation_euler=rot
for c in cam.constraints: c.mute=True
cam.data.shift_y=-0.02; cam.data.lens=32
for o in s.objects:
    if o.type=='MESH': o.hide_render=(o is not fox)
s.frame_start=1; s.frame_end=170
s.render.film_transparent=True; s.render.resolution_x=1920; s.render.resolution_y=1080; s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG'; s.render.image_settings.color_mode='RGBA'; s.render.image_settings.compression=40
s.eevee.taa_render_samples=32
s.render.filepath=r'/Users/L5/Claude/cowork/BERNVAPES/Web/assets/fox_seq_lp/'+'f_'; bpy.ops.render.render(animation=True)
