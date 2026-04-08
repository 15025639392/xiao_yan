"""人格模板系统测试

测试人格模板管理器和验证器
"""

import pytest
from app.persona.templates import (
    PersonaTemplateManager,
    PERSONA_TYPES,
    PERSONA_TEMPLATES
)
from app.persona.validator import PersonaValidator


class TestPersonaTemplateManager:
    """测试人格模板管理器"""
    
    def test_get_template_introvert(self):
        """测试获取内向型人格模板"""
        manager = PersonaTemplateManager()
        template = manager.get_template("introvert")
        
        assert template.id == "introvert_thinker"
        assert template.name == "内向思考者"
        assert template.personality.extraversion < 50
        assert template.personality.conscientiousness > 70
    
    def test_get_template_extrovert(self):
        """测试获取外向型人格模板"""
        manager = PersonaTemplateManager()
        template = manager.get_template("extrovert")
        
        assert template.id == "extrovert_friend"
        assert template.name == "外向朋友"
        assert template.personality.extraversion > 80
        assert template.personality.agreeableness > 70
    
    def test_get_template_professional(self):
        """测试获取专业型人格模板"""
        manager = PersonaTemplateManager()
        template = manager.get_template("professional")
        
        assert template.id == "professional_assistant"
        assert template.name == "专业助手"
        assert template.personality.conscientiousness > 80
        assert template.personality.neuroticism < 30
    
    def test_get_template_playful(self):
        """测试获取活泼型人格模板"""
        manager = PersonaTemplateManager()
        template = manager.get_template("playful")
        
        assert template.id == "playful_companion"
        assert template.name == "活泼伙伴"
        assert template.personality.openness > 80
        assert template.personality.extraversion > 70
    
    def test_get_template_invalid_type(self):
        """测试获取不存在的人格类型"""
        manager = PersonaTemplateManager()
        
        with pytest.raises(ValueError, match="Unknown persona type"):
            manager.get_template("invalid_type")
    
    def test_list_templates(self):
        """测试列出所有模板"""
        manager = PersonaTemplateManager()
        templates = manager.list_templates()
        
        assert len(templates) == 4
        template_ids = [t.id for t in templates]
        assert "introvert_thinker" in template_ids
        assert "extrovert_friend" in template_ids
        assert "professional_assistant" in template_ids
        assert "playful_companion" in template_ids
    
    def test_create_persona_from_template(self):
        """测试从模板创建人格"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        
        assert persona.name == "内向思考者"
        assert persona.personality.extraversion < 50
        assert persona.speaking_style.formal_level == "neutral"
        assert len(persona.values.core_values) >= 3
        assert len(persona.values.boundaries) >= 3
    
    def test_create_persona_with_customizations(self):
        """测试从模板创建人格并应用自定义配置"""
        manager = PersonaTemplateManager()
        
        customizations = {
            "name": "自定义人格",
            "identity": "我是一个自定义的数字伙伴"
        }
        
        persona = manager.create_persona_from_template(
            "extrovert",
            customizations
        )
        
        assert persona.name == "自定义人格"
        assert persona.identity == "我是一个自定义的数字伙伴"
        # 基础人格特征应该保持不变
        assert persona.personality.extraversion > 80
        assert len(persona.values.core_values) >= 3

    def test_all_templates_share_same_value_foundation(self):
        """测试所有人格模板共享同一套价值底盘"""
        manager = PersonaTemplateManager()

        introvert = manager.create_persona_from_template("introvert")
        extrovert = manager.create_persona_from_template("extrovert")

        assert [item.name for item in introvert.values.core_values] == [
            item.name for item in extrovert.values.core_values
        ]
        assert introvert.values.boundaries == extrovert.values.boundaries
    
    def test_compare_personas_similar(self):
        """测试比较相似的人格"""
        manager = PersonaTemplateManager()
        
        persona1 = manager.create_persona_from_template("introvert")
        persona2 = manager.create_persona_from_template("introvert")
        
        result = manager.compare_personas(persona1, persona2)
        
        assert "similarity_score" in result
        assert "dimension_differences" in result
        # 同一个模板的人格应该非常相似
        assert result["similarity_score"] > 0.9
    
    def test_compare_personas_different(self):
        """测试比较不同的人格"""
        manager = PersonaTemplateManager()
        
        persona1 = manager.create_persona_from_template("introvert")
        persona2 = manager.create_persona_from_template("extrovert")
        
        result = manager.compare_personas(persona1, persona2)
        
        assert "similarity_score" in result
        assert "dimension_differences" in result
        # 内向和外向人格应该有较大差异
        assert result["similarity_score"] < 0.8
        # 外向性维度应该差异很大
        assert result["dimension_differences"]["extraversion"] > 50
    
    def test_recommend_persona_professional(self):
        """测试推荐专业型人格"""
        manager = PersonaTemplateManager()
        
        preferences = {
            "formality": 0.8,
            "interaction": 0.5
        }
        
        recommended = manager.recommend_persona(preferences)
        
        assert recommended == "professional"
    
    def test_recommend_persona_extrovert(self):
        """测试推荐外向型人格"""
        manager = PersonaTemplateManager()
        
        preferences = {
            "formality": 0.3,
            "interaction": 0.8
        }
        
        recommended = manager.recommend_persona(preferences)
        
        assert recommended == "extrovert"
    
    def test_recommend_persona_introvert(self):
        """测试推荐内向型人格"""
        manager = PersonaTemplateManager()
        
        preferences = {
            "formality": 0.5,
            "interaction": 0.2
        }
        
        recommended = manager.recommend_persona(preferences)
        
        assert recommended == "introvert"
    
    def test_recommend_persona_playful(self):
        """测试推荐活泼型人格"""
        manager = PersonaTemplateManager()
        
        preferences = {
            "formality": 0.4,
            "interaction": 0.5
        }
        
        recommended = manager.recommend_persona(preferences)
        
        assert recommended == "playful"


class TestPersonaValidator:
    """测试人格验证器"""
    
    def test_validate_valid_persona(self):
        """测试验证有效的人格配置"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        
        validator = PersonaValidator()
        is_valid, errors = validator.validate_persona(persona)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_missing_name(self):
        """测试验证缺少名称的人格"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        persona.name = ""
        
        validator = PersonaValidator()
        is_valid, errors = validator.validate_persona(persona)
        
        assert is_valid is False
        assert any("名称不能为空" in error for error in errors)
    
    def test_validate_missing_identity(self):
        """测试验证缺少身份描述的人格"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        persona.identity = ""
        
        validator = PersonaValidator()
        is_valid, errors = validator.validate_persona(persona)
        
        assert is_valid is False
        assert any("身份描述不能为空" in error for error in errors)
    
    def test_validate_dimension_out_of_range(self):
        """测试验证性格维度超出范围的人格"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        persona.personality.openness = 150
        
        validator = PersonaValidator()
        is_valid, errors = validator.validate_persona(persona)
        
        assert is_valid is False
        assert any("openness" in error for error in errors)
    
    def test_validate_dimensions_balance(self):
        """测试验证性格维度平衡"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        
        validator = PersonaValidator()
        is_balanced = validator.validate_dimensions_balance(persona.personality)
        
        # 预设模板应该是平衡的
        assert is_balanced is True
    
    def test_get_validation_report(self):
        """测试获取验证报告"""
        manager = PersonaTemplateManager()
        persona = manager.create_persona_from_template("introvert")
        
        validator = PersonaValidator()
        report = validator.get_validation_report(persona)
        
        assert "is_valid" in report
        assert "errors" in report
        assert "warnings" in report
        assert "suggestions" in report
        assert report["is_valid"] is True


