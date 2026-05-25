from abc import ABC, abstractmethod

from src.schemas import AnalysisRequest, AnalysisResponse


class BehaviorAnalyzer(ABC):
    """行为心理分析器的抽象基类。

    所有接入端（CLI、MCP Server、OpenClaw Plugin）都应实例化此类的具体实现，
    组装 AnalysisRequest，调用 analyze()，返回 AnalysisResponse。

    该抽象层确保核心分析逻辑与接入层完全解耦，便于在不同生态中复用同一套
    心理分析引擎，同时保持输入输出契约的一致性。
    """

    @abstractmethod
    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """对给定的行为描述请求执行心理分析。

        Args:
            request: 标准化的分析请求，包含行为描述、对象 ID、上下文与追踪 ID。

        Returns:
            标准化的分析响应，包含标签、心理机制、替代解释、置信度、
            普适性评级与免责声明。
        """
        ...
