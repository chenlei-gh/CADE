"""Design source for I_CADEPartToAsm — regenerates production assets.

Metaphor (user-approved, Ultra-3D Master passed 2026-09-17):
  Precision machined engineering assembly:
  TOP    flanged stepped bushing with lead-in chamfer and center bore (part)
  BOTTOM CNC milled housing base with lead-in bore, ribs, socket screws (assembly)
  CENTER coaxial guide with 3D mating vector arrow

Outputs:
  - I_CADEPartToAsm_512.png (512 Master, RGBA Transparent)
  - I_CADEPartToAsm_256.png (256 HD / Documentation, RGBA Transparent)
  - I_CADEPartToAsm_64.png  (64 High-DPI UI, RGBA Transparent)
  - I_CADEPartToAsm_32.png  (32 CATIA Large Mode, RGBA Transparent)
  - I_CADEPartToAsm.png     (22 CATIA Normal Mode, RGBA Transparent)
  - I_CADEPartToAsm.bmp     (22 CATIA Runtime 8-bit indexed BMP, palette 0 = CATIA_BG)
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[2]                      # catia-caa-dev/
REPO = HERE.parents[5]                       # repository root
sys.path.insert(0, str(SKILL / "tools"))
sys.path.insert(0, str(SKILL / "skills"))

from icon_design_lib import draw_gradient_poly, draw_cylinder_shading  # noqa: E402
from icon_provider import _save_palette_bmp, CATIA_BG                  # noqa: E402
from icon_gen_pipeline import lint_bmp_asset, lint_alpha_png, clean_zero_alpha_rgb  # noqa: E402

STEM = "I_CADEPartToAsm"
MASTER_SIZE = 512
SIZE = MASTER_SIZE

# Multi-scale export specification: (size, suffix, description)
EXPORT_SCALES = [
    (512, "_512", "Master 高清透明原稿 (512x512)"),
    (256, "_256", "高清/文档展示 (256x256)"),
    (64,  "_64",  "中大图标 / 高分屏 UI (64x64)"),
    (32,  "_32",  "CATIA Large 模式 (32x32)"),
    (22,  "",     "CATIA Normal 模式 (22x22 PNG + BMP)"),
]


def build_ultra_3d_master():
    master = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # 1. 深度柔和接触阴影
    shadow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.polygon([(60, 445), (256, 498), (460, 435), (390, 375), (110, 385)], fill=(0, 0, 0, 95))
    sd.ellipse([(175, 235), (337, 295)], fill=(0, 0, 0, 135))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))

    # 2. 精密铣削合金装配基座
    base_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base_layer)
    base_top = [(55, 292), (256, 180), (457, 292), (256, 404)]
    draw_gradient_poly(base_layer, base_top, (245, 248, 254, 255), (165, 175, 192, 255))
    base_left = [(55, 292), (256, 404), (256, 465), (55, 355)]
    draw_gradient_poly(base_layer, base_left, (155, 166, 180, 255), (98, 108, 122, 255))
    base_right = [(256, 404), (457, 292), (457, 355), (256, 465)]
    draw_gradient_poly(base_layer, base_right, (110, 120, 134, 255), (65, 72, 85, 255))

    # 结构加强筋
    rib_l = [(125, 330), (145, 340), (145, 395), (125, 385)]
    draw_gradient_poly(base_layer, rib_l, (180, 190, 205, 255), (110, 120, 135, 255))
    bd.polygon(rib_l, outline=(24, 16, 82, 180), width=2)
    rib_r = [(367, 340), (387, 330), (387, 385), (367, 395)]
    draw_gradient_poly(base_layer, rib_r, (135, 145, 160, 255), (75, 85, 100, 255))
    bd.polygon(rib_r, outline=(24, 16, 82, 180), width=2)

    # 沉头螺栓与配合孔
    for bx, by in [(110, 292), (256, 210), (402, 292), (256, 372)]:
        bd.ellipse([(bx - 17, by - 10), (bx + 17, by + 10)], fill=(125, 135, 150, 255), outline=(24, 16, 82, 220), width=2)
        bd.ellipse([(bx - 14, by - 8), (bx + 14, by + 8)], fill=(255, 255, 255, 180))
        bd.ellipse([(bx - 12, by - 7), (bx + 12, by + 7)], fill=(30, 35, 45, 255))
        bd.ellipse([(bx - 8, by - 5), (bx + 8, by + 5)], fill=(160, 170, 185, 255), outline=(24, 16, 82, 200))
        bd.ellipse([(bx - 4, by - 3), (bx + 4, by + 3)], fill=(15, 18, 25, 255))

    bore_cx, bore_cy = 256, 292
    bd.ellipse([(bore_cx - 68, bore_cy - 37), (bore_cx + 68, bore_cy + 37)], fill=(130, 140, 158, 255), outline=(24, 16, 82, 220), width=2)
    bd.ellipse([(bore_cx - 62, bore_cy - 33), (bore_cx + 62, bore_cy + 33)], fill=(255, 255, 255, 200))
    bore_wall = [(bore_cx - 54, bore_cy), (bore_cx + 54, bore_cy), (bore_cx + 54, bore_cy + 52), (bore_cx - 54, bore_cy + 52)]
    draw_gradient_poly(base_layer, bore_wall, (32, 38, 50, 255), (8, 10, 16, 255))
    bd.ellipse([(bore_cx - 54, bore_cy - 28), (bore_cx + 54, bore_cy + 28)], fill=(18, 22, 30, 255))

    bd.line([(55, 292), (256, 180), (457, 292)], fill=(255, 255, 255, 255), width=5)
    bd.line([(55, 292), (256, 404)], fill=(255, 255, 255, 240), width=5)
    bd.line([(256, 404), (256, 465)], fill=(255, 255, 255, 220), width=4)
    bd.line([(55, 292), (256, 180), (457, 292), (457, 355), (256, 465), (55, 355), (55, 292)], fill=(24, 16, 82, 255), width=4)
    bd.line([(256, 404), (457, 292)], fill=(24, 16, 82, 240), width=3)
    bd.line([(55, 355), (256, 465)], fill=(24, 16, 82, 240), width=3)

    # 3. 零件
    part_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pd = ImageDraw.Draw(part_layer)
    pcx, p_top_y, p_mid_y, p_bot_y = 256, 60, 152, 236
    C_BASE, C_SPEC, C_SHADOW, C_RIM = (255, 210, 30), (255, 255, 210), (165, 110, 5), (230, 180, 50)

    r_bot = 48
    draw_cylinder_shading(part_layer, pcx, p_mid_y, p_bot_y, r_bot, C_BASE, C_SPEC, C_SHADOW, C_RIM)
    pd.arc([(pcx - r_bot, p_bot_y - 22), (pcx + r_bot, p_bot_y + 22)], start=0, end=180, fill=(24, 16, 82, 255), width=3)
    pd.line([(pcx - r_bot, p_mid_y), (pcx - r_bot, p_bot_y)], fill=(24, 16, 82, 255), width=3)
    pd.line([(pcx + r_bot, p_mid_y), (pcx + r_bot, p_bot_y)], fill=(24, 16, 82, 255), width=3)

    kw_pts = [(pcx - 12, p_mid_y + 12), (pcx + 12, p_mid_y + 12), (pcx + 12, p_bot_y - 15), (pcx - 12, p_bot_y - 15)]
    draw_gradient_poly(part_layer, kw_pts, (110, 70, 0, 255), (60, 35, 0, 255))
    pd.polygon(kw_pts, outline=(24, 16, 82, 220), width=2)

    r_flange, h_flange = 76, 28
    draw_cylinder_shading(part_layer, pcx, p_mid_y - h_flange, p_mid_y, r_flange, C_BASE, C_SPEC, C_SHADOW, C_RIM)
    pd.arc([(pcx - r_flange, p_mid_y - 34), (pcx + r_flange, p_mid_y + 12)], start=0, end=180, fill=(24, 16, 82, 255), width=3)
    pd.line([(pcx - r_flange, p_mid_y - h_flange), (pcx - r_flange, p_mid_y)], fill=(24, 16, 82, 255), width=3)
    pd.line([(pcx + r_flange, p_mid_y - h_flange), (pcx + r_flange, p_mid_y)], fill=(24, 16, 82, 255), width=3)

    for fx in [pcx - 52, pcx + 52]:
        pd.ellipse([(fx - 9, p_mid_y - h_flange + 3), (fx + 9, p_mid_y - h_flange + 15)], fill=(120, 80, 5, 255), outline=(24, 16, 82, 220), width=2)
        pd.ellipse([(fx - 6, p_mid_y - h_flange + 5), (fx + 6, p_mid_y - h_flange + 13)], fill=(40, 25, 0, 255))

    r_top = 56
    draw_cylinder_shading(part_layer, pcx, p_top_y, p_mid_y - h_flange, r_top, C_BASE, C_SPEC, C_SHADOW, C_RIM)
    pd.line([(pcx - r_top, p_top_y), (pcx - r_top, p_mid_y - h_flange)], fill=(24, 16, 82, 255), width=3)
    pd.line([(pcx + r_top, p_top_y), (pcx + r_top, p_mid_y - h_flange)], fill=(24, 16, 82, 255), width=3)
    pd.ellipse([(pcx - r_top, p_top_y - 26), (pcx + r_top, p_top_y + 26)], fill=(255, 255, 215, 255), outline=(24, 16, 82, 255), width=3)
    pd.ellipse([(pcx - 26, p_top_y - 13), (pcx + 26, p_top_y + 13)], fill=(25, 18, 5, 255), outline=(24, 16, 82, 255), width=2)

    pd.line([(pcx - 22, p_top_y + 8), (pcx - 22, p_mid_y - h_flange - 4)], fill=(255, 255, 255, 240), width=4)
    pd.line([(pcx - 28, p_mid_y - h_flange + 3), (pcx - 28, p_mid_y - 3)], fill=(255, 255, 255, 240), width=4)
    pd.line([(pcx - 18, p_mid_y + 3), (pcx - 18, p_bot_y - 3)], fill=(255, 255, 255, 230), width=3)
    pd.arc([(pcx - r_top, p_top_y - 26), (pcx + r_top, p_top_y + 26)], start=180, end=360, fill=(255, 255, 255, 255), width=4)

    # 4. 箭头与指示线
    arrow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arrow_layer)
    for y in range(int(p_mid_y + 15), int(bore_cy + 15), 16):
        ad.line([(pcx, y), (pcx, y + 10)], fill=(255, 255, 255, 240), width=5)
        ad.line([(pcx, y), (pcx, y + 10)], fill=(230, 30, 30, 255), width=3)

    arrow_pts = [
        (pcx, bore_cy + 16),
        (pcx - 36, bore_cy - 30),
        (pcx - 14, bore_cy - 26),
        (pcx - 14, bore_cy - 65),
        (pcx + 14, bore_cy - 65),
        (pcx + 14, bore_cy - 26),
        (pcx + 36, bore_cy - 30)
    ]
    draw_gradient_poly(arrow_layer, arrow_pts, (255, 55, 55, 255), (180, 15, 15, 255))
    ad.polygon(arrow_pts, outline=(24, 16, 82, 255), width=3)
    ad.line([(pcx, bore_cy + 16), (pcx - 36, bore_cy - 30), (pcx - 14, bore_cy - 26), (pcx - 14, bore_cy - 65)], fill=(255, 195, 195, 255), width=3)

    master.paste(shadow_layer, (0, 0), shadow_layer)
    master.paste(base_layer, (0, 0), base_layer)
    master.paste(part_layer, (0, 0), part_layer)
    master.paste(arrow_layer, (0, 0), arrow_layer)
    return master


def export_multi_scale_assets(master: Image.Image, out_dir: Path) -> dict:
    """Unified multi-scale export pipeline with strict engineering validation."""
    assert master.size == (MASTER_SIZE, MASTER_SIZE), f"Master must be {MASTER_SIZE}x{MASTER_SIZE}"
    assert master.mode == "RGBA", "Master must be RGBA mode"

    out_dir.mkdir(parents=True, exist_ok=True)
    generated_files = {}

    for size, suffix, desc in EXPORT_SCALES:
        resampled = master if size == MASTER_SIZE else master.resize((size, size), Image.Resampling.LANCZOS)
        resampled = clean_zero_alpha_rgb(resampled)

        # 1. 导出透明 PNG
        png_path = out_dir / f"{STEM}{suffix}.png"
        resampled.save(png_path)
        generated_files[f"png_{size}"] = png_path

        # 2. 如果是 22x22 Normal 尺寸，增补导出 CATIA 兼容 8-bit indexed BMP
        if size == 22:
            canvas_bg = Image.new("RGB", (22, 22), CATIA_BG)
            canvas_bg.paste(resampled, (0, 0), resampled)
            # 量化到 <= 16 色以严格对齐 CATIA 8-bit palettized 资源上限
            canvas_bg_quant = canvas_bg.quantize(
                colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
            ).convert("RGB")
            bmp_path = out_dir / f"{STEM}.bmp"
            _save_palette_bmp(canvas_bg_quant, bmp_path)
            generated_files["bmp_22"] = bmp_path

    # 3. 严格验证断言与同步真实度量数据
    lint_data = _verify_generated_assets(generated_files)
    update_provenance_json(lint_data)
    return generated_files, lint_data


def _verify_generated_assets(assets: dict) -> dict:
    """Verify all generated assets conform to CADE v3 specs using unified engineering lints."""
    # 1. Existence and basic format
    for key, path in assets.items():
        assert path.exists(), f"Missing expected output: {path}"
        assert path.stat().st_size > 0, f"Empty asset file: {path}"

    # 2. Unified Alpha PNG Linting across ALL exported scales (512, 256, 64, 32, 22)
    alpha_reports = {}
    for key, path in assets.items():
        if key.startswith("png_"):
            report = lint_alpha_png(path)
            assert report["has_transparency"], f"{path.name} has no transparency"
            assert report["corners_alpha_zero"], f"{path.name} four corners must have Alpha == 0"
            assert report["alpha_clean"], f"{path.name} Alpha channel failed cleanliness check: {report}"
            alpha_reports[key] = report

    # 3. Unified BMP Linting on 22x22 Normal BMP
    bmp_path = assets["bmp_22"]
    bmp_report = lint_bmp_asset(bmp_path)
    assert bmp_report["pass"], f"{bmp_path.name} failed hard engineering gate: {bmp_report['hard_checks']}"

    return {
        "bmp_lint": bmp_report,
        "alpha_lint": alpha_reports.get("png_512", {}),
        "alpha_reports_by_scale": alpha_reports,
    }


def update_provenance_json(lint_results: dict) -> None:
    """Synchronize genuine measured verification metrics into provenance JSON."""
    json_path = HERE / f"{STEM}.json"
    if not json_path.exists():
        return
    data = json.loads(json_path.read_text(encoding="utf-8"))

    bmp_lint = lint_results["bmp_lint"]
    alpha_lint = lint_results["alpha_lint"]
    alpha_by_scale = lint_results.get("alpha_reports_by_scale", {})

    all_scales_clean = (
        all(r["alpha_clean"] for r in alpha_by_scale.values())
        if alpha_by_scale
        else alpha_lint["alpha_clean"]
    )

    data["gate"] = {
        "master_size": f"{MASTER_SIZE}x{MASTER_SIZE}",
        "scales": [512, 256, 64, 32, 22],
        "bmp_mode": "8-bit indexed (palette 0 = CATIA_BG)",
        "bmp_colors": bmp_lint["colors"],
        "hard_checks": bmp_lint["hard_checks"],
        "fg_ratio": bmp_lint["soft_lints"]["fg_ratio"],
        "fg_in_guidance": bmp_lint["soft_lints"]["fg_in_guidance"],
        "isolated_noise_px": bmp_lint["soft_lints"]["isolated_noise_px"],
        "alpha_clean": all_scales_clean,
        "alpha_clean_definition": "All four corners 100% transparent (A=0) and zero RGB contamination on A=0 pixels across all exported PNG scales",
        "alpha_measured_by_scale": {
            k.replace("png_", ""): {
                "size": r["size"],
                "corners_alpha_zero": r["corners_alpha_zero"],
                "dirty_zero_alpha_pixels": r["dirty_zero_alpha_pixels"],
                "semi_transparent_ratio": r["semi_transparent_ratio"],
                "alpha_clean": r["alpha_clean"],
            }
            for k, r in alpha_by_scale.items()
        },
    }
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    master_img = build_ultra_3d_master()
    results, lint_data = export_multi_scale_assets(master_img, HERE)

    print(f"[PASS] {STEM} Ultra-3D multi-scale assets regenerated and verified:")
    for size, suffix, desc in EXPORT_SCALES:
        p = results[f"png_{size}"]
        print(f"  - {desc:32s}: {p.name}")
    print(f"  - CATIA Normal BMP (8-bit indexed) : {results['bmp_22'].name}")
    print(f"  - Unified BMP Lint : Hard Gates PASS, fg={lint_data['bmp_lint']['soft_lints']['fg_ratio']:.1%}, colors={lint_data['bmp_lint']['colors']}")
    print(f"  - Unified Alpha Lint: alpha_clean={lint_data['alpha_lint']['alpha_clean']}, dirty_zero_px={lint_data['alpha_lint']['dirty_zero_alpha_pixels']}")
