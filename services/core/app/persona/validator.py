"""人格配置验证器

验证人格配置的有效性和一致性
"""

from typing import List
from app.persona.models import PersonaProfile, PersonalityDimensions

class PersonaValidator:
    """人格配置验证器"""
    
    @staticmethod
    def validate_persona(persona: PersonaProfile) -> tuple[bool, List[str]]:
        """验证人格配置，返回 (是否有效, 错误列表)"""
        errors = []
        
        # 1. 验证性格维度范围（0-100）
        personality = persona.personality
        dims = [
            ('openness', personality.openness),
            ('conscientiousness', personality.conscientiousness),
            ('extraversion', personality.extraversion),
            ('agreeableness', personality.agreeableness),
            ('neuroticism', personality.neuroticism),
        ]
        
        for name, value in dims:
            if not 0 <= value <= 100:
                errors.append(f"{name} 必须在 0-100 范围内，当前值为 {value}")
        
        # 2. 验证必填字段
        if not persona.name or not persona.name.strip():
            errors.append("人格名称不能为空")
        
        if not persona.identity or not persona.identity.strip():
            errors.append("身份描述不能为空")
        
        # 3. 验证一致性
        # 高外向性 + 正式度 = 不一致
        if personality.extraversion > 80 and persona.speaking_style.formal_level == "very_formal":
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
        
        # 总和在 250-400 之间是合理的（50 * 5 = 250, 80 * 5 = 400）
        return 250 <= total <= 400
    
    @staticmethod
    def get_validation_report(persona: PersonaProfile) -> dict:
        """生成详细的验证报告"""
        is_valid, errors = PersonaValidator.validate_persona(persona)
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": PersonaValidator._generate_warnings(persona),
            "suggestions": PersonaValidator._generate_suggestions(persona)
        }
    
    @staticmethod
    def _generate_warnings(persona: PersonaProfile) -> List[str]:
        """生成配置警告"""
        warnings = []
        personality = persona.personality
        
        if personality.neuroticism > 80:
            warnings.append("高神经质可能导致情绪波动较大")
        
        if personality.conscientiousness < 30:
            warnings.append("低尽责性可能影响任务完成质量")
        
        return warnings
    
    @staticmethod
    def _generate_suggestions(persona: PersonaProfile) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        personality = persona.personality
        style = persona.speaking_style
        
        if personality.extraversion > 70 and style.sentence_style == "long":
            suggestions.append("高外向性人格可以考虑使用短句风格，更符合表达习惯")
        
        if personality.openness > 70 and style.expression_habit == "direct":
            suggestions.append("高开放性人格可以使用比喻等更丰富的表达方式")
        
        return suggestions
