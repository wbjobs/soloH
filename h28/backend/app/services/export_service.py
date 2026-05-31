from typing import Optional, Dict, List
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace
from xml.dom import minidom
from app.repositories.result_repository import ResultRepository
from app.repositories.task_repository import TaskRepository


TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
TEI_SCHEMA_LOCATION = "http://www.tei-c.org/ns/1.0 https://www.tei-c.org/release/xml/tei/custom/schema/tei_all.xsd"

register_namespace('', TEI_NS)
register_namespace('xml', XML_NS)
register_namespace('xsi', XSI_NS)


class ExportService:
    def __init__(self, result_repository: ResultRepository, task_repository: TaskRepository):
        self.result_repository = result_repository
        self.task_repository = task_repository

    def export_to_file(self, content: str, output_path: str) -> None:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def export_txt(
        self, 
        task_id: str,
        include_confidence: bool = False,
        include_coordinates: bool = False
    ) -> str:
        task = self.task_repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        page_results = self.result_repository.get_page_results_by_task_id(task_id)
        
        lines = []
        lines.append(f"OCR 识别结果 - {task.file_name}")
        lines.append("=" * 50)
        lines.append(f"任务ID: {task_id}")
        lines.append(f"文件类型: {task.file_type}")
        lines.append(f"页数: {task.page_count}")
        lines.append(f"创建时间: {task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else 'N/A'}")
        lines.append(f"完成时间: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else 'N/A'}")
        lines.append("=" * 50)
        lines.append("")
        
        for page_result in page_results:
            lines.append(f"--- 第 {page_result.page_number} 页 ---")
            lines.append("")
            
            columns = self._group_by_columns(page_result.text_lines)
            
            for col_idx, column_lines in enumerate(columns):
                if len(columns) > 1:
                    lines.append(f"[第 {col_idx + 1} 栏]")
                for text_line in column_lines:
                    if text_line.content:
                        line_content = text_line.content
                        if include_confidence and text_line.confidence is not None:
                            line_content += f" (置信度: {text_line.confidence:.2f})"
                        if include_coordinates and text_line.text_boxes:
                            coords = []
                            for tb in text_line.text_boxes:
                                coords.append(f"({tb.x1},{tb.y1})")
                            line_content += f" [坐标: {', '.join(coords)}]"
                        lines.append(line_content)
                lines.append("")
        
        return "\n".join(lines)

    def export_markdown(
        self, 
        task_id: str,
        include_confidence: bool = False,
        include_coordinates: bool = False
    ) -> str:
        task = self.task_repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        page_results = self.result_repository.get_page_results_by_task_id(task_id)
        
        lines = []
        lines.append(f"# OCR 识别结果 - {task.file_name}")
        lines.append("")
        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| **任务ID** | {task_id} |")
        lines.append(f"| **文件类型** | {task.file_type} |")
        lines.append(f"| **页数** | {task.page_count} |")
        lines.append(f"| **创建时间** | {task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else 'N/A'} |")
        lines.append(f"| **完成时间** | {task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else 'N/A'} |")
        lines.append("")
        
        for page_result in page_results:
            lines.append(f"## 第 {page_result.page_number} 页")
            lines.append("")
            
            columns = self._group_by_columns(page_result.text_lines)
            
            if len(columns) > 1:
                lines.append(self._render_vertical_columns(columns, include_confidence, include_coordinates))
            else:
                for text_line in columns[0] if columns else []:
                    if text_line.content:
                        line_content = text_line.content
                        if include_confidence and text_line.confidence is not None:
                            line_content += f" <sup>({text_line.confidence:.2f})</sup>"
                        if include_coordinates and text_line.text_boxes:
                            coords = []
                            for tb in text_line.text_boxes:
                                coords.append(f"({tb.x1},{tb.y1})")
                            line_content += f" <small>[{', '.join(coords)}]</small>"
                        lines.append(f"{line_content}  ")
                lines.append("")
        
        return "\n".join(lines)

    def _group_by_columns(self, text_lines: List) -> List[List]:
        columns = {}
        for text_line in text_lines:
            col_idx = text_line.column_index or 0
            if col_idx not in columns:
                columns[col_idx] = []
            columns[col_idx].append(text_line)
        
        sorted_columns = []
        for col_idx in sorted(columns.keys()):
            sorted_columns.append(sorted(columns[col_idx], key=lambda x: x.line_index or 0))
        
        return sorted_columns

    def _render_vertical_columns(
        self, 
        columns: List[List],
        include_confidence: bool,
        include_coordinates: bool
    ) -> str:
        max_lines = max(len(col) for col in columns) if columns else 0
        num_columns = len(columns)
        
        header = "| " + " | ".join([f"第 {i+1} 栏" for i in range(num_columns)]) + " |"
        separator = "| " + " | ".join(["---"] * num_columns) + " |"
        
        result = [header, separator]
        
        for line_idx in range(max_lines):
            row_cells = []
            for col in columns:
                if line_idx < len(col):
                    text_line = col[line_idx]
                    cell_content = text_line.content or ""
                    if include_confidence and text_line.confidence is not None:
                        cell_content += f"<br><small>置信度: {text_line.confidence:.2f}</small>"
                    if include_coordinates and text_line.text_boxes:
                        coords = []
                        for tb in text_line.text_boxes:
                            coords.append(f"({tb.x1},{tb.y1})")
                        cell_content += f"<br><small>[{', '.join(coords)}]</small>"
                    row_cells.append(cell_content)
                else:
                    row_cells.append("")
            result.append("| " + " | ".join(row_cells) + " |")
        
        return "\n".join(result) + "\n"

    def _create_tei_element(
        self, 
        tag: str, 
        text: Optional[str] = None, 
        attrs: Optional[dict] = None,
        parent: Optional[Element] = None
    ) -> Element:
        qname = f"{{{TEI_NS}}}{tag}"
        if parent is not None:
            elem = SubElement(parent, qname, attrs or {})
        else:
            elem = Element(qname, attrs or {})
        if text:
            elem.text = text
        return elem

    def _confidence_to_cert(self, confidence: float) -> str:
        if confidence >= 0.9:
            return "high"
        elif confidence >= 0.7:
            return "medium"
        elif confidence >= 0.5:
            return "low"
        else:
            return "uncertain"

    def export_tei_xml(
        self, 
        task_id: str,
        include_confidence: bool = False,
        include_coordinates: bool = False
    ) -> str:
        task = self.task_repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        page_results = self.result_repository.get_page_results_by_task_id(task_id)
        
        root_attrs = {
            f"{{{XML_NS}}}id": f"task-{task_id}",
            f"{{{XSI_NS}}}schemaLocation": TEI_SCHEMA_LOCATION
        }
        tei = self._create_tei_element("TEI", attrs=root_attrs)
        
        tei_header = self._create_tei_element("teiHeader", parent=tei)
        file_desc = self._create_tei_element("fileDesc", parent=tei_header)
        
        title_stmt = self._create_tei_element("titleStmt", parent=file_desc)
        self._create_tei_element("title", f"OCR 识别结果 - {task.file_name}", parent=title_stmt)
        self._create_tei_element("author", "古籍文字识别系统", parent=title_stmt)
        resp_stmt = self._create_tei_element("respStmt", parent=title_stmt)
        self._create_tei_element("resp", "OCR识别", parent=resp_stmt)
        self._create_tei_element("name", "古籍文字识别系统", parent=resp_stmt)
        
        publication_stmt = self._create_tei_element("publicationStmt", parent=file_desc)
        self._create_tei_element("publisher", "古籍文字识别系统", parent=publication_stmt)
        date_attrs = {"when": datetime.now().strftime("%Y-%m-%d")}
        self._create_tei_element("date", datetime.now().strftime("%Y-%m-%d"), date_attrs, parent=publication_stmt)
        self._create_tei_element("availability", parent=publication_stmt)
        self._create_tei_element("p", "本识别结果仅供研究使用", parent=publication_stmt.find(f"{{{TEI_NS}}}availability"))
        
        source_desc = self._create_tei_element("sourceDesc", parent=file_desc)
        bibl = self._create_tei_element("bibl", parent=source_desc)
        self._create_tei_element("title", task.file_name, parent=bibl)
        idno_attrs = {"type": "task"}
        self._create_tei_element("idno", task_id, idno_attrs, parent=bibl)
        ms_desc = self._create_tei_element("msDesc", parent=source_desc)
        ms_identifier = self._create_tei_element("msIdentifier", parent=ms_desc)
        self._create_tei_element("repository", "待入藏", parent=ms_identifier)
        self._create_tei_element("idno", task_id, parent=ms_identifier)
        
        profile_desc = self._create_tei_element("profileDesc", parent=tei_header)
        lang_usage = self._create_tei_element("langUsage", parent=profile_desc)
        lang_attrs = {
            f"{{{XML_NS}}}id": "zh-CN",
            "ident": "zh-CN"
        }
        self._create_tei_element("language", "中文", lang_attrs, parent=lang_usage)
        
        text = self._create_tei_element("text", parent=tei)
        text.set(f"{{{XML_NS}}}lang", "zh-CN")
        body = self._create_tei_element("body", parent=text)
        
        surface_grp = None
        if include_coordinates:
            facs = self._create_tei_element("facsimile", parent=tei)
            surface_grp = self._create_tei_element("surfaceGrp", parent=facs)
        
        for page_idx, page_result in enumerate(page_results):
            pb_attrs = {
                "n": str(page_result.page_number),
                f"{{{XML_NS}}}id": f"pb-{page_result.page_number}"
            }
            if page_result.image_path:
                pb_attrs["facs"] = page_result.image_path
            self._create_tei_element("pb", attrs=pb_attrs, parent=body)
            
            if include_coordinates and surface_grp is not None:
                surface_attrs = {
                    f"{{{XML_NS}}}id": f"surface-{page_result.page_number}",
                    "n": str(page_result.page_number)
                }
                if page_result.image_path:
                    surface_attrs["facs"] = page_result.image_path
                surface = self._create_tei_element("surface", attrs=surface_attrs, parent=surface_grp)
                if page_result.width and page_result.height:
                    graphic_attrs = {
                        "width": str(page_result.width),
                        "height": str(page_result.height)
                    }
                    self._create_tei_element("graphic", attrs=graphic_attrs, parent=surface)
            
            columns = self._group_by_columns(page_result.text_lines)
            
            for col_idx, column_lines in enumerate(columns):
                div_attrs = {
                    "type": "textpart",
                    "subtype": "column",
                    "n": f"{page_result.page_number}.{col_idx + 1}",
                    f"{{{XML_NS}}}id": f"col-{page_result.page_number}-{col_idx + 1}"
                }
                div = self._create_tei_element("div", attrs=div_attrs, parent=body)
                
                for line_idx, text_line in enumerate(column_lines):
                    if not text_line.content:
                        continue
                    
                    line_id = f"l-{page_result.page_number}-{col_idx + 1}-{line_idx + 1}"
                    lb_attrs = {
                        "n": str(line_idx + 1),
                        f"{{{XML_NS}}}id": f"lb-{line_id}"
                    }
                    self._create_tei_element("lb", attrs=lb_attrs, parent=div)
                    
                    seg_attrs = {
                        f"{{{XML_NS}}}id": f"seg-{line_id}",
                        "type": "line"
                    }
                    if include_confidence and text_line.confidence is not None:
                        seg_attrs["cert"] = self._confidence_to_cert(text_line.confidence)
                    
                    if include_coordinates or include_confidence:
                        seg = self._create_tei_element("seg", attrs=seg_attrs, parent=div)
                        
                        chars = list(text_line.content)
                        for char_idx, char in enumerate(chars):
                            w_attrs = {
                                f"{{{XML_NS}}}id": f"w-{line_id}-{char_idx + 1}"
                            }
                            if include_coordinates and char_idx < len(text_line.text_boxes):
                                text_box = text_line.text_boxes[char_idx]
                                zone_id = f"zone-{line_id}-{char_idx + 1}"
                                w_attrs["facs"] = f"#{zone_id}"
                                
                                if surface_grp is not None:
                                    zone_attrs = {
                                        f"{{{XML_NS}}}id": zone_id,
                                        "points": f"{text_box.x1},{text_box.y1} {text_box.x2},{text_box.y2} {text_box.x3},{text_box.y3} {text_box.x4},{text_box.y4}"
                                    }
                                    for surface in surface_grp.findall(f"{{{TEI_NS}}}surface"):
                                        if surface.get(f"{{{XML_NS}}}id") == f"surface-{page_result.page_number}":
                                            self._create_tei_element("zone", char, zone_attrs, parent=surface)
                                            break
                            
                            if include_confidence:
                                if char_idx < len(text_line.text_boxes) and text_line.text_boxes[char_idx].confidence is not None:
                                    w_attrs["cert"] = self._confidence_to_cert(text_line.text_boxes[char_idx].confidence)
                                elif text_line.confidence is not None:
                                    w_attrs["cert"] = self._confidence_to_cert(text_line.confidence)
                            
                            self._create_tei_element("w", char, w_attrs, parent=seg)
                            
                            if include_confidence:
                                degree = "1.0000"
                                if char_idx < len(text_line.text_boxes) and text_line.text_boxes[char_idx].confidence is not None:
                                    degree = f"{text_line.text_boxes[char_idx].confidence:.4f}"
                                elif text_line.confidence is not None:
                                    degree = f"{text_line.confidence:.4f}"
                                certainty_attrs = {
                                    "target": f"#w-{line_id}-{char_idx + 1}",
                                    "degree": degree,
                                    "locus": "value"
                                }
                                self._create_tei_element("certainty", attrs=certainty_attrs, parent=seg)
                    else:
                        seg = self._create_tei_element("seg", text_line.content, seg_attrs, parent=div)
        
        rough_string = tostring(tei, encoding='utf-8', xml_declaration=True)
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
