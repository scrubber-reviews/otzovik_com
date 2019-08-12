# -*- coding: utf-8 -*-

"""Top-level package for Otzovik com."""
from .otzovik_com import OtzovikCom, Rating

__author__ = """NMelis"""
__email__ = 'melis.zhoroev@gmail.com'
__version__ = '0.1.7'
__name__ = 'Отзовик'
__slug_img_link__ = 'https://i.ibb.co/jfyL3hK/image.png'
__how_get_slug__ = """
Slug это https://otzovik.com/reviews/ТО_ЧТО_ЗДЕСЬ/ (без слешей "/")
<img src="{}" alt="image" border="0">
""".format(__slug_img_link__)


provider = OtzovikCom
rating = Rating
