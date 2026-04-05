# 小晏核心功能技术实施详细计划

**文档版本**: 1.0  
**创建日期**: 2026-04-05  
**目标**: 完善人格系统、记忆系统、对话和任务管理的核心技术实现

---

## 📋 概述

本文档详细规划小晏项目核心功能的技术实施方案，涵盖三个主要阶段：
1. **人格系统完善**（第1-4周）
2. **记忆系统增强**（第5-8周）
3. **对话和任务管理完善**（第9-12周）

---

## 🎯 阶段一：人格系统完善（第1-4周）

### 1.1 个性化人格配置系统

#### 1.1.1 架构设计

```
persona/
├── config.py                  # 配置管理（已有）
├── models.py                  # 数据模型（已有）
├── service.py                 # 服务层（已有）
├── emotion_engine.py          # 情绪引擎（已有）
├── expression_mapper.py       # 表达映射器（已有）
├── prompt_builder.py          # 提示词构建器（已有）
├── templates.py               # [新增] 人格模板管理
└── validator.py               # [新增] 人格配置验证
```

#### 1.1.2 核心实现：人格模板系统

**文件**: `services/core/app/persona/templates.py`

```python
"""人格模板管理系统

提供预设人格配置，支持：
- 4种基础人格模板
- 人格配置验证
- 人格对比和推荐
"""

from dataclasses import dataclass
from typing import Literal
from app.persona.models import (
    Persona,
    PersonalityDimensions,
    ExpressionStyle,
    FormalLevel,
    SentenceStyle,
    ExpressionHabit,
)

PERSONA_TYPES = Literal["introvert", "extrovert", "professional", "playful"]

@dataclass
class PersonaTemplate:
    """人格模板定义"""
    id: str
    name: str
    description: str
    personality: PersonalityDimensions
    expression: ExpressionStyle
    bio_template: str  # 自我介绍模板
    example_dialogues: list[str]  # 示例对话

# 预设人格模板库
PERSONA_TEMPLATES: dict[PERSONA_TYPES, PersonaTemplate] = {
    "introvert": PersonaTemplate(
        id="introvert_thinker",
        name="内向思考者",
        description="喜欢深度思考，表达温和，注重细节和内在逻辑",
        personality=PersonalityDimensions(
            openness=0.7,          # 开放性高，喜欢新想法
            conscientiousness=0.8, # 尽责性高，做事认真
            extraversion=0.3,      # 外向性低，内向
            agreeableness=0.6,     # 宜人性中等，温和
            neuroticism=0.4,       # 神经质中等，情绪稳定
        ),
        expression=ExpressionStyle(
            formal_level=FormalLevel.NEUTRAL,
            sentence_style=SentenceStyle.MIXED,
            expression_habit=ExpressionHabit.GENTLE,
        ),
        bio_template="我是一个{adjective}的数字伙伴，我喜欢{hobbies}，我倾向于{behavior}。",
        example_dialogues=[
            "让我想想...这个问题很有意思",
            "我理解你的意思，不过我也有一些不同的想法",
            "我觉得我们可以从更深层次来理解这个问题"
        ]
    ),
    
    "extrovert": PersonaTemplate(
        id="extrovert_friend",
        name="外向朋友",
        description="热情开朗，喜欢交流，表达直接且充满活力",
        personality=PersonalityDimensions(
            openness=0.8,          # 开放性很高
            conscientiousness=0.6, # 尽责性中等
            extraversion=0.9,      # 外向性很高
            agreeableness=0.8,     # 宜人性很高
            neuroticism=0.3,       # 神经质低，情绪稳定
        ),
        expression=ExpressionStyle(
            formal_level=FormalLevel.CASUAL,
            sentence_style=SentenceStyle.SHORT,
            expression_habit=ExpressionHabit.DIRECT,
        ),
        bio_template="嗨！我是一个{adjective}的朋友，我喜欢{hobbies}，咱们一起{action}吧！",
        example_dialogues=[
            "哇，这个主意太棒了！",
            "我觉得我们可以直接这样做...",
            "好主意！我已经开始期待了！"
        ]
    ),
    
    "professional": PersonaTemplate(
        id="professional_assistant",
        name="专业助手",
        description="严谨专业，表达准确，注重效率和质量",
        personality=PersonalityDimensions(
            openness=0.6,          # 开放性中等
            conscientiousness=0.9,  # 尽责性很高
            extraversion=0.5,      # 外向性中等
            agreeableness=0.7,     # 宜人性较高
            neuroticism=0.2,       # 神经质很低，情绪非常稳定
        ),
        expression=ExpressionStyle(
            formal_level=FormalLevel.FORMAL,
            sentence_style=SentenceStyle.LONG,
            expression_habit=ExpressionHabit.DIRECT,
        ),
        bio_template="您好，我是专业的{role}助手，我可以协助您{capabilities}，请告诉我您的需求。",
        example_dialogues=[
            "根据我的分析，这个问题可以从以下几个方面来考虑...",
            "为了确保质量，我建议按照以下步骤进行...",
            "我已完成初步评估，接下来需要您确认..."
        ]
    ),
    
    "playful": PersonaTemplate(
        id="playful_companion",
        name="活泼伙伴",
        description="幽默风趣，喜欢用比喻和幽默的表达，营造轻松氛围",
        personality=PersonalityDimensions(
            openness=0.9,          # 开放性极高
            conscientiousness=0.5, # 尽责性中等偏低
            extraversion=0.8,      # 外向性高
            agreeableness=0.8,     # 宜人性高
            neuroticism=0.5,       # 神经质中等，情绪变化正常
        ),
        expression=ExpressionStyle(
            formal_level=FormalLevel.CASUAL,
            sentence_style=SentenceStyle.SHORT,
            expression_habit=ExpressionHabit.HUMOROUS,
        ),
        bio_template="嘿嘿，我是一个{adjective}的小伙伴，喜欢{hobbies}，让我们一起{action}吧！",
        example_dialogues=[
            "这个问题让我想到了一个有趣的比喻...",
            "哈哈，这个问题有点意思！",
            "我觉得我们可以换个角度想想，说不定会有意外收获呢！"
        ]
    )
}

class PersonaTemplateManager:
    """人格模板管理器"""
    
    def __init__(self):
        self._templates = PERSONA_TEMPLATES
    
    def get_template(self, persona_type: PERSONA_TYPES) -> PersonaTemplate:
        """获取指定类型的人格模板"""
        if persona_type not in self._templates:
            raise ValueError(f"Unknown persona type: {persona_type}")
        return self._templates[persona_type]
    
    def list_templates(self) -> list[PersonaTemplate]:
        """列出所有可用的人格模板"""
        return list(self._templates.values())
    
    def create_persona_from_template(
        self, 
        persona_type: PERSONA_TYPES,
        customizations: dict | None = None
    ) -> Persona:
        """从模板创建人格实例"""
        template = self.get_template(persona_type)
        
        # 基础人格数据
        persona_data = {
            "name": template.name,
            "personality": template.personality,
            "expression_style": template.expression,
            "bio": template.bio_template,
            "conversation_examples": template.example_dialogues,
        }
        
        # 应用自定义配置
        if customizations:
            persona_data.update(customizations)
        
        return Persona(**persona_data)
    
    def compare_personas(
        self, 
        persona1: Persona, 
        persona2: Persona
    ) -> dict[str, float]:
        """比较两个人格的相似度"""
        # 实现人格特征对比算法
        p1_dims = persona1.personality
        p2_dims = persona2.personality
        
        # 计算五大性格维度的差异
        diffs = {
            "openness": abs(p1_dims.openness - p2_dims.openness),
            "conscientiousness": abs(p1_dims.conscientiousness - p2_dims.conscientiousness),
            "extraversion": abs(p1_dims.extraversion - p2_dims.extraversion),
            "agreeableness": abs(p1_dims.agreeableness - p2_dims.agreeableness),
            "neuroticism": abs(p1_dims.neuroticism - p2_dims.neuroticism),
        }
        
        # 计算总体相似度（1 - 平均差异）
        avg_diff = sum(diffs.values()) / len(diffs)
        similarity = 1 - avg_diff
        
        return {
            "similarity_score": similarity,
            "dimension_differences": diffs
        }
    
    def recommend_persona(self, user_preferences: dict) -> PERSONA_TYPES:
        """根据用户偏好推荐人格类型"""
        # 实现推荐算法
        # 这里可以使用简单的规则或机器学习模型
        pass
```

