import asyncio
import random
from datetime import datetime

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter
from astrbot.api.event import AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

@register(
    "Dynamic Persona - 动态人格",
    "LumineStory",
    "一个为机器人赋予动态、情景感知人格的创新插件。",
    "1.0.0",
    "https://github.com/oyxning/astrbot_plugin_dynamic_persona"
)
class DynamicPersonaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 用于追踪每个会话的消息计数
        self.session_message_counts = {}

    @filter.on_llm_request(priority=100)
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        在LLM请求前触发，动态生成并注入新人格。
        """
        if not self.config.get("enabled", True):
            return

        session_id = event.unified_msg_origin
        
        # 更新会话消息计数
        current_count = self.session_message_counts.get(session_id, 0) + 1
        self.session_message_counts[session_id] = current_count

        # 根据配置的更新频率决定是否触发人格生成
        update_frequency = self.config.get("update_frequency", 1)
        if current_count % update_frequency != 0:
            return

        logger.info(f"触发动态人格生成... (会话: {session_id}, 第 {current_count} 条消息)")

        # 1. 构造情景信息
        context_info = f"- 用户最新消息: \"{req.prompt}\""
        if self.config.get("include_time", True):
            context_info += f"\n- 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 2. 获取用于生成人格的LLM
        persona_provider_id = self.config.get("persona_provider_id")
        if persona_provider_id:
            persona_llm = self.context.get_provider_by_id(persona_provider_id)
            if not persona_llm:
                logger.warning(f"找不到指定的人格生成LLM: {persona_provider_id}，将使用主LLM。")
                persona_llm = self.context.get_using_provider()
        else:
            persona_llm = self.context.get_using_provider()

        if not persona_llm:
            logger.error("动态人格生成失败：无可用LLM。")
            return
            
        # 3. 发起“灵感请求”
        try:
            generation_prompt_template = self.config.get("custom_generation_prompt")
            final_prompt = generation_prompt_template.format(context_info=context_info)

            response = await persona_llm.text_chat(
                prompt=final_prompt,
                contexts=[], # 人格生成不依赖历史上下文
                system_prompt="" # 使用模板中的指令
            )
            
            new_persona = response.completion_text.strip().replace("\n", " ")
            if not new_persona:
                logger.warning("人格生成LLM返回了空内容。")
                return

            # 4. 注入新人格
            logger.info(f"✨ 动态生成的新人格: 【{new_persona}】")
            # 将新生成的人格加在原有系统提示词之前
            original_system_prompt = req.system_prompt or ""
            req.system_prompt = f"{new_persona}\n{original_system_prompt}".strip()

        except Exception as e:
            logger.error(f"动态人格生成过程中发生错误: {e}")

    async def terminate(self):
        self.session_message_counts.clear()
        logger.info("动态人格插件已终止。")