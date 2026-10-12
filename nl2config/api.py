"""稳定 API 表面：baseline（缺陷版）与最终态共用同一组签名，
使同一套测试可以在两版之间构成回归对比（docs/06 回归记录的依据）。
"""
from .generator import GenerationResult, generate_config
from .golden import run_golden_regression
from .patch_engine import PatchResult, apply_patch

__all__ = ["GenerationResult", "generate_config", "PatchResult", "apply_patch",
           "run_golden_regression"]
