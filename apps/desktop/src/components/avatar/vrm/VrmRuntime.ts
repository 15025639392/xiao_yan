import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";

import type { AvatarRenderState } from "../avatarTypes";

type RuntimeOptions = {
  container: HTMLElement;
  modelUrl: string;
  onError?: (message: string) => void;
};

const EXPRESSION_PRESETS = ["happy", "sad", "angry", "relaxed", "surprised"];

export class VrmRuntime {
  private readonly container: HTMLElement;
  private readonly modelUrl: string;
  private readonly onError?: (message: string) => void;
  private readonly clock = new THREE.Clock();
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(25, 1, 0.1, 20);
  private readonly renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  private frameId: number | null = null;
  private vrm: VRM | null = null;
  private disposed = false;
  private currentState: AvatarRenderState | null = null;

  constructor({ container, modelUrl, onError }: RuntimeOptions) {
    this.container = container;
    this.modelUrl = modelUrl;
    this.onError = onError;
  }

  async start(): Promise<void> {
    this.setupScene();
    await this.loadModel();
    this.resize();
    this.renderLoop();
  }

  applyState(nextState: AvatarRenderState): void {
    this.currentState = nextState;
    this.applyExpression(nextState);
  }

  resize(): void {
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  dispose(): void {
    this.disposed = true;
    if (this.frameId != null) {
      window.cancelAnimationFrame(this.frameId);
      this.frameId = null;
    }
    this.container.removeChild(this.renderer.domElement);
    if (this.vrm) {
      this.scene.remove(this.vrm.scene);
      VRMUtils.deepDispose(this.vrm.scene);
      this.vrm = null;
    }
    this.renderer.dispose();
  }

  private setupScene(): void {
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.container.appendChild(this.renderer.domElement);
    this.camera.position.set(0, 1.25, 3.2);

    const light = new THREE.DirectionalLight(0xffffff, 1.8);
    light.position.set(1, 2, 3);
    this.scene.add(light);
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.4));
  }

  private async loadModel(): Promise<void> {
    try {
      const loader = new GLTFLoader();
      loader.register((parser) => new VRMLoaderPlugin(parser));
      const gltf = await loader.loadAsync(this.modelUrl);
      if (this.disposed) return;

      const vrm = gltf.userData.vrm as VRM | undefined;
      if (!vrm) {
        throw new Error("未能从模型中读取 VRM 数据");
      }

      VRMUtils.removeUnnecessaryVertices(gltf.scene);
      VRMUtils.removeUnnecessaryJoints(gltf.scene);
      VRMUtils.rotateVRM0(vrm);
      vrm.scene.position.set(0, -0.9, 0);
      this.vrm = vrm;
      this.scene.add(vrm.scene);
      if (this.currentState) {
        this.applyExpression(this.currentState);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "VRM 模型加载失败";
      this.onError?.(message);
    }
  }

  private renderLoop = (): void => {
    if (this.disposed) return;

    this.frameId = window.requestAnimationFrame(this.renderLoop);
    const delta = this.clock.getDelta();
    this.applyMotion(delta);
    this.vrm?.update(delta);
    this.renderer.render(this.scene, this.camera);
  };

  private applyExpression(state: AvatarRenderState): void {
    const manager = this.vrm?.expressionManager;
    if (!manager) return;

    for (const preset of EXPRESSION_PRESETS) {
      manager.setValue(preset, 0);
    }
    if (state.expression !== "neutral") {
      manager.setValue(state.expression, state.expressionWeight);
    }
  }

  private applyMotion(delta: number): void {
    if (!this.vrm || !this.currentState) return;

    const root = this.vrm.scene;
    const energy = this.currentState.motionEnergy;
    const time = this.clock.elapsedTime;
    const breathing = Math.sin(time * (1.2 + energy)) * 0.015 * energy;
    root.position.y = -0.9 + breathing;
    root.rotation.y = Math.sin(time * 0.45) * 0.05 * energy;

    if (this.currentState.motion === "sleeping") {
      root.rotation.x = THREE.MathUtils.lerp(root.rotation.x, 0.08, delta * 3);
    } else if (this.currentState.motion === "thinking") {
      root.rotation.x = THREE.MathUtils.lerp(root.rotation.x, -0.03, delta * 3);
    } else {
      root.rotation.x = THREE.MathUtils.lerp(root.rotation.x, 0, delta * 3);
    }
  }
}