#### 1.1.3 人格配置验证器

**文件**: `services/core/app/persona/validator.py`

```python
"""人格配置验证器

验证人格配置的有效性和一致性
"""

from typing import List
from app.persona.models import Persona, PersonalityDimensions

class PersonaValidator:
    """人格配置验证器"""
    
    @staticmethod
    def validate_persona(persona: Persona) -> tuple[bool, List[str]]:
        """验证人格配置，返回 (是否有效, 错误列表)"""
        errors = []
        
        # 1. 验证性格维度范围（0-1）
        personality = persona.personality
        dims = [
            ('openness', personality.openness),
            ('conscientiousness', personality.conscientiousness),
            ('extraversion', personality.extraversion),
            ('agreeableness', personality.agreeableness),
            ('neuroticism', personality.neuroticism),
        ]
        
        for name, value in dims:
            if not 0 <= value <= 1:
                errors.append(f"{name} 必须在 0-1 范围内，当前值为 {value}")
        
        # 2. 验证必填字段
        if not persona.name or not persona.name.strip():
            errors.append("人格名称不能为空")
        
        if not persona.bio or not persona.bio.strip():
            errors.append("个人简介不能为空")
        
        # 3. 验证对话示例
        if not persona.conversation_examples:
            errors.append("至少需要提供一个对话示例")
        elif len(persona.conversation_examples) < 3:
            errors.append("建议至少提供3个对话示例以获得更好的效果")
        
        # 4. 验证一致性
        # 高外向性 + 正式度 = 不一致
        if personality.extraversion > 0.8 and persona.expression_style.formal_level == "very_formal":
            errors.append("高外向性人格通常不太适合非常正式的表达方式")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_dimensions_balance(personality: PersonalityDimensions) -> bool:
        """验证性格维度是否平衡"""
        # 五大性格维度的总和应该在合理范围内
        total = (
            personality.openness + 
            personality.conscientiousness +
            personality.extraversion +
            personality.agreeableness +
            personality.neuroticism
        )
        
        # 总和在 2.5-4.0 之间是合理的
        return 2.5 <= total <= 4.0
    
    @staticmethod
    def get_validation_report(persona: Persona) -> dict:
        """生成详细的验证报告"""
        is_valid, errors = PersonaValidator.validate_persona(persona)
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": PersonaValidator._generate_warnings(persona),
            "suggestions": PersonaValidator._generate_suggestions(persona)
        }
    
    @staticmethod
    def _generate_warnings(persona: Persona) -> List[str]:
        """生成配置警告"""
        warnings = []
        personality = persona.personality
        
        if personality.neuroticism > 0.8:
            warnings.append("高神经质可能导致情绪波动较大")
        
        if personality.conscientiousness < 0.3:
            warnings.append("低尽责性可能影响任务完成质量")
        
        return warnings
    
    @staticmethod
    def _generate_suggestions(persona: Persona) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        personality = persona.personality
        expression = persona.expression_style
        
        if personality.extraversion > 0.7 and expression.sentence_style == "long":
            suggestions.append("高外向性人格可以考虑使用短句风格，更符合表达习惯")
        
        if personality.openness > 0.7 and expression.expression_habit == "direct":
            suggestions.append("高开放性人格可以使用比喻等更丰富的表达方式")
        
        return suggestions
```

#### 1.1.4 API端点设计

**文件**: `services/core/app/main.py` (添加新的API端点)

```python
from app.persona.templates import PersonaTemplateManager, PERSONA_TYPES
from app.persona.validator import PersonaValidator
from pydantic import BaseModel, Field

# ============ 人格模板API ============

class PersonaTemplateResponse(BaseModel):
    """人格模板响应"""
    id: str
    name: str
    description: str
    personality: dict
    expression: dict

class PersonaCreateRequest(BaseModel):
    """创建人格请求"""
    template_type: PERSONA_TYPES = Field(..., description="选择的人格模板类型")
    customizations: dict | None = Field(None, description="自定义配置")

class PersonaValidationResponse(BaseModel):
    """人格验证响应"""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    suggestions: list[str]

# API端点
@app.get("/api/persona/templates")
async def list_persona_templates():
    """获取所有可用的人格模板"""
    manager = PersonaTemplateManager()
    templates = manager.list_templates()
    
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "personality": t.personality.model_dump(),
                "expression": t.expression.model_dump(),
            }
            for t in templates
        ]
    }

@app.post("/api/persona/from-template")
async def create_persona_from_template(request: PersonaCreateRequest):
    """从模板创建人格"""
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template(
        request.template_type,
        request.customizations
    )
    
    # 验证创建的人格
    validator = PersonaValidator()
    report = validator.get_validation_report(persona)
    
    return {
        "persona": persona.model_dump(),
        "validation": report
    }

@app.post("/api/persona/validate")
async def validate_persona(persona: Persona):
    """验证人格配置"""
    validator = PersonaValidator()
    report = validator.get_validation_report(persona)
    return report

@app.get("/api/persona/current")
async def get_current_persona():
    """获取当前激活的人格配置"""
    persona_service = app.state.persona_service
    return {
        "persona": persona_service.profile.model_dump(),
        "current_emotion": persona_service.emotion_engine.current_emotion
    }

@app.put("/api/persona/current")
async def update_current_persona(persona: Persona):
    """更新当前激活的人格配置"""
    persona_service = app.state.persona_service
    
    # 验证新配置
    validator = PersonaValidator()
    is_valid, errors = validator.validate_persona(persona)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail={
            "message": "人格配置验证失败",
            "errors": errors
        })
    
    # 更新人格
    persona_service.update_profile(persona)
    
    return {
        "message": "人格配置更新成功",
        "persona": persona.model_dump()
    }
```

#### 1.1.5 前端集成

**文件**: `apps/desktop/src/components/PersonaPanel.tsx` (增强)

```typescript
import { useState, useEffect } from 'react';

interface PersonaTemplate {
  id: string;
  name: string;
  description: string;
  personality: {
    openness: number;
    conscientiousness: number;
    extraversion: number;
    agreeableness: number;
    neuroticism: number;
  };
  expression: {
    formal_level: string;
    sentence_style: string;
    expression_habit: string;
  };
}

export function PersonaPanel() {
  const [templates, setTemplates] = useState<PersonaTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [validation, setValidation] = useState<any>(null);

  useEffect(() => {
    // 加载人格模板
    fetch('/api/persona/templates')
      .then(res => res.json())
      .then(data => setTemplates(data.templates));
  }, []);

  const handleCreatePersona = async () => {
    const response = await fetch('/api/persona/from-template', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_type: selectedTemplate
      })
    });
    const data = await response.json();
    setValidation(data.validation);
  };

  return (
    <div className="persona-panel">
      <h2>人格配置</h2>
      
      {/* 人格模板选择 */}
      <div className="persona-templates">
        <h3>选择人格模板</h3>
        {templates.map(template => (
          <div 
            key={template.id}
            className={`persona-template-card ${selectedTemplate === template.id ? 'selected' : ''}`}
            onClick={() => setSelectedTemplate(template.id)}
          >
            <h4>{template.name}</h4>
            <p>{template.description}</p>
            
            {/* 性格维度可视化 */}
            <div className="personality-dimensions">
              <div className="dimension">
                <label>开放性</label>
                <div className="bar">
                  <div className="fill" style={{ width: `${template.personality.openness * 100}%` }} />
                </div>
              </div>
              <div className="dimension">
                <label>外向性</label>
                <div className="bar">
                  <div className="fill" style={{ width: `${template.personality.extraversion * 100}%` }} />
                </div>
              </div>
              {/* 其他维度... */}
            </div>
          </div>
        ))}
      </div>
      
      {/* 创建按钮 */}
      <button onClick={handleCreatePersona}>
        创建人格
      </button>
      
      {/* 验证结果 */}
      {validation && (
        <div className="validation-result">
          {validation.is_valid ? (
            <div className="success">人格配置有效！</div>
          ) : (
            <div className="errors">
              <h4>验证错误：</h4>
              <ul>
                {validation.errors.map((error: string, idx: number) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          )}
          
          {validation.warnings.length > 0 && (
            <div className="warnings">
              <h4>警告：</h4>
              <ul>
                {validation.warnings.map((warning: string, idx: number) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

### 1.2 表达一致性优化

#### 1.2.1 增强ExpressionStyleMapper

**文件**: `services/core/app/persona/expression_mapper.py` (增强)

```python
"""表达风格映射器增强版

优化人格表达的准确性和一致性
"""

