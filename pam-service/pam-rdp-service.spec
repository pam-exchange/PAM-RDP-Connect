# -*- mode: python ; coding: utf-8 -*-
# pam_rdp_service.spec
# This is a PyInstaller spec file for compiling the PAM RDP Service

block_cipher = None

a = Analysis(['src/pam-rdp-service.py'],
             pathex=['.'],
             binaries=[],
             datas=[('src/pam-rdp-service.properties', '.')],
             hiddenimports=['win32timezone', 'psutil'],
			 hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='PAMRDPService',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='PAMRDPService')