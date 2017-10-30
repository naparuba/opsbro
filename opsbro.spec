# -*- mode: python -*-

import glob
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

block_cipher = None


core_hiddenimports = collect_submodules( 'opsbro' )

packs_hiddenimports = []
for module_dir in glob.glob('data/*/*/*/module'):
   packs_hiddenimports.extend( collect_submodules( module_dir) )

all_hidden = core_hiddenimports + packs_hiddenimports

all_hidden.append('commands')


print "All hidden", all_hidden

a = Analysis(['bin/opsbro'],
             pathex=['./opsbro'],
             binaries=[],
             datas=[],
             hiddenimports=all_hidden,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='opsbro_exe',
          debug=False,
          strip=False,
          upx=False,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='opsbro-exe')
