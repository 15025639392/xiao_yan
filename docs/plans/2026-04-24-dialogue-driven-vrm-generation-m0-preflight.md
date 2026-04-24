# 对话驱动 VRM 生成 M0 技术预研记录

## 1. 预研目标

确认 MVP 前置条件是否具备：

- 本机是否可调用 Blender。
- 是否已有可用 VRM 或基础模型资产。
- 是否已有 VRM 导出插件或可脚本化导出路径。
- 是否存在可复用的前端 VRM 预览能力。

## 2. 本机检查结论

| 项目 | 结果 | 证据 | 结论 |
| --- | --- | --- | --- |
| Blender 命令 | 可用 | `/Applications/Blender.app/Contents/MacOS/Blender --version` 返回 Blender 4.5.0 | 可执行后台脚本 |
| macOS Blender App | 已安装 | `/Applications/Blender.app` | 可作为本地外部执行器 |
| 现有 VRM 资产 | 存在 | `apps/desktop/public/avatar/xiaoyan.vrm`，233K | 可作为预览 spike 资产，不宜作为最终模板 |
| VRM 资产格式 | VRM 0.x | glTF binary，`extensionsUsed` 包含 `VRM` | 可用于前端加载验证 |
| Humanoid 骨骼 | 存在 | VRM0 humanoid bones 数量为 43 | 可作为加载/渲染验证样本 |
| 前端预览依赖 | 存在 | `@pixiv/three-vrm` 与 `three` 已在 `apps/desktop/package.json` | 前端已有预览基础 |
| VRM 导出插件 | 已安装并验证 | VRM Add-on for Blender v3.26.7，`import_scene.vrm` 与 `export_scene.vrm` 均存在 | 可执行 VRM 导入导出 |

## 3. 现有资产说明

当前仓库已有临时 VRM：

- 路径：`apps/desktop/public/avatar/xiaoyan.vrm`
- 来源说明：`apps/desktop/public/avatar/README.md`
- 当前用途：前端 VRM 外显 spike 资产
- 资产风险：README 已标注需要确认本地桌面使用和再分发授权
- 建议：只作为加载和预览样本，不作为小晏正式形象或生成模板

解析结果摘要：

```json
{
  "format": "glTF binary 2.0",
  "extensionsUsed": ["KHR_materials_unlit", "KHR_texture_transform", "VRM"],
  "hasVRM0": true,
  "hasVRMCVRM": false,
  "nodeCount": 74,
  "meshCount": 1,
  "materialCount": 1,
  "skinCount": 1,
  "humanoidBones": 43
}
```

## 4. 官方工具链确认

- Blender 支持命令行后台模式和执行 Python 脚本，可作为本地外部执行器调用。
- VRM Add-on for Blender 官方提供 Blender 内 VRM 导入、编辑和导出能力，并公开脚本 API。
- 官方脚本 API 包含 `bpy.ops.export_scene.vrm(filepath=...)`，适合后续封装自动导出脚本。
- 当前预研已在本机完成导入再导出烟测。

参考链接：

- [Blender Command Line Arguments](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)
- [VRM Add-on for Blender](https://vrm-addon-for-blender.info/en-us/)
- [VRM Add-on Scripting API](https://vrm-addon-for-blender.info/en-us/scripting-api/)

## 5. 推荐最小导出命令

已验证的独立命令：

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python-exit-code 1 \
  --python services/core/scripts/vrm_generation/roundtrip_vrm.py \
  -- \
  --input apps/desktop/public/avatar/xiaoyan.vrm \
  --spec services/core/scripts/vrm_generation/character_spec.example.json \
  --output /tmp/xiaoyan-vrm-tools/xiaoyan-script-roundtrip.vrm
```

脚本内已验证调用形态：

```python
bpy.ops.import_scene.vrm(filepath=input_path)
bpy.ops.export_scene.vrm(filepath=output_path)
```

烟测结果：

- 输出文件：`/tmp/xiaoyan-vrm-tools/xiaoyan-script-roundtrip.vrm`
- 输出大小：227K
- Blender 版本：4.5.0
- VRM Add-on 版本：3.26.7

## 6. M0 结论

- M0 已通过工具链烟测：Blender、VRM Add-on、VRM 导入导出均可用。
- 可继续做的部分：角色规格 schema、任务状态设计、后端降级逻辑、生成任务 API。
- 不应继续做的部分：宣称已支持高质量自动建模，或把临时 spike 资产当作小晏正式模板。
- 推荐下一步：准备可编辑基础 `.blend` 模板，并进入 M1 后端任务闭环设计与实现。

## 7. 后续实现边界

- Blender 路径应通过配置项传入，例如 `VRM_BLENDER_PATH`。
- 未配置或不可执行时，API 应返回能力不可用，而不是阻止服务启动。
- 生成产物目录应固定在受控路径，例如 `services/core/.data/vrm_generation/`。
- 现有 `apps/desktop/public/avatar/xiaoyan.vrm` 只能作为 spike 预览资产。
