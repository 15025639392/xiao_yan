# 角色参数规格书：Xiaoyan Character Spec v1.0

## 一、全局基准系

```
坐标系：Y轴向上，角色面朝+Z方向，右侧为+X
单位：米（Blender默认）
总身高：1.60m（从脚底到头顶，不含发型蓬松度）
头身比：1:7.3（ anime风格，偏Q版写实之间）
```

---

## 二、身体比例参数

| 参数名 | 数值 | 占比（相对身高） | 测量说明 |
|--------|------|-----------------|----------|
| `total_height` | 1.600 | 100% | 脚底→头顶 |
| `head_height` | 0.220 | 13.75% | 下巴→头顶（不含头发厚度） |
| `head_width` | 0.145 | 9.06% | 两耳外侧距离 |
| `head_depth` | 0.155 | 9.69% | 鼻尖→后脑勺 |
| `neck_height` | 0.045 | 2.81% | 下巴→锁骨 |
| `neck_width` | 0.055 | 3.44% | 颈部最细处 |
| `shoulder_width` | 0.320 | 20.00% | 两肩峰外侧距离 |
| `shoulder_height` | 1.380 | 86.25% | 脚底→肩峰 |
| `torso_height` | 0.380 | 23.75% | 锁骨→胯骨 |
| `chest_width` | 0.260 | 16.25% | 腋窝水平围宽 |
| `waist_width` | 0.210 | 13.13% | 最细处 |
| `hip_width` | 0.245 | 15.31% | 胯骨外侧 |
| `arm_length` | 0.520 | 32.50% | 肩峰→手腕 |
| `upper_arm` | 0.220 | 13.75% | 肩峰→肘 |
| `forearm` | 0.200 | 12.50% | 肘→手腕 |
| `hand_length` | 0.100 | 6.25% | 手腕→中指指尖 |
| `leg_length` | 0.750 | 46.88% | 胯骨→脚底 |
| `thigh` | 0.380 | 23.75% | 胯骨→膝盖 |
| `calf` | 0.370 | 23.13% | 膝盖→脚踝 |
| `foot_length` | 0.210 | 13.13% | 拖鞋长度 |

---

## 三、头部详细参数

### 3.1 面部轮廓

| 参数 | 数值 | 备注 |
|------|------|------|
| `face_shape` | 圆润鹅蛋偏圆 | 下颌角不明显 |
| `face_width` | 0.130 | 颧骨处 |
| `face_height` | 0.155 | 发际线→下巴 |
| `forehead_height` | 0.055 | 占脸高35.5% |
| `eye_to_chin` | 0.075 | 占脸高48.4% |
| `chin_roundness` | 0.85 | 0-1，越接近1越圆 |
| `cheek_fullness` | 0.70 | 苹果肌饱满度 |

### 3.2 眼睛（核心识别特征）

| 参数 | 数值 | 备注 |
|------|------|------|
| `eye_size` | 0.042 | 眼睛高度（睁眼） |
| `eye_width` | 0.055 | 眼睛宽度 |
| `eye_spacing` | 0.058 | 两眼内眼角间距 |
| `eye_height_pos` | 0.525 | 眼睛中心相对脸高的位置（从下巴算） |
| `eye_tilt` | +5° | 外眼角略高于内眼角 |
| `iris_diameter` | 0.035 | 虹膜直径 |
| `pupil_diameter` | 0.022 | 瞳孔直径 |
| `iris_color` | [0.42, 0.32, 0.62] | RGB，淡紫灰色 |
| `pupil_color` | [0.08, 0.06, 0.12] | 深紫近黑 |
| `highlight_size` | 0.012 | 高光点直径 |
| `highlight_pos` | [0.008, 0.008] | 相对瞳孔中心偏移（右上） |
| `eyelash_length` | 0.008 | 上睫毛 |
| `eyelash_density` | 0.6 | 0-1 |
| `eyebrow_height` | 0.015 | 眉毛粗细 |
| `eyebrow_arc` | 0.012 | 眉弓弧度 |
| `eyebrow_color` | [0.55, 0.40, 0.65] | 比发色略深 |

### 3.3 眼镜（关键配饰）

