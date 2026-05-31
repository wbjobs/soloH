from typing import Optional, List, Dict, Any
from app.repositories.glyph_repository import GlyphRepository
from app.models.glyph_character import GlyphCharacter


class GlyphService:
    def __init__(self, glyph_repository: GlyphRepository):
        self.glyph_repository = glyph_repository

    def search_glyphs(self, radical: Optional[str] = None, stroke_count: Optional[int] = None,
                      stroke_tolerance: int = 2, char: Optional[str] = None,
                      structure: Optional[str] = None) -> List[GlyphCharacter]:
        if char:
            target = self.glyph_repository.get_by_char(char)
            if target:
                min_strokes = target.stroke_count - stroke_tolerance
                max_strokes = target.stroke_count + stroke_tolerance
                results = self.glyph_repository.search_by_radical_and_strokes(
                    radical or target.radical, min_strokes, max_strokes
                )
                if structure:
                    results = [r for r in results if r.structure == structure]
                return results
        if stroke_count is not None:
            min_strokes = stroke_count - stroke_tolerance
            max_strokes = stroke_count + stroke_tolerance
        else:
            min_strokes = None
            max_strokes = None
        results = self.glyph_repository.search_by_radical_and_strokes(radical, min_strokes, max_strokes)
        if structure:
            results = [r for r in results if r.structure == structure]
        return results

    def get_similar_variants(self, char: str) -> List[Dict[str, Any]]:
        target = self.glyph_repository.get_by_char(char)
        if not target:
            return []
        variants = []
        if target.variants:
            for variant_char in target.variants:
                variant_glyph = self.glyph_repository.get_by_char(variant_char)
                if variant_glyph:
                    similarity = self.calculate_shape_similarity(char, variant_char)
                    variants.append({
                        'char': variant_char,
                        'similarity': similarity,
                        'radical': variant_glyph.radical,
                        'stroke_count': variant_glyph.stroke_count,
                        'structure': variant_glyph.structure
                    })
        similar_chars = self.glyph_repository.get_similar_chars(char)
        for sc in similar_chars:
            similarity = self.calculate_shape_similarity(char, sc.char)
            if not any(v['char'] == sc.char for v in variants):
                variants.append({
                    'char': sc.char,
                    'similarity': similarity,
                    'radical': sc.radical,
                    'stroke_count': sc.stroke_count,
                    'structure': sc.structure
                })
        variants.sort(key=lambda x: x['similarity'], reverse=True)
        return variants

    def calculate_shape_similarity(self, char1: str, char2: str) -> float:
        g1 = self.glyph_repository.get_by_char(char1)
        g2 = self.glyph_repository.get_by_char(char2)
        if not g1 or not g2:
            return 0.0
        score = 0.0
        if g1.radical == g2.radical:
            score += 0.4
        stroke_diff = abs(g1.stroke_count - g2.stroke_count)
        max_strokes = max(g1.stroke_count, g2.stroke_count)
        stroke_sim = 1.0 - (stroke_diff / max_strokes if max_strokes > 0 else 0)
        score += stroke_sim * 0.3
        if g1.structure == g2.structure:
            score += 0.3
        return round(score, 3)

    def get_by_char(self, char: str) -> Optional[GlyphCharacter]:
        return self.glyph_repository.get_by_char(char)

    def create_glyph(self, data: Dict[str, Any]) -> GlyphCharacter:
        return self.glyph_repository.create_glyph(data)

    def list_all(self) -> List[GlyphCharacter]:
        return self.glyph_repository.list_all()

    def initialize_builtin_glyphs(self) -> int:
        existing = self.list_all()
        if len(existing) > 0:
            return 0
        glyphs_data = [
            {'char': '一', 'radical': '一', 'stroke_count': 1, 'pinyin': 'yī', 'variants': ['壹'], 'structure': '独体', 'unicode': 'U+4E00', 'kangxi_strokes': 1, 'frequency': 0.99},
            {'char': '二', 'radical': '二', 'stroke_count': 2, 'pinyin': 'èr', 'variants': ['贰'], 'structure': '独体', 'unicode': 'U+4E8C', 'kangxi_strokes': 2, 'frequency': 0.95},
            {'char': '三', 'radical': '一', 'stroke_count': 3, 'pinyin': 'sān', 'variants': ['叁'], 'structure': '独体', 'unicode': 'U+4E09', 'kangxi_strokes': 3, 'frequency': 0.93},
            {'char': '四', 'radical': '囗', 'stroke_count': 5, 'pinyin': 'sì', 'variants': ['肆'], 'structure': '包围', 'unicode': 'U+56DB', 'kangxi_strokes': 5, 'frequency': 0.90},
            {'char': '五', 'radical': '一', 'stroke_count': 4, 'pinyin': 'wǔ', 'variants': ['伍'], 'structure': '独体', 'unicode': 'U+4E94', 'kangxi_strokes': 4, 'frequency': 0.88},
            {'char': '六', 'radical': '八', 'stroke_count': 4, 'pinyin': 'liù', 'variants': ['陆'], 'structure': '上下', 'unicode': 'U+516D', 'kangxi_strokes': 4, 'frequency': 0.87},
            {'char': '七', 'radical': '一', 'stroke_count': 2, 'pinyin': 'qī', 'variants': ['柒'], 'structure': '独体', 'unicode': 'U+4E03', 'kangxi_strokes': 2, 'frequency': 0.86},
            {'char': '八', 'radical': '八', 'stroke_count': 2, 'pinyin': 'bā', 'variants': ['捌'], 'structure': '独体', 'unicode': 'U+516B', 'kangxi_strokes': 2, 'frequency': 0.85},
            {'char': '九', 'radical': '丿', 'stroke_count': 2, 'pinyin': 'jiǔ', 'variants': ['玖'], 'structure': '独体', 'unicode': 'U+4E5D', 'kangxi_strokes': 2, 'frequency': 0.84},
            {'char': '十', 'radical': '十', 'stroke_count': 2, 'pinyin': 'shí', 'variants': ['拾'], 'structure': '独体', 'unicode': 'U+5341', 'kangxi_strokes': 2, 'frequency': 0.89},
            {'char': '人', 'radical': '人', 'stroke_count': 2, 'pinyin': 'rén', 'variants': ['亻'], 'structure': '独体', 'unicode': 'U+4EBA', 'kangxi_strokes': 2, 'frequency': 0.98},
            {'char': '大', 'radical': '大', 'stroke_count': 3, 'pinyin': 'dà', 'variants': [], 'structure': '独体', 'unicode': 'U+5927', 'kangxi_strokes': 3, 'frequency': 0.97},
            {'char': '小', 'radical': '小', 'stroke_count': 3, 'pinyin': 'xiǎo', 'variants': [], 'structure': '独体', 'unicode': 'U+5C0F', 'kangxi_strokes': 3, 'frequency': 0.96},
            {'char': '天', 'radical': '大', 'stroke_count': 4, 'pinyin': 'tiān', 'variants': [], 'structure': '上下', 'unicode': 'U+5929', 'kangxi_strokes': 4, 'frequency': 0.95},
            {'char': '地', 'radical': '土', 'stroke_count': 6, 'pinyin': 'dì', 'variants': [], 'structure': '左右', 'unicode': 'U+5730', 'kangxi_strokes': 6, 'frequency': 0.94},
            {'char': '日', 'radical': '日', 'stroke_count': 4, 'pinyin': 'rì', 'variants': [], 'structure': '独体', 'unicode': 'U+65E5', 'kangxi_strokes': 4, 'frequency': 0.93},
            {'char': '月', 'radical': '月', 'stroke_count': 4, 'pinyin': 'yuè', 'variants': [], 'structure': '独体', 'unicode': 'U+6708', 'kangxi_strokes': 4, 'frequency': 0.92},
            {'char': '水', 'radical': '水', 'stroke_count': 4, 'pinyin': 'shuǐ', 'variants': ['氵'], 'structure': '独体', 'unicode': 'U+6C34', 'kangxi_strokes': 4, 'frequency': 0.91},
            {'char': '火', 'radical': '火', 'stroke_count': 4, 'pinyin': 'huǒ', 'variants': ['灬'], 'structure': '独体', 'unicode': 'U+706B', 'kangxi_strokes': 4, 'frequency': 0.90},
            {'char': '山', 'radical': '山', 'stroke_count': 3, 'pinyin': 'shān', 'variants': [], 'structure': '独体', 'unicode': 'U+5C71', 'kangxi_strokes': 3, 'frequency': 0.89},
            {'char': '木', 'radical': '木', 'stroke_count': 4, 'pinyin': 'mù', 'variants': ['扌'], 'structure': '独体', 'unicode': 'U+6728', 'kangxi_strokes': 4, 'frequency': 0.95},
            {'char': '金', 'radical': '金', 'stroke_count': 8, 'pinyin': 'jīn', 'variants': ['钅'], 'structure': '上下', 'unicode': 'U+91D1', 'kangxi_strokes': 8, 'frequency': 0.88},
            {'char': '土', 'radical': '土', 'stroke_count': 3, 'pinyin': 'tǔ', 'variants': [], 'structure': '独体', 'unicode': 'U+571F', 'kangxi_strokes': 3, 'frequency': 0.87},
            {'char': '石', 'radical': '石', 'stroke_count': 5, 'pinyin': 'shí', 'variants': [], 'structure': '半包围', 'unicode': 'U+77F3', 'kangxi_strokes': 5, 'frequency': 0.86},
            {'char': '田', 'radical': '田', 'stroke_count': 5, 'pinyin': 'tián', 'variants': [], 'structure': '独体', 'unicode': 'U+7530', 'kangxi_strokes': 5, 'frequency': 0.85},
            {'char': '中', 'radical': '丨', 'stroke_count': 4, 'pinyin': 'zhōng', 'variants': [], 'structure': '独体', 'unicode': 'U+4E2D', 'kangxi_strokes': 4, 'frequency': 0.97},
            {'char': '国', 'radical': '囗', 'stroke_count': 8, 'pinyin': 'guó', 'variants': ['國'], 'structure': '包围', 'unicode': 'U+56FD', 'kangxi_strokes': 11, 'frequency': 0.96},
            {'char': '上', 'radical': '一', 'stroke_count': 3, 'pinyin': 'shàng', 'variants': [], 'structure': '独体', 'unicode': 'U+4E0A', 'kangxi_strokes': 3, 'frequency': 0.95},
            {'char': '下', 'radical': '一', 'stroke_count': 3, 'pinyin': 'xià', 'variants': [], 'structure': '独体', 'unicode': 'U+4E0B', 'kangxi_strokes': 3, 'frequency': 0.94},
            {'char': '左', 'radical': '工', 'stroke_count': 5, 'pinyin': 'zuǒ', 'variants': [], 'structure': '半包围', 'unicode': 'U+5DE6', 'kangxi_strokes': 5, 'frequency': 0.93},
            {'char': '右', 'radical': '口', 'stroke_count': 5, 'pinyin': 'yòu', 'variants': [], 'structure': '半包围', 'unicode': 'U+53F3', 'kangxi_strokes': 5, 'frequency': 0.92},
            {'char': '口', 'radical': '口', 'stroke_count': 3, 'pinyin': 'kǒu', 'variants': [], 'structure': '独体', 'unicode': 'U+53E3', 'kangxi_strokes': 3, 'frequency': 0.96},
            {'char': '目', 'radical': '目', 'stroke_count': 5, 'pinyin': 'mù', 'variants': [], 'structure': '独体', 'unicode': 'U+76EE', 'kangxi_strokes': 5, 'frequency': 0.85},
            {'char': '耳', 'radical': '耳', 'stroke_count': 6, 'pinyin': 'ěr', 'variants': [], 'structure': '独体', 'unicode': 'U+8033', 'kangxi_strokes': 6, 'frequency': 0.84},
            {'char': '手', 'radical': '手', 'stroke_count': 4, 'pinyin': 'shǒu', 'variants': ['扌'], 'structure': '独体', 'unicode': 'U+624B', 'kangxi_strokes': 4, 'frequency': 0.88},
            {'char': '心', 'radical': '心', 'stroke_count': 4, 'pinyin': 'xīn', 'variants': ['忄'], 'structure': '独体', 'unicode': 'U+5FC3', 'kangxi_strokes': 4, 'frequency': 0.91},
            {'char': '言', 'radical': '言', 'stroke_count': 7, 'pinyin': 'yán', 'variants': ['讠'], 'structure': '独体', 'unicode': 'U+8A00', 'kangxi_strokes': 7, 'frequency': 0.87},
            {'char': '文', 'radical': '文', 'stroke_count': 4, 'pinyin': 'wén', 'variants': [], 'structure': '独体', 'unicode': 'U+6587', 'kangxi_strokes': 4, 'frequency': 0.89},
            {'char': '武', 'radical': '止', 'stroke_count': 8, 'pinyin': 'wǔ', 'variants': [], 'structure': '半包围', 'unicode': 'U+6B66', 'kangxi_strokes': 8, 'frequency': 0.78},
            {'char': '道', 'radical': '辶', 'stroke_count': 12, 'pinyin': 'dào', 'variants': [], 'structure': '半包围', 'unicode': 'U+9053', 'kangxi_strokes': 16, 'frequency': 0.82},
            {'char': '德', 'radical': '彳', 'stroke_count': 15, 'pinyin': 'dé', 'variants': [], 'structure': '左右', 'unicode': 'U+5FB7', 'kangxi_strokes': 15, 'frequency': 0.80},
            {'char': '仁', 'radical': '亻', 'stroke_count': 4, 'pinyin': 'rén', 'variants': [], 'structure': '左右', 'unicode': 'U+4EC1', 'kangxi_strokes': 4, 'frequency': 0.76},
            {'char': '义', 'radical': '丶', 'stroke_count': 3, 'pinyin': 'yì', 'variants': ['義'], 'structure': '独体', 'unicode': 'U+4E49', 'kangxi_strokes': 13, 'frequency': 0.77},
            {'char': '礼', 'radical': '礻', 'stroke_count': 5, 'pinyin': 'lǐ', 'variants': ['禮'], 'structure': '左右', 'unicode': 'U+793C', 'kangxi_strokes': 18, 'frequency': 0.75},
            {'char': '智', 'radical': '日', 'stroke_count': 12, 'pinyin': 'zhì', 'variants': [], 'structure': '上下', 'unicode': 'U+667A', 'kangxi_strokes': 12, 'frequency': 0.74},
            {'char': '信', 'radical': '亻', 'stroke_count': 9, 'pinyin': 'xìn', 'variants': [], 'structure': '左右', 'unicode': 'U+4FE1', 'kangxi_strokes': 9, 'frequency': 0.78},
            {'char': '圣', 'radical': '土', 'stroke_count': 5, 'pinyin': 'shèng', 'variants': ['聖'], 'structure': '上下', 'unicode': 'U+5723', 'kangxi_strokes': 13, 'frequency': 0.73},
            {'char': '贤', 'radical': '贝', 'stroke_count': 8, 'pinyin': 'xián', 'variants': ['賢'], 'structure': '上下', 'unicode': 'U+8D24', 'kangxi_strokes': 15, 'frequency': 0.72},
            {'char': '君', 'radical': '口', 'stroke_count': 7, 'pinyin': 'jūn', 'variants': [], 'structure': '上下', 'unicode': 'U+541B', 'kangxi_strokes': 7, 'frequency': 0.79},
            {'char': '臣', 'radical': '臣', 'stroke_count': 6, 'pinyin': 'chén', 'variants': [], 'structure': '独体', 'unicode': 'U+81E3', 'kangxi_strokes': 6, 'frequency': 0.71},
            {'char': '父', 'radical': '父', 'stroke_count': 4, 'pinyin': 'fù', 'variants': [], 'structure': '独体', 'unicode': 'U+7236', 'kangxi_strokes': 4, 'frequency': 0.70},
            {'char': '子', 'radical': '子', 'stroke_count': 3, 'pinyin': 'zǐ', 'variants': [], 'structure': '独体', 'unicode': 'U+5B50', 'kangxi_strokes': 3, 'frequency': 0.83},
            {'char': '男', 'radical': '田', 'stroke_count': 7, 'pinyin': 'nán', 'variants': [], 'structure': '上下', 'unicode': 'U+7537', 'kangxi_strokes': 7, 'frequency': 0.69},
            {'char': '女', 'radical': '女', 'stroke_count': 3, 'pinyin': 'nǚ', 'variants': [], 'structure': '独体', 'unicode': 'U+5973', 'kangxi_strokes': 3, 'frequency': 0.81},
            {'char': '兄', 'radical': '儿', 'stroke_count': 5, 'pinyin': 'xiōng', 'variants': [], 'structure': '上下', 'unicode': 'U+5144', 'kangxi_strokes': 5, 'frequency': 0.68},
            {'char': '弟', 'radical': '弓', 'stroke_count': 7, 'pinyin': 'dì', 'variants': [], 'structure': '上下', 'unicode': 'U+5F1F', 'kangxi_strokes': 7, 'frequency': 0.67},
            {'char': '夫', 'radical': '大', 'stroke_count': 4, 'pinyin': 'fū', 'variants': [], 'structure': '独体', 'unicode': 'U+592B', 'kangxi_strokes': 4, 'frequency': 0.66},
            {'char': '妻', 'radical': '女', 'stroke_count': 8, 'pinyin': 'qī', 'variants': [], 'structure': '上下', 'unicode': 'U+59BB', 'kangxi_strokes': 8, 'frequency': 0.65},
            {'char': '王', 'radical': '王', 'stroke_count': 4, 'pinyin': 'wáng', 'variants': [], 'structure': '独体', 'unicode': 'U+738B', 'kangxi_strokes': 4, 'frequency': 0.90},
            {'char': '侯', 'radical': '亻', 'stroke_count': 9, 'pinyin': 'hóu', 'variants': [], 'structure': '左右', 'unicode': 'U+4FAF', 'kangxi_strokes': 9, 'frequency': 0.64},
            {'char': '伯', 'radical': '亻', 'stroke_count': 7, 'pinyin': 'bó', 'variants': [], 'structure': '左右', 'unicode': 'U+4F2F', 'kangxi_strokes': 7, 'frequency': 0.63},
            {'char': '仲', 'radical': '亻', 'stroke_count': 6, 'pinyin': 'zhòng', 'variants': [], 'structure': '左右', 'unicode': 'U+4EF2', 'kangxi_strokes': 6, 'frequency': 0.62},
            {'char': '叔', 'radical': '又', 'stroke_count': 8, 'pinyin': 'shū', 'variants': [], 'structure': '左右', 'unicode': 'U+53D4', 'kangxi_strokes': 8, 'frequency': 0.61},
            {'char': '季', 'radical': '子', 'stroke_count': 8, 'pinyin': 'jì', 'variants': [], 'structure': '上下', 'unicode': 'U+5B63', 'kangxi_strokes': 8, 'frequency': 0.60},
            {'char': '风', 'radical': '风', 'stroke_count': 4, 'pinyin': 'fēng', 'variants': ['風'], 'structure': '半包围', 'unicode': 'U+98CE', 'kangxi_strokes': 9, 'frequency': 0.86},
            {'char': '云', 'radical': '二', 'stroke_count': 4, 'pinyin': 'yún', 'variants': ['雲'], 'structure': '上下', 'unicode': 'U+4E91', 'kangxi_strokes': 12, 'frequency': 0.85},
            {'char': '雨', 'radical': '雨', 'stroke_count': 8, 'pinyin': 'yǔ', 'variants': [], 'structure': '独体', 'unicode': 'U+96E8', 'kangxi_strokes': 8, 'frequency': 0.84},
            {'char': '雪', 'radical': '雨', 'stroke_count': 11, 'pinyin': 'xuě', 'variants': [], 'structure': '上下', 'unicode': 'U+96EA', 'kangxi_strokes': 11, 'frequency': 0.78},
            {'char': '花', 'radical': '艹', 'stroke_count': 7, 'pinyin': 'huā', 'variants': [], 'structure': '上下', 'unicode': 'U+82B1', 'kangxi_strokes': 8, 'frequency': 0.83},
            {'char': '草', 'radical': '艹', 'stroke_count': 9, 'pinyin': 'cǎo', 'variants': [], 'structure': '上下', 'unicode': 'U+8349', 'kangxi_strokes': 12, 'frequency': 0.82},
            {'char': '树', 'radical': '木', 'stroke_count': 9, 'pinyin': 'shù', 'variants': ['樹'], 'structure': '左右', 'unicode': 'U+6811', 'kangxi_strokes': 16, 'frequency': 0.81},
            {'char': '林', 'radical': '木', 'stroke_count': 8, 'pinyin': 'lín', 'variants': [], 'structure': '左右', 'unicode': 'U+6797', 'kangxi_strokes': 8, 'frequency': 0.80},
            {'char': '森', 'radical': '木', 'stroke_count': 12, 'pinyin': 'sēn', 'variants': [], 'structure': '品字', 'unicode': 'U+68EE', 'kangxi_strokes': 12, 'frequency': 0.75},
            {'char': '河', 'radical': '氵', 'stroke_count': 8, 'pinyin': 'hé', 'variants': [], 'structure': '左右', 'unicode': 'U+6CB3', 'kangxi_strokes': 9, 'frequency': 0.84},
            {'char': '江', 'radical': '氵', 'stroke_count': 6, 'pinyin': 'jiāng', 'variants': [], 'structure': '左右', 'unicode': 'U+6C5F', 'kangxi_strokes': 7, 'frequency': 0.83},
            {'char': '湖', 'radical': '氵', 'stroke_count': 12, 'pinyin': 'hú', 'variants': [], 'structure': '左右', 'unicode': 'U+6E56', 'kangxi_strokes': 13, 'frequency': 0.79},
            {'char': '海', 'radical': '氵', 'stroke_count': 10, 'pinyin': 'hǎi', 'variants': [], 'structure': '左右', 'unicode': 'U+6D77', 'kangxi_strokes': 11, 'frequency': 0.82},
            {'char': '诗', 'radical': '讠', 'stroke_count': 8, 'pinyin': 'shī', 'variants': ['詩'], 'structure': '左右', 'unicode': 'U+8BD7', 'kangxi_strokes': 13, 'frequency': 0.77},
            {'char': '书', 'radical': '乙', 'stroke_count': 4, 'pinyin': 'shū', 'variants': ['書'], 'structure': '独体', 'unicode': 'U+4E66', 'kangxi_strokes': 10, 'frequency': 0.79},
            {'char': '画', 'radical': '田', 'stroke_count': 8, 'pinyin': 'huà', 'variants': ['畫'], 'structure': '半包围', 'unicode': 'U+753B', 'kangxi_strokes': 12, 'frequency': 0.76},
            {'char': '琴', 'radical': '王', 'stroke_count': 12, 'pinyin': 'qín', 'variants': [], 'structure': '上下', 'unicode': 'U+7434', 'kangxi_strokes': 13, 'frequency': 0.70},
            {'char': '棋', 'radical': '木', 'stroke_count': 12, 'pinyin': 'qí', 'variants': [], 'structure': '左右', 'unicode': 'U+68CB', 'kangxi_strokes': 12, 'frequency': 0.69},
            {'char': '龙', 'radical': '龙', 'stroke_count': 5, 'pinyin': 'lóng', 'variants': ['龍'], 'structure': '独体', 'unicode': 'U+9F99', 'kangxi_strokes': 16, 'frequency': 0.85},
            {'char': '虎', 'radical': '虍', 'stroke_count': 8, 'pinyin': 'hǔ', 'variants': [], 'structure': '半包围', 'unicode': 'U+864E', 'kangxi_strokes': 8, 'frequency': 0.74},
            {'char': '凤', 'radical': '几', 'stroke_count': 4, 'pinyin': 'fèng', 'variants': ['鳳'], 'structure': '半包围', 'unicode': 'U+51E4', 'kangxi_strokes': 14, 'frequency': 0.72},
            {'char': '龟', 'radical': '刀', 'stroke_count': 7, 'pinyin': 'guī', 'variants': ['龜'], 'structure': '上下', 'unicode': 'U+9F9F', 'kangxi_strokes': 16, 'frequency': 0.68},
            {'char': '鸟', 'radical': '鸟', 'stroke_count': 5, 'pinyin': 'niǎo', 'variants': ['鳥'], 'structure': '独体', 'unicode': 'U+9E1F', 'kangxi_strokes': 11, 'frequency': 0.75},
            {'char': '鱼', 'radical': '鱼', 'stroke_count': 8, 'pinyin': 'yú', 'variants': ['魚'], 'structure': '上下', 'unicode': 'U+9C7C', 'kangxi_strokes': 11, 'frequency': 0.73},
            {'char': '马', 'radical': '马', 'stroke_count': 3, 'pinyin': 'mǎ', 'variants': ['馬'], 'structure': '独体', 'unicode': 'U+9A6C', 'kangxi_strokes': 10, 'frequency': 0.78},
            {'char': '牛', 'radical': '牛', 'stroke_count': 4, 'pinyin': 'niú', 'variants': [], 'structure': '独体', 'unicode': 'U+725B', 'kangxi_strokes': 4, 'frequency': 0.71},
            {'char': '羊', 'radical': '羊', 'stroke_count': 6, 'pinyin': 'yáng', 'variants': [], 'structure': '独体', 'unicode': 'U+7F8A', 'kangxi_strokes': 6, 'frequency': 0.70},
            {'char': '猪', 'radical': '犭', 'stroke_count': 11, 'pinyin': 'zhū', 'variants': ['豬'], 'structure': '左右', 'unicode': 'U+732A', 'kangxi_strokes': 16, 'frequency': 0.65},
            {'char': '狗', 'radical': '犭', 'stroke_count': 8, 'pinyin': 'gǒu', 'variants': [], 'structure': '左右', 'unicode': 'U+72D7', 'kangxi_strokes': 9, 'frequency': 0.67},
            {'char': '鸡', 'radical': '鸟', 'stroke_count': 7, 'pinyin': 'jī', 'variants': ['鷄'], 'structure': '左右', 'unicode': 'U+9E21', 'kangxi_strokes': 21, 'frequency': 0.66},
            {'char': '鸭', 'radical': '鸟', 'stroke_count': 10, 'pinyin': 'yā', 'variants': [], 'structure': '左右', 'unicode': 'U+9E2D', 'kangxi_strokes': 16, 'frequency': 0.64},
            {'char': '东', 'radical': '一', 'stroke_count': 5, 'pinyin': 'dōng', 'variants': ['東'], 'structure': '独体', 'unicode': 'U+4E1C', 'kangxi_strokes': 8, 'frequency': 0.87},
            {'char': '西', 'radical': '西', 'stroke_count': 6, 'pinyin': 'xī', 'variants': [], 'structure': '独体', 'unicode': 'U+897F', 'kangxi_strokes': 6, 'frequency': 0.86},
            {'char': '南', 'radical': '十', 'stroke_count': 9, 'pinyin': 'nán', 'variants': [], 'structure': '上下', 'unicode': 'U+5357', 'kangxi_strokes': 9, 'frequency': 0.85},
            {'char': '北', 'radical': '匕', 'stroke_count': 5, 'pinyin': 'běi', 'variants': [], 'structure': '左右', 'unicode': 'U+5317', 'kangxi_strokes': 5, 'frequency': 0.84},
            {'char': '春', 'radical': '日', 'stroke_count': 9, 'pinyin': 'chūn', 'variants': [], 'structure': '上下', 'unicode': 'U+6625', 'kangxi_strokes': 9, 'frequency': 0.83},
            {'char': '夏', 'radical': '夂', 'stroke_count': 10, 'pinyin': 'xià', 'variants': [], 'structure': '上下', 'unicode': 'U+590F', 'kangxi_strokes': 10, 'frequency': 0.82},
            {'char': '秋', 'radical': '禾', 'stroke_count': 9, 'pinyin': 'qiū', 'variants': [], 'structure': '左右', 'unicode': 'U+79CB', 'kangxi_strokes': 9, 'frequency': 0.81},
            {'char': '冬', 'radical': '夂', 'stroke_count': 5, 'pinyin': 'dōng', 'variants': [], 'structure': '上下', 'unicode': 'U+51AC', 'kangxi_strokes': 5, 'frequency': 0.80},
            {'char': '年', 'radical': '干', 'stroke_count': 6, 'pinyin': 'nián', 'variants': [], 'structure': '上下', 'unicode': 'U+5E74', 'kangxi_strokes': 6, 'frequency': 0.88},
            {'char': '岁', 'radical': '山', 'stroke_count': 6, 'pinyin': 'suì', 'variants': ['歲'], 'structure': '上下', 'unicode': 'U+5C81', 'kangxi_strokes': 13, 'frequency': 0.77},
            {'char': '时', 'radical': '日', 'stroke_count': 7, 'pinyin': 'shí', 'variants': ['時'], 'structure': '左右', 'unicode': 'U+65F6', 'kangxi_strokes': 10, 'frequency': 0.78},
            {'char': '节', 'radical': '艹', 'stroke_count': 5, 'pinyin': 'jié', 'variants': ['節'], 'structure': '上下', 'unicode': 'U+8282', 'kangxi_strokes': 15, 'frequency': 0.75},
        ]
        count = 0
        for data in glyphs_data:
            self.glyph_repository.create_glyph(data)
            count += 1
        return count
