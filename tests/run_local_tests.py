"""
run_local_tests.py
Script auxiliar para ejecutar pruebas locales de los modulos de src.
Permite probar la lectura del ultimo correo sin escribir argumentos cada vez.
"""

import os
import sys
import subprocess

# Asegurar que src/ esta en el path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Ejecutar read_gmail.py en modo --last
cmd = [sys.executable, "src/gmail/read_gmail.py", "--last"]
subprocess.run(cmd)