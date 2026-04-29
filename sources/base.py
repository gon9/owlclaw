"""
owlclaw: Sourceプラグイン基底クラス定義。

各Sourceプラグインはこのクラスを継承し、fetch() を実装する。
"""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseSource(ABC):
    """全Sourceプラグインの基底クラス。"""

    @abstractmethod
    def fetch(self, config: dict, cutoff: datetime) -> str:
        """
        イベントを取得してMarkdown文字列として返す。

        Parameters
        ----------
        config : dict
            ソース設定（sources.yaml の内容など）
        cutoff : datetime
            これより古い記事は除外する閾値（UTC aware）

        Returns
        -------
        str
            Markdown形式のイベント一覧テキスト
        """
