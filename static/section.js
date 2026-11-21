// 断面（切断面）を描く。ビューアーと図鑑で共通に使う。
//
// 1 枚の平面でモデルを切り、手前（カメラ側）を消して、切り口をハッチング（斜線）で塗る。
// 切り口はステンシルで求める：部品ごとに、裏の面で +1、表の面で -1 を数え、0 でない所が「部品の中」。
// そこに平面を描けば、その部品の切り口になる（部品のメッシュが閉じていること）。
import * as THREE from 'three';

const VS = `
#include <common>
#include <clipping_planes_pars_vertex>
void main() {
  #include <begin_vertex>
  #include <project_vertex>
  #include <clipping_planes_vertex>
}`;
// gl_FragCoord で斜線を引くので、拡大しても線の間隔は画面の上で一定
const FS = `
uniform vec3 color; uniform vec3 ink; uniform float angle; uniform float spacing; uniform float width;
void main() {
  float d = gl_FragCoord.x * cos(angle) + gl_FragCoord.y * sin(angle);
  float l = step(fract(d / spacing), width / spacing);
  gl_FragColor = vec4(mix(color, ink, l), 1.0);
}`;

const STENCIL_COUNT = { depthWrite: false, depthTest: false, colorWrite: false, stencilWrite: true, stencilFunc: THREE.AlwaysStencilFunc };
const STENCIL_CAP = { stencilWrite: true, stencilRef: 0, stencilFunc: THREE.NotEqualStencilFunc,
                      stencilFail: THREE.ReplaceStencilOp, stencilZFail: THREE.ReplaceStencilOp, stencilZPass: THREE.ReplaceStencilOp };

export class Section {
  /** scene に断面の部品（数えるための複製と、切り口の板）を置く */
  constructor(scene) {
    this.scene = scene;
    this.plane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
    this.planes = [this.plane];
    this.group = new THREE.Group();
    this.group.visible = false;
    scene.add(this.group);
    this.caps = [];
    this.active = false;
    this.size = 1;
    this.center = new THREE.Vector3();
    const inc = THREE.IncrementWrapStencilOp, dec = THREE.DecrementWrapStencilOp;
    this.backMat = new THREE.MeshBasicMaterial({ ...STENCIL_COUNT, side: THREE.BackSide, clippingPlanes: this.planes,
                                                 stencilFail: inc, stencilZFail: inc, stencilZPass: inc });
    this.frontMat = new THREE.MeshBasicMaterial({ ...STENCIL_COUNT, side: THREE.FrontSide, clippingPlanes: this.planes,
                                                  stencilFail: dec, stencilZFail: dec, stencilZPass: dec });
  }

  /** 切り口の材質（ハッチング）。index ごとに斜線の向きを 45° / 135° で交互にし、となりの部品と見分ける */
  hatch(color, ink, index, spacing = 7) {
    return new THREE.ShaderMaterial({
      ...STENCIL_CAP, side: THREE.DoubleSide,
      uniforms: { color: { value: new THREE.Color(color) }, ink: { value: new THREE.Color(ink) },
                  angle: { value: index % 2 ? Math.PI * 0.75 : Math.PI * 0.25 },
                  spacing: { value: spacing + (index % 3) }, width: { value: 1.3 } },
      vertexShader: VS, fragmentShader: FS,
    });
  }

  /** 図鑑の線画で、部品ごとの境目を取るための単色の材質（index を色にする） */
  idMaterial(index) {
    const c = new THREE.Color().setHex(((index + 1) * 2654435761) & 0xffffff);
    return new THREE.MeshBasicMaterial({ ...STENCIL_CAP, side: THREE.DoubleSide, color: c });
  }

  normalMaterial() {
    return new THREE.MeshNormalMaterial({ ...STENCIL_CAP, side: THREE.DoubleSide });
  }

  clear() {
    for (const c of this.caps) for (const m of Object.values(c.userData.mats)) m.dispose();
    this.group.clear();
    this.caps = [];
  }

  /** meshes を切る準備をする。style(mesh, index) は { color, ink } を返す */
  build(meshes, style) {
    this.clear();
    const box = new THREE.Box3();
    for (const m of meshes) box.expandByObject(m);
    if (box.isEmpty()) return;
    this.size = box.getSize(new THREE.Vector3()).length() || 1;
    box.getCenter(this.center);
    const capGeo = new THREE.PlaneGeometry(this.size * 3, this.size * 3);
    // 大きい部品から順に描く。中に入った小さな部品（ケースの中の歯車、ブロックの中のピストン）の切り口が上に重なる
    const vol = m => { const s = new THREE.Box3().setFromObject(m).getSize(new THREE.Vector3()); return s.x * s.y * s.z; };
    meshes = [...meshes].sort((a, b) => vol(b) - vol(a));
    meshes.forEach((m, i) => {
      m.updateWorldMatrix(true, false);
      const add = (obj, order) => {
        obj.matrixAutoUpdate = false;
        obj.matrix.copy(m.matrixWorld);
        obj.renderOrder = order;
        obj.userData.src = m;
        this.group.add(obj);
        return obj;
      };
      add(new THREE.Mesh(m.geometry, this.backMat), 10 + 3 * i);
      add(new THREE.Mesh(m.geometry, this.frontMat), 11 + 3 * i);
      const st = style(m, i);
      const mats = { hatch: this.hatch(st.color, st.ink, i), id: this.idMaterial(i), normal: this.normalMaterial() };
      const cap = new THREE.Mesh(capGeo, mats.hatch);
      cap.matrixAutoUpdate = false;
      cap.renderOrder = 12 + 3 * i;
      cap.userData = { src: m, mats };
      this.group.add(cap);
      this.caps.push(cap);
    });
    this.place();
  }

  /** 切る位置。axis（three.js の座標の単位ベクトル）の向きにある側を消し、pos は axis に沿った位置 */
  set(axis, pos) {
    const n = axis.clone().normalize().negate();
    this.plane.set(n, pos);            // n·p + pos = 0 → axis·p = pos
    this.place();
  }

  place() {
    const n = this.plane.normal;
    const p = this.plane.projectPoint(this.center, new THREE.Vector3()).addScaledVector(n, this.size * 2e-5);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), n);
    for (const c of this.caps) c.matrix.compose(p, q, new THREE.Vector3(1, 1, 1));
  }

  /** 切り口の塗り方を切り替える（"hatch" / "id" / "normal"） */
  mode(name) { for (const c of this.caps) c.material = c.userData.mats[name]; }

  /** 部品の表示・非表示を、数えるための複製と切り口にも反映する */
  sync(parentVisible = true) {
    this.group.visible = this.active && parentVisible;
    for (const o of this.group.children) o.visible = this.active && o.userData.src.visible;
  }

  /** 消した側（カメラ側）の点なら true（マウスで指した点を断面の手前で拾わないように） */
  removed(p) { return this.active && this.plane.distanceToPoint(p) < -this.size * 1e-6; }
}
