# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('index.html', '.'), ('static', 'static'), ('models', 'models')]
binaries = []
hiddenimports = ['scipy.special.cython_special']
tmp_ret = collect_all('mediapipe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'fontTools', 'jax', 'jaxlib', 'matplotlib', 
        'contourpy', 'kiwisolver', 'pyparsing', 'cycler',
        'openpyxl', 'playwright', 'reportlab', 'unittest.mock'
    ],
    noarchive=False,
    optimize=0,
)

# 1. Filter out unused Mediapipe .tflite model files (pose, hand, iris, palm, selfie, holistic)
filtered_datas = []
for dest, source, type_ in a.datas:
    if 'mediapipe' in source.lower() and 'modules' in source.lower() and source.endswith('.tflite'):
        if not any(x in source.lower() for x in ['face_detection', 'face_landmark', 'face_geometry']):
            continue
    filtered_datas.append((dest, source, type_))
a.datas = filtered_datas

# 2. Filter out OpenCV FFMPEG video I/O extension binary (since we only cull photos)
a.binaries = [x for x in a.binaries if 'opencv_videoio_ffmpeg' not in x[0].lower() and 'opencv_videoio_ffmpeg' not in x[1].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='QuantileCull_1.2.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['static\\favicon.ico'],
)
