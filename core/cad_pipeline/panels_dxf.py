from __future__ import annotations

from typing import List, Tuple, Optional
import os
import math
import ezdxf
from ezdxf.enums import TextEntityAlignment

from .geometry_engine import (
    ConicalHelixEngine,
    PanelDefinition,
    PanelFlatPattern,
)

from .pattern_mapper import MappedLine, MappedPolyline


# ========================
# ثوابت الطبقات والإعدادات
# ========================

class DXFLayers:
    """أسماء وألوان الطبقات في ملف DXF"""
    OUTLINE = ("OUTLINE", 1)        # أحمر
    HOLES = ("HOLES", 5)            # أزرق
    SAFE_ZONE = ("SAFE_ZONE", 8)    # رمادي
    PATTERN = ("PATTERN", 3)        # أخضر
    TEXT = ("TEXT", 7)              # أبيض/أسود
    DIMENSIONS = ("DIMENSIONS", 4)  # سماوي
    CENTERLINE = ("CENTERLINE", 6)  # ماجنتا

class DXFSettings:
    """إعدادات توليد DXF"""
    DEFAULT_HOLE_RADIUS = 5.0
    HOLE_POSITIONS_REL = [0.05, 0.15, 0.85, 0.95]
    ARC_SEGMENTS = 64                # عدد الأجزاء لتقريب القوس
    TEXT_HEIGHT = 20.0
    DIM_TEXT_HEIGHT = 15.0
    DXF_VERSION = "R2010"


# ========================
# مولد DXF الرئيسي
# ========================