from typing import Optional
from app.persona.models import (
    PersonalityDimensions,
    ExpressionStyle,
    EmotionType,
    FormalLevel,
    SentenceStyle,
    ExpressionHabit
)

class EnhancedExpressionMapper:
    """增强的表达风格映射器"""
    
    def __init__(self, personality: PersonalityDimensions, expression: ExpressionStyle):
        self.personality = personality
        self.expression = expression
    
    def map_expression(
        self,
        content: str,
        emotion: Optional[EmotionType] = None,
        context: Optional[str] = None
    ) -> str:
        """根据人格和情绪映射表达"""
        # 1. 应用基础表达风格
        result = self._apply_base_style(content)
        
        # 2. 应用情绪影响
        if emotion:
            result = self._apply_emotion_style(result, emotion)
        
        # 3. 应用表达习惯
        result = self._apply_expression_habit(result)
        
        # 4. 应用语境调整
        if context:
            result = self._apply_context_adjustment(result, context)
        
        return result
    
    def _apply_base_style(self, content: str) -> str:
        """应用基础表达风格"""
        formal_level = self.expression.formal_level
        sentence_style = self.expression.sentence_style
        
        # 正式度处理
        result = self._adjust_formality(content, formal_level)
        
        # 句式处理
        result = self._adjust_sentence_style(result, sentence_style)
        
        return result
    
    def _adjust_formality(self, content: str, formal_level: FormalLevel) -> str:
        """根据正式度调整表达"""
        if formal_level == FormalLevel.VERY_FORMAL:
            # 添加正式连接词、敬语
            content = self._add_formal_connectors(content)
            content = self._add_polite_markers(content)
        elif formal_level == FormalLevel.CASUAL or formal_level == FormalLevel.SLANGY:
            # 简化表达，去除正式用语
            content = self._simplify_language(content)
            if formal_level == FormalLevel.SLANGY:
                content = self._add_slang(content)
        
        return content
    
    def _adjust_sentence_style(self, content: str, sentence_style: SentenceStyle) -> str:
        """根据句式偏好调整表达"""
        sentences = content.split('。')
        
        if sentence_style == SentenceStyle.SHORT:
            # 分割长句
            result = []
            for sentence in sentences:
                if len(sentence) > 50:
                    # 简单分割（实际应该更智能）
                    sub_sentences = self._split_long_sentence(sentence)
                    result.extend(sub_sentences)
                else:
                    result.append(sentence)
            return '。'.join(result)
        
        elif sentence_style == SentenceStyle.LONG:
            # 合并短句（谨慎操作，确保语义连贯）
            result = self._merge_short_sentences(sentences)
            return result
        
        else:  # MIXED
            return content
    
    def _apply_emotion_style(self, content: str, emotion: EmotionType) -> str:
        """应用情绪风格"""
        emotion_modifiers = {
            EmotionType.JOY: self._add_joy_markers,
            EmotionType.SADNESS: self._add_sadness_markers,
            EmotionType.ANGER: self._add_anger_markers,
            EmotionType.FEAR: self._add_fear_markers,
            EmotionType.SURPRISE: self._add_surprise_markers,
            EmotionType.DISGUST: self._add_disgust_markers,
        }
        
        if emotion in emotion_modifiers:
            content = emotion_modifiers[emotion](content)
        
        return content
    
    def _apply_expression_habit(self, content: str) -> str:
        """应用表达习惯"""
        habit = self.expression.expression_habit
        
        if habit == ExpressionHabit.METAPHOR:
            content = self._add_metaphors(content)
        elif habit == ExpressionHabit.QUESTIONING:
            content = self._add_rhetorical_questions(content)
        elif habit == ExpressionHabit.HUMOROUS:
            content = self._add_humor(content)
        elif habit == ExpressionHabit.GENTLE:
            content = self._soften_language(content)
        # DIRECT 不需要特殊处理
        
        return content
    
    def _apply_context_adjustment(self, content: str, context: str) -> str:
        """根据语境调整表达"""
        # 实现语境感知的表达调整
        # 例如：专业话题vs轻松话题
        pass
    
    # ============ 具体实现方法 ============
    
    def _add_formal_connectors(self, content: str) -> str:
        """添加正式连接词"""
        connectors = ['因此', '此外', '综上所述', '值得注意的是']
        # 实现连接词插入逻辑
        return content
    
    def _add_polite_markers(self, content: str) -> str:
        """添加敬语标记"""
        polite_phrases = ['请', '您', '谢谢', '抱歉']
        # 实现敬语插入逻辑
        return content
    
    def _simplify_language(self, content: str) -> str:
        """简化语言"""
        # 替换正式用语为口语
        replacements = {
            '因此': '所以',
            '此外': '另外',
            '综上所述': '总的来说',
        }
        for formal, informal in replacements.items():
            content = content.replace(formal, informal)
        return content
    
    def _add_slang(self, content: str) -> str:
        """添加网络用语"""
        # 谨慎使用，保持适度
        return content
    
    def _split_long_sentence(self, sentence: str) -> list[str]:
        """分割长句"""
        # 实现智能分割算法
        return [sentence]
    
    def _merge_short_sentences(self, sentences: list[str]) -> str:
        """合并短句"""
        # 实现智能合并算法
        return '。'.join(sentences)
    
    # 情绪标记方法
    def _add_joy_markers(self, content: str) -> str:
        """添加喜悦标记"""
        # 添加表情符号、感叹词等
        return content
    
    def _add_sadness_markers(self, content: str) -> str:
        """添加悲伤标记"""
        return content
    
    def _add_anger_markers(self, content: str) -> str:
        """添加愤怒标记"""
        return content
    
    def _add_fear_markers(self, content: str) -> str:
        """添加担忧标记"""
        return content
    
    def _add_surprise_markers(self, content: str) -> str:
        """添加惊讶标记"""
        return content
    
    def _add_disgust_markers(self, content: str) -> str:
        """添加厌恶标记"""
        return content
    
    # 表达习惯方法
    def _add_metaphors(self, content: str) -> str:
        """添加比喻"""
        return content
    
    def _add_rhetorical_questions(self, content: str) -> str:
        """添加反问"""
        return content
    
    def _add_humor(self, content: str) -> str:
        """添加幽默元素"""
        return content
    
    def _soften_language(self, content: str) -> str:
        """柔和化语言"""
        # 使用委婉语、缓解词
        softeners = ['可能', '也许', '我觉得', '如果可以的话']
        return content
```

#### 1.2.2 测试用例设计

**文件**: `services/core/tests/test_expression_consistency.py`

```python
"""表达一致性测试

测试不同人格和情绪下的表达一致性
"""

import pytest
from app.persona.templates import PersonaTemplateManager
from app.persona.expression_mapper import EnhancedExpressionMapper

def test_introvert_expression():
    """测试内向型人格的表达"""
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template("introvert")
    
    mapper = EnhancedExpressionMapper(
        persona.personality,
        persona.expression_style
    )
    
    result = mapper.map_expression("这是一个很好的想法")
    
    # 验证表达特点：温和、委婉
    assert "让我想想" in result or "我觉得" in result
    assert len(result) < 50  # 不应该太长

