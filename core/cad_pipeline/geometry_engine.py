from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import math
import numpy as np


# =========================
#   Data Classes
# =========================

@dataclass
class EngineConfig:
    """إعدادات المحرك الهندسي - جميع القيم بالملليمتر"""
    sheet_width: float      # عرض اللوح (Pitch) على محور Z
    overlap: float          # التداخل الطولي بين الألواح
    safe_zone: float        # المنطقة الآمنة أعلى وأسفل اللوح
    raw_sheet_length: float = 3000.0
    units: str = "mm"
    
    # ثوابت القاعدة (بدلاً من magic numbers)
    base_height_ratio: float = 0.15  # نسبة ارتفاع القاعدة من الارتفاع الكلي
    min_base_panels: int = 3         # الحد الأدنى للألواح القاعدية
    max_base_panels: int = 10        # الحد الأقصى


@dataclass
class ConeGeometry:
    """توصيف كامل للمخروط الناقص وإفراده"""
    d_top: float
    d_bottom: float
    height: float
    r_top: float
    r_bottom: float
    slant_height: float
    taper_angle: float      # درجة
    r_large_flat: float
    r_small_flat: float
    arc_angle: float        # درجة


@dataclass
class PanelDefinition:
    """تعريف لوح واحد على العمود في الفراغ (3D layout)"""
    panel_id: int
    z_start: float
    z_end: float
    r_start: float
    r_end: float
    helix_turn_start: float  # راديان
    helix_turn_end: float    # راديان
    sheet_effective_height: float
    panel_type: str = "normal"


@dataclass
class PanelFlatPattern:
    """بيانات الإفراد لكل لوح"""
    panel_id: int
    r_outer: float
    r_inner: float
    arc_angle: float
    sheet_width_flat: float
    sheet_length_flat: float
    safe_zone: float
    overlap: float
    panel_type: str = "normal"


# =========================
#   المحرك الهندسي الرئيسي
# =========================