| 参数 | 数值 | 备注 |
|------|------|------|
| `glasses_type` | 圆框金属细框 | 正圆形 |
| `frame_diameter` | 0.048 | 单镜片外径 |
| `frame_thickness` | 0.0025 | 金属丝粗细 |
| `bridge_width` | 0.012 | 鼻梁架宽度 |
| `bridge_height` | 0.008 | 鼻梁架从镜片顶部下降 |
| `temple_length` | 0.090 | 镜腿长度 |
| `frame_color` | [0.12, 0.10, 0.10] | 深棕/黑金属色 |
| `lens_radius` | 0.022 | 镜片半径 |
| `lens_thickness` | 0.003 | 镜片边缘厚度 |
| `lens_transparency` | 0.75 | 透明度 |
| `lens_refraction` | 1.52 | 折射率（普通树脂） |
| `lens_tint` | [0.95, 0.95, 1.0] | 极淡蓝白 |

### 3.4 鼻子

| 参数 | 数值 | 备注 |
|------|------|------|
| `nose_length` | 0.025 | 鼻梁长度 |
| `nose_width` | 0.018 | 鼻尖宽度 |
| `nose_height` | 0.012 | 鼻尖突起高度 |
| `nose_tip_roundness` | 0.9 | 非常圆润 |
| `nostril_visibility` | 0.1 | 几乎不可见（anime风格） |

### 3.5 嘴巴

| 参数 | 数值 | 备注 |
|------|------|------|
| `mouth_width` | 0.025 | 嘴角间距 |
| `mouth_height` | 0.008 | 闭合时厚度 |
| `lip_thickness` | 0.005 | 上下唇合计 |
| `lip_color` | [0.85, 0.55, 0.55] | 淡粉 |
| `mouth_curve` | +0.003 | 微微上扬 |
| `mouth_position` | 0.180 | 从下巴向上的位置 |

### 3.6 耳朵

| 参数 | 数值 | 备注 |
|------|------|------|
| `ear_height` | 0.038 | 耳朵总高 |
| `ear_width` | 0.018 | 耳朵宽度 |
| `ear_protrusion` | 0.012 | 耳朵从头部突出 |
| `ear_position` | 0.520 | 耳朵中心相对头高 |
| `ear_lobe_attached` | true | 耳垂贴面 |

---

## 四、发型详细参数

### 4.1 主发色与材质

| 参数 | 数值 | 备注 |
|------|------|------|
| `hair_base_color` | [0.72, 0.56, 0.86] | 主色：淡薰衣草紫 |
| `hair_highlight_color` | [0.82, 0.72, 0.92] | 高光：亮紫 |
| `hair_shadow_color` | [0.58, 0.42, 0.72] | 阴影：深紫 |
| `hair_specular` | [0.80, 0.70, 0.90] | 高光反射色 |
| `hair_roughness` | 0.25 | 光泽度 |
| `hair_anisotropy` | 0.6 | 各向异性（发丝光泽方向） |

### 4.2 头顶/刘海区域

| 参数 | 数值 | 备注 |
|------|------|------|
| `hair_top_volume` | 0.085 | 头顶蓬松高度（从头皮） |
| `hair_top_width` | 0.160 | 头顶发宽 |
| `bangs_style` | 中分偏侧刘海 | 向两侧分开 |
| `bangs_length` | 0.095 | 刘海到眉毛下方 |
| `bangs_curve` | -0.015 | 向内微弯 |
| `bangs_strand_count` | 6 | 主要发束数 |
| `side_hair_length` | 0.120 | 两侧鬓角长度 |
| `side_hair_volume` | 0.040 | 两侧蓬松度 |

### 4.3 后发/颈部区域

| 参数 | 数值 | 备注 |
|------|------|------|
| `back_hair_length` | 0.180 | 后颈发际线→发尾 |
| `back_hair_width` | 0.140 | 后发宽度 |
| `neck_hairline` | 0.035 | 后颈发际线高度 |
| `hair_texture` | soft_wave | 柔软波浪 |

### 4.4 麻花辫（核心特征）

**左侧麻花辫：**

