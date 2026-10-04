"""Explicit Runnable for application nodes that contain no nested graphs."""
from langchain_core.runnables import Runnable, RunnableConfig


class FlatNode(Runnable):
    # LangGraph accepts public Runnable nodes. Keeping a plain custom Runnable
    # avoids discovering nonexistent subgraphs by walking closure bytecode,
    # a path observed in intermittent native interpreter failures here.
    def __init__(self, function, *, takes_config=False):
        self.function = function
        self.takes_config = takes_config

    def invoke(self, input, config: RunnableConfig | None = None, **kwargs):
        return self.function(input,config or {}) if self.takes_config else self.function(input)