class TestPersonaTemplatesStructure:
    """测试人格模板数据结构"""
    
    def test_all_templates_have_required_fields(self):
        """测试所有模板都有必需的字段"""
        required_fields = ["id", "name", "description", "personality", "speaking_style", "identity", "values", "example_dialogues"]
        
        # 使用实际的有效值列表
        persona_type_list = ["introvert", "extrovert", "professional", "playful"]
        
        for persona_type in persona_type_list:
            template = PERSONA_TEMPLATES[persona_type]
            
            for field in required_fields:
                assert hasattr(template, field), f"Template {persona_type} missing field {field}"
    
    def test_all_personality_dimensions_in_range(self):
        """测试所有人格模板的性格维度都在有效范围内"""
        persona_type_list = ["introvert", "extrovert", "professional", "playful"]
        
        for persona_type in persona_type_list:
            template = PERSONA_TEMPLATES[persona_type]
            dims = template.personality
            
            assert 0 <= dims.openness <= 100
            assert 0 <= dims.conscientiousness <= 100
            assert 0 <= dims.extraversion <= 100
            assert 0 <= dims.agreeableness <= 100
            assert 0 <= dims.neuroticism <= 100
    
    def test_all_templates_have_examples(self):
        """测试所有模板都有示例对话"""
        persona_type_list = ["introvert", "extrovert", "professional", "playful"]
        
        for persona_type in persona_type_list:
            template = PERSONA_TEMPLATES[persona_type]
            
            assert len(template.example_dialogues) >= 3
    
    def test_template_personalities_are_distinct(self):
        """测试不同模板的性格特征有明显差异"""
        introvert = PERSONA_TEMPLATES["introvert"].personality
        extrovert = PERSONA_TEMPLATES["extrovert"].personality
        
        # 外向性应该差异很大
        assert abs(introvert.extraversion - extrovert.extraversion) > 50
