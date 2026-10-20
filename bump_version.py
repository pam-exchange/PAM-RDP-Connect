#!/usr/bin/env python
import os
import sys

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    no_inc = '--no-increment' in sys.argv or '-n' in sys.argv
    version_file = os.path.join(script_dir, 'version')

    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8') as f:
            v = f.read().strip()
    else:
        v = '2.9.0.0'

    parts = v.split('.')
    if not no_inc:
        if len(parts) >= 4:
            parts = parts[:3] + [str(int(parts[3]) + 1)]
        elif len(parts) == 3:
            parts = parts[:3] + ['1']
        else:
            parts = ['2', '9', '0', '1']
        new_v = '.'.join(parts)
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(new_v + '\n')
    else:
        new_v = v
        while len(parts) < 4:
            parts.append('0')

    v_tuple = tuple(int(p) for p in parts[:4])
    prod_tuple = v_tuple[:3]
    prod_v = '.'.join(str(p) for p in prod_tuple)

    rc_content = f'''#include <windows.h>

VS_VERSION_INFO VERSIONINFO
FILEVERSION    {v_tuple[0]},{v_tuple[1]},{v_tuple[2]},{v_tuple[3]}
PRODUCTVERSION {v_tuple[0]},{v_tuple[1]},{v_tuple[2]},{v_tuple[3]}
FILEFLAGSMASK  0x3fL
#ifdef _DEBUG
FILEFLAGS      0x1L
#else
FILEFLAGS      0x0L
#endif
FILEOS         0x40004L
FILETYPE       0x1L
FILESUBTYPE    0x0L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0"
        BEGIN
            VALUE "CompanyName",      "PAM-Exchange"
            VALUE "FileDescription",  "PAM-RDP-Connect Service"
            VALUE "FileVersion",      "{new_v}"
            VALUE "InternalName",     "pam-rdp-service"
            VALUE "LegalCopyright",   "Copyright (c) 2024-2026 PAM-Exchange"
            VALUE "OriginalFilename", "pam-rdp-service.exe"
            VALUE "ProductName",      "PAM RDP Connect"
            VALUE "ProductVersion",   "{prod_v}"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x0409, 1200
    END
END
'''
    rc_path = os.path.join(script_dir, 'pam-rdp-service', 'src', 'pam-rdp-service.rc')
    if os.path.exists(os.path.dirname(rc_path)):
        with open(rc_path, 'w', encoding='utf-8') as f:
            f.write(rc_content)

    ver_txt_1 = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v_tuple},
    prodvers={v_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'PAM-Exchange'),
            StringStruct('FileDescription', 'PAM RDP Connect Application'),
            StringStruct('FileVersion', '{new_v}'),
            StringStruct('InternalName', 'pam-rdp'),
            StringStruct('LegalCopyright', 'Copyright (c) 2024-2026 PAM-Exchange'),
            StringStruct('OriginalFilename', 'pam-rdp.exe'),
            StringStruct('ProductName', 'PAM RDP Connect'),
            StringStruct('ProductVersion', '{prod_v}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    txt1_path = os.path.join(script_dir, 'pam-rdp', 'src', 'pam-rdp-version.txt')
    if os.path.exists(os.path.dirname(txt1_path)):
        with open(txt1_path, 'w', encoding='utf-8') as f:
            f.write(ver_txt_1)

    ver_txt_2 = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v_tuple},
    prodvers={v_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'PAM-Exchange'),
            StringStruct('FileDescription', 'PAM RDP Connect Configuration GUI'),
            StringStruct('FileVersion', '{new_v}'),
            StringStruct('InternalName', 'pam-rdp-config'),
            StringStruct('LegalCopyright', 'Copyright (c) 2024-2026 PAM-Exchange'),
            StringStruct('OriginalFilename', 'pam-rdp-config.exe'),
            StringStruct('ProductName', 'PAM RDP Connect Configuration'),
            StringStruct('ProductVersion', '{prod_v}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    txt2_path = os.path.join(script_dir, 'pam-rdp-config', 'src', 'pam-rdp-config-version.txt')
    if os.path.exists(os.path.dirname(txt2_path)):
        with open(txt2_path, 'w', encoding='utf-8') as f:
            f.write(ver_txt_2)

    print(new_v)

if __name__ == '__main__':
    main()