class ConicalHelixEngine:
    """
    المحرك الهندسي المُصحح:
    - يحسب خصائص المخروط الناقص بدقة
    - يقسم العمود إلى ألواح حلزونية متناسقة
    - يضمن أن اللوح الأول يبدأ من Z=0 بزاوية صحيحة
    - يعطي بيانات إفراد دقيقة لكل لوح
    """

    def __init__(self, d_top: float, d_bottom: float, height: float, config: EngineConfig):
        self._validate_inputs(d_top, d_bottom, height, config)
        
        self.config = config
        self.cone: ConeGeometry = self._compute_cone_geometry(d_top, d_bottom, height)
        self.panels: List[PanelDefinition] = []
        
        # حساب زاوية بداية الحلزون (الإصلاح الرئيسي!)
        self.helix_start_angle: float = 0.0  # يمكن تعديله لاحقاً

    # ---------- التحقق من المدخلات ----------

    def _validate_inputs(self, d_top: float, d_bottom: float, height: float, config: EngineConfig):
        """تحقق شامل من صحة المدخلات"""
        if d_top >= d_bottom:
            raise ValueError("القطر العلوي يجب أن يكون أصغر من السفلي")
        if height <= 0:
            raise ValueError("الارتفاع يجب أن يكون أكبر من صفر")
        if config.sheet_width <= 0:
            raise ValueError("عرض اللوح يجب أن يكون أكبر من صفر")
        if config.safe_zone < 0 or config.overlap < 0:
            raise ValueError("المنطقة الآمنة والتداخل يجب أن يكونا >= 0")
        if config.safe_zone * 2 >= config.sheet_width:
            raise ValueError(f"المنطقة الآمنة كبيرة جداً: {config.safe_zone*2} >= {config.sheet_width}")
        if config.overlap >= config.sheet_width:
            raise ValueError("التداخل يجب أن يكون أقل من عرض اللوح")

    # ---------- خصائص المخروط ----------

    def _compute_cone_geometry(self, d_top: float, d_bottom: float, height: float) -> ConeGeometry:
        """حساب الخصائص الهندسية للمخروط الناقص"""
        r_top = d_top / 2.0
        r_bottom = d_bottom / 2.0
        
        slant = math.sqrt(height**2 + (r_bottom - r_top)**2)
        angle_rad = math.atan2((r_bottom - r_top), height)
        taper_angle_deg = math.degrees(angle_rad)
        
        # أنصاف أقطار الإفراد
        R_large = (r_bottom * slant) / (r_bottom - r_top)
        R_small = R_large - slant
        
        # زاوية القوس الكلية
        phi_rad = (2 * math.pi * r_bottom) / R_large
        phi_deg = math.degrees(phi_rad)
        
        return ConeGeometry(
            d_top=d_top, d_bottom=d_bottom, height=height,
            r_top=r_top, r_bottom=r_bottom,
            slant_height=slant, taper_angle=taper_angle_deg,
            r_large_flat=R_large, r_small_flat=R_small,
            arc_angle=phi_deg
        )

    # ---------- نصف القطر عند ارتفاع Z ----------

    def _radius_at_z(self, z: float) -> float:
        """حساب نصف القطر عند ارتفاع z (تدرج خطي)"""
        z = max(0.0, min(z, self.cone.height))
        ratio = z / self.cone.height
        return self.cone.r_bottom + ratio * (self.cone.r_top - self.cone.r_bottom)

    # ---------- تقسيم العمود إلى ألواح (المُصحح!) ----------

    def compute_panels_layout(self) -> List[PanelDefinition]:
        """
        تقسيم العمود إلى ألواح حلزونية - النسخة المُصححة
        
        الإصلاحات:
        1. ✅ زاوية البداية متسقة مع الحلزون
        2. ✅ حساب Z صحيح بدون double counting
        3. ✅ ضمان Z=0 للوح الأول
        4. ✅ validation شامل
        """
        pitch = self.config.sheet_width
        
        # حساب عدد اللفات والزاوية الكلية
        calculated_turns = self.cone.height / pitch
        theta_total = 2.0 * math.pi * calculated_turns
        
        panels: List[PanelDefinition] = []
        panel_id = 1
        max_segment_len = self.config.raw_sheet_length - self.config.overlap
        
        # ========== الجزء 1: الألواح القاعدية ==========
        
        num_base_panels = self._calculate_num_base_panels()
        base_z_height = self.cone.height * self.config.base_height_ratio
        base_theta_total = (base_z_height / self.cone.height) * theta_total
        
        print(f"\n{'='*60}")
        print(f"🔧 معلومات القاعدة:")
        print(f"   - عدد الألواح القاعدية: {num_base_panels}")
        print(f"   - ارتفاع القاعدة: {base_z_height:.0f} مم ({self.config.base_height_ratio*100:.0f}%)")
        print(f"   - زاوية القاعدة الكلية: {math.degrees(base_theta_total):.1f}°")
        print(f"{'='*60}\n")
        
        # بدء الحلزون من الزاوية المحددة
        current_theta = self.helix_start_angle
        current_z = 0.0
        
        # توزيع الزاوية على الألواح القاعدية
        theta_per_base = base_theta_total / num_base_panels
        
        for i in range(num_base_panels):
            progress = i / max(1, num_base_panels - 1)
            panel_type, height_factor = self._get_base_panel_params(progress)
            
            # ✅ حساب Z بشكل صحيح (بدون double counting)
            z_start = current_z
            delta_z = (theta_per_base / theta_total) * self.cone.height
            z_end = min(z_start + delta_z, base_z_height)
            
            # حساب الزوايا
            theta_start = current_theta
            theta_end = current_theta + theta_per_base
            
            # حساب الأنصاف
            r_start = self._radius_at_z(z_start)
            r_end = self._radius_at_z(z_end)
            
            # الارتفاع الفعال
            effective_height = (self.config.sheet_width - 2.0 * self.config.safe_zone) * height_factor
            
            panels.append(PanelDefinition(
                panel_id=panel_id,
                z_start=z_start,
                z_end=z_end,
                r_start=r_start,
                r_end=r_end,
                helix_turn_start=theta_start,
                helix_turn_end=theta_end,
                sheet_effective_height=effective_height,
                panel_type=panel_type
            ))
            
            print(f"   📐 لوح {panel_id:02d} ({panel_type:12s}): "
                  f"Z=[{z_start:6.0f} → {z_end:6.0f}] "
                  f"ΔZ={z_end-z_start:5.0f}مم, "
                  f"θ={math.degrees(theta_end-theta_start):5.1f}°")
            
            panel_id += 1
            current_theta = theta_end
            current_z = z_end
        
        # ========== الجزء 2: الألواح العادية ==========
        
        print(f"\n{'='*60}")
        print(f"🔧 الألواح العادية:")
        print(f"{'='*60}\n")
        
        panel_count = 0
        while current_z < self.cone.height - 0.1:  # هامش صغير
            z_start = current_z
            r_start = self._radius_at_z(z_start)
            
            # حساب delta_theta بناءً على طول اللوح المتاح
            circumference = 2 * math.pi * r_start
            if circumference > 0:
                helical_factor = math.sqrt(circumference**2 + pitch**2) / circumference
            else:
                helical_factor = 1.0
            
            if r_start > 0:
                delta_theta = max_segment_len / (r_start * helical_factor)
            else:
                delta_theta = 0.1
            
            # التأكد من عدم تجاوز النهاية
            remaining_theta = theta_total - current_theta
            delta_theta = min(delta_theta, remaining_theta)
            
            # ✅ حساب z_end الصحيح من delta_theta
            delta_z = (delta_theta / theta_total) * self.cone.height
            z_end = min(z_start + delta_z, self.cone.height)
            
            theta_start = current_theta
            theta_end = current_theta + delta_theta
            r_end = self._radius_at_z(z_end)
            
            effective_height = self.config.sheet_width - 2.0 * self.config.safe_zone
            
            panels.append(PanelDefinition(
                panel_id=panel_id,
                z_start=z_start,
                z_end=z_end,
                r_start=r_start,
                r_end=r_end,
                helix_turn_start=theta_start,
                helix_turn_end=theta_end,
                sheet_effective_height=effective_height,
                panel_type="normal"
            ))
            
            if panel_count < 5 or panel_count % 10 == 0:  # طباعة عينات
                print(f"   📐 لوح {panel_id:02d} (normal      ): "
                      f"Z=[{z_start:6.0f} → {z_end:6.0f}] "
                      f"ΔZ={z_end-z_start:5.0f}مم, "
                      f"θ={math.degrees(theta_end-theta_start):5.1f}°")
            
            panel_id += 1
            panel_count += 1
            current_theta = theta_end
            current_z = z_end
            
            # حماية من infinite loop
            if panel_count > 1000:
                raise RuntimeError("عدد الألواح تجاوز 1000 - يرجى مراجعة الإعدادات")
        
        self.panels = panels
        
        print(f"\n{'='*60}")
        print(f"✅ اكتمل التقسيم: {len(panels)} لوح إجمالي")
        print(f"   - ألواح قاعدية: {num_base_panels}")
        print(f"   - ألواح عادية: {len(panels) - num_base_panels}")
        print(f"{'='*60}\n")
        
        # ✅ Validation نهائي
        self._validate_panels()
        
        return panels

    def _calculate_num_base_panels(self) -> int:
        """حساب عدد الألواح القاعدية بناءً على الأبعاد"""
        # صيغة محسّنة بناءً على نسبة الأقطار والارتفاع
        diameter_ratio = self.cone.d_bottom / self.cone.d_top
        
        # كلما كانت القاعدة أكبر، نحتاج ألواح أكثر للانتقال السلس
        if diameter_ratio > 3.0:
            num = int(4 + (diameter_ratio - 3.0) * 1.5)
        elif diameter_ratio > 2.0:
            num = int(3 + (diameter_ratio - 2.0) * 2)
        else:
            num = 3
        
        # تطبيق الحدود
        num = max(self.config.min_base_panels, min(num, self.config.max_base_panels))
        return num

    def _get_base_panel_params(self, progress: float) -> tuple[str, float]:
        """تحديد نوع اللوح القاعدي ومعامل الارتفاع"""
        if progress < 0.25:
            return "triangular", 0.4
        elif progress < 0.50:
            return "trapezoidal", 0.65
        elif progress < 0.75:
            return "short_rect", 0.85
        else:
            return "base_rect", 0.95

    def _validate_panels(self):
        """التحقق من صحة الألواح المُنتجة"""
        if not self.panels:
            raise RuntimeError("لم يتم إنشاء أي ألواح!")
        
        # التحقق من أن اللوح الأول يبدأ من Z=0
        first_panel = self.panels[0]
        if abs(first_panel.z_start) > 0.1:
            raise RuntimeError(f"اللوح الأول لا يبدأ من القاعدة! z_start={first_panel.z_start}")
        
        # التحقق من أن الألواح تغطي الارتفاع الكلي
        last_panel = self.panels[-1]
        coverage = last_panel.z_end / self.cone.height
        if coverage < 0.98:
            print(f"⚠️  تحذير: الألواح تغطي {coverage*100:.1f}% فقط من الارتفاع")
        
        # التحقق من التداخلات والفجوات
        for i in range(len(self.panels) - 1):
            gap = self.panels[i+1].z_start - self.panels[i].z_end
            if abs(gap) > 1.0:  # هامش 1 مم
                print(f"⚠️  فجوة بين لوح {i+1} و {i+2}: {gap:.1f} مم")

    # ---------- إفراد الألواح ----------

    def get_panel_by_id(self, panel_id: int) -> Optional[PanelDefinition]:
        """الحصول على لوح معين برقمه"""
        for p in self.panels:
            if p.panel_id == panel_id:
                return p
        return None

    def get_flat_pattern_for_panel(self, panel_id: int) -> PanelFlatPattern:
        """حساب بيانات الإفراد للوح معين"""
        if not self.panels:
            raise RuntimeError("لم يتم حساب الألواح. استدع compute_panels_layout أولاً")
        
        panel = self.get_panel_by_id(panel_id)
        if panel is None:
            raise ValueError(f"لا يوجد لوح برقم {panel_id}")
        
        # توجيه لدوال الإفراد المتخصصة
        if panel.panel_type == "triangular":
            return self._get_triangular_panel(panel)
        elif panel.panel_type == "trapezoidal":
            return self._get_trapezoidal_panel(panel)
        elif panel.panel_type == "short_rect":
            return self._get_short_rectangular_panel(panel)
        elif panel.panel_type == "base_rect":
            return self._get_base_rectangular_panel(panel)
        else:
            return self._get_normal_rectangular_panel(panel)

    def _get_triangular_panel(self, panel: PanelDefinition) -> PanelFlatPattern:
        """إفراد لوح مثلثي"""
        pitch = self.config.sheet_width
        delta_theta = panel.helix_turn_end - panel.helix_turn_start
        r_avg = (panel.r_start + panel.r_end) / 2.0
        
        helical_len = delta_theta * math.sqrt(r_avg**2 + (pitch / (2 * np.pi))**2)
        
        r_outer = panel.r_end + pitch * 0.4
        r_inner = max(panel.r_start * 0.15, 50.0)
        r_mid = (r_outer + r_inner) / 2.0
        arc_angle = math.degrees(helical_len / r_mid) * 1.4
        
        strip_width = r_outer - r_inner
        sheet_length = 2.0 * np.pi * r_outer * (arc_angle / 360.0)
        
        return PanelFlatPattern(
            panel_id=panel.panel_id,
            r_outer=r_outer, r_inner=r_inner,
            arc_angle=arc_angle,
            sheet_width_flat=strip_width,
            sheet_length_flat=sheet_length + self.config.overlap,
            safe_zone=self.config.safe_zone * 0.6,
            overlap=self.config.overlap,
            panel_type="triangular"
        )

    def _get_trapezoidal_panel(self, panel: PanelDefinition) -> PanelFlatPattern:
        """إفراد لوح شبه منحرف"""
        pitch = self.config.sheet_width
        delta_theta = panel.helix_turn_end - panel.helix_turn_start
        r_avg = (panel.r_start + panel.r_end) / 2.0
        
        helical_len = delta_theta * math.sqrt(r_avg**2 + (pitch / (2 * np.pi))**2)
        
        r_outer = panel.r_end + pitch * 0.5
        r_inner = max(panel.r_start * 0.4, 100.0)
        r_mid = (r_outer + r_inner) / 2.0
        arc_angle = math.degrees(helical_len / r_mid) * 1.1
        
        strip_width = r_outer - r_inner
        sheet_length = 2.0 * np.pi * r_outer * (arc_angle / 360.0)
        
        return PanelFlatPattern(
            panel_id=panel.panel_id,
            r_outer=r_outer, r_inner=r_inner,
            arc_angle=arc_angle,
            sheet_width_flat=strip_width,
            sheet_length_flat=sheet_length + self.config.overlap,
            safe_zone=self.config.safe_zone * 0.8,
            overlap=self.config.overlap,
            panel_type="trapezoidal"
        )

    def _get_short_rectangular_panel(self, panel: PanelDefinition) -> PanelFlatPattern:
        """إفراد لوح مستطيل قصير"""
        flat = self._get_normal_rectangular_panel(panel)
        flat.r_inner = flat.r_inner * 0.85
        flat.arc_angle = flat.arc_angle * 0.95
        flat.panel_type = "short_rect"
        return flat

    def _get_base_rectangular_panel(self, panel: PanelDefinition) -> PanelFlatPattern:
        """إفراد لوح مستطيل قاعدي"""
        flat = self._get_normal_rectangular_panel(panel)
        flat.r_inner = flat.r_inner * 0.92
        flat.arc_angle = flat.arc_angle * 0.97
        flat.panel_type = "base_rect"
        return flat

    def _get_normal_rectangular_panel(self, panel: PanelDefinition) -> PanelFlatPattern:
        """إفراد لوح مستطيل عادي"""
        z_avg = (panel.z_start + panel.z_end) / 2.0
        dist_from_apex = self.cone.r_large_flat - (z_avg / self.cone.height) * (self.cone.r_large_flat - self.cone.r_small_flat)
        
        strip_width_flat = self.config.sheet_width / math.cos(math.radians(self.cone.taper_angle))
        r_outer = dist_from_apex + strip_width_flat / 2.0
        r_inner = dist_from_apex - strip_width_flat / 2.0
        
        pitch = self.config.sheet_width
        r_avg = (panel.r_start + panel.r_end) / 2.0
        delta_theta = panel.helix_turn_end - panel.helix_turn_start
        
        helical_len = delta_theta * math.sqrt(r_avg**2 + (pitch / (2 * np.pi))**2)
        arc_angle_deg = math.degrees(helical_len / dist_from_apex)
        sheet_length = 2.0 * math.pi * r_outer * (arc_angle_deg / 360.0)
        
        return PanelFlatPattern(
            panel_id=panel.panel_id,
            r_outer=r_outer, r_inner=r_inner,
            arc_angle=arc_angle_deg,
            sheet_width_flat=strip_width_flat,
            sheet_length_flat=sheet_length + self.config.overlap,
            safe_zone=self.config.safe_zone,
            overlap=self.config.overlap,
            panel_type="normal"
        )

    # ---------- ملخص ----------

    def get_summary_dict(self) -> dict:
        """ملخص بيانات المخروط والألواح"""
        return {
            "d_top": self.cone.d_top,
            "d_bottom": self.cone.d_bottom,
            "height": self.cone.height,
            "r_top": self.cone.r_top,
            "r_bottom": self.cone.r_bottom,
            "slant_height": self.cone.slant_height,
            "taper_angle_deg": self.cone.taper_angle,
            "arc_angle_deg": self.cone.arc_angle,
            "num_panels": len(self.panels),
            "total_turns": self.cone.height / self.config.sheet_width if self.config.sheet_width > 0 else 0
        }