| 参数 | 数值 | 备注 |
|------|------|------|
| `braid_L_start_pos` | [-0.075, 0.020, 0.050] | 相对头部中心，左耳后下方 |
| `braid_L_length` | 0.380 | 总长度 |
| `braid_L_thickness` | 0.022 | 辫子粗细 |
| `braid_L_thickness_taper` | 0.65 | 末端变细至65% |
| `braid_L_segments` | 8 | 麻花交叉数 |
| `braid_L_cross_angle` | 45° | 每股交叉角度 |
| `braid_L_gravity_curve` | 0.12 | 自然下垂弧度 |
| `braid_L_swing` | 0.025 | 末端向外摆动 |
| `braid_L_hair_tie_pos` | 0.320 | 从起点算，绑发带位置 |
| `braid_L_hair_tie_color` | [0.60, 0.45, 0.75] | 同色系发带 |
| `braid_L_hair_tie_width` | 0.008 | 发带宽度 |

**右侧麻花辫：**（镜像，X轴取反）

| 参数 | 数值 | 备注 |
|------|------|------|
| `braid_R_start_pos` | [0.075, 0.020, 0.050] | 右耳后下方 |
| `braid_R_length` | 0.380 | 同左 |
| `braid_R_thickness` | 0.022 | 同左 |
| ... | ... | 其余参数镜像 |

**发尾细节：**

| 参数 | 数值 | 备注 |
|------|------|------|
| `braid_tip_style` | 松散散开 | 末端不绑紧 |
| `braid_tip_fluff` | 0.015 | 发尾蓬松半径 |
| `braid_tip_strands` | 12 | 散开的发丝数 |

---

## 五、服装详细参数

### 5.1 外层长袍（和服式）

| 参数 | 数值 | 备注 |
|------|------|------|
| `robe_type` | 交领右衽长袍 | 日式/中式混合 |
| `robe_main_color` | [0.96, 0.96, 0.96] | 本白，非纯白 |
| `robe_length` | 0.880 | 领口→下摆 |
| `robe_hem_from_ground` | 0.180 | 下摆离地高度 |
| `robe_shoulder_drop` | 0.080 | 落肩量 |
| `robe_sleeve_type` | 宽袖直筒 | 和服袖型 |
| `robe_sleeve_length` | 0.480 | 肩缝→袖口 |
| `robe_sleeve_opening_width` | 0.280 | 袖口宽度 |
| `robe_sleeve_seam_height` | 0.320 | 腋下开口高度 |
| `robe_body_width` | 0.380 | 平铺身宽 |
| `robe_collar_width` | 0.040 | 领子宽度 |
| `robe_collar_overlap` | 0.060 | 右衽重叠量 |
| `robe_collar_angle` | 55° | 领口V字角度 |
| `robe_fabric_thickness` | 0.008 | 布料厚度 |
| `robe_fabric_roughness` | 0.85 | 棉麻质感 |
| `robe_fold_count` | 5 | 主要衣褶数 |

### 5.2 腰带/系带

| 参数 | 数值 | 备注 |
|------|------|------|
| `obi_type` | 侧腰蝴蝶结 | 简化版 |
| `obi_position` | [-0.080, 0.000, 0.280] | 左腰前方 |
| `obi_main_width` | 0.060 | 腰带主体宽 |
| `obi_knot_width` | 0.090 | 蝴蝶结展开宽 |
| `obi_knot_height` | 0.070 | 蝴蝶结高 |
| `obi_knot_thickness` | 0.025 | 蝴蝶结厚度 |
| `obi_knot_loops` | 2 | 蝴蝶结两翼 |
| `obi_knot_tail_length` | 0.120 | 下垂飘带 |
| `obi_color` | [0.94, 0.94, 0.94] | 同袍色，略深 |
| `obi_fabric` | 同袍料 | 无特殊 |

### 5.3 内衬/袖口

| 参数 | 数值 | 备注 |
|------|------|------|
| `cuff_visible` | true | 袖口露出 |
| `cuff_visible_length` | 0.065 | 露出长度 |
| `cuff_color` | [0.06, 0.06, 0.06] | 近黑色 |
| `cuff_fabric` | 光滑内衬 | 与外袍对比 |

### 5.4 裤子

| 参数 | 数值 | 备注 |
|------|------|------|
| `pants_type` | 阔腿九分裤 | |
| `pants_color` | [0.95, 0.95, 0.95] | 本白 |
| `pants_waist_height` | 0.380 | 裤腰位置（从脚底） |
| `pants_length` | 0.520 | 裤腰→裤脚 |
| `pants_hem_height` | 0.180 | 裤脚离地 |
| `pants_leg_width` | 0.190 | 单腿宽度（平铺） |
| `pants_cuff_width` | 0.025 | 裤脚卷边 |
| `pants_fabric` | 棉麻 | 同外袍 |
| `pants_fold_depth` | 0.015 | 裤褶深度 |

