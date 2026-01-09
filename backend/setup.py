"""
Setup script to compile corrections_fast.pyx to C extension
Run: python setup.py build_ext --inplace
"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

# Define the extension
extensions = [
    Extension(
        name="corrections_fast",
        sources=["corrections_fast.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=[
            "/openmp",  # Enable OpenMP for multi-threading (Windows MSVC)
            "/O2",      # Optimization level 2
        ],
        extra_link_args=[
            "/openmp",  # Link OpenMP
        ],
        language="c++",
    )
]

setup(
    name="corrections_fast",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': "3",
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
        }
    ),
    include_dirs=[np.get_include()],
)