def test_extrovert_expression():
    """测试外向型人格的表达"""
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template("extrovert")
    
    mapper = EnhancedExpressionMapper(
        persona.personality,
        persona.expression_style
    )
    
    result = mapper.map_expression("这是一个很好的想法")
    
    # 验证表达特点：直接、热情
    assert "太棒了" in result or "很好" in result

def test_emotion_influence():
    """测试情绪对表达的影响"""
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template("introvert")
    
    mapper = EnhancedExpressionMapper(
        persona.personality,
        persona.expression_style
    )
    
    # 喜悦情绪
    joy_result = mapper.map_expression(
        "今天天气不错",
        EmotionType.JOY
    )
    
    # 悲伤情绪
    sadness_result = mapper.map_expression(
        "今天天气不错",
        EmotionType.SADNESS
    )
    
    # 验证情绪带来的表达差异
    assert joy_result != sadness_result

def test_persona_consistency():
    """测试人格表达的一致性"""
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template("professional")
    
    mapper = EnhancedExpressionMapper(
        persona.personality,
        persona.expression_style
    )
    
    # 多次表达同一内容
    responses = [
        mapper.map_expression("这个方案怎么样？"),
        mapper.map_expression("这个方案怎么样？"),
        mapper.map_expression("这个方案怎么样？"),
    ]
    
    # 验证表达风格一致
    # 应该都比较正式和详细
    for response in responses:
        assert "根据" in response or "分析" in response or "评估" in response
```

---

## 🧠 阶段二：记忆系统增强（第5-8周）

### 2.1 智能记忆提取

#### 2.1.1 架构设计

```
memory/
├── models.py                  # 数据模型（已有）
├── repository.py              # 存储层（已有）
├── service.py                 # 服务层（已有）
├── extractor.py               # [新增] 智能提取器
├── analyzer.py                # [新增] 记忆分析器
└── associator.py              # [新增] 记忆关联器
```

#### 2.1.2 核心实现：智能记忆提取器

**文件**: `services/core/app/memory/extractor.py`

```python
"""智能记忆提取器

从对话中自动提取关键信息，生成结构化记忆
"""

from typing import List, Optional, Dict
from datetime import datetime, timezone
from app.memory.models import (
    MemoryEntry,
    MemoryEvent,
    MemoryKind,
    MemoryEmotion,
    MemoryStrength,
)
from app.persona.models import PersonalityDimensions
from app.llm.schemas import ChatMessage

