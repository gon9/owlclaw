"""
owlclaw: Sourceプラグイン基底クラス定義。

各Sourceプラグインはこのクラスを継承し、fetch() を実装する。
"""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseSource(ABC):
    """全Sourceプラグインの基底クラス。"""

    @abstractmethod
    def fetch(
        self,
        config: dict,
        cutoff: datetime,
        last_seen_per_source: dict | None = None,
    ) -> tuple[str, dict]:
        """
        イベントを取得してMarkdown文字列と最終既読日時辞書を返す。

        Parameters
        ----------
        config : dict
            ソース設定（sources.yaml の内容など）
        cutoff : datetime
            これより古い記事は除外するグローバル閾値（UTC aware）
        last_seen_per_source : dict | None
            ソース名 → 最終既読日時 ISO 文字列。指定時は各ソース個別に
            max(cutoff, last_seen) を有効カットオフとして使用する。

        Returns
        -------
        tuple[str, dict]
            (Markdown テキスト, {source_name: latest_pub_iso_str})
        """