class PanelDXFGenerator:
    """
    مولد ملفات DXF المُحسّن:
    - توليد ملفات DXF لكل لوح مفرود
    - رسم دقيق للحدود والقوسين
    - إضافة ثقوب المسامير
    - رسم المناطق الآمنة
    - تطبيق الباترن المحول
    - إضافة أبعاد ومعلومات نصية
    - دعم الطبقات المتعددة
    """

    def __init__(self, engine: ConicalHelixEngine):
        if engine is None:
            raise ValueError("المحرك الهندسي لا يمكن أن يكون None")
        
        self.engine = engine
        self.layers = DXFLayers()
        self.settings = DXFSettings()

    # ========================
    # API رئيسي
    # ========================

    def export_all_panels(
        self,
        output_folder: str,
        base_name: str = "panel",
        patterns_per_panel: Optional[dict[int, dict[str, List]]] = None,
        include_dimensions: bool = True,
        include_centerlines: bool = True,
    ) -> List[str]:
        """
        توليد ملف DXF لكل لوح في engine.panels
        
        Args:
            output_folder: مجلد الإخراج
            base_name: اسم أساسي للملفات
            patterns_per_panel: الباترنات المحولة لكل لوح
            include_dimensions: إضافة الأبعاد
            include_centerlines: إضافة خطوط المحاور
        
        Returns:
            قائمة بمسارات الملفات المُنشأة
        """
        if not self.engine.panels:
            raise RuntimeError(
                "لم يتم حساب الألواح بعد.\n"
                "استدع compute_panels_layout في المحرك الهندسي أولاً."
            )

        # إنشاء مجلد الإخراج
        os.makedirs(output_folder, exist_ok=True)
        
        generated_files = []
        total = len(self.engine.panels)
        
        print(f"\n{'='*60}")
        print(f"📄 بدء توليد ملفات DXF...")
        print(f"   المجلد: {output_folder}")
        print(f"   عدد الألواح: {total}")
        print(f"{'='*60}\n")

        for i, panel in enumerate(self.engine.panels, 1):
            flat = self.engine.get_flat_pattern_for_panel(panel.panel_id)
            filename = os.path.join(output_folder, f"{base_name}_{panel.panel_id:02d}.dxf")

            # الحصول على الباترن إن وجد
            panel_pattern = None
            if patterns_per_panel is not None:
                panel_pattern = patterns_per_panel.get(panel.panel_id)

            # توليد الملف
            self._export_single_panel(
                filename=filename,
                panel=panel,
                flat=flat,
                panel_pattern=panel_pattern,
                include_dimensions=include_dimensions,
                include_centerlines=include_centerlines,
            )
            
            generated_files.append(filename)
            
            # تقرير التقدم
            if i <= 5 or i % 10 == 0 or i == total:
                has_pattern = "✓" if panel_pattern else "✗"
                print(f"✅ {i:02d}/{total:02d} - {os.path.basename(filename)} [باترن: {has_pattern}]")

        print(f"\n{'='*60}")
        print(f"✅ اكتمل توليد {len(generated_files)} ملف DXF")
        print(f"{'='*60}\n")
        
        return generated_files

    # ========================
    # توليد ملف لوح واحد
    # ========================

    def _export_single_panel(
        self,
        filename: str,
        panel: PanelDefinition,
        flat: PanelFlatPattern,
        panel_pattern: Optional[dict[str, List]] = None,
        include_dimensions: bool = True,
        include_centerlines: bool = True,
    ) -> None:
        """
        توليد ملف DXF واحد للوح مفرود
        
        Args:
            filename: اسم الملف
            panel: تعريف اللوح في الفراغ 3D
            flat: بيانات الإفراد
            panel_pattern: الباترن المحول (اختياري)
            include_dimensions: إضافة الأبعاد
            include_centerlines: إضافة خطوط المحاور
        """
        # إنشاء مستند DXF جديد
        doc = ezdxf.new(self.settings.DXF_VERSION)
        msp = doc.modelspace()

        # إنشاء الطبقات
        self._ensure_layers(doc)

        # 1) رسم خطوط المحاور (اختياري)
        if include_centerlines:
            self._draw_centerlines(msp, flat)

        # 2) رسم Outline اللوح (القوسين الخارجي والداخلي)
        self._draw_panel_outline(msp, flat)

        # 3) رسم Safe Zone
        if flat.safe_zone > 0:
            self._draw_safe_zone(msp, flat)

        # 4) إضافة ثقوب المسامير
        self._add_assembly_holes(msp, flat)

        # 5) رسم الباترن المحول (إن وجد)
        if panel_pattern is not None:
            lines: List[MappedLine] = panel_pattern.get("lines", [])
            polys: List[MappedPolyline] = panel_pattern.get("polylines", [])
            self._draw_mapped_pattern(msp, lines, polys)

        # 6) إضافة الأبعاد (اختياري)
        if include_dimensions:
            self._add_dimensions(msp, flat)

        # 7) إضافة معلومات نصية
        self._add_text_info(msp, panel, flat)

        # حفظ الملف
        doc.saveas(filename)

    # ========================
    # إنشاء الطبقات
    # ========================

    def _ensure_layers(self, doc: ezdxf.document.Drawing):
        """التأكد من وجود جميع الطبقات المطلوبة"""
        layers_config = [
            self.layers.OUTLINE,
            self.layers.HOLES,
            self.layers.SAFE_ZONE,
            self.layers.PATTERN,
            self.layers.TEXT,
            self.layers.DIMENSIONS,
            self.layers.CENTERLINE,
        ]

        for name, color in layers_config:
            if name not in doc.layers:
                doc.layers.new(name=name, dxfattribs={"color": color})

    # ========================
    # رسم حدود اللوح (Outline)
    # ========================

    def _draw_panel_outline(self, msp, flat: PanelFlatPattern):
        """
        رسم حدود اللوح المفرود:
        - القوس الخارجي
        - القوس الداخلي
        - خطوط الجانبين الراديالية
        """
        num_segments = self.settings.ARC_SEGMENTS
        
        # بناء نقاط القوس الخارجي والداخلي
        outer_points = self._build_arc_points(flat.r_outer, flat.arc_angle, num_segments)
        inner_points = self._build_arc_points(flat.r_inner, flat.arc_angle, num_segments)
        
        # رسم القوس الخارجي
        self._draw_polyline(msp, outer_points, self.layers.OUTLINE[0], closed=False)
        
        # رسم القوس الداخلي
        self._draw_polyline(msp, inner_points, self.layers.OUTLINE[0], closed=False)
        
        # رسم الجانبين الراديالية
        # الجانب الأيسر (عند زاوية 0)
        msp.add_line(
            (flat.r_inner, 0),
            (flat.r_outer, 0),
            dxfattribs={"layer": self.layers.OUTLINE[0]}
        )
        
        # الجانب الأيمن (عند الزاوية النهائية)
        angle_rad = math.radians(flat.arc_angle)
        inner_end = (flat.r_inner * math.cos(angle_rad), flat.r_inner * math.sin(angle_rad))
        outer_end = (flat.r_outer * math.cos(angle_rad), flat.r_outer * math.sin(angle_rad))
        
        msp.add_line(
            inner_end,
            outer_end,
            dxfattribs={"layer": self.layers.OUTLINE[0]}
        )

    def _build_arc_points(
        self,
        radius: float,
        arc_angle_deg: float,
        num_segments: int
    ) -> List[Tuple[float, float]]:
        """
        بناء نقاط القوس
        
        Args:
            radius: نصف القطر
            arc_angle_deg: زاوية القوس بالدرجات
            num_segments: عدد الأجزاء
        
        Returns:
            قائمة النقاط
        """
        theta_total_rad = math.radians(arc_angle_deg)
        points = []

        for i in range(num_segments + 1):
            t = i / num_segments
            theta = t * theta_total_rad
            x = radius * math.cos(theta)
            y = radius * math.sin(theta)
            points.append((x, y))

        return points

    # ========================
    # رسم Polyline
    # ========================

    def _draw_polyline(
        self,
        msp,
        points: List[Tuple[float, float]],
        layer: str,
        closed: bool = False,
    ) -> None:
        """رسم polyline من قائمة نقاط"""
        if not points or len(points) < 2:
            return

        pline = msp.add_lwpolyline(points, dxfattribs={"layer": layer})
        if closed:
            pline.closed = True

    # ========================
    # رسم Safe Zone
    # ========================

    def _draw_safe_zone(self, msp, flat: PanelFlatPattern) -> None:
        """
        رسم حدود المنطقة الآمنة (Safe Zone)
        """
        # حساب نصف القطر للمنطقة الآمنة
        r_inner_safe = flat.r_inner + flat.safe_zone
        r_outer_safe = flat.r_outer - flat.safe_zone
        
        # التحقق من منطقية القيم
        if r_outer_safe <= r_inner_safe:
            return  # المنطقة الآمنة كبيرة جداً، لا يمكن رسمها
        
        # رسم القوسين الداخلي والخارجي للمنطقة الآمنة
        num_segments = self.settings.ARC_SEGMENTS // 2  # دقة أقل
        
        inner_safe_points = self._build_arc_points(r_inner_safe, flat.arc_angle, num_segments)
        outer_safe_points = self._build_arc_points(r_outer_safe, flat.arc_angle, num_segments)
        
        # رسم بخطوط متقطعة
        self._draw_polyline(msp, inner_safe_points, self.layers.SAFE_ZONE[0], closed=False)
        self._draw_polyline(msp, outer_safe_points, self.layers.SAFE_ZONE[0], closed=False)
        
        # إضافة علامات نصية
        mid_angle_rad = math.radians(flat.arc_angle / 2.0)
        
        # علامة داخلية
        text_r_inner = r_inner_safe
        text_x_inner = text_r_inner * math.cos(mid_angle_rad)
        text_y_inner = text_r_inner * math.sin(mid_angle_rad)
        
        msp.add_text(
            f"SAFE {flat.safe_zone:.0f}mm",
            dxfattribs={
                "layer": self.layers.SAFE_ZONE[0],
                "height": self.settings.DIM_TEXT_HEIGHT * 0.7,
            }
        ).set_placement((text_x_inner, text_y_inner), align=TextEntityAlignment.MIDDLE_CENTER)

    # ========================
    # ثقوب المسامير
    # ========================

    def _add_assembly_holes(self, msp, flat: PanelFlatPattern) -> None:
        """
        إضافة ثقوب مسامير التجميع
        """
        hole_radius = self.settings.DEFAULT_HOLE_RADIUS
        offset_from_edge = flat.safe_zone + 20.0
        
        # التأكد من أن الثقوب لن تخرج عن الحدود
        r_hole = flat.r_inner + offset_from_edge
        if r_hole + hole_radius > flat.r_outer:
            r_hole = (flat.r_inner + flat.r_outer) / 2.0  # وسط اللوح

        for pos in self.settings.HOLE_POSITIONS_REL:
            theta = math.radians(flat.arc_angle * pos)
            x = r_hole * math.cos(theta)
            y = r_hole * math.sin(theta)

            msp.add_circle(
                (x, y),
                hole_radius,
                dxfattribs={"layer": self.layers.HOLES[0]}
            )

    # ========================
    # رسم الباترن المحول
    # ========================

    def _draw_mapped_pattern(
        self,
        msp,
        lines: List[MappedLine],
        polys: List[MappedPolyline],
    ) -> None:
        """
        رسم الباترن المحول على طبقة PATTERN
        """
        # رسم الخطوط
        for line in lines:
            msp.add_line(
                line.start,
                line.end,
                dxfattribs={"layer": self.layers.PATTERN[0]}
            )

        # رسم الـ polylines
        for poly in polys:
            if not poly.points or len(poly.points) < 2:
                continue
            
            pline = msp.add_lwpolyline(
                poly.points,
                dxfattribs={"layer": self.layers.PATTERN[0]}
            )
            if poly.closed:
                pline.closed = True

    # ========================
    # خطوط المحاور
    # ========================

    def _draw_centerlines(self, msp, flat: PanelFlatPattern) -> None:
        """
        رسم خطوط المحاور (مركز القوس)
        """
        # خط شعاعي في منتصف القوس
        mid_angle_rad = math.radians(flat.arc_angle / 2.0)
        
        # من المركز إلى ما بعد القوس الخارجي
        extend = 50.0
        r_max = flat.r_outer + extend
        
        x_end = r_max * math.cos(mid_angle_rad)
        y_end = r_max * math.sin(mid_angle_rad)
        
        msp.add_line(
            (0, 0),
            (x_end, y_end),
            dxfattribs={"layer": self.layers.CENTERLINE[0]}
        )
        
        # دائرة صغيرة في المركز
        msp.add_circle(
            (0, 0),
            5.0,
            dxfattribs={"layer": self.layers.CENTERLINE[0]}
        )

    # ========================
    # الأبعاد
    # ========================

    def _add_dimensions(self, msp, flat: PanelFlatPattern) -> None:
        """
        إضافة أبعاد توضيحية
        """
        # بعد نصف القطر الداخلي
        msp.add_line(
            (0, 0),
            (flat.r_inner, 0),
            dxfattribs={"layer": self.layers.DIMENSIONS[0]}
        )
        
        msp.add_text(
            f"R{flat.r_inner:.0f}",
            dxfattribs={
                "layer": self.layers.DIMENSIONS[0],
                "height": self.settings.DIM_TEXT_HEIGHT,
            }
        ).set_placement((flat.r_inner / 2, -30), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # بعد نصف القطر الخارجي
        angle_rad = math.radians(flat.arc_angle / 2.0)
        x_outer = flat.r_outer * math.cos(angle_rad)
        y_outer = flat.r_outer * math.sin(angle_rad)
        
        msp.add_line(
            (0, 0),
            (x_outer, y_outer),
            dxfattribs={"layer": self.layers.DIMENSIONS[0]}
        )
        
        # نص البعد
        text_r = flat.r_outer + 30
        text_x = text_r * math.cos(angle_rad)
        text_y = text_r * math.sin(angle_rad)
        
        msp.add_text(
            f"R{flat.r_outer:.0f}",
            dxfattribs={
                "layer": self.layers.DIMENSIONS[0],
                "height": self.settings.DIM_TEXT_HEIGHT,
            }
        ).set_placement((text_x, text_y), align=TextEntityAlignment.MIDDLE_CENTER)

    # ========================
    # المعلومات النصية
    # ========================

    def _add_text_info(self, msp, panel: PanelDefinition, flat: PanelFlatPattern) -> None:
        """
        إضافة معلومات نصية عن اللوح
        """
        # حساب موضع النص (خارج اللوح)
        text_x = flat.r_outer + 100
        text_y_start = 50
        line_spacing = 25
        
        # معلومات اللوح
        info_lines = [
            f"PANEL ID: {panel.panel_id}",
            f"Type: {flat.panel_type.upper()}",
            f"",
            f"R_outer: {flat.r_outer:.1f} mm",
            f"R_inner: {flat.r_inner:.1f} mm",
            f"Arc Angle: {flat.arc_angle:.2f}°",
            f"",
            f"Z_start: {panel.z_start:.1f} mm",
            f"Z_end: {panel.z_end:.1f} mm",
            f"ΔZ: {panel.z_end - panel.z_start:.1f} mm",
            f"",
            f"Sheet Length: {flat.sheet_length_flat:.1f} mm",
            f"Sheet Width: {flat.sheet_width_flat:.1f} mm",
            f"Overlap: {flat.overlap:.1f} mm",
            f"Safe Zone: {flat.safe_zone:.1f} mm",
        ]
        
        for i, line in enumerate(info_lines):
            if line:  # تخطي السطور الفارغة في الحساب
                msp.add_text(
                    line,
                    dxfattribs={
                        "layer": self.layers.TEXT[0],
                        "height": self.settings.TEXT_HEIGHT * 0.7,
                    }
                ).set_placement((text_x, text_y_start - i * line_spacing))
            else:
                # سطر فارغ = مسافة أصغر
                pass
        
        # عنوان كبير
        title_y = text_y_start + 50
        msp.add_text(
            f"PANEL {panel.panel_id:02d}",
            dxfattribs={
                "layer": self.layers.TEXT[0],
                "height": self.settings.TEXT_HEIGHT * 1.5,
            }
        ).set_placement((text_x, title_y))


# ========================
# دوال مساعدة عامة
# ========================

def quick_export_panel(
    engine: ConicalHelixEngine,
    panel_id: int,
    output_path: str,
    pattern_data: Optional[dict] = None
) -> str:
    """
    تصدير سريع للوح واحد
    
    Args:
        engine: المحرك الهندسي
        panel_id: رقم اللوح
        output_path: مسار ملف الإخراج
        pattern_data: بيانات الباترن (اختياري)
    
    Returns:
        مسار الملف المُنشأ
    """
    panel = engine.get_panel_by_id(panel_id)
    if panel is None:
        raise ValueError(f"لا يوجد لوح برقم {panel_id}")
    
    flat = engine.get_flat_pattern_for_panel(panel_id)
    
    gen = PanelDXFGenerator(engine)
    
    patterns_dict = {panel_id: pattern_data} if pattern_data else None
    
    gen._export_single_panel(
        filename=output_path,
        panel=panel,
        flat=flat,
        panel_pattern=pattern_data,
    )
    
    print(f"✅ تم حفظ اللوح {panel_id}: {output_path}")
    return output_path
