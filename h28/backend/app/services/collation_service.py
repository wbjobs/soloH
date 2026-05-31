from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
from datetime import datetime
from app.repositories.collation_repository import CollationRepository
from app.repositories.result_repository import ResultRepository
from app.models.collation import Collation
from app.models.text_line import TextLine


VARIANT_CHARACTERS: Dict[str, List[str]] = {
    '于': ['於'],
    '无': ['無'],
    '万': ['萬'],
    '礼': ['禮'],
    '体': ['體'],
    '后': ['後'],
    '里': ['裏'],
    '云': ['雲'],
    '才': ['纔'],
    '丰': ['豐'],
    '制': ['製'],
    '准': ['準'],
    '冲': ['衝'],
    '尽': ['盡', '儘'],
    '划': ['劃'],
    '合': ['閤'],
    '回': ['迴'],
    '伙': ['夥'],
    '刮': ['颳'],
    '姜': ['薑'],
    '说': ['悦'],
    '脩': ['修'],
    '彊': ['强'],
    '叚': ['假'],
    '徧': ['遍'],
    '莫': ['暮'],
    '景': ['影'],
    '知': ['智'],
    '反': ['返'],
    '取': ['娶'],
}


class CollationService:
    def __init__(
        self,
        collation_repository: CollationRepository,
        result_repository: ResultRepository
    ):
        self.collation_repository = collation_repository
        self.result_repository = result_repository
        self._match_score = 2
        self._mismatch_score = -1
        self._gap_score = -2

    def _is_variant(self, char1: str, char2: str) -> bool:
        if char1 == char2:
            return True
        variants = VARIANT_CHARACTERS.get(char1, [])
        if char2 in variants:
            return True
        variants = VARIANT_CHARACTERS.get(char2, [])
        if char1 in variants:
            return True
        return False

    def _char_compare_score(self, a: str, b: str) -> int:
        if a == b:
            return self._match_score
        if self._is_variant(a, b):
            return self._match_score - 1
        return self._mismatch_score

    def align_pages(
        self,
        base_text_lines: List[TextLine],
        compared_text_lines: List[TextLine]
    ) -> Tuple[List[Dict[str, Any]], float]:
        base_chars: List[Tuple[str, int, int]] = []
        compared_chars: List[Tuple[str, int, int]] = []

        for line_idx, line in enumerate(base_text_lines):
            if line.content:
                for char_idx, char in enumerate(line.content):
                    base_chars.append((char, line_idx, char_idx))

        for line_idx, line in enumerate(compared_text_lines):
            if line.content:
                for char_idx, char in enumerate(line.content):
                    compared_chars.append((char, line_idx, char_idx))

        m = len(base_chars)
        n = len(compared_chars)

        if m == 0 or n == 0:
            return [], 0.0

        dp = [[0] * (n + 1) for _ in range(m + 1)]
        traceback = [[None] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i * self._gap_score
            traceback[i][0] = 'up'
        for j in range(n + 1):
            dp[0][j] = j * self._gap_score
            traceback[0][j] = 'left'

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                base_char = base_chars[i - 1][0]
                comp_char = compared_chars[j - 1][0]
                match = dp[i - 1][j - 1] + self._char_compare_score(base_char, comp_char)
                delete = dp[i - 1][j] + self._gap_score
                insert = dp[i][j - 1] + self._gap_score

                max_score = max(match, delete, insert)
                dp[i][j] = max_score

                if max_score == match:
                    traceback[i][j] = 'diag'
                elif max_score == delete:
                    traceback[i][j] = 'up'
                else:
                    traceback[i][j] = 'left'

        alignment: List[Dict[str, Any]] = []
        i, j = m, n
        while i > 0 or j > 0:
            direction = traceback[i][j]
            if direction == 'diag':
                i -= 1
                j -= 1
                base_char, base_line, base_col = base_chars[i]
                comp_char, comp_line, comp_col = compared_chars[j]
                is_variant = self._is_variant(base_char, comp_char)
                alignment.append({
                    'type': 'match' if base_char == comp_char else ('variant' if is_variant else 'mismatch'),
                    'base_char': base_char,
                    'compared_char': comp_char,
                    'base_pos': {'line': base_line, 'col': base_col},
                    'compared_pos': {'line': comp_line, 'col': comp_col},
                    'is_variant': is_variant
                })
            elif direction == 'up':
                i -= 1
                base_char, base_line, base_col = base_chars[i]
                alignment.append({
                    'type': 'deletion',
                    'base_char': base_char,
                    'compared_char': None,
                    'base_pos': {'line': base_line, 'col': base_col},
                    'compared_pos': None
                })
            elif direction == 'left':
                j -= 1
                comp_char, comp_line, comp_col = compared_chars[j]
                alignment.append({
                    'type': 'insertion',
                    'base_char': None,
                    'compared_char': comp_char,
                    'base_pos': None,
                    'compared_pos': {'line': comp_line, 'col': comp_col}
                })

        alignment.reverse()

        max_possible = max(m, n) * self._match_score
        alignment_score = dp[m][n] / max_possible if max_possible > 0 else 0.0

        return alignment, alignment_score

    def compare_character(self, base_char: str, compared_char: str) -> Dict[str, Any]:
        if base_char == compared_char:
            return {
                'type': 'identical',
                'base_char': base_char,
                'compared_char': compared_char,
                'note': '字符完全相同'
            }
        if self._is_variant(base_char, compared_char):
            return {
                'type': 'variant',
                'base_char': base_char,
                'compared_char': compared_char,
                'note': '异体字关系'
            }
        return {
            'type': 'different',
            'base_char': base_char,
            'compared_char': compared_char,
            'note': '字符不同'
        }

    def generate_diff_report(
        self,
        base_lines: List[TextLine],
        compared_lines: List[TextLine],
        alignment: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        matches: List[Dict[str, Any]] = []
        differences: List[Dict[str, Any]] = []
        additions: List[Dict[str, Any]] = []
        deletions: List[Dict[str, Any]] = []

        for idx, item in enumerate(alignment):
            item_type = item['type']

            if item_type in ['match', 'variant']:
                matches.append({
                    'char': item['base_char'],
                    'base_pos': item['base_pos'],
                    'compared_pos': item['compared_pos'],
                    'confidence': 1.0 if item_type == 'match' else 0.85
                })

                if item_type == 'variant':
                    char_compare = self.compare_character(item['base_char'], item['compared_char'])
                    differences.append({
                        'type': 'variant',
                        'base_char': item['base_char'],
                        'compared_char': item['compared_char'],
                        'base_pos': item['base_pos'],
                        'compared_pos': item['compared_pos'],
                        'note': char_compare['note']
                    })

            elif item_type == 'mismatch':
                char_compare = self.compare_character(item['base_char'], item['compared_char'])
                differences.append({
                    'type': 'substitution',
                    'base_char': item['base_char'],
                    'compared_char': item['compared_char'],
                    'base_pos': item['base_pos'],
                    'compared_pos': item['compared_pos'],
                    'note': char_compare['note']
                })

            elif item_type == 'insertion':
                additions.append({
                    'char': item['compared_char'],
                    'position': item['compared_pos'],
                    'source': 'compared'
                })

            elif item_type == 'deletion':
                deletions.append({
                    'char': item['base_char'],
                    'position': item['base_pos'],
                    'source': 'base'
                })

        total_chars = len(alignment)
        match_count = len(matches)
        diff_count = len(differences) + len(additions) + len(deletions)

        return {
            'matches': matches,
            'differences': differences,
            'additions': additions,
            'deletions': deletions,
            'statistics': {
                'total_aligned': total_chars,
                'match_count': match_count,
                'diff_count': diff_count,
                'match_rate': match_count / total_chars if total_chars > 0 else 0.0
            }
        }

    def create_collation(
        self,
        base_task_id: str,
        compared_task_id: str,
        base_page_number: int,
        compared_page_number: Optional[int] = None
    ) -> Collation:
        if compared_page_number is None:
            compared_page_number = base_page_number

        collation_data = {
            'id': str(uuid4()),
            'base_task_id': base_task_id,
            'compared_task_id': compared_task_id,
            'base_page_number': base_page_number,
            'compared_page_number': compared_page_number,
            'status': 'pending'
        }

        collation = self.collation_repository.create(collation_data)

        base_page = self.result_repository.get_page_by_task_and_page(base_task_id, base_page_number)
        compared_page = self.result_repository.get_page_by_task_and_page(compared_task_id, compared_page_number)

        if not base_page or not compared_page:
            return self.collation_repository.update_status(
                collation.id,
                'failed',
                'Page not found'
            )

        base_lines = sorted(base_page.text_lines, key=lambda x: (x.column_index or 0, x.line_index or 0))
        compared_lines = sorted(compared_page.text_lines, key=lambda x: (x.column_index or 0, x.line_index or 0))

        try:
            alignment, alignment_score = self.align_pages(base_lines, compared_lines)
            diff_result = self.generate_diff_report(base_lines, compared_lines, alignment)

            update_data = {
                'alignment_score': alignment_score,
                'diff_result': diff_result,
                'status': 'completed',
                'completed_at': datetime.utcnow()
            }

            return self.collation_repository.update(collation, update_data)

        except Exception as e:
            return self.collation_repository.update_status(
                collation.id,
                'failed',
                str(e)
            )

    def get_collation(self, collation_id: str) -> Optional[Collation]:
        return self.collation_repository.get_by_id(collation_id)

    def list_collations(self, task_id: str) -> List[Collation]:
        return self.collation_repository.list_by_task_id(task_id)