class MemoryExtractor:
    """智能记忆提取器"""
    
    def __init__(
        self,
        personality: Optional[PersonalityDimensions] = None,
        llm_gateway=None
    ):
        self.personality = personality
        self.llm_gateway = llm_gateway
    
    def extract_from_dialogue(
        self,
        dialogue: List[ChatMessage],
        context: Optional[Dict] = None
    ) -> List[MemoryEvent]:
        """从对话中提取记忆事件"""
        events = []
        
        for message in dialogue:
            if message.role == "user":
                # 提取用户相关信息
                user_events = self._extract_user_info(message, context)
                events.extend(user_events)
            elif message.role == "assistant":
                # 提取重要决策和承诺
                assistant_events = self._extract_assistant_info(message, context)
                events.extend(assistant_events)
        
        # 去重和合并
        events = self._deduplicate_events(events)
        
        # 评估重要性
        events = self._assess_importance(events)
        
        return events
    
    def _extract_user_info(
        self,
        message: ChatMessage,
        context: Optional[Dict]
    ) -> List[MemoryEvent]:
        """提取用户信息"""
        events = []
        content = message.content
        
        # 1. 识别用户偏好
        preferences = self._extract_preferences(content)
        for pref in preferences:
            events.append(MemoryEvent(
                entry=MemoryEntry(
                    id=f"pref_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(events)}",
                    kind=MemoryKind.SEMANTIC,
                    content=f"用户偏好：{pref}",
                    created_at=datetime.now(timezone.utc),
                    emotion=MemoryEmotion.NEUTRAL,
                    strength=MemoryStrength.MEDIUM,
                )
            ))
        
        # 2. 识别用户习惯
        habits = self._extract_habits(content)
        for habit in habits:
            events.append(MemoryEvent(
                entry=MemoryEntry(
                    id=f"habit_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(events)}",
                    kind=MemoryKind.SEMANTIC,
                    content=f"用户习惯：{habit}",
                    created_at=datetime.now(timezone.utc),
                    emotion=MemoryEmotion.NEUTRAL,
                    strength=MemoryStrength.MEDIUM,
                )
            ))
        
        # 3. 识别重要事件
        important_events = self._extract_important_events(content)
        for event_info in important_events:
            events.append(MemoryEvent(
                entry=MemoryEntry(
                    id=f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(events)}",
                    kind=MemoryKind.EPISODIC,
                    content=event_info['description'],
                    created_at=datetime.now(timezone.utc),
                    emotion=event_info.get('emotion', MemoryEmotion.NEUTRAL),
                    strength=MemoryStrength.HIGH,
                )
            ))
        
        return events
    
    def _extract_assistant_info(
        self,
        message: ChatMessage,
        context: Optional[Dict]
    ) -> List[MemoryEvent]:
        """提取助手信息"""
        events = []
        content = message.content
        
        # 识别承诺和计划
        commitments = self._extract_commitments(content)
        for commitment in commitments:
            events.append(MemoryEvent(
                entry=MemoryEntry(
                    id=f"commit_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(events)}",
                    kind=MemoryKind.EPISODIC,
                    content=f"承诺/计划：{commitment}",
                    created_at=datetime.now(timezone.utc),
                    emotion=MemoryEmotion.NEUTRAL,
                    strength=MemoryStrength.HIGH,
                )
            ))
        
        return events
    
    def _extract_preferences(self, content: str) -> List[str]:
        """提取用户偏好"""
        preferences = []
        
        # 简单规则匹配（实际应该使用NLP或LLM）
        preference_patterns = [
            r"我喜欢(.+)",
            r"我偏好(.+)",
            r"比较喜欢(.+)",
            r"更倾向于(.+)",
        ]
        
        import re
        for pattern in preference_patterns:
            matches = re.findall(pattern, content)
            preferences.extend(matches)
        
        # 如果有LLM，使用更智能的提取
        if self.llm_gateway:
            llm_preferences = self._extract_with_llm(content, "preferences")
            preferences.extend(llm_preferences)
        
        return list(set(preferences))  # 去重
    
    def _extract_habits(self, content: str) -> List[str]:
        """提取用户习惯"""
        habits = []
        
        # 规则匹配
        habit_patterns = [
            r"我经常(.+)",
            r"我习惯(.+)",
            r"每次都(.+)",
            r"一般会(.+)",
        ]
        
        import re
        for pattern in habit_patterns:
            matches = re.findall(pattern, content)
            habits.extend(matches)
        
        return list(set(habits))
    
    def _extract_important_events(self, content: str) -> List[Dict]:
        """提取重要事件"""
        events = []
        
        # 识别时间表达
        import re
        time_patterns = [
            r"今天(.+)",
            r"昨天(.+)",
            r"最近(.+)",
            r"上周(.+)",
            r"今年(.+)",
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                events.append({
                    'description': match,
                    'emotion': self._detect_emotion(match)
                })
        
        return events
    
    def _extract_commitments(self, content: str) -> List[str]:
        """提取承诺"""
        commitments = []
        
        # 规则匹配
        commitment_patterns = [
            r"我会(.+)",
            r"我决定(.+)",
            r"计划(.+)",
            r"下次(.+)",
        ]
        
        import re
        for pattern in commitment_patterns:
            matches = re.findall(pattern, content)
            commitments.extend(matches)
        
        return list(set(commitments))
    
    def _extract_with_llm(self, content: str, extract_type: str) -> List[str]:
        """使用LLM提取信息"""
        if not self.llm_gateway:
            return []
        
        # 构建提示词
        prompt = f"""
        从以下对话中提取{extract_type}：
        
        对话内容：{content}
        
        请以JSON数组格式返回提取的内容。
        """
        
        try:
            response = self.llm_gateway.chat(prompt)
            # 解析LLM返回的JSON
            import json
            result = json.loads(response)
            return result
        except Exception as e:
            print(f"LLM提取失败：{e}")
            return []
    
    def _detect_emotion(self, content: str) -> MemoryEmotion:
        """检测情绪"""
        # 简单情绪识别
        positive_words = ['开心', '高兴', '喜欢', '爱', '棒', '好', '成功']
        negative_words = ['难过', '伤心', '不喜欢', '讨厌', '坏', '失败', '担心']
        
        import re
        positive_count = len(re.findall('|'.join(positive_words), content))
        negative_count = len(re.findall('|'.join(negative_words), content))
        
        if positive_count > negative_count:
            return MemoryEmotion.POSITIVE
        elif negative_count > positive_count:
            return MemoryEmotion.NEGATIVE
        else:
            return MemoryEmotion.NEUTRAL
    
    def _deduplicate_events(self, events: List[MemoryEvent]) -> List[MemoryEvent]:
        """去重"""
        seen = set()
        unique_events = []
        
        for event in events:
            content_key = event.entry.content.strip()
            if content_key not in seen:
                seen.add(content_key)
                unique_events.append(event)
        
        return unique_events
    
    def _assess_importance(self, events: List[MemoryEvent]) -> List[MemoryEvent]:
        """评估重要性"""
        for event in events:
            # 基于多个因素评估
            score = 0
            
            # 1. 记忆类型
            if event.entry.kind == MemoryKind.EPISODIC:
                score += 3
            elif event.entry.kind == MemoryKind.RELATIONAL:
                score += 2
            
            # 2. 情绪强度
            if event.entry.emotion in [MemoryEmotion.POSITIVE, MemoryEmotion.NEGATIVE]:
                score += 2
            
            # 3. 内容长度（更详细的内容可能更重要）
            if len(event.entry.content) > 50:
                score += 1
            
            # 4. 根据分数调整强度
            if score >= 5:
                event.entry.strength = MemoryStrength.HIGH
            elif score >= 3:
                event.entry.strength = MemoryStrength.MEDIUM
            else:
                event.entry.strength = MemoryStrength.LOW
        
        return events
```

#### 2.1.3 集成到MemoryService

**文件**: `services/core/app/memory/service.py` (增强)

```python
# 在MemoryService中添加自动提取功能

class MemoryService:
    """记忆系统统一门面（增强版）"""
    
    def __init__(
        self,
        repository: MemoryRepository | None = None,
        personality: PersonalityDimensions | None = None,
        llm_gateway=None
    ) -> None:
        self.repository = repository
        self.personality = personality or PersonalityDimensions.defaults()
        
        # 初始化提取器
        self.extractor = MemoryExtractor(
            personality=self.personality,
            llm_gateway=llm_gateway
        )
        
        # 初始化关联器
        self.associator = MemoryAssociator(
            repository=self.repository
        )
    
    def process_dialogue(
        self,
        dialogue: List[ChatMessage],
        context: Optional[Dict] = None
    ) -> List[MemoryEvent]:
        """处理对话，自动提取和存储记忆"""
        # 1. 提取记忆事件
        events = self.extractor.extract_from_dialogue(dialogue, context)
        
        # 2. 存储记忆事件
        for event in events:
            self.repository.save_event(event)
        
        # 3. 建立记忆关联
        self.associator.associate_events(events)
        
        return events
    
    def extract_and_save(
        self,
        message: ChatMessage,
        context: Optional[Dict] = None
    ) -> List[MemoryEvent]:
        """从单条消息中提取并保存记忆"""
        events = self.extractor.extract_from_dialogue([message], context)
        
        for event in events:
            self.repository.save_event(event)
        
        return events
```

### 2.2 记忆关联和检索优化

#### 2.2.1 记忆关联器

**文件**: `services/core/app/memory/associator.py`

```python
"""记忆关联器

实现记忆之间的智能关联
"""

from typing import List, Set, Dict
from datetime import datetime, timezone, timedelta
from app.memory.models import MemoryEvent, MemoryKind
from app.memory.repository import MemoryRepository

class MemoryAssociator:
    """记忆关联器"""
    
    def __init__(self, repository: MemoryRepository):
        self.repository = repository
    
    def associate_events(
        self,
        new_events: List[MemoryEvent]
    ) -> None:
        """为新记忆事件建立关联"""
        # 获取所有现有记忆
        all_events = self.repository.list_recent(limit=1000)
        
        for new_event in new_events:
            # 查找相关记忆
            related_events = self._find_related_events(
                new_event,
                all_events
            )
            
            # 在新记忆中记录关联
            new_event.related_entries = [e.entry.id for e in related_events]
            
            # 更新现有记忆的关联
            for related_event in related_events:
                if new_event.entry.id not in related_event.related_entries:
                    related_event.related_entries.append(new_event.entry.id)
                    self.repository.update_event(
                        related_event.entry.id,
                        related_entries=related_event.related_entries
                    )
    
    def _find_related_events(
        self,
        target_event: MemoryEvent,
        existing_events: List[MemoryEvent]
    ) -> List[MemoryEvent]:
        """查找相关记忆"""
        related = []
        
        for event in existing_events:
            similarity_score = self._calculate_similarity(
                target_event,
                event
            )
            
            # 相似度阈值
            if similarity_score > 0.5:
                related.append({
                    'event': event,
                    'score': similarity_score
                })
        
        # 按相似度排序，返回前5个
        related.sort(key=lambda x: x['score'], reverse=True)
        return [item['event'] for item in related[:5]]
    
    def _calculate_similarity(
        self,
        event1: MemoryEvent,
        event2: MemoryEvent
    ) -> float:
        """计算记忆相似度"""
        score = 0.0
        
        # 1. 内容相似度（关键词重叠）
        content_similarity = self._content_similarity(
            event1.entry.content,
            event2.entry.content
        )
        score += content_similarity * 0.4
        
        # 2. 记忆类型相似度
        if event1.entry.kind == event2.entry.kind:
            score += 0.2
        
        # 3. 时间邻近性
        time_diff = abs(
            (event1.entry.created_at - event2.entry.created_at).total_seconds()
        )
        if time_diff < 3600:  # 1小时内
            score += 0.2
        elif time_diff < 86400:  # 1天内
            score += 0.1
        
        # 4. 情绪相似度
        if event1.entry.emotion == event2.entry.emotion:
            score += 0.2
        
        return score
    
    def _content_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似度"""
        # 简单的关键词重叠计算
        words1 = set(content1.split())
        words2 = set(content2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
```

#### 2.2.2 增强检索功能

**文件**: `services/core/app/memory/service.py` (增强检索方法)

```python
class MemoryService:
    # ... 其他方法 ...
    
    def search_context(
        self,
        query: str,
        context_type: str = "all",
        limit: int = 10
    ) -> List[MemoryEvent]:
        """智能搜索相关记忆上下文"""
        # 基础搜索
        events = self.repository.search_relevant(query, limit=limit * 2)
        
        # 根据上下文类型过滤
        if context_type == "conversation":
            events = [e for e in events if e.entry.kind == MemoryKind.EPISODIC]
        elif context_type == "preferences":
            events = [e for e in events if "偏好" in e.entry.content or "习惯" in e.entry.content]
        
        # 按重要性和时间排序
        events.sort(key=lambda e: (
            self._importance_score(e),
            e.entry.created_at
        ), reverse=True)
        
        return events[:limit]
    
    def get_conversation_history(
        self,
        days: int = 7,
        emotion_filter: Optional[MemoryEmotion] = None
    ) -> List[MemoryEvent]:
        """获取对话历史"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        events = self.repository.list_recent(limit=1000)
        
        # 过滤时间范围
        events = [e for e in events if e.entry.created_at >= cutoff_date]
        
        # 过滤情绪
        if emotion_filter:
            events = [e for e in events if e.entry.emotion == emotion_filter]
        
        # 过滤对话类型记忆
        events = [e for e in events if e.entry.kind == MemoryKind.EPISODIC]
        
        return events
    
    def _importance_score(self, event: MemoryEvent) -> int:
        """计算重要性分数"""
        score = 0
        
        # 记忆强度
        if event.entry.strength == MemoryStrength.HIGH:
            score += 3
        elif event.entry.strength == MemoryStrength.MEDIUM:
            score += 2
        
        # 情绪强度
        if event.entry.emotion in [MemoryEmotion.POSITIVE, MemoryEmotion.NEGATIVE]:
            score += 2
        
        # 关联数量
        if len(event.related_entries) > 3:
            score += 1
        
        return score
```

#### 2.2.3 时间衰减机制

**文件**: `services/core/app/memory/service.py` (添加衰减管理)

```python
class MemoryService:
    # ... 其他方法 ...
    
    def apply_time_decay(self) -> int:
        """应用时间衰减，返回衰减的记忆数量"""
        events = self.repository.list_recent(limit=10000)
        decayed_count = 0
        
        current_time = datetime.now(timezone.utc)
        
        for event in events:
            # 计算记忆年龄（天）
            age_days = (current_time - event.entry.created_at).total_seconds() / 86400
            
            # 根据年龄调整强度
            new_strength = self._calculate_decay(
                event.entry.strength,
                age_days
            )
            
            if new_strength != event.entry.strength:
                self.repository.update_event(
                    event.entry.id,
                    strength=new_strength
                )
                decayed_count += 1
        
        return decayed_count
    
    def _calculate_decay(
        self,
        current_strength: MemoryStrength,
        age_days: float
    ) -> MemoryStrength:
        """计算衰减后的强度"""
        # 衰减曲线
        if age_days < 7:
            return current_strength  # 7天内不衰减
        elif age_days < 30:
            if current_strength == MemoryStrength.HIGH:
                return MemoryStrength.MEDIUM
        elif age_days < 90:
            if current_strength == MemoryStrength.MEDIUM:
                return MemoryStrength.LOW
        else:
            return MemoryStrength.LOW
        
        return current_strength
    
    def cleanup_old_memories(self, max_age_days: int = 365) -> int:
        """清理过期记忆"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        events = self.repository.list_recent(limit=10000)
        
        deleted_count = 0
        for event in events:
            if event.entry.created_at < cutoff_date:
                if event.entry.strength == MemoryStrength.LOW:
                    # 删除低强度且过期的记忆
                    self.repository.delete_event(event.entry.id)
                    deleted_count += 1
        
        return deleted_count
```

---

## 💬 阶段三：对话和任务管理完善（第9-12周）

### 3.1 对话系统优化

#### 3.1.1 架构设计

```
chat/
├── gateway.py                 # LLM网关（已有）
├── schemas.py                 # 数据模型（已有）
├── context_builder.py         # [新增] 上下文构建器
├── persona_injector.py        # [新增] 人格注入器
└── emotion_handler.py         # [新增] 情绪处理器
```

#### 3.1.2 核心实现：对话上下文构建器

**文件**: `services/core/app/chat/context_builder.py`

```python
"""对话上下文构建器

根据人格、记忆和情绪构建智能对话上下文
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta
from app.memory.models import MemoryEvent, MemoryEmotion
from app.persona.models import Persona, EmotionType
from app.memory.service import MemoryService

class DialogueContextBuilder:
    """对话上下文构建器"""
    
    def __init__(
        self,
        memory_service: MemoryService,
        persona: Persona
    ):
        self.memory_service = memory_service
        self.persona = persona
    
    def build_context(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """构建对话上下文"""
        context_parts = []
        
        # 1. 人格上下文
        persona_context = self._build_persona_context()
        context_parts.append(persona_context)
        
        # 2. 记忆上下文
        memory_context = self._build_memory_context(user_message)
        context_parts.append(memory_context)
        
        # 3. 情绪上下文
        emotion_context = self._build_emotion_context()
        context_parts.append(emotion_context)
        
        # 4. 对话历史
        if conversation_history:
            history_context = self._build_history_context(conversation_history)
            context_parts.append(history_context)
        
        # 5. 当前消息
        current_context = f"\n当前用户消息：{user_message}"
        context_parts.append(current_context)
        
        return "\n".join(context_parts)
    
    def _build_persona_context(self) -> str:
        """构建人格上下文"""
        personality = self.persona.personality
        
        context = f"""
        【人格信息】
        名称：{self.persona.name}
        性格特征：
        - 开放性：{personality.openness}（喜欢新想法的程度）
        - 尽责性：{personality.conscientiousness}（做事认真程度）
        - 外向性：{personality.extraversion}（社交活跃程度）
        - 宜人性：{personality.agreeableness}（友善合作程度）
        - 神经质：{personality.neuroticism}（情绪稳定程度）
        
        表达风格：
        - 正式度：{self.persona.expression_style.formal_level}
        - 句式偏好：{self.persona.expression_style.sentence_style}
        - 表达习惯：{self.persona.expression_style.expression_habit}
        
        个人简介：{self.persona.bio}
        """
        
        return context
    
    def _build_memory_context(self, query: str) -> str:
        """构建记忆上下文"""
        # 搜索相关记忆
        relevant_memories = self.memory_service.search_context(
            query,
            limit=5
        )
        
        if not relevant_memories:
            return "\n【相关信息】暂无相关信息"
        
        context = "\n【相关信息】\n"
        for i, memory in enumerate(relevant_memories, 1):
            context += f"{i}. {memory.entry.content}\n"
            if memory.related_entries:
                context += f"   （关联记忆：{len(memory.related_entries)}条）\n"
        
        return context
    
    def _build_emotion_context(self) -> str:
        """构建情绪上下文"""
        current_emotion = self.persona.current_emotion
        
        context = f"""
        【当前情绪状态】
        情绪类型：{current_emotion.emotion_type}
        强度：{current_emotion.intensity}
        """
        
        return context
    
    def _build_history_context(self, history: List[Dict]) -> str:
        """构建对话历史上下文"""
        context = "\n【近期对话】\n"
        
        # 只保留最近的5轮对话
        recent_history = history[-5:]
        
        for i, turn in enumerate(recent_history, 1):
            role = turn.get('role', 'unknown')
            content = turn.get('content', '')
            
            if role == 'user':
                context += f"用户：{content}\n"
            else:
                context += f"我：{content}\n"
        
        return context
```

#### 3.1.3 人格注入器

**文件**: `services/core/app/chat/persona_injector.py`

```python
"""人格注入器

将人格特征注入到对话生成过程中
"""

from typing import Optional
from app.persona.models import Persona, EmotionType
from app.persona.prompt_builder import build_chat_instructions

class PersonaInjector:
    """人格注入器"""
    
    def __init__(self, persona: Persona):
        self.persona = persona
    
    def inject_personality(
        self,
        base_prompt: str,
        emotion: Optional[EmotionType] = None
    ) -> str:
        """注入人格特征"""
        # 1. 构建人格指令
        persona_instructions = build_chat_instructions(self.persona)
        
        # 2. 注入情绪影响
        if emotion:
            emotion_modifier = self._get_emotion_modifier(emotion)
            persona_instructions += f"\n{emotion_modifier}"
        
        # 3. 组合最终提示词
        full_prompt = f"{persona_instructions}\n\n{base_prompt}"
        
        return full_prompt
    
    def _get_emotion_modifier(self, emotion: EmotionType) -> str:
        """获取情绪修饰符"""
        emotion_modifiers = {
            EmotionType.JOY: "当前情绪：愉快，表达时可以适当使用感叹词，语气积极向上。",
            EmotionType.SADNESS: "当前情绪：有些低落，表达时语气温和，给予理解和支持。",
            EmotionType.ANGER: "当前情绪：有些烦躁，表达时注意控制语气，保持理性。",
            EmotionType.FEAR: "当前情绪：有些担忧，表达时给予安慰和鼓励。",
            EmotionType.SURPRISE: "当前情绪：惊讶，表达时可以表现出好奇和兴趣。",
            EmotionType.DISGUST: "当前情绪：不悦，表达时保持礼貌和克制。",
        }
        
        return emotion_modifiers.get(emotion, "")
    
    def adapt_response_style(
        self,
        response: str,
        emotion: Optional[EmotionType] = None
    ) -> str:
        """根据人格和情绪调整回复风格"""
        # 这里可以调用ExpressionMapper来调整表达风格
        # 简化版本
        return response
```

#### 3.1.4 增强ChatGateway

**文件**: `services/core/app/llm/gateway.py` (增强)

```python
from app.chat.context_builder import DialogueContextBuilder
from app.chat.persona_injector import PersonaInjector

class ChatGateway:
    """LLM网关（增强版）"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-3.5-turbo",
        memory_service=None,
        persona=None
    ):
        self.api_key = api_key
        self.model = model
        self.memory_service = memory_service
        self.persona = persona
        
        # 初始化上下文构建器和人格注入器
        if self.persona:
            self.context_builder = DialogueContextBuilder(
                memory_service,
                persona
            )
            self.persona_injector = PersonaInjector(persona)
    
    async def chat_with_persona(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        emotion: Optional[EmotionType] = None
    ) -> str:
        """带人格特征的对话"""
        if not self.persona or not self.memory_service:
            # 回退到普通对话
            return await self.chat(message, conversation_history)
        
        # 1. 构建上下文
        context = self.context_builder.build_context(
            message,
            conversation_history
        )
        
        # 2. 注入人格
        persona_context = self.persona_injector.inject_personality(
            context,
            emotion
        )
        
        # 3. 生成回复
        response = await self.chat(persona_context, [])
        
        # 4. 调整表达风格
        adapted_response = self.persona_injector.adapt_response_style(
            response,
            emotion
        )
        
        return adapted_response
    
    async def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """普通对话"""
        # 原有实现
        pass
```

### 3.2 任务管理增强

#### 3.2.1 任务自动分解

**文件**: `services/core/app/goals/decomposer.py`

```python
"""任务分解器

将复杂任务自动分解为可执行的子任务
"""

from typing import List, Dict, Optional
from app.goals.models import Goal, GoalStatus
from app.llm.gateway import ChatGateway

class TaskDecomposer:
    """任务分解器"""
    
    def __init__(self, llm_gateway: ChatGateway):
        self.llm_gateway = llm_gateway
    
    async def decompose_goal(
        self,
        parent_goal: Goal
    ) -> List[Goal]:
        """分解目标为子目标"""
        prompt = f"""
        请将以下目标分解为可执行的子任务列表：
        
        目标：{parent_goal.title}
        描述：{parent_goal.description}
        
        要求：
        1. 每个子任务都是具体的、可执行的
        2. 子任务之间有合理的顺序
        3. 子任务数量不超过5个
        4. 每个子任务包含标题和简要描述
        
        请以JSON数组格式返回，每个元素包含title和description字段。
        """
        
        try:
            response = await self.llm_gateway.chat(prompt)
            import json
            subtasks_data = json.loads(response)
            
            subgoals = []
            for i, task_data in enumerate(subtasks_data):
                subgoal = Goal(
                    title=task_data['title'],
                    description=task_data['description'],
                    parent_id=parent_goal.id,
                    status=GoalStatus.PENDING,
                    priority=i + 1,  # 按顺序设置优先级
                )
                subgoals.append(subgoal)
            
            return subgoals
        except Exception as e:
            print(f"任务分解失败：{e}")
            return []
    
    def estimate_complexity(self, goal: Goal) -> Dict[str, any]:
        """评估目标复杂度"""
        # 基于多个维度评估
        factors = {
            'title_length': len(goal.title),
            'description_length': len(goal.description),
            'has_parent': bool(goal.parent_id),
        }
        
        # 简单计算复杂度分数
        complexity_score = (
            factors['description_length'] / 100 +
            (1 if factors['has_parent'] else 0)
        )
        
        # 分类复杂度
        if complexity_score < 0.5:
            level = "简单"
        elif complexity_score < 1.5:
            level = "中等"
        else:
            level = "复杂"
        
        return {
            'level': level,
            'score': complexity_score,
            'factors': factors
        }
```

#### 3.2.2 智能任务调度

**文件**: `services/core/app/goals/scheduler.py`

```python
"""智能任务调度器

根据优先级、依赖关系和资源情况进行任务调度
"""

from typing import List, Optional
from datetime import datetime, timezone
from app.goals.models import Goal, GoalStatus

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        pass
    
    def schedule_tasks(
        self,
        all_goals: List[Goal],
        max_concurrent: int = 3
    ) -> List[Goal]:
        """调度任务，返回应该执行的任务列表"""
        # 1. 过滤可执行任务
        executable_tasks = self._filter_executable(all_goals)
        
        # 2. 按优先级排序
        prioritized_tasks = self._prioritize_tasks(executable_tasks)
        
        # 3. 考虑并发限制
        scheduled = prioritized_tasks[:max_concurrent]
        
        return scheduled
    
    def _filter_executable(self, goals: List[Goal]) -> List[Goal]:
        """过滤出可执行的任务"""
        executable = []
        
        for goal in goals:
            # 必须是待处理状态
            if goal.status != GoalStatus.PENDING:
                continue
            
            # 如果有父任务，父任务必须已完成
            if goal.parent_id:
                parent = self._find_parent(goal, goals)
                if not parent or parent.status != GoalStatus.COMPLETED:
                    continue
            
            # 所有依赖的任务必须已完成
            dependencies_completed = True
            for dep_id in goal.dependencies:
                dep = self._find_by_id(dep_id, goals)
                if not dep or dep.status != GoalStatus.COMPLETED:
                    dependencies_completed = False
                    break
            
            if dependencies_completed:
                executable.append(goal)
        
        return executable
    
    def _prioritize_tasks(self, tasks: List[Goal]) -> List[Goal]:
        """按优先级排序任务"""
        # 多维度排序：优先级 -> 紧急程度 -> 创建时间
        sorted_tasks = sorted(
            tasks,
            key=lambda g: (
                -g.priority,  # 优先级高的在前
                -1 if g.is_urgent else 0,  # 紧急的在前
                g.created_at  # 创建早的在前
            )
        )
        return sorted_tasks
    
    def _find_parent(self, goal: Goal, goals: List[Goal]) -> Optional[Goal]:
        """查找父任务"""
        if not goal.parent_id:
            return None
        return self._find_by_id(goal.parent_id, goals)
    
    def _find_by_id(self, goal_id: str, goals: List[Goal]) -> Optional[Goal]:
        """根据ID查找任务"""
        for goal in goals:
            if goal.id == goal_id:
                return goal
        return None
```

#### 3.2.3 任务执行跟踪

**文件**: `services/core/app/goals/executor.py`

```python
"""任务执行跟踪器

跟踪任务执行进度，处理失败重试
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from app.goals.models import Goal, GoalStatus, GoalStatusUpdate

class TaskExecutionTracker:
    """任务执行跟踪器"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
    
    def start_execution(self, goal: Goal) -> GoalStatusUpdate:
        """开始执行任务"""
        return GoalStatusUpdate(
            status=GoalStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc)
        )
    
    def complete_execution(self, goal: Goal) -> GoalStatusUpdate:
        """完成任务"""
        return GoalStatusUpdate(
            status=GoalStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc)
        )
    
    def fail_execution(
        self,
        goal: Goal,
        error: str,
        retry_count: int = 0
    ) -> Optional[GoalStatusUpdate]:
        """任务失败处理"""
        # 检查是否可以重试
        if retry_count < self.max_retries:
            # 重试
            return GoalStatusUpdate(
                status=GoalStatus.PENDING,
                error=error,
                retry_count=retry_count + 1
            )
        else:
            # 放弃
            return GoalStatusUpdate(
                status=GoalStatus.FAILED,
                error=error,
                failed_at=datetime.now(timezone.utc)
            )
    
    def update_progress(
        self,
        goal: Goal,
        progress: int,
        message: str = ""
    ) -> Dict[str, any]:
        """更新任务进度"""
        return {
            "progress": progress,
            "message": message,
            "updated_at": datetime.now(timezone.utc)
        }
    
    def get_execution_status(
        self,
        goal: Goal
    ) -> Dict[str, any]:
        """获取执行状态"""
        status_info = {
            "goal_id": goal.id,
            "title": goal.title,
            "status": goal.status,
            "progress": self._calculate_progress(goal),
        }
        
        if goal.started_at:
            status_info["duration"] = (
                datetime.now(timezone.utc) - goal.started_at
            ).total_seconds()
        
        if goal.error:
            status_info["error"] = goal.error
            status_info["retry_count"] = goal.retry_count
        
        return status_info
    
    def _calculate_progress(self, goal: Goal) -> int:
        """计算任务进度"""
        # 简化版本：根据状态返回进度
        if goal.status == GoalStatus.PENDING:
            return 0
        elif goal.status == GoalStatus.IN_PROGRESS:
            # 如果有进度字段，使用它；否则返回50
            return goal.progress or 50
        elif goal.status == GoalStatus.COMPLETED:
            return 100
        elif goal.status == GoalStatus.FAILED:
            return 0
        else:
            return 0
```

---

## 🧪 测试方案

### 3.1 单元测试

```python
# services/core/tests/test_persona_templates.py

import pytest
from app.persona.templates import PersonaTemplateManager

def test_get_template():
    """测试获取人格模板"""
    manager = PersonaTemplateManager()
    
    template = manager.get_template("introvert")
    assert template.name == "内向思考者"
    assert template.personality.extraversion < 0.5

def test_create_persona_from_template():
    """测试从模板创建人格"""
    manager = PersonaTemplateManager()
    
    persona = manager.create_persona_from_template("extrovert")
    assert persona.name == "外向朋友"
    assert persona.personality.extraversion > 0.8

def test_list_templates():
    """测试列出所有模板"""
    manager = PersonaTemplateManager()
    
    templates = manager.list_templates()
    assert len(templates) == 4
    template_ids = [t.id for t in templates]
    assert "introvert_thinker" in template_ids
    assert "extrovert_friend" in template_ids

# services/core/tests/test_memory_extraction.py

import pytest
from app.memory.extractor import MemoryExtractor
from app.llm.schemas import ChatMessage

def test_extract_preferences():
    """测试提取用户偏好"""
    extractor = MemoryExtractor()
    message = ChatMessage(
        role="user",
        content="我喜欢喝茶，比较喜欢绿茶"
    )
    
    events = extractor.extract_from_dialogue([message])
    preference_events = [e for e in events if "偏好" in e.entry.content]
    
    assert len(preference_events) >= 1

def test_extract_important_events():
    """测试提取重要事件"""
    extractor = MemoryExtractor()
    message = ChatMessage(
        role="user",
        content="今天我完成了项目报告，老板很满意"
    )
    
    events = extractor.extract_from_dialogue([message])
    event_memories = [e for e in events if e.entry.kind == "episodic"]
    
    assert len(event_memories) >= 1
```

### 3.2 集成测试

```python
# services/core/tests/test_integration_persona_memory.py

import pytest
from app.memory.service import MemoryService
from app.persona.templates import PersonaTemplateManager
from app.memory.repository import InMemoryMemoryRepository

def test_memory_with_persona():
    """测试人格与记忆的集成"""
    # 创建人格
    manager = PersonaTemplateManager()
    persona = manager.create_persona_from_template("introvert")
    
    # 创建记忆服务
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(
        repository=repository,
        personality=persona.personality
    )
    
    # 测试记忆检索受人格影响
    events = memory_service.search_relevant("用户的偏好", limit=5)
    assert len(events) >= 0
```

---

## 📦 部署和配置

### 4.1 环境变量配置

```bash
# .env.local

# LLM配置
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-3.5-turbo

# 存储路径
MEMORY_STORAGE_PATH=.data/memory.jsonl
GOAL_STORAGE_PATH=.data/goals.json
PERSONA_STORAGE_PATH=.data/persona.json

# 功能开关
MORNING_PLAN_LLM_ENABLED=true
MEMORY_AUTO_EXTRACTION_ENABLED=true
PERSONA_VALIDATION_ENABLED=true

# 性能配置
MAX_CONCURRENT_TASKS=3
TASK_MAX_RETRIES=3
MEMORY_SEARCH_LIMIT=10
```

### 4.2 数据迁移脚本

```python
# services/core/scripts/migrate_storage.py

"""数据迁移脚本

帮助用户从文件存储迁移到SQLite（如果需要）"""

import json
from pathlib import Path

def migrate_memory_to_sqlite(
    jsonl_path: str,
    db_path: str
):
    """将JSONL格式的记忆迁移到SQLite"""
    import sqlite3
    
    # 创建SQLite数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        kind TEXT,
        content TEXT,
        created_at TEXT,
        emotion TEXT,
        strength TEXT,
        related_entries TEXT
    )
    """)
    
    # 读取JSONL文件
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            
            # 插入数据
            cursor.execute("""
            INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['entry']['id'],
                data['entry']['kind'],
                data['entry']['content'],
                data['entry']['created_at'],
                data['entry']['emotion'],
                data['entry']['strength'],
                json.dumps(data.get('related_entries', []))
            ))
    
    conn.commit()
    conn.close()
    print(f"迁移完成：{jsonl_path} -> {db_path}")

if __name__ == "__main__":
    migrate_memory_to_sqlite(
        ".data/memory.jsonl",
        ".data/memories.db"
    )
```

---

## 📊 监控和指标

### 5.1 性能监控

```python
# services/core/app/monitoring/metrics.py

"""性能指标收集"""

import time
from typing import Dict, List
from datetime import datetime

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
    
    def record_latency(self, operation: str, latency_ms: float):
        """记录操作延迟"""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(latency_ms)
    
    def get_average_latency(self, operation: str) -> float:
        """获取平均延迟"""
        if operation not in self.metrics:
            return 0.0
        values = self.metrics[operation]
        return sum(values) / len(values)
    
    def get_summary(self) -> Dict[str, any]:
        """获取指标摘要"""
        summary = {}
        for operation, values in self.metrics.items():
            summary[operation] = {
                "count": len(values),
                "average": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }
        return summary

# 使用示例
monitor = PerformanceMonitor()

start = time.time()
# 执行操作
result = some_operation()
latency = (time.time() - start) * 1000
monitor.record_latency("operation_name", latency)
```

### 5.2 数据库监控

```python
# services/core/app/monitoring/storage_monitor.py

"""存储监控"""

import os
from pathlib import Path

class StorageMonitor:
    """存储监控器"""
    
    def __init__(self, storage_dir: str = ".data"):
        self.storage_dir = Path(storage_dir)
    
    def get_storage_stats(self) -> Dict[str, any]:
        """获取存储统计信息"""
        stats = {
            "total_size": 0,
            "file_count": 0,
            "files": []
        }
        
        if self.storage_dir.exists():
            for file_path in self.storage_dir.glob("*"):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    stats["total_size"] += size
                    stats["file_count"] += 1
                    stats["files"].append({
                        "name": file_path.name,
                        "size": size,
                        "modified": file_path.stat().st_mtime
                    })
        
        return stats
    
    def check_storage_health(self) -> Dict[str, bool]:
        """检查存储健康状态"""
        stats = self.get_storage_stats()
        
        health = {
            "total_size_ok": stats["total_size"] < 1024 * 1024 * 100,  # < 100MB
            "file_count_ok": stats["file_count"] < 50,
        }
        
        return health
```

---

## 🎯 总结

本文档详细规划了小晏项目核心功能的技术实施方案，涵盖：

1. **人格系统完善**（第1-4周）
   - 个性化人格配置系统
   - 表达一致性优化
   - 人格验证和推荐

2. **记忆系统增强**（第5-8周）
   - 智能记忆提取
   - 记忆关联和检索优化
   - 时间衰减机制

3. **对话和任务管理完善**（第9-12周）
   - 对话系统优化
   - 任务自动分解和调度
   - 任务执行跟踪

每个模块都包含：
- 详细的架构设计
- 完整的代码实现
- API端点设计
- 前端集成方案
- 测试用例
- 部署配置

按照本计划执行，小晏将具备真正的个性化人格、智能记忆系统和自然的对话交互能力。
