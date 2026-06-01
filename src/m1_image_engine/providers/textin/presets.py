"""4 个 preset 配置 — 参数不写死在代码里。"""

PRESETS = [
    {
        "name": "A1_default",
        "pipeline": "direct_erase",
        "description": "直接擦除，全部默认参数 (binarization=1 锐化)。回答：开箱即用效果如何。",
        "erase_params": {"crop": 1, "doc_direction": 0, "dewarp": 1, "binarization": 1, "image_type": 1},
    },
    {
        "name": "A2_no_sharpen",
        "pipeline": "direct_erase",
        "description": "直接擦除，关闭官方默认锐化 (binarization=0)。回答：关锐化能否减少残影。",
        "erase_params": {"crop": 1, "doc_direction": 0, "dewarp": 1, "binarization": 0, "image_type": 1},
    },
    {
        "name": "B1_geom_only",
        "pipeline": "enhance_then_erase",
        "description": "前置切边+矫正不增强(enhance_mode=-1)，后置纯擦除。回答：前置切边是否优于A线。",
        "enhance_params": {"enhance_mode": -1, "crop_image": 1, "dewarp_image": 1, "correct_direction": 0, "deblur_image": 0, "jpeg_quality": 95},
        "erase_params": {"crop": 0, "doc_direction": 0, "dewarp": 0, "binarization": 0, "image_type": 1},
    },
    {
        "name": "B2_deshadow",
        "pipeline": "enhance_then_erase",
        "description": "前置切边+矫正+去阴影增强(enhance_mode=5)，后置纯擦除。回答：去阴影是否进一步提升。",
        "enhance_params": {"enhance_mode": 5, "crop_image": 1, "dewarp_image": 1, "correct_direction": 0, "deblur_image": 0, "jpeg_quality": 95},
        "erase_params": {"crop": 0, "doc_direction": 0, "dewarp": 0, "binarization": 0, "image_type": 1},
    },
]