### 5.5 拖鞋

| 参数 | 数值 | 备注 |
|------|------|------|
| `slipper_type` | 包脚布拖鞋 | 日式/居家 |
| `slipper_color` | [0.93, 0.93, 0.93] | 本白 |
| `slipper_length` | 0.210 | 鞋长 |
| `slipper_width` | 0.085 | 鞋宽 |
| `slipper_sole_thickness` | 0.018 | 鞋底厚 |
| `slipper_upper_height` | 0.025 | 鞋面高度 |
| `slipper_toe_roundness` | 0.9 | 圆头 |
| `slipper_heel_open` | true | 露跟 |
| `slipper_insole_color` | [0.90, 0.90, 0.90] | 略深 |

---

## 六、手部详细参数

| 参数 | 数值 | 备注 |
|------|------|------|
| `hand_palm_width` | 0.045 | 手掌宽 |
| `hand_palm_length` | 0.055 | 手掌长（腕→指根） |
| `finger_length_ratio` | [1.0, 0.85, 0.75, 0.65, 0.50] | 食/中/无/小/拇指 |
| `finger_thickness` | 0.012 | 指根粗 |
| `finger_taper` | 0.6 | 指尖变细 |
| `nail_length` | 0.003 | 指甲露出 |
| `nail_color` | [0.85, 0.75, 0.75] | 淡粉 |
| `thumb_angle` | 45° | 外展角度 |

---

## 七、姿态参数（T-Pose标准）

| 参数 | 数值 | 备注 |
|------|------|------|
| `pose_type` | A-Pose（微张） | 非严格T-Pose |
| `arm_angle` | 15° | 手臂与躯干夹角 |
| `elbow_rotation` | 0° | 前臂无旋转 |
| `palm_facing` | 45° | 掌心略向前 |
| `finger_pose` | 自然微曲 | 非握拳非伸直 |
| `leg_separation` | 0.080 | 双脚间距 |
| `foot_angle` | 15° | 外八角度 |
| `spine_curve` | 0.02 | 自然S曲线 |
| `shoulder_relax` | 0.015 | 下沉量 |

---

## 八、材质与渲染参数

### 8.1 皮肤

| 参数 | 数值 | 备注 |
|------|------|------|
| `skin_base` | [1.00, 0.88, 0.82] | 暖白 |
| `skin_subsurface` | 0.35 | 次表面散射 |
| `skin_subsurface_radius` | [0.015, 0.005, 0.003] | RGB散射半径 |
| `skin_roughness` | 0.55 | |
| `skin_specular` | 0.3 | |
| `skin_normal_detail` | 0.2 | 细微毛孔 |

### 8.2 头发（专用Shader）

| 参数 | 数值 | 备注 |
|------|------|------|
| `hair_shader` | anime_hair_anisotropic | |
| `hair_base` | [0.72, 0.56, 0.86] | |
| `hair_highlight1` | [0.85, 0.75, 0.95] | 主高光 |
| `hair_highlight2` | [0.65, 0.48, 0.78] | 次高光 |
| `hair_highlight_shift` | 0.15 | 高光偏移 |
| `hair_specular_power` | 128 | 锐利高光 |
| `hair_rim_light` | [0.90, 0.85, 0.95] | 边缘光 |

### 8.3 服装

| 参数 | 数值 | 备注 |
|------|------|------|
| `cloth_shader` | diffuse_fabric | |
| `cloth_roughness` | 0.80 | 棉麻 |
| `cloth_sheen` | 0.15 | 微弱丝光 |
| `cloth_normal_weave` | 0.05 | 织物纹理 |

---

## 九、评分标准（模型还原度测试）

| 检查项 | 权重 | 合格标准 | 测量方法 |
|--------|------|---------|---------|
| 总身高比例 | 5% | ±2% |  bounding box |
| 头身比 | 10% | ±5% | 头高/身高 |
| 发型颜色 | 10% | ΔE<5 | 色度计 |
| 麻花辫形态 | 15% | 位置/长度/节数一致 | 目视+尺寸 |
| 眼镜形状 | 10% | 圆度/尺寸±3% | 轮廓对比 |
| 服装比例 | 15% | 袖长/衣长/裤长±5% | 尺寸测量 |
| 交领右衽 | 5% | 结构正确 | 拓扑检查 |
| 袖口内衬露出 | 5% | 长度/颜色一致 | 目视 |
| 拖鞋形态 | 5% | 类型正确 | 目视 |
| 整体配色 | 10% | 主色ΔE<5 | 色度计 |
| 风格一致性 | 10% | anime/卡通渲染 | 目视 |

