"""
TTS 语音合成 Action
"""

from typing import ClassVar

from src.chat.utils.self_voice_cache import register_self_voice
from src.common.logger import get_logger
from src.plugin_system.base.base_action import BaseAction, ChatMode

from ..services.manager import get_service

logger = get_logger("tts_voice_plugin.action")


class TTSVoiceAction(BaseAction):
    """
    通过关键词或规划器自动触发 TTS 语音合成
    """

    action_name = "tts_voice_action"
    action_description = "将你生成好的文本转换为语音并发送。注意：这是纯语音合成，只能说话，不能唱歌！"

    mode_enable = ChatMode.ALL
    parallel_action = False

    action_parameters: ClassVar[dict] = {
        "tts_voice_text": {
            "type": "string",
            "description": "需要转换为语音并发送的完整、自然、适合口语的文本内容。注意：只能是说话内容，不能是歌词或唱歌！",
            "required": True
        },
        "voice_style": {
            "type": "string",
            "description": "语音的风格。请根据对话的情感和上下文选择一个最合适的风格。如果未提供，将使用默认风格。",
            "required": False
        },
        "text_language": {
            "type": "string",
            "description": (
                "指定用于合成的语言模式，请务必根据文本内容选择最精确、范围最小的选项以获得最佳效果。"
                "可用选项说明：\n"
                "- 'zh': 中文与英文混合 (最优选)\n"
                "- 'ja': 日文与英文混合 (最优选)\n"
                "- 'yue': 粤语与英文混合 (最优选)\n"
                "- 'ko': 韩文与英文混合 (最优选)\n"
                "- 'en': 纯英文\n"
                "- 'all_zh': 纯中文\n"
                "- 'all_ja': 纯日文\n"
                "- 'all_yue': 纯粤语\n"
                "- 'all_ko': 纯韩文\n"
                "- 'auto': 多语种混合自动识别 (备用选项，当前两种语言时优先使用上面的精确选项)\n"
                "- 'auto_yue': 多语种混合自动识别（包含粤语）(备用选项)"
            ),
            "required": False
        }
    }

    action_require: ClassVar[list] = [
        "【核心限制】此动作只能用于说话，绝对不能用于唱歌！TTS无法发出有音调的歌声，只会输出平淡的念白。如果用户要求唱歌，不要使用此动作！",
        "在调用此动作时，你必须在 'tts_voice_text' 参数中提供要合成语音的完整回复内容。这是强制性的。",
        "当用户明确请求使用语音进行回复时，例如'发个语音听听'、'用语音说'等。",
        "当对话内容适合用语音表达，例如讲故事、念诗、撒嬌或进行角色扮演时。",
        "在表达特殊情感（如安慰、鼓励、庆祝）的场景下，可以主动使用语音来增强感染力。",
        "不要在日常的、简短的问答或闲聊中频繁使用语音，避免打扰用户。",
        "提供的 'tts_voice_text' 内容必须是纯粹的对话，不能包含任何括号或方括号括起来的动作、表情、或场景描述（例如，不要出现 '(笑)' 或 '[歪头]'）",
        "**重要**：此动作专为语音合成设计，因此 'tts_voice_text' 参数的内容必须是纯净、标准的口语文本。请务必抑制你通常的、富有表现力的文本风格，不要使用任何辅助聊天或增强视觉效果的特殊符号（例如 '♪', '～', '∽', '☆' 等），因为它们无法被正确合成为语音。",
        "【**最终规则**】'tts_voice_text' 参数中，所有句子和停顿【必须】使用且只能使用以下四个标准标点符号：'，' (逗号)、'。' (句号)、'？' (问号)、'！' (叹号)。任何其他符号，特别是 '...'、'～' 以及任何表情符号或装饰性符号，都【严禁】出现，否则将导致语音合成严重失败。"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 关键配置项现在由 TTSService 管理
        self.tts_service = get_service("tts")
        
        # 动态更新 voice_style 参数描述（包含可用风格）
        self._update_voice_style_parameter()

    def _update_voice_style_parameter(self):
        """动态更新 voice_style 参数描述，包含实际可用的风格选项"""
        try:
            available_styles = self._get_available_styles_safe()
            if available_styles:
                styles_list = "、".join(available_styles)
                updated_description = (
                    f"语音的风格。请根据对话的情感和上下文选择一个最合适的风格。"
                    f"当前可用风格：{styles_list}。如果未提供，将使用默认风格。"
                )
                # 更新实例的参数描述
                self.action_parameters["voice_style"]["description"] = updated_description
                logger.debug(f"{self.log_prefix} 已更新语音风格参数描述，包含 {len(available_styles)} 个可用风格")
            else:
                logger.warning(f"{self.log_prefix} 无法获取可用语音风格，使用默认参数描述")
        except Exception as e:
            logger.error(f"{self.log_prefix} 更新语音风格参数时出错: {e}")

    def _get_available_styles_safe(self) -> list[str]:
        """安全地获取可用语音风格列表"""
        try:
            # 首先尝试从TTS服务获取
            if hasattr(self.tts_service, 'get_available_styles'):
                styles = self.tts_service.get_available_styles()
                if styles:
                    return styles
            
            # 回退到通过插件配置获取（不再使用硬编码路径）
            styles_config = self.get_config('tts_styles', [])
            
            if isinstance(styles_config, list):
                style_names = []
                for style in styles_config:
                    if isinstance(style, dict):
                        name = style.get('style_name')
                        if isinstance(name, str) and name:
                            style_names.append(name)
                return style_names if style_names else ['default']
        except Exception as e:
            logger.debug(f"{self.log_prefix} 获取可用语音风格时出错: {e}")
        
        return ['default']  # 安全回退

    @classmethod
    def get_action_info(cls) -> "ActionInfo":
        """重写获取Action信息的方法，动态更新参数描述"""
        # 先调用父类方法获取基础信息
        info = super().get_action_info()
        
        # 尝试动态更新 voice_style 参数描述
        try:
            # 尝试获取可用风格（不创建完整实例）
            available_styles = cls._get_available_styles_for_info()
            if available_styles:
                styles_list = "、".join(available_styles)
                updated_description = (
                    f"语音的风格。请根据对话的情感和上下文选择一个最合适的风格。"
                    f"当前可用风格：{styles_list}。如果未提供，将使用默认风格。"
                )
                # 更新参数描述
                info.action_parameters["voice_style"]["description"] = updated_description
        except Exception as e:
            logger.debug(f"[TTSVoiceAction] 在获取Action信息时更新参数描述失败: {e}")
        
        return info

    @classmethod 
    def _get_available_styles_for_info(cls) -> list[str]:
        """为 get_action_info 方法获取可用风格（类方法版本）
        
        由于这是类方法，无法访问插件实例，所以只能返回默认值。
        真正的风格列表会在运行时动态更新到action_info中。
        """
        # 类方法无法访问插件配置，返回通用默认值
        # 实际的风格列表会在实例方法get_action_info中动态更新
        return ['default']  # 安全回退

    async def go_activate(self, llm_judge_model=None) -> bool:
        """
        判断此 Action 是否应该被激活。
        满足以下任一条件即可激活：
        1. 55% 的随机概率
        2. 匹配到预设的关键词
        3. LLM 判断当前场景适合发送语音
        """
        # 条件1: 随机激活
        if await self._random_activation(0.25):
            logger.info(f"{self.log_prefix} 随机激活成功 (25%)")
            return True

        # 条件2: 关键词激活
        keywords = [
            "发语音", "语音", "说句话", "用语音说", "听你", "听声音", "想你", "想听声音",
            "讲个话", "说段话", "念一下", "读一下", "用嘴说", "说", "能发语音吗", "亲口"
        ]
        if await self._keyword_match(keywords):
            logger.info(f"{self.log_prefix} 关键词激活成功")
            return True

        # 条件3: LLM 判断激活
        # 注意：这里我们复用 action_require 里的描述，让 LLM 的判断更精准
        if await self._llm_judge_activation(
            llm_judge_model=llm_judge_model
        ):
            logger.info(f"{self.log_prefix} LLM 判断激活成功")
            return True

        logger.debug(f"{self.log_prefix} 所有激活条件均未满足，不激活")
        return False

    async def execute(self) -> tuple[bool, str]:
        """
        执行 Action 的核心逻辑
        """
        try:
            if not self.tts_service:
                logger.error(f"{self.log_prefix} TTSService 未注册或初始化失败，静默处理。")
                return False, "TTSService 未注册或初始化失败"

            initial_text = self.action_data.get("tts_voice_text", "").strip()
            voice_style = self.action_data.get("voice_style", "default")
            # 新增：从决策模型获取指定的语言模式
            text_language = self.action_data.get("text_language") # 如果模型没给，就是 None
            logger.info(f"{self.log_prefix} 接收到规划器初步文本: '{initial_text[:70]}...', 指定风格: {voice_style}, 指定语言: {text_language}")

            # 1. 使用规划器提供的文本
            text = initial_text
            if not text:
                logger.warning(f"{self.log_prefix} 规划器提供的文本为空，静默处理。")
                return False, "规划器提供的文本为空"

            # 2. 调用 TTSService 生成语音
            logger.info(f"{self.log_prefix} 使用最终文本进行语音合成: '{text[:70]}...'")
            audio_b64 = await self.tts_service.generate_voice(
                text=text,
                style_hint=voice_style,
                language_hint=text_language  # 新增：将决策模型指定的语言传递给服务
            )

            if audio_b64:
                # 在发送语音前，将文本注册到缓存中
                register_self_voice(audio_b64, text)
                await self.send_custom(message_type="voice", content=audio_b64)
                logger.info(f"{self.log_prefix} GPT-SoVITS语音发送成功")
                await self.store_action_info(
                    action_prompt_display=f"将文本转换为语音并发送 (风格:{voice_style})",
                    action_done=True
                )
                return True, f"成功生成并发送语音，文本长度: {len(text)}字符"
            else:
                logger.error(f"{self.log_prefix} TTS服务未能返回音频数据，静默处理。")
                await self.store_action_info(
                    action_prompt_display="语音合成失败: TTS服务未能返回音频数据",
                    action_done=False
                )
                return False, "语音合成失败"

        except Exception as e:
            logger.error(f"{self.log_prefix} 语音合成过程中发生未知错误: {e!s}")
            await self.store_action_info(
                action_prompt_display=f"语音合成失败: {e!s}",
                action_done=False
            )
            return False, f"语音合成出错: {e!s}"

