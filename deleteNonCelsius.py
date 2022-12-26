# -*- coding: utf-8 -*-
"""
Created on Wed Nov  9 09:55:28 2022

@author: ccalvo
"""

import os

root=r'Z:\ANID_Glaciares\DB\LST'

for path, subdirs, files in os.walk(root):
    for name in files:
        if 'celsius' not in name:
            print(os.path.join(path, name))
            os.remove(os.path.join(path, name))
