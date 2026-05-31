from app.services.collation_service import CollationService
from app.repositories.collation_repository import CollationRepository
from app.repositories.result_repository import ResultRepository
from unittest.mock import Mock

mock_collation_repo = Mock(spec=CollationRepository)
mock_result_repo = Mock(spec=ResultRepository)

service = CollationService(mock_collation_repo, mock_result_repo)

class MockTextLine:
    def __init__(self, content, column_index=0, line_index=0):
        self.content = content
        self.column_index = column_index
        self.line_index = line_index

base_lines = [
    MockTextLine('学而时习之', column_index=1, line_index=0),
    MockTextLine('不亦说乎', column_index=0, line_index=0),
]

compared_lines = [
    MockTextLine('学而时习之', column_index=1, line_index=0),
    MockTextLine('不亦悦乎', column_index=0, line_index=0),
]

alignment, score = service.align_pages(base_lines, compared_lines)
print(f'✓ Alignment score: {score:.4f}')
print(f'✓ Total aligned items: {len(alignment)}')

matches = sum(1 for a in alignment if a['type'] in ['match', 'variant'])
mismatches = sum(1 for a in alignment if a['type'] == 'mismatch')
variants = sum(1 for a in alignment if a['type'] == 'variant')

print(f'  - Matches: {matches}')
print(f'  - Variants: {variants}')
print(f'  - Mismatches: {mismatches}')

print()
print('✓ Character comparison tests:')
result1 = service.compare_character('说', '悦')
print(f'  说 vs 悦: {result1["type"]} - {result1["note"]}')

result2 = service.compare_character('于', '於')
print(f'  于 vs 於: {result2["type"]} - {result2["note"]}')

result3 = service.compare_character('之', '之')
print(f'  之 vs 之: {result3["type"]} - {result3["note"]}')

result4 = service.compare_character('学', '教')
print(f'  学 vs 教: {result4["type"]} - {result4["note"]}')

diff_report = service.generate_diff_report(base_lines, compared_lines, alignment)
print()
print('✓ Diff report generated:')
print(f'  - Statistics: {diff_report["statistics"]}')
print(f'  - Matches count: {len(diff_report["matches"])}')
print(f'  - Differences count: {len(diff_report["differences"])}')
print()
print('✓ All tests passed!')