---

## 十、JSON格式（可直接使用）

```json
{
  "spec_version": "1.0.0",
  "character_name": "xiaoyan",
  "reference_image": "three_view_turnaround.png",
  "unit": "meter",
  "global": {
    "total_height": 1.6,
    "head_to_body_ratio": 7.3,
    "coordinate_system": "Y_up_Z_front"
  },
  "head": {
    "proportions": {
      "height": 0.22,
      "width": 0.145,
      "depth": 0.155
    },
    "eyes": {
      "size": [0.055, 0.042],
      "spacing": 0.058,
      "height_pos": 0.525,
      "tilt": 5,
      "iris_color": [0.42, 0.32, 0.62],
      "pupil_size_ratio": 0.63,
      "highlight": {"size": 0.012, "offset": [0.008, 0.008]}
    },
    "glasses": {
      "type": "round_metal_thin",
      "diameter": 0.048,
      "frame_thickness": 0.0025,
      "bridge_width": 0.012,
      "color": [0.12, 0.10, 0.10],
      "lens_transparency": 0.75
    },
    "nose": {"length": 0.025, "width": 0.018, "tip_roundness": 0.9},
    "mouth": {"width": 0.025, "height": 0.008, "curve": 0.003},
    "ears": {"height": 0.038, "width": 0.018, "protrusion": 0.012}
  },
  "hair": {
    "base_color": [0.72, 0.56, 0.86],
    "top_volume": 0.085,
    "bangs": {"style": "parted_side", "length": 0.095, "strands": 6},
    "braids": {
      "count": 2,
      "symmetry": "mirror_x",
      "length": 0.38,
      "thickness": 0.022,
      "segments": 8,
      "cross_angle": 45,
      "gravity_curve": 0.12,
      "hair_tie": {"position_ratio": 0.84, "width": 0.008}
    }
  },
  "body": {
    "proportions": {
      "shoulder_width": 0.32,
      "torso_height": 0.38,
      "waist_width": 0.21,
      "hip_width": 0.245,
      "arm_length": 0.52,
      "leg_length": 0.75
    }
  },
  "clothing": {
    "outer_robe": {
      "type": "cross_collar_kimono",
      "color": [0.96, 0.96, 0.96],
      "length": 0.88,
      "sleeve": {"length": 0.48, "opening_width": 0.28},
      "collar": {"width": 0.04, "overlap": 0.06, "angle": 55}
    },
    "obi": {
      "type": "side_bow",
      "position": [-0.08, 0.0, 0.28],
      "knot": {"width": 0.09, "height": 0.07, "loops": 2}
    },
    "inner_cuff": {"visible_length": 0.065, "color": [0.06, 0.06, 0.06]},
    "pants": {
      "type": "wide_cropped",
      "length": 0.52,
      "leg_width": 0.19,
      "hem_height": 0.18
    },
    "slippers": {
      "length": 0.21,
      "width": 0.085,
      "sole_thickness": 0.018,
      "heel_open": true
    }
  },
  "materials": {
    "skin": {"base": [1.0, 0.88, 0.82], "subsurface": 0.35, "roughness": 0.55},
    "hair": {"base": [0.72, 0.56, 0.86], "specular": [0.8, 0.7, 0.9], "roughness": 0.25},
    "cloth": {"roughness": 0.8, "sheen": 0.15}
  },
  "pose": {
    "type": "A_pose_relaxed",
    "arm_angle": 15,
    "leg_separation": 0.08,
    "foot_angle": 15
  },
  "scoring": {
    "total_items": 11,
    "pass_threshold": 0.75
  }
}
```

---

## 使用说明

这份参数文档可直接用于：

1. **程序化生成**（Blender/Maya/Houdini脚本）
2. **AI模型评估**（对比生成结果与参考图）
3. **3D重建质量检测**（点云/网格 vs 参数约束）

---

*文档版本: 1.0.0*  
*生成日期: 2026-04-25*  
*对应参考图: three_view_turnaround.png*
